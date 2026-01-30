# Module: Shared Coordination
Last scanned: 2026-01-29T14:30:00Z  
Source files: 1

## Inter-Server Communication

### signal_stop_speaking() - shared/coordination.py:35
Signals claude-say to stop speaking when speech detected by claude-listen.

#### Methods
1. Direct import: Tries to import and call mcp_server.stop_speaking() 
2. Signal file: Creates /tmp/claude-voice-stop file as fallback

### check_stop_signal() - shared/coordination.py:76
Checks and clears stop signal file. Called by TTS worker thread.

### STOP_SIGNAL_FILE - shared/coordination.py:32
Shared signal file path: /tmp/claude-voice-stop

## TTS State Detection

### is_speaking() - shared/coordination.py:97
Checks if claude-say TTS is currently active via process detection.

#### Caching
- `_is_speaking_cache` :93 - Cached result with timestamp
- `_IS_SPEAKING_CACHE_TTL = 0.3` :94 - 300ms cache duration
- Uses `pgrep -x say` to detect macOS say process :119

### clear_stop_signal() - shared/coordination.py:133
Removes any pending stop signal file.

## Voice Coordination Class

### VoiceCoordinator - shared/coordination.py:142
Coordinates between TTS and STT to prevent feedback loops.

#### State Management
- `_listening` :152 - STT active state
- `_speaking` :153 - TTS active state

#### Methods
- `start_listening()` :155 - Mark STT as active
- `stop_listening()` :159 - Mark STT as inactive  
- `start_speaking()` :163 - Mark TTS as active
- `stop_speaking()` :167 - Mark TTS as inactive
- `on_speech_detected()` :179 - Interrupt TTS when speech detected

#### Properties
- `is_listening` :172 - STT state
- `is_speaking` :176 - TTS state (includes process check)

#### Singleton Function
- `get_coordinator()` :189 - Returns global VoiceCoordinator instance
