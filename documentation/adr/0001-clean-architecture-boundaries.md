# ADR 0001 : Découplage Strict et Frontières Clean Architecture

- **Statut** : Accepté
- **Date** : 2026-10-29
- **Auteurs** : Équipe d'Ingénierie SIMS 4 Mods Manager

## Contexte
Le projet combine une interface graphique de bureau (PySide6), une API REST locale asynchrone (FastAPI), un moteur de base de données relationnelle (SQLAlchemy/SQLite) et des connecteurs de scraping pour de multiples plateformes externes (CurseForge, The Sims Resource, LoversLab, NSFWMods, Patreon). Auparavant, certains shims et imports circulaires existaient entre les composants.

## Décision
1. **Frontières de couches unidirectionnelles** :
   - `src/domain/` : Entités pures et interfaces (DTOs, entités métier). Aucune dépendance externe (FastAPI, SQLAlchemy, PySide6 interdits).
   - `src/application/` : Cas d'utilisation, orchestrateurs et coordinateurs métier.
   - `src/infrastructure/` : Implémentations concrètes (BDD, chiffrement, filesystem, HTTP).
   - `src/api/` : API REST FastAPI (consomme les cas d'utilisation application).
   - `src/ui/` : Interface utilisateur graphique PySide6 (consomme l'API REST via `ApiClient`).
   - `plugins/` : Dépend des interfaces abstraites de `src/providers/` sans que `src/` ne dépende jamais de `plugins/`.
2. **Règle Zéro-Shim** : Élimination de tous les fichiers de redirection obsolètes au profit de chemins canoniques.

## Conséquences
- Typage strict Mypy à 100% sans exception.
- Tests unitaires isolés et exécutables en microsecondes.
