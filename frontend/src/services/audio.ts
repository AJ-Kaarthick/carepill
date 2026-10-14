class SoundSynthesizer {
  private ctx: AudioContext | null = null;
  private isMuted: boolean = false;
  private volume: number = 0.8; // 0.0 to 1.0
  private activeTimeouts: number[] = [];

  constructor() {
    // Check localStorage for persisted preferences if in browser
    try {
      if (typeof window !== 'undefined') {
        const savedMute = localStorage.getItem('carepill_audio_muted');
        if (savedMute !== null) this.isMuted = savedMute === 'true';
        const savedVol = localStorage.getItem('carepill_audio_volume');
        if (savedVol !== null) this.volume = parseFloat(savedVol) || 0.8;
      }
    } catch {
      // Ignore storage access errors
    }
  }

  public getMuted(): boolean {
    return this.isMuted;
  }

  public setMuted(muted: boolean) {
    this.isMuted = muted;
    try {
      localStorage.setItem('carepill_audio_muted', String(muted));
    } catch {}
    if (muted) {
      this.stopAllSounds();
    }
  }

  public getVolume(): number {
    return this.volume;
  }

  public setVolume(vol: number) {
    this.volume = Math.max(0, Math.min(1, vol));
    try {
      localStorage.setItem('carepill_audio_volume', String(this.volume));
    } catch {}
  }

  public stopAllSounds() {
    this.activeTimeouts.forEach((tid) => clearTimeout(tid));
    this.activeTimeouts = [];
    if (this.ctx && this.ctx.state === 'running') {
      try {
        // Suspend context briefly to stop running nodes
        this.ctx.suspend().then(() => {
          if (!this.isMuted && this.ctx) {
            this.ctx.resume();
          }
        });
      } catch {}
    }
  }

  private initCtx() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended' && !this.isMuted) {
      this.ctx.resume();
    }
  }

  private schedule(fn: () => void, delayMs: number) {
    const tid = window.setTimeout(() => {
      this.activeTimeouts = this.activeTimeouts.filter((t) => t !== tid);
      fn();
    }, delayMs);
    this.activeTimeouts.push(tid);
  }

  playTone(freq: number, durationSec: number, type: OscillatorType = 'sine', gainVal = 0.15) {
    if (this.isMuted || this.volume <= 0.01) return;
    try {
      this.initCtx();
      if (!this.ctx) return;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      const effectiveGain = gainVal * this.volume;
      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);

      gain.gain.setValueAtTime(effectiveGain, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, this.ctx.currentTime + durationSec);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + durationSec);
    } catch {
      // Audio playback might be constrained before user interaction
    }
  }

  // Exact buzzer cues corresponding to device firmware table
  playPreDoseReminder() {
    this.playTone(1000, 0.12, 'sine', 0.14);
    this.schedule(() => this.playTone(1000, 0.15, 'sine', 0.14), 200);
  }

  playDispensingTick() {
    this.playTone(2000, 0.05, 'triangle', 0.1);
  }

  playCollectionReminder() {
    // 3 rapid reminder beeps
    for (let i = 0; i < 3; i++) {
      this.schedule(() => this.playTone(1500, 0.14, 'square', 0.12), i * 220);
    }
  }

  playPickupChime() {
    // Ascending cheerful chime
    this.playTone(1046.5, 0.12, 'sine', 0.15); // C6
    this.schedule(() => this.playTone(1318.5, 0.15, 'sine', 0.15), 130); // E6
    this.schedule(() => this.playTone(1567.98, 0.25, 'sine', 0.18), 280); // G6
  }

  playUrgentEscalation() {
    // Alternating urgent siren
    for (let i = 0; i < 4; i++) {
      this.schedule(() => this.playTone(i % 2 === 0 ? 2200 : 880, 0.18, 'sawtooth', 0.16), i * 240);
    }
  }

  playFaultAlert() {
    this.playTone(440, 0.6, 'sawtooth', 0.2);
  }
}

export const sound = new SoundSynthesizer();
