# get_all_models.py - 사용자 전체 모델 처리 모듈

## 개요

CivitAI에서 특정 사용자의 모든 모델을 일괄 수집하고 다운로드하는 모듈입니다.

**파일 위치**: `E:\CivitAI Workspace\get_all_models.py`

---

## 초기화 및 전역 변수

### get_model.py 연동

```python
from get_model import (
    process_post_to_dir,
    parse_cookie_string,
    COOKIE_STRING,
    set_future_lists,
    set_download_targets,
    idm_start_download,
    idm_get_queue_size,
    safe_get,
    USERS_ROOT, POSTS_ROOT
)
from thread_pool import IMG_META_EXECUTOR, BG_LORA_EXECUTOR
```

### 전역 리스트 정의 및 주입

```python
# 다운로드 대상 목록
DOWNLOAD_TARGETS = []

# 비동기 작업 Future 리스트
IMG_META_FUTURES = []
LORA_FUTURES = []

# get_model.py에 리스트 주입
set_future_lists(IMG_META_FUTURES, LORA_FUTURES)
set_download_targets(DOWNLOAD_TARGETS)
```

---

## 유틸리티 함수

### extract_username

```python
def extract_username(url: str) -> str:
    """
    URL에서 username 추출

    입력: "https://civitai.com/user/username/models?query=..."
    출력: "username"
    """
```

### safe_folder_name

```python
def safe_folder_name(name: str) -> str:
    """
    Windows 안전한 폴더명 생성

    처리:
        1. Windows 금지 문자 치환: < > : " / \ | ? *
        2. 제어문자 제거 (\t \n \r, ASCII 0~31)
        3. Zero-width space 제거
        4. 공백 여러 개 → 1개
        5. 앞뒤 공백 정리
    """
```

### extract_trpc_items

```python
def extract_trpc_items(json_data: dict) -> list:
    """
    TRPC 응답에서 items 추출

    구조: result.data.json.items
    """
```

---

## CivitAI API 함수

### call_model_get_all

```python
def call_model_get_all(payload: dict) -> dict | None:
    """
    /api/trpc/model.getAll 호출

    특징:
        - 최대 10회 재시도
        - 429 에러 시 점진적 대기 (5초, 10초, 15초...)

    파라미터:
        payload: {"json": {...}} 형태

    반환: JSON 응답 또는 None (실패시)
    """
```

### get_user_models_v1

```python
def get_user_models_v1(username: str) -> list[dict]:
    """
    /api/v1/models API로 모델 목록 수집

    특징:
        - cursor 기반 페이지네이션
        - 429 에러 시 2초 대기 후 재시도
        - 최대 3회 재시도

    파라미터:
        username: CivitAI 사용자명

    반환: 모델 딕셔너리 리스트
    """
```

### get_user_models_trpc

```python
def get_user_models_trpc(username: str) -> list[dict]:
    """
    /api/trpc/model.getAll API로 모델 목록 수집

    payload 구조:
        {
            "json": {
                "periodMode": "published",
                "sort": "Newest",
                "username": username,
                "period": "AllTime",
                "browsingLevel": 31,
                "excludedTagIds": [...],
                "disablePoi": True,
                "disableMinor": True,
                "authed": True,
                "cursor": cursor  # 페이지네이션
            }
        }

    특징:
        - 브라우저와 동일한 payload 사용
        - cursor 기반 페이지네이션
        - 요청 간 3초 대기
    """
```

### get_user_models

```python
def get_user_models(username: str) -> list[dict]:
    """
    v1 + TRPC 결과 병합

    동작:
        1. get_user_models_v1() 호출
        2. get_user_models_trpc() 호출
        3. model id 기준 중복 제거 후 병합

    반환: 병합된 모델 리스트
    """
```

### get_post_id_from_model

