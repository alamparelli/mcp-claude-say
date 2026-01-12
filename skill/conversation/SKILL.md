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
| Tool | Description |
|------|-------------|
| `start_ptt_mode(key?)` | Start PTT mode (default: Left Cmd + S) |
| `stop_ptt_mode()` | Stop PTT mode |
| `get_ptt_status()` | Get PTT state |
| `get_segment_transcription(wait?, timeout?)` | Get transcription |

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
