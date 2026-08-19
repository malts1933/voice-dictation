'use strict';

const vscode = require('vscode');
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { formatTranscript } = require('./format');

const SPIN = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

const DEFAULT_STRUCTURE_PROMPT =
  'Ты — редактор текста. Удали ВСЕ слова-паразиты и заполнители: «ну», «бля», «типа», ' +
  '«короче», «это самое», «как его там», «вот», «в общем», «так сказать», «понимаешь» и подобные. ' +
  'Сохрани КАЖДУЮ реальную мысль, факт и деталь из исходного текста. Исправь пунктуацию, ' +
  'опечатки и согласование. Структурируй текст знаками препинания (запятые, точки, тире, скобки), ' +
  'но НЕ используй переносы строк, абзацы и списки с новой строки — весь результат должен быть ' +
  'ОДНОЙ строкой. Сохрани язык оригинала. Верни ТОЛЬКО готовый структурированный текст ' +
  'без вступлений, пояснений и кавычек.';

let statusBarItem;
let recording = false;
let transcribing = false;
let abortTranscription = false;
let recStartTime = 0;
let blinkTimer = null;
let elapsedTimer = null;
let blinkOn = false;
let activeBadge = 'none';
let spinIdx = 0;
let serverStarting = false;

const DECOR = {};

function cfg() {
  return vscode.workspace.getConfiguration('voiceDictation');
}

function serverUrl() {
  return cfg().get('serverUrl', 'http://127.0.0.1:8765');
}

function homeDir() {
  return process.env.HOME || process.env.USERPROFILE || '';
}

function appDataDir() {
  if (process.platform === 'win32') {
    return path.join(process.env.LOCALAPPDATA || path.join(homeDir(), 'AppData', 'Local'), 'voice_dictation');
  }
  if (process.platform === 'darwin') {
    return path.join(homeDir(), 'Library', 'Application Support', 'voice_dictation');
  }
  return path.join(process.env.XDG_DATA_HOME || path.join(homeDir(), '.local', 'share'), 'voice_dictation');
}

function envPython() {
  try {
    const j = JSON.parse(fs.readFileSync(path.join(appDataDir(), 'env.json'), 'utf8'));
    if (!j.python || !fs.existsSync(j.python)) return null;
    if (j.mode === 'managed') {
      if (!j.nonce) return null;
      const marker = path.join(j.root || appDataDir(), 'env', 'env.id');
      let got = '';
      try {
        got = fs.readFileSync(marker, 'utf8').trim();
      } catch {
        return null;
      }
      if (got !== j.nonce) return null;
    }
    return j.python;
  } catch {
    return null;
  }
}

function findPython() {
  const fromCfg = (cfg().get('pythonPath', '') || '').trim();
  let base = fromCfg || envPython() || 'python';
  if (!fs.existsSync(base)) base = 'python';
  const dir = path.dirname(base);
  for (const n of ['pythonw.exe', 'python3w.exe']) {
    const candidate = path.join(dir, n);
    if (fs.existsSync(candidate)) return candidate;
  }
  return base;
}

function startServerProcess() {
  if (envPython()) cleanupLegacy();
  const py = findPython();
  const script = path.join(__dirname, 'server.py');
  const logFile = fs.openSync(path.join(__dirname, 'server.log'), 'a');
  const args = [
    'server.py',
    '--model', cfg().get('model', 'small'),
    '--port', '8765',
    '--idle-timeout', String(cfg().get('serverIdleSeconds', 0)),
    '--sentences', cfg().get('sentencesOnNewLine', true) ? '1' : '0',
  ];
  const proc = spawn(py, args, { cwd: __dirname, detached: true, stdio: ['ignore', logFile, logFile], windowsHide: true });
  proc.unref();
}

function api(path, method, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(serverUrl() + path);
    const payload = body ? JSON.stringify(body) : null;
    const req = http.request(
      {
        hostname: url.hostname,
        port: url.port,
        path: url.pathname,
        method: method || 'GET',
        headers: payload ? { 'Content-Type': 'application/json' } : {},
      },
      res => {
        let data = '';
        res.on('data', chunk => (data += chunk));
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            reject(new Error('Invalid response from server'));
          }
        });
      }
    );
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

