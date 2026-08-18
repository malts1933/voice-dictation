# Changelog

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