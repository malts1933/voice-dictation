'use strict';

const PUNCT = [
  ['запятая', ', '],
  ['comma', ', '],
  ['точка', '. '],
  ['period', '. '],
  ['full stop', '. '],
  ['точка с запятой', '; '],
  ['semicolon', '; '],
  ['двоеточие', ': '],
  ['colon', ': '],
  ['вопросительный знак', '? '],
  ['question mark', '? '],
  ['восклицательный знак', '! '],
  ['exclamation mark', '! '],
  ['многоточие', '... '],
  ['ellipsis', '... '],
  ['тире', ' — '],
  ['dash', ' — '],
  ['дефис', '-'],
  ['hyphen', '-'],
  ['новая строка', '\n'],
  ['new line', '\n'],
  ['новый абзац', '\n\n'],
  ['new paragraph', '\n\n'],
  ['открыть кавычки', '"'],
  ['open quotes', '"'],
  ['закрыть кавычки', '"'],
  ['close quotes', '"'],
  ['открыть скобку', '('],
  ['open parenthesis', '('],
  ['закрыть скобку', ')'],
  ['close parenthesis', ')'],
];

const DELETE_WORD = ['удали последнее слово', 'delete last word'];
const DELETE_SENTENCE = ['удали последнее предложение', 'delete last sentence'];
const CAPITALIZE = ['большая буква', 'с большой буквы', 'capitalize'];

function matchAt(tokens, i, phrase) {
  const parts = phrase.split(' ');
  if (i + parts.length > tokens.length) return false;
  for (let k = 0; k < parts.length; k++) {
    if (tokens[i + k].toLowerCase() !== parts[k]) return false;
  }
  return true;
}

function formatTranscript(raw) {
  const tokens = raw.trim().split(/\s+/).filter(Boolean);
  let out = '';
  let capitalizeNext = false;
  let deleteWord = 0;
  let deleteSentence = 0;

  for (let i = 0; i < tokens.length; i++) {
    let handled = false;

    for (const [phrase, insert] of PUNCT) {
      if (matchAt(tokens, i, phrase)) {
        if (/^[,.;:!?…]/.test(insert)) out = out.trimEnd();
        out += insert;
        i += phrase.split(' ').length - 1;
        handled = true;
        break;
      }
    }
    if (handled) continue;

    if (DELETE_WORD.some(p => matchAt(tokens, i, p))) {
      const phrase = DELETE_WORD.find(p => matchAt(tokens, i, p));
      i += phrase.split(' ').length - 1;
      out = out.trimEnd();
      const idx = out.lastIndexOf(' ');
      out = idx === -1 ? '' : out.slice(0, idx + 1);
      if (!out.trim()) deleteWord++;
      continue;
    }

    if (DELETE_SENTENCE.some(p => matchAt(tokens, i, p))) {
      const phrase = DELETE_SENTENCE.find(p => matchAt(tokens, i, p));
      i += phrase.split(' ').length - 1;
      out = out.trimEnd();
      const idx = out.lastIndexOf('\n');
      out = idx === -1 ? '' : out.slice(0, idx + 1);
      if (!out.trim()) deleteSentence++;
      continue;
    }

    if (CAPITALIZE.some(p => matchAt(tokens, i, p))) {
      const phrase = CAPITALIZE.find(p => matchAt(tokens, i, p));
      i += phrase.split(' ').length - 1;
      capitalizeNext = true;
      continue;
    }

    let word = tokens[i];
    if (capitalizeNext) {
      word = word.charAt(0).toUpperCase() + word.slice(1);
      capitalizeNext = false;
    }
    out += word + ' ';
  }

  return { text: out.trim(), deleteWord, deleteSentence };
}

module.exports = { formatTranscript };