#!/bin/bash
# 启动数据采集截图触发器（后台运行）
cd "$(dirname "$0")"
nohup python3 trigger_daemon.py > trigger_daemon.log 2>&1 &
echo "Started: PID $!"
