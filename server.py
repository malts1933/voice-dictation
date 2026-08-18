import argparse
import os
import threading
import time

import numpy as np
import sounddevice as sd
from flask import Flask, jsonify, request
from faster_whisper import WhisperModel

app = Flask(__name__)

# Rough real-time factor used for the initial ETA estimate before the
# transcription actually starts measuring its own throughput
# (small model, int8, CPU is roughly 6x realtime).
INITIAL_RTF = 6.0

state = {
    "model": None,
    "model_name": "small",
    "language": "auto",
    "recording": False,
    "chunks": [],
    "stream": None,
    "lock": threading.Lock(),
    "last_active": time.time(),
    "idle_timeout": 300,
    "phase": "idle",
    "progress": 0.0,
    "eta_sec": None,
    "elapsed_sec": 0.0,
    "total_audio_sec": 0.0,
    "result": None,
}


@app.after_request
def touch(response):
    state["last_active"] = time.time()
    return response


def idle_watcher():
    while True:
        time.sleep(5)
        if state["idle_timeout"] <= 0:
            continue
        if state["recording"] or state["phase"] == "transcribing":
            continue
        if time.time() - state["last_active"] > state["idle_timeout"]:
            print("Idle timeout reached, shutting down.", flush=True)
            os._exit(0)


def audio_callback(indata, frames, time_info, status):
    if state["recording"]:
        state["chunks"].append(indata[:, 0].copy())


def transcribe_job(chunks, t0):
    audio = np.concatenate(chunks)
    language = None if state["language"] == "auto" else state["language"]
    segments, info = state["model"].transcribe(
        audio, language=language, vad_filter=True, without_timestamps=False
    )
    texts = []
    last_end = 0.0
    total = state["total_audio_sec"]
    for seg in segments:
        texts.append(seg.text)
        last_end = max(last_end, seg.end)
        with state["lock"]:
            state["progress"] = min(100.0, last_end / total * 100 if total else 100.0)
            state["elapsed_sec"] = time.time() - t0
            if state["progress"] > 0:
                state["eta_sec"] = (
                    state["elapsed_sec"] / state["progress"] * (100 - state["progress"])
                )
    text = "".join(texts).strip()
    with state["lock"]:
        if state["phase"] != "transcribing":
            return
        state["result"] = {"text": text, "language": info.language}
        state["phase"] = "done"
        state["progress"] = 100.0
        state["eta_sec"] = 0.0


@app.post("/api/start")
def start():
    with state["lock"]:
        if state["recording"]:
            return jsonify({"error": "already recording"}), 409
        if state["stream"] is None:
            try:
                state["stream"] = sd.InputStream(
                    samplerate=16000, channels=1, dtype="float32", callback=audio_callback
                )
                state["stream"].start()
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        state["chunks"] = []
        state["recording"] = True
        state["phase"] = "recording"
        state["progress"] = 0.0
        state["eta_sec"] = None
        state["elapsed_sec"] = 0.0
        state["total_audio_sec"] = 0.0
        state["result"] = None
    return jsonify({"recording": True})


@app.post("/api/stop")
def stop():
    with state["lock"]:
        if not state["recording"]:
            return jsonify({"text": "", "language": ""}), 200
        state["recording"] = False
        chunks = state["chunks"]
        state["chunks"] = []
        if not chunks:
            state["phase"] = "idle"
            return jsonify({"text": "", "language": ""}), 200
        total = sum(len(c) for c in chunks) / 16000.0
        state["total_audio_sec"] = total
        state["progress"] = 0.0
        state["elapsed_sec"] = 0.0
        state["eta_sec"] = total / INITIAL_RTF
        state["phase"] = "transcribing"
        state["result"] = None
        threading.Thread(
            target=transcribe_job, args=(chunks, time.time()), daemon=True
        ).start()
    return jsonify({"transcribing": True})


@app.post("/api/cancel")
def cancel():
    with state["lock"]:
        state["recording"] = False
        state["chunks"] = []
        state["phase"] = "idle"
        state["progress"] = 0.0
        state["eta_sec"] = None
        state["elapsed_sec"] = 0.0
        state["result"] = None
    return jsonify({"ok": True})


@app.get("/api/status")
def status():
    return jsonify(
        {
            "recording": state["recording"],
            "model": state["model_name"],
            "language": state["language"],
            "phase": state["phase"],
        }
    )


@app.get("/api/progress")
def progress():
    return jsonify(
        {
            "phase": state["phase"],
            "percent": round(state["progress"], 1),
            "elapsed": round(state["elapsed_sec"], 1),
            "eta": round(state["eta_sec"], 1) if state["eta_sec"] is not None else None,
            "total_audio": round(state["total_audio_sec"], 1),
            "text": state["result"]["text"] if state["result"] else None,
        }
    )


@app.get("/api/result")
def result():
    r = state["result"] or {"text": "", "language": ""}
    return jsonify(r)


@app.post("/api/language")
def set_language():
    data = request.get_json(force=True)
    lang = data.get("language", "auto")
    if lang not in ("auto", "ru", "en"):
        return jsonify({"error": "invalid language"}), 400
    state["language"] = lang
    return jsonify({"language": lang})


def main():
    parser = argparse.ArgumentParser(description="Local whisper dictation server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default="small",
                        help="whisper model size: tiny, base, small, medium, large-v3")
    parser.add_argument("--device", type=int, default=None, help="input device index")
    parser.add_argument("--language", default="auto", choices=["auto", "ru", "en"])
    parser.add_argument("--cpu-threads", type=int, default=4)
    parser.add_argument("--idle-timeout", type=int, default=300,
                        help="exit automatically after this many seconds without requests (0 = never)")
    args = parser.parse_args()

    state["model_name"] = args.model
    state["language"] = args.language
    state["idle_timeout"] = args.idle_timeout

    print("Available input devices:")
    print(sd.query_devices())
    if args.device is not None:
        sd.default.device = (args.device, None)

    print(f"Loading whisper model '{args.model}' (first run downloads it)...")
    state["model"] = WhisperModel(
        args.model, device="cpu", compute_type="int8", cpu_threads=args.cpu_threads
    )
    print("Model loaded. Server ready on http://%s:%d" % (args.host, args.port))
    if args.idle_timeout > 0:
        threading.Thread(target=idle_watcher, daemon=True).start()
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()