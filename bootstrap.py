import json
import os
import secrets
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"


def env_root():
    if IS_WIN:
        base = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local")
    elif IS_MAC:
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "voice_dictation")


def env_json_path():
    return os.path.join(env_root(), "env.json")


def managed_env_dir():
    return os.path.join(env_root(), "env")


def managed_python():
    if IS_WIN:
        return os.path.join(managed_env_dir(), "Scripts", "python.exe")
    return os.path.join(managed_env_dir(), "bin", "python")


def log(msg):
    print("[setup] " + msg, flush=True)


def run(args, timeout=300):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return 1, str(e)


def deps_ok(python):
    check = ("import faster_whisper, flask, sounddevice, pystray, "
             "pynput, pyperclip, requests, PIL; print(1)")
    rc, _ = run([python, "-c", check], timeout=60)
    return rc == 0


def find_system_python():
    cands = []
    if sys.executable:
        cands.append(sys.executable)
    if IS_WIN:
        cands += ["py", "-3", "python"]
    else:
        cands += ["python3", "python"]
    for c in cands:
        if c in ("python3", "python"):
            if shutil.which(c):
                return c
            continue
        rc, _ = run([c] + (["-3"] if c == "py" else []) + ["-c", "print(1)"], timeout=15)
        if rc == 0:
            return c
    return None


def install_python():
    if IS_WIN:
        log("No Python found, installing via winget...")
        rc, out = run(["winget", "install", "-e", "--id", "Python.Python.3.11",
                       "--silent", "--accept-package-agreements",
                       "--accept-source-agreements"], timeout=600)
        if rc != 0:
            log("winget failed: " + out.strip()[-300:])
            return None
        for c in (["py", "-3", "-c", "print(1)"], ["python", "-c", "print(1)"]):
            rc, _ = run(c, timeout=30)
            if rc == 0:
                return c[0] + (" -3" if c[0] == "py" else "")
        return None
    if IS_MAC:
        if shutil.which("brew"):
            log("No Python found, installing via Homebrew...")
            rc, out = run(["brew", "install", "--quiet", "python@3.11"], timeout=900)
            if rc != 0:
                log("brew failed: " + out.strip()[-300:])
            return find_system_python()
        log("No Python and no Homebrew. Install Python 3.11 from python.org, then retry.")
        return None
    if shutil.which("apt-get"):
        log("No Python found, installing via apt...")
        rc, out = run(["sudo", "-n", "apt-get", "install", "-y",
                       "python3", "python3-venv", "python3-pip"], timeout=600)
        if rc != 0:
            log("apt failed: " + out.strip()[-300:])
        return find_system_python()
    log("No Python found. Install Python 3.11 manually, then retry.")
    return None


def reuse_candidates(prefer):
    cands = []
    if prefer:
        cands.append(prefer)
    legacy = os.path.join(SCRIPT_DIR, "venv_dictation")
    if IS_WIN:
        cands.append(os.path.join(legacy, "Scripts", "pythonw.exe"))
        cands.append(os.path.join(legacy, "Scripts", "python.exe"))
    else:
        cands.append(os.path.join(legacy, "bin", "python"))
    for c in cands:
        if c and os.path.exists(c) and deps_ok(c):
            return c
    return None


