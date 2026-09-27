# Existence — Documentation de référence

> Ce fichier explique l'architecture de `galaxy_hub.py` et montre comment modifier
> ou étendre l'application toi-même.

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Structure du fichier](#structure-du-fichier)
3. [Le dictionnaire de couleurs `C`](#le-dictionnaire-de-couleurs-c)
4. [Les catégories `CATEGORIES`](#les-catégories-categories)
5. [Les apps par défaut `DEFAULT_APPS`](#les-apps-par-défaut-default_apps)
6. [ConfigManager — persistance des données](#configmanager--persistance-des-données)
7. [WorkspaceSessionManager — session de travail](#workspacesessionmanager--session-de-travail)
8. [AppCard — les cartes d'application](#appcard--les-cartes-dapplication)
8. [AppDialog — formulaire ajouter/modifier](#appdialog--formulaire-ajoutermodifier)
9. [Sidebar — barre latérale](#sidebar--barre-latérale)
10. [ContentArea — grille principale](#contentarea--grille-principale)
11. [GalaxyHub — fenêtre principale](#galaxyhub--fenêtre-principale)
12. [main() — démarrage et contournement KDE](#main--démarrage-et-contournement-kde)
13. [Recettes pratiques](#recettes-pratiques)

---

## Vue d'ensemble

Existence est un **espace de travail principal PySide6** (Qt 6 en Python). Il ne
fait pas le travail à la place des univers : il leur fournit l'environnement dans
lequel ils existent, se lancent, s'organisent, partagent certaines ressources et
peuvent communiquer.

Formulation cible :

> Existence est l’environnement de travail créatif Linux qui réunit tes applications
> autonomes dans un même espace, gère leur cycle de vie, leurs ressources et leurs
> communications, sans les transformer en une seule grosse application.

Le catalogue est conservé dans `~/.config/existence/apps.json` (le catalogue Galaxy
Hub est migré automatiquement au premier lancement).

La session de travail courante est conservée séparément dans
`~/.config/existence/workspaces.json`. Elle ne remplace pas le catalogue : elle
enregistre le contexte de travail de l'utilisateur.

Principe central :

```
Existence ne devient pas un monolithe.
Chaque univers reste autonome.
Existence fournit l'environnement commun.
```

Architecture visée :

```
                         EXISTENCE
                    ┌─────────────────┐
                    │ espace de travail│
                    │      principal   │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
       NEBULA              ATLAS              COSMOS
       raster             vectoriel          organisation
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                    communication
                    inter-applications
```

Dans cette architecture :

- **Existence** est l'environnement central.
- **Univers** désigne Nebula, Atlas, Cosmos, Singularity et les futurs mondes.
- **Modules orbitaux** désigne les extensions, outils ou services attachés à un
  univers ou à une couche commune.
- **Services communs** couvrent fichiers, installation, mises à jour, ressources,
  paramètres et communication entre modules.
- **Wormholes** désigne les passages entre univers autonomes.
- **Gravité** décrit les relations entre modules : dépendances, proximité,
  appartenance et services partagés.
- **Launcher** lance un univers ou un outil sans l'absorber.
- **Centralisation** signifie qu'Existence connaît les ressources et données communes
  sans forcément tout posséder lui-même.

Les trois niveaux à préserver sont :

```text
Existence = l'environnement
Univers = les applications principales
Modules = les extensions/services qui gravitent autour d'elles
```

L'interface sépare aussi deux façons de regarder la carte :

- **Cartographie** filtre par domaine d'usage : création, productivité,
  développement, utilitaires, autres.
- **Structure** filtre par nature d'astre : univers, modules, services,
  infrastructure.

Le but est que la carte ressemble à un environnement vivant. Les univers principaux
doivent rester dominants visuellement ; l'infrastructure et les services communs
doivent être accessibles, mais secondaires.

Les astres de la carte peuvent être déplacés directement par glisser-déposer. La
position est enregistrée dans `map_position` sous forme normalisée (`x`, `y`) afin
de rester valable quand la fenêtre change de taille. L'auto-layout sert donc de
position de départ, puis l'utilisateur peut organiser son propre espace.

La sauvegarde du catalogue utilise une écriture atomique : Existence écrit d'abord
un fichier temporaire, force l'écriture sur disque, puis remplace `apps.json`. Cela
évite de laisser un état partiellement écrit si l'application est interrompue.

La communication inter-applications est le morceau qui transforme Existence en
véritable environnement. Exemples visés :

- Atlas peut envoyer une illustration vectorielle vers Nebula pour la peinture raster.
- Nebula peut renvoyer une ressource vers Atlas.
- Cosmos peut référencer les documents et projets des autres univers.
- Singularity peut traiter une image produite par Nebula.
- Existence garde le contexte commun, les fichiers, les modules, les services et
  les relations orbitales.

Univers prêts pour l'intégration :

| Univers | Rôle | Lancement |
| --- | --- | --- |
| Atlas | vectoriel | `/home/deanos/Documents/Atlas/build_atlas/CreativeSystemAtlasGtk` |
| Nebula | raster | `python main.py` depuis `/home/deanos/Documents/Nebula` |
| Cosmos | connaissance / organisation | `/home/deanos/Documents/Cosmos/start-desktop.sh` |
| Singularity | traitement d'image | `python webready.py` depuis `/home/deanos/Documents/Singularity` |

Routes principales déclarées :

```text
Atlas export_vector      -> Nebula open_as_raster
Nebula send_resource     -> Singularity process_resource
Nebula send_resource     -> Cosmos reference_project
Cosmos reference_project -> Atlas send_resource
Singularity send_resource -> Nebula send_resource
```

La carte prépare maintenant le terrain pour les futurs “modules gravitationnels” :
un outil peut être rattaché à un univers avec `orbit_of`, et chaque astre peut être
typé avec `app_kind` (`environment`, `universe`, `orbital_module`, `service`,
`template`). Le catalogue reste limité à l'écosystème créé pour Existence, identifié
par `ecosystem_id`.

`Vérificateur d'app` est une sous-couche de `Installateur D'app` : son rôle n'est
pas de devenir un grand module séparé, mais de répondre simplement si une app de
l'écosystème est installée ou non. L'installateur utilise ensuite cette réponse
pour savoir s'il doit préparer ou lancer une installation.

## Contrat Existence

### Modules fournis par Existence

`Fusion Creator` et `Resources` sont des capacités d'Existence, pas des
fonctionnalités appartenant à Nebula. Le registre partagé est défini dans
`modules/registry.py` et expose pour chaque module un manifeste avec son identité,
ses types de ressources, ses messages et ses modes de présentation (`dock`,
`panel`, `floating`, `tab`, `contextual`, `workspace`).

Nebula conserve des adaptateurs minces dans `existence/module_adapter.py`. Ils
présentent encore les docks Qt existants pour préserver les workspaces et les
connexions actuelles, mais leur identité et leur protocole viennent d'Existence.
Si Existence n'est pas disponible, l'adaptateur utilise un manifeste local de
secours et Nebula reste lançable seul.

Les univers déclarent leur compatibilité via `accepts` : `fusion`,
`blend_result`, `blend_definition` pour Fusion Creator, et `resource`,
`resource_bundle`, `blend_definition`, `blend_result` pour Resources. Les
ressources ne sont donc plus implicitement liées au dock d'un univers.

Le catalogue Resources est organisé par catégories extensibles : documents,
images, projets, brushes, brush engines, blends, filters, effects, masks,
generators, fonts, profils ICC, libraries et modules, auxquels s'ajoutent les
catégories historiques de Nebula (textures, patterns, gradients, palettes,
styles et reference sets). Une liaison Existence explicite peut rattacher une
catégorie à un consommateur (`read`, `write`, `read_write` ou `reference`) ;
elle peut être retirée sans supprimer la ressource.

## WorkspaceSessionManager — session de travail

`WorkspaceSessionManager` est la couche entre Existence et les processus des
univers. Elle possède le contexte du travail, pas les applications elles-mêmes :

```text
Workspace Existence
├── current_project
├── active_universes
│   └── universe_id, pid, state, resources, window
├── open_resources
├── active_workflow
└── ui.windows
```

Le clic sur un univers passe par cette session. Si son processus est déjà actif,
Existence réactive la session et n'en crée pas une seconde. À l'ouverture d'un
nouveau processus, son PID et son contexte sont enregistrés ; à sa fermeture, la
session est marquée `closed`.

Au démarrage, `required_universe_ids()` calcule l'ensemble minimal à restaurer :
les sessions marquées `desired`, plus les propriétaires des ressources ouvertes
ou associées. Les univers installés mais absents de cet ensemble restent fermés.
`restore_on_start` permet de désactiver cette restauration pour le workspace
courant.

## Project et Workplace

Ces deux concepts sont volontairement séparés :

```text
Existence
├── ProjectManager
│   ├── ressources du projet
│   ├── état métier
│   └── ressources par univers
└── WorkspaceSessionManager
    ├── univers vivants
    ├── processus et IPC
    └── vue courante
```

`ProjectManager` persiste les projets dans `~/.config/existence/projects.json`.
Changer de projet ne ferme aucun univers. Changer d'univers ne change pas le
projet : cela sélectionne uniquement une autre vue dans la Workplace.

Le `ProjectManager` possède aussi un mode `standalone` (« hors projet »). Dans
ce mode, cliquer sur un univers lance son application externe classique, même si
elle possède un provider embarqué. Le mode `project` active au contraire les vues
embarquées Wayland. Passer hors projet ferme les vues embarquées du projet sans
fermer Existence ; les sessions externes peuvent continuer à vivre.

Le bouton **Projet / Hors projet** ouvre la fenêtre de gestion de projet
Existence. Elle permet de voir les projets, leurs nombres de ressources et
d'univers, de créer un projet, d'en ouvrir un autre ou de repasser en mode hors
projet. Le bouton **Espace actuel** n'est plus utilisé : la vue centrale est
directement la Workplace courante.

## Navigation Workplace

Quand un univers est sélectionné, Existence passe en mode compact : la sidebar,
la recherche et les contrôles de catalogue disparaissent pour laisser la place à
la vue centrale. Les processus et sessions ne sont pas arrêtés.

- **Univers** ouvre un menu pour passer à Atlas, Nebula, Cosmos ou Singularity ;
- **Accueil** revient à la carte racine Existence ;
- les univers déjà actifs sont marqués d'un point et sont simplement réactivés ;
- le retour à l'accueil ne ferme aucun processus.

## IPC réel et hébergement des fenêtres

`existence_ipc.py` fournit le transport de processus `existence.ipc.v1` : chaque
univers expose un endpoint JSON-lines indépendant, et `ExistenceIPCRouter` envoie
les messages au processus cible après le handshake. Les univers ne se parlent pas
directement. Le scénario Atlas → Nebula utilise maintenant ce routeur réel et
enregistre `transport: process-json-lines` dans l'événement de routage.

`WindowHost` définit maintenant deux modes. Le mode recommandé sous Wayland est
`embedding_mode: embeddable_view` : l'univers fournit une vue compatible au
workspace via `mount_embeddable_view()`. Cette vue est intégrée dans le même
processus d'interface, sans reparentage de fenêtre étrangère. Le mode
`embedding_mode: external` conserve le processus autonome et son IPC.

Le reparentage `QWindow.fromWinId` / `createWindowContainer` est uniquement une
compatibilité X11 opt-in (`EXISTENCE_ENABLE_X11_EMBEDDING=1`) ; il est désactivé
par défaut. Sous Wayland, `xdotool` ne peut pas héberger une fenêtre : il ne peut
au mieux qu'agir sur une fenêtre X11 via XWayland. Dans la session Garuda Wayland,
la prochaine intégration doit donc fournir une vue native embarquable pour Atlas,
Nebula et Cosmos, ou conserver leur fenêtre autonome médiée par Existence.

`UniverseViewRegistry` est le point d'extension pour ces vues. Un univers peut
enregistrer un provider qui reçoit le parent de la Workplace et retourne son
widget. Ce provider doit être créé dans le processus d'interface Existence (ou
dans un plugin compatible) : une fenêtre Wayland appartenant à un autre processus
ne peut pas être convertie en widget enfant.

Nebula fournit maintenant le premier provider concret via
`embedded_views.create_nebula_view()`. Il charge son interface PySide6 comme vue
dans Existence sous Wayland, sans lancer une seconde fenêtre. Cosmos fournit une vue
`QWebEngineView` directement construite par
`embedded_views.create_cosmos_view()` ; son bridge natif persistant reste à
reconnecter au `QWebChannel` de la Workplace. Atlas fournit une vue Qt native
`AtlasEmbeddedView` pilotée par son endpoint Existence compilé : le backend Atlas
reste indépendant et la vue ne lance plus la fenêtre GTK historique. Le portage
complet de l'éditeur GTK vers cette vue Qt reste une évolution UI distincte ; la
surface Wayland unique et le moteur vectoriel médié sont déjà en place.

Le prochain jalon architectural est le contrat `Universe / Module / Service /
Capability`. Il stabilise la mécanique avant de construire l'installateur complet
ou la communication réelle.

Un astre Existence doit pouvoir exposer :

```text
Universe ou Module ou Service
├── identity       id, name, version, app_kind, ecosystem_id
├── lifecycle      lifecycle_state, installed, exec_path
├── resources      resource_namespace, resource_types
├── communication  capabilities, accepted_messages, emitted_messages
├── relations      orbit_of, orbit_relation
└── compatibility  existence_min_version, dependencies, permissions
```

Cycle de vie prévu :

```text
not_installed
installed
available
loaded
active
closed
uninstalled
error
```

Types de ressources de départ :

```text
file, image, document, selection, project, event
```

Types de messages de départ :

```text
export_vector, open_as_raster, send_resource, reference_project, process_resource
```

Identité des ressources :

```text
resource://existence/nebula/...
resource://existence/atlas/...
resource://existence/cosmos/...
```

Cette forme évite de réduire une ressource à un simple chemin comme
`/home/.../image.png`. Le chemin peut exister derrière, mais l'environnement parle
d'abord en identité de ressource.

Relations d'orbite :

```text
visual           relation purement visuelle
available_from   module disponible depuis un univers
depends_on       dépendance fonctionnelle
uses_capability  module utilisant une capacité d'un univers
shared_service   service commun partagé par plusieurs astres
```

`orbit_of` indique autour de quoi un astre gravite. `orbit_relation` indique ce que
cette gravité signifie. Les deux doivent rester séparés pour éviter que “orbite”
veuille dire cinq choses différentes.

## Transport de Messages

Le premier prototype de communication est `MessageExecutor`. Il ne lance pas encore
de vraie action dans Nebula ou Atlas, mais il exécute déjà le contrat minimal :

```python
MessageExecutor(apps).send_message(
    source="atlas",
    target="nebula",
    message="export_vector",
    resource="resource://existence/atlas",
    payload={"intent": "open_as_raster"},
)
```

Flux conceptuel :

```text
Atlas
  │ export_vector
  ▼
Existence
  │ open_as_raster
  ▼
Nebula
```

Le transport vérifie :

- la source et la cible existent dans l'écosystème ;
- la source émet bien le message demandé ;
- la route transforme le message si nécessaire (`export_vector` vers `open_as_raster`) ;
- la cible accepte le message final ;
- la ressource `resource://...` existe dans le registre ;
- les permissions bloquantes sont respectées ;
- un événement est écrit dans `~/.config/existence/events.json`.

Les événements actuellement produits incluent :

```text
message.executed
message.failed
universe.started
universe.closed
universe.failed
```

Lorsqu'un univers est lancé depuis Existence, son processus est suivi. Le cycle de
vie passe à `active`, puis revient à `closed` quand le processus se termine. Si le
lancement échoue, l'état devient `error`.

Pour l'instant, le registre de ressources est minimal : chaque astre expose son
`resource_namespace` comme ressource existante. Plus tard, ce registre pourra pointer
vers des fichiers, documents, sélections, projets ou événements réels.

## Registre de Ressources

`ResourceRegistry` persiste les ressources dans `~/.config/existence/resources.json`.
Il donne une réalité minimale aux URI `resource://...`.

Structure d'une ressource :

```json
{
  "uri": "resource://existence/atlas/image/vector-42",
  "owner": "atlas",
  "type": "image",
  "version": 1,
  "physical_path": "/chemin/optionnel/vector-42.svg",
  "created_at": 0,
  "updated_at": 0,
  "lifecycle": "active",
  "access": {
    "read": ["atlas", "nebula"],
    "write": ["atlas"],
    "reference": ["*"]
  },
  "metadata": {
    "name": "vector-42"
  }
}
```

Le registre sait actuellement :

- créer une ressource ;
- créer automatiquement un namespace pour chaque astre ;
- résoudre une ressource par URI ;
- vérifier un accès simple (`read`, `write`, `reference`) ;
- marquer une ressource comme supprimée ;
- produire `resource.created` et `resource.deleted`.

Le transport de messages utilise maintenant ce registre : une cible ne reçoit une
ressource que si l'URI existe et si elle a le droit de la lire.

## Tests du Noyau

`test_existence_core.py` couvre les premiers scénarios critiques du noyau :

- Atlas → Nebula accepté avec ressource existante et permission `read` ;
- refus si la ressource n'existe pas ;
- refus si la cible n'accepte pas le message routé ;
- refus si la cible n'a pas accès à la ressource ;
- refus si un univers est fermé ;
- versionnement d'une ressource modifiée.

Ces tests servent de garde-fou avant de construire l'installation de modules,
les vrais wormholes visuels ou l'intégration plus profonde du workspace.

```
galaxy_hub.py
│
├── Constantes : APP_VERSION, CONFIG_DIR, CONFIG_FILE, C{}, CATEGORIES, DEFAULT_APPS
├── ConfigManager          — lit/écrit apps.json
├── verify_app_readiness   — indique si une app est installée ou à installer
├── StarField              — fond étoilé animé
├── AppIconWidget          — widget icône emoji avec fond coloré
├── AppCard                — carte d'une application
├── AppDialog              — dialogue ajouter / modifier
├── Sidebar                — barre latérale (catégories + bouton +)
├── ContentArea            — barre de recherche + grille scrollable
├── GalaxyHub              — QMainWindow principale
└── main()                 — point d'entrée
```

---

## Structure du fichier

Le fichier fait environ 1 100 lignes. Chaque classe est introduite par une bannière :

```python
# ══════════════════════════════════════════════════════════════
#  NOM DE LA CLASSE
# ══════════════════════════════════════════════════════════════
```

Utilise la recherche de ton éditeur sur `══` pour sauter d'une section à l'autre.

---

## Le dictionnaire de couleurs `C`

```python
C = {
    "bg":       "#07051a",   # fond le plus sombre (fenêtre principale)
    "bg2":      "#0d0b25",   # fond légèrement plus clair (sidebar, header)
    "surface":  "#12103a",   # fond des cartes et champs de saisie
    "surface_h":"#181550",   # surface au survol
    "border":   "#2a2560",   # bordure normale
    "border_h": "#3d37a0",   # bordure au survol
    "text":     "#e2e0ff",   # texte principal
    "text2":    "#9d98d4",   # texte secondaire
    "text3":    "#5a5490",   # texte tertiaire (labels, version)
    "purple":   "#7C3AED",   # couleur d'accentuation principale
    "purple_l": "#A78BFA",   # purple éclairci (textes, hover)
    "red":      "#EF4444",   # bouton fermer, erreur
}
```

**Changer le thème** : modifie les valeurs dans `C`. Toutes les couleurs de l'interface
en découlent — tu n'as pas besoin de toucher à autre chose.

> ⚠️ Evite les couleurs avec transparence (ex. `#7C3AED22`) dans les états hover/active :
> KDE/Kvantum injecte sa couleur verte à travers l'alpha. Utilise des couleurs opaques.

---

## Les catégories `CATEGORIES`

```python
CATEGORIES = ["Toutes", "Création", "Productivité", "Développement", "Utilitaires", "Autres"]
```

**Ajouter une catégorie** : insère simplement le nom dans cette liste.
La sidebar et le formulaire la reprendront automatiquement.

---

## Les apps par défaut `DEFAULT_APPS`

Structure d'une entrée :

```python
{
    "id":           "atlas",           # identifiant unique (slug)
    "name":         "Atlas",           # nom affiché sur la carte
    "description":  "…",              # description courte
    "category":     "Création",        # doit correspondre à une valeur de CATEGORIES
    "icon_emoji":   "🎨",             # emoji affiché dans l'icône
    "icon_path":    "",                # chemin vers une image (optionnel, laisse vide)
    "accent_color": "#f90004",         # couleur d'accentuation de la carte (hex)
    "version":      "0.1.0",           # numéro de version affiché
    "installed":    True,              # False = bouton "Configurer" au lieu de "Lancer"
    "exec_path":    "/chemin/vers/launch.sh",  # script ou exécutable à lancer
    "exec_args":    [],                # arguments supplémentaires passés à exec_path
    "install_type": "manual",          # info indicative (manual / git / …)
    "install_script": "",              # script d'installation (non utilisé pour l'instant)
    "git_url":      "",                # URL git de l'app (affiché dans le formulaire)
    "tags":         ["tag1", "tag2"],  # utilisés par la recherche
    "orbit_of":      "",               # id de l'univers parent si c'est un outil orbital
    "system_role":   "",               # réservé aux modules système d'Existence
    "ecosystem_id":  "existence",      # limite le catalogue à ton écosystème
    "app_kind":      "universe",       # environment / universe / orbital_module / service / template
    "capabilities":  ["send_resource"],# capacités futures de communication ou de service
    "map_position":  {"x": 0.5, "y": 0.5}, # position manuelle optionnelle sur la carte
}
```

`DEFAULT_APPS` initialise le catalogue. Si `apps.json` existe déjà, Existence ajoute
quand même les nouveaux astres système manquants sans remplacer tes apps personnelles.

---

## ConfigManager — persistance des données

```python
class ConfigManager:
    def load() -> list[dict]    # lit apps.json ; renvoie DEFAULT_APPS si absent
    def save(apps: list[dict])  # écrit apps.json (crée le dossier si besoin)
```

Le fichier de config est `~/.config/galaxy-hub/apps.json`.

**Pour lire un champ custom** que tu aurais ajouté (ex: "author") :

```python
app_data.get("author", "Inconnu")
```

**Pour ajouter un champ** et le conserver :

1. Ajoute-le dans `AppDialog._save()` : `"author": self.author_e.text().strip()`
2. La prochaine fois que l'utilisateur clique sur "Enregistrer", il sera sauvegardé.

---

## AppCard — les cartes d'application

### Taille

```python
CARD_W = 260   # largeur en pixels — modifiable
CARD_H = 200   # hauteur minimale — la carte grandit si le titre est long
```

### Signaux

| Signal | Émis quand |
|--------|-----------|
| `launch_requested(dict)` | clic sur "Lancer" |
| `edit_requested(dict)` | clic sur "Modifier" dans le menu ⋯ |
| `remove_requested(str)` | clic sur "Supprimer" (passe l'id) |
| `install_requested(dict)` | clic sur "Configurer" |

### Méthodes clés

- `_build_ui()` — construit l'interface (icône, nom, description, bouton)
- `_update_action_btn()` — "Lancer" ou "Configurer" selon `app_data["installed"]`
- `_update_frame_style()` — bordure normale vs survol + bande colorée en haut
- `update_data(new_data)` — met à jour la carte sans la recréer
- `enterEvent / leaveEvent` — halo lumineux au survol

### Modifier l'apparence d'une carte

Exemple : rendre le fond des cartes légèrement bleuté au lieu de `surface` :

```python
# dans _update_frame_style()
self.setStyleSheet(f"""
    QFrame#AppCard{{
        background:#0e0c32;   ← change ici
        border:1px solid {border};
        border-radius:16px;
        border-top:2px solid {accent};
    }}
""")
```

---

## AppDialog — formulaire ajouter/modifier

Dialogue modal (sans cadre système) qui collecte les infos d'une app.

```python
dlg = AppDialog()               # nouveau
dlg = AppDialog(app_data=dict)  # modification
if dlg.exec() == QDialog.DialogCode.Accepted:
    data = dlg.result_data      # dict avec tous les champs
```

### Ajouter un champ au formulaire

1. Dans `_build_ui()`, après les champs existants :

```python
self.author_e = QLineEdit((self.app_data or {}).get("author", ""))
self.author_e.setPlaceholderText("Ton nom")
form.addRow(lbl("Auteur"), self.author_e)
```

2. Dans `_save()`, ajoute la clé dans le dict :

```python
"author": self.author_e.text().strip(),
```

3. Dans `AppCard._build_ui()`, affiche-le si tu veux :

```python
author_lbl = QLabel(self.app_data.get("author", ""))
author_lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;")
meta_col.addWidget(author_lbl)
```

---

## Sidebar — barre latérale

```python
class Sidebar(QWidget):
    category_changed  = Signal(str)   # quand l'utilisateur clique une catégorie
    add_app_requested = Signal()      # quand il clique sur "+ Ajouter"
```

- Largeur fixe : `self.setFixedWidth(222)` — change ce nombre pour élargir/rétrécir.
- Les boutons de catégorie sont générés par une boucle sur `CATEGORIES` :
  ajouter une catégorie dans `CATEGORIES` suffit, pas besoin de toucher à `Sidebar`.
- `_btn_css(active)` retourne le QSS du bouton selon son état.
  Toutes les propriétés CSS sont explicites (sans abréviation) pour empêcher
  KDE/Kvantum d'injecter du vert.

---

## ContentArea — grille principale

```python
self.title_lbl   # QLabel — titre de la catégorie active
self.search_edit # QLineEdit — champ de recherche
self.grid        # QGridLayout — reçoit les AppCard
self.scroll      # QScrollArea — enveloppe la grille
```

Pour changer l'espacement entre les cartes :

```python
self.grid.setSpacing(16)   ← change ce nombre
```

Pour changer les marges autour de la grille :

```python
self.grid.setContentsMargins(24, 24, 24, 24)   ← (gauche, haut, droite, bas)
```

---

## GalaxyHub — fenêtre principale

C'est ici que tout est connecté.

### Flux de données

```
apps.json
    └─ ConfigManager.load() → self.apps (list[dict])
            └─ _refresh() → crée une AppCard par app filtrée
                    └─ AppCard Signals → _launch / _edit_app / _remove
                            └─ ConfigManager.save() → apps.json
```

### Ajouter un bouton global (ex: "Paramètres")

1. **Dans Sidebar** : ajoute un signal et un bouton

```python
settings_requested = Signal()

# dans _build_ui(), après le bouton "Ajouter" :
settings_btn = QPushButton("⚙  Paramètres")
settings_btn.clicked.connect(self.settings_requested.emit)
lay.addWidget(settings_btn)
```

2. **Dans GalaxyHub._build_ui()** : connecte le signal

```python
self.sidebar.settings_requested.connect(self._open_settings)
```

3. **Implémente la méthode** :

```python
def _open_settings(self):
    # ton code ici
    pass
```

### _refresh()

Vide la grille et la reconstruit selon `self._cat` et `self._query`.
Le nombre de colonnes est calculé automatiquement selon la largeur de la fenêtre.
Le placeholder "+ Nouvelle application" est ajouté en dernier si la recherche est vide.

### _launch()

Lance l'app avec `subprocess.Popen([exec_path, ...], start_new_session=True)`.
`start_new_session=True` détache le processus : fermer Existence ne tue pas l'app.

---

## main() — démarrage et contournement KDE

```python
def main():
    os.environ["QT_QPA_PLATFORMTHEME"] = ""   # désactive le thème KDE
    os.environ.pop("QT_STYLE_OVERRIDE", None)

    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))  # style neutre
    app.setStyleSheet("")                          # efface les QSS de la plateforme
    ...
    app.setPalette(pal)   # palette sombre — Fusion la respecte
```

**Pourquoi tout ça ?** Sur Garuda Linux / KDE Plasma avec Kvantum, le thème système
injecte sa couleur d'accentuation verte même quand tu fournis un QSS explicite.
La combinaison ci-dessus contourne ce comportement en forçant le moteur de rendu
à utiliser Fusion (style Qt natif multiplateforme) avec la palette définie ici.

---

## Recettes pratiques

### Changer la taille des cartes

```python
# class AppCard
CARD_W = 300   # plus large
CARD_H = 220   # plus haute (minimum)
```

### Changer la police de l'application

```python
# dans GalaxyHub._build_ui() ou main(), avant win.show() :
font = QFont("Fira Code", 11)
app.setFont(font)
```

### Ajouter une nouvelle app manuellement dans apps.json

Ouvre `~/.config/galaxy-hub/apps.json` et ajoute un objet à la liste
en suivant la structure expliquée dans [DEFAULT_APPS](#les-apps-par-défaut-default_apps).
Relance Existence — la carte apparaît immédiatement.

### Modifier le fond étoilé

La classe `StarField` gère l'animation des étoiles.
- Pour changer le nombre d'étoiles : modifie `count` dans `__init__`.
- Pour désactiver le fond étoilé : retire `self.stars = StarField(central)` et
  `self.stars.lower()` dans `GalaxyHub._build_ui()`.

### Désactiver la recherche

Retire `self.search_edit` de `ContentArea._build_ui()` et la connexion
`self.content.search_edit.textChanged.connect(self._on_search)` dans `GalaxyHub._build_ui()`.

---

*Dernière mise à jour : 2026-09-21*