function fmtSec(s) {
  s = Math.max(0, Math.round(s));
  const m = Math.floor(s / 60);
  return m + ':' + String(s % 60).padStart(2, '0');
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function toOneLine(t) {
  return t
    .split(/\r?\n/)
    .map(s => s.trim())
    .join(' ')
    .replace(/ {2,}/g, ' ');
}

function readApiKeys() {
  const keys = { gemini: [], nvidia: [] };
  const fromCfg = (cfg().get('apiKeyFile', '') || '').trim();
  const paths = [];
  if (fromCfg) paths.push(fromCfg);
  paths.push(path.join(__dirname, 'api_key.txt'));
  for (const p of paths) {
    try {
      const content = fs.readFileSync(p, 'utf8');
      for (const line of content.split(/\r?\n/)) {
        const k = line.trim();
        if (k.startsWith('AIza') || k.startsWith('AQ.')) keys.gemini.push(k);
        else if (k.startsWith('nvapi-')) keys.nvidia.push(k);
      }
    } catch {
      /* no keys file at this path */
    }
  }
  return keys;
}

function httpsPostJson(url, headers, body, timeoutMs) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const payload = JSON.stringify(body);
    const req = https.request(
      {
        hostname: u.hostname,
        path: u.pathname + u.search,
        method: 'POST',
        headers: Object.assign({}, headers, { 'Content-Length': Buffer.byteLength(payload) }),
      },
      res => {
        let data = '';
        res.on('data', c => (data += c));
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            reject(new Error('Invalid JSON from LLM'));
          }
        });
      }
    );
    req.setTimeout(timeoutMs || 60000, () => req.destroy(new Error('LLM timeout')));
    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

function callLLM(provider, model, key, userMsg) {
  if (provider === 'gemini') {
    return httpsPostJson(
      'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent?key=' + key,
      { 'Content-Type': 'application/json' },
      {
        contents: [{ parts: [{ text: userMsg }] }],
        generationConfig: { temperature: 0.2, maxOutputTokens: 4096 },
      },
      20000
    ).then(data => {
      const parts = ((data.candidates || [{}])[0].content || {}).parts || [];
      return parts.map(p => p.text || '').join('').trim();
    });
  }
  return httpsPostJson(
    'https://integrate.api.nvidia.com/v1/chat/completions',
    { 'Content-Type': 'application/json', Authorization: 'Bearer ' + key },
    {
      model: model,
      messages: [{ role: 'user', content: userMsg }],
      temperature: 0.2,
      max_tokens: 4096,
    },
    20000
  ).then(data => {
    const out = ((data.choices || [{}])[0].message || {}).content || '';
    return out.trim();
  });
}

async function structureWithLLM(text) {
  const configured = cfg().get('structureModel', 'nvidia/nemotron-3-super-120b-a12b');
  const prompt = cfg().get('structurePrompt', '') || DEFAULT_STRUCTURE_PROMPT;
  const keys = readApiKeys();
  const userMsg = prompt + '\n\nТЕКСТ ДЛЯ СТРУКТУРИРОВАНИЯ:\n' + text;
  const targets = [];
  const seen = new Set();
  const add = (model, provider) => {
    const id = provider + '|' + model;
    if (seen.has(id)) return;
    seen.add(id);
    targets.push({ model, provider });
  };
  add(configured, configured.startsWith('gemini-') ? 'gemini' : 'nvidia');
  add('nvidia/nemotron-3-super-120b-a12b', 'nvidia');
  add('nvidia/llama-3.3-nemotron-super-49b-v1', 'nvidia');
  for (const t of targets) {
    const pool = t.provider === 'gemini' ? keys.gemini : keys.nvidia;
    for (const k of pool) {
      try {
        const out = await callLLM(t.provider, t.model, k, userMsg);
        if (out) return out;
      } catch (e) {
        console.error('LLM attempt failed (' + t.provider + '/' + t.model + '):', e.message);
      }
    }
  }
  return null;
}

function makeDecor(color, text) {
  return vscode.window.createTextEditorDecorationType({
    after: {
      contentText: text || '',
      color: color,
      fontWeight: 'bold',
      margin: '0 0 0 0.4em',
    },
  });
}

