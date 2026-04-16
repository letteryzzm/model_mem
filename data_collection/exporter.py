"""
数据导出器
将标注后的数据转换为 minimind-v 所需的 parquet 格式
"""
import json
import glob
from pathlib import Path
from datetime import datetime
from typing import Optional
import pyarrow as pa
import pyarrow.parquet as pq

from config import RAW_CAPTURES_DIR, LABELED_DIR, PARQUET_DIR, ACTIVITIES


def load_labeled_data(data_dir: Path = RAW_CAPTURES_DIR) -> list[dict]:
    """加载所有已标注的数据"""
    records = []

    for json_path in data_dir.glob("*.json"):
        with open(json_path, "r", encoding="utf-8") as f:
            records.append(json.load(f))

    # 按时间排序
    records.sort(key=lambda x: x.get("datetime", datetime.now()))

    return records


def validate_activity(activity: str) -> str:
    """验证并规范化 activity 标签"""
    activity = activity.lower().strip()

    # 模糊匹配
    activity_mapping = {
        "code": "coding",
        "debug": "coding",
        "programming": "coding",
        "read": "reading",
        "docs": "reading",
        "browse": "browsing",
        "web": "browsing",
        "meeting": "meeting",
        "chat": "meeting",
        "video": "meeting",
        "write": "writing",
        "note": "writing",
        "doc": "writing",
        "search": "research",
        "research": "research",
        "investigate": "research",
        "analyze": "research",
        "wait": "idle",
        "idle": "idle",
        "break": "idle",
    }

    return activity_mapping.get(activity, activity if activity in ACTIVITIES else "idle")


def convert_to_minimind_format(records: list[dict]) -> list[dict]:
    """
    转换为 minimind-v 训练格式

    minimind-v 的 SFT 数据格式参考：
    - 输入: 图片 + 文本 prompt
    - 输出: 结构化的 activity/intent

    格式参考 Second Me 的 Strong COT 格式
    """
    converted = []

    for record in records:
        label = record.get("label")
        if not label:
            continue

        activity = validate_activity(label.get("activity", "idle"))
        intent = label.get("intent", "")
        confidence = label.get("confidence", 0.0)
        reasoning = label.get("reasoning", "")

        # 构建 conversation 格式（参考 minimind-v）
        conversation = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "image": record["path"],
                    },
                    {
                        "type": "text",
                        "text": f"""分析这张截图，识别用户当前的活动状态和意图。

活动类型（共7类）：coding, reading, browsing, meeting, writing, research, idle

请以以下 JSON 格式输出：
{{"activity": "...", "intent": "..."}}""",
                    },
                ],
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "activity": activity,
                        "intent": intent,
                        "confidence": round(confidence, 2),
                        "reasoning": reasoning,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        converted.append({
            # 标准字段
            "id": f"sample_{record['timestamp']}",
            "conversations": conversation,
            "category": "activity_recognition",

            # 自定义元数据
            "activity": activity,
            "intent": intent,
            "confidence": round(confidence, 2),

            # 原始信息
            "source_file": record["filename"],
            "source_app": record.get("app_name", "unknown"),
            "capture_reason": record.get("reason", "unknown"),
            "captured_at": record.get("datetime", "").isoformat() if isinstance(record.get("datetime"), datetime) else record.get("datetime", ""),
            "processed_at": record.get("processed_at", ""),
        })

    return converted


