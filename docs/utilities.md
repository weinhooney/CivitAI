# 유틸리티 스크립트 가이드

## 개요

메인 다운로드 시스템 외에 프롬프트 처리, 배치 실행 등을 위한 유틸리티 스크립트들입니다.

---

## batch_get_all_models.py

### 목적
여러 CivitAI 사용자 URL을 한 번에 순차 처리합니다.

### 파일 위치
`E:\CivitAI Workspace\batch_get_all_models.py`

### URL 목록 파일
`get_all_models_urls.txt` - 한 줄에 하나씩 URL 작성

```text
# 주석 (# 으로 시작하는 줄은 무시)
https://civitai.com/user/user1/models
https://civitai.com/user/user2/models
https://civitai.com/user/user3/models
```

### 사용법

```bash
python batch_get_all_models.py
```

### 동작 방식

```python
def run_get_all_models_for_url(get_all_path: str, url: str) -> int:
    """
    get_all_models.py를 별도 프로세스로 실행

    동작:
        1. subprocess.run()으로 get_all_models.py 실행
        2. 표준 입력에 URL 전달
        3. exit code 반환
    """
```

### 흐름도

```
batch_get_all_models.py
    │
    ├─> get_all_models_urls.txt 읽기
    │
    └─> 각 URL에 대해:
            │
            └─> subprocess.run(["python", "get_all_models.py"], input=url)
                    │
                    └─> get_all_models.py 실행 (독립 프로세스)
```

---

## download_state.py

### 목적
다운로드 성공/실패 상태를 관리하고 중복 다운로드를 방지합니다.

### 파일 위치
`E:\CivitAI Workspace\download_state.py`

### 전역 변수

```python
# 예전 방식 (다운로드된 파일 목록)
downloaded_records = {
    "lora": [],
    "images": []
}

# 새 통합 다운로드 로그
download_log = {
    "success": [],  # [{"id": int, "type": str, "path": str, "size": int}]
    "failed": [],   # [{"id": int, "type": str, "reason": str, "info": dict}]
}

_log_lock = threading.Lock()  # 스레드 안전 보장
```

### 주요 함수

#### is_success

```python
def is_success(file_id: int, file_type: str) -> bool:
    """
    해당 파일이 성공 목록에 있는지 확인

    파라미터:
        file_id: 이미지 ID 또는 model_version_id
        file_type: "image" 또는 "lora"
    """
```

#### mark_success

```python
def mark_success(file_id: int, file_type: str, path: str, size: int):
    """
    성공 기록 추가

    동작:
        1. 실패 기록에서 해당 항목 제거
        2. 이미 성공 기록에 있으면 path/size 갱신
        3. 없으면 새로 추가
    """
```

#### mark_failed

```python
def mark_failed(file_id: int, file_type: str, reason: str, info: dict = None):
    """
    실패 기록 추가

    동작:
        1. 기존 실패 기록에서 같은 항목 제거
        2. 새 실패 기록 추가

    reason 예시:
        - "uuid_not_found"
        - "missing"
        - "corrupted"
        - "presigned_url_failed"
        - "timeout"
        - "copy_failed"
    """
```

#### load_download_log

```python
def load_download_log(username: str):
    """
    프로그램 시작 시 다운로드 로그 파일 로드

    파일 경로: download_logs/{username}/{username}_download_log.json
    """
```

#### save_download_log

```python
def save_download_log(username: str):
    """
    모든 작업 완료 후 다운로드 로그 저장

    파일 경로: download_logs/{username}/{username}_download_log.json
    """
```

### 로그 파일 형식

```json
{
  "success": [
    {
      "id": 12345678,
      "type": "image",
      "path": "E:\\CivitAI\\Users\\user\\Model\\12345678.jpeg",
      "size": 524288
    },
    {
      "id": 987654,
      "type": "lora",
      "path": "E:\\CivitAI\\Users\\user\\Model\\model.safetensors",
      "size": 134217728
    }
  ],
  "failed": [
    {
      "id": 11111111,
      "type": "image",
      "reason": "missing",
      "info": {
        "expected_file_path": "...",
        "download_url": "..."
      }
    }
  ]
}
```

