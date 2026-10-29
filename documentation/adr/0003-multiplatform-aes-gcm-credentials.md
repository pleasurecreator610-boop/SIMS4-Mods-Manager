# ADR 0003 : Chiffrement Authentifié Multiplateforme des Identifiants (AES-256-GCM)

- **Statut** : Accepté
- **Date** : 2026-10-29

## Contexte
Les sessions des utilisateurs (cookies de session LoversLab, NSFWMods, Patreon, CurseForge) doivent être protégées au repos dans la base SQLite locale pour empêcher tout vol de compte en cas d'accès non autorisé au fichier de base de données.

## Décision
1. Utilisation du standard cryptographique **AES-256-GCM** avec dérivation de clé **PBKDF2-HMAC-SHA256** (100 000 itérations).
2. Clé dérivée d'un sel cryptographique de 16 octets persistant et d'un identifiant machine matériel local.
3. Rétrocompatibilité garantie avec les sessions préexistantes Windows DPAPI (`dpapi:`) et base64 (`enc:`).
