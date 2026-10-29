# Fournisseur CurseForge (ForgeCDN)

Le fournisseur `curseforge` permet l'indexation, la recherche, l'analyse des dépendances et le téléchargement direct d'archives de mods depuis la plateforme officielle **CurseForge The Sims 4**.

---

## 1. Caractéristiques Principales

- **Endpoint Officiel** : `https://www.curseforge.com/sims4`
- **Authentification & Anti-Bot** : Supporte la navigation publique et l'authentification avec contournement Cloudflare via le navigateur intégré.
- **Résolution ForgeCDN** : Résout les identifiants de projet et de fichier vers les binaires hébergés sur `edge.forgecdn.net` (`/api/v1/mods/{projectId}/files/{fileId}/download`).
- **9 Catégories Sims 4 Prises en Charge** :
  1. Mods - Gameplay (`mods-gameplay`)
  2. Mods - Utilities (`mods-utilities`)
  3. Mods - Poses & Animations (`mods-poses-animations`)
  4. Create a Sim (`create-a-sim`)
  5. Build / Buy (`build-buy`)
  6. Rooms / Lots (`rooms-lots`)
  7. Sims / Households (`sims-households`)
  8. Worlds (`worlds`)
  9. Translations (`translations`)

---

## 2. Extraction des Dépendances

Le fournisseur interroge les métadonnées officielles via la sous-page `/relations/dependencies` ou le DOM de description :
- Détection des dépendances strictes (`type: "MOD"`).
- Détection des bibliothèques fondamentales connues : XML Injector, Lot 51 Core Library, Smart Core Script, Sims 4 Community Library.

---

## 3. Gestion des Commentaires

- **Vérification** : Consultation de `/api/v1/mods/{projectId}/comments` pour détecter si l'utilisateur connecté a déjà signalé un prérequis manquant.
- **Publication** : Soumission sécurisée via l'API REST CurseForge.
- **Suppression** : Endpoint DELETE pour révoquer automatiquement les commentaires lorsque les prérequis sont résolus.
