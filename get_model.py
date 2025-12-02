# -*- coding: utf-8 -*-
import requests
import os
import json
import re
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
import threading



###########################################################
# ★ 모든 경로의 기반(ROOT) 를 한 곳에서 정의
###########################################################
ROOT = r"E:\CivitAI"   # ← 네가 원하는 경로로 변경

POSTS_ROOT = os.path.join(ROOT, "Posts")     # get_model.py → 단일 포스트
USERS_ROOT = os.path.join(ROOT, "Users")     # get_all_models.py → 전체 모델

FILTER_CLOTHES_PATH = os.path.join(ROOT, "Filter_Clothes.txt")
FILTER_ETC_PATH     = os.path.join(ROOT, "Filter_Etc.txt")
LORA_PASTE_TARGET_PATH = os.path.abspath(os.path.join(ROOT, "../sd/models/Lora")) # 로라 파일 붙여넣을 폴더


###########################################################
#  ★ 여기에 네 쿠키 전체를 그대로 복붙해라 ★
###########################################################
COOKIE_STRING = """
civitai-route=4fac7bdddd3d8de26621ca392c01ecaf|86d931b62a0bfdebdb632d2af59dceef; __Host-next-auth.csrf-token=dcf0009810e57b3b1f560f1b9ca9a15ad71ccc2e0fb467c8c6f035886173211b%7Cc9baf06e3cc8b8ebb284a7825d8f5754d6c555e97747cb36a53b81d683c46b9f; _sharedID=7a48cb06-1c3b-429d-b822-4539054ec690; _sharedID_cst=TyylLI8srA%3D%3D; _lr_env_src_ats=false; _ga=GA1.1.1775044621.1760120310; _cc_id=b76db4186625f576cda5f268f88e7ba8; TAPAD=%7B%22id%22%3A%225c9955fd-d70e-45aa-a642-93c810be5375%22%7D; __qca=I0-867660018-1760120320347; _ga_N6W8XF7DXE=deleted; logglytrackingsession=cd671a9f-b379-43a6-b3e8-3a03436d879f; ref_landing_page=%2Fsearch%2Fmodels%3FsortBy%3Dmodels_v9%26query%3Dclothes; panoramaId_expiry=1764931013008; panoramaId=87528db802fdd07446a3aa23bd4516d539389c900c9049bcce59b4041aedf155; panoramaIdType=panoIndiv; cto_bundle=9uWXVV9DTXRLMFlHOFdnUTFROGxjcVpyb3VIRXFEc1lZU3lrNTFuQWpUVXpnRG9ZQVZVJTJCTE1ybm9ySnh2ZmJFaW5qWCUyQlgzenRpTlRzRzVXVXk3SHRyJTJCcnY1TUc1UWppWTZoRnZwaGNBTUplVzBYS1l3RjR2Nmp4TklieG13ZXRJZkN5TWcwMng5UkkzNkVpZkJibjNRJTJGdEdhY09lMXoyVHJHRW1PR2tIb1I4N0YlMkJHaGp0VnR4NnQlMkJaSXh1UzJCYWVzdHJGcHBUZ0xQMU0lMkJxRzl5Y3E4RUtaVWclM0QlM0Q; __Secure-next-auth.callback-url=https%3A%2F%2Fcivitai.com%2Fimages%2F46561031; _sharedID_last=Sat%2C%2029%20Nov%202025%2015%3A31%3A13%20GMT; _lr_retry_request=true; civitai-route=5b7cdcef932889ec6d0f9c8f079ffd24|bf4092ed2cc1ac81a1918599cbb73e8c; __gads=ID=511ed81626cfbad7:T=1760120311:RT=1764435493:S=ALNI_MYEoURyzmRRPJ-z4HyZs99Jod_p2g; __gpi=UID=000011a1daa7c570:T=1760120311:RT=1764435493:S=ALNI_MYzvgw6Sx8g5gRotIm_7UT6ECcWiQ; __eoi=ID=60b396e298cc1fa5:T=1760120311:RT=1764435493:S=AA-AfjZJA57OxejXNdM93n8WLUQf; _ga_N6W8XF7DXE=GS2.1.s1764432295$o224$g1$t1764436352$j59$l0$h0; __Secure-civitai-token=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..NW5G-EP_Xc3LOFQG.8SogHo6ubxDUSdNUYRsDIILTzGg0N5oQbFyV_QF8C6q0G9d6-RbixV9oSBKwzFxvtMa-b5O8EZQd5lO4xNrSsvNEY9z9F2_yPsZ33WEkFdAzOWxqX7Fbujz1wctEE6cacSP1nWbfZGqOcAyKXBLAbqVeHAbQa8-cI4gNuhJz_d8834sMy0V-28V495G1SUPhg4RfJ4HoA3RHdpjA39we4vB-kC_Ki07V1JxVu5Wmn40Zj4A7ct8v_IGTyn-9bYGRLhwo4Y0E4-BUGN96vJqNiQQFOFEE6eg3SWx--3F-3ww0N6T26s4GwKVdbyw1-9C3M6-EpaF3hel8G_KzhyBrdlPaZWnylrlkcnqhjSvNWCMOq-9SBdH27l_WkCJNlkUeU5v3FCsp0MXX3TNK5VGnPnpQBJM7T3ThvWDI3Fo1Zw7leDqwup4DvXeuoD1ZjB0RruSmQu9BoYl48rTcaHUPW5nM0jx1WPUl3K85ZICY2qQ-EwBEWLfg-JI2PC4a7l1paTOQjDXjieEAoAMViPisJDfWWkmxzc6qv9k7RkdgQQ25oiKJceopqFdsrQTexL0ESN_O3o3uWh7u0gN8NK2P_hautx4gqSk9SmufSjcZSaGISCwmoMfoxAykaV-2VmpfSlUYrDtKDfVIroFrxX3ClJLj_y8ps9Wbdu5DFtfmqJmOEiazDh-NVJZrpDHfNC3JYLpt-d_kxz_XXjLZqcYAtbitYhPm6EIPbmAxYnujEUF9PsY8iND--lGVovHMgo9_oWn-dLVQT1QisVxmCvLV6LErOMZFqMOmCiHLmjkT7v1_2n_iNvWoITwcBdlFFwM5UuU-9GQWEqaocfZk9vtrXRPnphwjD2lcR77J0dJlTOO2HfoCESMCDBr02t0Vw0GhKshOIEj8ME1YYdKEPQxbFYF6coUSytQ2oaFIKBVi916v2YwFVt1YeMK2qmTPCfku3EvZ7KXFsBlBfSBPAMnC5Op3abhxfjZ1iDRcfSu4e13DQvQG46FL6DZ4Pq4mZhwhCVVUMA4AenFN-Dn0fQi8HNp6H0q8B3bDOlv-RwzaBATxZkKsAWt15FiPKOcwe08EQfyXBaZ30qMkJF15iqQJyi2PaYiHOI05bzEmh5yA-wAedm1_rtohat-YtEjnTUvbDB0og0-IilKbXhNEWLBee74azVHGQsAfFdQcNNdwScVJkpZ-R-E55lw6Ae3f7FeWdniVXnMBj5wPyJidhvWYJGleSgFxkJBO9OMtevdjHuexggRJvslZjC9yIyTTguq4eT6L9tHamc2Lcg3iWbLBJL74kwFFgMwnzA0c4qem1HPl6JpktffnNAVY7aoiB4QWyuxg2ARFkNhUuV9KIGp6.qkA29lO-NFGu-q6BsApo5Q
""".strip()



