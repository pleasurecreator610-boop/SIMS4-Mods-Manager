# 🔌 Catalogue des 22 Plateformes de Mods (`Providers`)

**SIMS 4 Mods Manager** intègre **22 plateformes auto-découvertes** dans [`plugins/`](../../plugins/) et déclarées dans la source unique de vérité [`src/core/provider_metadata.py`](../../src/core/provider_metadata.py).

Chaque plateforme dispose de sa fiche technique détaillée ci-dessous.

---

## 1. 🛡️ Portails Officiels de Frameworks (Priorité Absolue • Sans Compte)

> [!IMPORTANT]
> Conformément à la règle d'or d'architecture, toute dépendance pointant vers l'un de ces frameworks est **systématiquement interceptée et téléchargée depuis son site officiel**, même si la fiche du mod parent pointe vers un lien tiers (LoversLab, CurseForge, ModTheSims ou Patreon).

| Plateforme | ID Technique | Site Officiel | Mods & Frameworks Couverts | Fiche Détaillée |
| :--- | :--- | :--- | :--- | :--- |
| **Deaderpool (MCCC)** | `deaderpool` | `https://deaderpool-mccc.com` | *MC Command Center (MCCC)* & *MC WooHoo* | [📖 Fiche `deaderpool`](./deaderpool.md) |
| **Scumbumbo Memorial** | `scumbumbo` | `https://scumbumbomods.com` | *XML Injector*, *Teleport Any Sim*, *Keep Instruments* | [📖 Fiche `scumbumbo`](./scumbumbo.md) |
| **Lumpinou Mods** | `lumpinou` | `https://www.lumpinoumods.com` | *RPO (WooHoo Wellness)*, *Mood Pack*, *Toolbox*, *LGBTQIA+* | [📖 Fiche `lumpinou`](./lumpinou.md) |
| **Wicked.cc (TURBODRIVER)** | `wickedcc` | `https://wicked.cc` | *WickedWhims* (`+18`), *WonderfulWhims* & animations | [📖 Fiche `wickedcc`](./wickedcc.md) |
| **Basemental CC** | `basemental` | `https://basementalcc.com` | *Basemental Drugs* (`+18`), *Gangs*, *Universal Venue List* | [📖 Fiche `basemental`](./basemental.md) |

---

## 2. 🌟 Catalogues Communautaires & Portails Créateurs SFW

| Plateforme | ID Technique | Moteur / Socle | Compte / Session | Commentaires / MP | Fiche Détaillée |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CurseForge** | `curseforge` | API & Scraper CF + ForgeCDN | Optionnel (Anti-bot) | ✅ Oui | [📖 Fiche `curseforge`](./curseforge.md) |
| **The Sims Resource (TSR)** | `thesimsresource` | Scraper TSR custom | Optionnel | ✅ Oui | [📖 Fiche `thesimsresource`](./thesimsresource.md) |
| **ModTheSims (MTS)** | `modthesims` | vBulletin / MTS Downloader | Optionnel | ✅ Oui | [📖 Fiche `modthesims`](./modthesims.md) |
| **Nexus Mods** | `nexusmods` | API GraphQL v2 + REST v1 | Clé API / Session | ✅ Oui | [📖 Fiche `nexusmods`](./nexusmods.md) |
| **Patreon** | `patreon` | API Posts Créateurs | Optionnel (Abonnés) | ✅ Oui | [📖 Fiche `patreon`](./patreon.md) |
| **SimsFinds** | `simsfinds` | Scraper SimsFinds | Optionnel | ✅ Oui | [📖 Fiche `simsfinds`](./simsfinds.md) |
| **Maxis Match CC World** | `mmccworld` | Tumblr Tag Engine + SFS | Optionnel (Tumblr) | ✅ Oui | [📖 Fiche `mmccworld`](./mmccworld.md) |
| **SimFileShare (SFS)** | `simfileshare` | Résolveur direct `/download/` | ❌ Sans compte | ❌ Non | [📖 Fiche `simfileshare`](./simfileshare.md) |
| **Sims 4 Studio** | `sims4studio` | ProBoards + *Andrew's Pose Player* | Optionnel (Forum) | ✅ Oui | [📖 Fiche `sims4studio`](./sims4studio.md) |
| **GameBanana** | `gamebanana` | API Core v11 JSON (`Game 5508`) | Optionnel | ✅ Oui | [📖 Fiche `gamebanana`](./gamebanana.md) |
| **The Sims Catalog** | `thesimscatalog` | `BasePortalProvider` (WordPress) | ❌ Sans compte | ❌ Non | [📖 Fiche `thesimscatalog`](./thesimscatalog.md) |
| **itch.io** | `itchio` | Catalogue HTML/JSON `tag-sims-4` | Optionnel | ✅ Oui | [📖 Fiche `itchio`](./itchio.md) |
| **LittleMsSam** | `littlemssam` | `BasePortalProvider` (Tumblr/SFS) | ❌ Sans compte | ❌ Non | [📖 Fiche `littlemssam`](./littlemssam.md) |
| **SixamCC** | `sixamcc` | `BasePortalProvider` (Packs CC) | ❌ Sans compte | ❌ Non | [📖 Fiche `sixamcc`](./sixamcc.md) |

---

## 3. 🔞 Portails Adultes (`+18` — Masqués par défaut)

| Plateforme | ID Technique | Moteur / Socle | Compte / Session | Commentaires / MP | Fiche Détaillée |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LoversLab** | `loverslab` | `BaseIPSForumProvider` (IPS4) | Requis / Anti-bot | ✅ Oui (Forum & MP) | [📖 Fiche `loverslab`](./loverslab.md) |
| **NSFWMods** | `nsfwmods` | `BaseIPSForumProvider` (IPS4) | Optionnel / Anti-bot | ✅ Oui (Forum & MP) | [📖 Fiche `nsfwmods`](./nsfwmods.md) |
| **Synthira.ru** | `synthira` | `BasePortalProvider` (DLE/Forum) | Optionnel | ✅ Oui | [📖 Fiche `synthira`](./synthira.md) |
| **F95zone** | `f95zone` | `BasePortalProvider` (XenForo 2) | Requis | ✅ Oui | [📖 Fiche `f95zone`](./f95zone.md) |
| **SmutBase** | `smutbase` | `BasePortalProvider` (Archives 3D) | ❌ Sans compte | ❌ Non | [📖 Fiche `smutbase`](./smutbase.md) |

---

## 4. Ajouter une Nouvelle Plateforme

Pour intégrer un nouveau fournisseur, consultez le contrat normalisé et la matrice des **7 familles de tests obligatoires** dans [`AGENTS.md`](../../AGENTS.md).
