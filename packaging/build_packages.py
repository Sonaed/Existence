#!/usr/bin/env python3
"""Construit les paquets de l'écosystème Existence : .deb (Debian/Ubuntu) et Arch (AUR).

    python packaging/build_packages.py                 # tout, formats deb + arch
    python packaging/build_packages.py --only nebula,nova
    python packaging/build_packages.py --format deb     # ou arch
    python packaging/build_packages.py --github Sonaed  # propriétaire GitHub des PKGBUILD AUR

Sorties (dans packaging/dist/) :
  deb/existence-<app>_26.0-1_<arch>.deb      paquets Debian prêts à installer
  deb/existence-suite_26.0-1_all.deb          méta-paquet (installe tout)
  arch/<paquet>/PKGBUILD (+ source .tar.gz)   `makepkg -si` en local
  aur/<paquet>/PKGBUILD                        version AUR (sources git sur GitHub)

Chaque app est installée dans /usr/share/existence/<app> avec :
  /usr/bin/existence-<app>                     lanceur
  /usr/share/applications/existence-<app>.desktop
  /usr/share/icons/hicolor/scalable/apps/existence-<app>.svg
Les réglages, ressources et liens restent dans le dossier personnel
(~/.config/existence, ~/.local/share/CreativeSystem) : rien n'est écrit dans /usr.
"""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXISTENCE = HERE.parent
DOCUMENTS = Path(os.environ.get("EXISTENCE_SOURCES", Path.home() / "Documents"))
VERSION = "26.0"
RELEASE = "1"
MAINTAINER = os.environ.get("EXISTENCE_MAINTAINER", "Deanos <deanos@localhost>")
PREFIX = "/usr/share/existence"

EXCLUDE = [
    ".git", "__pycache__", "*.pyc", "build", "build_*", "build-*", "dist", "Claude outputs",
    "_backup*", "_avant*", "*.before_*", "*_backup.py", "main_v0.*", ".compat_test_py313",
    ".directory", "*.avant-renommage", "stardust_state.json", "CPP_TEST", "tests_gui",
    "venv", ".venv", "node_modules", "packaging", "*.ppm", "atlas_xppen_events.txt",
    "nebula_profile.txt",
]


@dataclass
class App:
    id: str
    folder: str
    name: str
    comment: str
    categories: str
    color: str
    letter: str
    run: list[str]                      # commande depuis le dossier installé
    arch_depends: list[str]
    deb_depends: list[str]
    arch_optdepends: list[str] = field(default_factory=list)
    deb_recommends: list[str] = field(default_factory=list)
    arch_makedepends: list[str] = field(default_factory=list)
    deb_build: list[str] = field(default_factory=list)
    build: list[str] = field(default_factory=list)     # commandes shell dans l'arbre source
    keep: list[str] = field(default_factory=list)      # artefacts de build conservés
    native: bool = False
    mime: str = ""
    conflicts: list[str] = field(default_factory=list)   # anciens paquets remplacés


PY_ARCH = ["python", "pyside6"]
PY_DEB = ["python3 (>= 3.11)", "python3-pyside6.qtcore", "python3-pyside6.qtgui", "python3-pyside6.qtwidgets"]
QT_DEB_RUNTIME = ["libqt6core6t64 | libqt6core6", "libqt6gui6t64 | libqt6gui6"]

