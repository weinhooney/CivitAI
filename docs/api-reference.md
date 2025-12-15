# CivitAI API 참조

## 개요

CivitAI에서 사용하는 API 엔드포인트들의 상세 정보입니다.

---

## REST API (v1)

### GET /api/v1/models

사용자의 모델 목록 조회

**URL**: `https://civitai.com/api/v1/models`

**파라미터**:
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|-----|------|
| username | string | O | 사용자명 |
| limit | int | X | 페이지당 개수 (기본: 100) |
| cursor | string | X | 페이지네이션 커서 |

**응답 예시**:
```json
{
  "items": [
    {
      "id": 123456,
      "name": "Model Name",
      "type": "LORA",
      "description": "...",
      "tags": ["tag1", "tag2"],
      "creator": {
        "username": "username",
        "image": "..."
      },
      "stats": {
        "downloadCount": 1000,
        "favoriteCount": 500,
        "commentCount": 50,
        "ratingCount": 100,
        "rating": 4.8
      },
      "modelVersions": [
        {
          "id": 789012,
          "name": "v1.0",
          "baseModel": "SD 1.5",
          "baseModelType": "Standard",
          "trainedWords": ["trigger1", "trigger2"],
          "files": [
            {
              "name": "model.safetensors",
              "sizeKB": 131072,
              "type": "Model"
            }
          ],
          "images": [
            {
              "id": 111111,
              "url": "uuid-string",
              "width": 512,
              "height": 768
            }
          ]
        }
      ]
    }
  ],
  "metadata": {
    "nextCursor": "cursor-string"
  }
}
```

**사용처**: `get_all_models.py` - `get_user_models_v1()`

---

### GET /api/v1/images

이미지 목록 조회

**URL**: `https://civitai.com/api/v1/images`

**파라미터**:
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|-----|------|
| modelVersionId | int | X | 모델 버전 ID |
| modelId | int | X | 모델 ID |
| limit | int | X | 페이지당 개수 (기본: 200) |

**응답 예시**:
```json
{
  "items": [
    {
      "id": 12345678,
      "url": "uuid-string",
      "width": 1024,
      "height": 1536,
      "postId": 9876543,
      "stats": {
        "heartCount": 100,
        "commentCount": 10
      },
      "meta": {
        "prompt": "1girl, solo, ...",
        "negativePrompt": "...",
        "cfgScale": 7,
        "steps": 30,
        "sampler": "Euler a",
        "seed": 123456789
      }
    }
  ],
  "metadata": {
    "nextCursor": "cursor-string"
  }
}
```

**사용처**:
- `get_all_models.py` - `get_post_id_from_model()`, `generate_model_meta_files()`
- `get_model.py` - 이미지 목록 조회 (fallback)

---

### GET /api/v1/model-versions/{id}

모델 버전 상세 정보 조회

**URL**: `https://civitai.com/api/v1/model-versions/{model_version_id}`

**응답 예시**:
```json
{
  "id": 789012,
  "name": "v1.0",
  "baseModel": "SD 1.5",
  "trainedWords": ["trigger"],
  "files": [
    {
      "name": "model.safetensors",
      "sizeKB": 131072,
      "downloadUrl": "https://...",
      "hashes": {
        "SHA256": "..."
      }
    }
  ]
}
```

**사용처**: `get_model.py` - `process_lora_task()`

---

### GET /api/download/models/{id}

LoRA 다운로드 URL 획득 (리다이렉트)

**URL**: `https://civitai.com/api/download/models/{model_version_id}`

**응답**: 302 Redirect
- `Location` 헤더에 presigned URL 포함

**사용처**: `get_model.py` - `get_lora_presigned()`

**주의사항**:
- 인증 필요 (쿠키)
- presigned URL은 일정 시간 후 만료

---

## TRPC API

### GET /api/trpc/model.getAll

사용자의 모델 목록 조회 (TRPC)

**URL**: `https://civitai.com/api/trpc/model.getAll`

**파라미터**: `input` (JSON 문자열)

**input 구조**:
```json
{
  "json": {
    "periodMode": "published",
    "sort": "Newest",
    "username": "username",
    "period": "AllTime",
    "pending": false,
    "hidden": false,
    "followed": false,
    "earlyAccess": false,
    "fromPlatform": false,
    "supportsGeneration": false,
    "isFeatured": false,
    "browsingLevel": 31,
    "excludedTagIds": [415792, 426772, 5188, ...],
    "disablePoi": true,
    "disableMinor": true,
    "authed": true,
    "cursor": "cursor-string"
  }
}
```

**응답 구조**:
```json
{
  "result": {
    "data": {
      "json": {
        "items": [...],
        "nextCursor": "cursor-string"
      }
    }
  }
}
```

**사용처**: `get_all_models.py` - `get_user_models_trpc()`

**특징**:
- 브라우저와 동일한 payload 사용
- v1 API보다 더 많은 필터 옵션 제공
- `excludedTagIds`로 특정 태그 제외 가능

---

### GET /api/trpc/image.getInfinite

포스트의 이미지 목록 조회 (무한 스크롤)

**URL**: `https://civitai.com/api/trpc/image.getInfinite`

**파라미터**: `input` (JSON 문자열)

**input 구조**:
```json
{
  "json": {
    "postId": 1234567,
    "pending": true,
    "browsingLevel": null,
    "withMeta": false,
    "include": [],
    "excludedTagIds": [],
    "disablePoi": true,
    "disableMinor": true,
    "cursor": null,
    "authed": true
  },
  "meta": {
    "values": {
      "browsingLevel": ["undefined"],
      "cursor": ["undefined"]
    }
  }
}
```

