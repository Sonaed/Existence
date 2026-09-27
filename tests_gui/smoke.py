#!/usr/bin/env python3
"""Banc de test GUI d'Existence — vrais processus, vraies fenêtres.

    python tests_gui/smoke.py                # Xvfb si disponible, sinon ton écran
    python tests_gui/smoke.py --screen       # fenêtres visibles sur ton écran
    python tests_gui/smoke.py --offscreen    # Qt sans affichage (OpenGL parfois indisponible)
    python tests_gui/smoke.py --only 1,2     # quelques scénarios seulement
    python tests_gui/smoke.py --keep         # garde le dossier de test (logs, états)

Isolation : chaque exécution utilise un HOME temporaire (catalogue Existence,
wormholes, ressources et réglages neufs) — tes vrais réglages ne sont pas touchés.
Les apps sont lancées par Existence lui-même, comme en vrai.

Scénarios :
  1. Nebula → Nova : lien en direct (Nova s'ouvre seule, un réglage revient dans le calque)
  2. Nova → Nebula : envoi d'image (nouveau calque)
  3. Nebula fermé → Alt-glisser (Nova → Nebula) : Existence relance Nebula, le lien arrive
     3b. Nebula fermé → Alt-glisser (Nebula → Nova) : Nebula s'ouvre et explique qu'il faut un document
  4. Fusion → Nebula : le panneau de fusion apparaît
  5. Palette → Nebula : panneau + menu Modules
  6. module incompatible (Pixel Art → StarDust) : refus expliqué, rien ne change
  7. débrancher → l'interface disparaît
  8. rebrancher → l'interface réapparaît
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

EXISTENCE = Path(__file__).resolve().parents[1]


class Failure(AssertionError):
    pass


class Harness:
    def __init__(self, home: Path, env: dict) -> None:
        self.home = home
        self.probe = Path(env["EXISTENCE_TEST_PROBE"])
        self.env = env
        self.counter = 0
        self.procs: list[subprocess.Popen] = []
        self.log = open(home / "hub.log", "w")

    # ── état / commandes ──
    def state(self, app: str) -> dict:
        try:
            return json.loads((self.probe / f"{app}.state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def fresh(self, app: str, max_age: float = 3.0) -> dict:
        data = self.state(app)
        if data and time.time() - float(data.get("time", 0)) < max_age:
            try:
                os.kill(int(data["pid"]), 0)
                return data
            except (OSError, KeyError, ValueError):
                return {}
        return {}

    def wait(self, what: str, predicate, timeout: float = 30.0):
        end = time.time() + timeout
        last = None
        while time.time() < end:
            try:
                last = predicate()
                if last:
                    return last
            except (KeyError, IndexError, TypeError, ValueError):
                pass
            time.sleep(0.3)
        raise Failure(f"délai dépassé ({timeout:.0f} s) : {what}")

    def cmd(self, app: str, name: str, *args, timeout: float = 20.0):
        self.counter += 1
        ident = str(self.counter)
        with open(self.probe / f"{app}.cmd.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"id": ident, "cmd": name, "args": list(args)}) + "\n")
        result = self.wait(f"{app}.{name}{tuple(args)}", lambda: self.fresh(app).get("results", {}).get(ident),
                           timeout)
        if not result.get("ok"):
            raise Failure(f"{app}.{name} a échoué : {result.get('error')}\n{result.get('trace', '')}")
        return result.get("value")

    # ── processus ──
    def start_hub(self) -> None:
        proc = subprocess.Popen([sys.executable, str(EXISTENCE / "galaxy_hub.py")], cwd=str(EXISTENCE),
                                env=self.env, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        self.procs.append(proc)
        self.wait("Existence démarre", lambda: self.fresh("existence"), 40)

    def kill_app(self, app: str) -> None:
        data = self.state(app)
        pid = int(data.get("pid", 0))
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            self.wait(f"{app} fermé", lambda: not self._alive(pid), 15)

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def shutdown(self) -> None:
        for app in ("nebula", "nova", "singularity"):
            pid = int(self.state(app).get("pid", 0) or 0)
            if pid and self._alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
        for proc in self.procs:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                pass
        time.sleep(1)
        for proc in self.procs:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass

    # ── aides ──
    def ensure_nebula(self) -> dict:
        if not self.fresh("nebula"):
            self.cmd("existence", "launch", "nebula")
        return self.wait("Nebula prêt", lambda: self.fresh("nebula"), 90)

    def ensure_document(self) -> None:
        if not self.fresh("nebula").get("document"):
            self.cmd("nebula", "new_document", 64, 64)
            self.wait("document Nebula ouvert", lambda: self.fresh("nebula").get("document"))

    def dock(self, app: str, name: str) -> dict | None:
        return next((d for d in self.fresh(app).get("docks", []) if d["name"] == name), None)

    def modules_menu(self, app: str) -> dict:
        return self.fresh(app).get("menus", {}).get("Modules", {})


# ══════════════════════════════════════════════════════════════
#  Scénarios
# ══════════════════════════════════════════════════════════════

def s6_incompatible(h: Harness) -> str:
    before = h.fresh("existence")["hosts"].get("pixel_art")
    h.cmd("existence", "plug", "pixel_art", "", "stardust", False)
    notice = h.wait("message de refus", lambda: "ne peut pas" in h.fresh("existence").get("last_notice", "")
                    and h.fresh("existence")["last_notice"])
    after = h.fresh("existence")["hosts"].get("pixel_art")
    if after != before:
        raise Failure(f"Pixel Art a quand même été branché : {before} → {after}")
    return notice


def s4_fusion(h: Harness) -> str:
    h.ensure_nebula()
    h.cmd("existence", "plug", "fusion_creator", "", "nebula", False)
    h.wait("Nebula voit Fusion branché", lambda: h.fresh("nebula").get("fusion_available"), 15)
    h.wait("panneau Fusion dans la fenêtre",
           lambda: (h.dock("nebula", "BlendCreatorDock") or {}).get("in_layout")
           and h.dock("nebula", "BlendCreatorDock").get("enabled"), 15)
    return "panneau de fusion présent et actif"


PALETTE_DOCK = "existence_module_palette_creator"


def s5_palette(h: Harness) -> str:
    h.ensure_nebula()
    h.cmd("existence", "plug", "palette_creator", "", "nebula", False)
    h.wait("panneau Palette Creator", lambda: (h.dock("nebula", PALETTE_DOCK) or {}).get("in_layout"), 20)
    menu = h.wait("menu Modules visible avec Palette",
                  lambda: h.modules_menu("nebula").get("visible") and h.modules_menu("nebula"), 10)
    return f"panneau + menu Modules ({len(menu.get('items', []))} entrée(s))"


def s7_unplug(h: Harness) -> str:
    h.cmd("existence", "plug", "palette_creator", "nebula", "__toolbox__", True)
    h.wait("panneau Palette retiré", lambda: not (h.dock("nebula", PALETTE_DOCK) or {}).get("in_layout"), 20)
    h.cmd("existence", "plug", "fusion_creator", "nebula", "__toolbox__", True)
    h.wait("panneau Fusion retiré", lambda: not (h.dock("nebula", "BlendCreatorDock") or {}).get("in_layout"), 20)
    return "Palette et Fusion retirés de Nebula"


def s8_replug(h: Harness) -> str:
    h.cmd("existence", "plug", "palette_creator", "", "nebula", False)
    h.wait("panneau Palette revenu", lambda: (h.dock("nebula", PALETTE_DOCK) or {}).get("in_layout"), 20)
    h.cmd("existence", "plug", "fusion_creator", "", "nebula", False)
    h.wait("panneau Fusion revenu", lambda: (h.dock("nebula", "BlendCreatorDock") or {}).get("in_layout"), 20)
    return "Palette et Fusion revenus"


def s1_nebula_to_nova(h: Harness) -> str:
    h.ensure_nebula()
    h.ensure_document()
    layer_id = h.cmd("nebula", "fill_active", 200, 40, 40)
    h.cmd("nebula", "send_layer", "nova", True)
    nova = h.wait("Nova lancé par Existence et lien reçu",
                  lambda: h.fresh("nova").get("link_id") and h.fresh("nova"), 90)
    before = next(l["hash"] for l in h.fresh("nebula")["layers"] if l["id"] == layer_id)
    h.cmd("nova", "set", "exposure", 1.5)
    h.wait("le réglage de Nova revient dans le calque Nebula",
           lambda: next(l["hash"] for l in h.fresh("nebula")["layers"] if l["id"] == layer_id) != before, 30)
    return f"lien {nova['link_id']} ; calque mis à jour par Nova"


def s2_nova_to_nebula(h: Harness) -> str:
    h.ensure_nebula()
    h.ensure_document()
    if not h.fresh("nova").get("photo"):
        raise Failure("Nova n'a pas de photo ouverte (le scénario 1 doit passer avant)")
    count = len(h.fresh("nebula")["layers"])
    h.cmd("nova", "send_to", "nebula", False)
    layers = h.wait("nouveau calque reçu dans Nebula",
                    lambda: len(h.fresh("nebula")["layers"]) > count and h.fresh("nebula")["layers"], 20)
    return f"calque « {layers[-1]['name']} »"


def s3_closed_alt_drag(h: Harness) -> str:
    h.kill_app("nebula")
    h.cmd("existence", "request_wormhole", "nova", "nebula")
    data = h.wait("Existence relance Nebula et le lien arrive",
                  lambda: (h.fresh("nebula").get("live_links") or None) and h.fresh("nebula"), 120)
    return f"Nebula relancé (pid {data['pid']}), {len(data['live_links'])} lien(s) en direct"


def s3b_closed_alt_drag_reverse(h: Harness) -> str:
    h.kill_app("nebula")
    h.cmd("existence", "request_wormhole", "nebula", "nova")
    status = h.wait("Nebula relancé et message « ouvre un document »",
                    lambda: "document" in (h.fresh("nebula").get("status") or "") and h.fresh("nebula")["status"], 120)
    return status


SCENARIOS = [
    ("6", "Module incompatible → refus", s6_incompatible),
    ("4", "Fusion → Nebula", s4_fusion),
    ("5", "Palette → Nebula", s5_palette),
    ("7", "Débrancher → l'UI disparaît", s7_unplug),
    ("8", "Rebrancher → l'UI réapparaît", s8_replug),
    ("1", "Nebula → Nova (lien en direct)", s1_nebula_to_nova),
    ("2", "Nova → Nebula (envoi d'image)", s2_nova_to_nebula),
    ("3", "Nebula fermé → Alt-glisser Nova→Nebula", s3_closed_alt_drag),
    ("3b", "Nebula fermé → Alt-glisser Nebula→Nova", s3b_closed_alt_drag_reverse),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--screen", action="store_true")
    mode.add_argument("--offscreen", action="store_true")
    parser.add_argument("--only", default="")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--inside-xvfb", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if not (args.screen or args.offscreen or args.inside_xvfb) and shutil.which("xvfb-run"):
        command = ["xvfb-run", "-a", "-s", "-screen 0 1600x1000x24", sys.executable, __file__, "--inside-xvfb"]
        if args.only:
            command += ["--only", args.only]
        if args.keep:
            command.append("--keep")
        return subprocess.call(command)
    display = ("Xvfb" if args.inside_xvfb else "offscreen" if args.offscreen else
               f"écran ({os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY') or '?'})")
    if not args.inside_xvfb and not args.screen and not args.offscreen:
        print("xvfb-run introuvable (paquet xorg-server-xvfb) : les fenêtres s'ouvriront sur ton écran.")

    home = Path(tempfile.mkdtemp(prefix="existence-smoke-"))
    env = dict(os.environ)
    env.update({
        "HOME": str(home), "EXISTENCE_TEST_PROBE": str(home / "probe"),
        "EXISTENCE_ROOT": str(EXISTENCE), "XDG_RUNTIME_DIR": str(home / "run"),
        "XDG_CONFIG_HOME": str(home / ".config"), "PYTHONUNBUFFERED": "1",
    })
    env.pop("CREATIVE_SYSTEM_DATA_HOME", None)
    (home / "run").mkdir(mode=0o700)
    if args.offscreen:
        env["QT_QPA_PLATFORM"] = "offscreen"
    elif args.inside_xvfb:
        env["QT_QPA_PLATFORM"] = "xcb"
        env.pop("WAYLAND_DISPLAY", None)

    wanted = {s.strip() for s in args.only.split(",") if s.strip()}
    selected = [s for s in SCENARIOS if not wanted or s[0] in wanted]
    print(f"Banc de test Existence · affichage : {display} · dossier : {home}\n")
    h = Harness(home, env)
    results = []
    try:
        h.start_hub()
        for ident, title, function in selected:
            started = time.time()
            try:
                detail = function(h)
                results.append((ident, title, True, detail, time.time() - started))
                print(f"  ✔ {ident:>2}  {title}  —  {detail}  ({time.time() - started:.1f} s)")
            except Exception as exc:  # noqa: BLE001
                message = str(exc) if isinstance(exc, Failure) else traceback.format_exc()[-800:]
                results.append((ident, title, False, message, time.time() - started))
                print(f"  ✘ {ident:>2}  {title}\n       {message}")
    except Exception as exc:  # noqa: BLE001
        print(f"Impossible de démarrer Existence : {exc}")
    finally:
        h.shutdown()
        snapshot = home / "etats_finaux"
        snapshot.mkdir(exist_ok=True)
        for state in (home / "probe").glob("*.state.json"):
            shutil.copy(state, snapshot / state.name)
    passed = sum(1 for r in results if r[2])
    print(f"\n{passed}/{len(selected)} scénario(s) réussi(s).")
    print(f"Logs et états : {home}" if (args.keep or passed < len(selected)) else "")
    if passed == len(selected) and not args.keep:
        shutil.rmtree(home, ignore_errors=True)
    return 0 if passed == len(selected) else 1


if __name__ == "__main__":
    sys.exit(main())