APPS: dict[str, App] = {a.id: a for a in [
    App("existence", "Existence", "Existence", "Carte des univers créatifs, ressources partagées et wormholes",
        "Graphics;Utility;", "#A5B4FC", "E", ["python3", "galaxy_hub.py"],
        PY_ARCH, PY_DEB + ["python3-pyside6.qtsvg", "python3-pyside6.qtsvgwidgets"],
        arch_optdepends=["qt6-webengine: vue Cosmos intégrée", "git: installation d'apps depuis le catalogue"],
        deb_recommends=["python3-pyside6.qtwebenginewidgets", "git"]),
    App("nebula", "Nebula", "Nebula", "Peinture numérique — moteur de pinceaux C++",
        "Graphics;RasterGraphics;2DGraphics;", "#F062D5", "N", ["python3", "main.py"],
        PY_ARCH + ["python-numpy", "qt6-base", "zlib", "gcc-libs"],
        PY_DEB + ["python3-pyside6.qtopengl", "python3-pyside6.qtopenglwidgets", "python3-numpy", "zlib1g",
                  "libgomp1"] + QT_DEB_RUNTIME,
        arch_optdepends=["python-psd-tools: import PSD avec calques"],
        deb_recommends=["python3-psd-tools"],
        arch_makedepends=["cmake", "gcc"], deb_build=["cmake", "g++", "qt6-base-dev", "zlib1g-dev"],
        build=["cmake -S . -B build_cpp_native -DCMAKE_BUILD_TYPE=Release",
               "cmake --build build_cpp_native --target CreativeCoreBridge -j$(nproc)"],
        keep=["build_cpp_native/libCreativeCoreBridge.so"], native=True,
        mime="application/x-nebula"),
    App("stardust", "StarDust", "StarDust", "Atelier de création d'outils : pinceaux, fusions, palettes",
        "Graphics;Development;", "#A78BFA", "S", ["python3", "main.py"],
        PY_ARCH + ["python-numpy"], PY_DEB + ["python3-numpy"],
        arch_makedepends=["cmake", "gcc"], deb_build=["cmake", "g++"],
        build=["cmake -S native -B native/build -DCMAKE_BUILD_TYPE=Release",
               "cmake --build native/build -j$(nproc)"],
        keep=["native/build/stardust-core"], native=True),
    App("atlas", "Atlas", "Atlas", "Illustration vectorielle",
        "Graphics;VectorGraphics;", "#34D399", "A", ["bin/CreativeSystemAtlasGtk"],
        ["gtk4", "cairo", "zlib"], ["libgtk-4-1", "libcairo2", "zlib1g"],
        arch_makedepends=["cmake", "gcc", "pkgconf"], deb_build=["cmake", "g++", "pkg-config", "libgtk-4-dev", "zlib1g-dev"],
        build=["cmake -S . -B build_atlas -DCMAKE_BUILD_TYPE=Release",
               "cmake --build build_atlas -j$(nproc)",
               "mkdir -p bin && cp build_atlas/CreativeSystemAtlasGtk build_atlas/AtlasExistenceAdapter build_atlas/AtlasExport bin/"],
        keep=["bin/CreativeSystemAtlasGtk", "bin/AtlasExistenceAdapter", "bin/AtlasExport"], native=True),
    App("cosmos", "Cosmos", "Cosmos", "Notes, idées et constellations",
        "Office;Utility;", "#818CF8", "C", ["bin/cosmos-desktop"],
        ["qt6-webengine", "qt6-base"], ["libqt6webenginewidgets6", "libqt6webchannel6"] + QT_DEB_RUNTIME,
        arch_makedepends=["cmake", "gcc"], deb_build=["cmake", "g++", "qt6-base-dev", "qt6-webengine-dev", "qt6-webchannel-dev"],
        build=["cmake -S . -B build -DCMAKE_BUILD_TYPE=Release", "cmake --build build -j$(nproc)",
               "mkdir -p bin && cp build/cosmos-desktop bin/"],
        keep=["bin/cosmos-desktop"], native=True),
    App("nova", "Nova", "Nova", "Développement photo RAW non destructif",
        "Graphics;Photography;", "#FBBF24", "N", ["python3", "main.py"],
        PY_ARCH + ["python-numpy", "python-pillow"], PY_DEB + ["python3-numpy", "python3-pil"],
        arch_optdepends=["python-rawpy: ouverture des fichiers RAW (AUR)"],
        deb_recommends=["python3-rawpy"]),
    App("singularity", "Singularity", "Singularity", "Optimisation d'images pour le web (WebP)",
        "Graphics;Utility;", "#FFB45B", "S", ["python3", "webready.py"],
        PY_ARCH + ["python-pillow"], PY_DEB + ["python3-pil"],
        conflicts=["singularity-image-optimizer", "singularity-image-optimizer-git"]),
]}


