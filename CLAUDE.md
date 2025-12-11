# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

CivitAI 모델 및 이미지 자동 다운로드 시스템입니다. CivitAI 웹사이트에서 사용자의 모든 모델과 관련 이미지를 수집하고, 프롬프트를 필터링하며, IDM(Internet Download Manager)을 통해 파일을 다운로드합니다.

## 핵심 아키텍처

### 1. 메인 스크립트

- **`get_model.py`**: 단일 포스트 처리 (포스트 ID 기반)
  - 포스트의 모든 이미지 수집 및 메타데이터 추출
  - LoRA 파일 다운로드 및 후처리
  - IDM을 통한 파일 다운로드 대기열 관리
  - 프롬프트 필터링 (성적/의상/기타 필터)

- **`get_all_models.py`**: 사용자의 전체 모델 일괄 처리
  - CivitAI API (v1 + TRPC) 병합 호출로 모델 목록 수집
  - 각 모델별로 포스트 ID 추출 후 `get_model.py`의 `process_post_to_dir()` 호출
  - 다운로드 성공/실패 검증 및 로그 생성

- **`batch_get_all_models.py`**: 여러 사용자 URL을 순차 처리
  - `get_all_models_urls.txt` 파일에서 URL 읽기
  - 각 URL마다 `get_all_models.py`를 별도 프로세스로 실행

### 2. 유틸리티 스크립트

- **`download_state.py`**: 다운로드 상태 관리
  - 성공/실패 로그를 JSON 파일에 기록
  - 중복 다운로드 방지 (이미지 ID, LoRA modelVersionId 기반)

- **`thread_pool.py`**: ThreadPoolExecutor 정의
  - `IMG_META_EXECUTOR`: 이미지 메타데이터 생성 (8 workers)
  - `BG_LORA_EXECUTOR`: LoRA 다운로드 처리 (4 workers)

- **`prompt_modifier.py`**: 프롬프트 재생성
  - 폴더 내 `.safetensors` 파일의 `ss_output_name` 기준으로 LoRA 태그 정규화
  - `raw_prompt` 기반으로 `prompt` / `prompt_with_clothes` 재생성

- **`re_filter_prompts.py`**: 기존 프롬프트 재필터링
  - 이미 생성된 txt 파일의 프롬프트를 필터 규칙 변경 후 다시 필터링

- **`all_prompts_collect.py`**: 모든 프롬프트 토큰 수집
  - 전체 폴더 순회하며 `raw_prompt`에서 LoRA 태그를 제외한 모든 토큰 수집
  - `all_prompts.json`으로 저장 (중복 제거)

## 주요 작동 흐름

### 전체 모델 다운로드 프로세스 (`get_all_models.py`)

1. 사용자 URL에서 username 추출
2. CivitAI API로 모델 목록 수집 (v1 + TRPC 병합)
3. 각 모델별로:
   - 모델 메타파일 생성 (JSON + TXT)
   - 포스트 ID 추출 (`get_post_ids_from_model()`)
   - `process_post_to_dir()` 호출하여 이미지 + LoRA 다운로드
4. IDM 다운로드 시작 (`idm_start_download()`)
5. 모든 백그라운드 작업 대기 (이미지 메타, LoRA 후처리)
6. 다운로드 검증 (`verify_all_downloads()`)
7. 통합 로그 저장 (`download_state.save_download_log()`)

### 단일 포스트 처리 (`get_model.py`)

1. 포스트 제목 + `modelVersionId` 추출 (`fetch_post_title_and_model_version()`)
2. 이미지 목록 수집 (`fetch_post_images()`)
3. LoRA 비동기 처리:
   - 중복 체크 (성공 로그 + 로컬 파일 크기)
   - IDM 대기열 추가
4. 각 이미지별로:
   - 중복 체크 (성공 로그 + 로컬 파일 존재)
   - IDM 대기열 추가
   - 메타데이터 비동기 생성 (프롬프트 필터링 포함)

## 파일 구조

```
E:\CivitAI\                       # ROOT (get_model.py에서 설정)
├── Posts\                        # 단일 포스트 저장 (get_model.py 단독 실행)
│   └── {포스트제목}\
│       ├── {imageId}.jpeg
│       ├── {imageId}.txt         # 메타데이터 (JSON)
│       └── {loraFile}.safetensors
│
├── Users\                        # 전체 모델 저장 (get_all_models.py)
│   └── {username}\
│       ├── model_meta_v{versionId}.json   # 모델 메타파일
│       ├── model_meta_v{versionId}.txt
│       ├── {username}_download_log.json   # 통합 다운로드 로그
│       └── {modelName}\
│           ├── {imageId}.jpeg
│           ├── {imageId}.txt
│           └── {loraFile}.safetensors
│
├── Filter_Sex.txt                # 성적 콘텐츠 필터
├── Filter_Clothes.txt            # 의상 필터
└── Filter_Etc.txt                # 기타 필터

E:\sd\models\Lora\                # LoRA 최종 복사 경로
```