###########################################################
#  딜레이
###########################################################
RATE_LIMIT_DELAY = 0.3  # 300ms

def safe_get(url, **kwargs):
    """전역적으로 rate-limit 딜레이를 적용한 GET 요청"""
    time.sleep(RATE_LIMIT_DELAY)
    return session.get(url, **kwargs)


###########################################################
#  쿠키 & 세션 설정
###########################################################
def parse_cookie_string(s: str):
    cookies = {}
    for part in s.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k] = v
    return cookies


session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
})
session.cookies.update(parse_cookie_string(COOKIE_STRING))

BASE_IMAGE_BUCKET = "https://image.civitai.com/xG1nkqKTMzGDvpLrqFT7WA"


###########################################################
#  HTML에서 포스트 제목 + modelVersionId 추출
###########################################################
def fetch_post_title_and_model_version(post_id: int):
    print("[INFO] 포스트 제목 + modelVersionId 가져오는 중…")
    url = f"https://civitai.com/posts/{post_id}"
    r = safe_get(url)
    r.raise_for_status()
    html = r.text

    # <title> ... | Civitai</title>
    m_title = re.search(r"<title>(.*?)\s*\|\s*Civitai</title>", html)
    if m_title:
        title = m_title.group(1).strip()
    else:
        title = f"Post_{post_id}"

    # "modelVersionId":1834089 형태 찾기
    m_mv = re.search(r'"modelVersionId"\s*:\s*(\d+)', html)
    model_version_id = int(m_mv.group(1)) if m_mv else None

    print(f"[INFO] 제목 = {title}")
    print(f"[INFO] modelVersionId = {model_version_id}")
    return title, model_version_id