def log(message: str) -> None:
    print(message, flush=True)


# ── sources ──────────────────────────────────────────────────
def excluded(rel: Path) -> bool:
    return any(fnmatch.fnmatch(part, pattern) for part in rel.parts for pattern in EXCLUDE)


def copy_source(app: App, target: Path) -> None:
    source = DOCUMENTS / app.folder
    if not source.is_dir():
        raise SystemExit(f"Sources introuvables pour {app.name} : {source}")
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if excluded(rel) or path.is_symlink():
            continue
        dest = target / rel
        if path.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)


def source_tarball(app: App, out: Path) -> Path:
    """Archive des sources propres (pour makepkg)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / f"existence-{app.id}-{VERSION}"
        copy_source(app, root)
        tarball = out / f"existence-{app.id}-{VERSION}.tar.gz"
        with tarfile.open(tarball, "w:gz") as tar:
            tar.add(root, arcname=root.name, filter=lambda info: _reproducible(info))
    return tarball


def _reproducible(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    return info


def build_native(app: App, tree: Path) -> None:
    for command in app.build:
        log(f"    $ {command}")
        subprocess.run(["bash", "-c", command], cwd=tree, check=True)
    for built in app.keep:
        if not (tree / built).exists():
            raise SystemExit(f"{app.name} : artefact manquant après compilation : {built}")
    # Ne garder des dossiers de build que les artefacts utiles.
    keep = {tree / k for k in app.keep}
    for build_dir in {Path(k).parts[0] for k in app.keep}:
        root = tree / build_dir
        if not root.is_dir() or build_dir == "bin":
            continue
        for path in sorted(root.rglob("*"), reverse=True):
            if path.is_file() and path not in keep:
                path.unlink()
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    if app.id == "stardust":
        shutil.rmtree(tree / "native" / "build" / "CMakeFiles", ignore_errors=True)


# ── fichiers communs ─────────────────────────────────────────
def launcher_script(app: App) -> str:
    home = f"{PREFIX}/{app.id}"
    command = " ".join(f'"{home}/{part}"' if part.startswith("bin/") else part for part in app.run)
    return textwrap.dedent(f"""\
        #!/bin/sh
        # Lanceur {app.name} {VERSION} — écosystème Existence
        export EXISTENCE_ROOT="{PREFIX}/existence"
        export EXISTENCE_APPS_DIR="{PREFIX}"
        cd "{home}" || exit 1
        exec {command} "$@"
        """)


def desktop_entry(app: App) -> str:
    mime = f"MimeType={app.mime};\n" if app.mime else ""
    return (f"[Desktop Entry]\nType=Application\nName={app.name}\nComment={app.comment}\n"
            f"Exec=existence-{app.id} %F\nIcon=existence-{app.id}\nTerminal=false\n"
            f"Categories={app.categories}\nStartupNotify=true\n{mime}X-Existence-Id={app.id}\n")


def icon_svg(app: App) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
            f'<defs><radialGradient id="g" cx="38%" cy="32%" r="75%"><stop offset="0" stop-color="#ffffff"/>'
            f'<stop offset=".18" stop-color="{app.color}"/><stop offset="1" stop-color="#14122b"/></radialGradient></defs>'
            f'<circle cx="64" cy="64" r="58" fill="url(#g)"/>'
            f'<ellipse cx="64" cy="64" rx="62" ry="16" fill="none" stroke="{app.color}" stroke-opacity=".55" stroke-width="3" transform="rotate(-18 64 64)"/>'
            f'<text x="64" y="80" text-anchor="middle" font-family="sans-serif" font-size="46" font-weight="700" fill="#ffffff">{app.letter}</text></svg>\n')


def install_tree(app: App, built: Path, root: Path) -> None:
    home = root / PREFIX.lstrip("/") / app.id
    shutil.copytree(built, home)
    bin_dir = root / "usr" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher = bin_dir / f"existence-{app.id}"
    launcher.write_text(launcher_script(app), encoding="utf-8")
    launcher.chmod(0o755)
    apps = root / "usr" / "share" / "applications"
    apps.mkdir(parents=True, exist_ok=True)
    (apps / f"existence-{app.id}.desktop").write_text(desktop_entry(app), encoding="utf-8")
    icons = root / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    icons.mkdir(parents=True, exist_ok=True)
    (icons / f"existence-{app.id}.svg").write_text(icon_svg(app), encoding="utf-8")
    for path in home.rglob("*"):
        if path.is_file():
            path.chmod(0o755 if (os.access(path, os.X_OK) or path.suffix == ".sh") else 0o644)


# ── Debian ───────────────────────────────────────────────────
def deb_arch(app: App) -> str:
    if not app.native:
        return "all"
    machine = platform.machine()
    return {"x86_64": "amd64", "aarch64": "arm64"}.get(machine, machine)


def deb_control(app: App, size_kb: int) -> str:
    lines = [f"Package: existence-{app.id}", f"Version: {VERSION}-{RELEASE}", "Section: graphics",
             "Priority: optional", f"Architecture: {deb_arch(app)}", f"Maintainer: {MAINTAINER}",
             f"Installed-Size: {size_kb}", f"Depends: {', '.join(app.deb_depends)}"]
    if app.deb_recommends:
        lines.append(f"Recommends: {', '.join(app.deb_recommends)}")
    if app.id != "existence":
        lines.append("Suggests: existence-existence")
    if app.conflicts:
        lines.append(f"Conflicts: {', '.join(app.conflicts)}")
        lines.append(f"Replaces: {', '.join(app.conflicts)}")
    lines.append(f"Homepage: https://github.com/{GITHUB}/{app.folder}")
    lines.append(f"Description: {app.name} {VERSION} — {app.comment}")
    lines.append(" Fait partie de l'écosystème créatif Existence (CreativeSystem).")
    return "\n".join(lines) + "\n"


POSTINST = """#!/bin/sh
set -e
python3 -m compileall -q "{home}" >/dev/null 2>&1 || true
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor || true
exit 0
"""
PRERM = """#!/bin/sh
set -e
find "{home}" -name __pycache__ -type d -prune -exec rm -rf {{}} + 2>/dev/null || true
exit 0
"""


def write_deb(root: Path, output: Path) -> None:
    if shutil.which("dpkg-deb"):
        subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", str(root), str(output)],
                       check=True, stdout=subprocess.DEVNULL)
        return
    # Sans dpkg (Arch) : un .deb est une archive ar de trois membres.
    def tar_bytes(base: Path, include_debian: bool) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            for path in sorted(base.rglob("*")):
                rel = path.relative_to(base)
                if (rel.parts[0] == "DEBIAN") != include_debian:
                    continue
                arc = "./" + str(rel.relative_to("DEBIAN") if include_debian else rel)
                tar.add(path, arcname=arc, recursive=False, filter=_reproducible)
        return buffer.getvalue()

    members = [("debian-binary", b"2.0\n"), ("control.tar.gz", tar_bytes(root, True)),
               ("data.tar.gz", tar_bytes(root, False))]
    with open(output, "wb") as out:
        out.write(b"!<arch>\n")
        for name, data in members:
            header = f"{name:<16}{int(time.time()):<12}0     0     100644  {len(data):<10}`\n"
            out.write(header.encode())
            out.write(data)
            if len(data) % 2:
                out.write(b"\n")


def package_deb(app: App, built: Path, out: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        install_tree(app, built, root)
        size_kb = sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) // 1024 + 1
        debian = root / "DEBIAN"
        debian.mkdir()
        (debian / "control").write_text(deb_control(app, size_kb), encoding="utf-8")
        home = f"{PREFIX}/{app.id}"
        for name, body in (("postinst", POSTINST), ("prerm", PRERM)):
            (debian / name).write_text(body.format(home=home), encoding="utf-8")
            (debian / name).chmod(0o755)
        target = out / f"existence-{app.id}_{VERSION}-{RELEASE}_{deb_arch(app)}.deb"
        write_deb(root, target)
    return target


def meta_deb(out: Path) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "root"
        (root / "DEBIAN").mkdir(parents=True)
        doc = root / "usr" / "share" / "doc" / "existence-suite"
        doc.mkdir(parents=True)
        (doc / "README").write_text("Méta-paquet : installe toutes les apps de l'écosystème Existence.\n")
        depends = ", ".join(f"existence-{a}" for a in APPS)
        (root / "DEBIAN" / "control").write_text(
            f"Package: existence-suite\nVersion: {VERSION}-{RELEASE}\nSection: graphics\nPriority: optional\n"
            f"Architecture: all\nMaintainer: {MAINTAINER}\nDepends: {depends}\n"
            f"Description: Existence {VERSION} — suite créative complète\n"
            " Existence, Nebula, StarDust, Atlas, Cosmos, Nova et Singularity.\n", encoding="utf-8")
        target = out / f"existence-suite_{VERSION}-{RELEASE}_all.deb"
        write_deb(root, target)
    return target


# ── Arch / AUR ───────────────────────────────────────────────
def arch_names(values: list[str]) -> str:
    return " ".join(f"'{v}'" for v in values)


def pkgbuild(app: App, source_line: str, checksum: str, srcdir_name: str) -> str:
    build = "\n".join(f"  {c}" for c in app.build) if app.build else "  :"
    keep = " ".join(f"'{k}'" for k in app.keep)
    return f"""# Maintainer: {MAINTAINER}
