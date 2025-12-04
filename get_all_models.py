import os
import datetime
import re
import time
import json
import urllib.parse
import requests
from get_model import process_post_to_dir, parse_cookie_string, COOKIE_STRING, set_future_lists
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
# get_model.py 의 future 리스트 주입
set_future_lists(IMG_META_FUTURES, LORA_FUTURES)


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
            wait = 2 + retry * 2
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
        time.sleep(1.0)  # 너무 빨리 때리는 것 방지

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
    IDM 다운로드 완료 여부와 상관없이
    '파일이 실제로 존재하는지 / 손상되었는지'만 검사하는 함수
    """

    verified = []

    for item in download_targets:
        path = item["expected_file_path"]

        status = "success"

        if not os.path.exists(path):
            status = "missing"
        else:
            size = os.path.getsize(path)
            if size < 5000:
                status = "corrupted"

        # 상태 기록 추가
        item["status"] = status

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

        post_ids = get_post_ids_from_model(m)

        if not post_ids:
            print("  [SKIP] 포스트 ID 없음 → 스킵")

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


    log_file_path = write_download_log(
        username=username,
        model_list_url=url,
        total_model_count=len(models),
        failed_models=failed_models
    )

    print("\n=== 모든 모델 처리 완료 ===")

    # 이미지 메타 작업 대기
    for f in IMG_META_FUTURES:
        try:
            f.result()
        except Exception as e:
            print(f"[META][ERROR] {e}")

    # 로라 작업 대기
    for f in LORA_FUTURES:
        try:
            f.result()
        except Exception as e:
            print(f"[LORA][ERROR] {e}")

    print("=== 모든 스레드 작업 완료 ===")

    print("[VERIFY] 다운로드 파일 검증 시작...")

    verified = verify_all_downloads(DOWNLOAD_TARGETS)

    # JSON 로그 저장
    json_log_path = os.path.join("download_logs", username)
    os.makedirs(json_log_path, exist_ok=True)

    json_log_file = os.path.join(
        json_log_path,
        f"{username}_download_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(json_log_file, "w", encoding="utf-8") as f:
        json.dump(verified, f, indent=2, ensure_ascii=False)

    print("[VERIFY] JSON 로그 저장 완료:", json_log_file)


if __name__ == "__main__":
    main()
