# download_state.py
import json
import os
import threading

# 예전 방식(다운로드된 파일 목록) - 그대로 둠
downloaded_records = {
    "lora": [],
    "images": []
}

# 새 통합 다운로드 로그
# success / failed 둘 다 한 파일에 관리
download_log = {
    "success": [],  # [{ "id": int, "type": "image"/"lora", "path": str, "size": int }]
    "failed": [],   # [{ "id": int, "type": str, "reason": str, "info": dict }]
}

_log_lock = threading.Lock()


def _find_success(file_id, file_type):
    for e in download_log["success"]:
        if e["id"] == file_id and e["type"] == file_type:
            return e
    return None


def is_success(file_id, file_type):
    """해당 파일이 성공 목록에 있는지 여부"""
    with _log_lock:
        return _find_success(file_id, file_type) is not None


def mark_success(file_id, file_type, path, size):
    """성공 기록 추가 (이미 있으면 path/size 갱신)"""
    with _log_lock:
        # 실패 기록 제거
        download_log["failed"] = [
            e for e in download_log["failed"]
            if not (e["id"] == file_id and e["type"] == file_type)
        ]

        exist = _find_success(file_id, file_type)
        if exist:
            exist["path"] = path
            exist["size"] = size
        else:
            download_log["success"].append({
                "id": file_id,
                "type": file_type,
                "path": path,
                "size": size,
            })


def mark_failed(file_id, file_type, reason, info=None):
    """실패 기록 추가 (같은 파일은 덮어쓰기)"""
    with _log_lock:
        download_log["failed"] = [
            e for e in download_log["failed"]
            if not (e["id"] == file_id and e["type"] == file_type)
        ]
        download_log["failed"].append({
            "id": file_id,
            "type": file_type,
            "reason": reason,
            "info": info or {},
        })


def load_download_log(username):
    """프로그램 시작 시 한 번만 호출해서 메모리에 올림"""
    global download_log

    folder = os.path.join("download_logs", username)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{username}_download_log.json")

    if not os.path.exists(path):
        download_log = {"success": [], "failed": []}
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            download_log = json.load(f)
        if "success" not in download_log or "failed" not in download_log:
            download_log = {"success": [], "failed": []}
        print(f"[LOG] 다운로드 로그 로드: {path}")
    except Exception as e:
        print(f"[ERROR] 다운로드 로그 로드 실패: {e}")
        download_log = {"success": [], "failed": []}


def save_download_log(username):
    """=== 모든 스레드 작업 완료 === 이후에 파일로 저장"""
    folder = os.path.join("download_logs", username)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{username}_download_log.json")

    with _log_lock:
        data = download_log.copy()

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[LOG] 다운로드 로그 저장 완료: {path}")
    except Exception as e:
        print(f"[ERROR] 다운로드 로그 저장 실패: {e}")
