# Résolution des Dépendances, Priorité Officielle, Filtrage du Bruit & Signalement Créateurs

Ce document décrit le pipeline complet d'extraction, de redirection officielle, de déduplication inter-plateformes, de filtrage du bruit et de signalement aux créateurs de **SIMS 4 Mods Manager**.

---

## 1. Priorité Absolue aux Sites Officiels des Frameworks (`SPECIAL_DEPENDENCY_CASES`)

De nombreux mods publiés sur LoversLab, CurseForge, ModTheSims, Patreon, F95zone ou Synthira dépendent de grands frameworks communautaires. Afin d'éviter les miroirs obsolètes et les blocages d'authentification, [`src/application/dependencies/dependency_special_cases.py`](../src/application/dependencies/dependency_special_cases.py) intercepte en priorité absolue ces dépendances et les redirige vers leur **site officiel public** (aucun compte requis) :

| Framework / Mod | Provider Officiel | ID Canonique | URL Officielle Prioritaire | Principaux Alias Reconnus |
| :--- | :--- | :--- | :--- | :--- |
| **WickedWhims** | `wickedcc` | `3169` | `https://wicked.cc/download/3169-wickedwhims/` | `WW`, `WickedWhims`, `Wicked-Whims`, `Wicked_Whims`, `loverslab.com/.../3169` |
| **WonderfulWhims** | `wickedcc` | `wonderfulwhims_official` | `https://wonderfulwhims.com/` | `WonderfulWhims`, `Wonderful Whims` |
| **MC Command Center** | `deaderpool` | `deaderpool_mccc` | `https://deaderpool-mccc.com/downloads.html#mccc` | `MCCC`, `MC Command Center`, `Deaderpool MCCC` |
| **MC WooHoo** | `deaderpool` | `deaderpool_mc_woohoo` | `https://deaderpool-mccc.com/downloads.html#mcwoohoo` | `MC WooHoo`, `MCWooHoo` |
| **XML Injector** | `scumbumbo` | `scumbumbo_xml_injector` | `https://scumbumbomods.com/xml-injector` | `XML Injector`, `Scumbumbo XML Injector`, `xmlinjector` |
| **Teleport Any Sim** | `scumbumbo` | `scumbumbo_teleport_any_sim` | `https://scumbumbomods.com/teleport-any-sim` | `Teleport Any Sim`, `Andrew's Teleport Any Sim` |
| **RPO (WooHoo Wellness)** | `lumpinou` | `lumpinou_rpo_collection` | `https://www.lumpinoumods.com/woohoo-wellness-and-pregnancy-overhaul` | `RPO`, `Relationship & Pregnancy Overhaul`, `WooHoo Wellness` |
| **Mood Pack Mod** | `lumpinou` | `lumpinou_mood_pack` | `https://www.lumpinoumods.com/mood-pack-mod/` | `Mood Pack Mod`, `Lumpinou Mood Pack` |
| **Lumpinou's Toolbox** | `lumpinou` | `lumpinou_toolbox` | `https://www.lumpinoumods.com/lumpinous-toolbox/` | `Lumpinou's Toolbox`, `Lumpinou Toolbox Library` |
| **LGBTQIA+ Mod** | `lumpinou` | `lumpinou_lgbtqia` | `https://www.lumpinoumods.com/lgbtqia-mod/` | `Lumpinou LGBTQIA+`, `LGBTQIA Mod` |
| **Basemental Drugs** | `basemental` | `basemental_drugs` | `https://basementalcc.com/adult_mods/basemental-drugs/` | `Basemental Drugs`, `Basemental Drug` |
| **Basemental Gangs** | `basemental` | `basemental_gangs` | `https://basementalcc.com/adult_mods/basemental-gangs/` | `Basemental Gangs` |
| **Universal Venue List** | `basemental` | `basemental_universal_venue_list` | `https://basementalcc.com/mods/universal-venue-list/` | `Universal Venue List`, `Basemental Venue List` |
| **Andrew's Pose Player** | `sims4studio` | `s4s_pose_player` | `https://sims4studio.com/thread/2617/andrews-studio` | `Andrew's Pose Player`, `Andrew's Studio Pose Player`, `Pose Player` |

---

## 2. Déduplication Inter-Plateformes & Installations Multiples

1. **Empreinte Canonique Inter-Plateformes (`ModMatcher.canonical_fingerprint`)** :
   - Nettoie les préfixes (`The Sims 4`, `[TS4]`), les numéros de version (`v1.4`, `2026.2.0`) et la ponctuation.
   - Si un mod a été installé depuis `scumbumbo`, `littlemssam` ou `wickedcc`, et qu'un mod téléchargé depuis `f95zone`, `thesimscatalog` ou `loverslab` le réclame via un lien `curseforge` ou `modthesims`, le résolveur le détecte immédiatement comme **`INSTALLED`** sans le re-télécharger.
2. **Registre d'Installations Actives (`ActiveInstallationRegistry`)** :
   - Lors de l'installation simultanée de plusieurs mods partageant une ou plusieurs dépendances (de la même plateforme ou de plateformes différentes), `ActiveInstallationRegistry` verrouille chaque dépendance par `(source, remote_id)` et par empreinte canonique de titre.

---

## 3. Filtrage du Bruit (`COMMENT_NOISE`) & Surcharge Utilisateur (`MOD` $\leftrightarrow$ `COMMENT`)

- **Détection Heuristique (`src/utils/dependency_noise_rules.py`)** :
  - Identifie automatiquement les consignes de jeu (*"Script Mods Enabled in Game Options"*), les notes de compatibilité (*"Compatible with patch 1.110+"*) et les mentions d'auteurs (*"Please do not reupload"*) en tant que **`COMMENT_NOISE`**.
- **Surcharge Manuelle (`requirements_overrides`)** :
  - Dans l'interface ou via l'API, l'utilisateur peut basculer tout élément entre **`MOD`** (vrai mod requis) et **`COMMENT`** (simple note ignorée).

---

## 4. Signalement & Commentaires aux Créateurs (`RequirementReporterService`)

Lorsqu'un prérequis est introuvable ou qu'une note pollue la section *Requirements*, l'utilisateur peut contacter l'auteur sur les plateformes compatibles (`loverslab`, `nsfwmods`, `curseforge`, `thesimsresource`, `modthesims`, `simsfinds`, `nexusmods`, `mmccworld`, `sims4studio`, `f95zone`, `gamebanana`, `itchio`, `synthira`) :
1. **Vérification d'Authentification** : Si `SessionManager.is_member_authenticated(source)` vaut `False`, l'application invite l'utilisateur à se connecter dans l'onglet **Comptes & Anti-Bot**.
2. **Anti-Doublon en Direct** : `check_report_status` inspecte la page du mod en direct pour vérifier si l'utilisateur a déjà signalé ce prérequis.
3. **Publication & Suppression** : `submit_report` publie le message en anglais standardisé (en commentaire ou en MP) et `delete_report` permet de supprimer le commentaire publié.
