# TICKET: Optimisation mémoire - Python consomme 13 Go de RAM

## Problème observé
Le processus Python (PID 83554) consomme **13,55 Go de RAM** selon le Moniteur d'activité macOS.

Le processus identifié est `tts_service.py` (service TTS).

## Analyse préliminaire

### Processus concerné
```
/opt/homebrew/Cellar/python@3.11/3.11.14_1/.../Python /Users/alessandrolamparelli/.mcp-claude-say/tts_service.py
```

### Causes possibles à investiguer

1. **Modèle Parakeet chargé en permanence**
   - Le modèle fait ~2.3 Go mais reste en mémoire même quand non utilisé
   - Pattern singleton dans `parakeet_transcriber.py` (ligne 119-127)

2. **Accumulation de données audio**
   - Buffers audio non libérés après transcription
   - Historique de transcriptions conservé en mémoire

3. **Fuite mémoire MLX/NumPy**
   - Arrays numpy non garbage collectés
   - Cache MLX qui grossit au fil du temps

4. **Multiple instances de modèles**
   - Vérifier si le modèle est chargé plusieurs fois

## Actions à investiguer

- [ ] Profiler la mémoire avec `memory_profiler` ou `tracemalloc`
- [ ] Vérifier si le modèle peut être déchargé quand inactif (lazy loading)
- [ ] Implémenter un timeout pour décharger le modèle après X minutes d'inactivité
- [ ] Vérifier les buffers audio dans `audio.py` et `simple_ptt.py`
- [ ] Tester avec le backend SpeechAnalyzer pour comparer

## Optimisations potentielles

1. **Lazy loading du modèle** - Ne charger que lors de la première transcription
2. **Auto-unload** - Décharger le modèle après période d'inactivité
3. **Limiter l'historique** - Ne pas conserver les transcriptions passées
4. **Garbage collection explicite** - Forcer `gc.collect()` après transcription

## Priorité
Moyenne - Impact sur les ressources système mais pas bloquant

## Date
2026-01-19
