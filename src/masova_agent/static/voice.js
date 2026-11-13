/* Transient manager audio. State follows media/provider events, never elapsed progress. */
class VoiceSession {
  constructor(env, onState, onSignal) {
    this.env = env; this.onState = onState; this.onSignal = onSignal;
    this.generation = 0; this.stream = null; this.recorder = null;
    this.audio = null; this.url = null; this.context = null; this.frame = null;
    this.controller = null; this.timer = null; this.chunks = []; this.size = 0;
    this.muted = false; this.state = 'Ready'; this.playbackDone = null; this.recordingDone = null;
  }
  setState(state) { this.state = state; this.onState(state); }
  release() {
    this.env.clearTimeout(this.timer); this.timer = null;
    if (this.recorder) {
      this.recorder.onstop = null; this.recorder.ondataavailable = null;
      this.recorder.onerror = null;
      if (this.recorder.state !== 'inactive') this.recorder.stop();
    }
    this.recorder = null;
    this.stream?.getTracks().forEach(track => track.stop()); this.stream = null;
    if (this.audio) {
      this.audio.onplaying = null; this.audio.onended = null; this.audio.onerror = null;
      this.audio.pause(); this.audio.removeAttribute('src'); this.audio.load();
    }
    this.audio = null;
    if (this.url) this.env.revokeObjectURL(this.url); this.url = null;
    if (this.frame !== null) this.env.cancelFrame?.(this.frame); this.frame = null;
    this.context?.close().catch(() => {}); this.context = null;
    this.onSignal(0); this.chunks = []; this.size = 0;
    this.playbackDone?.(); this.playbackDone = null;
    this.recordingDone?.(); this.recordingDone = null;
  }
  end() {
    this.generation++; this.controller?.abort(); this.controller = null;
    this.release(); this.setState('Ended');
  }
  fail(message) {
    this.generation++; this.controller?.abort(); this.controller = null;
    this.release(); this.setState(message);
  }
  watch(source, kind) {
    if (!this.env.makeContext) return;
    try {
      const context = this.env.makeContext(); this.context = context;
      const analyser = context.createAnalyser(); analyser.fftSize = 256;
      const input = kind === 'mic' ? context.createMediaStreamSource(source)
        : context.createMediaElementSource(source);
      input.connect(analyser);
      if (kind === 'playback') analyser.connect(context.destination);
      const data = new Uint8Array(analyser.fftSize);
      const sample = () => {
        if (this.context !== context) return;
        if (this.env.visualsEnabled() && !this.muted) {
          analyser.getByteTimeDomainData(data);
          const power = data.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0);
          this.onSignal(Math.min(1, Math.sqrt(power / data.length) * 4));
        } else this.onSignal(0);
        this.frame = this.env.requestFrame(sample);
      };
      this.frame = this.env.requestFrame(sample);
    } catch { this.onSignal(0); }
  }
  async start(send) {
    this.end(); const generation = this.generation;
    this.muted = false; this.send = send; this.setState('Requesting microphone');
    try {
      const stream = await this.env.getUserMedia({ audio: true });
      if (generation !== this.generation) {
        stream.getTracks().forEach(track => track.stop()); return;
      }
      this.stream = stream;
      const types = ['audio/webm', 'audio/mp4', 'audio/ogg'];
      const mime = types.find(type => this.env.MediaRecorder.isTypeSupported?.(type));
      this.recorder = new this.env.MediaRecorder(stream, mime ? { mimeType: mime } : {});
      this.recorder.ondataavailable = event => {
        if (!event.data.size || generation !== this.generation) return;
        this.size += event.data.size;
        if (this.size > 4 * 1024 * 1024) {
          this.fail('Recording too large. Record a shorter request.'); return;
        }
        this.chunks.push(event.data);
      };
      this.recorder.onerror = () => this.fail('Recording failed. Retry or type a message.');
      this.recorder.start(250); this.setState('Listening'); this.watch(stream, 'mic');
      this.timer = this.env.setTimeout(() => {
        this.fail('Recording reached 60 seconds. Record a shorter request.');
      }, 60000);
    } catch {
      if (generation === this.generation) {
        this.fail('Microphone unavailable. Allow access, then retry or type a message.');
      }
    }
  }
  mute() {
    if (!this.recorder || this.recorder.state === 'inactive') return;
    this.muted = !this.muted;
    this.stream.getTracks().forEach(track => { track.enabled = !this.muted; });
    if (this.muted) { this.recorder.pause(); this.onSignal(0); this.setState('Muted'); }
    else { this.recorder.resume(); this.setState('Listening'); }
  }
  async stop() {
    const recorder = this.recorder, generation = this.generation;
    if (!recorder || recorder.state === 'inactive') return;
    await new Promise(resolve => {
      this.recordingDone = resolve; recorder.onstop = resolve; recorder.stop();
    });
    if (generation !== this.generation) return;
    const recording = new this.env.Blob(this.chunks, { type: recorder.mimeType });
    this.release(); this.muted = false;
    if (!recording.size) { this.fail('No recording received. Retry or type a message.'); return; }
    this.setState('Processing'); this.controller = new AbortController();
    this.timer = this.env.setTimeout(() => this.controller?.abort(), 120000);
    try {
      const response = await this.send(recording, this.controller.signal);
      if (generation !== this.generation) return;
      this.env.clearTimeout(this.timer); this.timer = null; this.controller = null;
      if (response.audioError) { this.setState(response.audioError); return; }
      if (!response.audioBase64) { this.setState('Ready'); return; }
      const bytes = Uint8Array.from(atob(response.audioBase64), value => value.charCodeAt(0));
      this.url = this.env.createObjectURL(new this.env.Blob([bytes], { type: response.mimeType }));
      const audio = this.env.makeAudio(this.url); this.audio = audio;
      await new Promise((resolve, reject) => {
        this.playbackDone = resolve;
        audio.onplaying = () => {
          if (generation !== this.generation) return;
          this.setState('Speaking'); this.watch(audio, 'playback');
        };
        audio.onended = resolve;
        audio.onerror = () => reject(new Error('Audio playback failed. Text reply preserved.'));
        Promise.resolve(audio.play()).catch(() => {
          reject(new Error('Audio playback unavailable. Text reply preserved.'));
        });
      });
      if (generation === this.generation) { this.release(); this.setState('Ready'); }
    } catch (error) {
      if (generation === this.generation) {
        this.fail(error.name === 'AbortError' ? 'Request timed out. Retry or type a message.'
          : error.message || 'Voice unavailable. Retry or type a message.');
      }
    }
  }
}
if (typeof module !== 'undefined') module.exports = VoiceSession;
else globalThis.MaSoVaVoice = VoiceSession;