###########################################################
#  safetensors 메타 파싱
###########################################################
def read_safetensors_metadata(path: str):
    try:
        with open(path, "rb") as f:
            header = f.read(8)
            (json_len,) = struct.unpack("<Q", header)
            json_bytes = f.read(json_len)
            metadata = json.loads(json_bytes)
            return metadata.get("__metadata__", {})
    except Exception as e:
        print(f"[ERROR] safetensors 메타 읽기 실패: {e}")
        return {}


###########################################################
#  로라 파일 내부의 ss_output_name 값에 __를 _로 치환
###########################################################
def rewrite_safetensors_metadata(path: str, new_ss_name: str):
    with open(path, "rb") as f:
        header = f.read(8)
        (json_len,) = struct.unpack("<Q", header)

        json_bytes = f.read(json_len)
        metadata = json.loads(json_bytes)

        tensor_data = f.read()  # 나머지 binary 전체
    # 메타데이터 수정
    if "__metadata__" not in metadata:
        metadata["__metadata__"] = {}

    metadata["__metadata__"]["ss_output_name"] = new_ss_name

    # 새 JSON 직렬화
    new_json_bytes = json.dumps(metadata).encode("utf-8")
    new_json_len = struct.pack("<Q", len(new_json_bytes))

    # 새 파일 쓰기
    with open(path, "wb") as f:
        f.write(new_json_len)
        f.write(new_json_bytes)
        f.write(tensor_data)


###########################################################
#  LoRA 다운로드 presigned URL
###########################################################
def get_lora_presigned(model_version_id: int):
    url = f"https://civitai.com/api/download/models/{model_version_id}"
    r = safe_get(url, allow_redirects=False)
    if r.status_code in (302, 301, 303, 307, 308):
        loc = r.headers.get("Location")
        if not loc:
            raise RuntimeError("presigned URL 없음")
        return loc
    raise RuntimeError(f"presigned 요청 실패: {r.status_code}")