def export_to_parquet(
    records: list[dict],
    output_path: Optional[Path] = None,
    split: str = "train",
) -> Path:
    """
    导出为 parquet 文件
    minimind-v 使用的 schema
    """
    if output_path is None:
        output_path = PARQUET_DIR / f"{split}.parquet"

    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    # 定义 schema（参考 minimind-v）
    schema = pa.schema([
        ("id", pa.string()),
        ("conversations", pa.list_(pa.struct([
            ("role", pa.string()),
            ("content", pa.string()),  # minimind-v 可能用 string 而不是 list
        ]))),
        ("category", pa.string()),
        # 自定义字段
        ("activity", pa.string()),
        ("intent", pa.string()),
        ("confidence", pa.float32()),
        # 元数据
        ("source_file", pa.string()),
        ("source_app", pa.string()),
        ("capture_reason", pa.string()),
        ("captured_at", pa.string()),
        ("processed_at", pa.string()),
    ])

    # 构建 table
    table = pa.Table.from_pylist(records, schema=schema)

    # 写入
    pq.write_table(table, output_path, compression="snappy")

    return output_path


def export_temporal_pairs(records: list[dict]) -> list[dict]:
    """
    导出时序对数据（用于 RL 训练）

    t 时刻预测 intent，t+N 时刻 memory 事件作为 ground truth 验证
    reward = 1.0 if predicted_activity == actual_next_activity
    """
    if len(records) < 2:
        return []

    pairs = []
    window_size = 5  # 前后 5 条记录内

    for i, current in enumerate(records):
        current_activity = current.get("activity")
        current_intent = current.get("intent")
        current_time = current.get("captured_at", "")

        if not current_activity or not current_intent:
            continue

        # 查找后续 memory 事件作为验证
        next_memory = None
        for j in range(i + 1, min(i + window_size, len(records))):
            next_record = records[j]
            if next_record.get("capture_reason") == "enter":
                next_memory = next_record
                break

        if next_memory:
            pairs.append({
                "prompt_id": current["id"],
                "prompt_activity": current_activity,
                "prompt_intent": current_intent,
                "prompt_time": current_time,
                "prompt_source": current.get("source_file", ""),

                "ground_truth_activity": next_memory.get("activity"),
                "ground_truth_intent": next_memory.get("intent"),
                "ground_truth_time": next_memory.get("captured_at", ""),
                "ground_truth_source": next_memory.get("source_file", ""),

                # Reward signal
                "activity_match": int(current_activity == next_memory.get("activity")),
                "intent_mentioned": int(
                    any(word in next_memory.get("intent", "").lower()
                        for word in current_intent.lower().split()
                        if len(word) > 2)
                ),
            })

    return pairs


def main():
    print("=" * 60)
    print("Data Exporter for minimind-v")
    print("=" * 60)
    print(f"Input dir: {RAW_CAPTURES_DIR}")
    print(f"Output dir: {PARQUET_DIR}")
    print()

    # 1. 加载数据
    print("[STEP 1] Loading labeled data...")
    records = load_labeled_data()
    print(f"  Found {len(records)} labeled records")

    if not records:
        print("[WARN] No labeled data found")
        return

    # 2. 转换为 minimind 格式
    print("\n[STEP 2] Converting to minimind-v format...")
    converted = convert_to_minimind_format(records)
    print(f"  Converted {len(converted)} samples")

    # 3. 导出 SFT parquet
    print("\n[STEP 3] Exporting SFT parquet...")
    sft_path = export_to_parquet(converted, split="train")
    print(f"  Saved: {sft_path}")

    # 4. 导出时序对（用于 RL）
    print("\n[STEP 4] Exporting temporal pairs for RL...")
    pairs = export_temporal_pairs(converted)

    if pairs:
        pairs_path = PARQUET_DIR / "temporal_pairs.json"
        import json as json_module
        with open(pairs_path, "w", encoding="utf-8") as f:
            json_module.dump(pairs, f, ensure_ascii=False, indent=2)
        print(f"  Saved: {pairs_path} ({len(pairs)} pairs)")

    # 5. 统计
    print("\n[STATS]")
    activity_counts = {}
    for r in converted:
        act = r.get("activity", "unknown")
        activity_counts[act] = activity_counts.get(act, 0) + 1

    for act, count in sorted(activity_counts.items(), key=lambda x: -x[1]):
        print(f"  {act}: {count}")

    print(f"\n[DONE]")


if __name__ == "__main__":
    main()
