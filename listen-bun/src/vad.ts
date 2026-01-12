/**
 * Voice Activity Detection module for claude-listen (Bun version).
 * Implements both energy-based and WebRTC VAD options.
 */

export interface VADConfig {
  silenceTimeout: number; // ms
  energyThreshold: number; // 0-1, audio energy threshold
  minSpeechFrames: number; // minimum frames to confirm speech
  frameSize: number; // samples per frame (30ms = 480 at 16kHz)
}

export type VADCallback = () => void;

const DEFAULT_CONFIG: VADConfig = {
  silenceTimeout: 1500, // 1.5 seconds
  energyThreshold: 0.01, // Adjust based on testing
  minSpeechFrames: 2,
  frameSize: 480, // 30ms at 16kHz
};

export class EnergyVAD {
  private config: VADConfig;
  private isSpeaking = false;
  private speechFrameCount = 0;
  private lastSpeechTime: number | null = null;
  private silenceTimer: ReturnType<typeof setTimeout> | null = null;

  onSpeechStart: VADCallback | null = null;
  onSpeechEnd: VADCallback | null = null;

  constructor(config: Partial<VADConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Process an audio frame and detect speech.
   * Returns true if speech is detected.
   */
  processAudio(audio: Float32Array): boolean {
    const energy = this.calculateEnergy(audio);
    const isSpeech = energy > this.config.energyThreshold;

    if (isSpeech) {
      this.handleSpeechDetected();
    } else {
      this.handleSilenceDetected();
    }

    return isSpeech;
  }

  /**
   * Calculate RMS energy of audio frame.
   */
  private calculateEnergy(audio: Float32Array): number {
    let sum = 0;
    for (let i = 0; i < audio.length; i++) {
      sum += audio[i] * audio[i];
    }
    return Math.sqrt(sum / audio.length);
  }

  private handleSpeechDetected(): void {
    this.lastSpeechTime = Date.now();
    this.speechFrameCount++;

    // Cancel silence timer
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }

    // Confirm speech start after minimum frames
    if (!this.isSpeaking && this.speechFrameCount >= this.config.minSpeechFrames) {
      this.isSpeaking = true;
      this.onSpeechStart?.();
    }
  }

  private handleSilenceDetected(): void {
    this.speechFrameCount = 0;

    if (this.isSpeaking && this.lastSpeechTime) {
      const silenceDuration = Date.now() - this.lastSpeechTime;

      if (silenceDuration >= this.config.silenceTimeout) {
        this.triggerSpeechEnd();
      } else if (!this.silenceTimer) {
        const remaining = this.config.silenceTimeout - silenceDuration;
        this.silenceTimer = setTimeout(() => this.checkSilenceTimeout(), remaining);
      }
    }
  }

  private checkSilenceTimeout(): void {
    if (this.isSpeaking && this.lastSpeechTime) {
      const silenceDuration = Date.now() - this.lastSpeechTime;
      if (silenceDuration >= this.config.silenceTimeout) {
        this.triggerSpeechEnd();
      }
    }
  }

  private triggerSpeechEnd(): void {
    this.isSpeaking = false;
    this.silenceTimer = null;
    this.speechFrameCount = 0;
    this.onSpeechEnd?.();
  }

  /**
   * Reset VAD state.
   */
  reset(): void {
    this.isSpeaking = false;
    this.lastSpeechTime = null;
    this.speechFrameCount = 0;
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }

  get speaking(): boolean {
    return this.isSpeaking;
  }
}
