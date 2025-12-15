# 시스템 아키텍처

## 전체 시스템 흐름도

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        batch_get_all_models.py                          │
│   (여러 사용자 URL을 순차 처리, subprocess로 get_all_models.py 호출)    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          get_all_models.py                              │
│                      (사용자 전체 모델 일괄 처리)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  1. URL에서 username 추출                                               │
│  2. CivitAI API로 모델 목록 수집 (v1 + TRPC 병합)                       │
│  3. 각 모델별로:                                                        │
│     - 모델 메타파일 생성 (JSON + TXT)                                   │
│     - 포스트 ID 추출                                                    │
│     - process_post_to_dir() 호출                                        │
│  4. IDM 다운로드 시작                                                   │
│  5. 모든 비동기 작업 대기                                               │
│  6. 다운로드 검증 + 로그 저장                                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            get_model.py                                 │
│                       (단일 포스트 처리 핵심)                            │
├─────────────────────────────────────────────────────────────────────────┤
│  _process_post_core(post_id, save_dir):                                 │
│    1. 포스트 제목 + modelVersionId 추출                                 │
│    2. 이미지 목록 수집 (image.getInfinite API)                          │
│    3. LoRA 비동기 처리 (BG_LORA_EXECUTOR)                               │
│    4. 각 이미지별:                                                      │
│       - 중복 체크 (성공 로그 + 로컬 파일)                               │
│       - IDM 대기열 추가                                                 │
│       - 메타데이터 비동기 생성 (IMG_META_EXECUTOR)                      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
┌─────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  thread_pool.py │  │  download_state.py  │  │   Filter_*.txt      │
│                 │  │                     │  │                     │
│ IMG_META_EXECUTOR│  │ 다운로드 성공/실패 │  │ 프롬프트 필터링     │
│ (max_workers=1) │  │ 로그 관리          │  │ 단어 목록           │
│                 │  │                     │  │                     │
│ BG_LORA_EXECUTOR│  │ - is_success()     │  │ - SEX_FILTER        │
│ (max_workers=4) │  │ - mark_success()   │  │ - CLOTHES_FILTER    │
└─────────────────┘  │ - mark_failed()    │  │ - ETC_FILTER        │
                     └─────────────────────┘  └─────────────────────┘
                                 │
                                 ▼
                     ┌─────────────────────┐
                     │        IDM          │
                     │  (다운로드 수행)    │
                     │                     │
                     │ /a: 대기열 추가     │
                     │ /s: 다운로드 시작   │
                     └─────────────────────┘
```

---

## 모듈 간 의존성 관계

```
┌────────────────────────────────────────────────────────────────┐
│                    batch_get_all_models.py                     │
│                     (독립 프로세스 실행)                        │
└──────────────────────────┬─────────────────────────────────────┘
                           │ subprocess.run()
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                      get_all_models.py                         │
├────────────────────────────────────────────────────────────────┤
│ imports:                                                        │
│   - get_model (process_post_to_dir, safe_get, parse_cookie,    │
│                set_future_lists, set_download_targets,          │
│                idm_start_download, USERS_ROOT, POSTS_ROOT)     │
│   - thread_pool (IMG_META_EXECUTOR, BG_LORA_EXECUTOR)          │
│   - download_state (load_download_log, save_download_log,      │
│                     is_success, mark_failed)                   │
└──────────────────────────┬─────────────────────────────────────┘
                           │ import
                           ▼
