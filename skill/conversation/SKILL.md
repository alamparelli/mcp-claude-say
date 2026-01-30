---
name: conversation
description: "Bidirectional voice conversation with Push-to-Talk. Use when user says: 'conversation mode', 'let's talk', 'parlons', 'voice conversation', 'dialogue vocal', 'PTT mode', or wants to speak WITH Claude (not just listen). For one-way TTS (Claude speaks, user types), use /speak instead."
user_invocable: true
---

# Conversation Mode - Voice Loop with Push-to-Talk

You now have access to both text-to-speech (claude-say) AND speech-to-text (claude-listen) for a complete voice conversation.

## Architecture

Uses **simple Push-to-Talk (PTT)** mode:
- Press hotkey to start recording
- Press again to stop and transcribe
- No automatic voice detection
- Full control over when to record

## Available MCP Tools

### claude-listen (STT - Push-to-Talk)

**Synchronous mode (blocking) - RECOMMENDED:**
| Tool | Description |
|------|-------------|
| `start_ptt_mode(key?)` | Start PTT mode (default: Right Cmd) |
| `stop_ptt_mode()` | Stop PTT mode |
| `get_ptt_status()` | Get PTT state |
| `get_segment_transcription(wait?, timeout?)` | Wait for transcription (default timeout: 120s). Returns status: [Ready], [Recording...], [Transcribing...] |

**Background mode (non-blocking) - Alternative:**
| Tool | Description |
|------|-------------|
| `start_ptt_background(key?)` | Start PTT in background process |
| `check_transcription()` | Check for new transcription (non-blocking) |
| `stop_ptt_background()` | Stop background PTT |

### claude-say (TTS)
| Tool | Description |
|------|-------------|
| `speak(text, voice?, speed?)` | Queue text, returns immediately (preferred for natural flow) |
| `speak_and_wait(text, voice?, speed?)` | Speak and wait for completion (use when expecting response) |
| `stop_speaking()` | Stop immediately |

### TTS Backends

The TTS backend is configured in `~/.mcp-claude-say/.env`:

| Backend | Description |
|---------|-------------|
| `macos` | Native macOS `say` command (default, instant, offline) |
| `kokoro` | Kokoro MLX - 54 neural voices, 9 languages, runs locally on Apple Silicon |
| `google` | Google Cloud TTS - neural voices, requires API key |

### Kokoro Voices (if TTS_BACKEND=kokoro)

Pass voice ID as the `voice` parameter to use a specific voice:

| Language | Voice Examples |
|----------|---------------|
| American English | `af_heart` (default), `af_nova`, `am_adam`, `am_echo` |
| British English | `bf_emma`, `bf_alice`, `bm_george`, `bm_daniel` |
| French | `ff_siwis` |
| Spanish | `ef_dora`, `em_alex` |
| Italian | `if_sara`, `im_nicola` |
| Portuguese | `pf_dora`, `pm_alex` |
| Japanese | `jf_alpha`, `jm_kumo` |
| Chinese | `zf_xiaoxiao`, `zm_yunxi` |
| Hindi | `hf_alpha`, `hm_omega` |

Example: `speak("Bonjour!", voice="ff_siwis")` for French.

### When to use which TTS tool

**IMPORTANT - Natural Speech Pattern:**
- **speak()**: Use for normal responses. One single speak() call with your complete answer is the default.
- **speak_and_wait()**: ONLY use when you have a VERY LONG response broken into multiple parts. Put speak_and_wait() at the END to ensure all speech completes before listening.
- **Default speed**: Always use `speed=1` (1.0) for natural pacing.

**Best practice - use speak() for normal responses:**
```python
# For typical responses, use ONE speak() call:
speak("I understand completely. The function you're looking for handles authentication and it's located in the auth module. It validates tokens and manages user sessions.", speed=1)
```

**Only use speak_and_wait() for very long multi-part explanations:**
```python
# For very long responses that must be split:
speak("First part of a very detailed explanation that covers the initial concept.", speed=1)
speak("Second part that continues with more details.", speed=1)
speak_and_wait("Final part that concludes the explanation.", speed=1)  # Only the last one waits
```

**Why this matters:** speak() returns immediately without blocking. speak_and_wait() blocks until speech completes, which is only needed when breaking long responses into parts to ensure proper sequencing.

