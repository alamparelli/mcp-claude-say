# Conversation Mode - Full Voice Loop

You now have access to both text-to-speech (claude-say) AND speech-to-text (claude-listen) for a complete voice conversation.

## Activation

When this skill is activated:
1. Start listening with `start_listening()`
2. Enable voice responses (use speak() for all responses)
3. The user can now speak to you and you'll respond vocally

## Available MCP Tools

### claude-listen (STT)
| Tool | Description |
|------|-------------|
| `start_listening()` | Start continuous microphone listening |
| `stop_listening()` | Stop listening |
| `get_transcription(wait?, timeout?)` | Get the last transcription |
| `listening_status()` | Get current listening state |
| `transcribe_now()` | Force immediate transcription |

### claude-say (TTS)
| Tool | Description |
|------|-------------|
| `speak(text, voice?, speed?)` | Speak text aloud |
| `stop_speaking()` | Stop immediately |
| `skip()` | Skip to next message |
| `queue_status()` | Get speech queue status |

## How It Works

```
┌─────────────────────────────────────────┐
│            Conversation Loop            │
│                                         │
│  User speaks → VAD detects → Whisper    │
│       ↑              │         │        │
│       │              │         ↓        │
│  Speaker ← speak() ← Claude ← text      │
│                                         │
└─────────────────────────────────────────┘
```

1. **VAD** (Voice Activity Detection) monitors the microphone
2. When you speak, it automatically **interrupts** any ongoing TTS
3. After **2 seconds of silence**, your speech is transcribed
4. Claude processes and responds **vocally**

## Instructions

When conversation mode is active:

1. **Always use speak()** for responses - never just text
2. **Keep responses concise** - this is a conversation, not a lecture
3. **Wait for transcription** before responding
4. Detect **"fin de session"** to end conversation mode

## Starting Conversation Mode

```python
# 1. Start listening
start_listening()

# 2. Confirm vocally
speak("Mode conversation activé. Je t'écoute.")

# 3. Wait for TTS to finish BEFORE listening for transcription
# Poll queue_status() until "Status: Silent"
while queue_status() shows "Speaking":
    wait briefly

# 4. Only then wait for user speech
transcription = get_transcription(wait=True)

# 5. Respond vocally
speak("Your response here...")
```

## Critical: TTS/STT Synchronization

**IMPORTANT**: Always wait for TTS to finish speaking before calling `get_transcription()`.

The listen server ignores audio while TTS is speaking (to avoid feedback). If you call `get_transcription()` while TTS is still speaking, you will miss user speech.

**Correct flow:**
1. Call `speak()`
2. Poll `queue_status()` until it returns "Status: Silent"
3. Only then call `get_transcription(wait=True)`

This ensures you don't start waiting for transcription while still talking.

## Ending Conversation Mode

When user says **"fin de session"** (or similar):
```python
stop_listening()
speak("Fin de la session vocale. À bientôt!")
```

## Important Rules

1. **Interrupt = priority** - If user speaks, stop talking and listen
2. **No code vocally** - Never read code, paths, or logs aloud
3. **Match language** - Respond in the same language as the user
4. **Brief by default** - Keep responses short unless asked otherwise
5. **Execute directly, don't announce** - When performing an action (searching, running commands, editing), just do it. Don't say "I'm going to check..." or "Let me look at...". Execute first, then report results. Only speak before acting if you have a clarifying question or an important remark to share.

## Error Handling

- If no speech detected after 30s: `speak("Tu es toujours là?")`
- If transcription fails: `speak("Je n'ai pas compris, peux-tu répéter?")`
- If microphone error: Inform user and suggest checking permissions
