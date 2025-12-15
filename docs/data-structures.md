# 데이터 구조 및 파일 형식

## 개요

이 시스템에서 사용하는 데이터 구조와 파일 형식에 대한 상세 문서입니다.

---

## 이미지 메타데이터 파일 ({imageId}.txt)

이미지와 함께 저장되는 메타데이터 JSON 파일입니다.

### 파일 위치

```
E:\CivitAI\{Posts|Users}\{폴더}\{imageId}.txt
```

### 구조

```json
{
  "prompt": "필터링된 프롬프트 (SEX + CLOTHES + ETC 제거)",
  "prompt_with_clothes": "의상 필터 미적용 프롬프트 (SEX + ETC만 제거)",
  "negative": "네거티브 프롬프트",
  "cfg": 7,
  "steps": 30,
  "sampler": "Euler a",
  "seed": 123456789,
  "clip_skip": 2,
  "raw_prompt": "원본 프롬프트 (필터링 전)",
  "lora": "<lora:ModelName:0.8>",
  "url": "https://civitai.com/images/12345678",
  "resources_used": [
    {
      "modelVersionId": 789012,
      "name": "Model Name",
      "type": "lora",
      "download_url": "https://civitai.com/api/download/models/789012"
    }
  ]
}
```

### 필드 설명

| 필드 | 타입 | 설명 |
|-----|------|------|
| prompt | string | 전체 필터 적용된 프롬프트 (LoRA 태그 포함) |
| prompt_with_clothes | string | 의상 제외 필터 적용 프롬프트 |
| negative | string | 네거티브 프롬프트 |
| cfg | number | CFG Scale 값 |
| steps | number | 샘플링 스텝 수 |
| sampler | string | 샘플러 이름 |
| seed | number | 시드 값 |
| clip_skip | number | CLIP Skip 값 |
| raw_prompt | string | 원본 프롬프트 (필터링 전) |
| lora | string | 사용된 LoRA 태그 |
| url | string | CivitAI 이미지 페이지 URL |
| resources_used | array | 이미지 생성에 사용된 리소스 목록 |

### 생성 위치

`get_model.py` - `async_process_image_meta()`

---

## 모델 메타파일 (model_meta_v{versionId}.json)

각 모델 버전별로 생성되는 상세 메타데이터 파일입니다.

### 파일 위치

```
E:\CivitAI\Users\{username}\{modelName}\model_meta_v{versionId}.json
E:\CivitAI\Users\{username}\{modelName}\model_meta_v{versionId}.txt
```

### JSON 구조

```json
{
  "modelId": 123456,
  "modelName": "Model Name",
  "modelUrl": "https://civitai.com/models/123456",
  "modelType": "LORA",
  "tags": ["tag1", "tag2"],
  "creator": {
    "username": "username",
    "image": "avatar-url"
  },
  "stats": {
    "downloadCount": 10000,
    "favoriteCount": 5000,
    "commentCount": 100,
    "ratingCount": 500,
    "rating": 4.8
  },
  "descriptionHtml": "<p>모델 설명...</p>",
  "version": {
    "modelVersionId": 789012,
    "versionName": "v1.0",
    "publishedAt": "2024-01-01T00:00:00.000Z",
    "baseModel": "SD 1.5",
    "baseModelType": "Standard",
    "trainedWords": ["trigger1", "trigger2"],
    "files": [
      {
        "name": "model.safetensors",
        "sizeKB": 131072,
        "type": "Model",
        "download_endpoint": "https://civitai.com/api/download/models/789012"
      }
    ],
    "previewImages": [
      {
        "id": 111111,
        "url": "uuid-string",
        "pageUrl": "https://civitai.com/images/111111"
      }
    ],
    "gallery": [
      {
        "postId": 9876543,
        "imageId": 12345678,
        "url": "uuid-string",
        "width": 1024,
        "height": 1536,
        "stats": {"heartCount": 100},
        "prompt": "1girl, solo, ...",
        "negativePrompt": "...",
        "seed": 123456789,
        "sampler": "Euler a",
        "steps": 30,
        "models_used": [
          {
            "modelVersionId": 789012,
            "download_endpoint": "https://civitai.com/api/download/models/789012"
          }
        ]
      }
    ]
  }
}
```

### 생성 위치

`get_all_models.py` - `generate_model_meta_files()`

