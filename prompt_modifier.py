# -*- coding: utf-8 -*-
"""
prompt_modifier.py

지정된 폴더(또는 현재 작업 폴더) 하위의 모든 .txt 파일을 순회하면서
- raw_prompt 기반으로 LoRA 태그 / prompt / prompt_with_clothes / lora 필드를 재구성하는 스크립트.

사용법:
    python prompt_modifier.py                  # 현재 폴더 기준
    python prompt_modifier.py D:/CivitAI/Users/foobar
"""

import os
import sys
import json
import re

# get_model.py 에서 필터/유틸 재사용
import get_model


# ----------------------------------------------------------------------
#  safetensors → ss_output_name 찾기
# ----------------------------------------------------------------------
def find_lora_ss_output_name(folder: str):
    """
    folder 안에서 .safetensors 파일을 찾고, 그 안의 ss_output_name 을 반환한다.
    - .safetensors 가 없으면 예외 발생
    - ss_output_name 이 없으면:
        1) 로라 파일 이름(확장자 제거)을 기반으로 정규화(__ → _) 한 값을 ss_output_name 으로 사용
        2) 실제 로라 파일 이름도 정규화된 이름으로 rename
    """
    safes = [f for f in os.listdir(folder) if f.lower().endswith(".safetensors")]
    if not safes:
        raise RuntimeError(f"LoRA(.safetensors) 파일이 없습니다: {folder}")

    if len(safes) > 1:
        print(f"[WARN] safetensors 파일이 여러 개입니다. 첫 번째만 사용합니다: {safes}")
    safes.sort()

    lora_filename = safes[0]
    lora_path = os.path.join(folder, lora_filename)

    meta = get_model.read_safetensors_metadata(lora_path)
    if not meta:
        raise RuntimeError(f"메타데이터를 읽을 수 없습니다: {lora_path}")

    ss_name = meta.get("ss_output_name")
    if isinstance(ss_name, str):
        ss_name = ss_name.strip()
    else:
        ss_name = ""

    # 현재 파일 이름 기준 정규화 이름 계산
    base_name, ext = os.path.splitext(lora_filename)
    normalized_base = base_name.replace("__", "_")
    normalized_filename = normalized_base + ext

    if not ss_name:
        # 🔹 ss_output_name 이 없으면 → 정규화된 파일 이름(확장자 제거)을 ss_output_name 으로 사용
        ss_name = normalized_base

        # 🔹 실제 파일 이름도 정규화된 이름으로 변경
        if normalized_filename != lora_filename:
            new_path = os.path.join(folder, normalized_filename)
            if os.path.exists(new_path):
                print(f"[LORA][WARN] 정규화된 파일명이 이미 존재 → 파일명 변경 스킵: {new_path}")
                # 이 경우에는 파일명은 그대로 두고 ss_output_name만 맞춰둔다.
            else:
                os.rename(lora_path, new_path)
                print(f"[LORA] 파일명 정규화: {lora_filename} → {normalized_filename}")
                lora_filename = normalized_filename
                lora_path = new_path

        # 🔹 메타데이터에도 ss_output_name 써주기
        try:
            get_model.rewrite_safetensors_metadata(lora_path, ss_name)
            print(f"[LORA] ss_output_name 없음 → 파일명 기반으로 설정: {ss_name}")
        except Exception as e:
            print(f"[WARN] ss_output_name 자동 설정 실패: {e}")

    # ss_output_name 이 원래부터 있던 경우에는 여기서는 rename 안 하고,
    # get_model.py 쪽 wait_and_finalize_lora 에서 정규화 처리.

    return lora_filename, ss_name



# ----------------------------------------------------------------------
#  raw_prompt 안의 모든 <lora:...> 태그 찾기
# ----------------------------------------------------------------------
def extract_all_lora_tags(prompt: str):
    """
    prompt 안에서 <lora:...> 형태의 태그를 전부 찾아,
    (full_tag, name) 리스트를 반환한다.
    name 은 <lora:와 첫 번째 ':' 사이의 문자열.
    """
    if not prompt:
        return []

    tags = []
    pattern = r"<lora:[^>]+>"
    for m in re.finditer(pattern, prompt):
        tag = m.group(0)
        inner = tag[len("<lora:"):-1]  # "NAME:WEIGHT" 또는 "NAME"
        if ":" in inner:
            name = inner.split(":", 1)[0]
        else:
            name = inner
        tags.append((tag, name))
    return tags


# ----------------------------------------------------------------------
#  raw_prompt 의 토큰에서 LoRA 태그들을 앞으로 이동
# ----------------------------------------------------------------------
def reorder_lora_tags_to_front(prompt: str) -> str:
    """
    문자열 전체에서 <lora:...> 태그들을 모두 찾아
    - 태그들만 앞쪽으로 모으고
    - 나머지 텍스트는 뒤쪽에 붙인다.
    태그들의 원래 등장 순서는 유지한다.
    """
    import re

    if not prompt:
        return ""

    # 1) 전체 문자열에서 모든 <lora:...> 태그 추출
    lora_tags = re.findall(r"<lora:[^>]+>", prompt)

    # 2) 본문에서 태그들을 제거
    body = prompt
    for tag in lora_tags:
        body = body.replace(tag, "")

    # 3) 콤마 기준으로 정리해서 깔끔하게 붙이기
    def normalize_list(s: str) -> str:
        # 개행 제거 후 콤마로 나눠서 공백/빈 토큰 제거
        tokens = [t.strip() for t in s.replace("\n", " ").split(",") if t.strip()]
        return ", ".join(tokens)

    # 태그 부분: 태그들을 콤마로 이어 붙인 후 normalize
    lora_part = normalize_list(", ".join(lora_tags)) if lora_tags else ""
    # 나머지 본문 부분
    body_part = normalize_list(body)

    # 4) 합치기
    if lora_part and body_part:
        return f"{lora_part}, {body_part}"
    elif lora_part:
        return lora_part
    else:
        return body_part



