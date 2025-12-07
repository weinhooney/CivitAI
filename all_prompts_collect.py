# -*- coding: utf-8 -*-
"""
all_prompts_collect.py

지정된 폴더(기본: 현재 작업 폴더) 이하의 모든 하위 폴더를 순회하면서
각 .txt 파일의 JSON에서 "raw_prompt" 항목을 읽어,
콤마(,) 기준으로 나눈 토큰들 중:
  - "<lora:" 로 시작해서 ">" 로 끝나는 토큰은 제외하고
  - 나머지 토큰들을 전부 모은 뒤 (중복 제거)
base 폴더에 all_prompts.json 파일로 저장한다.

출력 형식:
    [
      "1girl",
      "solo",
      "score_9",
      ...
    ]

사용 예:
    python all_prompts_collect.py
    python all_prompts_collect.py D:\\CivitAI\\Users\\foobar
"""

import os
import sys
import json


def collect_from_raw_prompt(raw_prompt: str, acc_list, acc_set):
    """
    raw_prompt 문자열에서 콤마 기준으로 토큰을 나누고,
    <lora:...> 형태의 토큰을 제외한 나머지를 acc_list / acc_set 에 누적한다.
    - acc_list: 최종 JSON에 기록될 리스트 (순서 유지)
    - acc_set : 중복 체크용 집합 (정규화 키 기준)
    """
    if not raw_prompt:
        return

    if "BREAK" in raw_prompt:
        print(f"[DEBUG] BREAK found in prompt: {raw_prompt}")

    # 🔥 get_model.py에서 공통화한 정규화 기능 재사용
    try:
        from get_model import normalize_prompt_basic, normalize_filter_item
    except ImportError:
        # fallback: 최소 동작만 (정규화 없이)
        tmp = raw_prompt.replace("\r", " ").replace("\n", " ")
        def normalize_filter_item(x: str) -> str:
            return x.strip().lower()
    else:
        tmp = normalize_prompt_basic(raw_prompt)

    # 줄바꿈 제거 후 콤마 기준 분리
    tmp = tmp.replace("\r", " ").replace("\n", " ")
    raw_tokens = [t.strip() for t in tmp.split(",")]

    for token in raw_tokens:
        if not token:
            continue

        stripped = token.strip()

        # LoRA 태그는 제외: "<lora:" 로 시작하고 ">" 로 끝나는 토큰만 로라로 본다.
        if stripped.startswith("<lora:") and stripped.endswith(">"):
            continue

        # 🔹 정규화 키 생성
        #    "(Naughty smile:0.7)" → "naughty smile"
        key = normalize_filter_item(stripped)
        if not key:
            continue

        # 정규화 키 기준 중복 제거
        if key in acc_set:
            continue

        # acc_set 은 "논리적인 항목" 집합 (정규화된 키)
        acc_set.add(key)

        # acc_list 에 뭐 넣을지는 선택사항:
        #  - 첫 등장한 원본 문자열을 그대로 넣고 싶으면 stripped
        #  - 항상 정규화된 형태("naughty smile")로만 저장하고 싶으면 key
        # 여기서는 정규화된 값을 저장하도록 한다.
        acc_list.append(key)



def process_txt(path: str, acc_list, acc_set):
    """
    txt (JSON) 파일 하나를 열어서 raw_prompt가 있으면 수집.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        # print(f"[WARN] JSON 파싱 실패, 스킵: {path} - {e}")
        return

    if "raw_prompt" not in data:
        return

    raw_prompt = data.get("raw_prompt")
    if raw_prompt is None:
        return

    if not isinstance(raw_prompt, str):
        # 문자열이 아니면 스킵
        return

    collect_from_raw_prompt(raw_prompt, acc_list, acc_set)


def walk_all_txt(base_dir: str):
    """
    base_dir 이하 모든 .txt 파일 순회하면서 raw_prompt 수집.
    """
    collected_list = []
    collected_set = set()

    for root, dirs, files in os.walk(base_dir):
        for name in files:
            if not name.lower().endswith(".txt"):
                continue
            path = os.path.join(root, name)
            process_txt(path, collected_list, collected_set)

    return collected_list


def main():
    if len(sys.argv) >= 2:
        base_dir = sys.argv[1]
    else:
        base_dir = os.getcwd()

    # base_dir = os.path.abspath(base_dir)
    base_dir = r"E:\CivitAI\Users"
    # base_dir = r"E:\CivitAI\Users\Busterkun\Aisaki Miyako - Hugtto! Precure (ILXL)"
    
    print(f"[INFO] all_prompts_collect 시작: {base_dir}")

    if not os.path.isdir(base_dir):
        print(f"[ERROR] 유효하지 않은 폴더: {base_dir}")
        sys.exit(1)

    prompts = walk_all_txt(base_dir)

    # 결과 저장
    out_path = os.path.join(base_dir, "all_prompts.json")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, indent=2, ensure_ascii=False)
        print(f"[INFO] 수집된 프롬프트 수: {len(prompts)}")
        print(f"[INFO] 저장 완료: {out_path}")
    except Exception as e:
        print(f"[ERROR] all_prompts.json 저장 실패: {e}")
        sys.exit(1)

    print("[INFO] 작업 완료")


if __name__ == "__main__":
    main()
