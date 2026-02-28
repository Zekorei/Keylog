from string import ascii_letters, digits

ALLOWED_CHARS = set(ascii_letters + digits + "_")

def is_valid(key):
    if key == "":
        return False
    if key.isprintable() and all(c in ALLOWED_CHARS for c in key):
        return True
        # Allow named keys like ctrl_l, shift_r, f1, etc.
    if key.isalpha() and "_" in key:  # crude check for named keys
        return True
    return False

def normalize_key(key):
    try:
        return key.char.lower()
    except AttributeError:
        return str(key).replace("Key.", "").lower()

def on_press(stats, lock, pressed_keys):
    def handler(key):
        if key in pressed_keys:
            return

        pressed_keys.add(key)

        k = normalize_key(key)
        if not is_valid(k):
            return

        with lock:
            stats["keyboard"][k] = stats["keyboard"].get(k, 0) + 1
    return handler

def on_release(pressed_keys: set):
    def handler(key):
        pressed_keys.discard(key)
    return handler

def on_click(stats, lock):
    def handler(x, y, button, pressed):
        if not pressed:
            return

        button_id = str(button).replace("Button.", "")

        with lock:
            stats["mouse"][button_id] = stats["mouse"].get(button_id, 0) + 1
    return handler
