const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function fixture() {
  let uuid = 0, voice;
  const elements = new Map(), requests = [], pending = [], documentListeners = new Map();
  const document = {
    activeElement: null,
    getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
    createElement: () => element(),
    addEventListener(name, callback) { documentListeners.set(name, callback); },
  };
  function element() {
    return {
      value: '', textContent: '', children: [], disabled: false, open: false,
      classList: { toggle() {} },
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      querySelector: () => null, querySelectorAll: () => [], add() {},
      setAttribute() {}, removeAttribute() {},
      focus() { document.activeElement = this; },
      showModal() { this.open = true; }, close() { this.open = false; },
    };
  }
  const context = vm.createContext({
    document, window: { addEventListener() {} }, navigator: {},
    MaSoVaVoice: class { constructor(env, onState) { this.state = 'Ready'; this.onState = onState; voice = this; }
      end() { this.state = 'Ended'; this.onState(this.state); }
      start(send) { this.send = send; this.state = 'Listening'; this.onState(this.state); }
    }, crypto: { randomUUID: () => `session-${++uuid}` },
    Blob, AbortController, URLSearchParams, URL, Option: class {}, DOMException, btoa,
    setTimeout: () => 1, clearTimeout() {},
    fetch: async (url, options) => {
      requests.push({ url, options });
      if (url.startsWith('/agent/manager/conversations')) {
        return new Promise((resolve, reject) => pending.push({ url, options, resolve, reject }));
      }
      return { ok: true, json: async () => url === '/agent/console'
        ? { scopes: ['read:registry', 'chat:manager'], specialists: [] }
        : url === '/agent/manager/chat' ? { reply: 'Synthetic reply', historySaved: true }
        : url === '/agent/manager/stores' ? { ok: true, stores: [] } : [] };
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/masova_agent/static/console.js'), 'utf8'), context);
  const $ = id => document.getElementById(id);
  async function connect() { $('api-key').value = 'synthetic-key'; await $('connection').onsubmit({ preventDefault() {} }); }
  function resolve(data, index = pending.length - 1, ok = true) { pending[index].resolve({ ok, status: ok ? 200 : 503, json: async () => data }); }
  return { $, document, context, requests, pending, connect, resolve, get voice() { return voice; } };
}

const tick = () => new Promise(resolve => setImmediate(resolve));
const thread = { sessionId: 'saved-thread', storeId: null, title: '<img src=x>', updatedAt: '2026-10-11T00:00:00Z', messageCount: 2 };

test('history shows actual pending, empty, and error states with focus return', async () => {
  const f = fixture(); await f.connect();
  const open = f.$('conversation-history').onclick(); await tick();
  assert.equal(f.$('history-drawer').open, true);
  assert.match(f.$('history-state').textContent, /Loading/);
  f.resolve({ conversations: [] }); await open;
  assert.match(f.$('history-state').textContent, /No saved conversations/);
  f.$('history-drawer').oncancel({ preventDefault() {} });
  assert.equal(f.$('history-drawer').open, false);
  assert.equal(f.document.activeElement, f.$('conversation-history'));
  const reopen = f.$('conversation-history').onclick(); await tick();
  f.resolve({ detail: 'History unavailable' }, f.pending.length - 1, false); await reopen;
  assert.match(f.$('history-state').textContent, /History unavailable/);
  assert.equal(f.$('history-retry').disabled, false);
});

test('reopen restores public messages and resumes same persisted session, using safe text nodes', async () => {
  const f = fixture(); await f.connect();
  const open = f.$('conversation-history').onclick(); await tick();
  f.resolve({ conversations: [thread] }); await open;
  const row = f.$('history-list').children[0];
  assert.equal(row.children[0].textContent, '<img src=x>');
  const restore = row.onclick(); await tick();
  f.resolve({ conversation: { ...thread, messages: [{ role: 'user', text: 'Persisted request' }, { role: 'assistant', text: 'Persisted reply' }] } }); await restore;
  assert.equal(f.$('history-drawer').open, false);
  assert.equal(f.$('messages').children.length, 2);
  assert.equal(f.$('messages').children[0].children[1].textContent, 'Persisted request');
  f.$('message').value = 'Continue request';
  await f.$('composer').onsubmit({ preventDefault() {} });
  const body = JSON.parse(f.requests.find(request => request.url === '/agent/manager/chat').options.body);
  assert.equal(body.sessionId, 'saved-thread');
  assert.equal(body.storeId, null);
});

for (const action of ['close', 'store', 'disconnect']) {
  test(`late history reopen cannot replace conversation after ${action}`, async () => {
    const f = fixture(); await f.connect();
    const open = f.$('conversation-history').onclick(); await tick();
    f.resolve({ conversations: [thread] }); await open;
    const restore = f.$('history-list').children[0].onclick(); await tick();
    const request = f.pending.at(-1);
    if (action === 'close') f.$('history-close').onclick();
    if (action === 'store') { f.$('store').value = 'other-store'; f.$('store').onchange(); }
    if (action === 'disconnect') f.$('disconnect').onclick();
    assert.equal(request.options.signal.aborted, true);
    f.resolve({ conversation: { ...thread, messages: [{ role: 'assistant', text: 'LATE_REPLY' }] } });
    await restore;
    assert.equal(f.$('messages').children.some(row => row.children.some(child => child.textContent === 'LATE_REPLY')), false);
  });
}


test('drawer traps Tab and Shift+Tab within visible controls', async () => {
  const f = fixture(); await f.connect();
  const open = f.$('conversation-history').onclick(); await tick();
  f.resolve({ conversations: [] }); await open;
  const first = f.$('history-close'), last = f.$('history-retry');
  f.$('history-drawer').querySelectorAll = () => [first, last];
  let prevented = 0;
  first.focus();
  f.$('history-drawer').onkeydown({ key: 'Tab', shiftKey: true, preventDefault() { prevented++; } });
  assert.equal(f.document.activeElement, last);
  f.$('history-drawer').onkeydown({ key: 'Tab', shiftKey: false, preventDefault() { prevented++; } });
  assert.equal(f.document.activeElement, first);
  assert.equal(prevented, 2);
});

test('mismatched restored store cannot replace current conversation', async () => {
  const f = fixture(); await f.connect();
  f.$('message').value = 'Original request';
  await f.$('composer').onsubmit({ preventDefault() {} });
  const original = f.$('messages').children;
  const open = f.$('conversation-history').onclick(); await tick();
  f.resolve({ conversations: [thread] }); await open;
  const restore = f.$('history-list').children[0].onclick(); await tick();
  f.resolve({ conversation: { ...thread, storeId: 'another', messages: [] } }); await restore;
  assert.match(f.$('history-state').textContent, /context changed/);
  assert.equal(f.$('messages').children, original);
});

test('late voice blob cannot submit into a reopened or changed store context', async () => {
  const f = fixture(); await f.connect();
  f.$('voice-start').onclick();
  let resolve;
  const bytes = new Promise(done => { resolve = done; });
  const sending = f.voice.send({ type: 'audio/webm', arrayBuffer: () => bytes }, new AbortController().signal);
  f.$('store').value = 'other'; f.$('store').onchange();
  resolve(new Uint8Array([1]).buffer);
  await assert.rejects(sending, { name: 'AbortError' });
  assert.equal(f.requests.some(request => request.url === '/agent/manager/chat'), false);
});
