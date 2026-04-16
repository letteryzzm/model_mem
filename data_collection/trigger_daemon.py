"""
Screenshot Trigger Daemon - 数据采集专用截图触发器

触发条件：
  1. Enter 键 → 截取当前活跃应用窗口
  2. 鼠标静止 60s → 截取当前活跃应用窗口（仅第一次，之后直到用户活动才重新允许）

去重逻辑：
  - 静止超时触发后，标记"已触发"，不再重复截图
  - 只有用户活动（鼠标移动）才重置标记，允许下一次静止截图

环境变量：
  SCREENSHOT_DIR       - 截图保存目录
  IDLE_TIMEOUT         - 静止超时秒数（默认 60）
  MIN_CAPTURE_INTERVAL - 最小截图间隔（默认 5s）
"""
import os
import time
import hashlib
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from AppKit import NSWorkspace
from pynput import keyboard, mouse
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGNullWindowID,
    kCGWindowListExcludeDesktopElements,
    kCGWindowListOptionOnScreenOnly,
)


# ─── 配置 ───
SCREENSHOT_DIR = Path(os.environ.get(
    "SCREENSHOT_DIR",
    os.path.expanduser("~/Documents/code/memory/screenshot-daemon/captures"),
))
IDLE_TIMEOUT = int(os.environ.get("IDLE_TIMEOUT", "60"))
MIN_CAPTURE_INTERVAL = float(os.environ.get("MIN_CAPTURE_INTERVAL", "5.0"))

SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


# ─── 状态 ───
last_mouse_move_time = time.time()
last_capture_time = 0.0
cmd_held = False
lock = threading.Lock()

# ─── 静止触发状态 ───
# 用户静止超时后标记为 True，只有用户活动才重置
_idle_triggered = False


def get_window_info():
    """
    获取当前活跃窗口信息
    返回: (window_id, app_name, window_title, window_bounds)
    """
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if not app:
        return None, None, None, None

    pid = app.processIdentifier()
    app_name = app.localizedName() or "unknown"

    options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)

    target_window = None
    for window in window_list:
        if window.get("kCGWindowOwnerPID") == pid:
            layer = window.get("kCGWindowLayer", -1)
            if layer == 0:
                target_window = window
                break

    if not target_window:
        return None, app_name, None, None

    window_id = target_window.get("kCGWindowNumber")
    window_title = target_window.get("kCGWindowName", "") or target_window.get("kCGWindowOwnerName", "")

    bounds = target_window.get("kCGWindowBounds", {})

    return window_id, app_name, window_title, bounds


def capture_active_window(reason: str) -> Optional[Path]:
    """
    截取当前活跃应用窗口
    """
    global last_capture_time
    now = time.time()

    with lock:
        if now - last_capture_time < MIN_CAPTURE_INTERVAL:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] skipped ({reason}): too soon since last capture")
            return None
        last_capture_time = now

    window_id, app_name, window_title, bounds = get_window_info()

    if not app_name:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] skipped ({reason}): no active window")
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{ts}_{reason}_{app_name}.png"
    filepath = SCREENSHOT_DIR / filename

    # 截取活跃窗口
    if window_id:
        cmd = ["screencapture", "-x", "-l", str(window_id), str(filepath)]
    else:
        cmd = ["screencapture", "-x", "-C", str(filepath)]

    ret = subprocess.run(cmd, capture_output=True)

    if ret.returncode != 0 or not filepath.exists():
        print(f"[{datetime.now().strftime('%H:%M:%S')}] screencapture failed: {ret.stderr.decode()}")
        return None

    size_kb = filepath.stat().st_size / 1024
    title_short = (window_title[:30] + "...") if window_title and len(window_title) > 30 else (window_title or "untitled")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] captured ({reason}) [{app_name}] {title_short}: {filename} ({size_kb:.0f}KB)")

    return filepath