###########################################################
#  파일 다운로드
###########################################################
def download_file(url: str, save_path: str, retries=3):
    for attempt in range(retries):
        try:
            with safe_get(url, stream=True, timeout=10) as r:
                r.raise_for_status()
                with open(save_path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        if chunk:
                            f.write(chunk)
            return True  # 성공
        except Exception as e:
            print(f"[ERROR] 다운로드 실패 (시도 {attempt+1}/{retries}): {e}")
            if attempt == retries - 1:
                raise
            print("  [재시도] 1초 후 재시도…")
            time.sleep(1)



###########################################################
#  포스트의 전체 이미지 목록 (image.getInfinite)
###########################################################
def fetch_post_images(post_id: int):
    images = []
    cursor = None
    print("[INFO] 포스트 이미지 목록 수집 중…")

    while True:
        payload = {
            "json": {
                "postId": post_id,
                "pending": True,
                "browsingLevel": None,
                "withMeta": False,
                "include": [],
                "excludedTagIds": [],
                "disablePoi": True,
                "disableMinor": True,
                "cursor": cursor,
                "authed": True
            },
            "meta": {
                "values": {
                    "browsingLevel": ["undefined"],
                    "cursor": ["undefined" if cursor is None else "string"]
                }
            }
        }

        url = "https://civitai.com/api/trpc/image.getInfinite"
        params = {"input": json.dumps(payload, separators=(",", ":"))}
        r = safe_get(url, params=params)
        r.raise_for_status()

        data = r.json()["result"]["data"]["json"]
        items = data.get("items", [])
        images.extend(items)

        cursor = data.get("nextCursor")
        if not cursor:
            break

    print(f"[INFO] 총 {len(images)}개 이미지 발견")
    return images


###########################################################
#  개별 이미지 GenerationData (프롬프트 등)
###########################################################
def fetch_generation(image_id: int):
    payload = json.dumps({"json": {"id": image_id, "authed": True}}, separators=(",", ":"))
    url = "https://civitai.com/api/trpc/image.getGenerationData"
    r = safe_get(url, params={"input": payload})
    r.raise_for_status()
    return r.json()["result"]["data"]["json"]


###########################################################
#  uuid → 실제 이미지 URL
###########################################################
def build_image_url(uuid: str) -> str:
    return f"{BASE_IMAGE_BUCKET}/{uuid}/original=true/{uuid}.jpeg"


###########################################################
#  프롬프트 필터링
###########################################################
# ---------------------------
# 필터 파일 로드
# ---------------------------
def load_filter_file(path):
    words = []
    if not os.path.exists(path):
        print(f"[경고] 필터 파일 없음: {path}")
        return words

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w:
                words.append(w.lower())
    return words

CLOTHES_FILTER = load_filter_file(FILTER_CLOTHES_PATH)
ETC_FILTER = load_filter_file(FILTER_ETC_PATH)

# 전체 필터 = 두 개 합침
FILTER_WORDS = CLOTHES_FILTER + ETC_FILTER

INVALID_FS_CHARS = r'[\\/:*?"<>|]'

def clean_prompt(prompt: str, filters):
    if not prompt:
        return ""

    f_low = [f.lower() for f in filters]

    raw_tokens = [
        p.strip()
        for p in prompt.replace("\n", " ").replace("\r", " ").split(",")
    ]

    tokens = []
    for raw in raw_tokens:
        if not raw:
            tokens.append(None)
        else:
            tokens.append({
                "raw": raw,
                "lower": raw.lower(),
            })

    n = len(tokens)

    starts_group = [False] * n
    ends_group = [False] * n

    # --- 괄호 시작/종료 토큰 판별 ---
    for idx, t in enumerate(tokens):
        if t is None:
            continue
        s = t["raw"]

        i = 0
        while i < len(s) and s[i].isspace():
            i += 1
        if i < len(s) and s[i] == "(":
            starts_group[idx] = True

        j = len(s) - 1
        while j >= 0 and s[j].isspace():
            j -= 1
        if j >= 0 and s[j] == ")":
            ends_group[idx] = True

    # --- 그룹 범위 탐색 ---
    groups = []
    depth = 0
    current_start = None
    for idx in range(n):
        if tokens[idx] is None:
            continue

        if starts_group[idx]:
            if depth == 0:
                current_start = idx
            depth += 1

        if ends_group[idx] and depth > 0:
            depth -= 1
            if depth == 0 and current_start is not None:
                groups.append((current_start, idx))
                current_start = None

    in_group = [False] * n
    for s, e in groups:
        for i in range(s, e + 1):
            in_group[i] = True

    outputs = []
    idx = 0

    # --- 필터링 및 재구성 ---
    while idx < n:
        t = tokens[idx]
        if t is None:
            idx += 1
            continue

        if in_group[idx]:
            for s, e in groups:
                if s == idx:
                    start_i, end_i = s, e
                    break

            kept_inners = []

            for j in range(start_i, end_i + 1):
                tj = tokens[j]
                if tj is None:
                    continue

                raw_s = tj["raw"]

                # 그룹 시작 '(' 제거
                if j == start_i:
                    if raw_s.startswith("("):
                        raw_s = raw_s[1:]

                # 그룹 끝 ')' 제거
                if j == end_i:
                    if raw_s.endswith(")"):
                        raw_s = raw_s[:-1]

                inner = raw_s.strip()
                if not inner:
                    continue

                inner_low = inner.lower()

                # LoRA 태그는 무조건 유지
                if inner.startswith("<lora:"):
                    kept_inners.append(inner)
                    continue

                # 필터 단어 포함 → 제거
                if any(f in inner_low for f in f_low):
                    continue

                kept_inners.append(inner)

            if kept_inners:
                outputs.append("(" + ", ".join(kept_inners) + ")")

            idx = end_i + 1
            continue

        # --- 괄호 외부 토큰 처리 ---
        inner = t["raw"].strip()
        if not inner:
            idx += 1
            continue

        inner_low = inner.lower()

        if inner.startswith("<lora:"):
            outputs.append(inner)
        elif any(f in inner_low for f in f_low):
            pass
        else:
            outputs.append(inner)

        idx += 1

    final = ", ".join(outputs)
    return final + ("," if final else "")


###########################################################
#  LoRA 태그 관리 유틸
###########################################################
def remove_all_lora_tags(prompt: str) -> str:
    """프롬프트 안의 모든 <lora:...> 태그 제거"""
    if not prompt:
        return ""
    return re.sub(r"<lora:[^>]+>", "", prompt).strip()


def extract_lora_from_prompt(prompt: str) -> str:
    """
    prompt 안에서 <lora:NAME:WEIGHT> 형태의 태그를 찾는다.
    여러 개면 마지막 것 사용. WEIGHT 없으면 1로 처리.
    반환값 예: "<lora:Urushihara Satoshi_v3:0.8>"
    """
    if not prompt:
        return ""

    pattern = r"<lora:([^>:]+)(?::([^>]+))?>"
    matches = re.findall(pattern, prompt)
    if not matches:
        return ""

    name, weight = matches[-1]   # 마지막 LoRA 기준
    if not weight:
        weight = "1"
    return f"<lora:{name}:{weight}>"


###########################################################
#  이미지 ID로부터 모든 포스트 ID 얻기
###########################################################
def extract_post_ids_from_image_page(image_id):
    url = f"https://civitai.com/images/{image_id}"
    try:
        r = safe_get(url, timeout=10)
        html = r.text
    except:
        return []

    import re, json
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        html, re.DOTALL
    )
    if not m:
        return []

    # __NEXT_DATA__ JSON 파싱
    try:
        raw = m.group(1).strip()

        # 혹시 script 태그 안에 쓸데없는 공백/문자 섞여 있어도
        # 첫 '{'부터 마지막 '}'까지만 잘라서 로드
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]

        data = json.loads(raw)
    except Exception as e:
        print("[WARN] __NEXT_DATA__ JSON 파싱 실패:", e)
        return []

    post_ids = set()

    # JSON 전체를 재귀로 돌면서 postId / posts / post.id 검색
    def walk(obj):
        if isinstance(obj, dict):
            # Case 1: image.postId 또는 어디든지 있는 postId
            if "postId" in obj:
                pid = obj["postId"]
                if isinstance(pid, int):
                    post_ids.add(pid)

            # Case 2: posts: [{ id: ... }, ...]
            if "posts" in obj and isinstance(obj["posts"], list):
                for p in obj["posts"]:
                    if isinstance(p, dict):
                        pid = p.get("id")
                        if isinstance(pid, int):
                            post_ids.add(pid)

            # Case 3: post: { id: ... }
            if "post" in obj and isinstance(obj["post"], dict):
                pid = obj["post"].get("id")
                if isinstance(pid, int):
                    post_ids.add(pid)

            # 하위 값들 재귀
            for v in obj.values():
                walk(v)

        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)

    if not post_ids:
        # 디버그용으로 한 번만 찍어보고 싶으면 여기에 print 추가해도 됨
        # print("[DEBUG] __NEXT_DATA__ 에서 postId 를 찾지 못함")
        return []

    return list(post_ids)





