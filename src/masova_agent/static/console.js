/* Manager workspace: server records only. Credentials and audio never enter storage. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let key = '', scopes = [], specialists = [], selectedAgent = null;
  let session = crypto.randomUUID(), revision = 0, recordRequest = 0, chatting = false;
  let running = false, connecting = false, conversationRevision = 0;
  let historyOpen = false, historyPending = false, historyRequest = 0, historyController = null;
  const requests = new Set();
  const has = scope => key && (scopes.includes('*') || scopes.includes(scope));
  function notice(text, error = false) {
    $('notice').textContent = text; $('notice').classList.toggle('error', error);
  }
  async function api(path, body, signal) {
    if (!key) throw new Error('Connect with a console API key first.');
    const controller = new AbortController(); requests.add(controller);
    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
    const timer = setTimeout(abort, path.includes('/chat') ? 120000 : 90000);
    try {
      const response = await fetch(path, {
        method: body === undefined ? 'GET' : 'POST', signal: controller.signal,
        headers: { 'X-Agent-Api-Key': key, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'Check request fields and permissions.';
        throw new Error(`${response.status}: ${detail}`);
      }
      return data;
    } finally {
      clearTimeout(timer); requests.delete(controller); signal?.removeEventListener('abort', abort);
    }
  }
  function text(tag, value, className) {
    const element = document.createElement(tag); element.textContent = value ?? '';
    if (className) element.className = className; return element;
  }
  function appendTurn(role, content, evidence = '') {
    $('messages').querySelector('.welcome')?.remove();
    const turn = text('div', '', `turn ${role}`);
    turn.append(text('strong', role === 'user' ? 'You' : 'MaSoVa AI'), text('div', content));
    if (evidence) turn.append(text('p', evidence, 'small'));
    $('messages').append(turn); $('messages').scrollTop = $('messages').scrollHeight;
  }
  function chatEvidence(result) {
    return [result.used_fallback ? 'Fallback response; no model-generated operations answer.' : '',
      result.run_id ? `Run ${result.run_id}` : '',
      result.tools_used?.length ? `Public tools: ${result.tools_used.join(', ')}` : '',
      result.proposals?.length ? `${result.proposals.length} proposal(s); review required.` : '',
    ].filter(Boolean).join(' · ');
  }
  const voice = new globalThis.MaSoVaVoice({
    getUserMedia: options => {
      if (!navigator.mediaDevices?.getUserMedia || !globalThis.MediaRecorder) {
        return Promise.reject(new Error('Recording unavailable'));
      }
      return navigator.mediaDevices.getUserMedia(options);
    },
    MediaRecorder: globalThis.MediaRecorder, Blob,
    setTimeout: (callback, delay) => setTimeout(callback, delay),
    clearTimeout: timer => clearTimeout(timer), createObjectURL: blob => URL.createObjectURL(blob),
    revokeObjectURL: url => URL.revokeObjectURL(url), makeAudio: url => new Audio(url),
    makeContext: (globalThis.AudioContext || globalThis.webkitAudioContext)
      ? () => new (globalThis.AudioContext || globalThis.webkitAudioContext)() : undefined,
    requestFrame: callback => requestAnimationFrame(callback), cancelFrame: id => cancelAnimationFrame(id),
    visualsEnabled: () => !document.hidden && !matchMedia('(prefers-reduced-motion: reduce)').matches,
  }, state => {
    $('voice-state').textContent = state; $('voice-mute').textContent = state === 'Muted' ? 'Unmute' : 'Mute';
    controls();
  }, signal => { $('voice-level').value = signal; });
  function controls() {
    const recording = ['Listening', 'Muted'].includes(voice?.state);
    const active = voiceActive();
    $('send').disabled = !has('chat:manager') || chatting || active || historyOpen;
    $('voice-start').disabled = !has('chat:manager') || chatting || active || historyOpen;
    $('voice-send').disabled = !recording;
    $('voice-mute').disabled = !recording;
    $('voice-end').disabled = !active;
    $('new-conversation').disabled = chatting || active || historyOpen;
    $('conversation-history').disabled = !has('chat:manager') || chatting || historyOpen;
    $('history-retry').disabled = historyPending || !has('chat:manager');
    $('run-specialist').disabled = !selectedAgent || !has(`trigger:${selectedAgent.name}`) || running;
    $('refresh').disabled = !key;
    $('connect').disabled = connecting;
    $('disconnect').hidden = !key;
  }
  function voiceActive() {
    return ['Requesting microphone', 'Listening', 'Muted', 'Processing', 'Speaking'].includes(voice?.state);
  }
  function clearConversation() {
    conversationRevision++; chatting = false;
    session = crypto.randomUUID(); $('messages').replaceChildren(); $('chat-state').textContent = '';
    $('message').value = '';
  }
  function closeHistory(returnFocus = true) {
    historyRequest++; historyController?.abort(); historyController = null;
    historyPending = false; historyOpen = false;
    if ($('history-drawer').open) $('history-drawer').close();
    $('history-list').replaceChildren(); $('history-state').textContent = '';
    controls();
    if (returnFocus) (has('chat:manager') ? $('conversation-history') : $('api-key')).focus();
  }
  async function loadConversations() {
    if (!historyOpen || !has('chat:manager')) return;
    historyController?.abort(); historyController = new AbortController();
    const token = ++historyRequest, version = revision, store = $('store').value || '';
    historyPending = true; controls(); $('history-list').replaceChildren();
    $('history-state').textContent = 'Loading saved conversations…';
    try {
      const result = await api(`/agent/manager/conversations?${new URLSearchParams({ storeId: store, limit: '128' })}`, undefined, historyController.signal);
      if (!historyOpen || token !== historyRequest || version !== revision) return;
      if (!Array.isArray(result.conversations)) throw new Error('Conversation history unavailable. Retry.');
      $('history-state').textContent = result.conversations.length ? `${result.conversations.length} saved conversation${result.conversations.length === 1 ? '' : 's'}.` : 'No saved conversations for this credential and store context.';
      result.conversations.forEach(record => {
        const row = text('button', '', `history-row${record.sessionId === session ? ' selected' : ''}`);
        row.type = 'button';
        row.append(text('strong', record.title || 'Conversation'),
          text('span', `${record.messageCount} messages · ${record.updatedAt}`, 'small'));
        row.onclick = () => reopenConversation(record.sessionId);
        $('history-list').append(row);
      });
    } catch (error) {
      if (historyOpen && token === historyRequest && version === revision) $('history-state').textContent = error.message;
    } finally {
      if (token === historyRequest) { historyPending = false; controls(); }
    }
  }
  async function reopenConversation(id) {
    if (!historyOpen || historyPending || !has('chat:manager') || chatting) return;
    historyController?.abort(); historyController = new AbortController();
    const token = ++historyRequest, version = revision, store = $('store').value || '';
    historyPending = true; controls(); voice.end();
    $('history-state').textContent = 'Opening saved conversation…';
    try {
      const result = await api(`/agent/manager/conversations/${encodeURIComponent(id)}?${new URLSearchParams({ storeId: store })}`, undefined, historyController.signal);
      if (!historyOpen || token !== historyRequest || version !== revision) return;
      const record = result.conversation;
      if (!record || record.sessionId !== id || (record.storeId || '') !== store || !Array.isArray(record.messages)) {
        throw new Error('Conversation context changed. Refresh history.');
      }
      clearConversation(); session = record.sessionId;
      record.messages.forEach(turn => {
        if (['user', 'assistant'].includes(turn.role) && typeof turn.text === 'string') appendTurn(turn.role, turn.text);
      });
      closeHistory(false); $('chat-state').textContent = 'Saved conversation reopened. Continue below.';
      $('message').focus();
    } catch (error) {
      if (historyOpen && token === historyRequest && version === revision) $('history-state').textContent = error.message;
    } finally {
      if (token === historyRequest) { historyPending = false; controls(); }
    }
  }
  $('conversation-history').onclick = async () => {
    if (!has('chat:manager') || chatting || historyOpen) return;
    historyOpen = true; voice.end(); controls();
    $('history-context').textContent = $('store').selectedOptions?.[0]?.textContent || ($('store').value || 'All stores');
    $('history-drawer').showModal(); $('history-close').focus();
    await loadConversations();
  };
  $('history-close').onclick = () => closeHistory();
  $('history-retry').onclick = () => loadConversations();
  $('history-drawer').oncancel = event => { event.preventDefault(); closeHistory(); };
  $('history-drawer').onclick = event => { if (event.target === $('history-drawer')) closeHistory(); };
  $('history-drawer').onkeydown = event => {
    if (event.key !== 'Tab') return;
    const buttons = Array.from($('history-drawer').querySelectorAll('button:not([disabled])'));
    if (!buttons.length) return;
    const first = buttons[0], last = buttons[buttons.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  $('new-conversation').onclick = () => {
    if (chatting || voiceActive() || historyOpen) return;
    voice.end(); clearConversation(); $('message').focus();
  };
  function disconnect() {
    closeHistory(false);
    revision++; recordRequest++; key = ''; scopes = []; specialists = []; selectedAgent = null;
    requests.forEach(controller => controller.abort()); voice.end();
    $('api-key').value = ''; $('connection-state').textContent = 'Not connected';
    $('record-list').replaceChildren(); $('record-detail').replaceChildren();
    $('record-state').textContent = 'No records loaded.';
    $('store').replaceChildren(new Option('All stores', '')); $('specialist').hidden = true;
    clearConversation(); controls(); notice('Connect to read records and request operations.');
  }
  $('disconnect').onclick = disconnect;
  $('connection').onsubmit = async event => {
    event.preventDefault(); if (connecting) return;
    const submittedKey = $('api-key').value.trim();
    disconnect(); key = submittedKey; connecting = true; controls();
    $('connection-state').textContent = 'Connecting…';
    const version = revision;
    try {
      const catalog = await api('/agent/console');
      if (version !== revision) return;
      scopes = catalog.scopes; specialists = catalog.specialists;
      $('connection-state').textContent = 'Connected · scoped API key';
      notice('Connected. Approval records a decision; final execution happens in the platform.');
      controls(); await refreshRecords();
      try {
        const stores = await api('/agent/manager/stores');
        if (version !== revision) return;
        if (!stores.ok) throw new Error(stores.error || 'Store lookup unavailable');
        stores.stores.forEach(store => $('store').add(new Option(store.name, store.id)));
      } catch (error) {
        if (version === revision) notice(`Store lookup unavailable: ${error.message}. All-store context remains available.`, true);
      }
    } catch (error) {
      if (version === revision) { disconnect(); $('connection-state').textContent = error.message; }
    } finally { connecting = false; controls(); }
  };
  $('navigation').onclick = event => {
    const button = event.target.closest('button'); if (!button) return;
    $('navigation').querySelectorAll('button').forEach(item => {
      item.classList.toggle('selected', item === button);
      if (item === button) item.setAttribute('aria-current', 'page'); else item.removeAttribute('aria-current');
    });
    selectedAgent = specialists.find(agent => agent.name === button.dataset.agent) || null;
    $('specialist').hidden = !selectedAgent; $('page-title').textContent = button.textContent;
    if (button.dataset.agent && !selectedAgent) notice('Connect to access specialist controls.');
    if (selectedAgent) {
      $('specialist-title').textContent = selectedAgent.label;
      $('specialist-task').textContent = selectedAgent.task;
      const review = selectedAgent.scope === 'review_store';
      $('specialist-scope').textContent = review ? 'Scope: supplied review store. Draft only; manager review required.'
        : 'Scope: all available stores. Read / record selection does not scope this run.';
      $('review-input').hidden = !review;
      $('run-specialist').textContent = review ? 'Draft review reply' : 'Run for all stores';
    }
    if (button.dataset.view === 'history') $('record-type').value = 'runs';
    if (button.dataset.view === 'activity') $('record-type').value = 'activity';
    controls(); refreshRecords();
  };
  function publicPayload(value) {
    if (Array.isArray(value)) return value.map(publicPayload);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value)
      .filter(([name]) => !/token|key|secret|password|email|phone|customer|history|reasoning|authorization/i.test(name))
      .map(([name, field]) => [name, publicPayload(field)]));
    return value;
  }
  function status(value) { return text('span', value || 'Unknown', `status ${(value || '').toLowerCase()}`); }
  function recordDetail(record, kind) {
    const detail = $('record-detail'); detail.replaceChildren();
    detail.append(text('h3', kind === 'proposal' ? record.summary : 'Run record'), status(record.status));
    const definitions = document.createElement('dl');
    const fields = kind === 'proposal' ? { ID: record.proposal_id, Agent: record.agent, Store: record.store_id || 'Not recorded',
      Created: record.created_at, Resolved: record.resolved_at || 'Awaiting decision' }
      : { ID: record.run_id, Agent: record.agent, Scope: record.store_id || 'All stores / unscoped',
        Trigger: record.trigger, Time: record.timestamp, 'Chain sequence': record.chain_seq };
    Object.entries(fields).forEach(([name, value]) => definitions.append(text('dt', name), text('dd', value)));
    detail.append(definitions);
    if (kind === 'proposal') {
      detail.append(text('h3', 'Proposal rationale'), text('p', record.rationale || 'No public rationale recorded.'));
      const evidence = document.createElement('details'); evidence.append(text('summary', 'Proposed values / recorded evidence'),
        text('pre', JSON.stringify(publicPayload(record.payload || {}), null, 2))); detail.append(evidence);
      detail.append(text('p', 'Approval records review only. No purchase order, price change, campaign or other final action is executed here.', 'small'));
      if (record.status === 'PENDING' && has('resolve:proposals')) {
        const label = text('label', 'Review note (optional)'); label.htmlFor = 'decision-note';
        const note = document.createElement('textarea'); note.id = 'decision-note'; note.maxLength = 2000;
        const actions = text('div', '', 'actions');
        ['REJECTED', 'APPROVED'].forEach(decision => {
          const button = text('button', decision === 'APPROVED' ? 'Approve · record only' : 'Reject', decision === 'APPROVED' ? 'primary' : '');
          button.type = 'button';
          button.onclick = async () => {
            const version = revision; actions.querySelectorAll('button').forEach(item => { item.disabled = true; });
            try {
              const result = await api(`/agent/proposals/${encodeURIComponent(record.proposal_id)}/resolve`, { status: decision, note: note.value });
              if (version !== revision) return;
              recordDetail(result, 'proposal'); notice(`${result.status}: manager decision recorded. Final execution remains in the platform.`);
              await refreshRecords(false);
            } catch (error) {
              if (version !== revision) return;
              notice(error.message, true); actions.querySelectorAll('button').forEach(item => { item.disabled = false; });
            }
          }; actions.append(button);
        });
        detail.append(label, note, actions);
      } else if (record.resolution_note) detail.append(text('p', `Review note: ${record.resolution_note}`));
    } else {
      detail.append(text('p', record.summary || 'No public summary recorded.'));
      if (record.tools_used?.length) detail.append(text('p', `Public tools: ${record.tools_used.join(', ')}`));
      detail.append(text('p', 'Hash-chained run record. Private reasoning and raw tool inputs are not shown.', 'small'));
    }
  }
  async function refreshRecords(clearDetail = true) {
    if (!key) return;
    const version = revision, request = ++recordRequest;
    const kind = $('record-type').value, store = $('store').value;
    const query = new URLSearchParams({ limit: '100' });
    if (store) query.set('storeId', store);
    if (selectedAgent) query.set('agent', selectedAgent.name);
    const proposalQuery = new URLSearchParams(query);
    if ($('record-status').value) proposalQuery.set('status', $('record-status').value);
    $('record-status').disabled = kind === 'runs'; $('record-state').textContent = 'Loading records…';
    const sources = kind === 'runs' ? ['runs'] : kind === 'proposals' ? ['proposals'] : ['runs', 'proposals'];
    const results = await Promise.allSettled(sources.map(source => {
      if (!has(`read:${source}`)) return Promise.reject(new Error(`Missing scope: read:${source}`));
      return api(`/agent/${source}?${source === 'proposals' ? proposalQuery : query}`);
    }));
    if (version !== revision || request !== recordRequest) return;
    const rows = [], errors = [];
    results.forEach((result, index) => {
      if (result.status === 'rejected') { errors.push(result.reason.message); return; }
      const source = sources[index], records = source === 'runs' ? result.value : result.value.proposals;
      records.forEach(record => rows.push({ record, kind: source === 'runs' ? 'run' : 'proposal' }));
    });
    rows.sort((a, b) => (b.record.resolved_at || b.record.timestamp || b.record.created_at || '')
      .localeCompare(a.record.resolved_at || a.record.timestamp || a.record.created_at || ''));
    $('record-list').replaceChildren();
    if (clearDetail) $('record-detail').replaceChildren(text('p', 'Select a record to inspect its public evidence.'));
    $('record-state').textContent = errors.length ? errors.join(' · ') : rows.length
      ? `${rows.length} record(s) loaded · newest first · up to 100 per source` : 'No records match this context.';
    rows.forEach(({ record, kind: rowKind }) => {
      const button = text('button', '', 'record'); button.type = 'button';
      button.append(text('strong', record.summary || `${record.agent} run`), status(record.status),
        text('span', `${record.agent || 'Agent'} · ${record.store_id || 'All stores / unscoped'}`, 'small'));
      button.onclick = () => {
        $('record-list').querySelectorAll('button').forEach(item => item.classList.toggle('selected', item === button));
        recordDetail(record, rowKind);
      }; $('record-list').append(button);
    });
  }
  $('refresh').onclick = () => refreshRecords();
  ['record-type', 'record-status'].forEach(id => { $(id).onchange = () => refreshRecords(); });
  $('store').onchange = () => {
    closeHistory(false);
    revision++; requests.forEach(controller => controller.abort()); voice.end(); clearConversation();
    $('review-store').value = $('store').value; refreshRecords(); controls();
    notice('Read / record context changed. Conversation restarted. Specialist runs still cover all stores.');
  };
  $('run-specialist').onclick = async () => {
    if (!selectedAgent || running) return;
    let body;
    const agent = selectedAgent, version = revision;
    if (agent.scope === 'review_store') {
      if (!$('review-input').reportValidity()) return;
      body = { reviewId: $('review-id').value, storeId: $('review-store').value,
        rating: Number($('review-rating').value), text: $('review-text').value };
      if ($('review-order').value) body.orderId = $('review-order').value;
    }
    running = true; controls(); notice(`${agent.label}: awaiting actual ${agent.scope === 'all_stores' ? 'all-store' : 'review-store'} result…`);
    try {
      const result = await api(`/agents/${agent.route}/trigger`, body || {});
      if (version !== revision) return;
      if (result.error || result._runtime?.status === 'error') throw new Error(result.error || 'Specialist run failed');
      notice(`${agent.label}: ${result.summary || result.reason || result.status || 'Result received'}. Scope: ${agent.scope === 'all_stores' ? 'all stores' : body.storeId}. Review records for proposals.`);
      await refreshRecords();
    } catch (error) { if (version === revision) notice(error.message, true); }
    finally { running = false; controls(); }
  };
  $('composer').onsubmit = async event => {
    event.preventDefault(); const message = $('message').value.trim();
    if (!message || chatting || voiceActive() || historyOpen || !has('chat:manager')) return;
    const version = revision, conversation = conversationRevision;
    chatting = true; controls(); appendTurn('user', message);
    $('message').value = ''; $('chat-state').textContent = 'Awaiting manager response…';
    try {
      const result = await api('/agent/manager/chat', { message, sessionId: session, storeId: $('store').value || null });
      if (version !== revision || conversation !== conversationRevision) return;
      appendTurn('assistant', result.reply, chatEvidence(result));
      $('chat-state').textContent = result.historyError || (result.historySaved ? 'Conversation saved.' : '');
      await refreshRecords(false);
    } catch (error) {
      if (version === revision && conversation === conversationRevision) {
        $('chat-state').textContent = error.message; $('message').value = message;
      }
    } finally {
      if (version === revision && conversation === conversationRevision) chatting = false;
      controls();
    }
  };
  $('message').onkeydown = event => {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
      event.preventDefault(); $('composer').requestSubmit();
    }
  };
  $('voice-start').onclick = () => {
    if (!has('chat:manager') || chatting || historyOpen || voiceActive()) return;
    const version = revision, conversation = conversationRevision;
    const targetSession = session, storeId = $('store').value || null;
    return voice.start(async (blob, signal) => {
      const bytes = new Uint8Array(await blob.arrayBuffer());
      if (version !== revision || conversation !== conversationRevision || signal.aborted) {
        throw new DOMException('Cancelled', 'AbortError');
      }
      let binary = ''; bytes.forEach(byte => { binary += String.fromCharCode(byte); });
      const result = await api('/agent/manager/chat', { audioBase64: btoa(binary),
        mimeType: blob.type.split(';')[0], sessionId: targetSession, storeId }, signal);
      if (version !== revision || conversation !== conversationRevision || signal.aborted) {
        throw new DOMException('Cancelled', 'AbortError');
      }
      if (result.transcript) appendTurn('user', result.transcript);
      appendTurn('assistant', result.reply, chatEvidence(result));
      $('chat-state').textContent = result.historyError || (result.historySaved ? 'Conversation saved.' : '');
      refreshRecords(false); return result;
    });
  };
  $('voice-send').onclick = () => voice.stop();
  $('voice-mute').onclick = () => voice.mute(); $('voice-end').onclick = () => voice.end();
  document.addEventListener('visibilitychange', () => { if (document.hidden) voice.end(); });
  window.addEventListener('pagehide', disconnect);
  controls();
})();