```python
def get_post_id_from_model(model: dict) -> int | None:
    """
    모델에서 대표 postId 추출

    방법 1 (기존):
        modelVersions[0].id → /api/v1/images?modelVersionId=xxx
        → 이미지 중 postId 있는 것 찾기

    방법 2 (fallback):
        model.id → /api/v1/images?modelId=xxx
        → 이미지의 postId 찾기

    반환: postId 또는 None
    """
```

### get_post_ids_from_model

```python
def get_post_ids_from_model(model: dict) -> list[int]:
    """
    모델에서 모든 postId 추출

    검색 순서:
        1. model.images[].id → imageId
        2. modelVersions[*].images[].id
        3. modelVersions[*].sampleImages[].id

    imageId를 찾으면:
        → extract_post_ids_from_image_page(imageId) 호출
        → HTML 파싱으로 모든 postId 추출

    반환: postId 리스트
    """
```

### get_post_id_from_version

```python
def get_post_id_from_version(version_id: int, session) -> int | None:
    """
    modelVersionId로 postId 찾기

    동작:
        /api/v1/images?modelVersionId={version_id}&limit=200
        → 이미지 목록에서 postId 있는 첫 번째 반환
    """
```

---

## 모델 메타파일 생성

### generate_model_meta_files

```python
def generate_model_meta_files(m: dict, user_root: str):
    """
    모델 메타파일 생성 (JSON + TXT)

    생성 파일:
        - model_meta_v{versionId}.json
        - model_meta_v{versionId}.txt

    JSON 구조:
        {
            "modelId": int,
            "modelName": str,
            "modelUrl": str,
            "modelType": str,
            "tags": [...],
            "creator": {...},
            "stats": {...},
            "descriptionHtml": str,
            "version": {
                "modelVersionId": int,
                "versionName": str,
                "publishedAt": str,
                "baseModel": str,
                "baseModelType": str,
                "trainedWords": [...],
                "files": [...],
                "previewImages": [...],
                "gallery": [...]
            }
        }

    gallery 수집:
        /api/v1/images?modelVersionId={versionId}&limit=200
        → 이미지별 프롬프트, 설정값, 사용 모델 정보
    """
```

---

## 다운로드 검증 함수

### verify_download_targets

```python
def verify_download_targets(download_targets: list) -> dict:
    """
    다운로드 시작 전 DOWNLOAD_TARGETS 검증

    검증 항목:
        - 타입별 통계 (이미지, LoRA)
        - 다운로드 필요 여부 통계
        - 필수 필드 검증 (expected_file_path, image_id/model_version_id)
        - 중복 항목 검증

    반환:
        {
            "total": int,
            "images": int,
            "lora": int,
            "images_need_download": int,
            "lora_need_download": int,
            "missing_fields_count": int,
            "image_duplicates": int,
            "lora_duplicates": int
        }
    """
```

### verify_all_downloads

```python
def verify_all_downloads(download_targets: list) -> list:
    """
    다운로드 완료 후 파일 검증

    검증 로직:
        1. 이미 성공 로그에 있는 항목:
           - 파일 존재 + 용량 정상 → 스킵
           - 파일 없거나 손상 → 재검증

        2. 파일 존재 여부 검사:
           - 이미지: 확장자 무관 검색 (find_existing_image_by_id)
           - 없으면 status = "missing"

        3. 파일 용량 검사:
           - 이미지: 최소 5KB
           - LoRA: expected_file_size 이상
           - 미달 시 status = "corrupted"

        4. download_state에 결과 기록:
           - 성공: mark_success()
           - 실패: mark_failed()

    반환: 검증된 항목 리스트 (status 필드 추가됨)
    """
```

---

## 다운로드 로그 함수

### write_download_log

```python
def write_download_log(
    username: str,
    model_list_url: str,
    total_model_count: int,
    failed_models: list
) -> str:
    """
    다운로드 로그 텍스트 파일 생성

    저장 경로: download_logs/{username}/{username}_download_log_{timestamp}.txt

    내용:
        - 생성 시각
        - 입력 URL
        - 총 모델 수
        - 실패 모델별 상세 정보

    반환: 로그 파일 경로
    """
```

### save_download_records

