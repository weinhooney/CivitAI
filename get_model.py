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
import subprocess
import shlex
from thread_pool import IMG_META_EXECUTOR, BG_LORA_EXECUTOR

# ★ get_all_models.py 를 import 하지 않기 위해 전역 future 리스트를 외부에서 주입받는 구조로 변경
IMG_META_FUTURES = None
LORA_FUTURES = None

def set_future_lists(img_list, lora_list):
    global IMG_META_FUTURES, LORA_FUTURES
    IMG_META_FUTURES = img_list
    LORA_FUTURES = lora_list

# get_all_models.py 에서 주입해줄 다운로드 대상 리스트
DOWNLOAD_TARGETS = None

def set_download_targets(target_list):
    """get_all_models.py에서 DOWNLOAD_TARGETS 리스트를 주입해준다."""
    global DOWNLOAD_TARGETS
    DOWNLOAD_TARGETS = target_list


###########################################################
# IDM
###########################################################
IDM_PATH = r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe"


def idm_add_to_queue(url: str, save_dir: str, file_name: str):
    """
    IDM 다운로드 대기열에 추가 (/a)
    다운로드는 아직 시작되지 않음.
    """
    cmd = f'"{IDM_PATH}" /d "{url}" /p "{save_dir}" /f "{file_name}" /a'
    subprocess.Popen(shlex.split(cmd),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
    print(f"[IDM] Added to queue: {file_name}")

def idm_start_download():
    """IDM 대기열 다운로드 시작 (/s)"""
    subprocess.Popen(shlex.split(f'"{IDM_PATH}" /s'),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
    print("[IDM] Queue download started!")



###########################################################
# ★ 모든 경로의 기반(ROOT) 를 한 곳에서 정의
###########################################################
ROOT = r"E:\CivitAI"   # ← 네가 원하는 경로로 변경

POSTS_ROOT = os.path.join(ROOT, "Posts")     # get_model.py → 단일 포스트
USERS_ROOT = os.path.join(ROOT, "Users")     # get_all_models.py → 전체 모델

FILTER_SEX_PATH = os.path.join(ROOT, "Filter_Sex.txt")
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
# 이미지 중복 확인
###########################################################
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".jfif"}

def find_existing_image_by_id(folder, image_id):
    """
    폴더 내에서 image_id에 해당하는 이미지 파일을 확장자 무관하게 찾는다.
    """
    for name in os.listdir(folder):
        base, ext = os.path.splitext(name)
        if ext.lower() in IMAGE_EXTS and base == str(image_id):
            return os.path.join(folder, name)   # 실제 파일 경로 반환
    return None




###########################################################
# URL로부터 이미지 확장자 추출
###########################################################
def extract_image_extension(url):
    clean_url = url.split("?")[0]
    _, ext = os.path.splitext(clean_url)
    return ext.lower() if ext else ".png"



###########################################################
#  딜레이
###########################################################
REQUEST_LOCK = threading.Lock()
LAST_REQUEST_TIME = 0
REQUEST_INTERVAL = 1.0   # 최소 1초 — CivitAI 안정권

def safe_get(url, retries=5, **kwargs):
    global LAST_REQUEST_TIME

    for attempt in range(retries):
        with REQUEST_LOCK:

            # 요청 간 간격 보장
            now = time.time()
            wait = REQUEST_INTERVAL - (now - LAST_REQUEST_TIME)
            if wait > 0:
                time.sleep(wait)

            LAST_REQUEST_TIME = time.time()

            response = session.get(url, **kwargs)

            # success
            if response.status_code != 429:
                return response

            # 429면 LOCK 안에서 대기해야 한다 (중요!)
            backoff = 2 ** attempt
            print(f"[RATE LIMIT] 429 → {backoff}초 대기")
            time.sleep(backoff)

    raise Exception(f"429 Too Many Requests: {url}")



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

SEX_FILTER = load_filter_file(FILTER_SEX_PATH)
CLOTHES_FILTER = load_filter_file(FILTER_CLOTHES_PATH)
ETC_FILTER = load_filter_file(FILTER_ETC_PATH)

# 전체 필터 = 두 개 합침
FILTER_WORDS = SEX_FILTER + CLOTHES_FILTER + ETC_FILTER

INVALID_FS_CHARS = r'[\\/:*?"<>|]'

import re
...
def normalize_filter_item(text: str) -> str:
    """
    필터 비교/중복 제거용으로 토큰을 정규화한다.
    예:
      "(Naughty smile:0.7)"  -> "naughty smile"
      "( Naughty smile )"    -> "naughty smile"
      "Naughty smile:0.8"    -> "naughty smile"
      " Naughty  smile  "    -> "naughty smile"
    """
    if not text:
        return ""

    s = text.strip()

    # 바깥 한 겹 괄호 제거: ( ... )
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()

    # 끝에 붙은 가중치 제거: ":0.7", ": 0.8", ":1", ": 1.0" 등
    s = re.sub(r"\s*:\s*[0-9]+(?:\.[0-9]+)?\s*$", "", s)

    # 공백 여러 개 → 하나로
    s = re.sub(r"\s+", " ", s)

    # 필터 비교는 소문자로
    return s.lower()


def normalize_prompt_basic(prompt: str) -> str:
    if not prompt:
        return ""

    # 0) 필요하면 디버그용 로그
    if "BREAK" in prompt:
        print(f"[DEBUG] BREAK before replace: {repr(prompt)}")

    # 1) BREAK → 콤마 (정규식 쓰지 말고 그냥 문자열로 다 갈아버리자)
    #    어디에 붙어있든 "BREAK"라는 연속 글자가 나오면 전부 콤마로 교체
    prompt = prompt.replace("BREAK", ",")

    # 2) <lora:...> 태그 앞뒤에 콤마 자동 삽입
    #    예: "looking at viewer <lora:foo:1> breast"
    #      -> "looking at viewer , <lora:foo:1> , breast"
    prompt = re.sub(r"\s*(<lora:[^>]+>)\s*", r", \1, ", prompt)

    # 3) 콤마 정리
    #    - 콤마 기준으로 split
    #    - 양쪽 공백 제거
    #    - 빈 문자열은 버림 → ",, ,," 같은 건 다 사라짐
    parts = [p.strip() for p in prompt.split(",") if p.strip()]

    if not parts:
        return ""

    # 다시 ", "로 붙여서 깔끔한 형태로 반환
    return ", ".join(parts)




def clean_prompt(prompt: str, filters):
    if not prompt:
        return ""

    prompt = normalize_prompt_basic(prompt)

    # 필터 문자열을 정규화해서 키셋으로 만든다.
    # 예: "Naughty smile", "(Naughty smile)", "Naughty smile:0.7" 전부 "naughty smile" 로 통일
    f_keys = set()
    for f in filters:
        key = normalize_filter_item(f)
        if key:
            f_keys.add(key)

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

    # --- 그룹 구간 계산 (중첩 괄호 고려) ---
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

        # ===== 괄호 안 토큰 처리 =====
        if in_group[idx]:
            # 현재 idx 가 속한 그룹 찾기
            start_i = end_i = idx
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
                    raw_s = raw_s.lstrip()
                    if raw_s.startswith("("):
                        raw_s = raw_s[1:]

                # 그룹 끝 ')' 제거
                if j == end_i:
                    raw_s = raw_s.rstrip()
                    if raw_s.endswith(")"):
                        raw_s = raw_s[:-1]

                inner = raw_s.strip()
                if not inner:
                    continue

                # LoRA 태그는 무조건 유지
                if inner.startswith("<lora:"):
                    kept_inners.append(inner)
                    continue

                # 🔹 필터용 정규화 키로 비교
                #    "(Naughty smile:0.7)" -> "naughty smile"
                key = normalize_filter_item(inner)
                if key and key in f_keys:
                    # 필터에 걸렸으면 제거
                    continue

                kept_inners.append(inner)

            if kept_inners:
                outputs.append("(" + ", ".join(kept_inners) + ")")

            idx = end_i + 1
            continue

        # ===== 괄호 밖 토큰 처리 =====
        inner = t["raw"].strip()
        if not inner:
            idx += 1
            continue

        if inner.startswith("<lora:"):
            outputs.append(inner)
        else:
            key = normalize_filter_item(inner)
            if key and key in f_keys:
                # 필터 대상이면 버린다
                pass
            else:
                outputs.append(inner)


        idx += 1

    # 1차 조합
    final = ", ".join(outputs)

    if not final:
        return ""

    # 2차 정리: ",, , ,, tag" 같은 것들을 하나의 콤마 기준으로 정규화
    #   - 콤마로 다시 나눈 뒤 공백/빈 요소 제거
    parts = [p.strip() for p in final.split(",") if p.strip()]
    if not parts:
        return ""

    final = ", ".join(parts)

    # 기존과 동일하게 마지막에 콤마 하나 유지
    return final + ","




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


def async_process_image_meta(image_id, uuid, folder):
    try:
        gen = fetch_generation(image_id)
        meta = gen.get("meta") or {}

        resources_used = gen.get("resources") or []
        # resources_used 안에 download_endpoint 추가
        enriched_resources = []
        for r in resources_used:
            entry = dict(r)

            mv_id = r.get("modelVersionId")
            if mv_id:
                # presigned URL을 요청하지 않고, 고정 엔드포인트만 설정
                entry["download_url"] = f"https://civitai.com/api/download/models/{mv_id}"

            enriched_resources.append(entry)

        prompt = meta.get("prompt", "") or ""
        negative = meta.get("negativePrompt", "") or ""
        cfg = meta.get("cfgScale", "")
        steps = meta.get("steps", "")
        sampler = meta.get("sampler", "")
        seed = meta.get("seed", "")
        clip_skip = meta.get("clipSkip", "")

        # 줄바꿈 제거
        prompt = re.sub(r"[\r\n]+", " ", prompt).strip()
        negative = re.sub(r"[\r\n]+", " ", negative).strip()

        # 로라 제거
        prompt_no_lora = remove_all_lora_tags(prompt)

        # 필터링
        prompt_clean = clean_prompt(prompt_no_lora, FILTER_WORDS)
        prompt_with_clothes = clean_prompt(prompt_no_lora, ETC_FILTER)

        # 프롬프트 안에 원본 LoRA 태그가 있으면 검출
        final_lora_tag = extract_lora_from_prompt(prompt)

        # LoRA 태그를 앞에 붙이기
        if final_lora_tag:
            prompt_clean = f"{final_lora_tag}, {prompt_clean}" if prompt_clean else f"{final_lora_tag},"
            prompt_with_clothes = f"{final_lora_tag}, {prompt_with_clothes}" if prompt_with_clothes else f"{final_lora_tag},"

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
            "lora": final_lora_tag or "",
            "url": f"https://civitai.com/images/{image_id}",
            "resources_used": enriched_resources
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_out, f, indent=2, ensure_ascii=False)

        print(f"[META] 생성 완료: {meta_path}")

    except Exception as e:
        print(f"[ERROR] 메타 파일 생성 실패 ({image_id}): {e}")
        # 메타 작업 실패도 실패 로그에 남겨둔다 (type은 image로 통일)
        try:
            import download_state
            download_state.mark_failed(
                image_id,
                "image",
                f"meta_failed: {e}",
                {
                    "folder": folder,
                    "uuid": uuid,
                    "url": f"https://civitai.com/images/{image_id}",
                    "meta_path": os.path.join(folder, f"{image_id}.txt"),
                }
            )
        except Exception:
            pass




