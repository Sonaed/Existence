# Distribution d'Existence — paquets .deb et AUR

Tout se fait depuis ce dossier, sur ta machine (les sources sont lues dans `~/Documents/<App>`).

## Construire

```bash
cd ~/Documents/Existence
python packaging/build_packages.py                  # toutes les apps, .deb + Arch
python packaging/build_packages.py --only nebula    # une seule
python packaging/build_packages.py --format arch    # seulement Arch
```

Pour les apps en C++ (Nebula, StarDust, Atlas, Cosmos), la compilation a lieu pendant la construction du paquet :
il faut `cmake`, un compilateur et les en-têtes (`qt6-base`, `gtk4`, `qt6-webengine` selon l'app).

Résultat dans `packaging/dist/` :

| Dossier | Contenu | Usage |
|---|---|---|
| `deb/` | `existence-<app>_26.0-1_<arch>.deb`, `existence-suite`, `Packages.gz` | Debian / Ubuntu |
| `arch/<paquet>/` | `PKGBUILD` + archive des sources | `makepkg -si` en local |
| `aur/<paquet>/` | `PKGBUILD` qui télécharge depuis GitHub | à publier sur l'AUR |

## Installer

**Arch (local)** :
```bash
cd packaging/dist/arch/existence-nebula && makepkg -si
cd ../existence-suite && makepkg -si        # tout d'un coup (après les autres)
```
`python-rawpy` (RAW dans Nova) et `python-psd-tools` (PSD dans Nebula) sont dans l'AUR : `yay -S python-rawpy python-psd-tools`.

**Debian / Ubuntu** (Debian 13+ ou Ubuntu 24.10+, qui fournissent PySide6) :
```bash
sudo apt install ./packaging/dist/deb/existence-*.deb
```

Chaque app s'installe dans `/usr/share/existence/<app>`, avec la commande `existence-<app>`, une entrée de menu
et une icône. Tes réglages, ressources et liens restent dans ton dossier personnel.
Existence repère tout seul les apps installées par paquet et le catalogue affiche « mises à jour via pacman / apt ».

## Publier et mettre à jour

1. **Code** : pousse chaque app sur GitHub (`<compte>/Existence`, `/Nebula`, `/Nova`…) et crée le tag `v26.0`.
2. **AUR** : `python packaging/build_packages.py --format arch --github <compte>` puis `./packaging/publish_aur.sh`.
   Les gens installent avec `yay -S existence-suite` et reçoivent les mises à jour avec `yay -Syu`.
3. **APT** : publie le dossier `dist/deb/` tel quel (GitHub Pages, par exemple), puis côté utilisateur :
   ```
   echo "deb [trusted=yes] https://<compte>.github.io/existence-apt ./" | sudo tee /etc/apt/sources.list.d/existence.list
   sudo apt update && sudo apt install existence-suite
   ```
   `[trusted=yes]` saute la signature ; pour signer le dépôt plus tard : `apt-ftparchive` + `gpg --clearsign`.

**Nouvelle version** : change `VERSION` (ex. `26.1`) dans `build_packages.py`, tague `v26.1`, reconstruis, republie.
