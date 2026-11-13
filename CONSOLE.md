# Manager operations console

Open `/console` on the support service. The console contains the manager copilot,
seven specialists, public run history/activity, proposal evidence, explicit review
decisions, and integrated manager voice. It uses the existing support runtime,
policy and specialist endpoints. Customer `POST /agent/chat` remains unchanged.

## Authentication and scope

Enter an `X-Agent-Api-Key` credential configured through `AGENT_API_KEYS` or the
legacy `AGENT_TRIGGER_API_KEY`. The page keeps it in memory only; disconnect or
reload clears it. No credential is embedded in the public assets or browser storage.

The catalog requires `read:registry`; records require `read:runs` and/or
`read:proposals`; manager chat requires `chat:manager`; decisions require
`resolve:proposals`; specialists require their existing `trigger:<agent>` scope.
Controls respect these scopes and endpoints independently enforce them. A manager
chat key cannot use a model tool to bypass a missing specialist or proposal-read scope.

The store selector scopes records and supported manager read tools. Six specialist
runners currently operate across all available stores; their controls explicitly say
**Run for all stores**. Selecting a store does not scope those runs. Review response
requires a review ID, its store ID, rating (1–3), and review text; order ID is optional.
The console never creates sample reviews or claims that a selected-store run occurred.

## Text and voice contract

`POST /agent/manager/chat` accepts the existing `message`, `session_id`, and
`store_id` fields, plus fleet aliases `sessionId`, `storeId`, `audioBase64`, and
`mimeType`. Snake-case `audio_base64` and `mime_type` also work. Conflicting aliases
are rejected. Responses retain `reply` and `session_id` and add `sessionId`,
`storeId`, `transcript`, public `run_id`/`tools_used`/`proposals`, and `used_fallback`.

Provide text, audio, or both. Text takes precedence when both are provided, matching
the fleet contract. Audio requests receive a spoken reply when speech generation
succeeds. Audio is validated even when text takes precedence. Input audio is limited
to 4 MiB and accepted MIME types: WebM, Ogg, WAV, MP4, MPEG/MP3, FLAC. The browser
records at most 60 seconds. Transcription and TTS use installed Google GenAI's async
API with 45-second provider request limits. Transcription failures return a redacted
502; TTS failures preserve text with `audioError`. Native PCM is wrapped in a playable
mono, 16-bit WAV container. No raw recording is stored in proposals or run evidence.

Voice states follow actual permission, recording, request and playback events.
Mute pauses recording and disables microphone tracks. Stop releases the microphone
before processing. End, disconnect, context change, backgrounding, and page exit
cancel pending work and release tracks, players, object URLs and audio contexts.
Late permission/provider results cannot restart an ended session. Playback failure
preserves the text reply. Signal feedback uses actual audio samples and stays static
under reduced motion; there is no simulated waveform or timer-based business progress.

## Conversation history

The **Conversation history** drawer lists persisted manager conversations for the
current authenticated credential and exact selected store. “All stores” is its own
conversation scope; it does not aggregate individual-store threads. Reopen restores
public user/assistant messages and the same session ID, so the next request continues
that conversation. New conversation starts a fresh session. Completed exchanges save
on the server; opening or closing the drawer does not fabricate an archive record.

Both `GET /agent/manager/conversations?storeId=…&limit=…` and
`GET /agent/manager/conversations/{session_id}?storeId=…` require `chat:manager`.
Another credential or store cannot read a thread by guessing its session ID. Identity
is the authenticated API credential, not an individual staff login: people sharing a
key share its archive. Key rotation starts a separate archive; no migration is supplied.
The API returns public messages/title/timestamps only, never the credential hash.

Set `MANAGER_CONVERSATION_PATH` to an absolute SQLite file path outside source, on a
persistent volume when restart survival is required. Without this opt-in path, chat
still works with existing bounded process context and explicitly returns
`historySaved: false` plus `historyError`; history endpoints return redacted 503.
Disk/lock/corruption failures preserve the current text/voice reply with the same
warning. Failed provider requests do not create successful-looking archive records.