**응답 구조**:
```json
{
  "result": {
    "data": {
      "json": {
        "items": [
          {
            "id": 12345678,
            "url": "uuid-string"
          }
        ],
        "nextCursor": "cursor-string"
      }
    }
  }
}
```

**사용처**: `get_model.py` - `fetch_post_images()`

---

### GET /api/trpc/image.getGenerationData

이미지의 생성 데이터 조회

**URL**: `https://civitai.com/api/trpc/image.getGenerationData`

**파라미터**: `input` (JSON 문자열)

**input 구조**:
```json
{
  "json": {
    "id": 12345678,
    "authed": true
  }
}
```

**응답 구조**:
```json
{
  "result": {
    "data": {
      "json": {
        "meta": {
          "prompt": "1girl, solo, ...",
          "negativePrompt": "...",
          "cfgScale": 7,
          "steps": 30,
          "sampler": "Euler a",
          "seed": 123456789,
          "clipSkip": 2
        },
        "resources": [
          {
            "modelVersionId": 789012,
            "name": "Model Name",
            "type": "lora"
          }
        ]
      }
    }
  }
}
```

**사용처**: `get_model.py` - `fetch_generation()`, `async_process_image_meta()`

---

## 이미지 URL 구조

### 이미지 다운로드 URL

**패턴**: `https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA/{uuid}/original=true/{uuid}.jpeg`

**구성요소**:
- `xG1nkqKTMzGDvpLrqFT7WA`: 고정 버킷 ID
- `{uuid}`: 이미지 고유 식별자
- `original=true`: 원본 크기 요청
- `.jpeg`: 파일 확장자 (실제 형식과 다를 수 있음)

**사용처**: `get_model.py` - `build_image_url()`

```python
BASE_IMAGE_BUCKET = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA"

def build_image_url(uuid: str) -> str:
    return f"{BASE_IMAGE_BUCKET}/{uuid}/original=true/{uuid}.jpeg"
```

---

## 인증

### 쿠키 인증

대부분의 API는 쿠키 인증이 필요합니다.

**필수 쿠키**:
- `__Secure-civitai-token`: 인증 토큰 (JWT)
- `__Secure-next-auth.callback-url`: 콜백 URL
- `__Host-next-auth.csrf-token`: CSRF 토큰

**설정 방법**:

1. 브라우저에서 CivitAI 로그인
2. 개발자 도구 > Application > Cookies
3. 모든 쿠키를 복사하여 `COOKIE_STRING`에 설정

```python
COOKIE_STRING = """
key1=value1; key2=value2; ...
""".strip()

def parse_cookie_string(s: str):
    cookies = {}
    for part in s.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k] = v
    return cookies

session = requests.Session()
session.cookies.update(parse_cookie_string(COOKIE_STRING))
```

---

## Rate Limiting

### 요청 제한

- **권장 간격**: 1.5초 이상
- **429 오류 시**: Exponential backoff 적용

### 구현 예시

```python
REQUEST_LOCK = threading.Lock()
LAST_REQUEST_TIME = 0
REQUEST_INTERVAL = 1.5

def safe_get(url, retries=5, **kwargs):
    for attempt in range(retries):
        with REQUEST_LOCK:
            now = time.time()
            wait_time = REQUEST_INTERVAL - (now - LAST_REQUEST_TIME)
            if wait_time > 0:
                time.sleep(wait_time)

            LAST_REQUEST_TIME = time.time()
            response = session.get(url, **kwargs)

        if response.status_code != 429:
            return response

        # Exponential backoff
        backoff = min(2 ** attempt, 60)
        time.sleep(backoff)

    raise Exception("429 Too Many Requests")
```

---

## HTML 파싱

### 포스트 페이지

**URL**: `https://civitai.com/posts/{post_id}`

**추출 데이터**:
- 제목: `<title>...</title>` 태그
- modelVersionId: `"modelVersionId":\d+` 패턴

```python
def fetch_post_title_and_model_version(post_id: int):
    url = f"https://civitai.com/posts/{post_id}"
    html = session.get(url).text

    # 제목 추출
    m_title = re.search(r"<title>(.*?)\s*\|\s*Civitai</title>", html)
    title = m_title.group(1) if m_title else f"Post_{post_id}"

    # modelVersionId 추출
    m_mv = re.search(r'"modelVersionId"\s*:\s*(\d+)', html)
    model_version_id = int(m_mv.group(1)) if m_mv else None

    return title, model_version_id
```

### 이미지 페이지

**URL**: `https://civitai.com/images/{image_id}`

**추출 데이터**:
- `__NEXT_DATA__` JSON에서 postId 추출

```python
def extract_post_ids_from_image_page(image_id):
    url = f"https://civitai.com/images/{image_id}"
    html = session.get(url).text

    # __NEXT_DATA__ 추출
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        html, re.DOTALL
    )
    data = json.loads(m.group(1))

    # 재귀적으로 postId 검색
    def walk(obj):
        post_ids = set()
        if isinstance(obj, dict):
            if "postId" in obj:
                post_ids.add(obj["postId"])
            for v in obj.values():
                post_ids.update(walk(v))
        elif isinstance(obj, list):
            for v in obj:
                post_ids.update(walk(v))
        return post_ids

    return list(walk(data))
```

---

## 에러 코드

| 코드 | 설명 | 대응 |
|-----|------|-----|
| 200 | 성공 | - |
| 302 | 리다이렉트 | Location 헤더에서 URL 추출 |
| 400 | 잘못된 요청 | 파라미터 확인 |
| 401 | 인증 필요 | 쿠키 갱신 |
| 403 | 접근 금지 | 권한 확인 |
| 404 | 리소스 없음 | 존재 여부 확인 |
| 429 | 요청 과다 | 대기 후 재시도 |
| 500 | 서버 오류 | 잠시 후 재시도 |
