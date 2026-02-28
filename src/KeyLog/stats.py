import atexit
import os
import json

from datetime import datetime
from time import sleep
from threading import Thread
from typing import Callable

from .constants import BASE_DIR
from .handler import is_valid

type Stat = dict[str, dict[str, int]]

STATS_FILE = os.path.join(BASE_DIR, "stats.json")
SAVES_FOLDER = "saves"

def load_stats() -> Stat:
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)

        # --- Functional filtering ---
        keyboard_stats = stats.get("keyboard", {})
        stats["keyboard"] = dict(
            filter(lambda item: is_valid(item[0]), keyboard_stats.items())
        )

        stats["mouse"] = stats.get("mouse", {})  # unchanged
        return stats
    return {
        "keyboard": {},
        "mouse": {
            "left": 0,
            "right": 0,
            "middle": 0
        }
    }


def save_stats(stats, lock) -> Callable[[], None]:
    def wrapper():
        with lock:
            with open(STATS_FILE, "w") as f:
                f.write(json.dumps(stats, indent=2))
                print("[autosave] Saved stats.")
    return wrapper


def create_backup(stats, lock) -> Callable[[], None]:
    def wrapper():
        saves_dir = os.path.join(BASE_DIR, SAVES_FOLDER)
        if not os.path.exists(saves_dir):
            os.mkdir(saves_dir)

        time: str = datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
        save_name = f"backup_at_{time}.json"
        file_path = os.path.join(saves_dir, save_name)
        with lock:
            with open(file_path, "w") as f:
                f.write(json.dumps(stats, indent=2))
                print("[backup] Made backup.")
    return wrapper

def autosave_loop(save_handler, interval):
    while True:
        sleep(interval)
        save_handler()

def start_autosave_thread(save_handler, interval):
    print(f"[{save_handler.__name__}] Starting thread.")
    Thread(
        target=autosave_loop,
        args=(save_handler, interval),
        daemon=True
    ).start()

def register_handler(handler, interval):
    atexit.register(handler)
    start_autosave_thread(handler, interval)