# ─── 鼠标监听 ───
def on_mouse_move(x, y):
    global last_mouse_move_time, _idle_triggered
    last_mouse_move_time = time.time()
    # 用户活动了，重置静止触发标记
    if _idle_triggered:
        _idle_triggered = False
        print(f"[{datetime.now().strftime('%H:%M:%S')}] user active, reset idle trigger")


# ─── 键盘监听 ───
def on_key_press(key):
    global cmd_held

    if key in (keyboard.Key.cmd, keyboard.Key.cmd_r):
        cmd_held = True
        return

    # Cmd+Tab 切换应用时清空状态
    if cmd_held and key == keyboard.Key.tab:
        global _idle_triggered
        _idle_triggered = False
        print(f"[{datetime.now().strftime('%H:%M:%S')}] app switch detected")
        return

    # Enter 键触发截图
    if key == keyboard.Key.enter:
        capture_active_window("enter")


def on_key_release(key):
    global cmd_held
    if key in (keyboard.Key.cmd, keyboard.Key.cmd_r):
        cmd_held = False


# ─── 静止检测线程 ───
def idle_watcher():
    """
    每秒检查鼠标是否静止超过阈值
    静止超时后只触发一次截图，除非用户再次活动
    """
    global _idle_triggered

    while True:
        time.sleep(1)
        idle_duration = time.time() - last_mouse_move_time

        if idle_duration >= IDLE_TIMEOUT:
            # 静止超时
            if not _idle_triggered:
                # 第一次检测到静止超时，截图
                filepath = capture_active_window("idle")
                if filepath:
                    _idle_triggered = True
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] idle capture done, waiting for activity to reset")
            # else: 已触发过，不重复截图


# ─── 可扩展的触发器注册表 ───
_triggers: list[tuple[str, Callable[[], bool], float]] = []


def register_trigger(name: str, trigger_fn: Callable[[], bool], interval: float = 1.0):
    """
    注册自定义触发器

    示例:
        def check_slack():
            return is_slack_open()  # True = 触发截图

        register_trigger("slack_check", check_slack, interval=30.0)
    """
    _triggers.append((name, trigger_fn, interval))
    print(f"[TRIGGER] Registered: {name} (every {interval}s)")


def custom_triggers_watcher():
    """运行自定义触发器"""
    last_run: dict[str, float] = {}

    while True:
        current_time = time.time()

        for name, trigger_fn, interval in _triggers:
            last = last_run.get(name, 0)

            if current_time - last >= interval:
                try:
                    if trigger_fn():
                        capture_active_window(f"trigger_{name}")
                except Exception as e:
                    print(f"[TRIGGER ERROR] {name}: {e}")

                last_run[name] = current_time

        time.sleep(0.5)


# ─── 主函数 ───
def main():
    print("=" * 60)
    print("Screenshot Trigger Daemon (Data Collection)")
    print("=" * 60)
    print(f"  Screenshot dir:   {SCREENSHOT_DIR}")
    print(f"  Idle timeout:     {IDLE_TIMEOUT}s")
    print(f"  Min interval:     {MIN_CAPTURE_INTERVAL}s")
    print()
    print("  Triggers:")
    print(f"    [Enter]         - Capture active window")
    print(f"    [Idle {IDLE_TIMEOUT}s]    - Capture once, wait for activity to reset")
    print()

    # 启动静止检测线程
    threading.Thread(target=idle_watcher, daemon=True).start()

    # 启动自定义触发器线程
    if _triggers:
        threading.Thread(target=custom_triggers_watcher, daemon=True).start()
        print(f"  Custom triggers:  {len(_triggers)}")

    # 启动输入监听
    mouse_listener = mouse.Listener(on_move=on_mouse_move)
    keyboard_listener = keyboard.Listener(
        on_press=on_key_press, on_release=on_key_release
    )

    mouse_listener.start()
    keyboard_listener.start()

    print()
    print("Ready! Press Enter to capture, or wait for idle timeout...")
    print("Press Ctrl+C to stop.")
    print()

    try:
        keyboard_listener.join()
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


if __name__ == "__main__":
    main()