###########################################################
#  공통 코어
###########################################################
def _process_post_core(post_id: int, save_dir: str):
    """
    기존 process_post 로직 전체를 포함한다.
    다만 저장경로 folder 대신 save_dir을 사용한다.
    """
    print(f"[PROCESS] POST 처리 시작: {post_id}")

    # 실패 정보 수집 dict
    failed = {
        "failed_image_urls": [],
        "failed_lora": None
    }    

    # 기존 코드 1) 제목 + modelVersionId
    title, model_version_id = fetch_post_title_and_model_version(post_id)

    # 🔥 기존엔 여기서 folder = re.sub... 후 폴더를 만들었음
    # 이제는 save_dir(절대경로)만 사용한다.
    folder = save_dir
    os.makedirs(folder, exist_ok=True)
    print(f"[INFO] 저장 폴더: {folder}")

    # 2) 이미지 목록
    images = fetch_post_images(post_id)

    # ================================
    #  멀티쓰레드 LoRA 비동기 처리
    # ================================
    lora_future = None
    sanitized_ss_name = None
    lora_tag = ""

    if model_version_id:
        print(f"[THREAD] LoRA 작업 비동기 실행… modelVersionId={model_version_id}")

        # LoRA 작업을 즉시 비동기 실행 (대기하지 않음)
        executor = ThreadPoolExecutor(max_workers=1)
        lora_future = executor.submit(process_lora_task, folder, model_version_id, None)

    else:
        print("[WARN] modelVersionId 없음 → LoRA 스킵")

    ###########################################################
    # 4) 이미지 + 메타 처리
    ###########################################################
    for idx, img in enumerate(images, 1):
        image_id = img.get("id")
        uuid = img.get("url") or img.get("uuid")

        print(f"[{idx}/{len(images)}] image_id={image_id}, uuid={uuid}")

        if not uuid:
            print("  [WARN] uuid 없음 → 스킵")
            continue

        # 저장 경로
        img_filename = f"{image_id}.png"
        img_path = os.path.join(folder, img_filename)

        img_url = build_image_url(uuid)

        # 🔥 파일 크기 체크 → 100KB(=102400 bytes) 미만이면 재다운로드
        if os.path.exists(img_path):
            size = os.path.getsize(img_path)
            if size < 102400:  # 100KB 미만
                print(f"[INFO] 이미지 파일 크기 {size} bytes → 너무 작음, 재다운로드 진행")

                try:
                    os.remove(img_path)
                    print("  [INFO] 기존 파일 삭제 완료")
                except Exception as e:
                    print(f"  [ERROR] 기존 파일 삭제 실패: {e}")

                # 재다운로드 시도
                try:
                    download_file(img_url, img_path)
                    print("  [INFO] 재다운로드 성공")
                except Exception as e:
                    print(f"  [ERROR] 재다운로드 실패: {e}")
                    failed["failed_image_urls"].append({
                        "download_url": img_url,
                        "page_url": f"https://civitai.com/images/{image_id}"
                    })
                    continue

                # 다운로드 성공했으면 다음 단계 진행
                # (기본 로직 계속)
                # GenerationData 처리로 넘어간다.
                # 따라서 아래 else 블록 SKIP
                pass

            else:
                print(f"[SKIP] 이미지 이미 존재: {img_filename}")
        else:
            print(f"[Download] {img_filename}")
            try:
                try:
                    download_file(img_url, img_path)
                except Exception:
                    failed["failed_image_urls"].append({
                        "download_url": img_url,
                        "page_url": f"https://civitai.com/images/{image_id}"
                    })
                    continue
            except Exception as e:
                print(f"[ERROR] 이미지 다운로드 실패: {e}")
                continue

        # GenerationData
        try:
            gen = fetch_generation(image_id)
        except Exception as e:
            print(f"  [ERROR] GenerationData 실패: {e}")
            continue

        meta = gen.get("meta") or {}
        
        resources_used = gen.get("resources") or []
        prompt = meta.get("prompt", "") or ""
        negative = meta.get("negativePrompt", "") or ""
        cfg = meta.get("cfgScale", "")
        steps = meta.get("steps", "")
        sampler = meta.get("sampler", "")
        seed = meta.get("seed", "")
        clip_skip = meta.get("clipSkip", "")

        prompt = re.sub(r"[\r\n]+", " ", prompt).strip()
        negative = re.sub(r"[\r\n]+", " ", negative).strip()

        # 🔥 prompt 내부의 로라를 먼저 모두 제거해야 clean_prompt가 문제 없이 동작함
        prompt_no_lora = remove_all_lora_tags(prompt)

        # 1) 로라 제거된 프롬프트를 기준으로 필터링
        prompt_clean = clean_prompt(prompt_no_lora, FILTER_WORDS)
        prompt_with_clothes = clean_prompt(prompt_no_lora, ETC_FILTER)

        # 3) raw 프롬프트(prompt) 에서 LoRA 태그 다시 추출
        final_lora_tag = extract_lora_from_prompt(prompt)

        # raw 프롬프트에 LoRA가 없다면, safetensors 메타에서 보정용으로 한 번 더 시도
        if not final_lora_tag and sanitized_ss_name:
            base_name = sanitized_ss_name.split(":")[0]  # 이름만 사용
            final_lora_tag = f"<lora:{base_name}:1>"

        # 4) 최종 LoRA 태그를 prompt_* 에 반영
        if final_lora_tag:
            if prompt_clean:
                prompt_clean = f"{final_lora_tag}, {prompt_clean}"
            else:
                prompt_clean = f"{final_lora_tag},"

            if prompt_with_clothes:
                prompt_with_clothes = f"{final_lora_tag}, {prompt_with_clothes}"
            else:
                prompt_with_clothes = f"{final_lora_tag},"
        else:
            final_lora_tag = ""

        meta_path = os.path.join(folder, f"{image_id}.txt")
        meta_out = {
            "prompt": prompt_clean,
            "prompt_with_clothes": prompt_with_clothes,
            "negative": negative,
            "cfg": cfg,
            "steps": steps,
            "sampler": sampler,
            "seed": seed,
            "clip_skip": clip_skip,
            "raw_prompt": prompt,
            "lora": "",
            "url": f"https://civitai.com/images/{image_id}",
            "resources_used": resources_used
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_out, f, indent=2, ensure_ascii=False)

        print(f"  [META] 저장: {meta_path}\n")

    print(f"=== POST {post_id} 처리 완료 ===\n")

    return failed


