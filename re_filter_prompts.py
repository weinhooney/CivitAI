# -*- coding: utf-8 -*-
import os
import json
import re

# -----------------------------------------
# get_model.py의 모든 함수/변수 재사용
# -----------------------------------------
import get_model    # clean_prompt, FILTER_WORDS, ETC_FILTER 등을 그대로 가져옴

# ---------------------------------------------------
#  TXT 파일 1개 처리
# ---------------------------------------------------
def process_txt(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] JSON 읽기 실패: {path} - {e}")
        return

    # 1) raw_prompt / 기존 prompt / 기존 lora 읽기
    raw_prompt = data.get("raw_prompt", "") or ""
    prompt = data.get("prompt", "") or ""
    prompt_with_clothes = data.get("prompt_with_clothes", "") or ""
    old_lora = (data.get("lora", "") or "").strip()

    # -----------------------------
    # get_model.py와 동일한 개행 제거
    # -----------------------------
    raw_prompt = re.sub(r"[\r\n]+", " ", raw_prompt).strip()

    # ---------------------------------
    # 2) raw_prompt 에서 LoRA 먼저 찾기 (1순위)
    #    예: <lora:Urushihara Satoshi_v3:0.8>
    # ---------------------------------
    pattern = r"<lora:([^>:]+)(?::([^>]+))?>"
    matches = re.findall(pattern, raw_prompt)
    canonical_lora = ""

    if matches:
        # 마지막 LoRA 기준
        name, weight = matches[-1]
        if not weight:
            weight = "1"
        canonical_lora = f"<lora:{name}:{weight}>"
    else:
        # raw_prompt 에 LoRA 없으면 기존 txt 의 lora 를 그대로 사용 (2순위)
        # (기존처럼 :1 붙어있는 값이라고 가정)
        if old_lora.startswith("<lora:"):
            tmp = old_lora.rstrip(" ,")  # 뒤에 붙은 콤마/공백 제거
            canonical_lora = tmp

    # ---------------------------------
    # 3) 기존 prompt / prompt_with_clothes 에서
    #    모든 <lora:...> 태그 싹 제거
    # ---------------------------------
    def strip_lora(s: str) -> str:
        if not s:
            return ""
        s2 = re.sub(r"<lora:[^>]+>", "", s)
        return s2.strip(" ,")  # 앞뒤 콤마/공백 정리

    base_prompt = strip_lora(prompt)
    base_prompt_wc = strip_lora(prompt_with_clothes)


    # -----------------------------
    # 필터링 2종류 수행
    # clean_prompt는 get_model.py의 함수 사용
    # -----------------------------
    base_prompt = get_model.clean_prompt(base_prompt, get_model.FILTER_WORDS)
    base_prompt_wc = get_model.clean_prompt(base_prompt_wc, get_model.ETC_FILTER)

    # ---------------------------------
    # 4) txt 의 lora 정보(canonical_lora)를
    #    prompt / prompt_with_clothes 맨 앞에만 1번 붙이기
    # ---------------------------------
    def build_prompt(lora_tag: str, base: str) -> str:
        if not lora_tag:
            # LoRA 자체가 없으면 그냥 본문만
            return base
        if base:
            return f"{lora_tag}, {base}"
        else:
            # 본문이 비어있다면 LoRA만
            return f"{lora_tag},"

    new_prompt = build_prompt(canonical_lora, base_prompt)
    new_prompt_with_clothes = build_prompt(canonical_lora, base_prompt_wc)

    # ---------------------------------
    # 5) 결과를 txt JSON에 다시 기록
    # ---------------------------------
    data["prompt"] = new_prompt
    data["prompt_with_clothes"] = new_prompt_with_clothes
    data["lora"] = canonical_lora  # txt 파일의 lora 필드도 정규화

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[OK] 갱신됨 → {path}")
    except Exception as e:
        print(f"[ERROR] 저장 실패: {path} - {e}")


# ---------------------------------------------------
# 모든 폴더 순회하면서 txt 파일 갱신
# ---------------------------------------------------
def process_all_folders(base_dir):
    for root, dirs, files in os.walk(base_dir):
        for name in files:
            if name.lower().endswith(".txt"):
                path = os.path.join(root, name)
                process_txt(path)


# ---------------------------------------------------
# 실행
# ---------------------------------------------------
if __name__ == "__main__":
    base = os.getcwd()
    print(f"[INFO] 재필터링 시작: {base}")

    process_all_folders(base)

    print("[INFO] 모든 프롬프트 갱신 완료")
