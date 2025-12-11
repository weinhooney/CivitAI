import os
import datetime
import re
import time
import json
import urllib.parse
import requests
from concurrent.futures import as_completed
from get_model import (
    process_post_to_dir,
    parse_cookie_string,
    COOKIE_STRING,
    set_future_lists,
    set_download_targets,
    idm_start_download,
)
from get_model import USERS_ROOT, POSTS_ROOT
from get_model import safe_get
from thread_pool import IMG_META_EXECUTOR, BG_LORA_EXECUTOR


# ------------------------------------------------------------------
# 다운로드 대상들을 저장할 리스트 (이미지 + 로라 모두 포함)
DOWNLOAD_TARGETS = []
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# 모든 작업 쓰레드가 끝났는지 확인용
# ------------------------------------------------------------------
IMG_META_FUTURES = []
LORA_FUTURES = []


# =========================================================
# get_model.py 의 future 리스트 주입
# =========================================================
set_future_lists(IMG_META_FUTURES, LORA_FUTURES)


# =========================================================
# get_model.py 의 future 리스트 주입
# =========================================================
set_future_lists(IMG_META_FUTURES, LORA_FUTURES)

# =========================================================
# get_model.py 에 DOWNLOAD_TARGETS 리스트도 주입
# =========================================================
set_download_targets(DOWNLOAD_TARGETS)



session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})
session.cookies.update(parse_cookie_string(COOKIE_STRING))


# ------------------------------------------------------------------
# TRPC model.getAll 공용 호출 함수 (test.py에서 쓰던 것 그대로)
# ------------------------------------------------------------------
def call_model_get_all(payload: dict):
    """
    /api/trpc/model.getAll 을 호출한다.
    - payload는 {"json": {...}} 형태
    - input 파라미터에 JSON 문자열을 그대로 넣고,
      requests 가 알아서 URL 인코딩하게 둔다.
    """
    json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


    for retry in range(10):
        r = safe_get(
            "https://civitai.com/api/trpc/model.getAll",
            params={"input": json_str},
        )

        status = r.status_code

        if status == 200:
            try:
                return r.json()
            except Exception as e:
                print("[ERROR] TRPC JSON 파싱 실패:", e)
                print(r.text[:300])
                return None

        if status == 429:
            wait = 5 + retry * 5   # 5초, 10초, 15초… 증가
            print(f"[WARN] TRPC 429 Too Many Requests → {wait}초 대기 후 재시도")
            time.sleep(wait)
            continue

        print(f"[WARN] TRPC status={status}, retry={retry}")
        time.sleep(2)

    print("[FATAL] TRPC 연속 실패")
    return None





def get_post_id_from_version(version_id, session):
    """
    1) modelVersionId 기반으로 모든 이미지 목록 가져오기
    2) 그 중 postId 가진 이미지 찾기
    3) postId 반환
    """
    url = f"https://civitai.com/api/v1/images?modelVersionId={version_id}&limit=200"

    try:
        r = safe_get(url)
        data = r.json()
    except Exception as e:
        print(f"[ERROR] 이미지 목록 가져오기 실패: version_id={version_id}, err={e}")
        return None

    items = data.get("items", [])
    if not items:
        print(f"[WARN] modelVersionId={version_id} → 이미지 없음")
        return None

    # 이미지 목록에서 postId 가진 첫 번째 이미지 찾기
    for img in items:
        post_id = img.get("postId")
        if post_id:
            print(f"[INFO] 이미지 {img['id']} → postId={post_id} 발견")
            return post_id

    print(f"[WARN] modelVersionId={version_id} → postId 가진 이미지 없음")
    return None




###############################################################################
# Utility
###############################################################################
def _same_by_ids(a, b):
    # mv_id가 둘 다 있으면 그걸로 유일 식별
    if a.get("mv_id") is not None and b.get("mv_id") is not None:
        return a["mv_id"] == b["mv_id"]
    # mv_id 없으면 model_id + filename 조합으로 비교 (임시)
    if a.get("model_id") is not None and b.get("model_id") is not None:
        return a["model_id"] == b["model_id"] and a.get("filename") == b.get("filename")
    return False

def _same_by_name(a, b):
    # 최후의 보루: filename만 같으면 동일로 취급
    return a.get("filename") == b.get("filename")

# filename은 None 허용 (ID만으로 업서트 가능)
def _upsert(kind, filename=None, mv_id=None, image_id=None):
    import download_state
    lst = download_state.downloaded_records[kind]

    meta = {}
    if filename is not None: meta["filename"] = filename
    if mv_id   is not None:  meta["mv_id"]   = int(mv_id)
    if image_id is not None: meta["image_id"] = int(image_id)

    def same(a, b):
        if a.get("image_id") is not None and b.get("image_id") is not None:
            return a["image_id"] == b["image_id"]
        if a.get("mv_id") is not None and b.get("mv_id") is not None:
            return a["mv_id"] == b["mv_id"]
        # 마지막 보조: 파일명만 같으면 동일 취급 (ID 없을 때만)
        return a.get("filename") and b.get("filename") and a["filename"] == b["filename"]

    for i, it in enumerate(lst):
        if same(it, meta):
            lst[i] = {**it, **meta}  # 최신 정보로 병합
            return
    lst.append(meta)



