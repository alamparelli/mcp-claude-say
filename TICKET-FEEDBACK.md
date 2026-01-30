# Feedback Ticket - Community Contribution

**Source**: PR t.co/kLeWsukDMK
**Status**: A analyser

## Issues Encountered

1. **Hotkey Conflict**: Default PTT hotkey `cmd_l+s` conflicts with Save in most apps
2. **Permissions**: Cursor/VS Code needs explicit Accessibility permissions or keypresses aren't detected

## Solutions Proposed

1. **Alternative Hotkey**: Switched PTT to `cmd_r` (Right Command alone) - no conflicts
2. **Documentation**: Added permissions guidance to troubleshooting

## New Feature Integrated

- **Chatterbox Neural TTS**: Better voice quality (optional, falls back to macOS `say` if not running)

## PR Content (to review)

- Setup instructions
- Hotkey compatibility table
- Troubleshooting notes
- Chatterbox TTS integration

## Analysis Notes

_A compléter lors de l'analyse..._

### Questions to Consider

- [ ] Is `cmd_r` alone a better default than `cmd_l+s`?
- [ ] Should we add a hotkey compatibility table to docs?
- [ ] How to handle Accessibility permissions guidance?
- [ ] Evaluate Chatterbox TTS integration - worth including?
