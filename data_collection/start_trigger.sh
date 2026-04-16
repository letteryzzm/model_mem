#!/bin/bash
# 启动数据采集截图触发器
cd "$(dirname "$0")"
exec python3 trigger_daemon.py