###########################################################
#  다운로드했는지 확인
###########################################################
def is_lora_downloaded(downloaded_records, model_version_id):
    if not downloaded_records:
        return False
    for item in downloaded_records.get("lora", []):
        if item["model_version_id"] == model_version_id:
            return True
    return False



def is_image_downloaded(downloaded_records, image_id):
    if not downloaded_records:
        return False
    for item in downloaded_records.get("images", []):
        if item["image_id"] == image_id:
            return True
    return False




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
        lora_future = BG_LORA_EXECUTOR.submit(process_lora_task, folder, model_version_id, None)
        LORA_FUTURES.append(lora_future)

    else:
        print("[WARN] modelVersionId 없음 → LoRA 스킵")

    ###########################################################
    # 4) 이미지 + 메타 처리
    ###########################################################
    for idx, img in enumerate(images, 1):
        image_id = img.get("id")
        uuid = img.get("url") or img.get("uuid")

        print(f"[{idx}/{len(images)}] image_id={image_id}, uuid={uuid}")

        # =====================================================
        # 🚫 통합 로그 기반 이미지 중복 체크
        # =====================================================
        import download_state
        if download_state.is_success(image_id, "image"):
            print(f"[SKIP] 이미지 이미 성공 로그에 있음 → imageId={image_id}")
            continue
        # =====================================================


        if not uuid:
            print("  [WARN] uuid 없음 → 스킵")
            failed["failed_image_urls"].append({
                "download_url": None,
                "page_url": f"https://civitai.com/images/{image_id}"
            })
            continue

        # 이미지 파일명과 로컬 경로
        img_url = build_image_url(uuid)
        ext = extract_image_extension(img_url)
        default_filename = f"{image_id}{ext}"
        default_path = os.path.join(folder, default_filename)

        # =============================================
        # ① 이미지 존재 여부 체크 → 있으면 IDM queue 추가하지 않음
        #    (확장자 .png/.jpg/.jpeg 상관없이 image_id 기준으로 찾음)
        # =============================================
        existing_path = find_existing_image_by_id(folder, image_id)

        # 우리가 실제로 기대하는 로컬 파일 경로 (확장자 포함)
        expected_path = existing_path or default_path

        if existing_path:
            size = os.path.getsize(existing_path)
            if size >= 3000:
                print(f"[SKIP] 정상 이미지 존재 ({os.path.basename(existing_path)})")
                # 이미 폴더에 정상 파일이 있으므로 성공 로그에 추가
                try:
                    import download_state
                    download_state.mark_success(image_id, "image", existing_path, size)
                except Exception:
                    pass
            else:
                print(f"[WARN] 손상 이미지 감지 ({size} bytes) → 재다운로드: {existing_path}")
                try:
                    os.remove(existing_path)
                except:
                    pass
                # 손상 파일도 같은 이름으로 다시 받는다
                idm_add_to_queue(img_url, folder, os.path.basename(existing_path))
        else:
            print(f"[IDM] 신규 이미지 다운로드: {image_id}")
            # expected_path == default_path
            idm_add_to_queue(img_url, folder, os.path.basename(default_path))

        # 다운로드 대상 목록에 추가 (JSON 로그 & 자동 복구용)
        #  🔥 이제 get_all_models를 import하지 않고,
        #  get_all_models에서 주입해준 DOWNLOAD_TARGETS 전역을 그대로 사용한다.
        from get_model import DOWNLOAD_TARGETS  # 자기 자신 모듈의 전역을 참조

        if DOWNLOAD_TARGETS is not None:
            DOWNLOAD_TARGETS.append({
                "type": "image",
                "post_id": post_id,
                "image_id": image_id,
                "uuid": uuid,
                "download_url": img_url,
                "page_url": f"https://civitai.com/images/{image_id}",
                # ✅ 실제 존재하는(또는 앞으로 받을) 파일 경로 기준으로 저장
                "expected_file_path": expected_path,
            })
        else:
            # 혹시라도 세팅이 안 된 경우 디버그용
            print("[WARN] DOWNLOAD_TARGETS가 None이라 이미지 대상 리스트에 추가하지 못함")



        # =============================================
        # ② 메타 생성은 다운로드 여부와 무관하게 병렬 처리
        # =============================================
        future = IMG_META_EXECUTOR.submit(async_process_image_meta, image_id, uuid, folder)
        IMG_META_FUTURES.append(future)

    print(f"=== POST {post_id} 처리 완료 ===\n")

    return failed