def safe_folder_name(name: str) -> str:
    # 1) Windows 금지 문자 치환
    name = re.sub(r'[<>:"/\\|?*]', "_", name)

    # 2) 제어문자 제거 (\t \n \r 및 ASCII 0~31)
    name = re.sub(r'[\t\r\n]', " ", name)
    name = re.sub(r'[\x00-\x1F]+', " ", name)

    # 3) Zero-width space 제거
    name = name.replace('\u200b', '')

    # 4) 공백 여러 개 → 1개
    name = " ".join(name.split())

    # 5) 앞뒤 공백 정리
    return name.strip()



def extract_username(url: str):
    # 쿼리 제거
    u = url.split("?")[0]
    u = u.rstrip("/")
    return u.split("/user/")[1].split("/")[0]


def extract_trpc_items(json_data):
    """TRPC 구조 → items 추출"""
    return (
        json_data
        .get("result", {})
        .get("data", {})
        .get("json", {})
        .get("items", [])
    )



def get_user_models_v1(username):
    """
    A 방식: /api/v1/models 기반
    기존 코드 구조를 최대한 유지하면서,
    - 재시도 추가
    - 에러 핸들링
    - rate-limit(429) 처리
    - 페이징 안정성 보강
    """
    base = "https://civitai.com/api/v1/models"
    cursor = None
    models = []

    print(f"[INFO] v1 API 조회 시작: {username}")

    while True:
        params = {"username": username, "limit": 100}
        if cursor:
            params["cursor"] = cursor

        # -------------- 요청 단계 --------------
        for attempt in range(3):
            try:
                r = safe_get(base, params=params, timeout=10)

                # Rate limit
                if r.status_code == 429:
                    print("[WARN] v1 API 429: 2초 대기")
                    time.sleep(2)
                    continue

                r.raise_for_status()
                data = r.json()
                break

            except Exception as e:
                if attempt == 2:
                    print(f"[ERROR] v1 API 오류: {e}")
                    print("[ERROR] v1 API 조기 종료")
                    return models
                else:
                    print(f"[WARN] v1 API 오류 → 재시도 ({attempt+1}/3)")
                    time.sleep(2)

        # -------------- 아이템 수집 단계 --------------
        items = data.get("items", [])
        if not items:
            print("[INFO] v1 API: items 없음 → 종료")
            break

        models.extend(items)
        print(f"[INFO] v1 API: {len(items)}개 수집 (누적 {len(models)})")

        # -------------- 다음 페이지(cursor) 처리 --------------
        cursor = data.get("metadata", {}).get("nextCursor")
        if not cursor:
            print("[INFO] v1 API: nextCursor 없음 → 종료")
            break

    print(f"[INFO] v1 API 최종 수집 모델 수: {len(models)}")
    return models



def get_user_models(username):
    """
    최종 래퍼:
    - v1(/api/v1/models) 결과 + TRPC(model.getAll) 결과를 둘 다 가져와서
      model id 기준으로 병합한다.
    """
    print(f"[INFO] v1 API(/api/v1/models)로 '{username}' 모델 수집 시도…")
    models_v1 = get_user_models_v1(username)
    print(f"[INFO] v1 API 결과: {len(models_v1)}개")

    print(f"[INFO] TRPC(model.getAll)로 '{username}' 모델 수집 시도…")
    models_trpc = get_user_models_trpc(username)
    print(f"[INFO] TRPC 결과: {len(models_trpc)}개")

    # id 기준으로 병합 (중복 제거)
    merged = {}
    for m in models_v1 + models_trpc:
        mid = m.get("id")
        if mid is None:
            continue
        if mid not in merged:
            merged[mid] = m

    models = list(merged.values())
    print(f"[INFO] 병합 후 최종 모델 개수: {len(models)}개")

    return models








def get_user_models_trpc(username):
    """
    B 방식: TRPC model.getAll (브라우저와 같은 payload 사용)
    - cursor 기반으로 끝까지 돌면서 모든 모델을 모은다.
    """
    print(f"[INFO] TRPC(model.getAll)로 '{username}' 모델 목록 수집 중…")

    cursor = None
    all_items = []

    while True:
        # 브라우저에서 캡쳐한 payload와 동일한 구조
        payload = {
            "json": {
                "periodMode": "published",
                "sort": "Newest",  # 필요하면 'Highest Rated'로 바꿔도 됨
                "username": username,
                "period": "AllTime",
                "pending": False,
                "hidden": False,
                "followed": False,
                "earlyAccess": False,
                "fromPlatform": False,
                "supportsGeneration": False,
                "isFeatured": False,
                "browsingLevel": 31,
                "excludedTagIds": [
                    415792, 426772, 5188, 5249,
                    130818, 130820, 133182, 5351,
                    306619, 154326, 161829, 163032
                ],
                "disablePoi": True,
                "disableMinor": True,
                "authed": True,
            }
        }

        # 첫 페이지일 때는 cursor 키 자체를 안 넣는 쪽이 실제 브라우저와 더 비슷함
        if cursor is not None:
            payload["json"]["cursor"] = cursor

        print(f"  [TRPC] cursor={cursor}")
        result = call_model_get_all(payload)
        if not result:
            print("  [TRPC] result 없음 → 중단")
            break

        try:
            # 구조: {"result": {"data": {"json": { "items": [...], "nextCursor": ... }}}}
            data = (
                result.get("result", {})
                      .get("data", {})
                      .get("json", {})
            )
        except Exception as e:
            print(f"  [TRPC] 응답 구조 파싱 실패: {e}")
            print(result)
            break

        items = data.get("items", [])
        next_cursor = data.get("nextCursor")

        print(f"  [TRPC] 이번 페이지 {len(items)}개, 누적 {len(all_items) + len(items)}개")

        if not items:
            print("  [TRPC] items 비어있음 → 중단")
            break

        all_items.extend(items)

        if not next_cursor:
            print("  [TRPC] nextCursor 없음 → 마지막 페이지")
            break

        cursor = next_cursor
        time.sleep(3.0)  # 너무 빨리 때리는 것 방지

    print(f"[INFO] TRPC로 {len(all_items)}개 모델 수집 완료")
    return all_items











