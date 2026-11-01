# Fournisseur LoversLab (`loverslab` • `+18`)

Le fournisseur `loverslab` connecte **SIMS 4 Mods Manager** à la section **The Sims 4 Downloads** du forum Invision Community (IPS4) **LoversLab** (`loverslab.com/files/category/161-the-sims-4/`).

---

## 1. Caractéristiques Techniques

- **Identifiant Provider** : `loverslab`
- **Classe d'Implémentation** : [`plugins/loverslab/provider.py`](https://github.com/pleasurecreator610-boop/SIMS4-Mods-Manager/blob/main/plugins/loverslab/provider.py) (`LoversLabProvider`, héritant de `BaseIPSForumProvider`)
- **URL Officielle** : `https://www.loverslab.com`
- **Contenu Adulte (`+18`)** : Oui (`ADULT_PROVIDERS`)
- **Compte & Anti-Bot** : Supporte le contournement Cloudflare (`cf_clearance`), le cookie d'âge (`ips4_hasAcceptedAge=1`) et la session membre (`ips4_member_id`).

---

## 2. Sous-Catégories & Résolution Officielle

- **14 Sous-Catégories Sims 4** parcourues en parallèle.
- **Redirection Officielle Prioritaire** : Lorsqu'un mod LoversLab requiert *WickedWhims* (`#3169`), *MC Command Center*, *XML Injector*, *Lumpinou* ou *Basemental*, le résolveur redirige automatiquement le téléchargement vers le site officiel du framework (`wicked.cc`, `deaderpool-mccc.com`, `scumbumbomods.com`, `lumpinoumods.com`, `basementalcc.com`).
- **Commentaires & Messages Privés IPS4** : Support complet via `LoversLabForumService` et `RequirementReporterService`.

