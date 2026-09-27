# Audit complet de l'écosystème Existence
### Comparaison directe avec Photoshop et Krita
*Date : 25 septembre 2026 — basé sur l'état réel des sources*

---

## 1. Vue d'ensemble de l'écosystème

L'écosystème Existence est un ensemble d'applications Linux indépendantes réunies par un hub central appelé **Existence** (anciennement Existence). Il s'articule en 5 composants actifs :

| Composant | Rôle | Technologie | État |
|---|---|---|---|
| **Existence** (`galaxy_hub.py`) | Hub / environnement central | Python + PySide6 (Qt 6) | Actif, architecture définie |
| **Atlas** (`Atlas`) | Éditeur vectoriel | C++17 + GTK (UI) + CMake | Alpha — moteur vectoriel partiel |
| **Nebula** | Peinture raster | Python (PySide6) | Présent mais non auditable ici |
| **Cosmos** | Notes reliées / PKM | C++ + Qt WebEngine + JS | Le plus mature fonctionnellement |
| **Singularity** | Traitement d'image / webready | Python | Prototype léger |
| **StarDust** | Rôle orbital (bridge ?) | Python | Embryonnaire |

---

## 2. Existence — Le hub central

### Ce qui existe concrètement

- **Catalogue d'apps** persisté en JSON (`~/.config/existence/apps.json`) avec écriture atomique.
- **Carte interactive** avec drag-and-drop des "astres", positions normalisées, filtre par domaine et par nature (`universe`, `orbital_module`, `service`…).
- **IPC réel** (`existence_ipc.py`) : transport JSON-lines processus-à-processus, routeur de messages avec validation source/cible/ressource/permission.
- **Registre de ressources** (`resource://existence/atlas/image/xyz`) — URI nommées, droits `read/write/reference`, versionnement.
- **Session de travail** (`WorkspaceSessionManager`) : suivi de PID, états `active/closed/error`, restauration au démarrage.
- **Mode embarqué Wayland** : `embedded_views.py` fournit des vues natives Nebula, Cosmos (`QWebEngineView`) et Atlas (`AtlasEmbeddedView` via son endpoint compilé) intégrables dans la Workplace sans reparentage de fenêtre étrangère.
- **Tests du noyau** (`test_existence_core.py`, `test_existence_manifests.py`) couvrant les routes critiques Atlas→Nebula, rejets de ressource invalide, etc.

### Points forts
- Architecture non-monolithique clairement définie et respectée dans le code.
- Le principe "Existence fournit l'environnement, les univers restent autonomes" est réel, pas juste une doc.
- L'IPC + registre de ressources constituent une vraie colonne vertébrale d'interopérabilité.

### Manques objectifs
- Pas d'installateur d'app fonctionnel (déclaré mais non implémenté).
- Les "wormholes" visuels (passages entre univers sur la carte) ne sont pas encore construits.
- Le contrat `Universe/Module/Service/Capability` est spécifié mais pas encore stabilisé dans le code.
- Embedding mode Wayland d'Atlas est fonctionnel côté surface et moteur, mais le portage complet de l'UI GTK vers Qt est une évolution distincte non encore faite.

---

## 3. Atlas — Éditeur vectoriel

### Ce qui existe concrètement (état 24 sept 2026)

**Moteur vectoriel (`engine/vector/`) :**
- Modèle de données : `VectorDocument`, `VectorLayer`, `VectorShape` avec types `Path`, `Rectangle`, `Ellipse`, `Polygon`, `Star`, `Group`, `Text`.
- `flatten()` : conversion formes → contours polygonaux, corrigé pour les polygones paramétrables (n côtés), ellipses adaptatives (subdivision dépendant du rayon) et Bézier avec plafond 4096 points.
- **Pathfinder booléen (Clipper2 2.0.1)** : intégré sous `third_party/clipper2/`, licence Boost. Union, Intersection, Différence, XOR opérationnels. Tests `AtlasVectorBooleanTests` passent (flattening + booléen).
- Sérialisation projet (`engine/serialization/atlas_project.cpp`).
- Moteur de brosse (`engine/brush/`), compositor de calques, tile store, threading pool.
- **Existence adapter** compilé : `AtlasExistenceAdapter` — endpoint permettant à Existence de piloter le backend Atlas indépendamment de l'UI GTK.

**UI :**
- `ui/gtk/vector_main.cpp` (~140 Ko) : éditeur GTK vectoriel complet.
- `ui/gtk/color_wheel.cpp` : sélecteur de couleur natif.
- Build système : CMake, deux cibles (`build/` et `build_atlas/`), tests CTest.

**Tests :**
- `AtlasExistenceSmoke` : passe.
- `AtlasVectorBooleanTests` : passe (8 tests flattening + 5 tests Pathfinder avec Clipper2).
- `AtlasExistenceAdapter` : compilé et lié.

