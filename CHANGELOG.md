# Changelog

## [0.2.8] — 2026-08-19

### Changed
- Text structuring now uses a fast, reliable model by default: `nvidia/nemotron-3-super-120b-a12b` (per the SIN-Studio model rating) — with automatic fallback to `llama-3.3-nemotron-super-49b-v1`
- Stronger built-in structuring prompt: explicitly removes filler words («ну», «бля», «типа», «короче»…), keeps every real detail — verified live against the API
- Unstable/legacy models dropped from auto-fallback (gemini-2.5-flash, gemini-3.5-flash)

## [0.2.7] — 2026-08-19

### Added
- One shared environment for all apps (extension + global dictation + multiple editors) — never duplicated
- Old duplicated environments are removed automatically after the first successful restart from the shared one
- New command "Voice Dictation: Show environment info" — paths, disk usage, leftover copies (with one-click cleanup)

## [0.2.6] — 2026-08-19

### Added
- Fully automatic first-run setup: if Python is missing it gets installed (winget/brew/apt), a private hidden environment is created in the OS app-data folder, dependencies install themselves — zero manual steps
- Reuses an already working Python/dependencies if present — nothing is created when everything already exists
- Hidden environment is tamper-checked via a random nonce marker (env.id) — a swapped/hijacked interpreter is detected and re-created
- New command "Voice Dictation: Run first-time setup" for manual re-run
- Setup state stored in `%LOCALAPPDATA%/voice_dictation/env.json` (macOS/Linux: Application Support / .local/share)

## [0.2.5] — 2026-08-19

### Changed
- Removed machine-specific hardcoded paths from `extension.js` (privacy cleanup)

## [0.2.4] — 2026-08-19

### Fixed
- Idle auto-shutdown no longer fires right after a slow model load (timer starts when the server is actually ready) — fixes dictation dying on slow machines and on CI

## [0.2.3] — 2026-08-19

### Added
- **Sentence-structured dictation**: transcription is split into sentences — each on its own line
  - server splits on speech pauses (>0.9s) and sentence-ending punctuation (`--sentences` flag, on by default)
  - formatters (RU + EN) additionally split on `. ? ! …` and preserve server line breaks
- `voiceDictation.sentencesOnNewLine` setting (default `true`) to turn the line-per-sentence behavior off

## [0.2.2] — 2026-08-19

### Added
- **Self-healing**: a stuck/stale "recording" state is now auto-cancelled before every new dictation (extension and global app) — no more blocked dictations after a crash
- **Restart server** everywhere: tray menu item, `Voice Dictation: Restart server` command, `/api/shutdown` endpoint
- Server status is reset on connect if it was left mid-recording

## [0.2.1] — 2026-08-19

### Fixed
- Global hotkey `Ctrl+Alt+G`: letter keys (like `G`) are now tracked correctly — recording starts on the full combo, not on `Ctrl+Alt` alone
- Hotkey now also **stops** an ongoing recording (toggle behavior), including recordings started from the widget/tray
- Stuck "recording" state on the server no longer blocks new dictations (cancel/reset handled)

## [0.2.0] — 2026-08-19

### Added
- **Global dictation — anywhere on your computer** (`global_dictation.py`): press and hold `Ctrl+Alt+G`, speak, release — text is pasted into any app (browser, chat, documents, terminal)
- **Start at login**: tray toggle keeps the app + Whisper model in memory (instant dictation) via registry / LaunchAgent / autostart file
- **Hotkey changed to `Ctrl+Alt+G`** in the editor and terminal (extension and global app); `Ctrl+Alt+Space` now pastes the last transcript
- **Floating widget**: always-on-top mic bubble that can be hidden, closed and reopened; drag it anywhere, position is remembered
- **System tray app** with record/paste/language controls
- **History**: every dictation is saved with a timestamp to `dictation_history.md`, opened from the tray
- **Cross-platform**: same code runs on Windows, macOS and Linux; `Cmd`-based paste on Mac, `Super` hotkey support
- **CI**: GitHub Actions automatically tests the server, formatter and syntax on Windows, macOS and Linux
- `dictation_format.py`: formatter extracted into a shareable module with unit tests (`test_format.py`)

## [0.1.4] — 2026-08-19

### Added
- Server auto-shutdown: exits by itself after configurable idle time (`voiceDictation.serverIdleSeconds`, default 300s)

### Changed
- Server starts fully invisible (pythonw.exe, no console window)

## [0.1.3] — 2026-08-18

### Added
- Terminal dictation: speak into the integrated terminal (PowerShell, bash, cmd, REPL)
- `voiceDictation.toggleTerminal` command with `Ctrl+Alt+Space` when the terminal is focused

## [0.1.2] — 2026-08-18

### Fixed
- Python console window no longer appears when the server auto-starts (pythonw.exe)

## [0.1.1] — 2026-08-18

### Added
- Auto-start: the extension launches the local server itself when it is not running
- `voiceDictation.autoStartServer`, `voiceDictation.pythonPath`, `voiceDictation.model` settings
- Bundled `server.py` inside the extension package

## [0.1.0] — 2026-08-18

### Added
- Initial release: local faster-whisper dictation server + VS Code extension
- Editor dictation with `Ctrl+Alt+Space` toggle
- Voice commands (punctuation, new lines, deletions) in Russian and English
- Status bar recording indicator