import argparse
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk

import pynput
import pyperclip
import pystray
import requests
from PIL import Image

from dictation_format import format_transcript

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "global_dictation_config.json")
ICON_PATH = os.path.join(SCRIPT_DIR, "icon.png")
SERVER_URL = "http://127.0.0.1:8765"
IS_MAC = sys.platform == "darwin"

HOTKEY_KEYS = {
    "ctrl": pynput.keyboard.Key.ctrl,
    "alt": pynput.keyboard.Key.alt,
    "cmd": pynput.keyboard.Key.cmd,
    "shift": pynput.keyboard.Key.shift,
    "space": pynput.keyboard.Key.space,
}


class Config:
    def __init__(self):
        self.data = {"language": "auto", "hotkey": ["ctrl", "alt", "g"], "widget": None,
                     "history_file": "", "autostart": False, "skip_in_vscode": True}
        self.load()

    def load(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                self.data.update(json.load(f))
        except Exception:
            pass

    def save(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


config = Config()


def history_path():
    p = config.data.get("history_file") or ""
    return p if p else os.path.join(SCRIPT_DIR, "dictation_history.md")


def save_history(text):
    try:
        with open(history_path(), "a", encoding="utf-8") as f:
            f.write("## %s\n\n%s\n\n" % (time.strftime("%Y-%m-%d %H:%M"), text))
    except Exception:
        pass


def open_history():
    try:
        if os.name == "nt":
            os.startfile(history_path())
        elif IS_MAC:
            subprocess.Popen(["open", history_path()])
        else:
            subprocess.Popen(["xdg-open", history_path()])
    except Exception:
        pass


def find_python():
    if os.name == "nt":
        candidates = [
            os.path.join(SCRIPT_DIR, "venv_dictation", "Scripts", "pythonw.exe"),
            os.path.join(SCRIPT_DIR, "venv_dictation", "Scripts", "python.exe"),
            "python",
        ]
    else:
        candidates = [
            os.path.join(SCRIPT_DIR, "venv_dictation", "bin", "python"),
            "python3",
        ]
    for c in candidates:
        if c in ("python", "python3"):
            return c
        if os.path.exists(c):
            return c
    return candidates[-1]


def api(path, method="GET", body=None, timeout=5):
    r = requests.request(method, SERVER_URL + path, json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()


def ensure_server(model="small", device=None, idle_timeout=300):
    try:
        api("/api/status", timeout=2)
        return True
    except Exception:
        pass
    log = open(os.path.join(SCRIPT_DIR, "server.log"), "a", encoding="utf-8")
    args = [find_python(), "server.py", "--model", model, "--port", "8765",
            "--idle-timeout", str(idle_timeout)]
    if device is not None:
        args += ["--device", str(device)]
    flags = 0x08000000 if os.name == "nt" else 0
    subprocess.Popen(args, cwd=SCRIPT_DIR, stdout=log, stderr=log, creationflags=flags)
    for _ in range(60):
        time.sleep(2)
        try:
            api("/api/status", timeout=2)
            return True
        except Exception:
            pass
    return False


def register_autostart(enabled):
    script = os.path.join(SCRIPT_DIR, "global_dictation.py")
    python = find_python()
    try:
        if os.name == "nt":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            if enabled:
                winreg.SetValueEx(key, "VoiceDictation", 0, winreg.REG_SZ,
                                  '"%s" "%s"' % (python, script))
            else:
                try:
                    winreg.DeleteValue(key, "VoiceDictation")
                except OSError:
                    pass
            winreg.CloseKey(key)
        elif IS_MAC:
            d = os.path.expanduser("~/Library/LaunchAgents")
            os.makedirs(d, exist_ok=True)
            plist = os.path.join(d, "com.malts1933.voice-dictation.plist")
            if enabled:
                content = (
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0"><dict>\n'
                    "<key>Label</key><string>com.malts1933.voice-dictation</string>\n"
                    "<key>ProgramArguments</key><array>\n"
                    "<string>%s</string>\n<string>%s</string>\n</array>\n"
                    "<key>RunAtLoad</key><true/>\n"
                    "</dict></plist>\n" % (python, script)
                )
                with open(plist, "w", encoding="utf-8") as f:
                    f.write(content)
            elif os.path.exists(plist):
                os.remove(plist)
        else:
            d = os.path.join(os.path.expanduser("~"), ".config", "autostart")
            os.makedirs(d, exist_ok=True)
            desktop = os.path.join(d, "voice-dictation.desktop")
            if enabled:
                content = (
                    "[Desktop Entry]\nType=Application\nName=Voice Dictation\n"
                    "Exec=%s %s\nX-GNOME-Autostart-enabled=true\n" % (python, script)
                )
                with open(desktop, "w", encoding="utf-8") as f:
                    f.write(content)
            elif os.path.exists(desktop):
                os.remove(desktop)
        return True
    except Exception:
        return False


def vscode_focused():
    if not config.data.get("skip_in_vscode", True):
        return False
    try:
        if os.name == "nt":
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.lower()
        elif IS_MAC:
            out = subprocess.check_output(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first application process whose frontmost is true'],
                stderr=subprocess.DEVNULL, timeout=5)
            title = out.decode(errors="ignore").lower()
        else:
            return False
        return "visual studio code" in title or "antigravity" in title
    except Exception:
        return False


class Dictator:
    def __init__(self):
        self.lock = threading.Lock()
        self.recording = False
        self.hotkey_hold = False
        self.last_text = ""

    def start(self, via_hotkey=False):
        with self.lock:
            if self.recording:
                return
            if not ensure_server():
                show_status("server failed")
                return
            try:
                api("/api/language", "POST", {"language": config.data["language"]})
                api("/api/start", "POST")
                self.recording = True
                self.hotkey_hold = via_hotkey
                show_status("REC", recording=True)
            except Exception as e:
                show_status("error: %s" % e)

    def stop(self, paste=True):
        with self.lock:
            if not self.recording:
                return
            self.recording = False
            self.hotkey_hold = False
        show_status("")
        try:
            data = api("/api/stop", "POST")
        except Exception as e:
            show_status("error: %s" % e)
            return
        text = format_transcript(data.get("text", ""))
        if text and paste:
            self.last_text = text
            save_history(text)
            paste_text(text)

    def cancel(self):
        with self.lock:
            self.recording = False
            self.hotkey_hold = False
        try:
            api("/api/cancel", "POST")
        except Exception:
            pass
        show_status("")

    def toggle(self, via_hotkey=False):
        if self.recording:
            self.stop()
        else:
            self.start(via_hotkey=via_hotkey)


dictator = Dictator()


def paste_text(text):
    try:
        old = pyperclip.paste()
    except Exception:
        old = ""
    pyperclip.copy(text)
    time.sleep(0.15)
    kb = pynput.keyboard.Controller()
    mod = pynput.keyboard.Key.cmd if IS_MAC else pynput.keyboard.Key.ctrl
    with kb.pressed(mod):
        kb.press("v")
        kb.release("v")
    time.sleep(0.15)
    try:
        pyperclip.copy(old)
    except Exception:
        pass


def paste_last():
    if dictator.last_text:
        paste_text(dictator.last_text)


held = set()


def hotkey_keys():
    return [HOTKEY_KEYS.get(k, k) for k in config.data.get("hotkey", ["ctrl", "alt", "g"])]


def combo_held():
    return all(k in held for k in hotkey_keys())


def on_press(key):
    held.add(key)
    if key == pynput.keyboard.Key.esc and dictator.recording:
        dictator.cancel()
        return
    if (key == pynput.keyboard.Key.space
            and pynput.keyboard.Key.ctrl in held and pynput.keyboard.Key.alt in held
            and not dictator.recording and not combo_held()):
        paste_last()
        return
    if combo_held():
        if dictator.recording:
            dictator.stop()
        elif not vscode_focused():
            dictator.start(via_hotkey=True)
        return


def on_release(key):
    try:
        held.remove(key)
    except KeyError:
        pass
    if dictator.recording and dictator.hotkey_hold and not combo_held():
        dictator.stop()


class Widget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#111827")
        self.status_var = tk.StringVar(value="")
        self.drag_off = (0, 0)
        pos = config.data.get("widget")
        if pos:
            self.root.geometry("+%d+%d" % (pos[0], pos[1]))
        else:
            self.root.geometry("+80+80")
        self.build()

    def build(self):
        bar = tk.Frame(self.root, bg="#111827", padx=8, pady=6)
        bar.pack()
        bar.bind("<Button-1>", self.start_drag)
        bar.bind("<B1-Motion>", self.on_drag)
        mic = tk.Label(bar, text="🎤", bg="#111827", fg="white", font=("Segoe UI Emoji", 14), cursor="hand2")
        mic.pack(side="left", padx=(0, 6))
        mic.bind("<Button-1>", lambda e: dictator.toggle())
        self.dot = tk.Label(bar, text="○", bg="#111827", fg="#6b7280", font=("Segoe UI", 11))
        self.dot.pack(side="left")
        status = tk.Label(bar, textvariable=self.status_var, bg="#111827", fg="#9ca3af", font=("Segoe UI", 9))
        status.pack(side="left", padx=8)
        lang = tk.Label(bar, text=config.data.get("language", "auto").upper(), bg="#1f2937", fg="#d1d5db",
                        font=("Segoe UI", 8), padx=4, pady=1, cursor="hand2")
        lang.pack(side="left", padx=(0, 4))
        lang.bind("<Button-1>", self.cycle_language)
        close = tk.Label(bar, text="✕", bg="#111827", fg="#9ca3af", font=("Segoe UI", 11), cursor="hand2")
        close.pack(side="left")
        close.bind("<Button-1>", lambda e: self.hide())

    def cycle_language(self, e=None):
        langs = ["auto", "ru", "en"]
        cur = config.data.get("language", "auto")
        nxt = langs[(langs.index(cur) + 1) % len(langs)]
        config.data["language"] = nxt
        config.save()
        try:
            api("/api/language", "POST", {"language": nxt})
        except Exception:
            pass
        self.rebuild_label()

    def rebuild_label(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.build()

    def set_status(self, text, recording=False):
        self.status_var.set(text)
        self.dot.config(text="●" if recording else "○", fg="#ef4444" if recording else "#6b7280")
        self.root.update_idletasks()

    def start_drag(self, e):
        self.drag_off = (e.x, e.y)

    def on_drag(self, e):
        x = self.root.winfo_x() + e.x - self.drag_off[0]
        y = self.root.winfo_y() + e.y - self.drag_off[1]
        self.root.geometry("+%d+%d" % (x, y))

    def hide(self):
        config.data["widget"] = [self.root.winfo_x(), self.root.winfo_y()]
        config.save()
        self.root.withdraw()

    def show(self):
        self.root.deiconify()

    def run(self):
        self.root.mainloop()


widget = None
tray = None


def show_status(text, recording=False):
    if widget:
        widget.set_status(text, recording)
    if tray:
        try:
            tray.update_menu()
        except Exception:
            pass


def tray_menu():
    def make_lang(lang):
        def fn(icon, item):
            config.data["language"] = lang
            config.save()
            try:
                api("/api/language", "POST", {"language": lang})
            except Exception:
                pass
            icon.update_menu()

        return fn

    def record_label():
        return "Stop" if dictator.recording else "Record (Ctrl+Alt+G)"

    def on_record(icon, item):
        dictator.toggle()

    def on_autostart(icon, item):
        enabled = not config.data.get("autostart", False)
        config.data["autostart"] = enabled
        config.save()
        register_autostart(enabled)
        icon.update_menu()

    lang_items = [pystray.MenuItem(("● " if config.data.get("language") == l else "  ") + l,
                                   make_lang(l)) for l in ["auto", "ru", "en"]]
    items = [
        pystray.MenuItem(record_label, on_record, default=True),
        pystray.MenuItem("Paste last transcript (Ctrl+Alt+Space)", lambda i, it: paste_last()),
        pystray.MenuItem("📖 History", lambda i, it: open_history()),
        pystray.MenuItem("Language", pystray.Menu(lambda: [pystray.MenuItem(
            ("● " if config.data.get("language") == l else "  ") + l, make_lang(l)) for l in ["auto", "ru", "en"]])),
        pystray.MenuItem("Start at login", on_autostart,
                         checked=lambda item: config.data.get("autostart", False)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Show widget", lambda i, it: widget.show()),
        pystray.MenuItem("Hide widget", lambda i, it: widget.hide()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", lambda i, it: exit_app()),
    ]
    return pystray.Menu(*items)


def exit_app():
    if dictator.recording:
        dictator.cancel()
    if tray:
        tray.stop()
    if widget:
        widget.root.after(100, widget.root.destroy)


def main():
    parser = argparse.ArgumentParser(description="Global dictation widget (uses local whisper server)")
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", type=int, default=None)
    args = parser.parse_args()

    global widget, tray
    widget = Widget()
    tray = pystray.Icon("voice-dictation", Image.open(ICON_PATH), "Voice Dictation", tray_menu())

    threading.Thread(target=tray.run, daemon=True).start()

    def start_hotkeys():
        with pynput.keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

    threading.Thread(target=start_hotkeys, daemon=True).start()

    autostart = config.data.get("autostart", False)
    if autostart:
        register_autostart(True)
        widget.hide()
        threading.Thread(target=lambda: ensure_server(args.model, args.device, idle_timeout=0),
                         daemon=True).start()
    else:
        threading.Thread(target=lambda: ensure_server(args.model, args.device), daemon=True).start()
    widget.run()


if __name__ == "__main__":
    main()