# Changelog

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