---

## thread_pool.py

### 목적
전역 ThreadPoolExecutor 인스턴스 정의

### 파일 위치
`E:\CivitAI Workspace\thread_pool.py`

### 내용

```python
from concurrent.futures import ThreadPoolExecutor

# 이미지 메타데이터 처리: 429 오류 방지를 위해 1개로 제한
IMG_META_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ImgMeta")

# LoRA 처리: 파일 다운로드 및 후처리가 주요 작업이므로 4개 유지
BG_LORA_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="Lora")
```

### 사용 예시

```python
from thread_pool import IMG_META_EXECUTOR, BG_LORA_EXECUTOR

# 이미지 메타 작업 제출
future = IMG_META_EXECUTOR.submit(async_process_image_meta, image_id, uuid, folder)

# LoRA 작업 제출
future = BG_LORA_EXECUTOR.submit(process_lora_task, folder, model_version_id, None)
```

---

## prompt_modifier.py

### 목적
기존 메타데이터 파일의 프롬프트를 LoRA 파일 기준으로 재생성합니다.

### 파일 위치
`E:\CivitAI Workspace\prompt_modifier.py`

### 사용법

```bash
python prompt_modifier.py                  # 현재 폴더 기준
python prompt_modifier.py D:/CivitAI/Users/foobar  # 특정 폴더
```

### 주요 함수

#### find_lora_ss_output_name

```python
def find_lora_ss_output_name(folder: str) -> tuple[str, str]:
    """
    폴더 내 .safetensors 파일에서 ss_output_name 추출

    동작:
        1. .safetensors 파일 찾기
        2. 메타데이터에서 ss_output_name 읽기
        3. 없으면 파일명 기반으로 생성 (__ → _ 정규화)
        4. 메타데이터에 ss_output_name 쓰기
        5. 필요시 파일명도 정규화

    반환: (lora_filename, ss_output_name)
    """
```

#### extract_all_lora_tags

```python
def extract_all_lora_tags(prompt: str) -> list[tuple[str, str]]:
    """
    프롬프트에서 모든 <lora:...> 태그 추출

    반환: [(full_tag, name), ...]
        예: [("<lora:Model_v1:0.8>", "Model_v1")]
    """
```

#### reorder_lora_tags_to_front

```python
def reorder_lora_tags_to_front(prompt: str) -> str:
    """
    LoRA 태그들을 프롬프트 앞쪽으로 이동

    동작:
        1. 모든 <lora:...> 태그 추출
        2. 본문에서 태그 제거
        3. 태그들 + 본문 순서로 재조합
    """
```

#### process_txt

```python
def process_txt(path: str):
    """
    단일 txt 파일 처리

    동작:
        1. JSON 파일 로드
        2. raw_prompt 확인
        3. 폴더의 LoRA ss_output_name 확인 (캐시 사용)
        4. raw_prompt의 LoRA 태그와 ss_output_name 비교
           - 일치하면 원본 태그 사용
           - 불일치하면 <lora:ss_output_name:1> 생성
        5. LoRA 태그를 앞으로 이동
        6. 필터링 적용:
           - prompt: SEX + CLOTHES + ETC 필터
           - prompt_with_clothes: SEX + ETC 필터
        7. 결과 저장
    """
```

### 캐시 시스템

```python
_LORA_INFO_CACHE = {}  # {folder_path: (lora_filename, ss_output_name) or None}

def get_lora_info_for_folder(folder: str):
    """
    폴더별 LoRA 정보 캐시 조회

    동작:
        - 캐시에 있으면 반환
        - 없으면 find_lora_ss_output_name() 호출 후 캐시
    """
```

---

## re_filter_prompts.py

