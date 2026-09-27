"""Outils partagés par les interfaces de Creator d'Existence (Qt + couleur)."""

from __future__ import annotations

import colorsys
import json
import math

DEFAULT_THEME = {
    "bg": "#0B1224", "panel": "#111A31", "panel2": "#0E172B", "line": "#243251",
    "text": "#EAF0FF", "muted": "#7F91B8", "dim": "#56678C", "accent": "#8C9EFF",
    "primary": "#7667E8", "ok": "#5CE1B9", "warn": "#F5C56B", "err": "#FF7A8A",
}


def theme(host: dict | None) -> dict:
    t = dict(DEFAULT_THEME)
    t.update((host or {}).get("theme") or {})
    return t


class History:
    """Historique annuler/rétablir par instantanés JSON."""

    def __init__(self, snapshot, load, limit=100):
        self._snapshot, self._load, self.limit = snapshot, load, limit
        self.undo_stack: list[str] = []
        self.redo_stack: list[str] = []
        self._last = None

    def reset(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._last = json.dumps(self._snapshot())

    def commit(self) -> bool:
        """Enregistre l'état courant ; renvoie True si quelque chose a changé."""
        now = json.dumps(self._snapshot())
        if self._last is None:
            self._last = now
            return False
        if now == self._last:
            return False
        self.undo_stack.append(self._last)
        del self.undo_stack[:-self.limit]
        self.redo_stack.clear()
        self._last = now
        return True

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        self.redo_stack.append(json.dumps(self._snapshot()))
        self._last = self.undo_stack.pop()
        self._load(json.loads(self._last))
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        self.undo_stack.append(json.dumps(self._snapshot()))
        self._last = self.redo_stack.pop()
        self._load(json.loads(self._last))
        return True


# ─── Couleur ───────────────────────────────────────────────────────────────
def hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = str(value).lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (0.0, 0.0, 0.0)


def rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb[:3])


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def rgb_to_oklab(rgb):
    r, g, b = (_lin(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklab_to_rgb(lab):
    L, a, b = lab
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (_gam(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
            _gam(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
            _gam(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))


def mix(c1, c2, t, space="RGB"):
    """Interpole deux couleurs RGB (0..1) dans l'espace demandé."""
    if space.startswith("HSV"):
        h1, s1, v1 = colorsys.rgb_to_hsv(*c1)
        h2, s2, v2 = colorsys.rgb_to_hsv(*c2)
        dh = ((h2 - h1 + 0.5) % 1.0) - 0.5
        return colorsys.hsv_to_rgb((h1 + dh * t) % 1.0, s1 + (s2 - s1) * t, v1 + (v2 - v1) * t)
    if space.startswith("Perceptuel") or space.lower().startswith("oklab"):
        a, b = rgb_to_oklab(c1), rgb_to_oklab(c2)
        return oklab_to_rgb(tuple(x + (y - x) * t for x, y in zip(a, b)))
    return tuple(x + (y - x) * t for x, y in zip(c1, c2))


def relative_luminance(rgb) -> float:
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def median_cut(pixels: list[tuple[float, float, float]], count: int) -> list[tuple[float, float, float]]:
    """Quantification simple : renvoie `count` couleurs représentatives."""
    boxes = [pixels] if pixels else []
    while boxes and len(boxes) < count:
        boxes.sort(key=len, reverse=True)
        box = boxes.pop(0)
        if len(box) < 2:
            boxes.append(box)
            break
        ranges = [max(p[i] for p in box) - min(p[i] for p in box) for i in range(3)]
        axis = ranges.index(max(ranges))
        box.sort(key=lambda p: p[axis])
        mid = len(box) // 2
        boxes.extend([box[:mid], box[mid:]])
    out = []
    for box in boxes:
        n = len(box)
        out.append(tuple(sum(p[i] for p in box) / n for i in range(3)))
    out.sort(key=lambda c: colorsys.rgb_to_hsv(*c)[0])
    return out