## 중요 설정

### 경로 설정 (`get_model.py`)

```python
ROOT = r"E:\CivitAI"
POSTS_ROOT = os.path.join(ROOT, "Posts")
USERS_ROOT = os.path.join(ROOT, "Users")
LORA_PASTE_TARGET_PATH = r"E:\sd\models\Lora"
```

### 쿠키 설정 (`get_model.py`)

`COOKIE_STRING` 변수에 CivitAI 로그인 쿠키 전체 문자열을 설정해야 합니다.

### IDM 경로 (`get_model.py`)

```python
IDM_PATH = r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe"
```

## API 사용

### CivitAI API 엔드포인트

- **모델 목록**: `/api/v1/models?username={username}`
- **TRPC 모델 목록**: `/api/trpc/model.getAll` (브라우저와 동일한 payload)
- **이미지 목록**: `/api/trpc/image.getInfinite`
- **이미지 메타**: `/api/trpc/image.getGenerationData`
- **LoRA presigned URL**: `/api/download/models/{modelVersionId}`

### Rate Limiting

- `safe_get()` 함수에서 요청 간 최소 1초 간격 보장
- 429 에러 시 exponential backoff (2^attempt 초)
- 전역 `REQUEST_LOCK`으로 동시 요청 제어

## 프롬프트 필터링

### 필터 적용 순서

1. `raw_prompt`에서 LoRA 태그 추출
2. LoRA 태그 제거 후 필터링:
   - `prompt`: SEX + CLOTHES + ETC 필터 적용
   - `prompt_with_clothes`: SEX + ETC 필터만 적용
3. LoRA 태그를 필터링된 프롬프트 맨 앞에 추가

### 정규화 규칙 (`normalize_filter_item()`)

- 바깥 괄호 제거: `(tag)` → `tag`
- 가중치 제거: `tag:0.7` → `tag`
- 공백 정리 및 소문자 변환
- 예: `(Naughty smile:0.7)` → `naughty smile`

## LoRA 파일 후처리

1. **ss_output_name 정규화**: `__` → `_` 변경
2. **파일명 정규화**: ss_output_name이 없으면 파일명 기반 생성
3. **SD 폴더 복사**: 상대 경로 유지하여 `LORA_PASTE_TARGET_PATH`에 복사
4. **성공 로그 기록**: 용량 검증 후 통합 로그에 추가

## 다운로드 검증 (`verify_all_downloads()`)

- **이미지**: 최소 5KB 이상
- **LoRA**: `expected_file_size` 이상
- 확장자 무관 이미지 검색 (`find_existing_image_by_id()`)
- 검증 결과를 통합 로그에 반영

## 공통 개발 명령

### 단일 포스트 다운로드
```bash
python get_model.py
# 실행 후 포스트 URL 입력
```

### 전체 모델 다운로드
```bash
python get_all_models.py
# 실행 후 사용자 URL 입력 (예: https://civitai.com/user/{username}/models)
```

### 여러 사용자 일괄 처리
```bash
# get_all_models_urls.txt에 URL 작성 후:
python batch_get_all_models.py
```

### 프롬프트 재생성
```bash
python prompt_modifier.py  # 현재 폴더 기준
```

### 프롬프트 재필터링
```bash
python re_filter_prompts.py  # 현재 폴더 기준
```

### 전체 프롬프트 수집
```bash
python all_prompts_collect.py
```

## 주의사항

### 순환 import 방지

- `get_model.py`와 `get_all_models.py` 간 순환 참조 방지
- `set_future_lists()`, `set_download_targets()` 함수로 전역 리스트 주입

### 멀티스레딩

- 이미지 메타 생성: 최대 8개 동시 작업
- LoRA 다운로드: 최대 4개 동시 작업
- 모든 future 완료 대기 필수 (`for f in futures: f.result()`)

### IDM 사용

- `/a`: 대기열 추가 (다운로드 시작 안 됨)
- `/s`: 대기열 다운로드 시작
- 모든 파일을 대기열에 추가한 후 한 번만 `/s` 호출

### 파일명 정규화

- Windows 금지 문자: `< > : " / \ | ? *`
- 제어 문자 및 zero-width space 제거
- `safe_folder_name()` 함수 사용

## 코딩 스타일

- 들여쓰기: 2칸
- 주석: 한국어
- 변수명: camelCase 영어
- 함수명: snake_case 영어 (동사로 시작)
