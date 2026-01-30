# Analyse de consommation mémoire - MCP Claude-Say

## Résumé exécutif

L'observation de **13.55 GB de RAM** pour `tts_service.py` nécessite une investigation approfondie avant tout investissement en réécriture. Cette analyse identifie les sources de consommation mémoire, évalue le potentiel de chaque optimisation et fournit des recommandations priorisées.

---

## 1. Sources de consommation mémoire identifiées

### 1.1 Modèles ML (Source principale)

| Composant | RAM estimée | Fichier | Ligne |
|-----------|-------------|---------|-------|
| Parakeet MLX (STT) | ~2.0 GB | `parakeet_transcriber.py` | 43 |
| Chatterbox TTS | ~1.5 GB | `tts_service.py` | 97 |
| PyTorch + MLX runtime | ~0.5-1.0 GB | dépendances | - |
| **Total modèles** | **~4.0-4.5 GB** | - | - |

**Problème critique** : Les modèles sont chargés une fois et **jamais déchargés** (singleton permanent).

```python
# parakeet_transcriber.py:119-127 - Singleton sans déchargement
_transcriber: Optional[ParakeetTranscriber] = None

def get_parakeet_transcriber() -> ParakeetTranscriber:
    global _transcriber
    if _transcriber is None:
        _transcriber = ParakeetTranscriber()  # Charge ~2GB, jamais libéré
    return _transcriber
```

### 1.2 Buffers audio (Source secondaire)

| Buffer | RAM max | Condition | Fichier |
|--------|---------|-----------|---------|
| `_buffer` (list) | 20 MB | Enregistrement 5 min | `audio.py:45` |
| `_audio_queue` | 20 MB | Redondant avec _buffer | `audio.py:44` |
| Fichiers temp WAV | 2-5 MB | Par transcription | `parakeet_transcriber.py:79` |

**Impact faible** : Ces buffers sont correctement nettoyés après usage.

### 1.3 Écart inexpliqué

| Mémoire observée | 13.55 GB |
|------------------|----------|
| Modèles identifiés | ~4.5 GB |
| Écart à expliquer | **~9 GB** |

**Hypothèses pour l'écart** :
1. Fuite mémoire MLX/NumPy (accumulation progressive)
2. Fragmentation mémoire Python
3. Cache GPU/MPS non libéré
4. Erreur de mesure (mémoire virtuelle vs résidente)

---

## 2. Potentiel de gain par stratégie

### 2.1 Optimisations Python (Effort: Faible)

| Optimisation | Gain estimé | Complexité | Risque |
|--------------|-------------|------------|--------|
| Lazy loading du modèle | 0 GB* | Faible | Faible |
| Déchargement après timeout (30 min) | 2.0 GB | Moyenne | Faible |
| `gc.collect()` après transcription | 0.1-0.5 GB | Trivial | Aucun |
| Limiter taille historique audio | 0.02 GB | Trivial | Aucun |
| Queue bornée (`maxsize=50`) | Négligeable | Trivial | Aucun |

\* Le lazy loading existe déjà partiellement (ligne 35 de `parakeet_transcriber.py`).

**Code de déchargement proposé** :
```python
import time
import threading

_last_use = 0
_unload_timeout = 1800  # 30 minutes

def get_parakeet_transcriber() -> ParakeetTranscriber:
    global _transcriber, _last_use
    _last_use = time.time()
    if _transcriber is None:
        _transcriber = ParakeetTranscriber()
    return _transcriber

def _unload_if_idle():
    global _transcriber
    while True:
        time.sleep(60)  # Check every minute
        if _transcriber and (time.time() - _last_use > _unload_timeout):
            _transcriber = None
            gc.collect()
```

**Gain potentiel total (Python)** : **2.0-2.5 GB** (économise la RAM quand inactif)

### 2.2 Architecture microservices (Effort: Moyen)

