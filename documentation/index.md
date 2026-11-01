# 💎 SIMS 4 Mods Manager

<div class="s4-hero">
  <div class="s4-hero-grid">
    <div class="s4-hero-content">
      <div class="s4-badge-pill">💎 Écosystème Unifié Les Sims 4 • Clean Architecture & POO 3-Tiers</div>
      <h1>Gérez, Résolvez & Protégez tous vos Mods <span>Les Sims 4</span></h1>
      <p>
        Explorez simultanément <strong>22 plateformes de mods</strong>, téléchargez automatiquement vos frameworks
        (<em>MCCC, XML Injector, RPO, WickedWhims, Basemental, Pose Player</em>) depuis leurs <strong>sites officiels</strong>,
        dédupliquez vos installations inter-plateformes et détectez instantanément les conflits binaires <code>.package</code> (DBPF).
      </p>
      <div class="s4-cta-row">
        <a href="features/" class="s4-btn s4-btn-primary">✨ Découvrir les Fonctionnalités</a>
        <a href="providers/" class="s4-btn s4-btn-secondary">🔌 Explorer les 22 Plateformes</a>
        <a href="architecture/" class="s4-btn s4-btn-secondary">🏛️ Architecture & BDD</a>
      </div>
    </div>
    <div class="s4-plumbob-wrap" aria-hidden="true">
      <svg class="s4-plumbob-svg" viewBox="0 0 160 240" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="plumbobTopLeft" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#b9f6ca"/>
            <stop offset="100%" stop-color="#00e676"/>
          </linearGradient>
          <linearGradient id="plumbobTopRight" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#69f0ae"/>
            <stop offset="100%" stop-color="#00c853"/>
          </linearGradient>
          <linearGradient id="plumbobCenter" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#00e676"/>
            <stop offset="100%" stop-color="#00a152"/>
          </linearGradient>
          <linearGradient id="plumbobBottomLeft" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#00c853"/>
            <stop offset="100%" stop-color="#00695c"/>
          </linearGradient>
          <linearGradient id="plumbobBottomRight" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#009624"/>
            <stop offset="100%" stop-color="#004d40"/>
          </linearGradient>
        </defs>
        <!-- Facettes Supérieures du Plumbob -->
        <polygon points="80,10 18,120 55,120" fill="url(#plumbobTopLeft)"/>
        <polygon points="80,10 55,120 105,120" fill="url(#plumbobCenter)"/>
        <polygon points="80,10 105,120 142,120" fill="url(#plumbobTopRight)"/>
        <!-- Facettes Inférieures du Plumbob -->
        <polygon points="80,230 18,120 55,120" fill="url(#plumbobBottomLeft)"/>
        <polygon points="80,230 55,120 105,120" fill="#008e46"/>
        <polygon points="80,230 105,120 142,120" fill="url(#plumbobBottomRight)"/>
        <!-- Arêtes lumineuses -->
        <polyline points="80,10 55,120 80,230 105,120 80,10" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="1.5"/>
        <line x1="18" y1="120" x2="142" y2="120" stroke="rgba(255,255,255,0.5)" stroke-width="1.5"/>
      </svg>
    </div>
  </div>
</div>

<div class="s4-stats-strip">
  <div class="s4-stat-box">
    <span class="s4-stat-number">22</span>
    <span class="s4-stat-label">Plateformes Intégrées</span>
  </div>
  <div class="s4-stat-box">
    <span class="s4-stat-number">100%</span>
    <span class="s4-stat-label">Priorité Sites Officiels</span>
  </div>
  <div class="s4-stat-box">
    <span class="s4-stat-number">O(log N)</span>
    <span class="s4-stat-label">Moteur SQLite FTS5 & B-Tree</span>
  </div>
  <div class="s4-stat-box">
    <span class="s4-stat-number">Zero-Copy</span>
    <span class="s4-stat-label">Analyse Binaire DBPF mmap</span>
  </div>
  <div class="s4-stat-box">
    <span class="s4-stat-number">477</span>
    <span class="s4-stat-label">Tests Unitaires & E2E</span>
  </div>
</div>

---

## 🌟 Les 6 Piliers de l'Application

