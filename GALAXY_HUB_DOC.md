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
7. [AppCard — les cartes d'application](#appcard--les-cartes-dapplication)
8. [AppDialog — formulaire ajouter/modifier](#appdialog--formulaire-ajoutermodifier)
9. [Sidebar — barre latérale](#sidebar--barre-latérale)
10. [ContentArea — grille principale](#contentarea--grille-principale)
11. [GalaxyHub — fenêtre principale](#galaxyhub--fenêtre-principale)
12. [main() — démarrage et contournement KDE](#main--démarrage-et-contournement-kde)
13. [Recettes pratiques](#recettes-pratiques)

---

## Vue d'ensemble

Existence est un **hub créatif PySide6** (Qt 6 en Python). Il cartographie les
applications majeures comme des univers et leurs utilitaires comme des astres en
orbite. Le catalogue est conservé dans `~/.config/existence/apps.json` (le catalogue
Galaxy Hub est migré automatiquement au premier lancement).

```
galaxy_hub.py
│
├── Constantes : APP_VERSION, CONFIG_DIR, CONFIG_FILE, C{}, CATEGORIES, DEFAULT_APPS
├── ConfigManager          — lit/écrit apps.json
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
}
```

`DEFAULT_APPS` est chargé **seulement** si `apps.json` n'existe pas encore.
Une fois l'app lancée une première fois, c'est `apps.json` qui fait foi.

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
`start_new_session=True` détache le processus : fermer Galaxy Hub ne tue pas l'app.

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
Relance Galaxy Hub — la carte apparaît immédiatement.

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