### 목적
이미 생성된 txt 파일의 프롬프트를 필터 규칙 변경 후 다시 필터링합니다.

### 파일 위치
`E:\CivitAI Workspace\re_filter_prompts.py`

### 사용법

```bash
cd E:\CivitAI\Users\username\ModelName
python E:\CivitAI Workspace\re_filter_prompts.py
```

### 주요 함수

#### process_txt

```python
def process_txt(path: str):
    """
    단일 txt 파일 재필터링

    동작:
        1. JSON 로드
        2. raw_prompt, prompt, prompt_with_clothes, lora 읽기
        3. raw_prompt에서 LoRA 태그 추출 (없으면 기존 lora 사용)
        4. 기존 prompt에서 모든 LoRA 태그 제거
        5. 필터링 재적용:
           - prompt: FILTER_WORDS (전체 필터)
           - prompt_with_clothes: ETC_FILTER만
        6. LoRA 태그를 앞에 추가
        7. 결과 저장
    """
```

### prompt_modifier.py와의 차이점

| 항목 | prompt_modifier.py | re_filter_prompts.py |
|------|-------------------|---------------------|
| LoRA 태그 소스 | safetensors 파일의 ss_output_name | raw_prompt 또는 기존 lora 필드 |
| LoRA 태그 처리 | ss_output_name 기준 정규화 | 기존 태그 유지 |
| 용도 | LoRA 파일 기준 프롬프트 재생성 | 필터 규칙 변경 후 재적용 |

---

## all_prompts_collect.py

### 목적
전체 폴더의 모든 프롬프트 토큰을 수집하여 중복 제거된 목록을 생성합니다.

### 파일 위치
`E:\CivitAI Workspace\all_prompts_collect.py`

### 사용법

```bash
python all_prompts_collect.py                  # 현재 폴더 기준
python all_prompts_collect.py D:\CivitAI\Users # 특정 폴더
```

### 출력

파일: `{base_dir}/all_prompts.json`

```json
[
  "1girl",
  "solo",
  "score_9",
  "looking at viewer",
  "smile",
  ...
]
```

### 주요 함수

#### collect_from_raw_prompt

```python
def collect_from_raw_prompt(raw_prompt: str, acc_list: list, acc_set: set):
    """
    raw_prompt에서 토큰 수집

    동작:
        1. normalize_prompt_basic() 적용
        2. 콤마 기준 분리
        3. <lora:...> 태그 제외
        4. normalize_filter_item()으로 정규화
        5. 중복 제거 후 acc_list에 추가
    """
```

#### walk_all_txt

```python
def walk_all_txt(base_dir: str) -> list[str]:
    """
    모든 .txt 파일 순회하며 토큰 수집

    반환: 중복 제거된 프롬프트 토큰 리스트
    """
```

### 용도

1. **필터 규칙 개선**: 어떤 토큰들이 자주 사용되는지 분석
2. **새 필터 항목 추가**: 수집된 토큰에서 필터링할 항목 선별
3. **프롬프트 패턴 분석**: 자주 사용되는 조합 파악

---

## 스크립트 실행 순서 예시

### 1. 새 사용자 다운로드

```bash
# 단일 사용자
python get_all_models.py
# URL 입력: https://civitai.com/user/username/models

# 또는 여러 사용자 일괄
# get_all_models_urls.txt 작성 후
python batch_get_all_models.py
```

### 2. 필터 규칙 변경 후 재필터링

```bash
# 특정 모델 폴더로 이동
cd E:\CivitAI\Users\username\ModelName

# 재필터링 실행
python "E:\CivitAI Workspace\re_filter_prompts.py"
```

### 3. LoRA 기반 프롬프트 재생성

```bash
# 특정 사용자 전체
python prompt_modifier.py E:\CivitAI\Users\username
```

### 4. 전체 프롬프트 분석

```bash
python all_prompts_collect.py E:\CivitAI\Users
# 결과: E:\CivitAI\Users\all_prompts.json
```
