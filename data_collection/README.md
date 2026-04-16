# 数据采集管道

根据 `plan.md` 阶段 1 实施的数据采集代码。

## 目录结构

```
data_collection/
├── trigger_daemon.py    # 截图触发器守护进程
├── start_trigger.sh     # 前台启动脚本
├── start_trigger_bg.sh  # 后台启动脚本
├── collector.py         # 截图采集和标注
├── exporter.py          # 数据格式转换和导出
├── run_pipeline.py      # 数据处理主脚本
├── requirements.txt     # Python 依赖
└── README.md
```

## 截图触发器 (trigger_daemon.py)

数据采集专用的截图触发器，替代原来的 screenshot-daemon。

### 触发条件

| 触发条件 | 说明 |
|---------|------|
| **Enter 键** | 立即截取当前活跃应用窗口 |
| **鼠标静止 60s** | 截取当前活跃应用窗口 |

### 去重逻辑

- 同一窗口（app_name + window_title）只截一次
- 直到用户切换到其他窗口才会重新允许截图
- Cmd+Tab 切换应用时清空去重记录
- 如果同一窗口超过 5 分钟，允许重新截图

### 使用方法

```bash
# 安装依赖
pip install -r requirements.txt

# 前台运行
./start_trigger.sh

# 后台运行
./start_trigger_bg.sh
```

### 环境变量

| 变量 | 默认值 | 说明 |
|-----|-------|------|
| `SCREENSHOT_DIR` | `~/Documents/code/memory/screenshot-daemon/captures` | 截图保存目录 |
| `IDLE_TIMEOUT` | `60` | 静止超时秒数 |
| `MIN_CAPTURE_INTERVAL` | `5.0` | 最小截图间隔 |

### 添加自定义触发器

```python
from trigger_daemon import register_trigger

def check_slack():
    # 返回 True 时触发截图
    return is_slack_open()

register_trigger("slack", check_slack, interval=30.0)
```

## 数据处理管道

### 1. 设置环境变量

```bash
export MINIMAX_API_KEY=your_api_key_here
```

### 2. 运行完整流程

```bash
python run_pipeline.py
```

### 3. 分步运行

```bash
python run_pipeline.py --collect   # 收集截图
python run_pipeline.py --label     # 调用 MiniMax 标注
python run_pipeline.py --export     # 导出 parquet
```

## Activity 分类（7类）

- `coding` - 编写/调试代码
- `reading` - 阅读文档/代码
- `browsing` - 浏览网页
- `meeting` - 会议/沟通
- `writing` - 写作/整理
- `research` - 调研/搜索
- `idle` - 空闲/发呆

## 输出文件

```
data/
├── raw/                    # 原始截图 + 标注 JSON
│   ├── 20260407_151434.json
│   └── ...
├── labeled/                # 标注后的数据
└── parquet/
    ├── train.parquet       # SFT 训练数据
    └── temporal_pairs.json # RL 时序数据
```

## 参考

- plan.md 阶段 1：数据采集管道
- minimind-v: 基座模型代码