┌────────────────────────────────────────────────────────────────┐
│                         get_model.py                           │
├────────────────────────────────────────────────────────────────┤
│ imports:                                                        │
│   - thread_pool (IMG_META_EXECUTOR, BG_LORA_EXECUTOR)          │
│   - download_state (is_success, mark_success, mark_failed)     │
│                                                                 │
│ 외부 주입 시스템:                                               │
│   - set_future_lists(img_list, lora_list)                      │
│   - set_download_targets(target_list)                          │
└────────────────────────────────────────────────────────────────┘
                           │ import
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  thread_pool.py                  │  download_state.py          │
├──────────────────────────────────┼─────────────────────────────┤
│  IMG_META_EXECUTOR               │  downloaded_records (dict)  │
│  BG_LORA_EXECUTOR                │  download_log (dict)        │
│                                  │  _log_lock (threading.Lock) │
└──────────────────────────────────┴─────────────────────────────┘
```

---

## 순환 import 방지 패턴

`get_model.py`와 `get_all_models.py` 간 순환 참조를 방지하기 위해 **전역 리스트 주입 패턴**을 사용합니다.

### 문제 상황
- `get_all_models.py`는 `get_model.py`의 `process_post_to_dir()`을 호출해야 함
- `get_model.py`는 비동기 작업 결과를 `get_all_models.py`의 리스트에 추가해야 함
- 서로 import하면 순환 참조 발생

### 해결 방법 (get_model.py)
```python
# 전역 변수 (초기값 None)
IMG_META_FUTURES = None
LORA_FUTURES = None
DOWNLOAD_TARGETS = None

# 주입 함수
def set_future_lists(img_list, lora_list):
    global IMG_META_FUTURES, LORA_FUTURES
    IMG_META_FUTURES = img_list
    LORA_FUTURES = lora_list

def set_download_targets(target_list):
    global DOWNLOAD_TARGETS
    DOWNLOAD_TARGETS = target_list
```

### 사용 방법 (get_all_models.py)
```python
from get_model import set_future_lists, set_download_targets

# 리스트 정의
IMG_META_FUTURES = []
LORA_FUTURES = []
DOWNLOAD_TARGETS = []

# get_model.py에 주입
set_future_lists(IMG_META_FUTURES, LORA_FUTURES)
set_download_targets(DOWNLOAD_TARGETS)
```

---

## 멀티스레딩 아키텍처

### 스레드 풀 구성

| Executor | max_workers | 용도 | 이유 |
|----------|-------------|------|------|
| IMG_META_EXECUTOR | 1 | 이미지 메타데이터 생성 | 429 오류 방지 (API 호출 포함) |
| BG_LORA_EXECUTOR | 4 | LoRA 다운로드 및 후처리 | 파일 I/O가 주요 작업 |

### 비동기 작업 흐름

```
메인 스레드
    │
    ├─> IMG_META_EXECUTOR.submit(async_process_image_meta, ...)
    │       │
    │       └─> Future → IMG_META_FUTURES 리스트에 추가
    │
    ├─> BG_LORA_EXECUTOR.submit(process_lora_task, ...)
    │       │
    │       └─> Future → LORA_FUTURES 리스트에 추가
    │
    ▼
모든 모델 처리 완료 후
    │
    ├─> as_completed(IMG_META_FUTURES) - 이미지 메타 작업 대기
    │       (타임아웃: 작업당 5분)
    │
    └─> as_completed(LORA_FUTURES) - LoRA 작업 대기
            (타임아웃: 작업당 10분)
```

---

## IDM 연동 아키텍처

### IDM 명령어 인터페이스

```python
IDM_PATH = r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe"

# 대기열 추가 (다운로드 시작 안 됨)
cmd = f'"{IDM_PATH}" /d "{url}" /p "{save_dir}" /f "{file_name}" /a'

# 대기열 다운로드 시작
cmd = f'"{IDM_PATH}" /s'
```

### 대기열 관리

```python
IDM_QUEUE_COUNTER = 0      # 대기열에 추가된 파일 수
IDM_COUNTER_LOCK = Lock()  # 스레드 안전 보장

def idm_add_to_queue(url, save_dir, file_name):
    # 대기열 추가 + 카운터 증가
    ...

def idm_start_download():
    # 대기열이 비어있지 않으면 다운로드 시작 + 카운터 초기화
    ...

