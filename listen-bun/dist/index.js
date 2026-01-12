#!/usr/bin/env bun
// @bun

// src/audio.ts
var {spawn } = globalThis.Bun;
var DEFAULT_CONFIG = {
  sampleRate: 16000,
  channels: 1,
  bitDepth: 16
};

class AudioCapture {
  config;
  process = null;
  isRunning = false;
  onAudio;
  constructor(onAudio, config = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.onAudio = onAudio;
  }
  async start() {
    if (this.isRunning)
      return;
    this.process = spawn(["rec", "-q", "-t", "raw", "-b", "16", "-e", "signed-integer", "-r", String(this.config.sampleRate), "-c", "1", "-"], {
      stdout: "pipe",
      stderr: "pipe"
    });
    this.isRunning = true;
    this.readAudioStream();
  }
  async readAudioStream() {
    if (!this.process?.stdout)
      return;
    const reader = this.process.stdout.getReader();
    const bytesPerSample = this.config.bitDepth / 8;
    let buffer = new Uint8Array(0);
    try {
      while (this.isRunning) {
        const { done, value } = await reader.read();
        if (done)
          break;
        const newBuffer = new Uint8Array(buffer.length + value.length);
        newBuffer.set(buffer);
        newBuffer.set(value, buffer.length);
        buffer = newBuffer;
        const frameSize = 480 * bytesPerSample;
        while (buffer.length >= frameSize) {
          const frameBytes = buffer.slice(0, frameSize);
          buffer = buffer.slice(frameSize);
          const int16View = new Int16Array(frameBytes.buffer, frameBytes.byteOffset, frameBytes.length / 2);
          const float32 = new Float32Array(int16View.length);
          for (let i = 0;i < int16View.length; i++) {
            float32[i] = int16View[i] / 32768;
          }
          this.onAudio(float32);
        }
      }
    } catch (error) {
      console.error("Audio stream error:", error);
    }
  }
  stop() {
    this.isRunning = false;
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
  }
  async restart() {
    this.stop();
    await Bun.sleep(100);
    await this.start();
  }
  get running() {
    return this.isRunning;
  }
}

// src/vad.ts
var DEFAULT_CONFIG2 = {
  silenceTimeout: 1500,
  energyThreshold: 0.01,
  minSpeechFrames: 2,
  frameSize: 480
};