| Amélioration | Gain | Complexité | Avantage |
|--------------|------|------------|----------|
| Séparer STT en processus dédié | 2.0 GB (à la demande) | Moyenne | Start/stop on demand |
| Communication via socket/IPC | 0 GB | Moyenne | Isolation mémoire |
| Timeout automatique du process | 2.0 GB | Faible | Auto-cleanup |

**Architecture proposée** :
```
┌──────────────────┐     Socket      ┌──────────────────┐
│  MCP Server      │ ←────────────→  │  STT Worker      │
│  (léger, 100 MB) │                 │  (2 GB si actif) │
└──────────────────┘                 └──────────────────┘
                                           ↑ ↓
                                     Start/Stop à la demande
```

**Gain potentiel** : **2.0 GB** (libéré quand non utilisé) + isolation

### 2.3 Réécriture Swift native (Effort: Élevé)

| Composant | Gain potentiel | Faisabilité |
|-----------|----------------|-------------|
| MCP Server en Swift | ~50-100 MB | Élevée (SDK existe) |
| Apple SpeechAnalyzer natif | ~0 GB additionnel | Élevée |
| Élimination Python runtime | ~200-500 MB | Élevée |

**Limitations** :
- SpeechAnalyzer est **expérimental** et moins précis que Parakeet
- Nécessite macOS 26+
- Pas de support Chatterbox TTS (Python uniquement)

**Gain potentiel** : **0.5-1.0 GB** + meilleure intégration macOS

### 2.4 Réécriture Rust (Effort: Très élevé)

| Aspect | Évaluation |
|--------|------------|
| Gain mémoire potentiel | ~1.0 GB (élimination Python) |
| Complexité | Très élevée |
| Bindings MLX/Parakeet | N'existent pas |
| ROI | Négatif |

**Non recommandé** : Les modèles ML utilisent Python/MLX, pas de binding Rust.

---

## 3. Comparaison SpeechAnalyzer vs Parakeet

| Critère | Parakeet MLX | Apple SpeechAnalyzer |
|---------|--------------|----------------------|
| RAM | ~2.0 GB | ~0 GB (système) |
| Précision | Excellente | Variable |
| Latence | ~0.5s pour 30s audio | ~1-2s |
| Langues | Multi (auto-detect) | Configurable |
| Dépendances | Python, MLX | Swift CLI uniquement |
| Stabilité | Stable | Expérimental |

**Gain en passant à SpeechAnalyzer** : **2.0 GB** mais avec perte de fiabilité.

---

## 4. Estimation des gains cumulés

### Scénario conservateur (optimisations Python seules)

| Action | RAM économisée | Effort |
|--------|----------------|--------|
| Déchargement modèle après 30 min | 2.0 GB | 2h |
| gc.collect() post-transcription | 0.2 GB | 30 min |
| Queue bornée | Négligeable | 15 min |
| **Total** | **~2.2 GB** | **~3h** |

### Scénario modéré (microservices)

| Action | RAM économisée | Effort |
|--------|----------------|--------|
| Processus STT séparé | 2.0 GB (à la demande) | 8h |
| Timeout auto (5 min) | 2.0 GB (libéré rapidement) | 2h |
| Optimisations Python | 0.2 GB | 3h |
| **Total** | **~2.2 GB** actif, **~4.2 GB** libéré après timeout | **~13h** |

### Scénario agressif (Swift natif)

| Action | RAM économisée | Effort |
|--------|----------------|--------|
| MCP Server Swift | 0.5 GB | 40h |
| SpeechAnalyzer backend | 2.0 GB | Déjà implémenté |
| Élimination Python (STT) | 0.3 GB | Inclus |
| **Total** | **~2.8 GB** | **~40h+** |

---

## 5. Analyse de l'écart 13.55 GB

L'observation de 13.55 GB reste inexpliquée. Actions recommandées :

### 5.1 Profiling requis

