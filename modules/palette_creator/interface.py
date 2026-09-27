"""Interface du module Palette Creator (protocole existence.creator.v1).

Possédée par Existence ; chargée par l'univers hôte (StarDust).
"""

from __future__ import annotations

import colorsys

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QColorDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QPushButton, QScrollArea, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from modules.creator_ui import History, contrast_ratio, hex_to_rgb, median_cut, relative_luminance, rgb_to_hex, theme

CELL, GAP = 44, 6


def create_creator(host: dict | None = None):
    return PaletteCreator(host or {})


class SwatchGrid(QWidget):
    """Grille de nuanciers : clic = sélection, glisser = réordonner,
    double-clic = modifier, Suppr = supprimer, clic droit = actions."""
    selected_changed = Signal(int)
    edited = Signal()           # modification terminée (pour l'historique)
    request_edit = Signal(int)

    def __init__(self, t, parent=None):
        super().__init__(parent)
        self.t = t
        self.colors: list[dict] = []
        self.columns = 8
        self.selected = -1
        self._press = None
        self._drag = None
        self._drop = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    def sizeHint(self):
        from PySide6.QtCore import QSize
        rows = max(1, (len(self.colors) + self.columns) // self.columns)
        return QSize(self.columns * (CELL + GAP) + GAP, rows * (CELL + GAP) + GAP + 20)

    def minimumSizeHint(self):
        return self.sizeHint()

    def cell_rect(self, i):
        r, c = divmod(i, self.columns)
        return QRectF(GAP + c * (CELL + GAP), GAP + r * (CELL + GAP), CELL, CELL)

    def index_at(self, pos, allow_end=False):
        c = int((pos.x() - GAP / 2) // (CELL + GAP))
        r = int((pos.y() - GAP / 2) // (CELL + GAP))
        if c < 0 or c >= self.columns or r < 0:
            return -1
        i = r * self.columns + c
        limit = len(self.colors) + (1 if allow_end else 0)
        return i if i < limit else (len(self.colors) if allow_end else -1)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, entry in enumerate(self.colors):
            rect = self.cell_rect(i)
            if self._drag == i:
                p.setOpacity(0.3)
            p.setPen(QPen(QColor("#FFFFFF") if i == self.selected else QColor(self.t["line"]), 2.5 if i == self.selected else 1))
            p.setBrush(QColor(entry["hex"]))
            p.drawRoundedRect(rect, 8, 8)
            p.setOpacity(1.0)
        if self._drag is not None and self._drop is not None:
            rect = self.cell_rect(self._drop)
            p.setPen(QPen(QColor(self.t["accent"]), 3))
            p.drawLine(QPointF(rect.left() - GAP / 2, rect.top()), QPointF(rect.left() - GAP / 2, rect.bottom()))
        # case « + »
        plus = self.cell_rect(len(self.colors))
        p.setPen(QPen(QColor(self.t["dim"]), 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(plus, 8, 8)
        p.setPen(QColor(self.t["muted"]))
        p.setFont(QFont("Inter", 16))
        p.drawText(plus, Qt.AlignmentFlag.AlignCenter, "+")
        if not self.colors:
            p.setFont(QFont("Inter", 10))
            p.drawText(QRectF(plus.right() + 12, plus.top(), 400, CELL), Qt.AlignmentFlag.AlignVCenter,
                       "Clique « + » ou utilise Générer / Importer une image")
        p.end()

    def mousePressEvent(self, e):
        self.setFocus()
        i = self.index_at(e.position())
        if e.button() == Qt.MouseButton.LeftButton:
            if i == -1 and self.cell_rect(len(self.colors)).contains(e.position()):
                self.request_edit.emit(-1)
                return
            self.select(i)
            self._press = (e.position(), i) if i >= 0 else None

    def mouseMoveEvent(self, e):
        if self._press and (e.position() - self._press[0]).manhattanLength() > 6:
            self._drag = self._press[1]
            self._drop = self.index_at(e.position(), allow_end=True)
            self.update()

    def mouseReleaseEvent(self, e):
        if self._drag is not None and self._drop is not None and self._drop not in (self._drag, self._drag + 1):
            entry = self.colors.pop(self._drag)
            target = self._drop - (1 if self._drop > self._drag else 0)
            self.colors.insert(target, entry)
            self.select(target)
            self.edited.emit()
        self._press = self._drag = self._drop = None
        self.update()

    def mouseDoubleClickEvent(self, e):
        i = self.index_at(e.position())
        if i >= 0:
            self.request_edit.emit(i)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and 0 <= self.selected < len(self.colors):
            self.colors.pop(self.selected)
            self.select(min(self.selected, len(self.colors) - 1))
            self.edited.emit()
        elif e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right) and self.colors:
            self.select(max(0, min(len(self.colors) - 1, self.selected + (1 if e.key() == Qt.Key.Key_Right else -1))))
        else:
            super().keyPressEvent(e)

    def select(self, i):
        self.selected = i
        self.selected_changed.emit(i)
        self.update()

    def set_colors(self, colors, columns):
        self.colors, self.columns = colors, max(1, columns)
        self.selected = min(self.selected, len(colors) - 1)
        self.updateGeometry()
        self.update()


class PalettePreview(QWidget):
    """Aperçu : illustration, valeurs et contrastes."""

    def __init__(self, creator, t):
        super().__init__()
        self.creator, self.t = creator, t
        self.setMinimumHeight(320)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(self.t["panel2"]))
        colors = [QColor(c["hex"]) for c in self.creator.colors]
        if not colors:
            p.setPen(QColor(self.t["muted"]))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Palette vide")
            return
        w, h = self.width(), self.height()
        # 1. illustration : fond + formes superposées
        area = QRectF(16, 16, w * 0.55 - 24, h - 32)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colors[0])
        p.drawRoundedRect(area, 12, 12)
        n = len(colors)
        for i, c in enumerate(colors[1:], start=1):
            f = i / max(1, n - 1)
            r = area.height() * (0.45 - 0.25 * f)
            cx = area.left() + area.width() * (0.2 + 0.6 * ((i * 0.37) % 1.0))
            cy = area.top() + area.height() * (0.25 + 0.5 * ((i * 0.61) % 1.0))
            p.setBrush(c)
            p.drawEllipse(QPointF(cx, cy), r, r)
        # 2. bande de valeurs (luminance)
        x0 = w * 0.55 + 8
        p.setPen(QColor(self.t["muted"]))
        p.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        p.drawText(QPointF(x0, 28), "VALEURS (luminance)")
        bw = (w - x0 - 16) / n
        for i, c in enumerate(colors):
            lum = relative_luminance((c.redF(), c.greenF(), c.blueF())) ** (1 / 2.2)
            g = QColor.fromRgbF(lum, lum, lum)
            p.fillRect(QRectF(x0 + i * bw, 36, bw - 2, 26), c)
            p.fillRect(QRectF(x0 + i * bw, 64, bw - 2, 26), g)
        # 3. contrastes les plus forts / faibles
        p.setPen(QColor(self.t["muted"]))
        p.drawText(QPointF(x0, 116), "CONTRASTES (WCAG)")
        pairs = []
        rgb = [(c.redF(), c.greenF(), c.blueF()) for c in colors]
        for a in range(n):
            for b in range(a + 1, n):
                pairs.append((contrast_ratio(rgb[a], rgb[b]), a, b))
        pairs.sort(reverse=True)
        y = 126
        for ratio, a, b in pairs[:6]:
            p.fillRect(QRectF(x0, y, 90, 26), colors[a])
            p.setPen(colors[b])
            p.setFont(QFont("Inter", 10, QFont.Weight.Bold))
            p.drawText(QRectF(x0, y, 90, 26), Qt.AlignmentFlag.AlignCenter, "Texte")
            p.setPen(QColor(self.t["ok"] if ratio >= 4.5 else self.t["warn"] if ratio >= 3 else self.t["err"]))
            p.setFont(QFont("Inter", 10))
            grade = "AA" if ratio >= 4.5 else "AA large" if ratio >= 3 else "faible"
            p.drawText(QPointF(x0 + 100, y + 18), f"{ratio:4.1f}:1  {grade}")
            y += 32
        p.end()


class PaletteCreator(QObject):
    changed = Signal()
    default_name = "Nouvelle palette"

    def __init__(self, host: dict):
        super().__init__()
        self.t = theme(host)
        self.colors: list[dict] = [{"hex": h, "name": ""} for h in ("#1B1F3B", "#3E4A89", "#8C9EFF", "#F5C56B", "#FF7A8A")]
        self.columns = 8
        self.history = History(self.snapshot, self._apply)
        self._edit = None
        self._test = None
        self._syncing = False

    # ── contrat ──
    def snapshot(self) -> dict:
        return {"colors": [dict(c) for c in self.colors], "columns": self.columns}

    def load(self, data: dict):
        self._apply(data or {})
        self.history.reset()

    def _apply(self, data):
        colors = data.get("colors") if isinstance(data, dict) else None
        if isinstance(colors, list):
            self.colors = [{"hex": QColor(c.get("hex", "#000000")).name().upper(), "name": str(c.get("name", ""))}
                           for c in colors if isinstance(c, dict)]
        self.columns = int(data.get("columns", self.columns)) if isinstance(data, dict) else self.columns
        self._refresh()

    def validate(self):
        issues = []
        if len(self.colors) < 2:
            issues.append(("error", "Une palette doit contenir au moins 2 couleurs"))
        seen = set()
        for c in self.colors:
            if c["hex"] in seen:
                issues.append(("warning", f"Couleur en double : {c['hex']}"))
            seen.add(c["hex"])
        return issues

    def resource_payload(self):
        return {"palette": self.snapshot(), "count": len(self.colors),
                "hex": [c["hex"] for c in self.colors]}

    def library_export(self, name: str):
        """(type, contenu, apps) pour la bibliothèque centrale : format palette
        commun (lu tel quel par Nebula) + le document complet du module."""
        payload = {"format": "CreativeSystemPalette", "version": 1, "name": name,
                   "colors": [c["hex"] for c in self.colors],
                   "names": [c["name"] for c in self.colors],
                   "stellardust": self.snapshot()}
        return "palettes", payload, ("nebula", "stardust", "atlas", "cosmos")

    def undo(self):
        if self.history.undo():
            self.changed.emit()

    def redo(self):
        if self.history.redo():
            self.changed.emit()

    def _commit(self):
        if self.history.commit():
            self._refresh()
            self.changed.emit()

    # ── interface ──
    def edit_widget(self):
        if self._edit is not None:
            return self._edit
        t = self.t
        root = QWidget()
        lay = QHBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        left = QVBoxLayout()
        bar = QHBoxLayout()

        def btn(text, tip, fn):
            b = QPushButton(text)
            b.setObjectName("secondary")
            b.setToolTip(tip)
            b.clicked.connect(fn)
            bar.addWidget(b)
            return b
        btn("+ Couleur", "Ajouter une couleur", lambda: self._edit_color(-1))
        btn("Dupliquer", "Dupliquer la couleur sélectionnée", self._duplicate)
        gen = QToolButton()
        gen.setText("Générer ▾")
        gen.setToolTip("Harmonies à partir de la couleur sélectionnée")
        gen.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(gen)
        for name in ("Complémentaire", "Triade", "Analogue", "Tétrade", "Complémentaires adjacentes",
                     "Nuances (plus sombre)", "Teintes (plus clair)", "Monochrome"):
            menu.addAction(name, lambda n=name: self._harmony(n))
        gen.setMenu(menu)
        bar.addWidget(gen)
        sort = QToolButton()
        sort.setText("Trier ▾")
        sort.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        smenu = QMenu(sort)
        for name in ("Teinte", "Luminosité", "Saturation", "Inverser l'ordre"):
            smenu.addAction(name, lambda n=name: self._sort(n))
        sort.setMenu(smenu)
        bar.addWidget(sort)
        btn("Importer une image…", "Extraire les couleurs dominantes d'une image", self._import_image)
        bar.addStretch()
        bar.addWidget(QLabel("Colonnes"))
        self.col_spin = QSpinBox()
        self.col_spin.setRange(1, 24)
        self.col_spin.setValue(self.columns)
        self.col_spin.valueChanged.connect(self._set_columns)
        bar.addWidget(self.col_spin)
        left.addLayout(bar)
        hint = QLabel("Glisser pour réordonner · double-clic pour modifier · Suppr pour retirer · ← → pour naviguer")
        hint.setStyleSheet(f"color:{t['muted']}; font-size:11px;")
        left.addWidget(hint)
        self.grid = SwatchGrid(t)
        self.grid.selected_changed.connect(self._on_select)
        self.grid.edited.connect(self._commit)
        self.grid.request_edit.connect(self._edit_color)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._grid_menu)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.grid)
        left.addWidget(scroll, 1)
        lay.addLayout(left, 3)

        side = QVBoxLayout()
        side.addWidget(self._title("COULEUR SÉLECTIONNÉE"))
        self.picker = QColorDialog()
        self.picker.setOptions(QColorDialog.ColorDialogOption.NoButtons | QColorDialog.ColorDialogOption.DontUseNativeDialog)
        self.picker.setWindowFlags(Qt.WindowType.Widget)
        self.picker.currentColorChanged.connect(self._picker_changed)
        side.addWidget(self.picker)
        row = QHBoxLayout()
        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("#RRGGBB")
        self.hex_edit.editingFinished.connect(self._hex_changed)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nom (facultatif)")
        self.name_edit.editingFinished.connect(self._name_changed)
        row.addWidget(self.hex_edit)
        row.addWidget(self.name_edit, 1)
        side.addLayout(row)
        self.info = QLabel("")
        self.info.setStyleSheet(f"color:{t['muted']}; font-size:11px;")
        side.addWidget(self.info)
        side.addStretch()
        lay.addLayout(side, 2)
        self._edit = root
        self._refresh()
        self.history.reset()
        return root

    def test_widget(self):
        if self._test is None:
            self._test = PalettePreview(self, self.t)
        return self._test

    # ── actions ──
    def _title(self, text):
        lab = QLabel(text)
        lab.setStyleSheet(f"color:{self.t['muted']}; font-size:10px; font-weight:700; letter-spacing:1px;")
        return lab

    def _refresh(self):
        if self._edit is not None:
            self.grid.set_colors(self.colors, self.columns)
            self.col_spin.blockSignals(True)
            self.col_spin.setValue(self.columns)
            self.col_spin.blockSignals(False)
            self._on_select(self.grid.selected)
        if self._test is not None:
            self._test.update()

    def _current(self):
        i = self.grid.selected if self._edit is not None else -1
        return i if 0 <= i < len(self.colors) else -1

    def _on_select(self, i):
        if self._edit is None:
            return
        self._syncing = True
        valid = 0 <= i < len(self.colors)
        for w in (self.picker, self.hex_edit, self.name_edit):
            w.setEnabled(valid)
        if valid:
            c = self.colors[i]
            self.picker.setCurrentColor(QColor(c["hex"]))
            self.hex_edit.setText(c["hex"])
            self.name_edit.setText(c["name"])
            qc = QColor(c["hex"])
            h, s, v, _ = qc.getHsvF()
            self.info.setText(f"#{i + 1} · TSV {max(0, h) * 360:.0f}° {s:.0%} {v:.0%} · "
                              f"RGB {qc.red()} {qc.green()} {qc.blue()}")
        else:
            self.info.setText("Sélectionne une couleur dans la grille")
        self._syncing = False

    def _picker_changed(self, color):
        i = self._current()
        if self._syncing or i < 0:
            return
        self.colors[i]["hex"] = color.name().upper()
        self.hex_edit.setText(self.colors[i]["hex"])
        self.grid.update()
        if self._test is not None:
            self._test.update()
        self._commit()

    def _hex_changed(self):
        i = self._current()
        c = QColor(self.hex_edit.text().strip())
        if i >= 0 and c.isValid():
            self.colors[i]["hex"] = c.name().upper()
            self._commit()

    def _name_changed(self):
        i = self._current()
        if i >= 0:
            self.colors[i]["name"] = self.name_edit.text().strip()
            self._commit()

    def _edit_color(self, i):
        start = QColor(self.colors[i]["hex"]) if 0 <= i < len(self.colors) else QColor(self.colors[-1]["hex"] if self.colors else "#8C9EFF")
        c = QColorDialog.getColor(start, self._edit, "Couleur")
        if not c.isValid():
            return
        if i < 0:
            self.colors.append({"hex": c.name().upper(), "name": ""})
            i = len(self.colors) - 1
        else:
            self.colors[i]["hex"] = c.name().upper()
        self.grid.selected = i
        self._commit()

    def _duplicate(self):
        i = self._current()
        if i >= 0:
            self.colors.insert(i + 1, dict(self.colors[i]))
            self.grid.selected = i + 1
            self._commit()

    def _set_columns(self, n):
        self.columns = n
        self._commit()

    def _grid_menu(self, pos):
        i = self.grid.index_at(pos)
        if i < 0:
            return
        self.grid.select(i)
        menu = QMenu(self._edit)
        menu.addAction("Modifier…", lambda: self._edit_color(i))
        menu.addAction("Dupliquer", self._duplicate)
        menu.addAction("Copier le code hex", lambda: QGuiApplication.clipboard().setText(self.colors[i]["hex"]))
        menu.addSeparator()
        menu.addAction("Supprimer", lambda: (self.colors.pop(i), self._commit()))
        menu.exec(self.grid.mapToGlobal(pos))

    def _harmony(self, kind):
        i = self._current()
        base = QColor(self.colors[i]["hex"] if i >= 0 else "#8C9EFF")
        h, s, v, _ = base.getHsvF()
        h = max(0.0, h)
        new = []
        rot = {"Complémentaire": [0.5], "Triade": [1 / 3, 2 / 3], "Analogue": [-1 / 12, 1 / 12, 1 / 6],
               "Tétrade": [0.25, 0.5, 0.75], "Complémentaires adjacentes": [5 / 12, 7 / 12]}
        if kind in rot:
            new = [QColor.fromHsvF((h + d) % 1.0, s, v) for d in rot[kind]]
        elif kind.startswith("Nuances"):
            new = [QColor.fromHsvF(h, s, v * f) for f in (0.8, 0.6, 0.4, 0.2)]
        elif kind.startswith("Teintes"):
            new = [QColor.fromHsvF(h, s * f, v + (1 - v) * (1 - f)) for f in (0.75, 0.5, 0.3, 0.12)]
        else:
            new = [QColor.fromHsvF(h, s * a, v * b) for a, b in ((1, .45), (1, .7), (.7, 1), (.35, 1))]
        insert = (i + 1) if i >= 0 else len(self.colors)
        for k, c in enumerate(new):
            self.colors.insert(insert + k, {"hex": c.name().upper(), "name": ""})
        self._commit()

    def _sort(self, kind):
        def hsv(c):
            return colorsys.rgb_to_hsv(*hex_to_rgb(c["hex"]))
        if kind == "Teinte":
            self.colors.sort(key=lambda c: hsv(c)[0])
        elif kind == "Luminosité":
            self.colors.sort(key=lambda c: relative_luminance(hex_to_rgb(c["hex"])))
        elif kind == "Saturation":
            self.colors.sort(key=lambda c: hsv(c)[1])
        else:
            self.colors.reverse()
        self._commit()

    def _import_image(self):
        path, _ = QFileDialog.getOpenFileName(self._edit, "Extraire les couleurs d'une image", "",
                                              "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        image = QImage(path) if path else QImage()
        if image.isNull():
            return
        small = image.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        pixels = []
        for y in range(small.height()):
            for x in range(small.width()):
                c = small.pixelColor(x, y)
                if c.alpha() > 128:
                    pixels.append((c.redF(), c.greenF(), c.blueF()))
        for rgb in median_cut(pixels, 8):
            self.colors.append({"hex": rgb_to_hex(rgb), "name": ""})
        self._commit()