###############################################################################
# ⭐ modelVersion → 포스트 ID 얻기
###############################################################################
# def get_post_id_from_model(model):
#     """
#     기존 코드와 완전히 동일한 인터페이스를 유지한다.
#     session, cookies, main 구조 절대 변경 없음.
#     modelVersionId 기반으로 /api/v1/images 에서 postId를 찾는다.
#     """

#     ############################################################
#     # 1) modelVersionId 추출 (네 기존 코드 구조와 동일)
#     ############################################################
#     versions = model.get("modelVersions")
#     if not versions:
#         print("  [WARN] modelVersions 없음")
#         return None

#     version_id = versions[0].get("id")
#     if not version_id:
#         print("  [WARN] version_id 없음")
#         return None

#     print(f"  [INFO] version_id: {version_id}")

#     ############################################################
#     # 2) /api/v1/images?modelVersionId=xxx 로 이미지 목록 조회
#     ############################################################
#     import requests
#     headers = {
#         "User-Agent": "Mozilla/5.0"
#     }

#     url = f"https://civitai.com/api/v1/images?modelVersionId={version_id}&limit=200"

#     try:
#         r = session.get(url, headers=headers)
#         data = r.json()
#     except Exception as e:
#         print(f"  [ERROR] 이미지 목록 조회 실패: {e}")
#         return None

#     items = data.get("items", [])
#     if not items:
#         print(f"  [WARN] version_id={version_id} → 이미지 없음")
#         return None

#     ############################################################
#     # 3) 이미지 중 postId 가진 이미지 찾기 (공식 문서 기준)
#     ############################################################
#     for img in items:
#         pid = img.get("postId")
#         if pid:
#             print(f"  [INFO] 이미지 {img['id']} → postId={pid} 발견")
#             return pid

#     print(f"  [WARN] version_id={version_id} → postId 가진 이미지 없음")
#     return None
def get_post_id_from_model(model):
    """
    기존 코드 100% 유지 + modelVersions 없을 때 fallback 추가한 최종 버전
    """

    ###############################
    # 1) 기존 방식 (과거엔 항상 성공하던 방식)
    ###############################
    versions = model.get("modelVersions")

    if versions:
        version_id = versions[0].get("id")
        if version_id:
            print(f"  [INFO] version_id: {version_id}")

            # 기존 방식 그대로 사용
            url = f"https://civitai.com/api/v1/images?modelVersionId={version_id}&limit=200"
            headers = {"User-Agent": "Mozilla/5.0"}

            try:
                r = safe_get(url, headers=headers)
                data = r.json()
                items = data.get("items", [])

                for img in items:
                    pid = img.get("postId")
                    if pid:
                        print(f"  [INFO] 이미지 {img['id']} → postId={pid} (기존 방식)")
                        return pid

                print(f"  [WARN] version_id={version_id} → postId 없음 (기존 방식)")
            except Exception as e:
                print(f"  [ERROR] 기존 방식 실패: {e}")
        else:
            print("  [WARN] version_id 없음")

    else:
        print("  [WARN] modelVersions 없음 → fallback 필요")

    ###################################
    # 2) Fallback 방식 (modelId 기반)
    ###################################
    # 이 방식은 modelVersions 없이도 항상 작동
    model_id = model.get("id")

    if not model_id:
        print("  [ERROR] model_id 없음 → fallback 불가")
        return None

    print(f"  [INFO] fallback: modelId={model_id} 로 이미지 기반 postId 탐색")

    try:
        url = "https://civitai.com/api/v1/images"
        params = {"modelId": model_id, "limit": 1}
        r = safe_get(url, params=params)
        data = r.json()

        items = data.get("items", [])
        if items:
            pid = items[0].get("postId")
            if pid:
                print(f"  [INFO] fallback 성공 → postId={pid}")
                return pid

        print(f"  [WARN] fallback 실패 → 이미지에 postId 없음")
    except Exception as e:
        print(f"  [ERROR] fallback 조회 실패: {e}")

    return None



