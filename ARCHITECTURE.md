# Claude Voice - Architecture

## Vue d'ensemble

Ce repo contient deux serveurs MCP complémentaires pour créer une boucle vocale complète avec Claude Code :

- **claude-say** (TTS) : Synthèse vocale - Claude parle
- **claude-listen** (STT) : Reconnaissance vocale - Claude écoute

## Architecture globale

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code                               │
│                            ↑ ↓                                   │
├─────────────────────────────────────────────────────────────────┤
│                      MCP Protocol                                │
│                       ↑       ↓                                  │
├───────────────────────┴───────┴─────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │   claude-listen  │   [stop]     │    claude-say    │         │
│  │      (STT)       │ ──────────→  │      (TTS)       │         │
│  │                  │              │                  │         │
│  │  - Silero VAD    │              │  - macOS say     │         │
│  │  - Whisper       │              │  - Queue         │         │
│  └────────┬─────────┘              └────────┬─────────┘         │
│           │                                  │                   │
│           ↓                                  ↓                   │
│      [Microphone]                      [Speakers]                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## claude-listen - Spécifications

### Composants

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| VAD | Silero VAD | Détection d'activité vocale + trigger words |
| STT | Parakeet MLX (par défaut) / Whisper | Transcription |
| Audio | sounddevice | Capture micro |
| Langue | Auto-détect | Détection automatique |

### Transcribers disponibles

| Transcriber | Performance | RAM | Recommandé pour |
|-------------|-------------|-----|-----------------|
| **Parakeet MLX** | ~60x temps réel | ~2 GB | Apple Silicon (M1/M2/M3) |
| Whisper (faster-whisper) | ~10x temps réel | ~4-6 GB | GPU CUDA / Fallback |

Configuration via variable d'environnement :
```bash
CLAUDE_LISTEN_TRANSCRIBER=parakeet  # ou whisper, auto (défaut)
```

### Paramètres

| Paramètre | Valeur par défaut | Variable d'env | Description |
|-----------|-------------------|----------------|-------------|
| Silence timeout | 2 secondes | `CLAUDE_LISTEN_SILENCE_TIMEOUT` | Délai avant transcription |
| Quick check timeout | 0.5 secondes | `CLAUDE_LISTEN_QUICK_CHECK_TIMEOUT` | Délai avant vérification trigger word |
| Source audio | Microphone only | - | Pas de capture système |

### Trigger Words (mots déclencheurs)

Dire un de ces mots à la fin d'une phrase déclenche immédiatement la transcription (sans attendre 2s) :

- "stop", "terminé", "fini", "ok", "c'est tout"
- "that's it", "done", "end", "over", "go"

### Tools MCP

```python
@mcp.tool()
def start_listening() -> str:
    """Démarre l'écoute continue."""

@mcp.tool()
def stop_listening() -> str:
    """Arrête l'écoute."""

@mcp.tool()
def get_transcription() -> str:
    """Récupère la dernière transcription."""

@mcp.tool()
def listening_status() -> str:
    """Retourne l'état de l'écoute."""
```

### Flow d'écoute

```
1. start_listening() appelé
2. VAD surveille le micro en continu
3. Parole détectée →
   - Signal stop_speaking() à claude-say
   - Buffer audio commence
4. Silence 2s détecté →
   - Whisper transcrit le buffer
   - Transcription disponible via get_transcription()
5. Boucle continue jusqu'à stop_listening()
```

### Interruption

Quand l'utilisateur parle :
1. VAD détecte immédiatement la voix
2. Envoie `stop_speaking()` à claude-say
3. claude-say coupe la synthèse en cours
4. claude-listen buffer et transcrit

Règle simple : **parole = interruption**, pas de cas particulier.

## Coordination inter-serveurs

### Communication

claude-listen → claude-say : Signal "stop" quand parole détectée

Options d'implémentation :
1. **Import direct** : claude-listen importe les fonctions de claude-say
2. **Fichier signal** : `/tmp/claude-voice-stop`
3. **MCP interne** : Appel tool via le protocole

Recommandation : **Import direct** (plus simple, même process Python possible)

## Activation / Désactivation

### Skill "mode conversation"

Active les deux serveurs ensemble :
```
User: /conversation
→ start_listening()
→ Voice mode ON pour claude-say
→ Boucle vocale active
```

### Fin de session

Commande vocale "fin de session" :
```
User dit: "fin de session"
→ Whisper transcrit
→ Détecte mot-clé
→ stop_listening()
→ Voice mode OFF
```

## Structure du repo

```
.claude-say/
├── ARCHITECTURE.md             # Ce fichier
├── README.md                   # Documentation utilisateur
├── requirements.txt            # Dépendances Python
├── install.sh                  # Installation (télécharge modèle)
│
├── say/                        # Module TTS
│   ├── __init__.py
│   └── mcp_server.py          # Serveur MCP claude-say
│
├── listen/                     # Module STT
│   ├── __init__.py
│   ├── mcp_server.py          # Serveur MCP claude-listen
│   ├── vad.py                 # Silero VAD wrapper
│   ├── transcriber.py         # Whisper wrapper
│   └── audio.py               # Capture audio
│
├── shared/                     # Code partagé
│   ├── __init__.py
│   └── coordination.py        # Communication say ↔ listen
│
├── models/                     # Modèles (gitignore)
│   └── ggml-large-v3-turbo.bin
│
└── skills/                     # Skills Claude Code
    └── conversation/
        └── SKILL.md
```

## Installation

### install.sh

```bash
#!/bin/bash
# 1. Créer environnement virtuel
# 2. Installer dépendances (requirements.txt)
# 3. Télécharger modèle Whisper si absent
# 4. Configurer MCP servers dans Claude Code
```

### requirements.txt

```
mcp
faster-whisper  # ou whisper.cpp bindings
silero-vad
sounddevice
numpy
```

## Dépendances système

- **macOS** : Accès micro (permissions)
- **Python** : 3.10+
- **Whisper model** : ~1.5GB (large-v3-turbo)

## Performance

| Métrique | Cible |
|----------|-------|
| Latence VAD | < 100ms |
| Latence transcription | < 2s (selon longueur) |
| RAM | ~2GB (modèle chargé) |
| CPU | Utilise Metal/GPU si disponible |

## Optimisation Claude Code - Model Switching

Pour réduire la latence des réponses vocales, configurer Claude Code pour utiliser Haiku lors des conversations vocales :

### Configuration recommandée

Dans le skill `conversation`, ajouter une instruction pour utiliser Haiku :

```markdown
# Dans le skill conversation
model: haiku  # Réponses vocales rapides
```

Ou via le paramètre `model` dans les Task agents :

```python
# Pour les réponses texte (qualité)
model="opus"  # ou "sonnet"

# Pour les réponses vocales (vitesse)
model="haiku"  # 3-5x plus rapide
```

### Gain de latence

| Modèle | Temps réponse typique | Recommandé pour |
|--------|----------------------|-----------------|
| Opus | 2-4s | Texte à l'écran, tâches complexes |
| Sonnet | 1-2s | Équilibre qualité/vitesse |
| **Haiku** | 0.3-0.8s | **Réponses vocales** |

## Évolutions futures

1. **Migration Rust** : Si latence Python insuffisante
2. **Streaming transcription** : Afficher texte en temps réel
3. **Wake word** : "Hey Claude" pour activer sans skill
4. **Multi-langue explicit** : Forcer une langue spécifique
5. **Streaming TTS** : Envoyer au TTS phrase par phrase pendant la génération