const badgeEditors = new Set();

function clearAllBadges() {
  for (const ed of badgeEditors) {
    for (const k of ['recOn', 'recOff', 'busy']) ed.setDecorations(DECOR[k], []);
  }
  badgeEditors.clear();
  for (const ed of vscode.window.visibleTextEditors) {
    for (const k of ['recOn', 'recOff', 'busy']) ed.setDecorations(DECOR[k], []);
  }
}

function applyBadge(kind, text) {
  const ed = vscode.window.activeTextEditor;
  if (kind === 'none') {
    if (activeBadge !== 'none') {
      clearAllBadges();
      activeBadge = 'none';
    }
    return;
  }
  if (!ed) return;
  if (activeBadge !== kind) {
    clearAllBadges();
    activeBadge = kind;
  }
  badgeEditors.add(ed);
  const pos = ed.selection.active;
  const opt = { range: new vscode.Range(pos, pos) };
  if (text !== undefined) {
    opt.renderOptions = { after: { contentText: text } };
  }
  ed.setDecorations(DECOR[kind], [opt]);
}

function tickBlink() {
  blinkOn = !blinkOn;
  applyBadge(blinkOn ? 'recOn' : 'recOff');
}

function startBlink() {
  stopBlink();
  blinkOn = true;
  tickBlink();
  blinkTimer = setInterval(tickBlink, 600);
}

function stopBlink() {
  if (blinkTimer) clearInterval(blinkTimer);
  blinkTimer = null;
}

function updateStatusBar() {
  if (!statusBarItem) return;
  if (recording) {
    const s = Math.round((Date.now() - recStartTime) / 1000);
    statusBarItem.text = '$(circle-filled) ' + SPIN[spinIdx % SPIN.length] + ' REC ' + fmtSec(s);
    statusBarItem.tooltip = 'Voice dictation is recording. Press Ctrl+Alt+Space (or Ctrl+Alt+G) to stop.';
    statusBarItem.color = new vscode.ThemeColor('charts.red');
  } else {
    statusBarItem.text = '$(mic) Dictate';
    statusBarItem.tooltip = 'Voice dictation (Ctrl+Alt+Space / Ctrl+Alt+G)';
    statusBarItem.color = undefined;
  }
}

function runBootstrapArgs(extra) {
  return new Promise((resolve, reject) => {
    const bp = path.join(__dirname, 'bootstrap.py');
    const args = [bp].concat(extra);
    const proc = spawn('python', args, { cwd: __dirname, windowsHide: true });
    let out = '';
    proc.stdout.on('data', d => (out += d));
    proc.stderr.on('data', d => (out += d));
    const timer = setTimeout(() => {
      proc.kill();
      reject(new Error('bootstrap timed out'));
    }, 15 * 60 * 1000);
    proc.on('close', code => {
      clearTimeout(timer);
      if (code === 0) resolve(out);
      else reject(new Error('bootstrap failed:\n' + out.split('\n').slice(-12).join('\n')));
    });
    proc.on('error', err => {
      clearTimeout(timer);
      reject(new Error('Could not run bootstrap: ' + err.message));
    });
  });
}

function runBootstrap(bootstrapPy) {
  return runBootstrapArgs(['--requirements', path.join(__dirname, 'requirements.txt')]);
}

function cleanupLegacy() {
  return runBootstrapArgs(['--cleanup-legacy']).catch(() => {});
}

function serverLogTail() {
  try {
    const log = fs.readFileSync(path.join(__dirname, 'server.log'), 'utf8');
    const lines = log.split(/\r?\n/).filter(Boolean);
    return lines.slice(-15).join('\n');
  } catch {
    return '(no server.log yet)';
  }
}