###############################################################################
# 정상적으로 다운로드 됐는지 검증
###############################################################################
def verify_all_downloads(download_targets):
    """
    다운로드된 파일을 검사하는 함수.
    - 이미지: 최소 파일 크기 기준으로 검사
    - 모델 파일(LoRA): expected_file_size 기반으로 검사
    """
    import os
    import download_state

    verified = []

    for item in download_targets:
        # 안전하게 get() 사용
        path = item.get("expected_file_path")
        item_type = item.get("type")
        expected_size = item.get("expected_file_size")

        # 파일 ID 추출
        file_id = None
        if item_type == "image":
            file_id = item.get("image_id")
        elif item_type == "lora":
            file_id = item.get("model_version_id")

        # ================================
        # 0) path 자체가 비정상인 경우 방어
        # ================================
        if not path or not isinstance(path, (str, bytes, os.PathLike)):
            # 이 경우는 애초에 잘못 들어온 엔트리이므로 바로 실패 처리
            item["status"] = "invalid_path"
            item["actual_file_size"] = 0

            if file_id is not None:
                info = {
                    "expected_file_path": path,
                    "expected_file_size": expected_size,
                }
                if item_type == "image":
                    info["download_url"] = item.get("download_url")
                    info["page_url"] = item.get("page_url")
                elif item_type == "lora":
                    info["presigned_url"] = item.get("presigned_url")

                download_state.mark_failed(
                    file_id,
                    item_type,
                    item["status"],  # "invalid_path"
                    info,
                )

            verified.append(item)
            continue

        # ================================
        # 1) 파일 존재 여부 검사
        #    - 이미지인 경우, 같은 ID의 다른 확장자 파일도 한 번 더 검색
        # ================================

        # 1-0) 이미지라면, 무조건 실제 디스크에서 image_id 기준으로 경로 보정
        #      (IDM이 .jpeg 대신 .png 등으로 저장하는 경우 대응)
        if item_type == "image":
            try:
                from get_model import find_existing_image_by_id
                folder = os.path.dirname(path) if path else None
                image_id = item.get("image_id")
                if folder and image_id is not None:
                    alt_path = find_existing_image_by_id(folder, image_id)
                    if alt_path and os.path.exists(alt_path):
                        # 실제 파일 발견 → 이 경로를 기준으로 이후 로직 진행
                        path = alt_path
                        item["expected_file_path"] = alt_path
            except Exception:
                # 보정 시도 실패하면 그냥 원래 로직으로 처리
                pass


        # 1-1) 최종적으로도 파일이 없다면 missing
        if not os.path.exists(path):
            item["status"] = "missing"
            item["actual_file_size"] = 0

            if file_id is not None:
                info = {
                    "expected_file_path": path,
                    "expected_file_size": expected_size,
                }
                if item_type == "image":
                    info["download_url"] = item.get("download_url")
                    info["page_url"] = item.get("page_url")
                elif item_type == "lora":
                    info["presigned_url"] = item.get("presigned_url")

                download_state.mark_failed(file_id, item_type, "missing", info)

            verified.append(item)
            continue


        # ================================
        # 2) 실제 파일 용량 체크
        # ================================
        actual_size = os.path.getsize(path)
        item["actual_file_size"] = actual_size

        # ----------------------------
        #   2-1) 이미지 파일
        # ----------------------------
        if item_type == "image":
            # 원본 용량을 모르니까 최소값 기준 (5KB)
            if actual_size < 5000:
                item["status"] = "corrupted"
            else:
                item["status"] = "success"

        # ----------------------------
        #   2-2) LoRA 등 모델 파일
        # ----------------------------
        else:
            if expected_size:
                # == 말고 >= 로 해서 여유를 둔다
                if actual_size >= expected_size:
                    item["status"] = "success"
                else:
                    item["status"] = "corrupted"
            else:
                item["status"] = "success" if actual_size > 0 else "corrupted"

        # --- 여기서 통합 로그 갱신 ---
        if file_id is not None:
            if item["status"] == "success":
                # LoRA는 다운로드 폴더 기준 경로 저장
                download_state.mark_success(file_id, item_type, path, actual_size)
            else:
                info = {
                    "expected_file_path": path,
                    "expected_file_size": expected_size,
                    "actual_file_size": actual_size,
                }
                if item_type == "image":
                    info["download_url"] = item.get("download_url")
                    info["page_url"] = item.get("page_url")
                elif item_type == "lora":
                    info["presigned_url"] = item.get("presigned_url")

                download_state.mark_failed(
                    file_id,
                    item_type,
                    item["status"],
                    info
                )

        verified.append(item)

    return verified






###############################################################################
# 다운로드 로그 파일
###############################################################################
def write_download_log(
    username,
    model_list_url,
    total_model_count,
    failed_models
):
    
    # failed_models 형식 예시:
    # [
    #     {
    #         "model_name": "ABC Model",
    #         "model_url": "https://civitai.com/models/xxxxx",
    #         "post_id": 1234567,
    #         "failed_image_urls": ["https://....jpg", ...],
    #         "failed_lora": {
    #             "lora_url": "https://civitai.com/api/download/xxx",
    #             "copy_error": "복사 실패: Permission denied"
    #         }
    #     },
    #     ...
    # ]

    folder = os.path.join("download_logs", username)
    os.makedirs(folder, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(folder, f"{username}_download_log_{timestamp}.txt")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"===== CivitAI 모델 다운로드 기록 =====\n")
        f.write(f"생성 시각: {timestamp}\n\n")

        f.write(f"[입력한 모델 목록 URL]\n{model_list_url}\n\n")
        
        f.write(f"[다운받을 모델 갯수]\n{total_model_count}\n\n")

        f.write("[다운로드 받지 못한 모델 정보]\n")
        if not failed_models:
            f.write(" - 모든 모델 다운로드 성공!\n")
        else:
            for m in failed_models:
                # 실패한 항목이 하나도 없으면 기록하지 않음
                # 실패하지 않은 경우만 continue
                if (
                    m.get("post_id") is not None                # postId 있음 → 정상 모델
                    and not m.get("failed_image_urls")          # 이미지 실패 없음
                    and not m.get("failed_lora")                # 로라 실패 없음
                ):
                    continue
               
                f.write("\n--------------------------------------\n")
                f.write(f"모델 이름: {m.get('model_name','(이름 없음)')}\n")
                f.write(f"모델 URL: {m.get('model_url','')}\n")
                f.write(f"포스트 아이디: {m.get('post_id','')}\n")

                # 이미지 실패
                failed_imgs = m.get("failed_image_urls", [])
                if failed_imgs:
                    f.write("다운 못받은 이미지 URL들:\n")
                    for item in failed_imgs:
                        f.write(f" - 다운로드 URL: {item['download_url']}\n")
                        f.write(f"   페이지 URL:    {item['page_url']}\n")
                else:
                    f.write("다운 못받은 이미지 없음\n")

                # 로라 실패
                failed_lora = m.get("failed_lora")
                if failed_lora:
                    f.write("다운 못받은 로라 정보:\n")
                    f.write(f" - 로라 URL: {failed_lora.get('lora_url','')}\n")
                    ce = failed_lora.get("copy_error")
                    if ce:
                        f.write(f" - 복사 실패 정보: {ce}\n")
                else:
                    f.write("다운 못받은 로라 없음\n")

                f.write("--------------------------------------\n")

    return log_path



