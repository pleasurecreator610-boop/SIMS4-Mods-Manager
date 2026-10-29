# ADR 0002 : Mode WAL SQLite, Index Composites et Système de Migrations Versionné

- **Statut** : Accepté
- **Date** : 2026-10-29

## Contexte
L'application ingère des dizaines de milliers de fiches de mods depuis 4 plateformes en parallèle. L'accès concurrent entre l'API REST en tâche de fond et l'UI Qt nécessitait une élimination totale des verrous de base de données (`database is locked`) et des temps de réponse ultra-rapides.

## Décision
1. **Pragmas SQLite Optimaux** :
   - `journal_mode=WAL` (Write-Ahead Logging pour lecture/écriture simultanées sans blocage).
   - `synchronous=NORMAL`, `busy_timeout=15000` (15s), `cache_size=-64000` (64 Mo en RAM), `mmap_size=268435456` (256 Mo memory-mapped I/O).
2. **Index Composites Exhaustifs** :
   - `(source, remote_id)` index unique composite utilisé par tous les upserts.
   - `(source, updated_date)` et `(category, updated_date)`.
3. **MigrationRunner Versionné** :
   - Remplacement des `ALTER TABLE` disséminés par une table `_schema_migrations` et des migrations atomiques réversibles ordonnées.