async function ensureServer() {
  try {
    await api('/api/status');
    return false;
  } catch {
    /* server offline */
  }
  if (!cfg().get('autoStartServer', true)) {
    vscode.window.showErrorMessage(
      'Voice dictation server is offline. Start it with start_dictation_server.bat'
    );
    throw new Error('server offline');
  }
if (!serverStarting) {
    serverStarting = true;
    statusBarItem.text = '$(sync~spin) Starting server...';
    const fromCfg = (cfg().get('pythonPath', '') || '').trim();
    if (!fromCfg && !envPython()) {
      statusBarItem.text = '$(sync~spin) First-time setup...';
      try {
        await runBootstrap('python');
      } catch (e) {
        serverStarting = false;
        updateStatusBar();
        vscode.window.showErrorMessage(e.message);
        throw e;
      }
    }
    startServerProcess();
  }

  for (let i = 0; i < 900; i++) {
    await sleep(500);
    try {
      await api('/api/status');
      serverStarting = false;
      updateStatusBar();
      return true;
    } catch {
      if (i === 60) statusBarItem.text = '$(sync~spin) Loading model...';
      /* still loading */
    }
  }
  serverStarting = false;
  updateStatusBar();
  vscode.window.showErrorMessage(
    'Failed to start dictation server. Check voiceDictation.pythonPath setting and server.log.\n' +
      serverLogTail()
  );
  throw new Error('server start failed');
}

function warmUpServer() {
  setTimeout(async () => {
    try {
      const st = await api('/api/status');
      if (st && st.model) return;
    } catch {
      /* offline — start it in background so dictation is instant later */
    }
    if (!cfg().get('autoStartServer', true)) return;
    if (!serverStarting) {
      serverStarting = true;
      startServerProcess();
    }
  }, 1500);
}

async function startRecording() {
  await ensureServer();
  const lang = cfg().get('language', 'auto');
  try {
    await api('/api/language', 'POST', { language: lang });
    try {
      await api('/api/start', 'POST');
    } catch (e) {
      if (/already recording|409/.test(String(e.message))) {
        await api('/api/cancel', 'POST');
        await api('/api/start', 'POST');
      } else {
        throw e;
      }
    }
  } catch (e) {
    vscode.window.showErrorMessage('Failed to start recording: ' + e.message);
    return;
  }
  recording = true;
  abortTranscription = false;
  recStartTime = Date.now();
  vscode.commands.executeCommand('setContext', 'voiceDictation.recording', true);
  updateStatusBar();
  if (cfg().get('cursorIndicator', true)) startBlink();
  elapsedTimer = setInterval(() => {
    spinIdx++;
    updateStatusBar();
  }, 300);
  vscode.window.showInformationMessage('Dictation: recording... (Ctrl+Alt+Space to stop, Esc to cancel)');
}

async function waitForResult() {
  transcribing = true;
  abortTranscription = false;
  vscode.commands.executeCommand('setContext', 'voiceDictation.transcribing', true);
  const deadline = Date.now() + 5 * 60 * 1000;
  let spin = 0;
  try {
    for (;;) {
      if (abortTranscription) return { cancelled: true };
      if (Date.now() > deadline) return { error: 'transcription timed out' };
      let p;
      try {
        p = await api('/api/progress');
      } catch {
        await sleep(250);
        continue;
      }
      spin = (spin + 1) % SPIN.length;
      if (p.phase === 'transcribing') {
        const pct = Math.round(p.percent || 0);
        const eta = p.eta != null ? ' · ~' + fmtSec(p.eta) : '';
        statusBarItem.text = '$(loading~spin) ' + SPIN[spin] + ' ' + pct + '%' + eta;
        statusBarItem.tooltip =
          'Transcribing... audio ' + fmtSec(p.total_audio || 0) + ', ' + pct + '%, ETA ' + fmtSec(p.eta || 0);
        statusBarItem.color = new vscode.ThemeColor('charts.blue');
        if (cfg().get('cursorIndicator', true)) applyBadge('busy', ' ' + SPIN[spin] + ' ' + pct + '%');
      } else if (p.phase === 'done') {
        const r = await api('/api/result');
        return { text: r.text, language: r.language };
      } else if (p.phase === 'idle') {
        return { text: '', language: '' };
      }
      await sleep(250);
    }
  } finally {
    transcribing = false;
    vscode.commands.executeCommand('setContext', 'voiceDictation.transcribing', false);
    applyBadge('none');
    updateStatusBar();
  }
}