###############################################################################
# 모델로부터 모든 포스트 ID 얻기
###############################################################################
def get_post_ids_from_model(model):

    image_id = None

    # ------------------------------------------------------
    # 1) 최상단 model.images 에서 먼저 찾음
    # ------------------------------------------------------
    top_imgs = model.get("images")
    if top_imgs:
        for img in top_imgs:
            image_id = img.get("id") or img.get("imageId")
            if image_id:
                break

    # ------------------------------------------------------
    # 2) modelVersions[*].images / sampleImages 에서 찾기
    #    (model.images 에서 못 찾았을 때만)
    # ------------------------------------------------------
    if not image_id:
        mv_list = model.get("modelVersions") or []
        for mv in mv_list:
            for key in ("images", "sampleImages"):
                imgs = mv.get(key)
                if not imgs:
                    continue
                for img in imgs:
                    image_id = img.get("id") or img.get("imageId")
                    if image_id:
                        break
                if image_id:
                    break
            if image_id:
                break

    # ------------------------------------------------------
    # 3) 이미지가 없으면 실패
    # ------------------------------------------------------
    if not image_id:
        print("  [WARN] 이미지 ID를 찾지 못함 (model.images / modelVersions 모두 실패)")
        return []

    # 2) 이미지 HTML에서 postIds 가져오기
    from get_model import extract_post_ids_from_image_page
    post_ids = extract_post_ids_from_image_page(image_id)

    return post_ids


###############################################################################
# 모델 메타파일 생성
###############################################################################
import os
import json
import pprint
import time

