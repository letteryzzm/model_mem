"""
数据采集配置
连接 screenshot-daemon 和数据处理管道
"""
from pathlib import Path
from dataclasses import dataclass
import os

# ========== 路径配置 ==========
# screenshot-daemon 截图目录
SCREENSHOT_DIR = Path(os.environ.get(
    "SCREENSHOT_DIR",
    os.path.expanduser("~/Documents/code/memory/screenshot-daemon/captures"),
))

# 输出目录
OUTPUT_DIR = Path(os.environ.get(
    "OUTPUT_DIR",
    os.path.expanduser("~/Documents/code/mem_rl/model_mem/data"),
))

# 原始截图缓存
RAW_CAPTURES_DIR = OUTPUT_DIR / "raw"
# 标注后的数据
LABELED_DIR = OUTPUT_DIR / "labeled"
# 最终 parquet 数据集
PARQUET_DIR = OUTPUT_DIR / "parquet"

# ========== MiniMax API 配置 ==========
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_API_URL = os.environ.get(
    "MINIMAX_API_URL",
    "https://api.minimax.chat/v1/text/chatcompletion_v2"
)
MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-Text-01")

# ========== Activity 分类体系 ==========
# 参考 plan.md：5~8 类，越少越好验证
ACTIVITIES = [
    "coding",      # 编写/调试代码
    "reading",     # 阅读文档/代码
    "browsing",    # 浏览网页
    "meeting",     # 会议/沟通
    "writing",     # 写作/整理
    "research",    # 调研/搜索
    "idle",        # 空闲/发呆
]

# ========== 标注提示词 ==========
LABEL_PROMPT = """你是一个行为理解专家。根据截图内容，分析用户的当前活动状态。

## Activity 分类（必须选择一个）:
- coding: 编写、调试、查看代码
- reading: 阅读文档、代码、书籍
- browsing: 浏览网页、社交媒体
- meeting: 视频会议、聊天
- writing: 写文档、做笔记、整理
- research: 调研、搜索、分析
- idle: 空闲、等待、发呆

## Intent 描述:
用 1-2 句话描述用户的具体意图，例如："正在修复 Docker 网络问题" 或 "阅读 React 文档"

## 输出格式（严格 JSON）:
{
    "activity": "activity_name",
    "intent": "用户意图描述",
    "confidence": 0.0-1.0,
    "reasoning": "简要推理过程"
}

只输出 JSON，不要有其他内容。"""

# ========== 数据采集配置 ==========
# 批量处理大小
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
# 标注并发数
CONCURRENT_REQUESTS = int(os.environ.get("CONCURRENT_REQUESTS", "3"))
# 请求间隔（秒）
REQUEST_INTERVAL = float(os.environ.get("REQUEST_INTERVAL", "1.0"))
