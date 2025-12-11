from concurrent.futures import ThreadPoolExecutor

IMG_META_EXECUTOR = ThreadPoolExecutor(max_workers=8)
BG_LORA_EXECUTOR = ThreadPoolExecutor(max_workers=4)