---

## 다운로드 로그 ({username}_download_log.json)

성공/실패 기록을 관리하는 통합 로그 파일입니다.

### 파일 위치

```
E:\CivitAI Workspace\download_logs\{username}\{username}_download_log.json
```

### 구조

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
      "id": 789012,
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
        "expected_file_path": "E:\\...",
        "expected_file_size": null,
        "download_url": "https://...",
        "page_url": "https://civitai.com/images/11111111"
      }
    },
    {
      "id": 999999,
      "type": "lora",
      "reason": "presigned_url_failed",
      "info": {
        "error_type": "RuntimeError",
        "lora_filename": "model.safetensors",
        "folder": "E:\\..."
      }
    }
  ]
}
```

### success 항목 필드

| 필드 | 타입 | 설명 |
|-----|------|------|
| id | int | 이미지 ID 또는 model_version_id |
| type | string | "image" 또는 "lora" |
| path | string | 파일 저장 경로 |
| size | int | 파일 크기 (bytes) |

### failed 항목 필드

| 필드 | 타입 | 설명 |
|-----|------|------|
| id | int | 이미지 ID 또는 model_version_id |
| type | string | "image", "lora", "model_meta" 등 |
| reason | string | 실패 이유 코드 |
| info | object | 추가 정보 |

### reason 코드

| 코드 | 설명 |
|------|------|
| uuid_not_found | 이미지 UUID 없음 |
| missing | 파일이 존재하지 않음 |
| corrupted | 파일 손상 (용량 부족) |
| invalid_path | 경로가 유효하지 않음 |
| presigned_url_failed | presigned URL 획득 실패 |
| timeout | 다운로드 타임아웃 |
| copy_failed | SD 폴더 복사 실패 |
| safetensors_not_found_in_api | API에 safetensors 파일 없음 |
| meta_failed | 메타데이터 생성 실패 |
| no_model_versions | 모델 버전 없음 |
| generation_failed | 메타파일 생성 실패 |

### 관리 위치

`download_state.py`

---

## DOWNLOAD_TARGETS 항목 구조

런타임에서 다운로드 대상을 추적하는 리스트입니다.

### 이미지 항목

```python
{
    "type": "image",
    "post_id": 9876543,
    "image_id": 12345678,
    "uuid": "uuid-string",
    "download_url": "https://image.civitai.com/.../uuid.jpeg",
    "page_url": "https://civitai.com/images/12345678",
    "expected_file_path": "E:\\CivitAI\\Users\\...\\12345678.jpeg",
    "needs_download": True,

    # 검증 후 추가
    "status": "success",  # "success", "missing", "corrupted"
    "actual_file_size": 524288
}
```

### LoRA 항목

```python
{
    "type": "lora",
    "post_id": None,
    "model_version_id": 789012,
    "presigned_url": "https://cdn.civitai.com/...",  # 또는 None
    "expected_file_path": "E:\\CivitAI\\Users\\...\\model.safetensors",
    "expected_file_size": 134217728,
    "final_paste_path": None,  # 후처리에서 채워짐
    "needs_download": True,

    # 검증 후 추가
    "status": "success",
    "actual_file_size": 134217728
}
```

### 실패 모델 항목 (postId 없음)

```python
{
    "type": "model_no_postid",
    "model_id": 123456,
    "model_name": "Model Name",
    "model_url": "https://civitai.com/models/123456",
    "reason": "postId_not_found",
    "expected_file_path": None,
    "expected_file_size": None,
    "status": "failed"
}
```

---

## 필터 파일 형식

프롬프트 필터링에 사용되는 단어 목록 파일입니다.

### 파일 위치

```
E:\CivitAI Workspace\Filter_Sex.txt
E:\CivitAI Workspace\Filter_Clothes.txt
E:\CivitAI Workspace\Filter_Etc.txt
```

### 형식

- 한 줄에 하나의 필터 단어
- 빈 줄 무시
- 대소문자 구분 없음 (로드 시 소문자 변환)

```text
dynamic pose
crossed legs
looking_at_viewer
arm_up
closed_eyes
...
```

### 필터 유형

| 파일 | 용도 | 적용 |
|-----|------|------|
| Filter_Sex.txt | 성적 콘텐츠 필터 | prompt, prompt_with_clothes 모두 |
| Filter_Clothes.txt | 의상 필터 | prompt만 (prompt_with_clothes에는 미적용) |
| Filter_Etc.txt | 기타 필터 | prompt, prompt_with_clothes 모두 |

### 정규화 규칙

필터 매칭 시 `normalize_filter_item()` 함수로 정규화됩니다.

```python
def normalize_filter_item(text: str) -> str:
    # "(Naughty smile:0.7)" → "naughty smile"
    # "( Naughty smile )"  → "naughty smile"
    # "Naughty smile:0.8"  → "naughty smile"