def generate_model_meta_files(m, user_root):
    r"""
    m : get_user_models(username) 에서 얻은 모델 데이터(dict)
    user_root : 사용자 폴더 경로 (예: E:/CivitAI/Users/username)
    """

    model_name = m.get("name", "UnknownModel")
    model_id = m.get("id")
    model_url = f"https://civitai.com/models/{model_id}"
    model_type = m.get("type")
    description_html = m.get("description")
    tags = m.get("tags", [])
    creator = m.get("creator", {})
    stats = m.get("stats", {})

    # 모델 폴더 생성
    model_folder = os.path.join(user_root, safe_folder_name(model_name))
    os.makedirs(model_folder, exist_ok=True)

    version_data = m.get("modelVersions") or m.get("version")

    if isinstance(version_data, list):
        model_versions = version_data
    elif isinstance(version_data, dict):
        # version이 단일 객체일 때도 기존 코드가 돌아가도록 리스트로 통일
        model_versions = [version_data]
    else:
        model_versions = []

    # ✅ 빈 리스트 검증 추가
    if not model_versions:
        print(f"[WARN] 모델 버전 없음 (메타파일 생성 스킵): {model_name} (ID: {model_id})")
        import download_state
        download_state.mark_failed(
            model_id,
            "model_meta",
            "no_model_versions",
            {
                "model_name": model_name,
                "model_url": model_url
            }
        )
        return  # ✅ 조기 return

    success_count = 0
    failed_count = 0

    for v in model_versions:
        try:
            version_id = v.get("id")
            version_name = v.get("name")
            base_model = v.get("baseModel")
            base_model_type = v.get("baseModelType")
            trained_words = v.get("trainedWords", [])
            published_at = v.get("publishedAt")

            files = v.get("files", [])
            preview_images = v.get("images", [])

            # 이미지 페이지 URL 추가
            for p in preview_images:
                img_id = p.get("id")
                if img_id:
                    p["pageUrl"] = f"https://civitai.com/images/{img_id}"

            # 파일 다운로드 엔드포인트 추가
            for f in files:
                f["download_endpoint"] = f"https://civitai.com/api/download/models/{version_id}"

            # ---------------------------------------------------------
            #                    갤러리 이미지 가져오기
            #   /api/v1/images?modelVersionId=xxx  (resources 없음)
            #   modelVersion 정보는 meta.modelIds / meta.versionIds 로 가져옴
            # ---------------------------------------------------------
            gallery = []
            try:
                gallery_url = f"https://civitai.com/api/v1/images?modelVersionId={version_id}&limit=200"
                r = safe_get(gallery_url)
                jj = r.json()
                items = jj.get("items", [])

                for img in items:
                    meta = img.get("meta") or {}

                    # 모델 버전 정보 추출
                    model_ids = (
                        meta.get("modelIds") or
                        meta.get("versionIds") or
                        []
                    )

                    models_used = []
                    for mv_id in model_ids:
                        models_used.append({
                            "modelVersionId": mv_id,
                            "download_endpoint": f"https://civitai.com/api/download/models/{mv_id}"
                        })

                    gallery.append({
                        "postId": img.get("postId"),
                        "imageId": img.get("id"),
                        "url": img.get("url"),
                        "width": img.get("width"),
                        "height": img.get("height"),
                        "stats": img.get("stats"),
                        "prompt": meta.get("prompt"),
                        "negativePrompt": meta.get("negativePrompt"),
                        "seed": meta.get("seed"),
                        "sampler": meta.get("sampler") or meta.get("scheduler"),
                        "steps": meta.get("steps"),
                        "models_used": models_used
                    })

            except Exception as e:
                print(f"[WARN] 갤러리 조회 실패 modelVersionId={version_id}: {e}")

            # ---------------------------------------------------------
            #                     JSON 구조 생성
            # ---------------------------------------------------------
            meta_json = {
                "modelId": model_id,
                "modelName": model_name,
                "modelUrl": model_url,
                "modelType": model_type,
                "tags": tags,
                "creator": creator,
                "stats": stats,
                "descriptionHtml": description_html,

                "version": {
                    "modelVersionId": version_id,
                    "versionName": version_name,
                    "publishedAt": published_at,
                    "baseModel": base_model,
                    "baseModelType": base_model_type,
                    "trainedWords": trained_words,
                    "files": files,
                    "previewImages": preview_images,   # 모델 상세 페이지의 대표 이미지들
                    "gallery": gallery                 # 갤러리(예제 이미지)
                }
            }

            # ---------------------------------------------------------
            #                     JSON 저장
            # ---------------------------------------------------------
            json_path = os.path.join(model_folder, f"model_meta_v{version_id}.json")
            with open(json_path, "w", encoding="utf-8") as fp:
                json.dump(meta_json, fp, indent=4, ensure_ascii=False)
            print(f"[META] JSON 저장됨: {json_path}")

            # ---------------------------------------------------------
            #                     TXT 저장
            # ---------------------------------------------------------
            txt_path = os.path.join(model_folder, f"model_meta_v{version_id}.txt")
            with open(txt_path, "w", encoding="utf-8") as fp:
                fp.write(pprint.pformat(meta_json, width=180, compact=False))
            print(f"[META] TXT 저장됨: {txt_path}")

            success_count += 1  # ✅ 성공 카운트

        except Exception as e:
            failed_count += 1  # ✅ 실패 카운트
            version_id = v.get("id")
            print(f"[ERROR] 모델 버전 메타 생성 실패 modelVersionId={version_id}: {e}")

            # ✅ 실패 기록 추가
            import download_state
            import traceback
            download_state.mark_failed(
                version_id if version_id else f"unknown_v_{failed_count}",
                "model_meta",
                f"generation_failed: {str(e)}",
                {
                    "model_name": model_name,
                    "model_id": model_id,
                    "error_type": type(e).__name__,
                    "error_traceback": traceback.format_exc()[:500]  # 처음 500자만
                }
            )

    # ✅ 결과 로깅 추가
    print(f"[META] {model_name}: {success_count}개 성공, {failed_count}개 실패")



###############################################################################
# 다운로드 파일 목록 생성
###############################################################################
def save_downloaded_file_list(username, verified_items):
    """
    verified_items: verify_all_downloads() 결과 리스트
    """

    user_root = os.path.join("E:\\CivitAI\\Users", username)
    save_path = os.path.join(user_root, "downloaded_files.json")

    # -------------------------------------------------
    # 기존 기록 불러오기
    # -------------------------------------------------
    if os.path.exists(save_path):
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except:
            existing = {"lora": [], "images": []}
    else:
        existing = {"lora": [], "images": []}

    # dict 형태로 lookup map 화
    lora_map = { item["model_version_id"]: item for item in existing["lora"] }
    image_map = { item["image_id"]: item for item in existing["images"] }

    # -------------------------------------------------
    # 새로운 다운로드 성공 항목 병합
    # -------------------------------------------------
    for item in verified_items:
        if item.get("status") != "success":
            continue

        # ===================== LoRA / Model =====================
        if item.get("type") == "lora":
            mv_id = item.get("model_version_id")
            filename = os.path.basename(item.get("expected_file_path"))

            if mv_id:
                lora_map[mv_id] = {
                    "model_version_id": mv_id,
                    "filename": filename
                }

        # ===================== Images =====================
        elif item.get("type") == "image":
            img_id = item.get("image_id")
            filename = os.path.basename(item.get("expected_file_path"))
            post_id = item.get("post_id")

            if img_id:
                image_map[img_id] = {
                    "image_id": img_id,
                    "filename": filename,
                    "post_id": post_id
                }

    # -------------------------------------------------
    # 저장
    # -------------------------------------------------
    final_data = {
        "lora": list(lora_map.values()),
        "images": list(image_map.values())
    }

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)

    print(f"[DOWNLOAD LIST] 다운로드 목록 저장됨: {save_path}")


