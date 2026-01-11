---
name: speak
description: "TTS Voice Mode - Claude speaks responses via macOS speech synthesis. Use this skill when user says: 'speak', 'talk to me', 'voice mode', 'vocal on', 'read aloud', or asks Claude to vocalize responses. Disable with 'stop', 'silence', 'vocal off'."
user_invocable: true
---

# TTS Voice Mode

You now have access to text-to-speech via the `claude-say` MCP server.

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `speak(text, voice?, speed?)` | Add text to the speech queue |
| `stop_speaking()` | Stop immediately and clear the queue |
| `skip()` | Skip to the next message in queue |
| `list_voices()` | List available system voices |
| `queue_status()` | Get current queue status |

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

- **Voice**: Siri/system voice (don't specify)
- **Speed**: 1.1 in brief mode, 1.0 in brainstorming and complete modes