```

---

## safetensors 메타데이터

LoRA 파일 내부의 메타데이터 구조입니다.

### 파일 구조

```
[8 bytes: JSON 길이 (little-endian uint64)]
[N bytes: JSON 메타데이터]
[나머지: 텐서 데이터]
```

### 메타데이터 구조

```json
{
  "__metadata__": {
    "ss_output_name": "model_name",
    "ss_sd_model_name": "base_model",
    "ss_network_module": "networks.lora",
    "ss_network_dim": "32",
    "ss_network_alpha": "16",
    ...
  },
  "텐서이름1": {...},
  "텐서이름2": {...}
}
```

### 주요 필드

| 필드 | 설명 | 용도 |
|-----|------|------|
| ss_output_name | LoRA 이름 | 프롬프트 LoRA 태그 생성에 사용 |
| ss_sd_model_name | 베이스 모델 | 참고용 |
| ss_network_dim | 네트워크 차원 | 참고용 |

### 처리 함수

```python
# 읽기
def read_safetensors_metadata(path: str) -> dict:
    ...

# 쓰기
def rewrite_safetensors_metadata(path: str, new_ss_name: str):
    ...
```

---

## downloaded_files.json

사용자별 다운로드 완료 파일 목록 (legacy 형식)

### 파일 위치

```
E:\CivitAI\Users\{username}\downloaded_files.json
```

### 구조

```json
{
  "lora": [
    {
      "model_version_id": 789012,
      "filename": "model.safetensors"
    }
  ],
  "images": [
    {
      "image_id": 12345678,
      "filename": "12345678.jpeg",
      "post_id": 9876543
    }
  ]
}
```

### 용도

- 중복 다운로드 방지 (레거시)
- 현재는 `download_state.py`의 `download_log`가 주로 사용됨

---

## 텍스트 로그 파일

### 다운로드 로그 ({username}_download_log_{timestamp}.txt)

**위치**: `download_logs/{username}/`

**내용**:
```text
===== CivitAI 모델 다운로드 기록 =====
생성 시각: 20241201_120000

[입력한 모델 목록 URL]
https://civitai.com/user/username/models

[다운받을 모델 갯수]
50

[다운로드 받지 못한 모델 정보]
--------------------------------------
모델 이름: Model Name
모델 URL: https://civitai.com/models/123456
포스트 아이디: 9876543
다운 못받은 이미지 URL들:
 - 다운로드 URL: https://...
   페이지 URL:    https://civitai.com/images/...
다운 못받은 로라 없음
--------------------------------------
```

---

## 디렉토리 구조 요약

```
E:\CivitAI Workspace\           # 소스 코드 디렉토리
├── docs\                       # 문서
├── download_logs\              # 다운로드 로그
│   └── {username}\
│       ├── {username}_download_log.json    # 통합 로그 (JSON)
│       └── {username}_download_log_*.txt   # 실행별 로그 (텍스트)
├── Filter_*.txt                # 필터 파일
└── *.py                        # 소스 코드

E:\CivitAI\                     # 다운로드 디렉토리
├── Posts\                      # 단일 포스트 다운로드
│   └── {포스트제목}\
│       ├── {imageId}.jpeg
│       ├── {imageId}.txt
│       └── {loraFile}.safetensors
│
└── Users\                      # 사용자별 전체 모델
    └── {username}\
        ├── downloaded_files.json    # 다운로드 완료 목록 (legacy)
        └── {modelName}\
            ├── model_meta_v{versionId}.json
            ├── model_meta_v{versionId}.txt
            ├── {imageId}.jpeg
            ├── {imageId}.txt
            └── {loraFile}.safetensors

E:\sd\models\Lora\              # LoRA 복사 대상
└── Users\{username}\{modelName}\
    └── {loraFile}.safetensors
```