def process_lora_task(folder, model_version_id, _):
    import download_state

    # 1) 통합 성공 로그 기반 중복 체크
    if download_state.is_success(model_version_id, "lora"):
        print(f"[SKIP] 이미 성공 로그에 있는 LoRA → modelVersionId={model_version_id}")
        return  # 해당 LoRA 처리 전체 스킵

    # 2) 모델 버전 메타 받아서 파일 정보 확인
    mv_url = f"https://civitai.com/api/v1/model-versions/{model_version_id}"
    mv = safe_get(mv_url)
    mv_json = mv.json()

    safes = [f for f in mv_json.get("files", []) if f["name"].endswith(".safetensors")]
    if not safes:
        print(f"[LORA][WARN] safetensors 파일 없음 → modelVersionId={model_version_id}")
        return

    info = safes[0]
    remote_size = info.get("sizeKB", 0) * 1024
    lora_filename = info["name"]
    lora_path = os.path.join(folder, lora_filename)

    from get_model import DOWNLOAD_TARGETS  # 주입된 전역 리스트 사용

    if DOWNLOAD_TARGETS is not None:
        DOWNLOAD_TARGETS.append({
            "type": "lora",
            "post_id": None,  # LoRA는 post_id가 없으므로 None
            "model_version_id": model_version_id,
            "presigned_url": None,  # presigned 이후에 채워짐
            "expected_file_path": lora_path,
            "expected_file_size": remote_size,
            "final_paste_path": None,  # 후처리 단계에서 채워짐
        })
    else:
        print("[WARN] DOWNLOAD_TARGETS가 None이라 LoRA 대상 리스트에 추가하지 못함")


    # 3) 🔥 로컬에 이미 파일이 있고, 용량이 remote_size 이상이면
    #    → 성공 로그에 추가 + IDM 안 태우고 후처리만 실행
    actual_size = 0
    if os.path.exists(lora_path):
        actual_size = os.path.getsize(lora_path)

    if os.path.exists(lora_path) and actual_size >= remote_size:
        print(f"[SKIP] LoRA 이미 존재하고 정상 용량 확인됨: {lora_filename}")

        # ✅ 여기서 성공 로그에 등록
        try:
            download_state.mark_success(model_version_id, "lora", lora_path, actual_size)
        except Exception:
            pass

        # 정규화 + SD 폴더 복사는 그대로 수행
        wait_and_finalize_lora(folder, None, lora_filename)
        return

    elif os.path.exists(lora_path) and actual_size < remote_size:
        print(f"[WARN] 기존 파일 용량 부족({actual_size} < {remote_size}) → 재다운로드")
        try:
            os.remove(lora_path)
        except:
            pass


    presigned = get_lora_presigned(model_version_id)
    DOWNLOAD_TARGETS[-1]["presigned_url"] = presigned

    # IDM 대기열에 추가
    idm_add_to_queue(presigned, folder, lora_filename)
    print(f"[IDM] LoRA 대기열에 추가됨: {lora_filename}") 

    # ⚠ 여기서는 /s 호출 안 함
    # 실제 다운로드 시작은 _process_post_core 마지막에서 한 번만 호출된다.

    # 후처리
    wait_and_finalize_lora(folder, presigned, lora_filename)
    
    print(f"[LORA] 처리 완료: {lora_filename}")



