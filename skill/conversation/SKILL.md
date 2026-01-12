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

**Synchronous mode (blocking):**
| Tool | Description |
|------|-------------|
| `start_ptt_mode(key?)` | Start PTT mode (default: Left Cmd + S) |
| `stop_ptt_mode()` | Stop PTT mode |
| `get_ptt_status()` | Get PTT state |
| `get_segment_transcription(wait?, timeout?)` | Get transcription (blocks) |

**Background mode (non-blocking) - RECOMMENDED:**
| Tool | Description |
|------|-------------|
| `start_ptt_background(key?)` | Start PTT in background process |
| `check_transcription()` | Check for new transcription (non-blocking) |
| `stop_ptt_background()` | Stop background PTT |

### claude-say (TTS)
| Tool | Description |
|------|-------------|
| `speak_and_wait(text, voice?, speed?)` | Speak and wait for completion |
| `stop_speaking()` | Stop immediately |

## How It Works

```
┌─────────────────────────────────────────────────┐
│              Push-to-Talk Mode                  │
│                                                 │
│  [Left Cmd + S] → Start recording               │
│       │                                         │
│       │     (records continuously)              │
│       │                                         │
│  [Left Cmd + S] → Stop → Save → Transcribe      │
│       │                                         │
│       ↓                                         │
│  Claude responds vocally                        │
└─────────────────────────────────────────────────┘
```

1. User presses **Left Cmd + S** to start recording
2. Audio is captured continuously
3. User presses **Left Cmd + S** again to stop
4. Audio is saved and transcribed with **Parakeet MLX**
5. Claude processes and responds **vocally**

## Starting Conversation Mode

```python
# 1. Start PTT mode
start_ptt_mode()  # Uses default key: cmd_l+s

# 2. Confirm vocally
speak_and_wait("Mode conversation activé. Appuie sur Commande gauche S pour parler.")

# 3. Wait for transcription
transcription = get_segment_transcription(wait=True, timeout=60)

# 4. Process and respond
speak_and_wait("Your response here...")

# 5. Loop back to step 3
```

## Conversation Loop

```python
# Main loop
while True:
    # Wait for transcription
    text = get_segment_transcription(wait=True, timeout=60)

    # Check for end command
    if "fin de session" in text.lower():
        break

    # Check for timeout
    if "Timeout" in text:
        speak_and_wait("Tu es toujours là?")
        continue

    # Process and respond
    response = process(text)
    speak_and_wait(response)

# End session
stop_ptt_mode()
speak_and_wait("Fin de la session vocale. À bientôt!")
```

## Ending Conversation Mode

When user says **"fin de session"** (or similar):
```python
stop_ptt_mode()
speak_and_wait("Fin de la session vocale. À bientôt!")
```

## Background Mode (Non-Blocking) - RECOMMENDED

Background mode avoids blocking Claude while waiting for transcriptions.
PTT runs in a separate process and writes to a file.

### Starting Background Mode

```python
# 1. Start background PTT
start_ptt_background()  # Returns immediately

# 2. Confirm vocally
speak_and_wait("Mode conversation activé. Appuie sur Commande gauche S pour parler.")

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
speak_and_wait("Fin de la session vocale.")
```

### Advantages of Background Mode

- **Non-blocking**: Claude isn't frozen waiting for speech
- **Responsive**: Can do other things while waiting
- **Stable**: No long-running tool calls that might timeout

## Important Rules

1. **Use speak_and_wait()** - Ensures TTS completes before listening
2. **No code vocally** - Never read code, paths, or logs aloud
3. **Match language** - Respond in the same language as the user
4. **Brief by default** - Keep responses short unless asked otherwise
5. **Execute directly** - Don't announce actions, just do them and report results

## Error Handling

- If timeout (no speech): `speak_and_wait("Tu es toujours là?")`
- If transcription unclear: `speak_and_wait("Je n'ai pas compris, peux-tu répéter?")`

## Available Keys for PTT

| Key | Name |
|-----|------|
| `cmd_l+s` | Left Command + S (default) |
| `cmd_r+m` | Right Command + M |
| `cmd_r` | Right Command |
| `cmd_l` | Left Command |
| `alt_r` | Right Option |
| `alt_l` | Left Option |
| `ctrl_r` | Right Control |
| `f13`, `f14`, `f15` | Function keys |
