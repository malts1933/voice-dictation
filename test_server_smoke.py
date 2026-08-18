import json
import subprocess
import sys
import time
import urllib.request

PORT = 8799
BASE = "http://127.0.0.1:%d" % PORT


def http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def main():
    log = open("server_smoke.log", "a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "server.py", "--port", str(PORT), "--idle-timeout", "30"],
                            stdout=log, stderr=log)
    try:
        ok = False
        for _ in range(60):
            time.sleep(2)
            try:
                st = http("GET", "/api/status")
                ok = True
                break
            except Exception:
                pass
        if not ok:
            print("FAIL: server did not start")
            sys.exit(1)
        print("status:", st)
        lang = http("POST", "/api/language", {"language": "ru"})
        print("language:", lang)
        st2 = http("GET", "/api/status")
        print("status after language:", st2)
        print("SMOKE OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()