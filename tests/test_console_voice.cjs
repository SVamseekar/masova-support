// Browser-independent lifecycle proof using real state transitions and controlled media resources.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const VoiceSession = require('../src/masova_agent/static/voice.js');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

async function consoleFixture() {
  let voice;
  const chatRequests = [];
  const elements = new Map();
  const element = () => ({
    value: '', textContent: '', classList: { toggle() {} },
    replaceChildren() {}, append() {}, querySelector: () => null, querySelectorAll: () => [], add() {},
  });
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    createElement: element, addEventListener() {},
  };
  const context = vm.createContext({
    document, window: { addEventListener() {} }, navigator: {},
    MaSoVaVoice: class extends VoiceSession {
      constructor(...args) { super(...args); voice = this; }
    }, crypto: { randomUUID: () => 'test-session' },
    Blob, AbortController, URLSearchParams, URL, Option: class {},
    setTimeout() {
      'use strict';
      if (this !== undefined) throw new TypeError('Illegal invocation');
      return 1;
    },
    clearTimeout() {
      'use strict';
      if (this !== undefined) throw new TypeError('Illegal invocation');
    },
    fetch: async (url, options) => {
      if (url === '/agent/manager/chat') chatRequests.push(JSON.parse(options.body));
      return { ok: true, json: async () => url === '/agent/console'
      ? { scopes: ['read:registry', 'read:proposals', 'chat:manager'], specialists: [] }
      : url === '/agent/manager/chat' ? { reply: 'Synthetic reply' }
      : url.startsWith('/agent/proposals') ? { proposals: [] } : { ok: true, stores: [] } };
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/masova_agent/static/console.js'), 'utf8'), context);
  document.getElementById('api-key').value = 'synthetic-console-key';
  document.getElementById('record-type').value = 'proposals';
  await document.getElementById('connection').onsubmit({ preventDefault() {} });
  return { document, voice, chatRequests };
}

test('console connects with browser timers that require their Window receiver', async () => {
  const { document } = await consoleFixture();
  assert.equal(document.getElementById('connection-state').textContent, 'Connected · scoped API key');
  assert.equal(document.getElementById('send').disabled, false);
  document.getElementById('disconnect').onclick();
  assert.equal(document.getElementById('send').disabled, true);
});

for (const state of ['Requesting microphone', 'Listening', 'Muted', 'Processing', 'Speaking']) {
  test(`Enter preserves unsent text during voice ${state} and resumes after End`, async () => {
    const { document, voice, chatRequests } = await consoleFixture();
    const message = document.getElementById('message');
    const composer = document.getElementById('composer');
    let submission;
    composer.requestSubmit = () => { submission = composer.onsubmit({ preventDefault() {} }); };
    voice.setState(state);
    assert.equal(document.getElementById('send').disabled, true);
    message.value = 'Synthetic unsent message';
    message.onkeydown({ key: 'Enter', preventDefault() {} });
    await submission;
    assert.equal(chatRequests.length, 0);
    assert.equal(message.value, 'Synthetic unsent message');
    voice.end();
    message.onkeydown({ key: 'Enter', preventDefault() {} });
    await submission;
    assert.equal(chatRequests.length, 1);
  });
}

function fixture(overrides = {}) {
  const states = [], tracks = [{ enabled: true, stopped: false, stop() { this.stopped = true; } }];
  const stream = { getTracks: () => tracks };
  class Recorder {
    constructor() { this.state = 'inactive'; this.mimeType = 'audio/webm'; }
    start() { this.state = 'recording'; }
    pause() { this.state = 'paused'; }
    resume() { this.state = 'recording'; }
    stop() { this.state = 'inactive'; queueMicrotask(() => this.onstop?.()); }
  }
  const env = {
    getUserMedia: async () => stream, MediaRecorder: Recorder, Blob,
    setTimeout, clearTimeout, createObjectURL: () => 'blob:test', revokeObjectURL() {},
    makeAudio: () => ({ pause() {}, removeAttribute() {}, load() {} }),
    ...overrides,
  };
  const voice = new VoiceSession(env, state => states.push(state), () => {});
  return { voice, states, tracks };
}

test('permission denial gives recoverable state without retained media', async () => {
  const { voice, states } = fixture({ getUserMedia: async () => { throw new Error('denied'); } });
  await voice.start(async () => ({}));
  assert.match(states.at(-1), /Microphone unavailable/);
  assert.equal(voice.stream, null);
});

test('end during permission request disposes late stream and prevents listening', async () => {
  let resolve;
  const { voice, states, tracks } = fixture({ getUserMedia: () => new Promise(r => { resolve = r; }) });
  const starting = voice.start(async () => ({}));
  voice.end();
  resolve({ getTracks: () => tracks });
  await starting;
  assert.equal(tracks[0].stopped, true);
  assert.equal(states.at(-1), 'Ended');
  assert.equal(states.includes('Listening'), false);
});

test('mute pauses recording and end releases microphone', async () => {
  const { voice, states, tracks } = fixture();
  await voice.start(async () => ({}));
  voice.mute();
  assert.equal(tracks[0].enabled, false);
  assert.equal(voice.recorder.state, 'paused');
  assert.equal(states.at(-1), 'Muted');
  voice.mute();
  assert.equal(voice.recorder.state, 'recording');
  voice.end();
  assert.equal(tracks[0].stopped, true);
  assert.equal(voice.recorder, null);
});

test('processing failure releases tracks and exposes error', async () => {
  const { voice, states, tracks } = fixture();
  await voice.start(async () => { throw new Error('Provider unavailable'); });
  voice.recorder.ondataavailable({ data: new Blob(['audio']) });
  await voice.stop();
  assert.equal(tracks[0].stopped, true);
  assert.match(states.at(-1), /Provider unavailable/);
});

test('end aborts provider request and ignores late audio', async () => {
  let signal, resolve;
  const { voice, states, tracks } = fixture();
  await voice.start((blob, s) => { signal = s; return new Promise(r => { resolve = r; }); });
  voice.recorder.ondataavailable({ data: new Blob(['audio']) });
  const processing = voice.stop();
  await new Promise(r => setImmediate(r));
  voice.end();
  assert.equal(signal.aborted, true);
  resolve({ audioBase64: 'YQ==', mimeType: 'audio/wav' });
  await processing;
  assert.equal(states.at(-1), 'Ended');
  assert.equal(tracks[0].stopped, true);
  assert.equal(voice.audio, null);
});

test('speaking begins only at playback event and cleanup revokes URL', async () => {
  let player, revoked = false;
  const { voice, states } = fixture({
    makeAudio: () => (player = { pause() {}, removeAttribute() {}, load() {},
      async play() { this.onplaying(); queueMicrotask(() => this.onended()); } }),
    revokeObjectURL: () => { revoked = true; },
  });
  await voice.start(async () => ({ audioBase64: 'YQ==', mimeType: 'audio/wav' }));
  voice.recorder.ondataavailable({ data: new Blob(['audio']) });
  await voice.stop();
  assert.equal(states.includes('Speaking'), true);
  assert.equal(states.at(-1), 'Ready');
  assert.equal(revoked, true);
  assert.equal(voice.audio, null);
  assert.ok(player);
});

test('end while stopping recorder resolves cancelled stop without submitting', async () => {
  class DelayedRecorder {
    constructor() { this.state = 'inactive'; this.mimeType = 'audio/webm'; }
    start() { this.state = 'recording'; }
    stop() { this.state = 'inactive'; }
  }
  let submitted = false;
  const { voice, states } = fixture({ MediaRecorder: DelayedRecorder });
  await voice.start(async () => { submitted = true; return {}; });
  voice.recorder.ondataavailable({ data: new Blob(['audio']) });
  const stopped = voice.stop();
  voice.end();
  const result = await Promise.race([stopped.then(() => 'released'),
    new Promise(resolve => setTimeout(() => resolve('hung'), 20))]);
  assert.equal(result, 'released');
  assert.equal(submitted, false);
  assert.equal(states.at(-1), 'Ended');
});
