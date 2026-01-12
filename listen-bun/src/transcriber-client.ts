/**
 * HTTP client for Python transcriber microservice.
 * Sends audio to Python for transcription via Parakeet MLX.
 */

export interface TranscriptionResult {
  text: string;
  language: string;
  confidence: number;
}

export interface TranscriberConfig {
  host: string;
  port: number;
}

const DEFAULT_CONFIG: TranscriberConfig = {
  host: "localhost",
  port: 8765,
};

export class TranscriberClient {
  private config: TranscriberConfig;
  private baseUrl: string;

  constructor(config: Partial<TranscriberConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.baseUrl = `http://${this.config.host}:${this.config.port}`;
  }

  /**
   * Transcribe audio data.
   */
  async transcribe(audio: Float32Array): Promise<TranscriptionResult> {
    if (audio.length === 0) {
      return { text: "", language: "", confidence: 0 };
    }

    // Convert Float32Array to base64 for transmission
    const buffer = Buffer.from(audio.buffer);
    const base64Audio = buffer.toString("base64");

    try {
      const response = await fetch(`${this.baseUrl}/transcribe`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          audio: base64Audio,
          sample_rate: 16000,
        }),
      });

      if (!response.ok) {
        throw new Error(`Transcription failed: ${response.status}`);
      }

      const result = await response.json() as TranscriptionResult;
      return result;
    } catch (error) {
      console.error("Transcription error:", error);
      return { text: "", language: "", confidence: 0 };
    }
  }

  /**
   * Check if transcriber service is available.
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: "GET",
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}