async function insertIntoEditor(text, deleteWord, deleteSentence) {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    const term = vscode.window.activeTerminal;
    if (term && text) {
      term.sendText(toOneLine(text), false);
      vscode.window.showInformationMessage('No text editor open — inserted into terminal.');
      return;
    }
    if (text) {
      await vscode.env.clipboard.writeText(toOneLine(text));
      vscode.window.showWarningMessage('No text editor open — text copied to clipboard (one line).');
      return;
    }
    vscode.window.showWarningMessage('No text editor open and no speech detected.');
    return;
  }

  const doc = editor.document;
  const pos = editor.selection.active;

  if (deleteWord || deleteSentence) {
    const count = deleteWord || deleteSentence;
    const ranges = [];
    let line = pos.line;
    let char = pos.character;
    for (let n = 0; n < count; n++) {
      const lineText = doc.lineAt(line).text;
      let end = char;
      while (end > 0 && /\s/.test(lineText[end - 1])) end--;
      let start = end;
      while (start > 0 && !/\s/.test(lineText[start - 1])) start--;
      if (start === end) {
        if (line > 0) {
          line--;
          char = doc.lineAt(line).text.length;
          n--;
          continue;
        }
        break;
      }
      ranges.push(new vscode.Range(line, start, line, end));
      char = start;
    }
    if (ranges.length) {
      await editor.edit(builder => {
        for (const r of ranges) builder.delete(r);
      });
    }
  }

  if (text) {
    let insert = text;
    const start = editor.selection.isEmpty ? pos : editor.selection.start;
    const end = editor.selection.isEmpty ? pos : editor.selection.end;
    const before = doc.getText(new vscode.Range(doc.positionAt(0), start)).slice(-1);
    if (insert && before && !/\s/.test(before) && !/^\s/.test(insert)) {
      insert = ' ' + insert;
    }
    if (cfg().get('addTrailingSpace', true) && !insert.endsWith('\n')) {
      insert += ' ';
    }
    await editor.edit(builder => {
      if (!editor.selection.isEmpty) builder.delete(editor.selection);
      builder.insert(end, insert);
    });
    vscode.window.showInformationMessage('Inserted ' + text.length + ' chars at cursor.');
  }
}

async function stopToTarget(target) {
  let data;
  try {
    data = await api('/api/stop', 'POST');
  } catch (e) {
    recording = false;
    stopBlink();
    if (elapsedTimer) clearInterval(elapsedTimer);
    vscode.commands.executeCommand('setContext', 'voiceDictation.recording', false);
    applyBadge('none');
    updateStatusBar();
    vscode.window.showErrorMessage('Failed to stop recording: ' + e.message);
    return;
  }
  recording = false;
  stopBlink();
  if (elapsedTimer) clearInterval(elapsedTimer);
  vscode.commands.executeCommand('setContext', 'voiceDictation.recording', false);
  updateStatusBar();

  if (!data.transcribing) return;

  const result = await waitForResult();
  if (result.cancelled) {
    vscode.window.showInformationMessage('Dictation cancelled.');
    return;
  }
  if (result.error) {
    vscode.window.showErrorMessage('Transcription failed: ' + result.error);
    return;
  }

  const { text, deleteWord, deleteSentence } = formatTranscript(result.text || '');
  let finalText = text;

  if (text && cfg().get('structure', true)) {
    statusBarItem.text = '$(sync~spin) Structuring...';
    statusBarItem.tooltip = 'Structuring text with AI...';
    if (cfg().get('cursorIndicator', true)) applyBadge('busy', ' ✦');
    const structured = await structureWithLLM(text);
    applyBadge('none');
    updateStatusBar();
    if (abortTranscription) return;
    if (structured) {
      finalText = toOneLine(structured);
      vscode.window.showInformationMessage('Text structured with AI (one line).');
    }
  }

  if (target === 'terminal') {
    const term = vscode.window.activeTerminal;
    if (term && finalText) {
      term.sendText(toOneLine(finalText), false);
    } else if (finalText) {
      await vscode.env.clipboard.writeText(toOneLine(finalText));
      vscode.window.showWarningMessage('No active terminal — text copied to clipboard (one line).');
    }
    return;
  }
  await insertIntoEditor(finalText, deleteWord, deleteSentence);
}