## How It Works

```
┌─────────────────────────────────────────────────┐
│              Push-to-Talk Mode                  │
│                                                 │
│  [Right Cmd] → Start recording                  │
│       │                                         │
│       │     (records continuously)              │
│       │                                         │
│  [Right Cmd] → Stop → Save → Transcribe         │
│       │                                         │
│       ↓                                         │
│  Claude responds vocally                        │
└─────────────────────────────────────────────────┘
```

1. User presses **Right Command** to start recording
2. Audio is captured continuously
3. User presses **Right Command** again to stop
4. Audio is saved and transcribed with the configured STT engine
5. Claude processes and responds **vocally**

## Starting Conversation Mode

```python
# 1. Start PTT mode
start_ptt_mode()  # Uses default key: cmd_r (Right Command)

# 2. Confirm vocally (short message only)
speak_and_wait("Prêt.")

# 3. Wait for transcription
transcription = get_segment_transcription(wait=True, timeout=120)

# 4. Process and respond (use speak() for natural flow, speak_and_wait() at the end)
speak("Here's what I found.")
speak("The first point is this.")
speak_and_wait("What would you like to know next?")  # Blocks before listening

# 5. Loop back to step 3
```

## Conversation Loop

```python
# Main loop
while True:
    # Wait for transcription
    text = get_segment_transcription(wait=True, timeout=120)

    # Check for end command
    if "fin de session" in text.lower():
        break

    # Check for timeout
    if "Timeout" in text:
        speak_and_wait("Tu es toujours là?")
        continue

    # Process and respond - use speak() for flow, speak_and_wait() at end
    speak("I understand your question.")
    speak("Let me explain.")
    speak_and_wait("Does that make sense?")  # Last message blocks

# End session
stop_ptt_mode()
speak_and_wait("Désactivé.")
```

## Ending Conversation Mode

When user says **"fin de session"** (or similar):
```python
stop_ptt_mode()
speak_and_wait("Désactivé.")
```

## Background Mode (Non-Blocking) - Alternative

Background mode uses polling instead of blocking. Use this if you need Claude to do other tasks while waiting for speech.

### Starting Background Mode

```python
# 1. Start background PTT
start_ptt_background()  # Returns immediately

# 2. Confirm vocally
speak_and_wait("Prêt.")

# 3. Poll for transcriptions (non-blocking)
result = check_transcription()
# Returns: transcription text, or status like "[Ready...]", "[Recording...]"
```

### Background Conversation Loop

```python
import time

while True:
    # Non-blocking check
    result = check_transcription()

    # Check if it's actual transcription (not status message)
    if not result.startswith("["):
        # Got real transcription!
        if "fin de session" in result.lower():
            break

        # Respond
        speak_and_wait(f"Tu as dit: {result}")

    # Small delay before next check
    time.sleep(0.5)

# End session
stop_ptt_background()
speak_and_wait("Désactivé.")
```

### When to use Background Mode

- When you need Claude to perform other tasks while waiting
- When synchronous mode times out frequently
- Note: Creates more visible tool calls in the interface

## Important Rules

1. **Use speak() for natural flow** - Queue multiple sentences without blocking
2. **Use speak_and_wait() at the end** - Only when you need to wait for user response
3. **No code vocally** - Never read code, paths, or logs aloud
4. **Match language** - Respond in the same language as the user
5. **Detailed responses by default** - Give thorough, complete explanations naturally. Technical topics, concepts, and questions deserve full answers. Don't artificially shorten responses.
6. **Execute directly** - Don't announce actions, just do them and report results
7. **Minimal activation messages** - Use ONE word only for activation ("Ready", "Prêt", etc.) and deactivation ("Disabled", "Désactivé", etc.) in the user's language
8. **Show visual content proactively** - When explaining concepts, processes, or technical topics, don't hesitate to display diagrams, tables, code snippets, or structured lists on screen. Voice mode doesn't mean text-only - use the screen as a visual aid. If something would be clearer with a diagram or example, show it while explaining verbally.

## Error Handling

- If timeout (no speech): `speak_and_wait("Tu es toujours là?")`
- If transcription unclear: `speak_and_wait("Je n'ai pas compris, peux-tu répéter?")`

## Available Keys for PTT

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