---

## 4. Cosmos — Notes reliées

### Ce qui existe concrètement

C'est le composant le plus fonctionnel de l'écosystème. Voici ce qu'il fait réellement :

- **Éditeur par blocs** (style Notion) : `/` menu, 15+ types de blocs, glisser-déposer, titres/listes/tâches/tableaux/code/images.
- **Graphe 3D/2D full GPU** : nœuds et liens dans des tampons uniques, galaxies spirales en shader, jusqu'à 30 000 nœuds, FPS adaptatif.
- **Bases de données** : 10+ types de propriétés, vues Tableau/Kanban/Calendrier/Galerie/Liste, filtres, tris, export CSV.
- **Import Notion** : HTML + Markdown fusionnés, types de propriétés reconstruits, icônes et couvertures, relations inter-pages, bases de données avec vues.
- **Multi-projets**, onglets, arborescence de pages illimitée, glisser-déposer de pages.
- **Coffre** : sauvegarde atomique C++, 30 backups datés, changement de dossier à chaud.
- **Intégration Existence** : `existence-manifest.json`, pont `window.cosmosExistence`, vue embarquable `QWebEngineView`.

---

## 5. Singularity et StarDust

**Singularity** (`webready.py`, 27 Ko) : traitement et conversion d'images, packaging. Dispose d'un `existence-manifest.json` et d'un `existence_adapter.py`. Clairement en phase de prototype.

**StarDust** (`main.py`, 74 Ko) : bridge avec `core_bridge.py` et un manifest Existence. Rôle exact non précisé dans les docs disponibles, mais présent dans l'écosystème avec son manifest.

---

## 6. Comparaison directe : Atlas vs Photoshop vs Krita

> ⚠️ Comparaison honnête et non commerciale. Photoshop = PS, Krita = KR.

### 6.1 Dessin et édition vectorielle

| Capacité | PS (vectoriel) | KR (vectoriel) | **Atlas** |
|---|---|---|---|
| Formes de base | ✅ Complet | ✅ Complet | ✅ Rect, Ellipse, Polygone(n), Étoile(n,ratio), Path |
| Pathfinder booléen | ✅ (Clipper interne) | ✅ | ✅ **Clipper2 2.0.1 — passe les tests** |
| Contours (pointillés, caps, joins) | ✅ | ✅ | ❌ Absent du modèle |
| Profil de largeur variable | ✅ | ✅ (via brushes) | ❌ |
| Dégradés (linéaire, radial, maille) | ✅ Complet | ✅ | ⚠️ Linéaire 2 arrêts seulement |
| Texte sur tracé | ✅ | ✅ | ❌ |
| Vectorisation d'image | ✅ (Live Trace) | ❌ | ❌ |
| Plans de travail multiples | ✅ | ❌ | ❌ |
| Masques d'écrêtage | ✅ | ✅ | ❌ |
| Symboles / composants réutilisables | ✅ | ❌ | ❌ |
| Export SVG/PDF propre | ✅ | ✅ | ⚠️ Non validé publiquement |

### 6.2 Peinture et raster

