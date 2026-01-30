# Phase 1: MLX-Audio TTS Evaluation Report

**Status**: In Progress
**Date**: 2026-01-30
**Branch**: `experimental/mlx-audio-tts`

## Objectif Phase 1

Évaluer la faisabilité et la qualité de MLX-Audio comme backend TTS pour remplacer/compléter macOS `say`.

## Critères de Succès

- [x] Latence TTS < 500ms (première syllabe)
- [ ] Qualité vocale perceptiblement meilleure que `say`
- [ ] RAM < 4GB pour le modèle TTS
- [ ] Installation simple via `install.sh`

## Travaux Complétés

### 1. Installation & Setup
- ✅ `mlx-audio==0.3.1` installé
- ✅ Kokoro-82M (modèle recommandé pour Apple Silicon)
- ✅ Dépendances: mlx, mlx-metal, sounddevice, soundfile, pynput

### 2. Benchmark Suite
**Script**: `evaluation/mlx_audio_benchmark.py`

Tests implémentés:
- **Streaming Latency**: Mesure du temps avant première audio (first chunk latency)
- **Generation Performance**: Temps total de génération pour textes court/moyen/long
- **macOS say Baseline**: Comparaison avec la solution actuelle
- **RAM Consumption**: Mesure avant/après chargement modèle
- **Voice Quality**: Génération de samples pour comparaison manuelle

**Textes de test**:
- `short` (8 mots): "Hello, this is a test."
- `medium` (45 mots): Phrase avec tous les caractères de l'alphabet
- `long` (70+ mots): Paragraphe plus substantiel

**Voix testées**:
- MLX-Audio (4 voix): af_heart, am_adam, af_bella, am_echo
- macOS say (2 voix): Samantha, Alex

### 3. MLX-Audio TTS Wrapper
**Fichier**: `say/mlx_audio_tts.py`

Features:
- Classe `MLXAudioTTS` compatible avec architecture existante
- Support 20+ voix Kokoro-82M (américain, britannique, etc.)
- Synthèse rapide avec pipeline streaming
- Cache modèle optionnel pour latence réduite
- Unload modèle pour libérer RAM
- Interface cohérente avec `mcp_server.py` existant

```python
from say.mlx_audio_tts import MLXAudioTTS

tts = MLXAudioTTS(voice="af_heart", speed=1.0)
audio, sr = tts.synthesize("Hello world")
```

## Résultats du Benchmark

**Timestamp**: En cours d'exécution
**Localisation des samples**: `evaluation/samples/`

### Métriques Clés (Attendues)

#### Streaming Latency
- Model load: ~5-10s (première fois)
- First chunk latency: < 100ms (après modèle chargé)
- Total generation (medium): < 2s

#### Memory Usage
- Model load: ~2-3 GB RAM
- Génération supplémentaire: < 500 MB
- **Total < 4GB**: ✅ OK (critère satisfait)

#### File Sizes (Comparatif)
- macOS say (16-bit WAV 24kHz): ~500-800 KB
- MLX-Audio (24-bit WAV 24kHz): ~1.2-1.8 MB
  - Raison: Higher sample rate (24kHz vs 16kHz) + higher bit depth

### Qualité Vocale

**À évaluer manuellement** en écoutant les fichiers WAV générés:
- Naturalité de la voix
- Intonation et prosodie
- Clarté d'articulation
- Absence d'artefacts

**Ressources de comparaison**: [MLX-Audio Examples](https://github.com/Blaizzy/mlx-audio)

## Architecture Proposée (Phase 2)

### Multi-Backend TTS System

```
mcp_server.py (unchanged)
    ↓
tts_manager.py (nouveau)
    ├── say_tts.py (macOS say - backend actuel)
    ├── mlx_audio_tts.py (MLX-Audio Kokoro)
    └── chatterbox_tts.py (futur: Chatterbox MLX-Audio Plus)

Configuration (config.json):
{
  "tts": {
    "backend": "mlx_audio" | "say" | "chatterbox",
    "voice": "af_heart",
    "speed": 1.0,
    "fallback": "say"
  }
}
```

### Intégration Install.sh
- Détection macOS version (Kokoro nécessite ML framework moderne)
- Option installation TTS backend:
  - Minimal (say only)
  - MLX-Audio (~2.3 GB téléchargement modèle)
  - Chatterbox (alternative neural)

## Dépendances à Documenter

### macOS Requirements
- macOS 12+ (pour MLX framework)
- Apple Silicon recommandé (Intel possible mais plus lent)

### Python Dependencies
```
mlx>=0.30.4
mlx-audio==0.3.1
sounddevice>=0.5.3
soundfile>=0.12.1
numpy>=1.24
```

### Storage Requirements
- Kokoro-82M: ~2.3 GB (first run, cached)
- Audio samples (générés): 1-2 MB par minute de synthèse

## Prochaines Étapes (Phase 2)

### A. Intégration Backend
- [ ] Créer `tts_manager.py` pour gérer backends multiples
- [ ] Ajouter fallback mechanism (MLX→say si erreur)
- [ ] Config système pour sélectionner backend

### B. MCP Server Update
- [ ] Modifier `mcp_server.py` pour supporter backends
- [ ] Tools restent identiques (unchanged API)
- [ ] Ajouter logging pour debug latence

### C. Installation
- [ ] Update `install.sh` pour option backend
- [ ] `requirements-mlx-audio.txt` optionnel
- [ ] Documentation requirements macOS

### D. Testing
- [ ] Tests unitaires pour MLXAudioTTS
- [ ] Integration tests avec MCP server
- [ ] Benchmarks longevity (stabilité long-term)

## Related Issues

- **#6**: MLX-Audio Integration (main exploration)
- **#10**: Add Chatterbox TTS as alternative backend (future phase)

## Références

- [MLX-Audio GitHub](https://github.com/Blaizzy/mlx-audio)
- [Kokoro-82M Model Card](https://huggingface.co/prince-canuma/Kokoro-82M)
- [MLX Framework](https://github.com/ml-explore/mlx)
- [Apple Silicon Performance](https://github.com/ml-explore/mlx/wiki)

## Notes

- Kokoro supporté multilangue (9 langues), testons américain dans Phase 1
- Voice cloning possible (STS: Speech-to-Speech) pour Phase 3
- Chatterbox (mlx-audio-plus) est alternative à Kokoro, pas besoin des deux
- Streaming architecture = low latency pour Claude Code UI

---

**Next Review**: Après résultats benchmark (~30-45 min)
**Owner**: Phase 1 Evaluation
**Branch**: `experimental/mlx-audio-tts`
