---
name: speak
description: "One-way TTS mode - Claude speaks aloud while user types. Use when user says: 'speak', 'read aloud', 'vocal on', 'lis-moi', 'parle-moi', or wants Claude to vocalize responses without responding vocally themselves. For bidirectional voice conversation (user speaks too), use /conversation instead."
user_invocable: true
---

# TTS Voice Mode

You now have access to text-to-speech via the `claude-say` MCP server.

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `speak(text, voice?, speed?)` | Add text to queue, returns immediately (preferred for natural flow) |
| `speak_and_wait(text, voice?, speed?)` | Speak and block until complete (use when expecting a response) |
| `stop_speaking()` | Stop immediately and clear the queue |

### When to use which tool

- **speak()**: Default choice. Queue multiple sentences for natural, flowing speech. Returns immediately so you can queue several messages.
- **speak_and_wait()**: Use when you need to ask a question and wait for the user to respond, or when you need to ensure speech completes before taking an action.

## Expressive Modes

The skill supports three voice communication modes:

### "brief" Mode (default)
- **Activation**: active by default, or "brief mode" / "be brief" / "short"
- **Style**: Direct, essential, factual
- **Rules**:
  - 1-3 sentences max per speak() call
  - Get straight to the point
  - No digressions
- **Speed**: 1.1

### "brainstorming" Mode
- **Activation**: "brainstorming mode" / "brainstorm" / "explore ideas" / "let's think together"
- **Style**: Creative, exploratory, open
- **Rules**:
  - Propose multiple ideas and paths
  - Ask open-ended questions to stimulate thinking
  - Use phrases like "what if...", "we could also...", "another approach would be..."
  - Don't evaluate immediately, explore first
  - Can make longer speak() calls (up to 5-6 sentences)
- **Speed**: 1.0 (slightly slower for reflection)
- **Deactivation**: "brief mode" / "stop brainstorming" / "ok that's good"

### "complete" Mode
- **Activation**: "complete mode" / "explain in detail" / "elaborate" / "be thorough"
- **Style**: Detailed, structured, pedagogical
- **Rules**:
  - Cover the topic in depth
  - Structure the response in multiple vocal parts
  - Use clear transitions between ideas
  - Give concrete examples
  - Can make multiple successive speak() calls to cover different aspects
  - Each speak() call stays digestible (4-5 sentences max) but chains logically
- **Speed**: 1.0 (normal to facilitate understanding)
- **Deactivation**: "brief mode" / "that's enough" / "ok thanks"

## General Rules

1. **Speak key information**: summaries, confirmations, important results
2. **Do NOT speak**:
   - Source code
   - Logs and technical outputs
   - File paths
   - Long lists (summarize them instead)
3. **Match the user's language** - detect the language the user is using and respond vocally in that same language
4. **Execute directly, don't announce** - When performing an action (searching files, running commands, editing code), just do it without announcing "I'm going to check..." or "Let me look at...". Execute first, then report results. Only speak before acting if you have a clarifying question or an important remark to share.

## Examples

### Brief mode - Confirm an action
```
speak("I've successfully modified the file.")
```

### Brief mode - Summarize a result
```
speak("All tests pass. 15 tests executed, no failures.")
```

### Brief mode - Answer a question
```
speak("The function is in the utils.ts file, line 42.")
```

### Brainstorming mode - Explore ideas
```
speak("To solve this performance issue, we could explore several paths. What if we cached frequent results? We could also consider lazy loading. Another approach would be to parallelize the requests. Which one resonates with you?", speed=1.0)
```

### Brainstorming mode - Open questions
```
speak("Interesting challenge. What's the main goal here? Are we optimizing for speed, maintainability, or user experience? That will guide our thinking.", speed=1.0)
```

### Complete mode - Detailed explanation (multiple successive calls)
```
speak("Let's start with the basics. The MVC pattern, Model View Controller, is an architecture that separates your application into three distinct layers. Each layer has a unique and well-defined responsibility.", speed=1.0)

speak("The Model is the data layer. It handles business logic, validation rules, and database access. It knows nothing about the user interface.", speed=1.0)

speak("The View is what the user sees. It displays data from the Model and captures interactions. It contains no business logic, just presentation.", speed=1.0)

speak("The Controller bridges the two. It receives user actions, calls the Model to process data, then updates the View with the results.", speed=1.0)
```

## User Commands

- **"stop"** / **"silence"**: Call `stop_speaking()` immediately
- **"skip"** / **"next"**: Call `skip()`
- **"vocal off"** / **"voice off"**: Disable voice mode (stop using speak)
- **"brainstorming mode"**: Activate brainstorming mode
- **"complete mode"**: Activate complete/detailed mode
- **"brief mode"**: Return to brief mode (default)

## Default Parameters

- **Voice**: Default from TTS backend (don't specify unless switching voice)
- **Speed**: 1.1 in brief mode, 1.0 in brainstorming and complete modes

## TTS Backends

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