```python
def save_download_records(user_dir: str, list_url: str, total_models: int, records: dict):
    """
    다운로드 기록 텍스트 파일 저장

    저장 경로: {user_dir}/{username}_download_log.txt

    내용:
        - 입력 URL
        - 모델 개수
        - LoRA 목록
        - Images 목록
    """
```

### save_downloaded_file_list

```python
def save_downloaded_file_list(username: str, verified_items: list):
    """
    다운로드 완료 파일 목록 JSON 저장

    저장 경로: E:\CivitAI\Users\{username}\downloaded_files.json

    구조:
        {
            "lora": [{"model_version_id": int, "filename": str}, ...],
            "images": [{"image_id": int, "filename": str, "post_id": int}, ...]
        }
    """
```

### get_downloaded_file_list

```python
def get_downloaded_file_list(username: str) -> dict:
    """
    기존 다운로드 파일 목록 로드

    반환: {"lora": [...], "images": [...]} 또는 빈 구조
    """
```

---

## 메인 함수

### main

```python
def main():
    """
    메인 실행 함수

    실행 흐름:
        1. URL 입력받아 username 추출
        2. 사용자 폴더 생성: E:\CivitAI\Users\{username}
        3. 모델 목록 수집 (v1 + TRPC 병합)
        4. download_state 로드 (기존 기록)
        5. 각 모델별:
           a. 모델 폴더 생성
           b. 메타파일 생성
           c. postId 추출
           d. process_post_to_dir() 호출
           e. 대기열 있으면 IDM 다운로드 시작
        6. DOWNLOAD_TARGETS 검증
        7. 남은 대기열 다운로드 시작
        8. 다운로드 로그 작성
        9. 이미지 메타 작업 대기 (타임아웃: 5분/작업)
       10. LoRA 작업 대기 (타임아웃: 10분/작업)
       11. verify_all_downloads() 실행
       12. download_state.save_download_log() 저장
    """
```

---

## DOWNLOAD_TARGETS 항목 구조

### 이미지 항목

```python
{
    "type": "image",
    "post_id": int,
    "image_id": int,
    "uuid": str,
    "download_url": str,
    "page_url": str,
    "expected_file_path": str,
    "needs_download": bool,
    # 검증 후 추가:
    "status": "success" | "missing" | "corrupted",
    "actual_file_size": int
}
```

### LoRA 항목

```python
{
    "type": "lora",
    "post_id": None,
    "model_version_id": int,
    "presigned_url": str | None,
    "expected_file_path": str,
    "expected_file_size": int,
    "final_paste_path": str | None,
    "needs_download": bool,
    # 검증 후 추가:
    "status": "success" | "missing" | "corrupted" | "presigned_failed",
    "actual_file_size": int
}
```

### 실패 항목 (postId 없음)

```python
{
    "type": "model_no_postid",
    "model_id": int,
    "model_name": str,
    "model_url": str,
    "reason": "postId_not_found",
    "expected_file_path": None,
    "expected_file_size": None,
    "status": "failed"
}
```

---

## failed_models 항목 구조

```python
{
    "model_name": str,
    "model_url": str,
    "post_id": int | None,
    "failed_image_urls": [
        {
            "download_url": str,
            "page_url": str
        },
        ...
    ],
    "failed_lora": {
        "lora_url": str,
        "copy_error": str
    } | None
}
```

---

## 실행 예시

```bash
python get_all_models.py
# 입력: https://civitai.com/user/username/models
```

출력 예시:
```
CivitAI 전체 모델 처리기
모델 목록 URL 입력: https://civitai.com/user/testuser/models
[INFO] 사용자명: testuser
[INFO] v1 API 결과: 15개
[INFO] TRPC 결과: 18개
[INFO] 병합 후 최종 모델 개수: 20개

[MODEL] Test Model 1
  [INFO] version_id: 123456
  [INFO] 이미지 123 → postId=789 발견
[PROCESS] postId = 789
[IDM] Added to queue: 111.jpeg (총 1개)
...
```
