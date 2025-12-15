# get_model.py - 단일 포스트 처리 모듈

## 개요

CivitAI 포스트 하나를 처리하여 이미지와 LoRA 파일을 다운로드하고, 메타데이터를 추출하는 핵심 모듈입니다.

**파일 위치**: `E:\CivitAI Workspace\get_model.py`

---

## 전역 설정

### 경로 설정

```python
ROOT = r"E:\CivitAI"                           # 기본 저장 경로
ROOT_Filter = r"E:\CivitAI Workspace"          # 필터 파일 경로
POSTS_ROOT = os.path.join(ROOT, "Posts")       # 단일 포스트 저장 경로
USERS_ROOT = os.path.join(ROOT, "Users")       # 전체 모델 저장 경로
LORA_PASTE_TARGET_PATH = r"E:\sd\models\Lora"  # LoRA 복사 대상 경로

FILTER_SEX_PATH = os.path.join(ROOT_Filter, "Filter_Sex.txt")
FILTER_CLOTHES_PATH = os.path.join(ROOT_Filter, "Filter_Clothes.txt")
FILTER_ETC_PATH = os.path.join(ROOT_Filter, "Filter_Etc.txt")
```

### IDM 설정

```python
IDM_PATH = r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe"
IDM_QUEUE_COUNTER = 0        # 대기열 카운터
IDM_COUNTER_LOCK = Lock()    # 스레드 안전 락
```

### Rate Limiting 설정

```python
REQUEST_LOCK = threading.Lock()
LAST_REQUEST_TIME = 0
REQUEST_INTERVAL = 1.5  # 최소 요청 간격 (초)
```

### 이미지 확장자

```python
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".jfif"}
```

---

## 전역 리스트 주입 시스템

순환 import 방지를 위해 `get_all_models.py`에서 리스트를 주입받는 구조입니다.

### 주입 변수

```python
IMG_META_FUTURES = None    # 이미지 메타 Future 리스트
LORA_FUTURES = None        # LoRA Future 리스트
DOWNLOAD_TARGETS = None    # 다운로드 대상 리스트
```

### 주입 함수

```python
def set_future_lists(img_list, lora_list):
    """get_all_models.py에서 Future 리스트 주입"""
    global IMG_META_FUTURES, LORA_FUTURES
    IMG_META_FUTURES = img_list
    LORA_FUTURES = lora_list

def set_download_targets(target_list):
    """get_all_models.py에서 DOWNLOAD_TARGETS 리스트 주입"""
    global DOWNLOAD_TARGETS
    DOWNLOAD_TARGETS = target_list
```

---

## IDM 관련 함수

### idm_add_to_queue

```python
def idm_add_to_queue(url: str, save_dir: str, file_name: str):
    """
    IDM 다운로드 대기열에 추가 (/a 옵션)

    파라미터:
        url: 다운로드 URL
        save_dir: 저장 디렉토리
        file_name: 저장 파일명

    동작:
        1. IDM 명령어 실행: /d "{url}" /p "{save_dir}" /f "{file_name}" /a
        2. 1초 대기 (빠른 등록 시 누락 방지)
        3. IDM_QUEUE_COUNTER 증가
    """
```

### idm_start_download

```python
def idm_start_download():
    """
    IDM 대기열 다운로드 시작 (/s 옵션)

    동작:
        1. 대기열이 비어있으면 리턴
        2. IDM /s 명령어 실행
        3. IDM_QUEUE_COUNTER 초기화
    """
```

### idm_get_queue_size

```python
def idm_get_queue_size() -> int:
    """현재 대기열에 추가된 파일 개수 반환"""
```

---

## HTTP 요청 함수

### safe_get

```python
def safe_get(url, retries=5, **kwargs) -> Response:
    """
    Rate limit을 고려한 안전한 GET 요청

    특징:
        - REQUEST_LOCK 안에서 대기 + API 호출까지 수행
        - 여러 스레드의 동시 API 호출 완전 차단
        - 429 오류 시 exponential backoff (2^attempt 초, 최대 60초)

    파라미터:
        url: 요청 URL
        retries: 최대 재시도 횟수 (기본: 5)
        **kwargs: requests.get()에 전달할 추가 인자

    예외:
        Exception: 5회 재시도 후에도 429 발생 시
    """
```

### parse_cookie_string

```python
def parse_cookie_string(s: str) -> dict:
    """
    쿠키 문자열을 딕셔너리로 파싱

    입력: "key1=value1; key2=value2; ..."
    출력: {"key1": "value1", "key2": "value2", ...}
    """
```

---

## CivitAI API 함수

### fetch_post_title_and_model_version

```python
def fetch_post_title_and_model_version(post_id: int) -> tuple[str, int | None]:
    """
    포스트 HTML에서 제목과 modelVersionId 추출

    동작:
        1. https://civitai.com/posts/{post_id} 페이지 로드
        2. <title> 태그에서 제목 추출
        3. "modelVersionId": 패턴으로 버전 ID 추출

    반환: (title, model_version_id)
        - title: 포스트 제목 (없으면 "Post_{post_id}")
        - model_version_id: 버전 ID (없으면 None)
    """
```