# ----------------------------------------------------------------------
#  TXT 한 개 처리
# ----------------------------------------------------------------------
def process_txt(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        # print(f"[ERROR] JSON 읽기 실패: {path} - {e}")
        return

    raw_prompt = (data.get("raw_prompt") or "").strip()

    # raw_prompt 가 없거나 빈 문자열이면 스킵
    if not raw_prompt:
        print(f"[SKIP] raw_prompt 없음 또는 빈 값: {path}")
        return

    # prompt / prompt_with_clothes 초기화
    data["prompt"] = ""
    data["prompt_with_clothes"] = ""

    # --------------------------------------------------
    # 1) 해당 폴더의 LoRA(.safetensors) → ss_output_name
    # --------------------------------------------------
    folder = os.path.dirname(path)
    try:
        lora_filename, ss_output_name = find_lora_ss_output_name(folder)
    except Exception as e:
        # 요구사항: 없으면 에러. 여기서는 에러 로그 출력 후 스킵.
        print(f"[ERROR] LoRA 메타 처리 실패: {path} - {e}")
        return

    # ss_output_name 비교용으로 약간 정규화 ( '__' → '_' )
    target_name = ss_output_name.replace("__", "_")

    # --------------------------------------------------
    # 2) raw_prompt 안의 모든 <lora:...> 태그 검사
    # --------------------------------------------------
    all_lora_tags = extract_all_lora_tags(raw_prompt)

    chosen_lora_tag = None  # txt 의 lora 필드에 기록할 값

    if all_lora_tags:
        # 모든 태그에 대해 name 과 ss_output_name 비교
        for full_tag, name in all_lora_tags:
            name_norm = name.replace("__", "_")
            if name_norm == target_name:
                # 요구사항: 같은 값이면 raw_prompt 에서 찾은 태그 문자열 자체를 사용
                chosen_lora_tag = full_tag

        if chosen_lora_tag is None:
            # 하나도 매칭되는 것이 없으면 <lora:ss_output_name:1>
            chosen_lora_tag = f"<lora:{target_name}:1>"
    else:
        # raw_prompt 에 LoRA 태그가 하나도 없으면 <lora:ss_output_name:1>
        chosen_lora_tag = f"<lora:{target_name}:1>"

    # lora 필드 설정
    data["lora"] = chosen_lora_tag

    # --------------------------------------------------
    # 3) raw_prompt_temp 생성 및 LoRA 태그들 앞으로 이동
    # --------------------------------------------------
    raw_prompt_temp = reorder_lora_tags_to_front(raw_prompt)

    # lora 항목값(chosen_lora_tag)이 raw_prompt_temp 안에 없으면 맨 앞에 추가
    if chosen_lora_tag and chosen_lora_tag not in raw_prompt_temp:
        if raw_prompt_temp:
            raw_prompt_temp = f"{chosen_lora_tag}, {raw_prompt_temp}"
        else:
            raw_prompt_temp = chosen_lora_tag

    # --------------------------------------------------
    # 4) 필터링해서 prompt / prompt_with_clothes 설정
    #    - prompt             : CLOTHES_FILTER + ETC_FILTER
    #    - prompt_with_clothes: ETC_FILTER
    # --------------------------------------------------
    clothes_filter = getattr(get_model, "CLOTHES_FILTER", [])
    etc_filter = getattr(get_model, "ETC_FILTER", [])
    all_filter = clothes_filter + etc_filter

    # clean_prompt 로 필터링 (기존 로직 재사용)
    prompt_filtered = get_model.clean_prompt(raw_prompt_temp, all_filter)
    prompt_with_clothes_filtered = get_model.clean_prompt(raw_prompt_temp, etc_filter)

    data["prompt"] = prompt_filtered
    data["prompt_with_clothes"] = prompt_with_clothes_filtered

    # --------------------------------------------------
    # 5) 결과 저장
    # --------------------------------------------------
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[OK] 처리 완료: {path}")
    except Exception as e:
        print(f"[ERROR] 저장 실패: {path} - {e}")


# ----------------------------------------------------------------------
#  모든 폴더 순회
# ----------------------------------------------------------------------
def process_all_folders(base_dir: str):
    for root, dirs, files in os.walk(base_dir):
        for name in files:
            if not name.lower().endswith(".txt"):
                continue
            txt_path = os.path.join(root, name)
            process_txt(txt_path)


# ----------------------------------------------------------------------
#  메인
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # if len(sys.argv) >= 2:
    #     base = sys.argv[1]
    # else:
    #     base = os.getcwd()

    # base = os.path.abspath(base)
    base = r"E:\CivitAI\Users"

    print(f"[INFO] prompt_modifier 시작: {base}")

    if not os.path.isdir(base):
        print(f"[ERROR] 유효하지 않은 폴더: {base}")
        sys.exit(1)

    process_all_folders(base)

    print("[INFO] 모든 프롬프트 처리 완료")