def process_lora_task(folder, model_version_id, failed_dict_lock):
    """
    멀티쓰레드로 실행되는 LoRA 처리 함수
    - presigned URL 얻기
    - 다운로드
    - ss_output_name 정규화
    - 최종 폴더 복사
    - 실패정보는 dict 형태로 리턴
    """

    result = {
        "failed_lora": None,
        "lora_tag": "",
        "sanitized_ss_name": None
    }

    try:
        # 1) model-versions 정보 가져오기
        mv_url = f"https://civitai.com/api/v1/model-versions/{model_version_id}"
        mv = safe_get(mv_url)
        mv.raise_for_status()
        mv_json = mv.json()

        files = mv_json.get("files", [])
        safes = [f for f in files if f.get("name","").endswith(".safetensors")]

        if not safes:
            print("[WARN] safetensors 파일 없음")
            return result

        # 첫 safetensors 파일만 우선 처리 (나중에 전부 처리로 확대 가능)
        info = safes[0]
        lora_filename = info["name"]

        # 2) presigned URL 얻기
        try:
            presigned = get_lora_presigned(model_version_id)
        except Exception as e:
            result["failed_lora"] = {
                "lora_url": None,
                "copy_error": f"presigned 실패: {e}"
            }
            return result

        # 3) 다운로드 경로
        lora_path = os.path.join(folder, lora_filename)

        # 다운로드 (이미 있으면 스킵)
        if not os.path.exists(lora_path):
            try:
                download_file(presigned, lora_path)
            except Exception as e:
                result["failed_lora"] = {
                    "lora_url": presigned,
                    "copy_error": f"LoRA 다운로드 실패: {e}"
                }
                return result
        else:
            print(f"[INFO] LoRA 이미 있음: {lora_filename}")

        # 4) ss_output_name 읽기 → 정규화
        meta = read_safetensors_metadata(lora_path)
        ss_name = meta.get("ss_output_name")
        if ss_name:
            sanitized = ss_name.replace("__", "_")
            rewrite_safetensors_metadata(lora_path, sanitized)
            result["sanitized_ss_name"] = sanitized
            result["lora_tag"] = f"<lora:{sanitized}:1>"
        else:
            result["sanitized_ss_name"] = None

        # 5) Stable Diffusion 폴더로 복사
        folder_abs = os.path.abspath(folder)
        exclude_abs = os.path.abspath(ROOT)

        if folder_abs.startswith(exclude_abs):
            relative = folder_abs[len(exclude_abs):].lstrip("\\/")
        else:
            relative = os.path.basename(folder_abs)

        final_dir = os.path.abspath(os.path.join(LORA_PASTE_TARGET_PATH, relative))
        os.makedirs(final_dir, exist_ok=True)

        final_lora_path = os.path.join(final_dir, lora_filename)

        if not os.path.exists(final_lora_path):
            try:
                shutil.copy2(lora_path, final_lora_path)
            except Exception as e:
                result["failed_lora"] = {
                    "lora_url": presigned,
                    "copy_error": f"LoRA 복사 실패: {e}"
                }
        else:
            print(f"[SKIP] 최종 경로에 이미 존재: {final_lora_path}")

    except Exception as e:
        result["failed_lora"] = {"copy_error": str(e)}

    return result



###########################################################
#  기존 함수 유지 — test3.py 단독 실행용
###########################################################
def process_post(post_id: int):
    title, _ = fetch_post_title_and_model_version(post_id)

    # 안전한 폴더명 변환
    folder_name = re.sub(INVALID_FS_CHARS, "_", title)

    # Posts/{제목}
    folder = os.path.join(POSTS_ROOT, folder_name)
    folder = os.path.abspath(folder)

    return _process_post_core(post_id, folder)


###########################################################
#  새로운 함수 — get_all_models.py 전용
###########################################################
def process_post_to_dir(post_id: int, save_dir: str):
    """
    get_all_models.py에서 사용하는 버전
    저장 경로는 완전히 save_dir로 강제됨
    """
    save_dir = os.path.abspath(save_dir)
    return _process_post_core(post_id, save_dir)




###########################################################
#  메인 실행
###########################################################
if __name__ == "__main__":
    post_url = input("CivitAI 포스트 URL 입력: ").strip()

    m = re.search(r"/posts/(\d+)", post_url)
    if not m:
        print("URL에서 postId 추출 실패")
        raise SystemExit

    post_id = int(m.group(1))
    process_post(post_id)