# Généré par Existence/packaging/build_packages.py — ne pas modifier à la main.
pkgname=existence-{app.id}
pkgver={VERSION}
pkgrel={RELEASE}
pkgdesc="{app.name} — {app.comment} (écosystème Existence)"
arch=('{'x86_64' if app.native else 'any'}')
url="https://github.com/{GITHUB}/{app.folder}"
license=('custom')
depends=({arch_names(app.arch_depends)})
makedepends=({arch_names(app.arch_makedepends)})
optdepends=({arch_names(app.arch_optdepends)})
conflicts=({arch_names(app.conflicts)})
replaces=({arch_names(app.conflicts)})
source=({source_line})
sha256sums=('{checksum}')

build() {{
  cd "$srcdir/{srcdir_name}"
{build}
}}

package() {{
  cd "$srcdir/{srcdir_name}"
  local home="$pkgdir{PREFIX}/{app.id}"
  install -d "$home"
  # Sources, sans dossiers de build ; seuls les artefacts utiles sont gardés.
  find . -mindepth 1 -maxdepth 1 ! -name 'build*' ! -name '.git' -exec cp -a {{}} "$home/" \\;
  for artefact in {keep}; do
    install -Dm755 "$artefact" "$home/$artefact"
  done
  find "$home" -name '__pycache__' -prune -exec rm -rf {{}} +
  rm -rf "$home/native/build/CMakeFiles" 2>/dev/null || true
  python -m compileall -q "$home" >/dev/null 2>&1 || true
  install -Dm755 "$startdir/existence-{app.id}" "$pkgdir/usr/bin/existence-{app.id}"
  install -Dm644 "$startdir/existence-{app.id}.desktop" "$pkgdir/usr/share/applications/existence-{app.id}.desktop"
  install -Dm644 "$startdir/existence-{app.id}.svg" "$pkgdir/usr/share/icons/hicolor/scalable/apps/existence-{app.id}.svg"
}}
"""


def arch_meta() -> str:
    return f"""# Maintainer: {MAINTAINER}
