# Versions de l'écosystème Existence

Schéma : **`<année sur 2 chiffres>.<release>`**, affiché « Nom Version ».

| Exemple | Signification |
|---|---|
| Nebula 26.0 | 1re release de 2026 |
| Nebula 26.1 | release suivante en 2026 |
| Nebula 27.0 | 1re release de 2027 |

Où changer la version :
- Existence : `APP_VERSION` dans `galaxy_hub.py` (+ `DEFAULT_APPS`)
- Modules Existence : `modules/<id>/manifest.py`
- Nebula : `CORE/version.py` et `EXISTENCE/manifest.json`
- StarDust : `STARDUST_VERSION` dans `main.py` et `existence-manifest.json`
- Atlas : `engine/existence/atlas_existence.h` (+ `project(... VERSION)` du CMake) — recompiler
- Cosmos, Singularity, Nova : `existence-manifest.json`

Le manifest d'une app fait foi : Existence le relit à chaque démarrage.
Les anciennes versions (0.x, 1.x, 2.x) du catalogue sont migrées automatiquement.
