# Détection, Redirection Officielle & Résolution des Dépendances

## 1. Priorité Absolue aux Sites Officiels (`SPECIAL_DEPENDENCY_CASES`)
Dans [`src/application/dependencies/dependency_special_cases.py`](../../src/application/dependencies/dependency_special_cases.py), les frameworks majeurs sont systématiquement interceptés en priorité absolue par `find_special_dependency_case(title, url, remote_id)` avant toute recherche par `remote_id` tiers :
- **Deaderpool (`deaderpool`)** : *MC Command Center (MCCC)* & *MC WooHoo* (`https://deaderpool-mccc.com`)
- **Scumbumbo (`scumbumbo`)** : *XML Injector*, *Teleport Any Sim*, etc. (`https://scumbumbomods.com`)
- **Lumpinou (`lumpinou`)** : *RPO (WooHoo Wellness)*, *Mood Pack Mod*, *Lumpinou's Toolbox*, *LGBTQIA+ Mod* (`https://www.lumpinoumods.com`)
- **Wicked.cc (`wickedcc`)** : *WickedWhims* (`remote_id: "3169"`, `https://wicked.cc/download/3169-wickedwhims/`) & *WonderfulWhims* (`https://wonderfulwhims.com/`)
- **Basemental (`basemental`)** : *Basemental Drugs*, *Basemental Gangs*, *Universal Venue List* (`https://basementalcc.com`)
- **Sims 4 Studio (`sims4studio`)** : *Andrew's Pose Player* (`https://sims4studio.com/thread/2617/andrews-studio`)

Même si l'auteur d'un mod a mis un lien vers LoversLab (`#3169`), CurseForge ou ModTheSims pour l'un de ces frameworks, la dépendance est redirigée vers son site officiel public (sans compte requis).

---

## 2. Déduplication Inter-Plateformes & Concurrence
1. **`ModMatcher.canonical_fingerprint`** :
   - Permet de reconnaître qu'un mod déjà installé depuis une plateforme A (ex. `scumbumbo`, `littlemssam`, `wickedcc`) correspond au prérequis demandé sur une plateforme B (`curseforge`, `f95zone`, `thesimscatalog`, `loverslab`), et le marque `INSTALLED` sans le re-télécharger.
2. **`ActiveInstallationRegistry`** :
   - Garantit que lors de l'installation simultanée de plusieurs mods partageant une même dépendance, un seul thread la télécharge et l'installe tandis que les autres attendent sa fin.

---

## 3. Classification `MOD` vs `COMMENT_NOISE` & Signalement Créateurs
- Les phrases narratives et consignes de configuration sont automatiquement classées en `COMMENT_NOISE`.
- L'utilisateur peut forcer la qualification d'un élément en `MOD` ou `COMMENT` via `requirements_overrides`.
- Pour les prérequis introuvables (`NOT_DETECTED_FINISHED`), `RequirementReporterService` vérifie d'abord si l'utilisateur est authentifié (`SessionManager.is_member_authenticated(source)`), lui demande de se connecter si nécessaire, vérifie l'absence de doublon en direct sur la page, puis publie le commentaire ou MP en anglais standardisé.
