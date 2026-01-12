/**
 * Audio capture module for claude-listen (Bun version).
 * Uses native audio capture via subprocess or FFI.
 */

import { spawn, type Subprocess } from "bun";

export interface AudioConfig {
  sampleRate: number;
  channels: number;
  bitDepth: number;
}

export type AudioCallback = (chunk: Float32Array) => void;

const DEFAULT_CONFIG: AudioConfig = {
  sampleRate: 16000,
  channels: 1,
  bitDepth: 16,
};

export class AudioCapture {
  private config: AudioConfig;
  private process: Subprocess<"ignore", "pipe", "pipe"> | null = null;
  private isRunning = false;
  private onAudio: AudioCallback;

  constructor(onAudio: AudioCallback, config: Partial<AudioConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.onAudio = onAudio;
  }

  /**
   * Start audio capture using sox/rec command.
   */
  async start(): Promise<void> {
    if (this.isRunning) return;

    // Use sox/rec for audio capture (cross-platform)
    // On macOS, this uses Core Audio
    this.process = spawn(["rec", "-q", "-t", "raw", "-b", "16", "-e", "signed-integer", "-r", String(this.config.sampleRate), "-c", "1", "-"], {
      stdout: "pipe",
      stderr: "pipe",
    });

    this.isRunning = true;
    this.readAudioStream();
  }

  /**
   * Read audio stream continuously.
   */
  private async readAudioStream(): Promise<void> {
    if (!this.process?.stdout) return;

    const reader = this.process.stdout.getReader();
    const bytesPerSample = this.config.bitDepth / 8;
    let buffer = new Uint8Array(0);

    try {
      while (this.isRunning) {
        const { done, value } = await reader.read();
        if (done) break;

        // Accumulate data
        const newBuffer = new Uint8Array(buffer.length + value.length);
        newBuffer.set(buffer);
        newBuffer.set(value, buffer.length);
        buffer = newBuffer;

        // Process complete frames (480 samples = 30ms at 16kHz)
        const frameSize = 480 * bytesPerSample;
        while (buffer.length >= frameSize) {
          const frameBytes = buffer.slice(0, frameSize);
          buffer = buffer.slice(frameSize);

          // Convert Int16 to Float32
          const int16View = new Int16Array(frameBytes.buffer, frameBytes.byteOffset, frameBytes.length / 2);
          const float32 = new Float32Array(int16View.length);
          for (let i = 0; i < int16View.length; i++) {
            float32[i] = int16View[i] / 32768.0;
          }

          this.onAudio(float32);
        }
      }
    } catch (error) {
      console.error("Audio stream error:", error);
    }
  }

  /**
   * Stop audio capture.
   */
  stop(): void {
    this.isRunning = false;
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
  }

  /**
   * Restart audio capture (useful after device change).
   */
  async restart(): Promise<void> {
    this.stop();
    await Bun.sleep(100);
    await this.start();
  }

  get running(): boolean {
    return this.isRunning;
  }
}
