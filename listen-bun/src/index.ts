#!/usr/bin/env bun
/**
 * Claude-Listen MCP Server (Bun version)
 * Fast speech-to-text server with VAD and Parakeet transcription.
 */

import { AudioCapture } from "./audio";
import { EnergyVAD } from "./vad";
import { TranscriberClient, type TranscriptionResult } from "./transcriber-client";

// Configuration
const SILENCE_TIMEOUT = parseInt(process.env.CLAUDE_LISTEN_SILENCE_TIMEOUT || "1500");
const TRANSCRIBER_HOST = process.env.CLAUDE_LISTEN_TRANSCRIBER_HOST || "localhost";
const TRANSCRIBER_PORT = parseInt(process.env.CLAUDE_LISTEN_TRANSCRIBER_PORT || "8765");

// Global state
let isListening = false;
let audioBuffer: Float32Array[] = [];
let lastTranscription: TranscriptionResult | null = null;
let transcriptionReady = false;
let pendingResolve: ((value: TranscriptionResult | null) => void) | null = null;

// Components
let audio: AudioCapture | null = null;
let vad: EnergyVAD | null = null;
const transcriber = new TranscriberClient({
  host: TRANSCRIBER_HOST,
  port: TRANSCRIBER_PORT,
});

// Shared coordination with TTS (via file-based IPC or HTTP)
let isTTSSpeaking = false;

function onAudioChunk(chunk: Float32Array): void {
  if (!isListening || !vad) return;

  // Skip audio while TTS is speaking
  if (isTTSSpeaking) return;

  // Add to buffer
  audioBuffer.push(chunk);

  // Process with VAD
  vad.processAudio(chunk);
}

function onSpeechStart(): void {
  // Clear buffer
  audioBuffer = [];

  // TODO: Signal TTS to stop (interrupt)
  console.error("[VAD] Speech started");
}

async function onSpeechEnd(): Promise<void> {
  console.error("[VAD] Speech ended, transcribing...");

  if (audioBuffer.length === 0) return;

  // Concatenate audio buffer
  const totalLength = audioBuffer.reduce((acc, chunk) => acc + chunk.length, 0);
  const fullAudio = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of audioBuffer) {
    fullAudio.set(chunk, offset);
    offset += chunk.length;
  }
  audioBuffer = [];

  // Transcribe
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

function initializeComponents(): void {
  if (!audio) {
    audio = new AudioCapture(onAudioChunk);
  }

  if (!vad) {
    vad = new EnergyVAD({
      silenceTimeout: SILENCE_TIMEOUT,
    });
    vad.onSpeechStart = onSpeechStart;
    vad.onSpeechEnd = onSpeechEnd;
  }
}

// MCP Tool implementations
async function startListening(): Promise<string> {
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

function stopListening(): string {
  if (!isListening) {
    return "Not currently listening.";
  }

  isListening = false;
  audio?.stop();
  vad?.reset();

  return "Listening stopped.";
}

async function getTranscription(wait: boolean = true, timeout: number = 15000): Promise<string> {
  if (wait) {
    transcriptionReady = false;

    // Wait for transcription with timeout
    const result = await Promise.race([
      new Promise<TranscriptionResult | null>((resolve) => {
        pendingResolve = resolve;
      }),
      new Promise<null>((resolve) => setTimeout(() => resolve(null), timeout)),
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

function listeningStatus(): string {
  const parts = [
    `Listening: ${isListening ? "Yes" : "No"}`,
    `Speaking (TTS): ${isTTSSpeaking ? "Yes" : "No"}`,
    `Transcriber: parakeet-mlx`,
    `VAD: Energy-based`,
    `Silence timeout: ${SILENCE_TIMEOUT}ms`,
  ];

  if (vad) {
    parts.push(`Speech detected: ${vad.speaking ? "Yes" : "No"}`);
  }

  if (lastTranscription) {
    const preview = lastTranscription.text.slice(0, 50);
    parts.push(`Last transcription: "${preview}${lastTranscription.text.length > 50 ? "..." : ""}"`);
    parts.push(`Language: ${lastTranscription.language}`);
  }

  return parts.join("\n");
}

async function restartAudio(): Promise<string> {
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

async function transcribeNow(): Promise<string> {
  if (audioBuffer.length === 0) {
    return "[No audio buffered]";
  }

  // Concatenate and transcribe immediately
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

// MCP Server using stdio
async function handleMCPRequest(request: any): Promise<any> {
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
            inputSchema: { type: "object", properties: {} },
          },
          {
            name: "stop_listening",
            description: "Stop listening mode.",
            inputSchema: { type: "object", properties: {} },
          },
          {
            name: "get_transcription",
            description: "Get the last transcription result.",
            inputSchema: {
              type: "object",
              properties: {
                wait: { type: "boolean", default: true },
                timeout: { type: "number", default: 15 },
              },
            },
          },
          {
            name: "listening_status",
            description: "Get current listening status.",
            inputSchema: { type: "object", properties: {} },
          },
          {
            name: "restart_audio",
            description: "Restart audio capture for device changes.",
            inputSchema: { type: "object", properties: {} },
          },
          {
            name: "transcribe_now",
            description: "Immediately transcribe buffered audio.",
            inputSchema: { type: "object", properties: {} },
          },
        ],
      },
    };
  }

  if (method === "tools/call") {
    const { name, arguments: args } = params;
    let result: string;

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
          error: { code: -32601, message: `Unknown tool: ${name}` },
        };
    }

    return {
      jsonrpc: "2.0",
      id,
      result: { content: [{ type: "text", text: result }] },
    };
  }

  if (method === "initialize") {
    return {
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: "claude-listen-bun", version: "1.0.0" },
      },
    };
  }

  return {
    jsonrpc: "2.0",
    id,
    error: { code: -32601, message: `Method not found: ${method}` },
  };
}

// Main loop - read from stdin, write to stdout
async function main() {
  console.error("[claude-listen-bun] Starting MCP server...");

  const decoder = new TextDecoder();
  let buffer = "";

  for await (const chunk of Bun.stdin.stream()) {
    buffer += decoder.decode(chunk, { stream: true });

    // Process complete JSON-RPC messages
    while (true) {
      const newlineIndex = buffer.indexOf("\n");
      if (newlineIndex === -1) break;

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
