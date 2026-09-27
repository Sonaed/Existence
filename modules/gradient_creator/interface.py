"""Interface du module Gradient Creator (protocole existence.creator.v1).

Possédée par Existence ; chargée par l'univers hôte (StarDust).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush, QColor, QConicalGradient, QGradient, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QVBoxLayout, QWidget,
)

from modules.creator_ui import History, hex_to_rgb, mix, theme

INTERPOLATIONS = ["Perceptuel (OKLab)", "RGB", "HSV (teinte la plus courte)"]
PRESETS = {
    "Nuit stellaire": [(0.0, "#0B1224"), (0.55, "#3E4A89"), (1.0, "#8C9EFF")],
    "Coucher de soleil": [(0.0, "#2D1B69"), (0.45, "#E85D9E"), (0.8, "#F7A35C"), (1.0, "#FDE68A")],
    "Océan": [(0.0, "#03256C"), (0.5, "#2541B2"), (1.0, "#06BEE1")],
    "Forêt": [(0.0, "#0B3D2E"), (0.6, "#3F8F4F"), (1.0, "#D8E9A8")],
    "Noir → blanc": [(0.0, "#000000"), (1.0, "#FFFFFF")],
    "Arc-en-ciel": [(i / 6, QColor.fromHsvF(i / 6 * 0.83, 0.85, 1.0).name()) for i in range(7)],
}


def create_creator(host: dict | None = None):
    return GradientCreator(host or {})


def sample(stops, t, interpolation="RGB"):
    """Couleur (r, g, b, a) en 0..1 à la position t."""
    if not stops:
        return (0.0, 0.0, 0.0, 0.0)
    st = sorted(stops, key=lambda s: s["pos"])
    if t <= st[0]["pos"]:
        return (*hex_to_rgb(st[0]["hex"]), st[0].get("alpha", 1.0))
    if t >= st[-1]["pos"]:
        return (*hex_to_rgb(st[-1]["hex"]), st[-1].get("alpha", 1.0))
    for a, b in zip(st, st[1:]):
        if a["pos"] <= t <= b["pos"]:
            span = max(1e-9, b["pos"] - a["pos"])
            f = (t - a["pos"]) / span
            mid = a.get("mid", 0.5)
            if mid != 0.5:   # point milieu déplacé → courbe de transition
                f = f ** (math.log(0.5) / math.log(max(0.01, min(0.99, mid))))
            rgb = mix(hex_to_rgb(a["hex"]), hex_to_rgb(b["hex"]), f, interpolation)
            alpha = a.get("alpha", 1.0) + (b.get("alpha", 1.0) - a.get("alpha", 1.0)) * f
            return (*rgb, alpha)
    return (*hex_to_rgb(st[-1]["hex"]), st[-1].get("alpha", 1.0))


def qt_stops(stops, interpolation, steps=48):
    """Échantillonne le dégradé pour que Qt reproduise l'interpolation choisie."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        r, g, b, a = sample(stops, t, interpolation)
        out.append((t, QColor.fromRgbF(max(0, min(1, r)), max(0, min(1, g)), max(0, min(1, b)), max(0, min(1, a)))))
    return out


def checker(p, rect, size=8):
    p.save()
    p.setClipRect(rect)
    p.fillRect(rect, QColor("#DDDDDD"))
    y = rect.top()
    row = 0
    while y < rect.bottom():
        x = rect.left() + (size if row % 2 else 0)
        while x < rect.right():
            p.fillRect(QRectF(x, y, size, size), QColor("#AAAAAA"))
            x += size * 2
        y += size
        row += 1
    p.restore()


