# -*- coding: utf-8 -*-
"""
여러 개의 CivitAI 사용자 모델 URL을 한 번에 처리하기 위한 배치 스크립트.

- 같은 폴더에 있는 get_all_models.py 를 그대로 재사용한다.
- get_all_models_urls.txt 에 한 줄에 하나씩 URL을 적어두면,
  각 URL을 차례대로 처리한다.
"""

import os
import sys
import subprocess

# 한 줄에 하나씩 URL을 적어둘 텍스트 파일 이름
URL_LIST_FILE = "get_all_models_urls.txt"


def read_url_list(path):
    """텍스트 파일에서 URL 목록을 읽어온다."""
    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            urls.append(line)
    return urls


def run_get_all_models_for_url(get_all_path, url):
    """
    get_all_models.py 를 별도 프로세스로 실행해서
    하나의 URL에 대한 처리를 끝까지 수행한다.
    """
    print("\n" + "=" * 80)
    print(f"[BATCH] 시작: {url}")
    print("=" * 80 + "\n")

    # get_all_models.py 는 실행 시 input() 으로 URL을 한 번 받으므로
    # 표준 입력에 url + 개행을 넘겨준다.
    proc = subprocess.run(
        [sys.executable, get_all_path],
        input=url + "\n",
        text=True,
        cwd=os.path.dirname(get_all_path),
    )

    if proc.returncode != 0:
        print(f"[BATCH][ERROR] 처리 실패 (exit code={proc.returncode}): {url}")
    else:
        print(f"[BATCH] 완료: {url}")

    return proc.returncode


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    get_all_path = os.path.join(script_dir, "get_all_models.py")
    url_list_path = os.path.join(script_dir, URL_LIST_FILE)

    if not os.path.exists(get_all_path):
        print(f"[ERROR] get_all_models.py 를 찾을 수 없습니다: {get_all_path}")
        return

    if not os.path.exists(url_list_path):
        print(f"[ERROR] URL 목록 파일이 없습니다: {url_list_path}")
        print(f"한 줄에 하나씩 URL을 적은 파일을 만들고,")
        print(f"파일 이름을 {URL_LIST_FILE} 로 저장한 뒤 다시 실행하세요.")
        return

    urls = read_url_list(url_list_path)
    if not urls:
        print(f"[ERROR] URL 목록이 비어 있습니다: {url_list_path}")
        return

    print(f"[BATCH] 총 {len(urls)}개 URL 처리 시작")

    for idx, url in enumerate(urls, 1):
        print(f"\n[BATCH] ({idx}/{len(urls)}) 처리 중: {url}")
        code = run_get_all_models_for_url(get_all_path, url)
        if code != 0:
            print(f"[BATCH][WARN] {url} 처리 중 에러 발생, 다음 URL로 계속 진행")

    print("\n[BATCH] 모든 URL 처리 완료")


if __name__ == "__main__":
    main()
