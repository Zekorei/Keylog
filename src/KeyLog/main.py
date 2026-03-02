import os
import platform
import sys

from pynput import keyboard, mouse
from threading import Lock

from .display import StatsApp
from .handler import on_click, on_press, on_release
from .stats import load_stats, save_stats, create_backup, register_handler

SAVE_INTERVAL: int = 10
BACKUP_INTERVAL: int = 60*60*4

lock = Lock()

def check_linux_display():
    if platform.system() != "Linux":
        return

    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        print("Wayland session detected.")
        print("Global keyboard capture is not supported under Wayland.")
        sys.exit(1)

def setup():
    stats = load_stats()
    pressed_keys = set()

    save_handler = save_stats(stats, lock)
    register_handler(save_handler, SAVE_INTERVAL)

    backup_handler = create_backup(stats, lock)
    register_handler(backup_handler, BACKUP_INTERVAL)

    keyboard.Listener(on_press=on_press(stats, lock, pressed_keys),
                      on_release=on_release(pressed_keys)).start()
    mouse.Listener(on_click=on_click(stats, lock),
                   on_release=on_release(pressed_keys)).start()

    app = StatsApp(stats, lock)
    app.run()

def main():
    check_linux_display()

    setup()

if __name__ == "__main__":
    main()