def wait_and_finalize_lora(folder, presigned, lora_filename):
    lora_path = os.path.join(folder, lora_filename)

    # presigned가 None이면 "이미 존재하는 파일의 사후처리 모드"
    if presigned is None:
        print(f"[LORA] 기존 파일 사후 처리 시작: {lora_filename}")
    else:
        print(f"[IDM] LoRA 다운로드 대기중: {lora_filename}")

    # ------------------------------------------------------
    # 로라 expected_size 검색 (DOWNLOAD_TARGETS에서 찾기)
    #   🔥 이제 get_all_models이 아니라, get_model 전역에서 주입받은 리스트 사용
    # ------------------------------------------------------
    from get_model import DOWNLOAD_TARGETS

    expected_size = None
    model_version_id = None

    if DOWNLOAD_TARGETS is not None:
        # presigned 모드라면 model_version_id를 DOWNLOAD_TARGETS에서 lookup 가능
        for item in DOWNLOAD_TARGETS:
            if item["type"] == "lora" and item["expected_file_path"] == lora_path:
                expected_size = item.get("expected_file_size")
                model_version_id = item.get("model_version_id")
                break
    else:
        print("[WARN] DOWNLOAD_TARGETS가 None이라 expected_size lookup 불가")


    # ------------------------------------------------------
    # 정확한 다운로드 완료 대기 (expected_size 비교) + 타임아웃
    # ------------------------------------------------------
    start_ts = time.time()
    last_size = -1
    stagnant_count = 0
    TIMEOUT_SEC = 60 * 20  # 20분, 필요하면 조절

    while True:
        if os.path.exists(lora_path):
            size = os.path.getsize(lora_path)

            if size != last_size:
                last_size = size
                stagnant_count = 0
            else:
                stagnant_count += 1

            if expected_size:
                # 너무 빡빡하게 == 말고 어느 정도 여유를 둔다
                if size >= expected_size:
                    break
            else:
                # presigned가 없고, 용량이 조금이라도 있고 일정 시간 동안 변화 없으면 완료로 간주
                if size > 0 and stagnant_count >= 3:
                    break

        # 타임아웃 처리
        if time.time() - start_ts > TIMEOUT_SEC:
            print(f"[LORA][ERROR] 다운로드 타임아웃: {lora_filename}")
            if model_version_id:
                import download_state
                download_state.mark_failed(
                    model_version_id,
                    "lora",
                    "timeout",
                    {
                        "expected_file_path": lora_path,
                        "expected_file_size": expected_size,
                        "last_size": last_size,
                    },
                )
            return  # 더 이상 후처리 진행하지 않고 종료

        time.sleep(2)



    print(f"[IDM] 다운로드 완료됨: {lora_filename}")

    # ------------------------------------------------------
    # ss_output_name 정규화
    #  - 있으면: __ → _ 만 적용
    #  - 없으면: 파일명(확장자 제거)을 정규화(__ → _) 해서
    #             1) ss_output_name 으로 쓰고
    #             2) 실제 파일 이름도 정규화된 이름으로 rename
    # ------------------------------------------------------
    meta = read_safetensors_metadata(lora_path)
    ss_name = meta.get("ss_output_name")
    if isinstance(ss_name, str):
        ss_name = ss_name.strip()
    else:
        ss_name = ""

    # 현재 lora_filename 기준 정규화 이름 계산
    base_name, ext = os.path.splitext(lora_filename)
    normalized_base = base_name.replace("__", "_")
    normalized_filename = normalized_base + ext

    if not ss_name:
        # 🔹 ss_output_name 없으면 → 정규화된 파일명(확장자 제거)을 ss_output_name 으로 사용
        new_path = lora_path

        # 🔹 실제 파일 이름도 정규화된 이름으로 변경
        if normalized_filename != lora_filename:
            candidate = os.path.join(folder, normalized_filename)
            if os.path.exists(candidate):
                print(f"[LORA][WARN] 정규화된 파일명이 이미 존재 → 파일명 변경 스킵: {candidate}")
                # 이 경우에는 파일명은 그대로 두고 ss_output_name만 맞추고 간다.
            else:
                os.rename(lora_path, candidate)
                print(f"[LORA] 파일명 정규화: {lora_filename} → {normalized_filename}")
                lora_filename = normalized_filename
                new_path = candidate

        try:
            rewrite_safetensors_metadata(new_path, normalized_base)
            print(f"[LORA] ss_output_name 없음 → 파일명 기반으로 설정: {normalized_base}")
        except Exception as e:
            print(f"[ERROR] ss_output_name 설정 실패: {e}")

        # 이후 로직에서 사용할 실제 경로 갱신
        lora_path = new_path

    else:
        # 🔹 ss_output_name 이 이미 있으면 → __ 를 _ 로만 정규화
        sanitized = ss_name.replace("__", "_")
        try:
            rewrite_safetensors_metadata(lora_path, sanitized)
            print(f"[LORA] ss_output_name 정규화 완료: {sanitized}")
        except Exception as e:
            print(f"[ERROR] ss_output_name 정규화 실패: {e}")


    # SD 폴더로 복사
    folder_abs = os.path.abspath(folder)
    exclude_abs = os.path.abspath(ROOT)

    if folder_abs.startswith(exclude_abs):
        relative = folder_abs[len(exclude_abs):].lstrip("\\/")
    else:
        relative = os.path.basename(folder_abs)

    expected_size = expected_size or 0

    final_dir = os.path.abspath(os.path.join(LORA_PASTE_TARGET_PATH, relative))
    os.makedirs(final_dir, exist_ok=True)

    final_lora_path = os.path.join(final_dir, lora_filename)

    # -------------------------------------------------------------
    # 🔥 기존 파일 vs expected_size 비교해서 복사 여부 결정
    # -------------------------------------------------------------
    need_copy = True

    if os.path.exists(final_lora_path):
        actual = os.path.getsize(final_lora_path)

        if expected_size > 0:
            if actual >= expected_size:
                print(f"[SKIP] SD 폴더에 이미 정상 파일 존재: {final_lora_path}")
                need_copy = False
            else:
                print(f"[WARN] SD 폴더의 기존 파일 용량 부족 → 재복사 ({actual} < {expected_size})")
                try:
                    os.remove(final_lora_path)
                except:
                    pass
        else:
            # expected_size가 없으면 fallback (기존 정책)
            if actual > 0:
                need_copy = False

    # -------------------------------------------------------------
    # 🔥 복사 수행
    # -------------------------------------------------------------
    # -------------------------------------------------------------
    # 🔥 복사 수행
    # -------------------------------------------------------------
    if need_copy:
        try:
            shutil.copy2(lora_path, final_lora_path)
            print(f"[COPY] LoRA 복사됨 → {final_lora_path}")
        except Exception as e:
            print(f"[LORA][ERROR] SD 폴더 복사 실패: {e}")
            if model_version_id:
                import download_state
                download_state.mark_failed(
                    model_version_id,
                    "lora",
                    f"copy_failed: {e}",
                    {
                        "source_path": lora_path,
                        "dest_path": final_lora_path,
                        "expected_size": expected_size,
                    }
                )
            return  # 복사 실패면 여기서 종료

    # ✅ 여기까지 왔으면: 로라 파일 존재 + 용량 OK + (필요하면) SD 폴더 복사 완료
    if model_version_id and os.path.exists(lora_path):
        try:
            import download_state
            size = os.path.getsize(lora_path)
            download_state.mark_success(model_version_id, "lora", lora_path, size)
        except Exception:
            pass

        except Exception as e:
            print(f"[LORA][ERROR] SD 폴더 복사 실패: {e}")
            if model_version_id:
                import download_state
                download_state.mark_failed(
                    model_version_id,
                    "lora",
                    f"copy_failed: {e}",
                    {
                        "source_path": lora_path,
                        "dest_path": final_lora_path,
                        "expected_size": expected_size,
                    }
                )
            return  # 복사 실패면 여기서 종료

    # 여기까지 왔으면 정규화 + 복사까지 정상 완료 → 성공 로그에 기록
    if model_version_id and os.path.exists(final_lora_path):
        try:
            import download_state
            size = os.path.getsize(final_lora_path)
            download_state.mark_success(
                model_version_id,
                "lora",
                final_lora_path,
                size
            )
        except Exception:
            pass




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