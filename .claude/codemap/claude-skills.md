# Module: Claude Skills
Last scanned: 2026-01-30T14:30:00Z
Source files: 2 (skill/SKILL.md, skill/conversation/SKILL.md)

## Overview
Voice interaction skills for Claude Code. Two modes: one-way TTS (/speak) and bidirectional conversation (/conversation) with Push-to-Talk.

## /speak Skill - One-Way TTS

### Location: skill/SKILL.md

#### Description
Text-to-speech mode where Claude speaks aloud while user types. No microphone interaction.

#### Activation Triggers
- "speak", "read aloud", "vocal on", "lis-moi", "parle-moi"
- Or when user wants Claude to vocalize responses without vocal interaction

#### Available MCP Tools
- `speak(text, voice?, speed?)` - Queue TTS without blocking
- `speak_and_wait(text, voice?, speed?)` - Speak and wait for completion
- `stop_speaking()` - Stop immediately and clear queue

#### Three Expressive Modes

**1. Brief Mode (default)**
- Activation: "brief mode", "be brief", "short"
- Style: Direct, factual, essential
- Rules: 1-3 sentences max per speak() call
- Speed: 1.1

**2. Brainstorming Mode**
- Activation: "brainstorming mode", "brainstorm", "explore ideas", "let's think together"
- Style: Creative, exploratory, open-ended
- Rules: Propose multiple ideas, open questions, up to 5-6 sentences per call
- Speed: 1.0

**3. Complete Mode**
- Activation: "complete mode", "explain in detail", "elaborate", "be thorough"
- Style: Detailed, structured, pedagogical
- Rules: Cover in depth, multiple successive speak() calls, 4-5 sentences each
- Speed: 1.0

#### Voice Specifications

**Voice Parameter Format**: None (use backend default) or voice ID

**macOS Voices**: Native system voices

**Kokoro MLX Voices** (if TTS_BACKEND=kokoro):
- American English: `af_heart` (default), `af_nova`, `am_adam`, `am_echo` (20 total)
- British English: `bf_emma`, `bf_alice`, `bm_george`, `bm_daniel` (8 total)
- French: `ff_siwis`
- Spanish: `ef_dora`, `em_alex`
- Italian: `if_sara`, `im_nicola`
- Portuguese: `pf_dora`, `pm_alex`
- Japanese: `jf_alpha`, `jm_kumo`
- Chinese: `zf_xiaoxiao`, `zm_yunxi`
- Hindi: `hf_alpha`, `hm_omega`

#### User Commands
- "stop", "silence" → `stop_speaking()`
- "skip", "next" → `skip()` (if available)
- "vocal off", "voice off" → Disable voice mode
- Mode activation: "brainstorming mode", "complete mode", "brief mode"

#### Rules
1. Speak key information: summaries, confirmations, results
2. DO NOT speak: source code, logs, file paths, long lists
3. Match user's language
4. Execute directly, don't announce actions
5. Return to brief mode from other modes with "brief mode" or completion

#### Example Usage

**Brief mode**:
```
speak("I've successfully modified the file.")
speak("All tests pass. 15 tests executed, no failures.")
```

**Brainstorming mode**:
```
speak("To solve this, we could explore several paths. What if we cached results? Another approach would be parallelization. Which resonates?", speed=1.0)
```

**Complete mode (multiple calls)**:
```
speak("Let's start with the basics.", speed=1.0)
speak("The Model handles business logic.", speed=1.0)
speak("The Controller bridges them together.", speed=1.0)
```