class GradientBar(QWidget):
    """Barre d'édition : clic sur la barre = ajouter un arrêt, glisser un arrêt =
    le déplacer, le tirer vers le bas = le supprimer, double-clic = couleur."""
    selected_changed = Signal(int)
    edited = Signal()
    live = Signal()

    def __init__(self, creator, t):
        super().__init__()
        self.c, self.t = creator, t
        self.selected = 0
        self._drag = None
        self._removing = False
        self.setMinimumHeight(110)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def bar_rect(self):
        return QRectF(14, 10, self.width() - 28, 52)

    def x_of(self, pos):
        r = self.bar_rect()
        return r.left() + pos * r.width()

    def pos_of(self, x):
        r = self.bar_rect()
        return max(0.0, min(1.0, (x - r.left()) / r.width()))

    def handle_at(self, pt):
        best, dist = -1, 12.0
        for i, s in enumerate(self.c.stops):
            d = abs(self.x_of(s["pos"]) - pt.x())
            if d < dist and pt.y() > self.bar_rect().bottom() - 4:
                best, dist = i, d
        return best

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.bar_rect()
        checker(p, r)
        g = QLinearGradient(r.left(), 0, r.right(), 0)
        for t, col in qt_stops(self.c.stops, self.c.interpolation, 96):
            g.setColorAt(t, col)
        p.setPen(QPen(QColor(self.t["line"]), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, 6, 6)
        for i, s in enumerate(self.c.stops):
            x = self.x_of(s["pos"])
            y = r.bottom() + 4
            path = QPainterPath()
            path.moveTo(x, y)
            path.lineTo(x - 9, y + 12)
            path.lineTo(x + 9, y + 12)
            path.closeSubpath()
            sel = i == self.selected
            p.setPen(QPen(QColor("#FFFFFF" if sel else self.t["muted"]), 2 if sel else 1))
            p.setBrush(QColor(s["hex"]))
            p.drawPath(path)
            p.drawRoundedRect(QRectF(x - 9, y + 12, 18, 18), 3, 3)
            if self._drag == i and self._removing:
                p.setPen(QColor(self.t["err"]))
                p.drawText(QRectF(x - 40, y + 32, 80, 16), Qt.AlignmentFlag.AlignCenter, "retirer")
        p.end()

    def mousePressEvent(self, e):
        self.setFocus()
        pt = e.position()
        i = self.handle_at(pt)
        if i < 0 and self.bar_rect().adjusted(0, 0, 0, 20).contains(pt):
            pos = self.pos_of(pt.x())
            r, g, b, a = sample(self.c.stops, pos, self.c.interpolation)
            self.c.stops.append({"pos": round(pos, 4), "hex": QColor.fromRgbF(r, g, b).name().upper(), "alpha": round(a, 3)})
            i = len(self.c.stops) - 1
            self.edited.emit()
        if i >= 0:
            self.select(i)
            self._drag = i

    def mouseMoveEvent(self, e):
        if self._drag is None:
            return
        pt = e.position()
        self._removing = pt.y() > self.bar_rect().bottom() + 70 and len(self.c.stops) > 2
        self.c.stops[self._drag]["pos"] = round(self.pos_of(pt.x()), 4)
        self.update()
        self.live.emit()

    def mouseReleaseEvent(self, _e):
        if self._drag is not None:
            if self._removing:
                self.c.stops.pop(self._drag)
                self.select(max(0, self._drag - 1))
            self._drag = None
            self._removing = False
            self.edited.emit()
        self.update()

    def mouseDoubleClickEvent(self, e):
        i = self.handle_at(e.position())
        if i >= 0:
            self.c.pick_color(i)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and len(self.c.stops) > 2:
            self.c.stops.pop(self.selected)
            self.select(max(0, self.selected - 1))
            self.edited.emit()
        elif e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) and self.c.stops:
            step = 0.01 * (10 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1)
            s = self.c.stops[self.selected]
            s["pos"] = round(max(0.0, min(1.0, s["pos"] + (step if e.key() == Qt.Key.Key_Right else -step))), 4)
            self.edited.emit()
        else:
            super().keyPressEvent(e)

    def select(self, i):
        self.selected = max(0, min(i, len(self.c.stops) - 1))
        self.selected_changed.emit(self.selected)
        self.update()