Each credential retains at most 128 recent conversations across all stores. Each
conversation retains at most 100 messages of 2,000 characters each; older messages
are trimmed. The model receives the latest ten messages, separately from that archive.
Only screened public input/transcript and assistant reply text are saved; configured
credentials and common personal data are redacted. Raw audio, speech output, private
reasoning, provider telemetry, tool arguments and proposal payloads are not archived.
User and assistant messages commit as one exchange. SQLite serializes concurrent
writers to the same local file with a five-second lock timeout; provider calls use a
context snapshot and are not distributed session transactions. File mode is 0600.

Storage is local SQLite, not a distributed Cloud Run archive: separate instance disks
have separate histories. Deployments must provision an appropriate shared persistence
strategy before claiming multi-instance conversation continuity. No delete, export,
store-proof or demo-application controls are supplied. Run records remain the service's
existing separate hash-chained public evidence.

Drawer loading/error/empty states reflect server responses. Closing, disconnecting or
changing store discards pending drawer results. Opening history ends active voice;
recording/playback/provider resources retain their existing cleanup rules. Reopening
never replays recorded audio. Keyboard Escape closes the dialog, focus remains inside
while open, and close returns focus to its opener. No archive or credential is written
to browser storage.

## Decisions and evidence

Approve/Reject records a manager decision only. It does not apply prices, send a
purchase order, activate campaigns, execute refunds, or mutate final commerce state.
Only pending proposals can change status. Repeating the same decision returns the
original record without changing its note/timestamp; a competing terminal decision
returns 409. The expiry/supersession paths remain internal.

Records show authoritative statuses, timestamps, public summaries, tool names and
proposal payload evidence. They do not expose private reasoning, provider telemetry,
raw audio, API keys, or unsupported execution controls. The UI removes sensitive
payload fields; configured API credentials should still be restricted to trusted staff.
The existing JSONL stores and decision lock are process-local: this slice does not
provide cross-process transactions or distributed decision coordination.

## Local verification

Use isolated storage and dummy credentials for UI checks without live providers,
schedulers or event consumers:

```bash
GOOGLE_API_KEY=test-not-a-real-key LLM_API_KEY=test-not-a-real-key \
OPS_PREFER_LLM=false AGENT_TRIGGER_API_KEY=test-console-key \
AGENT_TOKEN=test-agent-token BACKEND_URL=http://127.0.0.1:9 \
PROPOSAL_DATA_DIR=/tmp/masova-console/proposals \
RUN_STORE_PATH=/tmp/masova-console/runs.jsonl \
MANAGER_CONVERSATION_PATH=/tmp/masova-console/conversations.sqlite3 \
.venv/bin/uvicorn masova_agent.main:app --app-dir src \
  --host 127.0.0.1 --port 8011 --lifespan off
```

`JWT_SECRET` must also be configured as described in `config/env.example`.
Open `/console`, enter the dummy console key, and expect explicit backend/provider
unavailability. Populate isolated stores with synthetic fixtures only when inspecting
proposal/run states. Dummy responses do not establish live service integration.

```bash
GOOGLE_API_KEY=test-not-a-real-key LLM_API_KEY=test-not-a-real-key \
AGENT_TOKEN=test-agent-token OPS_PREFER_LLM=false .venv/bin/python -m pytest tests/ -q
node --test tests/test_console_voice.cjs tests/test_console_history.cjs
make lint
make hygiene
```

## Remaining consolidation capabilities

Fleet's SQLite demo backend, demo table inspector/store proof, approved-proposal
demo application hooks, store performance comparison, audit export, and showcase
are not ported in this slice. No corresponding working controls are advertised. Live specialist results require the owning backend
services; manager voice requires configured Gemini transcription/TTS access and
browser microphone/playback permissions. These integrations need separate real-service
and physical audio verification before being described as verified.
