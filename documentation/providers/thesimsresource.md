# Fournisseur The Sims Resource (TSR)

Le fournisseur `thesimsresource` assure l'indexation de la plateforme **The Sims Resource (TSR)**, l'extraction des meshes requis et le téléchargement via le protocole officiel de tickets AJAX.

---

## 1. Caractéristiques Principales

- **Endpoint Officiel** : `https://www.thesimsresource.com/downloads/browse/category/sims4/skipsetitems/1/`
- **12 Catégories Scrappées** :
  1. Mods (`sims4-mods`)
  2. Clothing (`sims4-clothing`)
  3. Hair (`sims4-hair`)
  4. Shoes (`sims4-shoes`)
  5. Accessories (`sims4-accessories`)
  6. Makeup (`sims4-makeup`)
  7. Skintones (`sims4-skintones`)
  8. Eye Colors (`sims4-eyecolors`)
  9. Objects (`sims4-objects`)
  10. Sets (`sims4-sets`)
  11. Lots & Rooms (`sims4-lots`)
  12. Sims (`sims4-sims`)

---

## 2. Protocole de Téléchargement par Ticket AJAX

TSR utilise un mécanisme de temporisation et de validation de ticket pour les téléchargements :

1. **Initialisation** : Appel à `/ajax.php?c=downloads&a=initDownload&itemid={id}&format=zip` pour générer un jeton `ticket`.
2. **Attente & Session** : Initialisation du cookie de session `tsrdlsession`.
3. **Sondage** : Requêtes successives à `/ajax.php?c=downloads&a=getdownloadurl` jusqu'à validation du délai (configurable via `ticket_poll_interval`).
4. **Streaming S3** : Téléchargement du binaire `.package` ou `.zip` depuis les serveurs signés TSR / AWS S3.

---

## 3. Extraction des Meshes & Dépendances

- Extraction automatique des attributs `RequiredItems` et `requiredDownloadIds` dans le JSON embarqué `data-item`.
- Extraction des liens de mesh dans le bloc `.required-items` et la description HTML.
