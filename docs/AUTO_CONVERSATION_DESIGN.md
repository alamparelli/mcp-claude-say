# Auto-Conversation Design Document

This document describes the phased implementation plan for automatic voice conversation mode in claude-say/claude-listen.

## Overview

The goal is to evolve from manual Push-to-Talk (PTT) to a fully automatic conversation mode where:
1. User speaks naturally without pressing buttons
2. Recording starts/stops automatically based on voice activity
3. The system handles turn-taking between Claude (TTS) and user (STT)

## Current State (Pre-Phase 1)

```
User presses PTT key → Recording starts
User presses PTT key again → Recording stops → Transcription
Claude responds → TTS plays
User presses PTT key → ... (repeat)
```

**Limitations:**
- Manual start/stop is unnatural
- User must time their key presses
- No automatic turn detection

---

## Phase 1: VAD Auto-Stop (IMPLEMENTED)

### Goal
Automatically stop recording when user finishes speaking.

### Implementation
- Added Silero VAD integration (`listen/vad.py`)
- New parameter `auto_stop=True` in `start_ptt_mode()`
- VAD monitors audio stream for end-of-speech (configurable silence threshold)
- When silence detected → auto-trigger stop + transcription

### Flow
```
User presses PTT key → Recording starts + VAD monitoring
User speaks...
VAD detects 1.5s silence → Recording stops automatically → Transcription
Claude responds...
User presses PTT key → ... (repeat)
```

### Configuration
```python
start_ptt_mode(
    key="cmd_r",
    auto_stop=True,           # Enable VAD-based auto-stop
    vad_silence_ms=1500,      # 1.5s silence = end of utterance
)
```

### Dependencies
- `torch` (PyTorch for Silero VAD)
- Silero VAD model (downloaded from torch.hub on first use)

### Files Modified
- `listen/vad.py` (NEW) - Silero VAD wrapper
- `listen/simple_ptt.py` - Added auto_stop support
- `listen/mcp_server.py` - Exposed auto_stop parameter

---

## Phase 2: Auto-Start After TTS (IMPLEMENTED)

### Goal
Automatically start listening when Claude finishes speaking.

### Architecture Challenge

The main challenge is that `claude-say` and `claude-listen` are **separate MCP server processes**:

```
┌─────────────────┐          ┌──────────────────┐
│   claude-say    │    ???   │  claude-listen   │
│   (TTS server)  │─────────▶│   (STT server)   │
│                 │          │                  │
│ speak_and_wait()│          │ start_recording()│
│ returns when    │          │ should trigger   │
│ speech done     │          │ automatically    │
└─────────────────┘          └──────────────────┘
```

**Problem**: How does claude-listen know when claude-say finished speaking?

### Proposed Solutions

#### Solution A: Signal File (Simplest)

Create a signal file when TTS completes:

```python
# In claude-say/mcp_server.py
def speak_and_wait(...):
    # ... TTS playback ...
    Path("/tmp/claude-tts-complete").touch()  # Signal completion
    return "Speech completed"

# In claude-listen, poll for this file or use inotify/kqueue
```

**Pros:**
- Simple to implement
- No new dependencies

**Cons:**
- Requires polling or OS-specific file watching
- Slight latency

#### Solution B: Unix Domain Socket (Recommended)

Create a coordination service that both servers connect to:

```python
# shared/coordinator.py
class ConversationCoordinator:
    def __init__(self, socket_path="/tmp/claude-conversation.sock"):
        self.socket_path = socket_path
        self.state = "IDLE"  # IDLE, SPEAKING, LISTENING, PROCESSING

    def on_tts_complete(self):
        """Called by claude-say when TTS finishes."""
        self.state = "LISTENING"
        self.notify_listeners("START_LISTEN")

    def on_stt_complete(self, text):
        """Called by claude-listen when transcription is ready."""
        self.state = "PROCESSING"
        self.notify_listeners("TRANSCRIPTION", text)
```

**Pros:**
- Real-time communication
- Proper state machine
- Extensible

**Cons:**
- More complex implementation
- Need to manage socket lifecycle

#### Solution C: Combined MCP Server (Alternative)

Merge both servers into one process:

```python
# mcp_server.py (combined)
mcp = FastMCP("claude-voice")

# TTS tools
@mcp.tool()
def speak_and_wait(text: str) -> str:
    # Play TTS...
    # Automatically start listening
    _start_recording_internal()
    return "Speaking complete, now listening"
```

**Pros:**
- Simplest coordination (shared memory)
- Single process to manage

**Cons:**
- Major refactor
- Loses modularity

### Implemented Approach for Phase 2

**Used Solution A (Signal File)** for simplicity:

1. Extended `shared/coordination.py` with signal file at `/tmp/claude-tts-complete`
2. Modified `speak_and_wait()` to call `signal_tts_complete()` after speech
3. Modified `start_ptt_mode()` to accept `auto_start=True` and `echo_delay_ms` parameters
4. When `auto_start=True`, background thread polls for TTS completion signal → auto-starts recording

### Implementation Details

1. **Extended Coordinator Module**
   ```
   shared/coordination.py
   ├── signal_tts_complete()       # Called by claude-say when TTS ends
   ├── wait_for_tts_complete()     # Called by claude-listen to wait for signal
   └── clear_tts_complete_signal() # Cleanup
   ```

2. **Modified claude-say (mcp_server.py)**
   ```python
   def speak_and_wait(text, voice, speed):
       # ... TTS ...
       signal_tts_complete()  # Signal completion to claude-listen
       return "Speech completed"
   ```

3. **Modified claude-listen (listen/mcp_server.py)**
   ```python
   def start_ptt_mode(auto_start=False, echo_delay_ms=400):
       if auto_start:
           # Start background thread to wait for TTS completion
           threading.Thread(target=_auto_start_waiter).start()
   ```

4. **Auto-Start Waiter Thread**
   ```python
   def _auto_start_waiter():
       while auto_start_enabled:
           if wait_for_tts_complete(timeout=5.0):
               time.sleep(echo_delay_ms / 1000)  # Echo prevention
               recorder.start()  # Auto-start recording
   ```

### Echo Prevention

When auto-starting after TTS, the microphone might capture:
- Residual TTS audio (speaker → mic feedback)
- Room reverb

**Mitigation strategies:**
1. **Delay**: 300-500ms delay after TTS before recording
2. **Initial VAD Gate**: Require 200ms+ of speech before accepting audio
3. **Audio Fingerprinting**: Compare TTS output with mic input (advanced)

### API (Phase 2 - Implemented)

```python
# claude-listen
start_ptt_mode(
    key="cmd_r",
    auto_stop=True,         # Phase 1: VAD-based stop
    vad_silence_ms=1500,    # Silence duration for auto-stop
    auto_start=True,        # Phase 2: Auto-start after TTS
    echo_delay_ms=400,      # Delay before starting recording (echo prevention)
)

# claude-say - no API changes, speak_and_wait() automatically signals completion
speak_and_wait(text="Hello!")  # Signals TTS complete internally
```

---

## Phase 3: Full Conversational Mode (PLANNED)

### Goal
Hands-free, natural conversation mode like talking to a person.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ConversationOrchestrator                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  State Machine:                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                                                           │   │
│  │   ┌───────┐  TTS done  ┌───────────┐  VAD end  ┌───────┐ │   │
│  │   │SPEAKING│──────────▶│ LISTENING │──────────▶│PROCESS│ │   │
│  │   └───────┘            └───────────┘           └───────┘ │   │
│  │       ▲                      │                     │      │   │
│  │       │                      │ interrupt           │      │   │
│  │       │                      ▼                     │      │   │
│  │       │               ┌───────────┐                │      │   │
│  │       └───────────────│   IDLE    │◀───────────────┘      │   │
│  │                       └───────────┘                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Coordination:                                                   │
│  ├── TTS playback management                                     │
│  ├── STT recording control                                       │
│  ├── Turn-taking logic                                          │
│  ├── Barge-in detection (interrupt TTS when user speaks)        │
│  └── Timeout handling                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

#### 1. Barge-In Support
Allow user to interrupt Claude while speaking:
```
Claude: "Let me explain the—"
User: "Wait, I have a question"
→ TTS stops immediately, STT captures user's interruption
```

**Implementation:**
- Keep mic partially active during TTS (reduced sensitivity)
- Use VAD to detect user speech during TTS
- Signal stop to TTS immediately
- Capture audio from interruption point