###########################################################
#  다운로드한 파일 목록 얻기
###########################################################
def get_downloaded_file_list(username):
    user_root = os.path.join("E:\\CivitAI\\Users", username)
    save_path = os.path.join(user_root, "downloaded_files.json")

    if not os.path.exists(save_path):
        return {"lora": [], "images": []}

    try:
        with open(save_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"lora": [], "images": []}



###########################################################
#  다운로드 파일목록 파일 생성
###########################################################
import os

def save_download_records(user_dir, list_url, total_models, records):
    import os
    os.makedirs(user_dir, exist_ok=True)
    username = os.path.basename(os.path.normpath(user_dir))
    log_path = os.path.join(user_dir, f"{username}_download_log.txt")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"입력한 모델 목록 URL: {list_url}\n")
        f.write(f"다운받을 모델 개수: {total_models}\n")
        f.write("\n=== 다운로드된 파일 목록 ===\n\n")

        f.write("[LoRA]\n")
        for it in records.get("lora", []):
            line = f"  - {it.get('filename')}"
            if it.get("model_id") is not None: line += f"  modelId={it['model_id']}"
            if it.get("mv_id")   is not None: line += f"  mvId={it['mv_id']}"
            f.write(line + "\n")
        if not records.get("lora"): f.write("  (없음)\n")

        f.write("\n[Images]\n")
        for it in records.get("images", []):
            line = f"  - {it.get('filename')}"
            if it.get("model_id") is not None: line += f"  modelId={it['model_id']}"
            if it.get("mv_id")   is not None: line += f"  mvId={it['mv_id']}"
            f.write(line + "\n")
        if not records.get("images"): f.write("  (없음)\n")

    print(f"[LOG] 다운로드 기록 저장 완료 → {log_path}")


def apply_verified_to_records(verified):
    """
    verify_all_downloads(DOWNLOAD_TARGETS) 결과에서
    성공(OK) 항목만 download_state.downloaded_records 에 반영
    """
    import os

    for item in verified or []:
        # 성공 플래그는 프로젝트 구현에 맞춰 아래 중 하나일 가능성:
        ok = item.get("ok") or item.get("success") or (item.get("status") == "ok")
        if not ok:
            continue

        t = item.get("type")
        # 최종 파일명: final_paste_path 우선, 없으면 expected_file_path 사용
        final_path = item.get("final_paste_path") or item.get("expected_file_path")
        filename = os.path.basename(final_path) if final_path else None

        if t == "lora":
            mv_id = item.get("model_version_id")
            _upsert_verified("lora", filename=filename, mv_id=mv_id)

        elif t == "image":
            image_id = item.get("image_id")       # ← 0)에서 넣어둔 필드
            mv_id    = item.get("model_version_id")  # 있으면 유지
            _upsert_verified("images", filename=filename, mv_id=mv_id, image_id=image_id)

        # 필요 시 다른 type도 여기서 처리



