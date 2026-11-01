# ADR 0004 : Défense en Profondeur Contre les Bombes de Décompression et Attaques SSRF

- **Statut** : Accepté
- **Date** : 2026-10-29

## Contexte
Le téléchargement automatique et l'extraction d'archives ZIP, 7Z et RAR provenant de la communauté exposent le poste de l'utilisateur à des vecteurs d'attaques :

- Évasions d'arborescence (ZipSlip `../../`).
- Scripts exécutables malveillants (`.exe`, `.bat`, `.ps1`, `.vbs`, etc.).
- Déni de service par saturation mémoire / disque (Zip Bombs).
- Redirection ou requêtes forgées côté serveur (SSRF) vers des interfaces locales privées ou des métadonnées cloud.

## Décision

1. **Validation Anti-SSRF** : Validation stricte des schémas d'URL, blocage des plages d'adresses privées (RFC 1918) et métadonnées cloud (`169.254.169.254`), et filtrage sur domaines de confiance autorisés (`*.forgecdn.net`, `*.thesimsresource.com`, etc.).
2. **Quotas d'Extraction Stricts** : Plafond de 10 000 fichiers, 8 Gio décompressés max, et ratio limite de 100:1.
3. **Quarantaine et Neutralisation** : Filtrage pré et post-extraction supprimant immédiatement tout fichier exécutable non autorisé.