def write_env_json(python, mode):
    nonce = None
    if mode == "managed":
        nonce = secrets.token_hex(16)
        with open(os.path.join(managed_env_dir(), "env.id"), "w", encoding="utf-8") as f:
            f.write(nonce)
    os.makedirs(env_root(), exist_ok=True)
    data = {"root": env_root(), "python": python, "mode": mode, "nonce": nonce}
    with open(env_json_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    if IS_WIN:
        try:
            subprocess.run(["attrib", "+h", env_root()], capture_output=True, timeout=30)
        except Exception:
            pass


def create_managed_env(base):
    log("Creating private environment (hidden)...")
    rc, out = run([base, "-m", "venv", managed_env_dir()], timeout=300)
    if rc != 0:
        print("BOOTSTRAP_FAIL venv: " + out.strip()[-300:])
        return None
    if IS_WIN:
        if not os.path.exists(managed_python().replace("python.exe", "pythonw.exe")):
            base_dir = os.path.dirname(os.path.abspath(base))
            base_w = os.path.join(base_dir, "pythonw.exe")
            if os.path.exists(base_w):
                try:
                    shutil.copy(base_w, os.path.join(managed_env_dir(), "Scripts", "pythonw.exe"))
                except Exception:
                    pass
        try:
            subprocess.run(["attrib", "+h", env_root()], capture_output=True, timeout=30)
        except Exception:
            pass
    return managed_python()


def dir_size(path):
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except Exception:
                    pass
    except Exception:
        pass
    return total


def legacy_env():
    return os.path.join(SCRIPT_DIR, "venv_dictation")


def report():
    out = {"env_root": env_root(), "mode": None, "python": None,
           "env_size_mb": round(dir_size(env_root()) / 1048576),
           "legacy": [], "hf_cache_mb": 0}
    try:
        with open(env_json_path(), encoding="utf-8") as f:
            j = json.load(f)
        out["mode"] = j.get("mode")
        out["python"] = j.get("python")
    except Exception:
        pass
    if os.path.exists(legacy_env()):
        out["legacy"].append({"path": legacy_env(),
                              "size_mb": round(dir_size(legacy_env()) / 1048576)})
    old = os.path.join(os.path.expanduser("~"), ".voice-dictation")
    if os.path.exists(old):
        out["legacy"].append({"path": old,
                              "size_mb": round(dir_size(old) / 1048576)})
    hf = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    if os.path.exists(hf):
        out["hf_cache_mb"] = round(dir_size(hf) / 1048576)
    print(json.dumps(out, indent=2))
    return 0


def cleanup_legacy():
    removed = []
    for p in (legacy_env(), os.path.join(os.path.expanduser("~"), ".voice-dictation")):
        if not os.path.exists(p):
            continue
        try:
            shutil.rmtree(p, ignore_errors=True)
            status = "removed" if not os.path.exists(p) else "partial (files in use)"
        except Exception as e:
            status = "error: %s" % e
        removed.append({"path": p, "status": status})
    print(json.dumps(removed, indent=2))
    return 0


def main():
    if "--report" in sys.argv:
        return report()
    if "--cleanup-legacy" in sys.argv:
        return cleanup_legacy()
    prefer = None
    if "--prefer" in sys.argv:
        prefer = sys.argv[sys.argv.index("--prefer") + 1]
    req = None
    if "--requirements" in sys.argv:
        req = sys.argv[sys.argv.index("--requirements") + 1]
    if not req:
        req = os.path.join(SCRIPT_DIR, "requirements.txt")

    reused = reuse_candidates(prefer)
    if reused:
        write_env_json(reused, "existing")
        print("BOOTSTRAP_OK " + reused)
        return 0

    py = managed_python()
    if os.path.exists(py) and deps_ok(py):
        write_env_json(py, "managed")
        print("BOOTSTRAP_OK " + py)
        return 0

    if not os.path.exists(py):
        base = find_system_python()
        if not base:
            base = install_python()
        if not base:
            print("BOOTSTRAP_FAIL no python available")
            return 1
        py = create_managed_env(base)
        if not py:
            return 1

    log("Installing dependencies (first run only, may take a few minutes)...")
    rc, out = run([py, "-m", "pip", "install", "--disable-pip-version-check",
                   "--quiet", "-r", req], timeout=900)
    if rc != 0:
        print("BOOTSTRAP_FAIL pip: " + out.strip()[-500:])
        return 1

    if deps_ok(py):
        write_env_json(py, "managed")
        print("BOOTSTRAP_OK " + py)
        return 0
    print("BOOTSTRAP_FAIL imports broken")
    return 1


if __name__ == "__main__":
    sys.exit(main())