```bash
# Profiler la mémoire Python
pip install memory_profiler
python -m memory_profiler tts_service.py

# Tracer les allocations
python -c "
import tracemalloc
tracemalloc.start()
# ... charger le modèle et faire des transcriptions ...
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:20]:
    print(stat)
"
```

### 5.2 Vérifications à effectuer

- [ ] Différencier mémoire **résidente** (RSS) vs **virtuelle** (VSIZE)
- [ ] Mesurer avant/après chargement du modèle
- [ ] Mesurer la croissance après 10, 50, 100 transcriptions
- [ ] Comparer avec backend SpeechAnalyzer (0 modèle Python)

### 5.3 Fuites possibles (à investiguer)

| Suspect | Indice | Fichier |
|---------|--------|---------|
| Tensors MLX non libérés | `.cpu()` sans cleanup | `tts_service.py:220` |
| Audio queue unbounded | `Queue()` sans maxsize | `audio.py:44` |
| Buffer list growth | Pas de limite | `audio.py:45` |
| Parakeet internal cache | Possible | Lib externe |

---

## 6. Recommandations priorisées

### Phase 1 : Investigation (Priorité: HAUTE)

1. **Reproduire l'observation** sur plusieurs machines
2. **Profiler avec tracemalloc** pour identifier la source exacte
3. **Comparer RSS vs VSIZE** dans Activity Monitor
4. **Tester avec SpeechAnalyzer** pour baseline sans modèle Python

### Phase 2 : Quick wins (Priorité: MOYENNE)

Si le problème est confirmé :

1. Ajouter `gc.collect()` après transcription
2. Implémenter le déchargement après timeout
3. Borner la queue (`Queue(maxsize=100)`)

### Phase 3 : Architecture (Priorité: BASSE)

Si les quick wins sont insuffisants :

1. Séparer STT en processus dédié avec timeout
2. Évaluer migration vers SpeechAnalyzer si acceptable

---

## 7. Conclusion

| Métrique | Valeur |
|----------|--------|
| Mémoire théorique attendue | 4.0-4.5 GB |
| Mémoire observée | 13.55 GB |
| Écart inexpliqué | ~9 GB |
| Gain max avec optimisations Python | 2.5 GB |
| Gain max avec architecture microservices | 4.2 GB |
| Gain max avec réécriture Swift | 2.8 GB |

**Verdict** : Avant tout investissement en réécriture, il est **impératif** de :
1. Reproduire l'observation
2. Identifier la source des 9 GB inexpliqués
3. Tester les optimisations Python simples

Une réécriture complète n'est **pas justifiée** à ce stade. Le ROI des optimisations Python (3h de travail pour 2+ GB) est bien supérieur à une réécriture Swift (40h+ pour 2.8 GB).

---

## Annexe : Code de profiling recommandé

```python
# memory_profiler.py - À exécuter pendant une session de test
import tracemalloc
import gc
import psutil
import os

def get_memory_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def profile_transcription():
    print(f"Baseline: {get_memory_mb():.1f} MB")

    tracemalloc.start()

    from listen.parakeet_transcriber import get_parakeet_transcriber
    print(f"After import: {get_memory_mb():.1f} MB")

    t = get_parakeet_transcriber()
    print(f"After model load: {get_memory_mb():.1f} MB")

    # Simulate 10 transcriptions
    import numpy as np
    for i in range(10):
        audio = np.random.randn(16000 * 5).astype(np.float32)  # 5 sec
        result = t.transcribe(audio)
        print(f"After transcription {i+1}: {get_memory_mb():.1f} MB")

    gc.collect()
    print(f"After gc.collect(): {get_memory_mb():.1f} MB")

    snapshot = tracemalloc.take_snapshot()
    print("\nTop 10 memory allocations:")
    for stat in snapshot.statistics('lineno')[:10]:
        print(stat)

if __name__ == "__main__":
    profile_transcription()
```

---

*Analyse effectuée le 2026-01-30 par Claude Code*
