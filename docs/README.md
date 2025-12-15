# CivitAI 모델 자동 다운로드 시스템 - 기술 문서

## 문서 목차

| 문서 | 설명 |
|------|------|
| [architecture.md](./architecture.md) | 시스템 전체 아키텍처 및 흐름도 |
| [get_model.md](./get_model.md) | 단일 포스트 처리 핵심 모듈 상세 |
| [get_all_models.md](./get_all_models.md) | 사용자 전체 모델 일괄 처리 모듈 상세 |
| [utilities.md](./utilities.md) | 유틸리티 스크립트 가이드 |
| [api-reference.md](./api-reference.md) | CivitAI API 엔드포인트 참조 |
| [data-structures.md](./data-structures.md) | 데이터 구조 및 파일 형식 |

---

## 프로젝트 개요

CivitAI 웹사이트에서 사용자의 모든 모델과 관련 이미지를 자동으로 수집하고, 프롬프트를 필터링하며, IDM(Internet Download Manager)을 통해 파일을 다운로드하는 시스템입니다.

### 주요 기능

1. **모델 수집**: CivitAI API를 통해 특정 사용자의 모든 모델 목록 수집
2. **이미지 다운로드**: 각 모델에 연결된 포스트의 모든 이미지 다운로드
3. **LoRA 다운로드**: 모델의 safetensors 파일 다운로드 및 후처리
4. **메타데이터 추출**: 이미지의 프롬프트, 설정값 등 메타데이터 저장
5. **프롬프트 필터링**: 성적/의상/기타 콘텐츠 필터링 적용
6. **다운로드 상태 관리**: 중복 다운로드 방지 및 실패 기록

---

## 핵심 파일 구조

```
E:\CivitAI Workspace\
├── get_model.py           # 단일 포스트 처리 (핵심 모듈)
├── get_all_models.py      # 사용자 전체 모델 일괄 처리
├── batch_get_all_models.py # 여러 사용자 URL 순차 처리
├── download_state.py      # 다운로드 상태 관리 (성공/실패 로그)
├── thread_pool.py         # ThreadPoolExecutor 정의
├── prompt_modifier.py     # 프롬프트 재생성 유틸리티
├── re_filter_prompts.py   # 프롬프트 재필터링 유틸리티
├── all_prompts_collect.py # 전체 프롬프트 토큰 수집
├── Filter_Sex.txt         # 성적 콘텐츠 필터 목록
├── Filter_Clothes.txt     # 의상 필터 목록
├── Filter_Etc.txt         # 기타 필터 목록
├── get_all_models_urls.txt # 배치 처리용 URL 목록
└── docs/                  # 기술 문서
```

---

## 출력 디렉토리 구조

```
E:\CivitAI\
├── Posts\                        # 단일 포스트 다운로드 (get_model.py 단독 실행)
│   └── {포스트제목}\
│       ├── {imageId}.jpeg
│       ├── {imageId}.txt         # 메타데이터 (JSON)
│       └── {loraFile}.safetensors
│
└── Users\                        # 전체 모델 다운로드 (get_all_models.py)
    └── {username}\
        ├── model_meta_v{versionId}.json
        ├── model_meta_v{versionId}.txt
        └── {modelName}\
            ├── {imageId}.jpeg
            ├── {imageId}.txt
            └── {loraFile}.safetensors

E:\sd\models\Lora\                # LoRA 파일 복사 대상 경로
└── Users\{username}\{modelName}\
    └── {loraFile}.safetensors
```

---

## 실행 방법

### 1. 단일 포스트 다운로드
```bash
python get_model.py
# 실행 후 포스트 URL 입력 (예: https://civitai.com/posts/1234567)
```

### 2. 사용자 전체 모델 다운로드
```bash
python get_all_models.py
# 실행 후 사용자 모델 목록 URL 입력
# (예: https://civitai.com/user/username/models)
```

### 3. 여러 사용자 일괄 처리
```bash
# get_all_models_urls.txt에 URL들을 한 줄씩 작성 후:
python batch_get_all_models.py
```

---

## 설정 항목

### 경로 설정 (get_model.py)
```python
ROOT = r"E:\CivitAI"                    # 기본 저장 경로
ROOT_Filter = r"E:\CivitAI Workspace"   # 필터 파일 경로
POSTS_ROOT = os.path.join(ROOT, "Posts")
USERS_ROOT = os.path.join(ROOT, "Users")
LORA_PASTE_TARGET_PATH = r"E:\sd\models\Lora"  # LoRA 복사 대상
```

### 쿠키 설정 (get_model.py)
- `COOKIE_STRING` 변수에 CivitAI 로그인 쿠키 전체 문자열 설정 필요
- 브라우저 개발자 도구에서 쿠키 복사 가능

### IDM 경로 (get_model.py)
```python
IDM_PATH = r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe"
```

---

## 스레드 풀 설정 (thread_pool.py)

```python
IMG_META_EXECUTOR = ThreadPoolExecutor(max_workers=1)   # 이미지 메타 처리
BG_LORA_EXECUTOR = ThreadPoolExecutor(max_workers=4)    # LoRA 다운로드
```

- 이미지 메타: 429 오류 방지를 위해 1개로 제한
- LoRA: 파일 다운로드가 주요 작업이므로 4개 유지

---

## Rate Limiting

- `safe_get()` 함수에서 요청 간 최소 1.5초 간격 보장
- 429 에러 시 exponential backoff (2^attempt 초, 최대 60초)
- 전역 `REQUEST_LOCK`으로 동시 요청 제어

---

## 의존성

- Python 3.10+
- requests
- concurrent.futures (표준 라이브러리)
- Internet Download Manager (IDM)

---

## 주의사항

1. **쿠키 만료**: CivitAI 쿠키는 주기적으로 갱신 필요
2. **API Rate Limit**: 너무 빠른 요청 시 429 에러 발생
3. **IDM 설치**: IDM이 설치되어 있어야 다운로드 가능
4. **디스크 공간**: 대량 다운로드 시 충분한 저장 공간 확보 필요