*(Note : le raster est le domaine de **Nebula**, non d'Atlas.)*

| Capacité | PS | KR | **Nebula (estimé)** |
|---|---|---|---|
| Brosse bitmap | ✅ | ✅ | ✅ (`bitmap_brush.cpp` présent) |
| Brosse avancée (texture, wet) | ✅ | ✅ | ⚠️ `advanced_brushes.cpp` présent |
| Calques et modes de fusion | ✅ | ✅ | ⚠️ `layer_compositor.cpp` présent |
| Gestion mémoire tuiles | ✅ | ✅ | ✅ `tile_store.cpp` présent |
| Tablette XP-Pen (pression, inclinaison) | ✅ | ✅ | ✅ (`atlas_xppen_events.txt` — XP-Pen intégré) |
| Historique d'annulations | ✅ | ✅ | ❓ Non confirmé |
| Peinture HDR | ✅ | ✅ | ❓ |

### 6.3 Organisation et gestion de projet

| Capacité | PS | KR | **Existence / Cosmos** |
|---|---|---|---|
| Hub multi-app | ❌ | ❌ | ✅ Existence |
| Notes reliées / PKM intégré | ❌ | ❌ | ✅ Cosmos |
| Graphe visuel de connaissances | ❌ | ❌ | ✅ Cosmos (GPU, 30K nœuds) |
| Import Notion | ❌ | ❌ | ✅ Cosmos |
| Communication inter-apps | ❌ | ❌ | ✅ IPC JSON-lines + registre de ressources |
| Registre de ressources partagées | ❌ | ❌ | ✅ Existence |

### 6.4 Plateforme et écosystème

| Aspect | PS | KR | **Existence** |
|---|---|---|---|
| OS | Win/Mac | Win/Mac/Linux | **Linux-first** (Wayland natif) |
| Licence | Propriétaire ($$$) | GPL libre | Code perso / Open si voulu |
| Prix | 55 €/mois | Gratuit | 0 € |
| Plugin API | ✅ CEP / UXP | ✅ PyKrita | ⚠️ Déclarée (`creative_plugin_api.h`, `fusion_api.h`) — pas encore publique |
| Multi-language scripting | ✅ JS/Python | ✅ Python | ⚠️ `scripting/bindings/` — non implémenté |
| Performance GPU | ✅ Metal/OpenCL | ✅ OpenGL/Vulkan | ⚠️ EGL/Wayland (`platform/egl/`) — non benchmarké |
| Maturité | 35 ans | 15 ans | **alpha 0.1** |

---

## 7. Évaluation honnête par domaine

### 7.1 Ce que Existence fait MIEUX que PS et Krita

1. **Intégration PKM** : ni Photoshop ni Krita n'ont de système de notes reliées + graphe. Cosmos à ce niveau-là (import Notion, éditeur par blocs, graphe GPU) dépasse même des outils dédiés comme Logseq en termes de graphe de performance.

2. **Architecture inter-applications** : l'IPC avec registre de ressources URI est plus propre que n'importe quelle tentative d'intégration PS↔Illustrator. Le principe "les apps restent autonomes mais parlent" est rare dans le domaine créatif.

3. **Natif Wayland Linux** : PS n'existe pas sur Linux. Krita tourne sous X11/XWayland. Existence est pensé pour Wayland dès la conception.

### 7.2 Ce que Existence fait à parité (pour une alpha)

- **Pathfinder booléen** : avec Clipper2, Atlas est maintenant correct sur Union/Intersection/Différence/XOR. Les outils vectoriels pro l'utilisent aussi (Affinity, etc. se basent sur des implémentations similaires).
- **Graphe Cosmos** : le graphe GPU 30K nœuds est meilleur que la quasi-totalité des outils PKM du marché.
- **Tablette XP-Pen** : intégration native visible dans les sources.

### 7.3 Les écarts critiques à combler (objectif)

**Court terme (bloquants pour un usage pro):**
- Contours vectoriels (pointillés, largeur variable) — absent du modèle Atlas.
- Dégradés complets (radial, arrêts multiples) — manque fonctionnel notable.
- Export SVG/PDF validé de bout en bout.
- API plugin publique fonctionnelle.

**Moyen terme :**
- Masques d'écrêtage vectoriels.
- Texte sur tracé.
- Moteur GPU pour Nebula (peinture haute performance).
- Plans de travail multiples dans Atlas.

**Long terme :**
- Maturité générale, stabilité, gestion d'erreurs production.
- Vectorisation d'image (Live Trace équivalent).
- Benchmark performance GPU Wayland.

---

## 8. Tableau de maturité global

| Composant | Maturité | Utilisable seul ? | Différenciant ? |
|---|---|---|---|
| **Existence** (hub) | Beta architecturale | ✅ Comme launcher | ✅✅ L'interopérabilité est unique |
| **Atlas** (vectoriel) | Alpha fonctionnelle | ⚠️ Oui, avec lacunes | ✅ Fondations solides |
| **Cosmos** (PKM) | La plus avancée | ✅✅ Oui | ✅✅ Meilleur que la concurrence sur le graphe |
| **Nebula** (raster) | Alpha | ⚠️ Non évalué ici | ⚠️ À confirmer |
| **Singularity** | Prototype | ⚠️ Outil spécialisé | ✅ Niche utile |
| **StarDust** | Embryonnaire | ❌ | À définir |

---

## 9. Conclusion

Existence est objectivement une alpha sérieuse, pas un projet jouet. L'architecture Existence est la pièce la plus remarquable : propre, non-monolithique, testée, avec de vraies primitives d'interopérabilité que des éditeurs commerciaux n'ont pas. Cosmos est déjà au niveau d'un outil PKM de niche compétitif. Atlas a résolu ses problèmes bloquants (Pathfinder avec Clipper2) et ses fondations C++ sont solides.

Les écarts avec PS et Krita sont réels mais attendus pour une alpha 0.1 : ils concernent la profondeur fonctionnelle (contours, dégradés, texte avancé) et la maturité, pas l'architecture de base. La direction est bonne. La valeur différenciatrice (intégration PKM + interopérabilité Linux-native + hub créatif cohérent) est réelle et inexistante chez la concurrence.

---

*Audit basé sur : `GALAXY_HUB_DOC.md`, `AUDIT_VECTORIEL_ATLAS.md`, `docs/ARCHITECTURE.md`, `Cosmos/README.md`, `StarDust/README.md`, analyse des structures de dossiers et fichiers sources clés.*