async function cancelRecording() {
  if (recording) {
    abortTranscription = true;
    try {
      await api('/api/cancel', 'POST');
    } catch {
      /* ignore */
    }
    recording = false;
    stopBlink();
    if (elapsedTimer) clearInterval(elapsedTimer);
    vscode.commands.executeCommand('setContext', 'voiceDictation.recording', false);
    applyBadge('none');
    updateStatusBar();
    vscode.window.showInformationMessage('Dictation cancelled.');
    return;
  }
  if (transcribing) {
    abortTranscription = true;
    try {
      await api('/api/cancel', 'POST');
    } catch {
      /* ignore */
    }
    vscode.window.showInformationMessage('Dictation cancelled.');
  }
}

async function toggle() {
  if (recording) {
    await stopToTarget('editor');
  } else {
    await startRecording();
  }
}

async function toggleTerminal() {
  if (recording) {
    await stopToTarget('terminal');
  } else {
    await startRecording();
  }
}

async function envInfoCommand() {
  try {
    const out = await runBootstrapArgs(['--report']);
    const r = JSON.parse(out);
    const lines = [
      'Mode: ' + (r.mode || 'not set up yet'),
      'Environment: ' + (r.python || '(none)') + ' (' + r.env_size_mb + ' MB)',
    ];
    if (r.legacy && r.legacy.length) {
      for (const l of r.legacy) lines.push('Old copies (' + l.size_mb + ' MB each): ' + l.path);
    }
    lines.push('Whisper models cache: ' + r.hf_cache_mb + ' MB (shared by all apps)');
    vscode.window.showInformationMessage(lines.join('\n'), 'Run cleanup').then(choice => {
      if (choice === 'Run cleanup') {
        vscode.window.withProgress(
          { location: vscode.ProgressLocation.Notification, title: 'Voice dictation: cleaning old copies...' },
          async () => {
            try {
              await runBootstrapArgs(['--cleanup-legacy']);
              vscode.window.showInformationMessage('Old copies removed.');
            } catch (e) {
              vscode.window.showErrorMessage(e.message);
            }
          }
        );
      }
    });
  } catch (e) {
    vscode.window.showErrorMessage(e.message);
  }
}

async function runSetupCommand() {
  vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: 'Voice dictation: installing environment...',
      cancellable: false,
    },
    async () => {
      try {
        await runBootstrap('python');
        vscode.window.showInformationMessage('Environment ready.');
      } catch (e) {
        vscode.window.showErrorMessage(e.message);
      }
    }
  );
}

async function restartServer() {
  if (recording) await stopRecording(false);
  try {
    await api('/api/shutdown', 'POST');
  } catch {
    /* server may already be down */
  }
  await sleep(800);
  serverStarting = true;
  startServerProcess();
  updateStatusBar();
  for (let i = 0; i < 120; i++) {
    await sleep(500);
    try {
      await api('/api/status');
      break;
    } catch {
      /* still loading */
    }
  }
  serverStarting = false;
  updateStatusBar();
  vscode.window.showInformationMessage('Voice dictation server restarted.');
}

function activate(context) {
  DECOR.recOn = makeDecor('#ff4d4d', '● REC');
  DECOR.recOff = makeDecor('rgba(255, 80, 80, 0.35)', '● REC');
  DECOR.busy = makeDecor('#4fc3f7', '');

  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'voiceDictation.toggle';
  updateStatusBar();
  statusBarItem.show();

  warmUpServer();

  context.subscriptions.push(
    vscode.commands.registerCommand('voiceDictation.toggle', toggle),
    vscode.commands.registerCommand('voiceDictation.toggleTerminal', toggleTerminal),
    vscode.commands.registerCommand('voiceDictation.cancel', cancelRecording),
    vscode.commands.registerCommand('voiceDictation.restartServer', restartServer),
    vscode.commands.registerCommand('voiceDictation.setup', runSetupCommand),
    vscode.commands.registerCommand('voiceDictation.envInfo', envInfoCommand),
    DECOR.recOn,
    DECOR.recOff,
    DECOR.busy,
    statusBarItem
  );
}

function deactivate() {}

module.exports = { activate, deactivate };