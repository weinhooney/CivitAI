from concurrent.futures import ThreadPoolExecutor

# 이미지 메타데이터 처리: API 호출 간격(1초) 고려하여 3개로 제한
IMG_META_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ImgMeta")

# LoRA 처리: 파일 다운로드 및 후처리가 주요 작업이므로 유지
BG_LORA_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="Lora")