class GradientPreview(QWidget):
    def __init__(self, creator, t):
        super().__init__()
        self.c, self.t = creator, t
        self.setMinimumHeight(260)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        checker(p, r, 12)
        pv = self.c.preview
        kind, angle, spread = pv.get("type", "linéaire"), float(pv.get("angle", 0.0)), pv.get("repeat", "aucune")
        center = r.center()
        radius = min(r.width(), r.height()) / 2 * float(pv.get("scale", 1.0))
        if kind == "radial":
            g = QRadialGradient(center, radius)
        elif kind == "conique":
            g = QConicalGradient(center, -angle)
        else:
            a = math.radians(angle)
            half = QPointF(math.cos(a), math.sin(a)) * (radius if spread != "aucune" else max(r.width(), r.height()) / 2)
            g = QLinearGradient(center - half, center + half)
        g.setSpread({"répéter": QGradient.Spread.RepeatSpread, "miroir": QGradient.Spread.ReflectSpread}.get(spread, QGradient.Spread.PadSpread))
        for t, col in qt_stops(self.c.stops, self.c.interpolation, 64):
            g.setColorAt(t, col)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, 10, 10)
        p.end()


class GradientCreator(QObject):
    changed = Signal()
    default_name = "Nouveau dégradé"

    def __init__(self, host: dict):
        super().__init__()
        self.t = theme(host)
        self.stops = [{"pos": p, "hex": h, "alpha": 1.0} for p, h in PRESETS["Nuit stellaire"]]
        self.interpolation = INTERPOLATIONS[0]
        self.preview = {"type": "linéaire", "angle": 0.0, "repeat": "aucune", "scale": 1.0}
        self.history = History(self.snapshot, self._apply)
        self._edit = None
        self._test = None
        self._sync = False

    # ── contrat ──
    def snapshot(self):
        return {"stops": sorted((dict(s) for s in self.stops), key=lambda s: s["pos"]),
                "interpolation": self.interpolation, "preview": dict(self.preview)}

    def load(self, data):
        self._apply(data or {})
        self.history.reset()

    def _apply(self, data):
        stops = data.get("stops") if isinstance(data, dict) else None
        if isinstance(stops, list) and stops:
            self.stops = [{"pos": float(s.get("pos", 0)), "hex": QColor(s.get("hex", "#000")).name().upper(),
                           "alpha": float(s.get("alpha", 1.0)), **({"mid": float(s["mid"])} if "mid" in s else {})}
                          for s in stops if isinstance(s, dict)]
        if isinstance(data, dict):
            self.interpolation = data.get("interpolation", self.interpolation)
            self.preview.update(data.get("preview") or {})
        self._refresh()

    def validate(self):
        issues = []
        if len(self.stops) < 2:
            issues.append(("error", "Un dégradé doit avoir au moins 2 arrêts de couleur"))
        positions = [round(s["pos"], 3) for s in self.stops]
        if len(set(positions)) != len(positions):
            issues.append(("warning", "Deux arrêts sont à la même position (transition brutale)"))
        return issues

    def resource_payload(self):
        return {"gradient": self.snapshot(),
                "sampled": [QColor.fromRgbF(*[max(0, min(1, v)) for v in sample(self.stops, i / 15, self.interpolation)]).name(QColor.NameFormat.HexArgb)
                            for i in range(16)]}

    def library_export(self, name: str):
        """(type, contenu, apps) pour la bibliothèque centrale : format dégradé
        commun (position/couleur, lu par Nebula) + le document complet du module."""
        stops = [{"position": round(float(s["pos"]), 4),
                  "color": s["hex"] if float(s.get("alpha", 1.0)) >= 0.999
                  else s["hex"] + f"{round(float(s.get('alpha', 1.0)) * 255):02X}",
                  "alpha": float(s.get("alpha", 1.0))}
                 for s in sorted(self.stops, key=lambda s: s["pos"])]
        payload = {"format": "CreativeSystemGradient", "version": 2, "name": name, "stops": stops,
                   "interpolation": self.interpolation, "stellardust": self.snapshot()}
        return "gradients", payload, ("nebula", "stardust", "atlas", "cosmos")

    def undo(self):
        if self.history.undo():
            self.changed.emit()

    def redo(self):
        if self.history.redo():
            self.changed.emit()

    def _commit(self):
        self.stops.sort(key=lambda s: s["pos"])
        if self._edit is not None:
            sel = self.bar.selected
            self.bar.selected = min(sel, len(self.stops) - 1)
        if self.history.commit():
            self.changed.emit()
        self._refresh()

    # ── interface ──
    def edit_widget(self):
        if self._edit is not None:
            return self._edit
        t = self.t
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("Clic sur la barre : ajouter un arrêt · glisser : déplacer · tirer vers le bas : retirer · "
                      "double-clic : couleur · ← → : ajuster (Maj = ×10)")
        hint.setStyleSheet(f"color:{t['muted']}; font-size:11px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.bar = GradientBar(self, t)
        self.bar.selected_changed.connect(self._on_select)
        self.bar.edited.connect(self._commit)
        self.bar.live.connect(self._live)
        lay.addWidget(self.bar)
        row = QHBoxLayout()
        form = QFormLayout()
        self.color_btn = QPushButton("Couleur…")
        self.color_btn.clicked.connect(lambda: self.pick_color(self.bar.selected))
        form.addRow("Couleur", self.color_btn)
        self.pos_spin = QDoubleSpinBox()
        self.pos_spin.setRange(0, 100)
        self.pos_spin.setSuffix(" %")
        self.pos_spin.setDecimals(1)
        self.pos_spin.valueChanged.connect(lambda v: self._set_stop("pos", round(v / 100, 4)))
        form.addRow("Position", self.pos_spin)
        self.alpha = QSlider(Qt.Orientation.Horizontal)
        self.alpha.setRange(0, 100)
        self.alpha.sliderReleased.connect(lambda: self._set_stop("alpha", self.alpha.value() / 100))
        self.alpha.valueChanged.connect(lambda v: self._set_stop("alpha", v / 100, commit=not self.alpha.isSliderDown()))
        form.addRow("Opacité", self.alpha)
        self.mid = QSlider(Qt.Orientation.Horizontal)
        self.mid.setRange(5, 95)
        self.mid.setToolTip("Point milieu de la transition vers l'arrêt suivant")
        self.mid.sliderReleased.connect(lambda: self._set_stop("mid", self.mid.value() / 100))
        self.mid.valueChanged.connect(lambda v: self._set_stop("mid", v / 100, commit=not self.mid.isSliderDown()))
        form.addRow("Transition", self.mid)
        row.addLayout(form, 1)
        form2 = QFormLayout()
        self.interp = QComboBox()
        self.interp.addItems(INTERPOLATIONS)
        self.interp.setToolTip("OKLab donne des transitions sans zone grise/boueuse")
        self.interp.currentTextChanged.connect(self._set_interp)
        form2.addRow("Interpolation", self.interp)
        self.preset = QComboBox()
        self.preset.addItem("— Charger un préréglage —")
        self.preset.addItems(list(PRESETS))
        self.preset.activated.connect(self._load_preset)
        form2.addRow("Préréglages", self.preset)
        btns = QHBoxLayout()
        for text, fn in (("Inverser", self._reverse), ("Répartir", self._distribute), ("Symétriser", self._mirror)):
            b = QPushButton(text)
            b.setObjectName("secondary")
            b.clicked.connect(fn)
            btns.addWidget(b)
        form2.addRow(btns)
        row.addLayout(form2, 1)
        lay.addLayout(row)
        self.inline_preview = GradientPreview(self, t)
        self.inline_preview.setMinimumHeight(140)
        lay.addWidget(self.inline_preview, 1)
        self._edit = root
        self._refresh()
        self.history.reset()
        return root

    def test_widget(self):
        if self._test is not None:
            return self._test
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        kind = QComboBox()
        kind.addItems(["linéaire", "radial", "conique"])
        kind.setCurrentText(self.preview.get("type", "linéaire"))
        rep = QComboBox()
        rep.addItems(["aucune", "répéter", "miroir"])
        rep.setCurrentText(self.preview.get("repeat", "aucune"))
        angle = QSlider(Qt.Orientation.Horizontal)
        angle.setRange(-180, 180)
        angle.setValue(int(self.preview.get("angle", 0)))
        scale = QSlider(Qt.Orientation.Horizontal)
        scale.setRange(10, 200)
        scale.setValue(int(float(self.preview.get("scale", 1.0)) * 100))
        for text, w in (("Type", kind), ("Répétition", rep), ("Angle", angle), ("Échelle", scale)):
            bar.addWidget(QLabel(text))
            bar.addWidget(w, 1 if isinstance(w, QSlider) else 0)
        lay.addLayout(bar)
        self.test_preview = GradientPreview(self, self.t)
        lay.addWidget(self.test_preview, 1)

        def upd(key, value):
            self.preview[key] = value
            self.test_preview.update()
            if self._edit is not None:
                self.inline_preview.update()
        kind.currentTextChanged.connect(lambda v: (upd("type", v), self._commit()))
        rep.currentTextChanged.connect(lambda v: (upd("repeat", v), self._commit()))
        angle.valueChanged.connect(lambda v: upd("angle", float(v)))
        angle.sliderReleased.connect(self._commit)
        scale.valueChanged.connect(lambda v: upd("scale", v / 100))
        scale.sliderReleased.connect(self._commit)
        self._test = root
        return root

    # ── actions ──
    def _refresh(self):
        if self._edit is not None:
            self.bar.update()
            self.inline_preview.update()
            self._sync = True
            self.interp.setCurrentText(self.interpolation)
            self._sync = False
            self._on_select(self.bar.selected)
        if self._test is not None:
            self.test_preview.update()

    def _live(self):
        if self._edit is not None:
            self.inline_preview.update()
            self._on_select(self.bar.selected)
        if self._test is not None:
            self.test_preview.update()

    def _on_select(self, i):
        if self._edit is None or not (0 <= i < len(self.stops)):
            return
        s = self.stops[i]
        self._sync = True
        self.pos_spin.setValue(s["pos"] * 100)
        self.alpha.setValue(int(s.get("alpha", 1.0) * 100))
        self.mid.setValue(int(s.get("mid", 0.5) * 100))
        self.mid.setEnabled(i < len(self.stops) - 1)
        self.color_btn.setText(s["hex"])
        self.color_btn.setStyleSheet(f"background:{s['hex']}; color:{'#000' if QColor(s['hex']).lightnessF() > 0.55 else '#FFF'};")
        self._sync = False

    def _set_stop(self, key, value, commit=True):
        if self._sync or self._edit is None:
            return
        i = self.bar.selected
        if 0 <= i < len(self.stops):
            self.stops[i][key] = value
            if commit:
                self._commit()
            else:
                self._live()

    def _set_interp(self, value):
        if not self._sync:
            self.interpolation = value
            self._commit()

    def pick_color(self, i):
        if not (0 <= i < len(self.stops)):
            return
        s = self.stops[i]
        start = QColor(s["hex"])
        start.setAlphaF(s.get("alpha", 1.0))
        c = QColorDialog.getColor(start, self._edit, "Couleur de l'arrêt", QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if c.isValid():
            s["hex"] = c.name().upper()
            s["alpha"] = round(c.alphaF(), 3)
            self._commit()

    def _load_preset(self, index):
        if index <= 0:
            return
        name = self.preset.itemText(index)
        self.stops = [{"pos": p, "hex": QColor(h).name().upper(), "alpha": 1.0} for p, h in PRESETS[name]]
        self.preset.setCurrentIndex(0)
        self.bar.selected = 0
        self._commit()

    def _reverse(self):
        for s in self.stops:
            s["pos"] = round(1.0 - s["pos"], 4)
            if "mid" in s:
                s["mid"] = round(1.0 - s["mid"], 4)
        self._commit()

    def _distribute(self):
        self.stops.sort(key=lambda s: s["pos"])
        n = len(self.stops)
        for i, s in enumerate(self.stops):
            s["pos"] = round(i / max(1, n - 1), 4)
        self._commit()

    def _mirror(self):
        half = [dict(s, pos=round(s["pos"] / 2, 4)) for s in sorted(self.stops, key=lambda s: s["pos"])]
        mirrored = [dict(s, pos=round(1.0 - s["pos"], 4)) for s in half if s["pos"] < 0.5]
        self.stops = half + mirrored
        self._commit()
