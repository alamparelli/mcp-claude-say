# Module: Listen STT Module  
Last scanned: 2026-01-29T14:30:00Z
Source files: 8

## Main STT Server

### FastMCP("claude-listen") - listen/mcp_server.py:32
Main STT MCP server with push-to-talk functionality.

#### Global State
- `_transcription_ready` :36 - Threading event for transcription completion
- `_last_transcription` :37 - Most recent transcription result
- `_current_status` :38 - Current state (ready/recording/transcribing)

#### Callback Functions
- `_on_transcription_ready(text)` :41 - Called when transcription completes
- `_ptt_start_recording()` :50 - PTT key press handler, stops TTS and starts recording
- `_ptt_stop_recording()` :65 - PTT key release handler, stops and transcribes

## MCP Tools

### start_ptt_mode(key) - listen/mcp_server.py:75
Starts PTT with hotkey toggle. Creates PTTController with callbacks.

### stop_ptt_mode() - listen/mcp_server.py:107
Stops PTT and releases microphone via destroy functions.

### get_ptt_status() - listen/mcp_server.py:127
Returns current PTT state (inactive/ready/recording/transcribing).

### interrupt_conversation(reason) - listen/mcp_server.py:138
Stops TTS and PTT cleanly. Idempotent for typed input interruption.

### get_segment_transcription(wait, timeout) - listen/mcp_server.py:168
Gets transcription with optional blocking wait. Returns status or text.

## Audio Capture

### AudioCapture - listen/audio.py:21
Real-time microphone capture with sounddevice.

#### Configuration
- `SAMPLE_RATE = 16000` :29 - Whisper-compatible sample rate
- `CHANNELS = 1` :30 - Mono audio
- `BLOCK_SIZE = 512` :32 - ~32ms chunks at 16kHz

#### Methods  
- `start()` :90 - Opens microphone stream
- `stop()` :116 - Closes stream and releases microphone
- `get_buffer()` :133 - Returns concatenated audio data
- `clear_buffer()` :148 - Empties audio buffer
- `_audio_callback(indata, frames, time, status)` :70 - Sounddevice callback

#### Singleton Functions
- `get_capture()` :194 - Returns global AudioCapture instance
- `destroy_capture()` :202 - Destroys instance and releases mic

## Push-to-Talk Recording

### SimplePTTRecorder - listen/simple_ptt.py:26
Simple PTT recorder without VAD. Records between start/stop calls.

#### Methods
- `start()` :113 - Starts recording audio
- `stop()` :126 - Stops recording and transcribes
- `_get_transcriber()` :62 - Lazy loads Parakeet or SpeechAnalyzer
- `clear()` :179 - Clears last recording and file

#### Properties
- `is_recording` :104 - Current recording state
- `last_transcription` :109 - Most recent transcription result

#### Singleton Functions
- `get_simple_ptt(callback)` :191 - Returns global SimplePTTRecorder
- `destroy_simple_ptt()` :201 - Destroys instance and releases mic

## Hotkey Control

### PTTController - listen/ptt_controller.py:80
Global hotkey detection with pynput for PTT toggle functionality.

#### Configuration
- `PTTConfig` :39 - Configuration with key and callbacks
- `PTTState` :32 - State enum (IDLE/LISTENING/RECORDING)
- `KEY_MAP` :52 - Mapping of key strings to pynput keys

#### Methods
- `start()` :239 - Starts keyboard listener
- `stop()` :265 - Stops listener and cleanup
- `_on_key_press(key)` :173 - Handles key press events
- `_on_key_release(key)` :225 - Handles key release events
- `_check_combo()` :163 - Validates combo key state

#### Key Support
- Single keys: cmd_l, cmd_r, alt_l, alt_r, ctrl_l, ctrl_r, shift_l, shift_r
- Function keys: f13, f14, f15, space
- Combos: modifier+char (e.g., cmd_r+m)

#### Singleton Functions
- `get_ptt_controller()` :305 - Returns global PTTController
- `create_ptt_controller(config)` :310 - Creates with config
- `destroy_ptt_controller()` :317 - Stops and destroys

## Transcriber Interface

### BaseTranscriber - listen/transcriber_base.py:18
Abstract base class for speech-to-text engines.

#### Methods
- `transcribe(audio, language)` :24 - Main transcription method
- `transcribe_streaming(audio, language)` :42 - Fast streaming variant

#### Properties  
- `name` :62 - Transcriber name identifier
- `supports_streaming` :68 - Streaming capability flag

### TranscriptionResult - listen/transcriber_base.py:11
Named tuple with text, language, and confidence fields.

## Parakeet Transcriber

### ParakeetTranscriber - listen/parakeet_transcriber.py:14
Speech-to-text using Parakeet MLX for Apple Silicon.

#### Configuration
- `DEFAULT_MODEL = "mlx-community/parakeet-tdt-0.6b-v3"` :21

#### Methods
- `transcribe(audio, language)` :50 - Main transcription via temp file
- `transcribe_streaming(audio, language)` :97 - Same as transcribe
- `_load_model()` :37 - Downloads and loads Parakeet model

#### Singleton Function
- `get_parakeet_transcriber()` :122 - Returns global ParakeetTranscriber

## SpeechAnalyzer Transcriber

### SpeechAnalyzerTranscriber - listen/speechanalyzer_transcriber.py:17
Apple native STT for macOS 26+ via CLI wrapper.

#### Configuration  
- `DEFAULT_CLI_PATH` :26 - Path to apple-speechanalyzer-cli binary

#### Methods
- `transcribe(audio, language)` :64 - Transcription via CLI subprocess
- `transcribe_streaming(audio, language)` :147 - Same as transcribe
- `_verify_cli()` :45 - Validates CLI binary exists and is executable

#### Utility Functions
- `get_speechanalyzer_transcriber(locale)` :169 - Returns global instance
- `is_speechanalyzer_available()` :179 - Checks macOS 26+ and CLI availability

## Logging

### get_logger(name) - listen/logger.py:15
Dual-output logger (stderr + /tmp/claude-listen.log).

#### Configuration
- Log file: `/tmp/claude-listen.log` :13
- File level: DEBUG, Stderr level: INFO :40,46  
- Format: Timestamped for file, simple for stderr :32,36

#### Utility Functions
- `clear_log()` :56 - Removes log file
