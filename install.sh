#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════
#  Galaxy Hub — Script d'installation (ArchLinux / Garuda)
# ══════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="galaxy-hub"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     Galaxy Hub — Installation           ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Dépendances
echo "› Vérification de python-pyside6…"
if ! python -c "import PySide6" 2>/dev/null; then
    echo "  PySide6 non trouvé — installation via pacman…"
    if command -v pacman &>/dev/null; then
        sudo pacman -S --needed python-pyside6
    elif command -v pip &>/dev/null; then
        pip install --user PySide6
    else
        echo "  ERREUR : installe python-pyside6 manuellement puis relance ce script."
        exit 1
    fi
else
    echo "  ✓ PySide6 déjà installé"
fi

# ── 2. Dépendances WebReady
echo "› Vérification de Pillow…"
if ! python -c "import PIL" 2>/dev/null; then
    echo "  Pillow non trouvé — installation…"
    if command -v pacman &>/dev/null; then
        sudo pacman -S --needed python-pillow
    elif command -v pip &>/dev/null; then
        pip install --user Pillow
    else
        echo "  ERREUR : installe python-pillow manuellement puis relance ce script."
        exit 1
    fi
else
    echo "  ✓ Pillow déjà installé"
fi

# ── 3. Copie des fichiers
echo "› Copie dans $INSTALL_DIR …"
mkdir -p "$INSTALL_DIR"
cp -f "$SCRIPT_DIR/galaxy_hub.py" "$INSTALL_DIR/"

# WebReady — cherche dans ../Singularity par rapport à ce script
SINGULARITY_DIR="$(cd "$SCRIPT_DIR/../Singularity" 2>/dev/null && pwd)" || true
if [[ -d "$SINGULARITY_DIR" ]]; then
    cp -f "$SINGULARITY_DIR/webready.py" "$INSTALL_DIR/"
    # Génère un lanceur avec chemin absolu (évite les erreurs de CWD)
    cat > "$INSTALL_DIR/webready_launch.sh" <<WEOF
#!/usr/bin/env bash
exec python "$INSTALL_DIR/webready.py"
WEOF
    chmod +x "$INSTALL_DIR/webready_launch.sh"
    echo "  ✓ WebReady copié"
else
    echo "  ⚠  Dossier Singularity introuvable — WebReady non copié."
    echo "     Attendu : $SCRIPT_DIR/../Singularity"
fi

# ── 3. Wrapper exécutable
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/$APP_NAME" <<EOF
#!/usr/bin/env bash
exec python "$INSTALL_DIR/galaxy_hub.py" "\$@"
EOF
chmod +x "$BIN_DIR/$APP_NAME"
echo "  ✓ Lanceur créé : $BIN_DIR/$APP_NAME"

# ── 4. Fichier .desktop
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Galaxy Hub
GenericName=Creative Suite Launcher
Comment=Lanceur d'applications — Atlas, Cosmos et tes créations
Exec=$BIN_DIR/$APP_NAME
Icon=system-software-install
Categories=Utility;
Terminal=false
StartupWMClass=galaxy_hub
Keywords=launcher;hub;atlas;cosmos;créatif;
EOF
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
echo "  ✓ Entrée .desktop créée"

# ── 6. Injection de WebReady dans la config Galaxy existante
CONFIG_FILE="$HOME/.config/galaxy-hub/apps.json"
WEBREADY_EXEC="$INSTALL_DIR/webready_launch.sh"

if [[ -f "$CONFIG_FILE" ]] && command -v python &>/dev/null; then
    python - <<PYEOF
import json, sys
from pathlib import Path

config_path = Path("$CONFIG_FILE")
exec_path   = "$WEBREADY_EXEC"

with open(config_path, encoding="utf-8") as f:
    apps = json.load(f)

webready_entry = {
    "id":           "webready",
    "name":         "WebReady",
    "description":  "Optimise tes images pour le web — conversion WebP, max 2560×1440, 72 DPI",
    "category":     "Utilitaires",
    "icon_emoji":   "🖼️",
    "icon_path":    "",
    "accent_color": "#06B6D4",
    "version":      "2.0.0",
    "installed":    True,
    "exec_path":    exec_path,
    "exec_args":    [],
    "install_type": "manual",
    "install_script": "",
    "git_url":      "",
    "tags":         ["images", "webp", "optimisation", "web"],
}

# Remplace si déjà présent, sinon ajoute
idx = next((i for i, a in enumerate(apps) if a.get("id") == "webready"), None)
if idx is not None:
    apps[idx] = webready_entry
    print("  ✓ WebReady mis à jour dans apps.json")
else:
    apps.append(webready_entry)
    print("  ✓ WebReady injecté dans apps.json")

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(apps, f, indent=2, ensure_ascii=False)

print("  ✓ WebReady injecté dans apps.json")
PYEOF
fi

# ── 7. PATH check
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "  ⚠  $BIN_DIR n'est pas dans ton PATH."
    echo "     Ajoute cette ligne à ~/.bashrc ou ~/.zshrc :"
    echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "  ✦ Galaxy Hub installé avec succès !"
echo "  › Lancement : $APP_NAME"
echo "     ou depuis ton lanceur d'applications (⚙ redémarre-le si absent)"
echo ""
