"""
截图采集器
从 screenshot-daemon 目录采集截图，整理成可处理的数据集
"""
import json
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional
import httpx

from config import (
    SCREENSHOT_DIR,
    RAW_CAPTURES_DIR,
    MINIMAX_API_KEY,
    MINIMAX_API_URL,
    MINIMAX_MODEL,
    LABEL_PROMPT,
    CONCURRENT_REQUESTS,
    REQUEST_INTERVAL,
)


def encode_image_to_base64(image_path: Path) -> Optional[str]:
    """将图片编码为 base64 字符串"""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"[ERROR] Failed to encode {image_path}: {e}")
        return None


def label_screenshot(image_path: Path) -> Optional[dict]:
    """
    使用 MiniMax API 对截图进行标注
    返回: {"activity": "...", "intent": "...", "confidence": 0.x, "reasoning": "..."}
    """
    if not MINIMAX_API_KEY:
        print("[WARN] MINIMAX_API_KEY not set, skipping label")
        return None

    image_base64 = encode_image_to_base64(image_path)
    if not image_base64:
        return None

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MINIMAX_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": LABEL_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        },
                    },
                ],
            }
        ],
        "max_tokens": 512,
        "temperature": 0.3,
    }

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                MINIMAX_API_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            # 解析 MiniMax 返回的内容
            content = result["choices"][0]["message"]["content"]

            # 尝试解析 JSON
            # 有些模型会返回 ```json ... ``` 格式，需要提取
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()

            return json.loads(content)

    except Exception as e:
        print(f"[ERROR] Failed to label {image_path.name}: {e}")
        return None


def parse_screenshot_filename(filename: str) -> dict:
    """
    从 screenshot-daemon 的命名规则解析信息
    命名格式: {timestamp}_{reason}_{app_name}.png
    例如: 20260407_151434_enter_Safari.png
    """
    parts = filename.replace(".png", "").split("_")
    if len(parts) >= 3:
        return {
            "timestamp": parts[0] + "_" + parts[1],  # YYYYMMDD_HHMMSS
            "reason": parts[2],  # enter / idle
            "app_name": "_".join(parts[3:]) if len(parts) > 3 else "unknown",
            "datetime": datetime.strptime(parts[0] + "_" + parts[1], "%Y%m%d_%H%M%S"),
        }
    return {
        "timestamp": "unknown",
        "reason": "unknown",
        "app_name": "unknown",
        "datetime": datetime.now(),
    }


def collect_screenshots() -> list[dict]:
    """
    扫描 screenshot-daemon 目录，收集所有截图并整理元数据
    返回截图列表，每个元素包含路径和元数据
    """
    if not SCREENSHOT_DIR.exists():
        print(f"[ERROR] Screenshot dir not found: {SCREENSHOT_DIR}")
        return []

    screenshots = []
    for img_path in SCREENSHOT_DIR.glob("*.png"):
        meta = parse_screenshot_filename(img_path.name)
        meta["path"] = str(img_path)
        meta["filename"] = img_path.name
        meta["size_kb"] = img_path.stat().st_size / 1024
        screenshots.append(meta)

    # 按时间排序
    screenshots.sort(key=lambda x: x["datetime"])

    print(f"[INFO] Found {len(screenshots)} screenshots")
    return screenshots


def process_and_save(
    screenshots: list[dict],
    output_dir: Path,
    label_fn=label_screenshot,
) -> list[dict]:
    """
    批量处理截图，生成标注数据
    label_fn: 标注函数，接受 Path，返回标注 dict 或 None
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, shot in enumerate(screenshots):
        print(f"[{i+1}/{len(screenshots)}] Processing {shot['filename']}...")

        label = label_fn(Path(shot["path"]))

        record = {
            **shot,
            "label": label,
            "processed_at": datetime.now().isoformat(),
        }

        # 保存单条记录
        output_path = output_dir / f"{shot['timestamp']}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        results.append(record)

        # 简单 rate limit
        import time
        time.sleep(REQUEST_INTERVAL)

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("Screenshot Data Collection Pipeline")
    print("=" * 60)
    print(f"Screenshot dir: {SCREENSHOT_DIR}")
    print(f"Output dir: {RAW_CAPTURES_DIR}")
    print()

    # 1. 收集截图
    screenshots = collect_screenshots()

    if not screenshots:
        print("[WARN] No screenshots found")
        exit(0)

    # 2. 复制到 raw 目录（备份原始截图）
    import shutil

    RAW_CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    for shot in screenshots:
        src = Path(shot["path"])
        dst = RAW_CAPTURES_DIR / shot["filename"]
        if not dst.exists():
            shutil.copy2(src, dst)
            print(f"[COPY] {shot['filename']} -> {RAW_CAPTURES_DIR}")

    # 3. 批量标注
    print("\n[STEP] Labeling screenshots...")
    results = process_and_save(screenshots, RAW_CAPTURES_DIR)

    print(f"\n[DONE] Processed {len(results)} screenshots")
    print(f"Output: {RAW_CAPTURES_DIR}")