#### 2. Continuous Listening Mode
Option to keep mic always open:
```python
start_conversation_mode(
    continuous=True,      # Always listening (vs PTT-triggered)
    barge_in=True,        # Allow interrupting TTS
    idle_timeout_s=300,   # Auto-exit after 5min silence
)
```

**Privacy Concerns:**
- Clear visual indicator (beyond orange dot)
- Automatic timeout
- Easy exit ("stop listening" voice command)

#### 3. Voice Activity Detection Refinements
```python
VAD_CONFIG = {
    "speech_threshold": 0.5,      # Basic speech detection
    "sentence_end_silence_ms": 1500,  # End of utterance
    "word_pause_max_ms": 500,     # Max pause within speech
    "min_speech_duration_ms": 300,    # Ignore very short sounds
    "barge_in_threshold": 0.7,    # Higher threshold during TTS
}
```

#### 4. Context-Aware Turn Taking
Smart detection of incomplete sentences:
- "I want to..." → Wait longer for continuation
- "Thank you!" → Shorter wait, likely complete

**Implementation options:**
- Simple: Fixed silence threshold (Phase 1/2 approach)
- Advanced: Use Parakeet's partial transcription to detect incomplete sentences
- Most Advanced: Fine-tuned model for turn-taking prediction

### API (Phase 3)

```python
# New MCP tool
@mcp.tool()
def start_conversation_mode(
    wake_word: Optional[str] = None,  # "Hey Claude" to start
    barge_in: bool = True,            # Allow interrupting TTS
    continuous: bool = False,         # Always listening vs PTT
    idle_timeout_s: int = 300,        # Auto-exit on silence
    vad_config: Optional[dict] = None # Custom VAD settings
) -> str:
    """
    Start full conversational mode.

    In this mode:
    - TTS and STT are coordinated automatically
    - Turn-taking is handled by the system
    - User can interrupt Claude mid-sentence
    - Conversation ends on timeout or explicit exit
    """
```

### Implementation Steps

1. **Conversation State Machine**
   - Implement proper state transitions
   - Handle edge cases (concurrent events, errors)
   - Add timeout management

2. **Barge-In Detection**
   - Dual-mode VAD (background during TTS, active during listen)
   - Echo cancellation (at least basic delay-based)
   - Immediate TTS interruption

3. **Unified MCP Interface**
   - Single `start_conversation_mode()` tool
   - Subsumes Phase 1 & 2 features
   - Cleaner API for skill/prompt usage

4. **Testing & Refinement**
   - Real-world conversation testing
   - Tune VAD thresholds
   - Handle edge cases (background noise, multiple speakers)

---

## Dependencies Summary

| Phase | New Dependencies |
|-------|-----------------|
| Phase 1 | `torch` (for Silero VAD) |
| Phase 2 | None (socket is stdlib) |
| Phase 3 | Possibly `webrtcvad` for advanced VAD |

## Risk Assessment

| Risk | Phase | Mitigation |
|------|-------|------------|
| VAD false positives | 1 | Tune thresholds, add min speech duration |
| Echo/feedback loop | 2 | Delay after TTS, VAD gating |
| IPC reliability | 2 | Fallback to signal files |
| CPU usage (continuous) | 3 | Efficient VAD, suspend on idle |
| Privacy concerns | 3 | Clear indicators, timeouts, easy exit |

## Timeline Estimate

- **Phase 1**: Implemented (this PR)
- **Phase 2**: ~2-3 days implementation + testing
- **Phase 3**: ~1 week implementation + extensive testing

---

## Appendix: Alternative Approaches Considered

### A. WebRTC-based Solution
Use WebRTC for full-duplex audio with built-in echo cancellation.

**Rejected because:**
- Overkill for local-only use case
- Complex setup
- Not needed for MVP

### B. Whisper Streaming with Endpoint Detection
Use Whisper's own endpoint detection for turn-taking.

**Partially adopted:**
- Parakeet (Whisper variant) is already used for transcription
- Could explore streaming mode in future

### C. LLM-based Turn Prediction
Use Claude to predict when user is done speaking.

**Deferred:**
- Adds latency
- Expensive API calls
- Simple VAD works well enough for MVP