class EnergyVAD {
  config;
  isSpeaking = false;
  speechFrameCount = 0;
  lastSpeechTime = null;
  silenceTimer = null;
  onSpeechStart = null;
  onSpeechEnd = null;
  constructor(config = {}) {
    this.config = { ...DEFAULT_CONFIG2, ...config };
  }
  processAudio(audio) {
    const energy = this.calculateEnergy(audio);
    const isSpeech = energy > this.config.energyThreshold;
    if (isSpeech) {
      this.handleSpeechDetected();
    } else {
      this.handleSilenceDetected();
    }
    return isSpeech;
  }
  calculateEnergy(audio) {
    let sum = 0;
    for (let i = 0;i < audio.length; i++) {
      sum += audio[i] * audio[i];
    }
    return Math.sqrt(sum / audio.length);
  }
  handleSpeechDetected() {
    this.lastSpeechTime = Date.now();
    this.speechFrameCount++;
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
    if (!this.isSpeaking && this.speechFrameCount >= this.config.minSpeechFrames) {
      this.isSpeaking = true;
      this.onSpeechStart?.();
    }
  }
  handleSilenceDetected() {
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
  checkSilenceTimeout() {
    if (this.isSpeaking && this.lastSpeechTime) {
      const silenceDuration = Date.now() - this.lastSpeechTime;
      if (silenceDuration >= this.config.silenceTimeout) {
        this.triggerSpeechEnd();
      }
    }
  }
  triggerSpeechEnd() {
    this.isSpeaking = false;
    this.silenceTimer = null;
    this.speechFrameCount = 0;
    this.onSpeechEnd?.();
  }
  reset() {
    this.isSpeaking = false;
    this.lastSpeechTime = null;
    this.speechFrameCount = 0;
    if (this.silenceTimer) {
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }
  get speaking() {
    return this.isSpeaking;
  }
}

// src/transcriber-client.ts
var DEFAULT_CONFIG3 = {
  host: "localhost",
  port: 8765
};

class TranscriberClient {
  config;
  baseUrl;
  constructor(config = {}) {
    this.config = { ...DEFAULT_CONFIG3, ...config };
    this.baseUrl = `http://${this.config.host}:${this.config.port}`;
  }
  async transcribe(audio) {
    if (audio.length === 0) {
      return { text: "", language: "", confidence: 0 };
    }
    const buffer = Buffer.from(audio.buffer);
    const base64Audio = buffer.toString("base64");
    try {
      const response = await fetch(`${this.baseUrl}/transcribe`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          audio: base64Audio,
          sample_rate: 16000
        })
      });
      if (!response.ok) {
        throw new Error(`Transcription failed: ${response.status}`);
      }
      const result = await response.json();
      return result;
    } catch (error) {
      console.error("Transcription error:", error);
      return { text: "", language: "", confidence: 0 };
    }
  }
  async healthCheck() {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: "GET"
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

// src/index.ts
var SILENCE_TIMEOUT = parseInt(process.env.CLAUDE_LISTEN_SILENCE_TIMEOUT || "1500");
var TRANSCRIBER_HOST = process.env.CLAUDE_LISTEN_TRANSCRIBER_HOST || "localhost";
var TRANSCRIBER_PORT = parseInt(process.env.CLAUDE_LISTEN_TRANSCRIBER_PORT || "8765");
var isListening = false;
var audioBuffer = [];
var lastTranscription = null;
var transcriptionReady = false;
var pendingResolve = null;
var audio = null;
var vad = null;
var transcriber = new TranscriberClient({
  host: TRANSCRIBER_HOST,
  port: TRANSCRIBER_PORT
});
var isTTSSpeaking = false;
function onAudioChunk(chunk) {
  if (!isListening || !vad)
    return;
  if (isTTSSpeaking)
    return;
  audioBuffer.push(chunk);
  vad.processAudio(chunk);
}
function onSpeechStart() {
  audioBuffer = [];
  console.error("[VAD] Speech started");
}
async function onSpeechEnd() {
  console.error("[VAD] Speech ended, transcribing...");
  if (audioBuffer.length === 0)
    return;
  const totalLength = audioBuffer.reduce((acc, chunk) => acc + chunk.length, 0);
  const fullAudio = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of audioBuffer) {
    fullAudio.set(chunk, offset);
    offset += chunk.length;
  }
  audioBuffer = [];
  const startTime = Date.now();
  lastTranscription = await transcriber.transcribe(fullAudio);
  const elapsed = Date.now() - startTime;
  console.error(`[Transcription] "${lastTranscription.text}" (${elapsed}ms)`);
  transcriptionReady = true;
  if (pendingResolve) {
    pendingResolve(lastTranscription);
    pendingResolve = null;
  }
}
function initializeComponents() {
  if (!audio) {
    audio = new AudioCapture(onAudioChunk);
  }
  if (!vad) {
    vad = new EnergyVAD({
      silenceTimeout: SILENCE_TIMEOUT
    });
    vad.onSpeechStart = onSpeechStart;
    vad.onSpeechEnd = onSpeechEnd;
  }
}
async function startListening() {
  if (isListening) {
    return "Already listening.";
  }
  try {
    initializeComponents();
    isListening = true;
    transcriptionReady = false;
    await audio?.start();
    return `Listening started. Speak now - I'll transcribe after ${SILENCE_TIMEOUT}ms of silence.`;
  } catch (error) {
    isListening = false;
    return `Error starting listening: ${error}`;
  }
}
function stopListening() {
  if (!isListening) {
    return "Not currently listening.";
  }
  isListening = false;
  audio?.stop();
  vad?.reset();
  return "Listening stopped.";
}
async function getTranscription(wait = true, timeout = 15000) {
  if (wait) {
    transcriptionReady = false;
    const result = await Promise.race([
      new Promise((resolve) => {
        pendingResolve = resolve;
      }),
      new Promise((resolve) => setTimeout(() => resolve(null), timeout))
    ]);
    if (!result) {
      return "[Timeout: No speech detected]";
    }
    return result.text;
  }
  if (!lastTranscription) {
    return "[No transcription available]";
  }
  return lastTranscription.text;
}
function listeningStatus() {
  const parts = [
    `Listening: ${isListening ? "Yes" : "No"}`,
    `Speaking (TTS): ${isTTSSpeaking ? "Yes" : "No"}`,
    `Transcriber: parakeet-mlx`,
    `VAD: Energy-based`,
    `Silence timeout: ${SILENCE_TIMEOUT}ms`
  ];
  if (vad) {
    parts.push(`Speech detected: ${vad.speaking ? "Yes" : "No"}`);
  }
  if (lastTranscription) {
    const preview = lastTranscription.text.slice(0, 50);
    parts.push(`Last transcription: "${preview}${lastTranscription.text.length > 50 ? "..." : ""}"`);
    parts.push(`Language: ${lastTranscription.language}`);
  }
  return parts.join(`
`);
}
async function restartAudio() {
  if (!isListening) {
    return "Not currently listening. Start listening first.";
  }
  try {
    await audio?.restart();
    vad?.reset();
    return "Audio capture restarted. Device change should now be handled.";
  } catch (error) {
    return `Error restarting audio: ${error}`;
  }
}
async function transcribeNow() {
  if (audioBuffer.length === 0) {
    return "[No audio buffered]";
  }
  const totalLength = audioBuffer.reduce((acc, chunk) => acc + chunk.length, 0);
  const fullAudio = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of audioBuffer) {
    fullAudio.set(chunk, offset);
    offset += chunk.length;
  }
  audioBuffer = [];
  lastTranscription = await transcriber.transcribe(fullAudio);
  return lastTranscription.text || "[Transcription failed]";
}
async function handleMCPRequest(request) {
  const { method, params, id } = request;
  if (method === "tools/list") {
    return {
      jsonrpc: "2.0",
      id,
      result: {
        tools: [
          {
            name: "start_listening",
            description: "Start continuous listening mode with VAD.",
            inputSchema: { type: "object", properties: {} }
          },
          {
            name: "stop_listening",
            description: "Stop listening mode.",
            inputSchema: { type: "object", properties: {} }
          },
          {
            name: "get_transcription",
            description: "Get the last transcription result.",
            inputSchema: {
              type: "object",
              properties: {
                wait: { type: "boolean", default: true },
                timeout: { type: "number", default: 15 }
              }
            }
          },
          {
            name: "listening_status",
            description: "Get current listening status.",
            inputSchema: { type: "object", properties: {} }
          },
          {
            name: "restart_audio",
            description: "Restart audio capture for device changes.",
            inputSchema: { type: "object", properties: {} }
          },
          {
            name: "transcribe_now",
            description: "Immediately transcribe buffered audio.",
            inputSchema: { type: "object", properties: {} }
          }
        ]
      }
    };
  }
  if (method === "tools/call") {
    const { name, arguments: args } = params;
    let result;
    switch (name) {
      case "start_listening":
        result = await startListening();
        break;
      case "stop_listening":
        result = stopListening();
        break;
      case "get_transcription":
        result = await getTranscription(args?.wait ?? true, (args?.timeout ?? 15) * 1000);
        break;
      case "listening_status":
        result = listeningStatus();
        break;
      case "restart_audio":
        result = await restartAudio();
        break;
      case "transcribe_now":
        result = await transcribeNow();
        break;
      default:
        return {
          jsonrpc: "2.0",
          id,
          error: { code: -32601, message: `Unknown tool: ${name}` }
        };
    }
    return {
      jsonrpc: "2.0",
      id,
      result: { content: [{ type: "text", text: result }] }
    };
  }
  if (method === "initialize") {
    return {
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "claude-listen-bun", version: "1.0.0" }
      }
    };
  }
  return {
    jsonrpc: "2.0",
    id,
    error: { code: -32601, message: `Method not found: ${method}` }
  };
}
async function main() {
  console.error("[claude-listen-bun] Starting MCP server...");
  const decoder = new TextDecoder;
  let buffer = "";
  for await (const chunk of Bun.stdin.stream()) {
    buffer += decoder.decode(chunk, { stream: true });
    while (true) {
      const newlineIndex = buffer.indexOf(`
`);
      if (newlineIndex === -1)
        break;
      const line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);
      if (line.trim()) {
        try {
          const request = JSON.parse(line);
          const response = await handleMCPRequest(request);
          console.log(JSON.stringify(response));
        } catch (error) {
          console.error("[Error parsing request]", error);
        }
      }
    }
  }
}
main().catch(console.error);