### fetch_post_images

```python
def fetch_post_images(post_id: int) -> list[dict]:
    """
    포스트의 모든 이미지 목록 수집 (image.getInfinite API)

    동작:
        1. /api/trpc/image.getInfinite 호출
        2. cursor 기반 페이지네이션으로 모든 이미지 수집

    반환: 이미지 딕셔너리 리스트
        [{"id": 123, "url": "uuid-string", ...}, ...]
    """
```

### fetch_generation

```python
def fetch_generation(image_id: int) -> dict:
    """
    이미지의 생성 데이터 조회 (image.getGenerationData API)

    반환: {"meta": {...}, "resources": [...]}
        - meta: prompt, negativePrompt, cfgScale, steps, sampler, seed, clipSkip
        - resources: 사용된 모델/LoRA 정보
    """
```

### get_lora_presigned

```python
def get_lora_presigned(model_version_id: int) -> str:
    """
    LoRA 다운로드용 presigned URL 획득

    동작:
        1. /api/download/models/{model_version_id} 요청
        2. 302 리다이렉트의 Location 헤더에서 URL 추출

    예외:
        RuntimeError: presigned URL 획득 실패 시
    """
```

### extract_post_ids_from_image_page

```python
def extract_post_ids_from_image_page(image_id: int) -> list[int]:
    """
    이미지 페이지 HTML에서 모든 postId 추출

    동작:
        1. /images/{image_id} 페이지 로드
        2. __NEXT_DATA__ JSON 파싱
        3. 재귀적으로 postId, posts, post.id 검색

    반환: postId 리스트 (중복 제거)
    """
```

---

## safetensors 메타데이터 함수

### read_safetensors_metadata

```python
def read_safetensors_metadata(path: str) -> dict:
    """
    safetensors 파일의 메타데이터 읽기

    동작:
        1. 파일의 처음 8바이트에서 JSON 길이 읽기
        2. JSON 파싱 후 __metadata__ 반환

    반환: {"ss_output_name": "...", ...} 또는 빈 dict
    """
```

### rewrite_safetensors_metadata

```python
def rewrite_safetensors_metadata(path: str, new_ss_name: str):
    """
    safetensors 파일의 ss_output_name 수정

    동작:
        1. 기존 파일의 메타데이터 + 텐서 데이터 읽기
        2. __metadata__.ss_output_name 수정
        3. 새 JSON + 텐서 데이터로 파일 재작성
    """
```

---

## 프롬프트 필터링 함수

### normalize_filter_item

```python
def normalize_filter_item(text: str) -> str:
    """
    필터 비교용 토큰 정규화

    예시:
        "(Naughty smile:0.7)" → "naughty smile"
        "( Naughty smile )"  → "naughty smile"
        "Naughty smile:0.8"  → "naughty smile"

    동작:
        1. 바깥 한 겹 괄호 제거
        2. 끝에 붙은 가중치 제거 (":0.7", ":1.0" 등)
        3. 공백 여러 개 → 하나로
        4. 소문자 변환
    """
```

### normalize_prompt_basic

```python
def normalize_prompt_basic(prompt: str) -> str:
    """
    프롬프트 기본 정규화

    동작:
        1. "BREAK" → 콤마로 변환
        2. <lora:...> 태그 앞뒤에 콤마 자동 삽입
        3. 콤마 정리 (중복 콤마 제거, 공백 정리)
    """
```

### clean_prompt

```python
def clean_prompt(prompt: str, filters: list[str]) -> str:
    """
    프롬프트에서 필터 단어 제거

    동작:
        1. normalize_prompt_basic() 적용
        2. 필터 단어 세트 생성 (정규화된 키)
        3. 토큰 파싱 (괄호 그룹 처리)
        4. LoRA 태그는 항상 유지
        5. 필터에 매칭되는 토큰 제거
        6. 결과 조합 후 마지막에 콤마 추가

    반환: "토큰1, 토큰2, 토큰3,"
    """
```

### 필터 변수

```python
SEX_FILTER = load_filter_file(FILTER_SEX_PATH)      # 성적 콘텐츠
CLOTHES_FILTER = load_filter_file(FILTER_CLOTHES_PATH)  # 의상
ETC_FILTER = load_filter_file(FILTER_ETC_PATH)      # 기타

FILTER_WORDS = SEX_FILTER + CLOTHES_FILTER + ETC_FILTER  # 전체 필터
```

---

## LoRA 태그 유틸 함수

### remove_all_lora_tags

```python
def remove_all_lora_tags(prompt: str) -> str:
    """프롬프트에서 모든 <lora:...> 태그 제거"""
```

### extract_lora_from_prompt

```python
def extract_lora_from_prompt(prompt: str) -> str:
    """
    프롬프트에서 마지막 LoRA 태그 추출

    반환: "<lora:Name:Weight>" 또는 "" (없으면)
    """
```

---

## 파일 유틸 함수

