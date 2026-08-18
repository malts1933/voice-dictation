# Voice Dictation — Local Whisper

Press a key, speak, text appears. **100% free, private, on-device speech-to-text** for VS Code and Antigravity — powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

No cloud. No API keys. No accounts. Your voice never leaves your computer.

![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Local](https://img.shields.io/badge/privacy-100%25%20local-orange)
![Version](https://img.shields.io/badge/version-0.1.4-purple)

---

## Why this extension?

Most dictation tools send your audio to a cloud service. **This one doesn't.** It runs a tiny local server on your machine that transcribes your speech with Whisper, right on your CPU. Dictate documents, commit messages, prompts, or terminal commands — without a single byte leaving your computer.

**Install it once, forget about it.** The server starts itself in the background the first time you press the hotkey, and shuts itself down when you're done. All you do is press a key and talk.

## How it works

```
1. Press Ctrl+Alt+Space   →  recording starts (red ● REC in the status bar)
2. Speak                  →  audio is transcribed locally by Whisper
3. Press Ctrl+Alt+Space   →  text appears right where your cursor is
```

Works in **any text document** (markdown, code, notes...) and in the **integrated terminal** — focus the terminal, press the same key, and your words are typed straight into the console.

## Features

- 🎙️ **Push-to-talk toggle** — record only while you want, nothing is listened to otherwise
- 🏠 **100% local & private** — faster-whisper runs on your machine, no cloud, no API key
- 🖥️ **Zero-click server** — auto-starts in the background (invisible, no windows), auto-exits after inactivity
- ⌨️ **Voice commands** — say "comma", "new line", "delete last word", "capitalize" and more (RU + EN)
- 🌐 **Russian + English** — auto-detection or explicit language selection
- 💻 **Terminal dictation** — dictate straight into PowerShell, bash, cmd, or any REPL
- 🔌 **Works in Antigravity** — it's a VS Code fork, so the same VSIX installs there too
- 📦 **No dependencies to install** — Python environment with Whisper included in the setup flow

## Voice commands

Say these while dictating — they become formatting in real time:

| You say | Result |
| --- | --- |
| «запятая» / «comma» | `,` |
| «точка» / «period» | `.` |
| «вопросительный знак» / «question mark» | `?` |
| «восклицательный знак» / «exclamation mark» | `!` |
| «двоеточие» / «colon» | `:` |
| «точка с запятой» / «semicolon» | `;` |
| «тире» / «dash» | `—` |
| «новая строка» / «new line» | line break |
| «новый абзац» / «new paragraph» | paragraph break |
| «большая буква» / «capitalize» | next word capitalized |
| «удали последнее слово» / «delete last word» | removes last word |
| «удали последнее предложение» / «delete last sentence» | removes last sentence |
| «кавычки», «скобки», «многоточие» | `"`, `()`, `...` |

## Installation

### Prerequisites

- Windows 10/11 (Linux & macOS work too, tested on Windows)
- [Python 3.10+](https://www.python.org/downloads/)
- A microphone

### 1. Set up the Python environment (one time)

```bat
cd voice-dictation
python -m venv venv_dictation
venv_dictation\Scripts\python -m pip install -r requirements.txt
```

> The first dictation downloads the Whisper model (~460 MB, one time). The extension auto-detects the environment; you can also point it to any Python with the `voiceDictation.pythonPath` setting.

### 2. Install the extension

Grab the latest `voice-dictation-*.vsix` from [Releases](https://github.com/malts1933/voice-dictation/releases), then:

**VS Code:** Extensions panel → `⋯` menu → **Install from VSIX...**

**Antigravity:** same flow — Extensions panel → **Install from VSIX...** (Antigravity is a VS Code fork and accepts VSIX files directly).

### 3. Start dictating

Open any file (or a terminal), press **`Ctrl+Alt+Space`**, speak, press **`Ctrl+Alt+Space`** again. Done.

`Esc` while recording cancels without inserting anything.

## Configuration

| Setting | Default | Description |
| --- | --- | --- |
| `voiceDictation.language` | `auto` | Recognition language: `auto`, `ru`, `en` |
| `voiceDictation.model` | `small` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `voiceDictation.serverIdleSeconds` | `300` | Server auto-exits after this many idle seconds (`0` = never) |
| `voiceDictation.autoStartServer` | `true` | Start the local server automatically when needed |
| `voiceDictation.pythonPath` | *(auto)* | Custom Python interpreter path with faster-whisper |
| `voiceDictation.addTrailingSpace` | `true` | Append a space after inserted text |

### Model size vs. accuracy

| Model | Size | Russian quality | Speed (CPU) |
| --- | --- | --- | --- |
| `tiny` | 75 MB | poor | instant |
| `base` | 140 MB | ok | fast |
| `small` | 460 MB | good **(recommended)** | ~1s per phrase |
| `medium` | 1.5 GB | very good | ~3s per phrase |
| `large-v3` | 3 GB | best | slow |

## How it works under the hood

```
┌────────────────────┐   HTTP (localhost:8765)   ┌──────────────────────┐
│  VS Code extension │ ◄────────────────────────► │  server.py (Python) │
│  - hotkeys/status  │    /api/start, /api/stop   │  - records mic      │
│  - inserts text    │                            │  - faster-whisper   │
│  - voice commands  │                            │  - auto-shutdown    │
└────────────────────┘                            └──────────────────────┘
```

The extension is a thin client: it tells the server when to record, the server transcribes with Whisper locally, and the extension formats the result (voice commands → punctuation) and inserts it at your cursor. The server starts on demand in the background, with **no console window**, and exits by itself after 5 minutes of inactivity.

## Troubleshooting

- **"Failed to start dictation server"** — check `voiceDictation.pythonPath` points to a Python with `faster-whisper` installed, and look at `server.log` next to the extension.
- **Hotkey does nothing in Antigravity** — some AI keybindings conflict. Use the Command Palette (`Ctrl+Shift+P` → *Voice Dictation: Dictate into terminal*) or rebind via `Ctrl+K Ctrl+S`.
- **Wrong microphone** — the server uses the system default input device; change it in Windows Sound settings or pass `--device N` to `server.py`.
- **First dictation is slow** — the model is being downloaded/loaded. Subsequent ones are fast.

## Roadmap

- [ ] Hold-to-talk (record while key is held)
- [ ] Streaming partial results while you speak
- [ ] Custom vocabulary (technical terms, names)
- [ ] Multi-language voice commands
- [ ] macOS / Linux packaging

## Contributing

Issues and PRs are welcome! See [CONTRIBUTING](CONTRIBUTING.md) — or just open an issue with your idea.

## License

[MIT](LICENSE) © 2026 [malts1933](https://github.com/malts1933)