def idm_get_queue_size():
    # 현재 대기열 크기 반환
    ...
```

### 다운로드 타이밍

1. **모델별 처리 완료 후**: 각 모델 처리 후 대기열이 있으면 즉시 다운로드 시작
2. **전체 처리 완료 후**: 남은 대기열이 있으면 마지막으로 다운로드 시작

```python
# 각 모델 처리 완료 후
queue_size = idm_get_queue_size()
if queue_size > 0:
    idm_start_download()

# 전체 처리 완료 후
remaining_queue = idm_get_queue_size()
if remaining_queue > 0:
    idm_start_download()
```

---

## 데이터 흐름

### 1. 모델 수집 단계

```
CivitAI API
    │
    ├─> /api/v1/models?username={username}
    │       └─> 모델 기본 정보 (id, name, modelVersions)
    │
    └─> /api/trpc/model.getAll
            └─> 추가 모델 정보 (TRPC 전용 필드)
                │
                ▼
            모델 목록 병합 (id 기준 중복 제거)
```

### 2. 포스트 ID 추출 단계

```
모델 데이터
    │
    ├─> model.images[].id → imageId 추출
    │       │
    │       └─> /images/{imageId} HTML 파싱
    │               │
    │               └─> __NEXT_DATA__ JSON에서 postId 추출
    │
    └─> modelVersions[].images[].id (fallback)
```

### 3. 이미지 다운로드 단계

```
포스트 ID
    │
    ▼
/api/trpc/image.getInfinite?postId={postId}
    │
    └─> 이미지 목록 (id, url/uuid)
            │
            ├─> 중복 체크 (download_state.is_success)
            │
            ├─> 이미지 URL 생성
            │       https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/{uuid}/original=true/{uuid}.jpeg
            │
            └─> IDM 대기열 추가
```

### 4. 메타데이터 추출 단계

```
이미지 ID
    │
    ▼
/api/trpc/image.getGenerationData
    │
    └─> 생성 데이터 (meta.prompt, meta.negativePrompt, etc.)
            │
            ├─> raw_prompt 저장
            │
            ├─> 프롬프트 필터링
            │       ├─> SEX_FILTER + CLOTHES_FILTER + ETC_FILTER
            │       │       └─> prompt 필드
            │       │
            │       └─> SEX_FILTER + ETC_FILTER만
            │               └─> prompt_with_clothes 필드
            │
            └─> {imageId}.txt 파일 저장 (JSON)
```

---

## 오류 처리 전략

### Rate Limiting (429 오류)

```python
def safe_get(url, retries=5, **kwargs):
    for attempt in range(retries):
        with REQUEST_LOCK:
            # 최소 1.5초 간격 대기
            wait_time = REQUEST_INTERVAL - (time.time() - LAST_REQUEST_TIME)
            if wait_time > 0:
                time.sleep(wait_time)

            response = session.get(url, **kwargs)

        if response.status_code != 429:
            return response

        # 429 시 exponential backoff
        backoff = min(2 ** attempt, 60)
        time.sleep(backoff)
```

### 다운로드 실패 처리

1. **실패 기록**: `download_state.mark_failed(id, type, reason, info)`
2. **재시도 시 체크**: `download_state.is_success(id, type)` - 실패한 것은 재다운로드
3. **검증 단계**: `verify_all_downloads()` - 파일 존재 및 크기 확인

### 스레드 작업 타임아웃

```python
# 이미지 메타: 작업당 5분
for future in as_completed(IMG_META_FUTURES, timeout=300 * total_tasks):
    try:
        future.result(timeout=300)
    except TimeoutError:
        # 타임아웃 처리
        ...

# LoRA: 작업당 10분
for future in as_completed(LORA_FUTURES, timeout=600 * total_tasks):
    try:
        future.result(timeout=600)
    except TimeoutError:
        # 타임아웃 처리
        ...
```