<div class="s4-features-grid">
  <div class="s4-feature-card">
    <span class="s4-feature-icon">🌐</span>
    <h3>1. Catalogue Unifié (22 Sources)</h3>
    <p>
      Agrège en temps réel les frameworks officiels, les catalogues communautaires SFW et les portails adultes
      (masqués par défaut) avec recherche plein texte <code>SQLite FTS5</code> et filtre indexé par type de mod.
    </p>
  </div>
  <div class="s4-feature-card">
    <span class="s4-feature-icon">🛡️</span>
    <h3>2. Priorité Absolue aux Sites Officiels</h3>
    <p>
      Toute dépendance vers <strong>MCCC (Deaderpool)</strong>, <strong>XML Injector (Scumbumbo)</strong>,
      <strong>RPO / Mood Pack (Lumpinou)</strong>, <strong>WickedWhims (Wicked.cc)</strong>, <strong>Basemental</strong>
      ou <strong>Pose Player</strong> est redirigée en O(1) vers son site officiel public sans compte requis.
    </p>
  </div>
  <div class="s4-feature-card">
    <span class="s4-feature-icon">🧩</span>
    <h3>3. Déduplication Inter-Plateformes</h3>
    <p>
      L'empreinte canonique <code>title_fingerprint</code> reconnaît un même mod entre CurseForge, ModTheSims,
      Patreon ou LoversLab, évite toute réinstallation en doublon et filtre automatiquement les consignes d'auteurs (<code>COMMENT_NOISE</code>).
    </p>
  </div>
  <div class="s4-feature-card">
    <span class="s4-feature-icon">📢</span>
    <h3>4. Interpellation & MP aux Créateurs</h3>
    <p>
      Publiez un commentaire ou envoyez un message privé standardisé à l'auteur lorsqu'un prérequis est manquant,
      avec vérification anti-doublon automatique, invitation à s'authentifier et révocation en 1 clic.
    </p>
  </div>
  <div class="s4-feature-card">
    <span class="s4-feature-icon">⚔️</span>
    <h3>5. Détecteur de Conflits DBPF (mmap)</h3>
    <p>
      Inspecte les tables d'index binaires <code>TGI (Type-Group-Instance)</code> de vos fichiers <code>.package</code>
      sans copie RAM, distingue les collisions de Tuning des traductions <code>STBL</code> et désactive les conflits en 1 clic.
    </p>
  </div>
  <div class="s4-feature-card">
    <span class="s4-feature-icon">📦</span>
    <h3>6. Règle .ts4script & Rollback ZIP</h3>
    <p>
      Remonte automatiquement les scripts <code>.ts4script</code> au niveau 1 (exigence stricte du jeu Les Sims 4),
      préserve vos fichiers de configuration et crée une sauvegarde ZIP restaurable avant chaque mise à jour.
    </p>
  </div>
</div>

---

## 🔌 Explorateur Interactif des 22 Plateformes Intégrées

Cliquez sur un filtre ou tapez le nom d'un créateur/mod pour explorer les **22 plateformes** et accéder à leur fiche technique :

<div class="s4-filter-toolbar">
  <button class="s4-filter-btn active" data-filter="all">✨ Toutes (22)</button>
  <button class="s4-filter-btn" data-filter="official">🛡️ Frameworks Officiels (5)</button>
  <button class="s4-filter-btn" data-filter="sfw">🌟 Catalogues & Créateurs SFW (12)</button>
  <button class="s4-filter-btn" data-filter="adult">🔞 Portails Adultes +18 (5)</button>
  <button class="s4-filter-btn" data-filter="no-account">🔓 Sans Compte (10)</button>
  <button class="s4-filter-btn" data-filter="comments">💬 Commentaires / MP (13)</button>
  <input id="s4-provider-search" class="s4-search-input" type="search" placeholder="🔍 Filtrer (ex: MCCC, XML Injector, CurseForge, Lumpinou...)" />
</div>

