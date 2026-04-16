#!/usr/bin/env python3
"""
数据采集主脚本
一键运行: 收集截图 -> 标注 -> 导出 parquet

使用方式:
    python run_pipeline.py              # 完整流程
    python run_pipeline.py --collect    # 仅收集截图
    python run_pipeline.py --label      # 仅标注（需要已有截图）
    python run_pipeline.py --export     # 仅导出（需要已有标注数据）
"""
import argparse
import sys
from pathlib import Path

# 添加当前目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from collector import (
    collect_screenshots,
    process_and_save,
    RAW_CAPTURES_DIR,
    SCREENSHOT_DIR,
)
from exporter import (
    load_labeled_data,
    convert_to_minimind_format,
    export_to_parquet,
    export_temporal_pairs,
    PARQUET_DIR,
)


def step_collect():
    """步骤1: 收集截图"""
    print("\n" + "=" * 60)
    print("STEP 1: Collect Screenshots")
    print("=" * 60)

    screenshots = collect_screenshots()
    print(f"\nFound {len(screenshots)} screenshots in {SCREENSHOT_DIR}")

    if not screenshots:
        print("[WARN] No screenshots to process")
        return False

    # 复制到 raw 目录
    import shutil
    from config import RAW_CAPTURES_DIR

    RAW_CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for shot in screenshots:
        src = Path(shot["path"])
        dst = RAW_CAPTURES_DIR / shot["filename"]
        if not dst.exists():
            shutil.copy2(src, dst)
            copied += 1

    print(f"Copied {copied} new screenshots to {RAW_CAPTURES_DIR}")
    return True


def step_label():
    """步骤2: 标注截图"""
    print("\n" + "=" * 60)
    print("STEP 2: Label Screenshots (MiniMax API)")
    print("=" * 60)

    from config import MINIMAX_API_KEY

    if not MINIMAX_API_KEY:
        print("[ERROR] MINIMAX_API_KEY not set")
        print("  Set it via environment variable:")
        print("    export MINIMAX_API_KEY=your_api_key")
        return False

    from collector import label_screenshot

    screenshots = collect_screenshots()
    results = process_and_save(screenshots, RAW_CAPTURES_DIR, label_screenshot)

    print(f"\nLabeled {len(results)} screenshots")
    return True


def step_export():
    """步骤3: 导出 parquet"""
    print("\n" + "=" * 60)
    print("STEP 3: Export to Parquet")
    print("=" * 60)

    records = load_labeled_data()
    print(f"Loaded {len(records)} labeled records")

    if not records:
        print("[WARN] No labeled data to export")
        return False

    # SFT 数据
    converted = convert_to_minimind_format(records)
    sft_path = export_to_parquet(converted, split="train")
    print(f"Exported SFT: {sft_path}")

    # RL 时序数据
    pairs = export_temporal_pairs(converted)
    if pairs:
        import json
        pairs_path = PARQUET_DIR / "temporal_pairs.json"
        with open(pairs_path, "w", encoding="utf-8") as f:
            json.dump(pairs, f, ensure_ascii=False, indent=2)
        print(f"Exported RL pairs: {pairs_path}")

    # 统计
    print("\n[Activity Distribution]")
    activity_counts = {}
    for r in converted:
        act = r.get("activity", "unknown")
        activity_counts[act] = activity_counts.get(act, 0) + 1
    for act, count in sorted(activity_counts.items(), key=lambda x: -x[1]):
        print(f"  {act}: {count}")

    return True


def main():
    parser = argparse.ArgumentParser(description="VLM Training Data Pipeline")
    parser.add_argument(
        "--collect", action="store_true", help="Only run collect step"
    )
    parser.add_argument(
        "--label", action="store_true", help="Only run label step"
    )
    parser.add_argument(
        "--export", action="store_true", help="Only run export step"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all steps (default)"
    )

    args = parser.parse_args()

    # 默认运行全部
    run_all = args.all or not (args.collect or args.label or args.export)

    print("=" * 60)
    print("VLM Training Data Collection Pipeline")
    print("=" * 60)
    print(f"Collect dir: {SCREENSHOT_DIR}")
    print(f"Working dir: {RAW_CAPTURES_DIR}")
    print(f"Output dir: {PARQUET_DIR}")

    success = True

    if run_all or args.collect:
        if not step_collect():
            success = False

    if (run_all or args.label) and success:
        if not step_label():
            success = False

    if (run_all or args.export) and success:
        if not step_export():
            success = False

    print("\n" + "=" * 60)
    if success:
        print("Pipeline completed successfully!")
    else:
        print("Pipeline failed, check errors above")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
