# 🔌 Catalogue des 22 Plateformes de Mods (`Providers`)

**SIMS 4 Mods Manager** intègre **22 plateformes auto-découvertes** dans `plugins/` et déclarées dans la source unique de vérité `src/core/provider_metadata.py`.

Chaque plateforme dispose de sa fiche technique détaillée ci-dessous.

---

## 1. 🛡️ Portails Officiels de Frameworks (Priorité Absolue • Sans Compte)

!!! important "Règle d'Or : Priorité Absolue aux Sites Officiels"
    Conformément à la règle d'or d'architecture, toute dépendance pointant vers l'un de ces frameworks est **systématiquement interceptée et téléchargée depuis son site officiel**, même si la fiche du mod parent pointe vers un lien tiers (LoversLab, CurseForge, ModTheSims ou Patreon).

| Plateforme | ID Technique | Site Officiel | Mods & Frameworks Couverts | Accès | Fiche |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Deaderpool (MCCC)** | `deaderpool` | [deaderpool-mccc.com](https://deaderpool-mccc.com) | *MC Command Center (MCCC)* & *MC WooHoo* | ✅ **100% Public** | [📖 Fiche](./deaderpool.md) |
| **Scumbumbo Memorial** | `scumbumbo` | [scumbumbomods.com](https://scumbumbomods.com) | *XML Injector*, *Teleport Any Sim*, *Keep Instruments* | ✅ **100% Public** | [📖 Fiche](./scumbumbo.md) |
| **Lumpinou Mods** | `lumpinou` | [lumpinoumods.com](https://www.lumpinoumods.com) | *RPO (WooHoo Wellness)*, *Mood Pack*, *Toolbox*, *LGBTQIA+* | ✅ **100% Public** | [📖 Fiche](./lumpinou.md) |
| **Wicked.cc (TURBODRIVER)** | `wickedcc` | [wicked.cc](https://wicked.cc) | *WickedWhims* (`+18`), *WonderfulWhims* & animations | ✅ **100% Public** | [📖 Fiche](./wickedcc.md) |
| **Basemental CC** | `basemental` | [basementalcc.com](https://basementalcc.com) | *Basemental Drugs* (`+18`), *Gangs*, *Universal Venue List* | ✅ **100% Public** | [📖 Fiche](./basemental.md) |

---

## 2. 🌟 Catalogues Communautaires & Portails Créateurs SFW

| Plateforme | ID Technique | Moteur / Socle | Accès & Session | Commentaires / MP | Fiche |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CurseForge** | `curseforge` | API & Scraper CF + ForgeCDN | ✅ Optionnel (Anti-bot) | ✅ Oui | [📖 Fiche](./curseforge.md) |
| **The Sims Resource (TSR)** | `thesimsresource` | Scraper TSR custom | ✅ Optionnel | ✅ Oui | [📖 Fiche](./thesimsresource.md) |
| **ModTheSims (MTS)** | `modthesims` | vBulletin / MTS Downloader | ✅ Optionnel | ✅ Oui | [📖 Fiche](./modthesims.md) |
| **Nexus Mods** | `nexusmods` | API GraphQL v2 + REST v1 | 🔑 Clé API / Session | ✅ Oui | [📖 Fiche](./nexusmods.md) |
| **Patreon** | `patreon` | API Posts Créateurs | ✅ Optionnel (Abonnés) | ✅ Oui | [📖 Fiche](./patreon.md) |
| **SimsFinds** | `simsfinds` | Scraper SimsFinds | ✅ Optionnel | ✅ Oui | [📖 Fiche](./simsfinds.md) |
| **Maxis Match CC World** | `mmccworld` | Tumblr Tag Engine + SFS | ✅ Optionnel (Tumblr) | ✅ Oui | [📖 Fiche](./mmccworld.md) |
| **SimFileShare (SFS)** | `simfileshare` | Résolveur direct `/download/` | ✅ **Public (Sans compte)** | ➖ Hébergeur CDN | [📖 Fiche](./simfileshare.md) |
| **Sims 4 Studio** | `sims4studio` | ProBoards + *Andrew's Pose Player* | ✅ Optionnel (Forum) | ✅ Oui | [📖 Fiche](./sims4studio.md) |
| **GameBanana** | `gamebanana` | API Core v11 JSON (`Game 5508`) | ✅ Optionnel | ✅ Oui | [📖 Fiche](./gamebanana.md) |
| **The Sims Catalog** | `thesimscatalog` | `BasePortalProvider` (WordPress) | ✅ **Public (Sans compte)** | ➖ Portail direct | [📖 Fiche](./thesimscatalog.md) |
| **itch.io** | `itchio` | Catalogue HTML/JSON `tag-sims-4` | ✅ Optionnel | ✅ Oui | [📖 Fiche](./itchio.md) |
| **LittleMsSam** | `littlemssam` | `BasePortalProvider` (Tumblr/SFS) | ✅ **Public (Sans compte)** | ➖ Portail créateur | [📖 Fiche](./littlemssam.md) |
| **SixamCC** | `sixamcc` | `BasePortalProvider` (Packs CC) | ✅ **Public (Sans compte)** | ➖ Portail créateur | [📖 Fiche](./sixamcc.md) |

---

## 3. 🔞 Portails Adultes (`+18` — Masqués par défaut)

| Plateforme | ID Technique | Moteur / Socle | Accès & Session | Commentaires / MP | Fiche |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LoversLab** | `loverslab` | `BaseIPSForumProvider` (IPS4) | 🔑 Compte requis | ✅ Oui (Forum & MP) | [📖 Fiche](./loverslab.md) |
| **NSFWMods** | `nsfwmods` | `BaseIPSForumProvider` (IPS4) | ✅ Optionnel / Anti-bot | ✅ Oui (Forum & MP) | [📖 Fiche](./nsfwmods.md) |
| **Synthira.ru** | `synthira` | `BasePortalProvider` (DLE/Forum) | ✅ Optionnel | ✅ Oui | [📖 Fiche](./synthira.md) |
| **F95zone** | `f95zone` | `BasePortalProvider` (XenForo 2) | 🔑 Compte requis | ✅ Oui (Forum & MP) | [📖 Fiche](./f95zone.md) |
| **SmutBase** | `smutbase` | `BasePortalProvider` (Archives 3D) | ✅ **Public (Sans compte)** | ➖ Archive directe | [📖 Fiche](./smutbase.md) |

---

## 4. Ajouter une Nouvelle Plateforme

Pour intégrer un nouveau fournisseur, consultez le contrat d'architecture dans [Architecture Unifiée](../architecture.md) ainsi que la matrice des **7 familles de tests obligatoires** dans `AGENTS.md` à la racine du dépôt.
