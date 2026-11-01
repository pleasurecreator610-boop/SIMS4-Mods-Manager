# 💎 SIMS 4 Mods Manager

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Site%20Vitrine%20%26%20Guide%20Joueur-00C853?logo=github)](https://pleasurecreator610-boop.github.io/SIMS4-Mods-Manager/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-0077C8.svg)](https://www.python.org/)
[![Plateformes](https://img.shields.io/badge/catalogues-Multi--Plateformes%20Sims%204-orange.svg)](./documentation/providers/README.md)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](./LICENSE)

Le compagnon tout-en-un pour gérer, installer et protéger tous vos **Mods et Custom Content (CC) Les Sims 4**.  
Il réunit vos sites de téléchargement au même endroit, récupère automatiquement les **mods prérequis sur les sites officiels de leurs créateurs**, évite les doublons dans votre dossier `Mods` et détecte en un clic les fichiers incompatibles qui font planter votre jeu.

👉 **[Découvrir le Site Vitrine & le Guide Complet (GitHub Pages)](https://pleasurecreator610-boop.github.io/SIMS4-Mods-Manager/)**

---

## ✨ Ce que l'Application Fait pour Votre Jeu

| Fonctionnalité | Bénéfice pour le Joueur | Guide Dédié |
| :--- | :--- | :--- |
| 🌐 **Tous vos Catalogues au Même Endroit** | Parcourez et recherchez instantanément des coiffures, vêtements, meubles et mods de gameplay sur l'ensemble des sites supportés (avec masquage par défaut des contenus `+18`). | [🔌 Plateformes & Sites](./documentation/providers/README.md) |
| 🛡️ **Prérequis Téléchargés à la Source** | Lorsqu'un mod dépend d'un mod socle ou d'un utilitaire, l'application va automatiquement le chercher sur le **site officiel du créateur**, gratuitement et sans compte requis. | [✨ Guide des Fonctionnalités](./documentation/features.md#2-telechargement-automatique-des-prerequis-depuis-les-sites-officiels) |
| 🧩 **Fin des Doublons & Tri Automatique** | Reconnaît un même mod quel que soit le site d'où il provient pour ne jamais l'installer deux fois, et écarte automatiquement les simples notes d'auteurs. | [✨ Guide des Fonctionnalités](./documentation/features.md#3-fin-des-doublons--tri-automatique-des-notes-dauteurs) |
| 📢 **Contact Direct avec les Créateurs** | Prévenez l'auteur en un clic par commentaire ou message privé lorsqu'un prérequis ou un lien est manquant sur une fiche, sans jamais poster en double. | [✨ Guide des Fonctionnalités](./documentation/features.md#4-contacter-les-createurs-en-1-clic-commentaires--messages) |
| ⚔️ **Détecteur de Mods Incompatibles** | Repère immédiatement les fichiers `.package` qui entrent en conflit dans votre jeu (sans les confondre avec les traductions) et sans ralentir votre PC. | [✨ Guide des Fonctionnalités](./documentation/features.md#6-detecteur-de-mods-incompatibles-ultra-rapide-sans-ralentir-votre-pc) |
| 📦 **Installation Propre & Retour en Arrière** | Place automatiquement vos fichiers `.ts4script` au bon endroit, conserve vos réglages personnels et permet d'annuler une mise à jour en un clic. | [✨ Guide des Fonctionnalités](./documentation/features.md#5-installation-propre-scripts-ts4script--retour-en-arriere) |

---

## 🚀 Démarrage Rapide (3 Commandes)

```powershell
# 1. Installer le gestionnaire d'environnement uv (via Scoop)
scoop install uv

# 2. Préparer l'application et le navigateur intégré
uv sync
uv run playwright install chromium

# 3. Ouvrir SIMS 4 Mods Manager
uv run python run.py
```

---

## 📚 Sommaire de la Documentation

### 1. Guides Joueur Les Sims 4

- 🌟 **[Site Vitrine & Explorateur des Plateformes (`documentation/index.md`)](./documentation/index.md)** : Présentation visuelle aux couleurs des Sims 4 et recherche par site ou type de contenu.
- ✨ **[Guide Complet des Fonctionnalités (`documentation/features.md`)](./documentation/features.md)** : Explication simple et détaillée de chaque fonctionnalité pour votre jeu.
- 🔌 **[Catalogue des Plateformes & Sites Supportés (`documentation/providers/README.md`)](./documentation/providers/README.md)** : Liste complète des sites officiels, catalogues CC et portails communautaires pris en charge.
- 🌍 **[Langues & Internationalisation (`documentation/i18n.md`)](./documentation/i18n.md)** : Interface disponible en Français, Anglais, Espagnol, Chinois et Hindi.

### 2. Documentation Technique (Développeurs & Contributeurs)

- 🛠️ **[Architecture Logicielle & Base de Données (`documentation/architecture.md`)](./documentation/architecture.md)**
- 🧩 **[Pipeline de Résolution & Classification des Dépendances (`documentation/dependency_classification_and_noise.md`)](./documentation/dependency_classification_and_noise.md)**
- 📊 **[Modules, Classes & Modèle de Données (`documentation/modules_and_classes.md`)](./documentation/modules_and_classes.md)**
- 📐 **[Architecture Decision Records (`documentation/adr/index.md`)](./documentation/adr/index.md)**
- 🌐 **[Référence API REST (`documentation/api_reference.md`)](./documentation/api_reference.md)**
- 🤖 **[Guide Normalisé pour Agents LLM (`AGENTS.md`)](./AGENTS.md)**

---

## 📄 Licence

Distribué sous licence **GNU GPL v3**. Voir [LICENSE](./LICENSE).