<div class="s4-providers-grid">
  <a class="s4-provider-card" href="providers/deaderpool/" data-category="official" data-tags="official,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">⚙️ Deaderpool (MCCC)</span>
        <span class="s4-tag s4-tag-official">Officiel</span>
      </div>
      <div class="s4-provider-desc">Site officiel de MC Command Center (MCCC) et MC WooHoo. Priorité absolue sur toute dépendance MCCC.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>⚡ API / Direct</span></div>
  </a>

  <a class="s4-provider-card" href="providers/scumbumbo/" data-category="official" data-tags="official,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🧪 Scumbumbo Memorial</span>
        <span class="s4-tag s4-tag-official">Officiel</span>
      </div>
      <div class="s4-provider-desc">Portail officiel de XML Injector, Teleport Any Sim, Keep Instruments et utilitaires scripts Sims 4.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>⚡ Direct ZIP/Package</span></div>
  </a>

  <a class="s4-provider-card" href="providers/lumpinou/" data-category="official" data-tags="official,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">💖 Lumpinou Mods</span>
        <span class="s4-tag s4-tag-official">Officiel</span>
      </div>
      <div class="s4-provider-desc">Site officiel de RPO (Relationship & Pregnancy Overhaul), Mood Pack Mod, Lumpinou's Toolbox et LGBTQIA+.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>⚡ Direct / SFS</span></div>
  </a>

  <a class="s4-provider-card" href="providers/wickedcc/" data-category="official" data-tags="official,adult,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🔥 Wicked.cc (TURBODRIVER)</span>
        <span class="s4-tag s4-tag-official">Officiel</span>
      </div>
      <div class="s4-provider-desc">Portail officiel de WickedWhims, WonderfulWhims et du répertoire officiel des créateurs d'animations.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>🔞 +18 / SFW</span></div>
  </a>

  <a class="s4-provider-card" href="providers/basemental/" data-category="official" data-tags="official,adult,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🌿 Basemental CC</span>
        <span class="s4-tag s4-tag-official">Officiel</span>
      </div>
      <div class="s4-provider-desc">Site officiel de Basemental Drugs, Basemental Gangs et du framework Universal Venue List.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>🔞 +18</span></div>
  </a>

  <a class="s4-provider-card" href="providers/curseforge/" data-category="sfw" data-tags="sfw,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🔥 CurseForge</span>
        <span class="s4-tag s4-tag-sfw">Catalogue SFW</span>
      </div>
      <div class="s4-provider-desc">Catalogue officiel Sims 4 avec téléchargement direct ForgeCDN, détection des dépendances et commentaires.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte optionnel</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/thesimsresource/" data-category="sfw" data-tags="sfw,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">👗 The Sims Resource (TSR)</span>
        <span class="s4-tag s4-tag-sfw">Catalogue SFW</span>
      </div>
      <div class="s4-provider-desc">Plus grand catalogue mondial de Custom Content (coiffures, vêtements, meubles, maquillage et mods).</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte optionnel</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/modthesims/" data-category="sfw" data-tags="sfw,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🛠️ ModTheSims (MTS)</span>
        <span class="s4-tag s4-tag-sfw">Catalogue SFW</span>
      </div>
      <div class="s4-provider-desc">Portail historique de mods de gameplay, scripts, traits, carrières et utilitaires pour Les Sims 4.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte optionnel</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/nexusmods/" data-category="sfw" data-tags="sfw,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">⚡ Nexus Mods</span>
        <span class="s4-tag s4-tag-sfw">Catalogue SFW</span>
      </div>
      <div class="s4-provider-desc">Intégration GraphQL v2 et API REST v1 pour les mods Sims 4, presets Reshade et refontes de gameplay.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Clé API / Session</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/patreon/" data-category="sfw" data-tags="sfw,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🎨 Patreon</span>
        <span class="s4-tag s4-tag-sfw">Créateurs</span>
      </div>
      <div class="s4-provider-desc">Synchronisation des publications publiques et abonnés des créateurs de mods et CC Sims 4.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte optionnel</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/simsfinds/" data-category="sfw" data-tags="sfw,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🔎 SimsFinds</span>
        <span class="s4-tag s4-tag-sfw">Catalogue SFW</span>
      </div>
      <div class="s4-provider-desc">Répertoire communautaire de Custom Content, meubles, tenues et mods avec téléchargement direct.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte optionnel</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/mmccworld/" data-category="sfw" data-tags="sfw,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🌈 Maxis Match CC World</span>
        <span class="s4-tag s4-tag-sfw">Maxis Match</span>
      </div>
      <div class="s4-provider-desc">Plus grand annuaire Tumblr de créations Maxis Match avec résolution automatique SimFileShare & Patreon.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte Tumblr opt.</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/simfileshare/" data-category="sfw" data-tags="sfw,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">📁 SimFileShare (SFS)</span>
        <span class="s4-tag s4-tag-sfw">Hébergeur Direct</span>
      </div>
      <div class="s4-provider-desc">Résolveur natif haute vitesse pour tous les fichiers individuels et dossiers partagés SimFileShare.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>⚡ Direct CDN</span></div>
  </a>

  <a class="s4-provider-card" href="providers/sims4studio/" data-category="sfw" data-tags="sfw,official,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🎬 Sims 4 Studio</span>
        <span class="s4-tag s4-tag-sfw">Officiel & Studios</span>
      </div>
      <div class="s4-provider-desc">Hébergeur officiel d'Andrew's Pose Player, Teleport Any Sim et des Creator Studios communautaires.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte Forum opt.</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/gamebanana/" data-category="sfw" data-tags="sfw,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🍌 GameBanana</span>
        <span class="s4-tag s4-tag-sfw">API Core v11</span>
      </div>
      <div class="s4-provider-desc">Catalogue Sims 4 propulsé par l'API JSON publique Core v11 de GameBanana (Game ID 5508).</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte optionnel</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/thesimscatalog/" data-category="sfw" data-tags="sfw,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">📚 The Sims Catalog</span>
        <span class="s4-tag s4-tag-sfw">Catalogue SFW</span>
      </div>
      <div class="s4-provider-desc">Portail public de mods de gameplay, carrières, traits de caractère et coiffures Sims 4.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>⚡ Public</span></div>
  </a>

  <a class="s4-provider-card" href="providers/itchio/" data-category="sfw" data-tags="sfw,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🎮 itch.io (Sims 4)</span>
        <span class="s4-tag s4-tag-sfw">Créateurs Indés</span>
      </div>
      <div class="s4-provider-desc">Mods indépendants, outils et créations tagués <code>sims-4</code> sur la plateforme itch.io.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte optionnel</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/littlemssam/" data-category="sfw" data-tags="sfw,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🌟 LittleMsSam's Mods</span>
        <span class="s4-tag s4-tag-sfw">Créatrice Majeure</span>
      </div>
      <div class="s4-provider-desc">Plus de 200 mods de gameplay, Random Small Mods (RSM) et correctifs maintenus à chaque patch EA.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>⚡ Direct / SFS</span></div>
  </a>

  <a class="s4-provider-card" href="providers/sixamcc/" data-category="sfw" data-tags="sfw,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🛋️ SixamCC</span>
        <span class="s4-tag s4-tag-sfw">Packs CC</span>
      </div>
      <div class="s4-provider-desc">Packs d'objets, mobilier et décoration Maxis Match conçus comme des Kits officiels Sims 4.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>⚡ Direct</span></div>
  </a>

  <a class="s4-provider-card" href="providers/loverslab/" data-category="adult" data-tags="adult,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🔞 LoversLab</span>
        <span class="s4-tag s4-tag-adult">Adulte +18</span>
      </div>
      <div class="s4-provider-desc">Catalogue complet Sims 4 Adulte (14 sous-catégories, animations, frameworks, support Forum IPS4 & MP).</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte requis</span> • <span>💬 Forum & MP</span></div>
  </a>

  <a class="s4-provider-card" href="providers/nsfwmods/" data-category="adult" data-tags="adult,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🔞 NSFWMods</span>
        <span class="s4-tag s4-tag-adult">Adulte +18</span>
      </div>
      <div class="s4-provider-desc">Portail communautaire de mods adultes, animations et accessoires Sims 4 sur moteur IPS4.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte optionnel</span> • <span>💬 Forum & MP</span></div>
  </a>

  <a class="s4-provider-card" href="providers/synthira/" data-category="adult" data-tags="adult,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🔞 Synthira.ru</span>
        <span class="s4-tag s4-tag-adult">Adulte +18</span>
      </div>
      <div class="s4-provider-desc">Portail Sims 4 (+18) regroupant mods adultes, animations WickedWhims et traductions.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte optionnel</span> • <span>💬 Commentaires</span></div>
  </a>

  <a class="s4-provider-card" href="providers/f95zone/" data-category="adult" data-tags="adult,comments">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🔞 F95zone (Sims 4)</span>
        <span class="s4-tag s4-tag-adult">Adulte +18</span>
      </div>
      <div class="s4-provider-desc">Fils dédiés aux mods Sims 4, packs d'animations et scripts sur le forum XenForo 2 F95zone.</div>
    </div>
    <div class="s4-provider-meta"><span>🔑 Compte requis</span> • <span>💬 Forum & MP</span></div>
  </a>

  <a class="s4-provider-card" href="providers/smutbase/" data-category="adult" data-tags="adult,no-account">
    <div>
      <div class="s4-provider-head">
        <span class="s4-provider-title">🔞 SmutBase</span>
        <span class="s4-tag s4-tag-adult">Adulte +18</span>
      </div>
      <div class="s4-provider-desc">Archive publique d'assets 3D, rigs, accessoires et ressources d'animation compatibles Sims 4.</div>
    </div>
    <div class="s4-provider-meta"><span>🔓 Sans compte</span> • <span>⚡ Direct</span></div>
  </a>
</div>

---

## 🧭 Sommaire Général de la Documentation

| Section | Description | Lien Direct |
| :--- | :--- | :--- |
| ✨ **Fonctionnalités** | Guide illustré complet de toutes les fonctionnalités utilisateur | [Consulter `features.md`](features.md) |
| 🔌 **22 Plateformes** | Comparatif technique et fiches dédiées des 22 providers | [Consulter `providers/README.md`](providers/README.md) |
| 🏛️ **Architecture & BDD** | Clean Architecture, POO 3-Tiers, SQLite WAL/FTS5, DBPF `mmap` | [Consulter `architecture.md`](architecture.md) |
| 🧩 **Dépendances & Bruit** | Priorité aux sites officiels, `ModMatcher` et classification `COMMENT_NOISE` | [Consulter `dependency_classification_and_noise.md`](dependency_classification_and_noise.md) |
| 🌐 **API REST FastAPI** | Référence complète des endpoints REST et flux NDJSON | [Consulter `api_reference.md`](api_reference.md) |
| 📐 **Décisions ADR** | Architecture Decision Records (ADR 0001 à 0005) | [Consulter `adr/index.md`](adr/index.md) |
