# Module: Kokoro MLX TTS Backend
Last scanned: 2026-01-30T14:30:00Z
Source files: 2 (say/mlx_audio_tts.py, mcp_server.py integration)

## Overview
Kokoro-82M neural text-to-speech engine with 54 voices across 9 languages, optimized for Apple Silicon via MLX framework. Supports multilingual synthesis including French, Spanish, Italian, and more.

## MLXAudioTTS Class

### MLXAudioTTS - say/mlx_audio_tts.py:46
Main TTS synthesis engine with multilingual voice support and model caching.

#### Language Support (9 languages)
- `"a"` - American English (20 voices)
- `"b"` - British English (8 voices)
- `"e"` - Spanish (3 voices)
- `"f"` - French (1 voice: ff_siwis)
- `"h"` - Hindi (4 voices)
- `"i"` - Italian (2 voices)
- `"p"` - Portuguese Brazilian (3 voices)
- `"j"` - Japanese (5 voices)
- `"z"` - Mandarin Chinese (8 voices)

#### Voice Collections
- `LANGUAGES` :50 - Language code to name mapping
- `VOICES_BY_LANGUAGE` :63 - Organized voices per language
- `VOICES` :147 - Flat dictionary of all 54 voices
- `DEFAULT_VOICES` :152 - Default voice per language

#### Constructor
- `__init__(voice, speed, model_id, cache_model)` :165 - Initializes with voice selection and speed (0.5-2.0)

#### Core Methods
- `synthesize(text, voice)` :225 - Synthesizes text to audio array, returns (audio_ndarray, sample_rate)
- `synthesize_to_file(text, output_path, format, voice)` :258 - Saves synthesis to WAV/MP3 file
- `play(audio_array, sample_rate)` :280 - Plays audio via macOS afplay
- `speak(text, voice, blocking)` :294 - Synthesize and play with blocking option

#### Model Management
- `_load_model(lang_code)` :209 - Lazy loads KokoroPipeline for specified language
- `unload_model()` :326 - Unloads model to free RAM

#### Utility Methods
- `get_language_from_voice(voice_id)` :202 - Extracts language code from voice ID
- `get_voice_name(voice_id)` :333 - Gets human-readable voice description
- `list_voices(language)` :338 - Returns available voices, optionally filtered
- `list_languages()` :353 - Returns all supported languages
- `get_default_voice(language)` :358 - Gets default voice for language

#### Internal State
- `self.voice` - Current voice ID
- `self.speed` - Speaking speed multiplier
- `self.model_id` - HuggingFace model identifier
- `self._model` - Loaded model (cached)
- `self._pipeline` - KokoroPipeline instance
- `self._current_lang` - Currently loaded language

## Kokoro MCP Integration Functions

### kokoro_available() - mcp_server.py:205
Checks if Kokoro MLX TTS backend is available and configured.

### get_kokoro_tts() - mcp_server.py:216
Gets or creates singleton Kokoro TTS instance with thread safety via lock.

### speak_with_kokoro(text, blocking, voice) - mcp_server.py:238
Synthesizes and plays audio via Kokoro. Uses temp file with afplay. Thread-safe playback control.

#### Features
- Voice override support
- Blocking and non-blocking playback modes
- Automatic temp file cleanup on blocking mode
- Stop signal polling during playback
- Integration with process_lock for thread safety

### stop_kokoro() - mcp_server.py:305
Stops active Kokoro playback by terminating afplay process.

## Configuration

### Environment Variables
- `TTS_BACKEND=kokoro` - Enables Kokoro as default TTS backend
- `KOKORO_VOICE` - Default voice ID (default: af_heart)
- `KOKORO_SPEED` - Default speed multiplier (default: 1.0)
- `PHONEMIZER_ESPEAK_LIBRARY` - Path to espeak-ng library (for multilingual phonemization)

### Global State (mcp_server.py)
- `_kokoro_tts` :126 - Singleton instance (None until first use)
- `_kokoro_lock` :127 - Thread lock for singleton creation
- `TTS_BACKEND` :109 - Backend selection from env

## Dependencies
- `mlx-audio` - Kokoro synthesis
- `mlx` - Apple Silicon optimized ML framework
- `numpy` - Audio array operations
- `soundfile` - WAV file I/O
- `espeak-ng` - Multilingual phonemization (via homebrew)

## Voice Examples by Language
- American: `af_heart`, `af_nova`, `am_adam`, `am_echo`
- British: `bf_emma`, `bf_alice`, `bm_george`, `bm_daniel`
- French: `ff_siwis`
- Spanish: `ef_dora`, `em_alex`
- Italian: `if_sara`, `im_nicola`
- Portuguese: `pf_dora`, `pm_alex`
- Japanese: `jf_alpha`, `jm_kumo`
- Chinese: `zf_xiaoxiao`, `zm_yunxi`
- Hindi: `hf_alpha`, `hm_omega`

## Usage Example
```
tts = MLXAudioTTS(voice="ff_siwis", speed=1.0)
audio, sr = tts.synthesize("Bonjour le monde")
tts.play(audio, sr)
```

## Performance
- Model size: 82M parameters (efficient)
- Sample rate: 24000 Hz
- Languages: 9 with automatic detection
- Optimization: Apple Silicon via MLX framework

## Integration with MCP Tools
The `speak()` and `speak_and_wait()` MCP tools automatically route to Kokoro when:
- `TTS_BACKEND=kokoro` in environment
- Voice parameter is a Kokoro voice ID (format: `[language_code][gender]_[name]`)
- Example: `speak("Bonjour!", voice="ff_siwis")`