pkgname=existence-suite
pkgver={VERSION}
pkgrel={RELEASE}
pkgdesc="Existence {VERSION} — suite créative complète (méta-paquet)"
arch=('any')
url="https://github.com/{GITHUB}/Existence"
license=('custom')
depends=({arch_names([f'existence-{a}' for a in APPS])})
"""


def write_arch(app: App, out_local: Path, out_aur: Path) -> None:
    for folder in (out_local, out_aur):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"existence-{app.id}").write_text(launcher_script(app), encoding="utf-8")
        (folder / f"existence-{app.id}.desktop").write_text(desktop_entry(app), encoding="utf-8")
        (folder / f"existence-{app.id}.svg").write_text(icon_svg(app), encoding="utf-8")
    tarball = source_tarball(app, out_local)
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    (out_local / "PKGBUILD").write_text(
        pkgbuild(app, f"'{tarball.name}'", digest, f"existence-{app.id}-{VERSION}"), encoding="utf-8")
    (out_aur / "PKGBUILD").write_text(
        pkgbuild(app, f"\"{app.folder}::git+https://github.com/{GITHUB}/{app.folder}.git#tag=v{VERSION}\"",
                 "SKIP", app.folder).replace("makedepends=(", "makedepends=('git' ", 1), encoding="utf-8")
    for folder in (out_local, out_aur):
        if shutil.which("makepkg"):
            srcinfo = subprocess.run(["makepkg", "--printsrcinfo"], cwd=folder, capture_output=True, text=True)
            if srcinfo.returncode == 0:
                (folder / ".SRCINFO").write_text(srcinfo.stdout, encoding="utf-8")


# ── orchestration ───────────────────────────────────────────
GITHUB = os.environ.get("EXISTENCE_GITHUB", "Sonaed")


def main() -> int:
    global GITHUB
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", default="", help="apps à construire (virgules)")
    parser.add_argument("--format", choices=("all", "deb", "arch"), default="all")
    parser.add_argument("--github", default=GITHUB, help="propriétaire GitHub pour les PKGBUILD AUR")
    parser.add_argument("--out", default=str(HERE / "dist"))
    parser.add_argument("--skip-native", action="store_true", help="ne pas compiler (tests du packaging)")
    args = parser.parse_args()
    GITHUB = args.github
    wanted = [a.strip() for a in args.only.split(",") if a.strip()] or list(APPS)
    unknown = [a for a in wanted if a not in APPS]
    if unknown:
        raise SystemExit(f"Apps inconnues : {unknown}. Connues : {list(APPS)}")
    out = Path(args.out)
    (out / "deb").mkdir(parents=True, exist_ok=True)
    done = []
    for app_id in wanted:
        app = APPS[app_id]
        log(f"\n▸ {app.name} {VERSION}")
        if args.format in ("all", "deb"):
            with tempfile.TemporaryDirectory() as tmp:
                tree = Path(tmp) / app.id
                copy_source(app, tree)
                if app.build and not args.skip_native:
                    build_native(app, tree)
                deb = package_deb(app, tree, out / "deb")
                log(f"  .deb   {deb}")
                done.append(deb)
        if args.format in ("all", "arch"):
            write_arch(app, out / "arch" / f"existence-{app.id}", out / "aur" / f"existence-{app.id}")
            log(f"  Arch   {out / 'arch' / f'existence-{app.id}'}/PKGBUILD   (AUR : {out / 'aur' / f'existence-{app.id}'})")
    if not args.only:
        if args.format in ("all", "deb"):
            log(f"\n▸ méta-paquet\n  .deb   {meta_deb(out / 'deb')}")
        if args.format in ("all", "arch"):
            for folder in (out / "arch" / "existence-suite", out / "aur" / "existence-suite"):
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "PKGBUILD").write_text(arch_meta(), encoding="utf-8")
    if args.format in ("all", "deb") and shutil.which("dpkg-scanpackages"):
        index = subprocess.run(["dpkg-scanpackages", "--multiversion", "."], cwd=out / "deb",
                               capture_output=True, text=True)
        if index.returncode == 0:
            (out / "deb" / "Packages").write_text(index.stdout, encoding="utf-8")
            with gzip.open(out / "deb" / "Packages.gz", "wt", encoding="utf-8") as handle:
                handle.write(index.stdout)
            log(f"\nIndex APT : {out / 'deb' / 'Packages.gz'}")
    log("\nTerminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