#### Default Parameters
- Voice: Backend default (don't specify unless switching)
- Speed: 1.1 brief mode, 1.0 brainstorming/complete

#### TTS Backends
- `macos` - Native macOS say (default, instant, offline)
- `kokoro` - Kokoro MLX (54 voices, 9 languages, locally on Apple Silicon)
- `google` - Google Cloud TTS (neural voices, requires API key)

---

## /conversation Skill - Bidirectional Voice

### Location: skill/conversation/SKILL.md

#### Description
Complete voice conversation with Push-to-Talk. User speaks, Claude responds vocally. Uses simple PTT mode without VAD.

#### Architecture
- Press hotkey (default: Right Cmd) to start recording
- Press again to stop and transcribe
- No automatic voice detection
- Full control over when to record

#### Available MCP Tools

**STT (claude-listen) - Push-to-Talk**:
- `start_ppt_mode(key?)` - Start PTT (default: cmd_r)
- `stop_ptt_mode()` - Stop PTT
- `get_ppt_status()` - Get state
- `get_segment_transcription(wait?, timeout?)` - Wait for transcription (default timeout: 120s)

**Status Messages from get_segment_transcription()**:
- `[Ready]` - Waiting for user
- `[Recording...]` - Currently recording
- `[Transcribing...]` - Processing audio
- `[Timeout: No transcription received]` - Wait timed out
- Otherwise: Actual transcription text

**TTS (claude-say)**:
- `speak(text, voice?, speed?)` - Queue without blocking
- `speak_and_wait(text, voice?, speed?)` - Speak and wait
- `stop_speaking()` - Stop immediately

#### TTS Voice Specifications
Same as /speak skill: macOS default, Kokoro MLX, or Google Cloud

#### When to Use TTS Tools

**speak()**: Default for natural flow. Queue multiple sentences without blocking.

**speak_and_wait()**: ONLY when breaking very long responses into parts. Put at the END to ensure completion before listening.

```python
# Typical: one speak() call
speak("The answer is X. This matters because Y.", speed=1)

# Long explanation: multiple calls with wait() at end
speak("Part 1: introduction", speed=1)
speak("Part 2: details", speed=1)
speak_and_wait("Part 3: conclusion", speed=1)  # Only this waits
```

#### Starting Conversation Mode
```python
start_ptt_mode()  # Default: Right Cmd
speak_and_wait("Ready.")  # Confirmation
transcription = get_segment_transcription(wait=True, timeout=120)
# Process and respond with speak() calls
speak("Your response here.")
speak_and_wait("What's next?")  # Blocks before listening
```

#### Main Conversation Loop
```python
while True:
    text = get_segment_transcription(wait=True, timeout=120)
    
    # Check for end
    if "fin de session" in text.lower():
        break
    
    # Check for timeout
    if "Timeout" in text:
        speak_and_wait("Still there?")
        continue
    
    # Process and respond
    speak("Your response.")
    speak_and_wait("Next question?")  # Last call blocks
```

#### Ending Conversation Mode
```python
stop_ptt_mode()
speak_and_wait("Disabled.")
```

#### PTT Key Options
| Key | Name |
|-----|------|
| `cmd_r` | Right Command (default, recommended) |
| `cmd_l+s` | Left Command + S |
| `cmd_r+m` | Right Command + M |
| `cmd_l` | Left Command |
| `alt_r` | Right Option |
| `alt_l` | Left Option |
| `ctrl_r` | Right Control |
| `f13`, `f14`, `f15` | Function keys |

#### Important Rules
1. Use `speak()` for natural flow
2. Use `speak_and_wait()` only at the end of multi-part responses
3. No code vocally - never read code, paths, logs
4. Match user's language
5. Give detailed responses - don't artificially shorten
6. Execute directly, don't announce actions
7. Minimal activation messages - ONE word only
8. Show visual content proactively - use screen for diagrams/tables while explaining verbally

#### Error Handling
- Timeout (no speech): `speak_and_wait("Tu es toujours là?")`
- Unclear transcription: `speak_and_wait("Je n'ai pas compris, peux-tu répéter?")`

#### Background Mode (Non-Blocking Alternative)
- `start_ppt_background(key?)` - Start in background
- `check_transcription()` - Poll for results (non-blocking)
- `stop_ppt_background()` - Stop background PTT

Use background mode when:
- Need Claude to perform other tasks while waiting
- Synchronous mode times out frequently
- Note: Creates more visible tool calls

#### STT Backends
- Parakeet-MLX (recommended) - Fast, 2.3GB model, excellent accuracy
- Apple SpeechAnalyzer (experimental) - macOS 26+ native, no download, less reliable