###############################################################################
# Main
###############################################################################
def main():
    print("CivitAI 전체 모델 처리기")

    url = input("모델 목록 URL 입력: ").strip()
    username = extract_username(url)
    print("[INFO] 사용자명:", username)

    # Users/{username} 폴더로 고정
    user_root = os.path.join(USERS_ROOT, username)

    # 🔥 최상위 유저 폴더 먼저 생성
    if not os.path.exists(user_root):
        os.makedirs(user_root)
        print(f"[INFO] 사용자 폴더 생성: {user_root}")

    models = get_user_models(username)
    # models = models[:3]  # 테스트 3개

    print(f"[INFO] 총 모델 수: {len(models)}")

    # 실행 시작 시 단 1번만 다운로드 기록 로드
    import download_state

    # 예전에 만든 downloaded_files.json → get_model.is_*_downloaded 에서 사용
    downloaded_records = get_downloaded_file_list(username)
    download_state.downloaded_records = downloaded_records

    # 새 통합 다운로드 로그 (성공/실패 목록) 로드
    download_state.load_download_log(username)


    failed_models = []

    for m in models:
        model_name = m.get("name", "UnknownModel")
        model_id = m.get("id")
        model_url = f"https://civitai.com/models/{model_id}" if model_id else None

        # 🔥 모델 폴더 절대경로 생성
        folder = os.path.abspath(os.path.join(user_root, safe_folder_name(model_name)))

        print(f"\n[MODEL] {model_name}")

        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"  [INFO] 폴더 생성:", folder)

        # 모델 메타파일(JSON+TXT) 자동 생성
        generate_model_meta_files(m, user_root)

        post_ids = get_post_ids_from_model(m)

        if not post_ids:
            print("  [SKIP] 포스트 ID 없음 → 스킵")

            # ⭕ JSON 로그에도 기록하기 위한 DOWNLOAD_TARGETS 추가
            DOWNLOAD_TARGETS.append({
                "type": "model_no_postid",
                "model_id": model_id,
                "model_name": model_name,
                "model_url": model_url,
                "reason": "postId_not_found",
                "expected_file_path": None,
                "expected_file_size": None,
                "status": "failed"
            })

            failed_models.append({
                "model_name": model_name,
                "model_url": model_url,
                "post_id": None,
                "failed_image_urls": [],
                "failed_lora": None,
            })
            continue


        print(f"  [INFO] 발견된 postIds: {post_ids}")

        # 여러 postId 처리
        for pid in post_ids:
            print(f"[PROCESS] postId = {pid}")

            try:
                result = process_post_to_dir(pid, folder)

                failed_models.append({
                    "model_name": model_name,
                    "model_url": model_url,
                    "post_id": pid,
                    "failed_image_urls": result.get("failed_image_urls", []),
                    "failed_lora": result.get("failed_lora")
                })

            except Exception as e:
                print("[ERROR] process_post 실패:", e)

                failed_models.append({
                    "model_name": model_name,
                    "model_url": model_url,
                    "post_id": pid,
                    "failed_image_urls": [],
                    "failed_lora": {"copy_error": str(e)},
                })

        idm_start_download()


    log_file_path = write_download_log(
        username=username,
        model_list_url=url,
        total_model_count=len(models),
        failed_models=failed_models
    )

    print("\n=== 모든 모델 처리 완료 ===")
    print("=== 비동기 작업 대기 시작 ===")

    # ====================================================================
    # 이미지 메타 작업 대기 (타임아웃: 작업당 5분)
    # ====================================================================
    IMG_TIMEOUT = 300  # 5분
    total_img_tasks = len(IMG_META_FUTURES)

    if total_img_tasks > 0:
        print(f"[INFO] 이미지 메타 작업 대기 중... (총 {total_img_tasks}개, 타임아웃: {IMG_TIMEOUT}초)")

        completed_count = 0
        failed_count = 0
        start_time = time.time()

        try:
            for future in as_completed(IMG_META_FUTURES, timeout=IMG_TIMEOUT * total_img_tasks):
                try:
                    future.result(timeout=IMG_TIMEOUT)
                    completed_count += 1

                    # 10개마다 진행상황 출력
                    if completed_count % 10 == 0:
                        elapsed = time.time() - start_time
                        print(f"[PROGRESS] 이미지 메타: {completed_count}/{total_img_tasks} 완료 (경과: {elapsed:.1f}초)")

                except TimeoutError:
                    failed_count += 1
                    print(f"[META][TIMEOUT] 작업 타임아웃 발생 ({IMG_TIMEOUT}초 초과)")
                except Exception as e:
                    failed_count += 1
                    print(f"[META][ERROR] {e}")
                    # ✅ 예외 타입 및 스택 트레이스 로깅
                    import traceback
                    print(f"[META][ERROR] 예외 타입: {type(e).__name__}")
                    print(f"[META][ERROR] 스택 트레이스:\n{traceback.format_exc()}")

        except TimeoutError:
            # as_completed 자체의 타임아웃
            print(f"[META][FATAL] 전체 작업 타임아웃 ({IMG_TIMEOUT * total_img_tasks}초 초과)")
            print(f"[META][FATAL] 완료: {completed_count}, 실패: {failed_count}, 미완료: {total_img_tasks - completed_count - failed_count}")

        elapsed = time.time() - start_time
        print(f"[RESULT] 이미지 메타 작업 완료: {completed_count}개 성공, {failed_count}개 실패 (소요 시간: {elapsed:.1f}초)")
    else:
        print("[INFO] 이미지 메타 작업 없음")

    # ====================================================================
    # LoRA 작업 대기 (타임아웃: 작업당 10분 - 파일 다운로드가 있으므로 더 긴 시간)
    # ====================================================================
    LORA_TIMEOUT = 600  # 10분
    total_lora_tasks = len(LORA_FUTURES)

    if total_lora_tasks > 0:
        print(f"\n[INFO] LoRA 작업 대기 중... (총 {total_lora_tasks}개, 타임아웃: {LORA_TIMEOUT}초)")

        completed_count = 0
        failed_count = 0
        start_time = time.time()

        try:
            for future in as_completed(LORA_FUTURES, timeout=LORA_TIMEOUT * total_lora_tasks):
                try:
                    future.result(timeout=LORA_TIMEOUT)
                    completed_count += 1
                    print(f"[PROGRESS] LoRA: {completed_count}/{total_lora_tasks} 완료")

                except TimeoutError:
                    failed_count += 1
                    print(f"[LORA][TIMEOUT] 작업 타임아웃 발생 ({LORA_TIMEOUT}초 초과)")
                except Exception as e:
                    failed_count += 1
                    print(f"[LORA][ERROR] {e}")
                    # ✅ 예외 타입 및 스택 트레이스 로깅
                    import traceback
                    print(f"[LORA][ERROR] 예외 타입: {type(e).__name__}")
                    print(f"[LORA][ERROR] 스택 트레이스:\n{traceback.format_exc()}")

        except TimeoutError:
            print(f"[LORA][FATAL] 전체 작업 타임아웃 ({LORA_TIMEOUT * total_lora_tasks}초 초과)")
            print(f"[LORA][FATAL] 완료: {completed_count}, 실패: {failed_count}, 미완료: {total_lora_tasks - completed_count - failed_count}")

        elapsed = time.time() - start_time
        print(f"[RESULT] LoRA 작업 완료: {completed_count}개 성공, {failed_count}개 실패 (소요 시간: {elapsed:.1f}초)")
    else:
        print("[INFO] LoRA 작업 없음")

    print("\n=== 모든 스레드 작업 완료 ===")

    print("[VERIFY] 다운로드 파일 검증 시작...")

    verified = verify_all_downloads(DOWNLOAD_TARGETS)

    # 통합 다운로드 로그(JSON) 저장 (기존 파일은 덮어씀)
    download_state.save_download_log(username)


if __name__ == "__main__":
    main()