### find_existing_image_by_id

```python
def find_existing_image_by_id(folder: str, image_id: int) -> str | None:
    """
    폴더에서 image_id에 해당하는 이미지 파일 검색 (확장자 무관)

    동작:
        - IMAGE_EXTS 중 하나인 파일 중 base name이 image_id와 일치하는 파일 검색

    반환: 파일 전체 경로 또는 None
    """
```

### extract_image_extension

```python
def extract_image_extension(url: str) -> str:
    """
    URL에서 이미지 확장자 추출

    반환: ".jpeg", ".png" 등 (없으면 ".png" 기본값)
    """
```

### build_image_url

```python
def build_image_url(uuid: str) -> str:
    """
    UUID로 이미지 다운로드 URL 생성

    반환: "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/{uuid}/original=true/{uuid}.jpeg"
    """
```

---

## 핵심 처리 함수

### _process_post_core

```python
def _process_post_core(post_id: int, save_dir: str) -> dict:
    """
    포스트 처리의 핵심 로직

    파라미터:
        post_id: CivitAI 포스트 ID
        save_dir: 저장 디렉토리 (절대 경로)

    처리 흐름:
        1. 포스트 제목 + modelVersionId 추출
        2. 저장 폴더 생성
        3. 이미지 목록 수집
        4. LoRA 비동기 처리 시작 (BG_LORA_EXECUTOR)
        5. 각 이미지별:
           - 중복 체크 (성공 로그 + 로컬 파일)
           - IDM 대기열 추가 (필요시)
           - DOWNLOAD_TARGETS에 추가
           - 메타데이터 비동기 생성 (IMG_META_EXECUTOR)

    반환: {
        "failed_image_urls": [...],
        "failed_lora": {...} or None
    }
    """
```

### process_lora_task

```python
def process_lora_task(folder: str, model_version_id: int, _) -> None:
    """
    LoRA 다운로드 작업 (비동기 실행용)

    처리 흐름:
        1. 통합 성공 로그 기반 중복 체크
        2. 모델 버전 메타 API 호출
        3. safetensors 파일 정보 확인
        4. 로컬 파일 존재/용량 체크
        5. presigned URL 획득 (필요시)
        6. DOWNLOAD_TARGETS에 추가
        7. IDM 대기열 추가 (필요시)

    예외 처리:
        - presigned URL 실패: mark_failed() 후 리턴
        - 전체 예외: 스택 트레이스 로깅 + mark_failed() + raise
    """
```

### wait_and_finalize_lora

```python
def wait_and_finalize_lora(folder: str, presigned: str | None, lora_filename: str):
    """
    LoRA 다운로드 대기 및 후처리

    처리 흐름:
        1. 파일 다운로드 완료 대기 (타임아웃: 20분)
        2. ss_output_name 정규화 (__ → _)
        3. ss_output_name 없으면 파일명 기반으로 설정
        4. SD 폴더로 복사 (상대 경로 유지)
        5. 성공 로그 기록

    참고: 현재 빠른 다운로드를 위해 주석 처리됨
    """
```

### async_process_image_meta

```python
def async_process_image_meta(image_id: int, uuid: str, folder: str):
    """
    이미지 메타데이터 비동기 생성

    처리 흐름:
        1. fetch_generation() 호출
        2. 프롬프트 추출 및 줄바꿈 제거
        3. LoRA 태그 제거 후 필터링
           - prompt: SEX + CLOTHES + ETC 필터
           - prompt_with_clothes: SEX + ETC 필터만
        4. LoRA 태그를 앞에 추가
        5. {imageId}.txt 파일 저장 (JSON)

    예외 처리:
        - 실패 시 download_state.mark_failed() 호출
    """
```

---

## 외부 호출용 함수

### process_post

```python
def process_post(post_id: int) -> dict:
    """
    단독 실행용 포스트 처리 (get_model.py 직접 실행 시)

    저장 경로: E:\CivitAI\Posts\{포스트제목}\
    """
```

### process_post_to_dir

```python
def process_post_to_dir(post_id: int, save_dir: str) -> dict:
    """
    get_all_models.py에서 호출하는 포스트 처리

    저장 경로: save_dir (외부에서 지정)
    """
```

---

## 중복 체크 함수

### is_lora_downloaded

```python
def is_lora_downloaded(downloaded_records: dict, model_version_id: int) -> bool:
    """downloaded_records에서 LoRA 다운로드 여부 확인"""
```

### is_image_downloaded

```python
def is_image_downloaded(downloaded_records: dict, image_id: int) -> bool:
    """downloaded_records에서 이미지 다운로드 여부 확인"""
```

---

## 메인 실행

```python
if __name__ == "__main__":
    post_url = input("CivitAI 포스트 URL 입력: ").strip()

    # URL에서 post_id 추출
    m = re.search(r"/posts/(\d+)", post_url)
    post_id = int(m.group(1))

    # 포스트 처리
    process_post(post_id)
```

실행 예시:
```bash
python get_model.py
# 입력: https://civitai.com/posts/1234567
```
