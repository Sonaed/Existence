#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║           EXISTENCE  ·  Creative Universe Hub           ║
║         ArchLinux / Garuda  ·  Space Theme  v2.0        ║
╠══════════════════════════════════════════════════════════╣
║  Nebula · Cosmos · outils en orbite                     ║
╚══════════════════════════════════════════════════════════╝
  Dépendances : python-pyside6  (pacman -S python-pyside6)
  Lancement   : python galaxy_hub.py
"""

import sys
import json
import os
import subprocess
import math
import random
import uuid
from pathlib import Path
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QScrollArea, QFrame,
    QDialog, QFormLayout, QFileDialog, QMessageBox,
    QComboBox, QTextEdit, QSizePolicy, QGraphicsDropShadowEffect,
    QGridLayout, QSpacerItem, QToolButton, QMenu, QColorDialog,
    QStyleFactory,
)
from PySide6.QtCore import (
    Qt, QSize, QTimer, Signal, QRectF, QPointF, QPoint
)
from PySide6.QtGui import (
    QFont, QPixmap, QPainter, QColor, QLinearGradient,
    QPalette, QPen, QRadialGradient, QBrush, QCursor,
    QAction,
)


# ══════════════════════════════════════════════════════════════
#  CONFIG & PALETTE
# ══════════════════════════════════════════════════════════════

APP_VERSION  = "2.0.0"
CONFIG_DIR   = Path.home() / ".config" / "existence"
CONFIG_FILE  = CONFIG_DIR / "apps.json"
LEGACY_CONFIG_FILE = Path.home() / ".config" / "galaxy-hub" / "apps.json"

# Galaxy / Space dark palette
C: Dict[str, str] = {
    "bg":        "#080818",
    "bg2":       "#0C0C20",
    "surface":   "#111128",
    "surface_h": "#181838",
    "border":    "#1E1E45",
    "border_h":  "#3A3A80",
    "text":      "#E8E8FF",
    "text2":     "#9090CC",
    "text3":     "#404068",
    "purple":    "#7C3AED",
    "purple_l":  "#A855F7",
    "cyan":      "#06B6D4",
    "pink":      "#D946EF",
    "green":     "#10B981",
    "orange":    "#F97316",
    "red":       "#EF4444",
    "yellow":    "#F59E0B",
    "blue":      "#3B82F6",
}

CATEGORIES = ["Toutes", "Création", "Productivité", "Développement", "Utilitaires", "Autres"]

DEFAULT_APPS: List[Dict] = [
    {
        "id":           "nebula",
        "name":         "Nebula",
        "description":  "Un univers de création visuelle — là où la matière devient image.",
        "category":     "Création",
        "icon_emoji":   "✦",
        "icon_path":    "",
        "accent_color": "#F062D5",
        "version":      "0.1.0",
        "installed":    False,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "manual",
        "install_script": "",
        "git_url":      "",
        "tags":         ["dessin", "art", "création", "univers"],
    },
    {
        "id":           "cosmos",
        "name":         "Cosmos",
        "description":  "L'univers où les idées, les notes et les constellations se rencontrent.",
        "category":     "Productivité",
        "icon_emoji":   "🌌",
        "icon_path":    "",
        "accent_color": "#8B5CF6",
        "version":      "0.1.0",
        "installed":    False,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "manual",
        "install_script": "",
        "git_url":      "",
        "tags":         ["notes", "knowledge", "productivité", "univers"],
    },
    {
        "id":           "webready",
        "name":         "WebReady",
        "description":  "Prépare les images de Nebula pour traverser le web.",
        "category":     "Utilitaires",
        "icon_emoji":   "🖼️",
        "icon_path":    "",
        "accent_color": "#06B6D4",
        "version":      "2.0.0",
        "installed":    False,
        "exec_path":    "",
        "exec_args":    [],
        "install_type": "manual",
        "install_script": "",
        "git_url":      "",
        "tags":         ["images", "webp", "optimisation", "web", "nebula"],
        "orbit_of":     "nebula",
    },
    {
        "id": "singularity", "name": "Singularity",
        "description": "Un laboratoire d'outils et de transformations pour Nebula.",
        "category": "Utilitaires", "icon_emoji": "◉", "icon_path": "",
        "accent_color": "#FFB45B", "version": "0.1.0", "installed": False,
        "exec_path": "", "exec_args": [], "install_type": "manual",
        "install_script": "", "git_url": "", "tags": ["outil", "nebula", "création"],
        "orbit_of": "nebula",
    },
]


# ══════════════════════════════════════════════════════════════
#  CONFIG MANAGER
# ══════════════════════════════════════════════════════════════

class ConfigManager:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            # Récupère le catalogue existant au premier lancement d'Existence.
            if LEGACY_CONFIG_FILE.exists():
                try:
                    with open(LEGACY_CONFIG_FILE, encoding="utf-8") as f:
                        self.save(json.load(f))
                except Exception:
                    self.save(DEFAULT_APPS)
            else:
                self.save(DEFAULT_APPS)

    def load(self) -> List[Dict]:
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                apps = json.load(f)
                # Existence est la continuité de Galaxy Hub : Atlas devient Nebula
                # sans perdre le chemin de lancement déjà configuré.
                for app in apps:
                    if app.get("id") == "atlas" or app.get("name") == "Atlas":
                        app.update({"id": "nebula", "name": "Nebula", "icon_emoji": "✦",
                                    "accent_color": "#F062D5", "orbit_of": ""})
                    elif app.get("id") == "webready":
                        app.setdefault("orbit_of", "nebula")
                # Les nouveaux outils conceptuels apparaissent sans toucher aux apps
                # personnelles déjà présentes dans le catalogue.
                if not any(app.get("id") == "singularity" for app in apps):
                    apps.append(dict(next(a for a in DEFAULT_APPS if a["id"] == "singularity")))
                return apps
        except Exception:
            return [dict(a) for a in DEFAULT_APPS]

    def save(self, apps: List[Dict]) -> None:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════
#  STAR FIELD BACKGROUND
# ══════════════════════════════════════════════════════════════

class StarField(QWidget):
    """Fond étoilé animé avec nébuleuses."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._phase  = 0.0
        self._stars  = []
        self._nebulae = []
        self._generate()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)  # ~20 fps

    def _generate(self):
        rng = random.Random(1337)
        for _ in range(180):
            self._stars.append({
                "x":     rng.random(),
                "y":     rng.random(),
                "size":  rng.uniform(0.4, 2.4),
                "phase": rng.random() * math.pi * 2,
                "speed": rng.uniform(0.3, 1.6),
            })
        nebula_defs = [
            ("#7C3AED", 0.042), ("#06B6D4", 0.030), ("#D946EF", 0.026),
            ("#1D4ED8", 0.035), ("#7C3AED", 0.028), ("#0F766E", 0.024),
        ]
        for color, alpha in nebula_defs:
            self._nebulae.append({
                "x":     rng.uniform(0.05, 0.95),
                "y":     rng.uniform(0.05, 0.95),
                "rx":    rng.uniform(0.08, 0.24),
                "ry":    rng.uniform(0.06, 0.18),
                "color": color,
                "alpha": alpha,
            })

    def _tick(self):
        self._phase += 0.04
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Deep-space gradient
        grad = QLinearGradient(0, 0, w * 0.7, h)
        grad.setColorAt(0.0, QColor("#050512"))
        grad.setColorAt(0.4, QColor("#08081A"))
        grad.setColorAt(1.0, QColor("#060614"))
        p.fillRect(0, 0, w, h, grad)

        # ── Nebulae
        for n in self._nebulae:
            cx, cy = n["x"] * w, n["y"] * h
            rx, ry = n["rx"] * w, n["ry"] * h
            rg = QRadialGradient(QPointF(cx, cy), max(rx, ry))
            c0 = QColor(n["color"]); c0.setAlphaF(n["alpha"])
            c1 = QColor(n["color"]); c1.setAlphaF(n["alpha"] * 0.4)
            c2 = QColor(n["color"]); c2.setAlphaF(0.0)
            rg.setColorAt(0.0, c0)
            rg.setColorAt(0.5, c1)
            rg.setColorAt(1.0, c2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(rg))
            p.drawEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))

        # ── Stars
        for star in self._stars:
            b = 0.45 + 0.55 * math.sin(self._phase * star["speed"] + star["phase"])
            alpha = int(b * 220 + 35)
            rv = int(200 + b * 55)
            color = QColor(rv, rv, 255, alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            sx, sy = star["x"] * w, star["y"] * h
            size = star["size"] * (0.7 + 0.3 * b)
            p.drawEllipse(QRectF(sx - size / 2, sy - size / 2, size, size))
            if star["size"] > 1.5 and b > 0.7:
                glow = QColor(180, 180, 255, int(alpha * 0.12))
                p.setBrush(glow)
                p.drawEllipse(QRectF(sx - size * 2, sy - size * 2, size * 4, size * 4))

        p.end()


# ══════════════════════════════════════════════════════════════
#  APP ICON WIDGET
# ══════════════════════════════════════════════════════════════

class AppIconWidget(QLabel):
    """Cercle coloré avec emoji centré."""

    def __init__(self, emoji: str = "📦", color: str = "#7C3AED", size: int = 54, parent=None):
        super().__init__(parent)
        self.emoji  = emoji
        self.accent = QColor(color)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont(); f.setPointSize(size // 3)
        self.setFont(f)
        self.setText(emoji)

    def set_accent(self, color: str):
        self.accent = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bg = QColor(self.accent); bg.setAlphaF(0.14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawEllipse(2, 2, w - 4, h - 4)
        border = QColor(self.accent); border.setAlphaF(0.45)
        p.setPen(QPen(border, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(2, 2, w - 4, h - 4)
        p.end()
        super().paintEvent(event)


# ══════════════════════════════════════════════════════════════
#  APP CARD
# ══════════════════════════════════════════════════════════════

class AppCard(QFrame):
    """Carte d'application avec launch / configure / menu contextuel."""

    launch_requested   = Signal(dict)
    edit_requested     = Signal(dict)
    remove_requested   = Signal(str)
    install_requested  = Signal(dict)

    CARD_W = 260
    CARD_H = 200

    def __init__(self, app_data: dict, parent=None):
        super().__init__(parent)
        self.app_data = app_data
        self._hovered = False
        self._build_ui()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda _: self._show_menu())

    # ── helpers
    @staticmethod
    def _lighten(hex_c: str, amt: int = 22) -> str:
        c = QColor(hex_c); h, s, l, a = c.getHsl()
        return QColor.fromHsl(h, s, min(255, l + amt), a).name()

    @staticmethod
    def _darken(hex_c: str, amt: int = 22) -> str:
        c = QColor(hex_c); h, s, l, a = c.getHsl()
        return QColor.fromHsl(h, s, max(0, l - amt), a).name()

    def _build_ui(self):
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setObjectName("AppCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 14, 14)
        layout.setSpacing(6)

        # ── Header row
        hdr = QHBoxLayout(); hdr.setSpacing(12)

        accent = self.app_data.get("accent_color", C["purple"])
        self.icon_w = AppIconWidget(self.app_data.get("icon_emoji", "📦"), accent, 52)
        hdr.addWidget(self.icon_w)

        meta_col = QVBoxLayout(); meta_col.setSpacing(2)
        self.name_lbl = QLabel(self.app_data["name"])
        self.name_lbl.setFont(QFont("", 15, QFont.Weight.Bold))
        self.name_lbl.setStyleSheet(f"color:{C['text']};background:transparent;")
        meta_col.addWidget(self.name_lbl)

        meta_row = QHBoxLayout(); meta_row.setSpacing(8)
        ver_lbl = QLabel(f"v{self.app_data.get('version','0.1.0')}")
        ver_lbl.setStyleSheet(f"color:{C['text3']};background:transparent;font-size:10px;")
        meta_row.addWidget(ver_lbl)
        cat_lbl = QLabel(self.app_data.get("category", ""))
        cat_lbl.setStyleSheet(f"color:{accent};background:transparent;font-size:10px;font-weight:600;")
        meta_row.addWidget(cat_lbl)
        meta_row.addStretch()
        meta_col.addLayout(meta_row)
        hdr.addLayout(meta_col)
        hdr.addStretch()

        # ⋯ button
        self.menu_btn = QToolButton()
        self.menu_btn.setText("⋯")
        self.menu_btn.setFixedSize(26, 26)
        self.menu_btn.setStyleSheet(f"""
            QToolButton{{color:{C['text3']};background:transparent;border:none;font-size:14px;border-radius:5px;}}
            QToolButton:hover{{color:{C['text2']};background:{C['border']};}}
        """)
        self.menu_btn.clicked.connect(self._show_menu)
        hdr.addWidget(self.menu_btn, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(hdr)

        # ── Description
        self.desc_lbl = QLabel(self.app_data.get("description", ""))
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet(f"color:{C['text2']};background:transparent;font-size:11px;")
        self.desc_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.desc_lbl.setMaximumHeight(38)
        layout.addWidget(self.desc_lbl)
        layout.addStretch()

        # ── Action button
        self.action_btn = QPushButton()
        self.action_btn.setFixedHeight(34)
        self.action_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._update_action_btn()
        layout.addWidget(self.action_btn)

        self._update_frame_style()

    def _update_action_btn(self):
        accent = self.app_data.get("accent_color", C["purple"])
        is_installed = self.app_data.get("installed") and self.app_data.get("exec_path")

        try:
            self.action_btn.clicked.disconnect()
        except Exception:
            pass

        if is_installed:
            self.action_btn.setText("▶  Lancer")
            self.action_btn.setStyleSheet(f"""
                QPushButton{{background:{accent};color:white;border:none;border-radius:8px;
                             font-size:12px;font-weight:700;}}
                QPushButton:hover{{background:{self._lighten(accent)};}}
                QPushButton:pressed{{background:{self._darken(accent)};}}
            """)
            self.action_btn.clicked.connect(lambda: self.launch_requested.emit(self.app_data))
        else:
            self.action_btn.setText("⚙  Configurer")
            self.action_btn.setStyleSheet(f"""
                QPushButton{{background:{C['surface_h']};color:{C['text2']};border:1px solid {C['border']};
                             border-radius:8px;font-size:12px;font-weight:600;}}
                QPushButton:hover{{background:{C['border']};color:{C['text']};border-color:{C['border_h']};}}
            """)
            self.action_btn.clicked.connect(lambda: self.install_requested.emit(self.app_data))

    def _update_frame_style(self):
        accent = self.app_data.get("accent_color", C["purple"])
        border = C["border_h"] if self._hovered else C["border"]
        self.setStyleSheet(f"""
            QFrame#AppCard{{
                background:{C['surface']};
                border:1px solid {border};
                border-radius:16px;
                border-top:2px solid {accent};
            }}
        """)

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu{{background:{C['surface_h']};border:1px solid {C['border']};
                   border-radius:10px;padding:4px;color:{C['text']};}}
            QMenu::item{{padding:8px 18px;border-radius:6px;font-size:12px;}}
            QMenu::item:selected{{background:{C['border']};}}
            QMenu::separator{{height:1px;background:{C['border']};margin:4px 8px;}}
        """)
        edit_a   = menu.addAction("✏️   Modifier")
        menu.addSeparator()
        remove_a = menu.addAction("🗑️   Supprimer")

        action = menu.exec(QCursor.pos())
        if action == edit_a:
            self.edit_requested.emit(self.app_data)
        elif action == remove_a:
            self.remove_requested.emit(self.app_data["id"])

    def update_data(self, new_data: dict):
        self.app_data = new_data
        accent = new_data.get("accent_color", C["purple"])
        self.icon_w.emoji = new_data.get("icon_emoji", "📦")
        self.icon_w.set_accent(accent)
        self.icon_w.setText(new_data.get("icon_emoji", "📦"))
        self.name_lbl.setText(new_data["name"])
        self.desc_lbl.setText(new_data.get("description", ""))
        self._update_action_btn()
        self._update_frame_style()

    def enterEvent(self, event):
        self._hovered = True
        self._update_frame_style()
        sh = QGraphicsDropShadowEffect()
        sh.setBlurRadius(22)
        glow = QColor(self.app_data.get("accent_color", C["purple"]))
        glow.setAlphaF(0.35)
        sh.setColor(glow)
        sh.setOffset(0, 5)
        self.setGraphicsEffect(sh)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._update_frame_style()
        self.setGraphicsEffect(None)
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.app_data.get("installed") and self.app_data.get("exec_path"):
            self.launch_requested.emit(self.app_data)


# ══════════════════════════════════════════════════════════════
#  ADD / EDIT DIALOG
# ══════════════════════════════════════════════════════════════

class AppDialog(QDialog):
    """Dialogue d'ajout ou de modification d'application."""

    def __init__(self, app_data: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.app_data     = dict(app_data) if app_data else None
        self.is_edit      = app_data is not None
        self._color       = (app_data or {}).get("accent_color", C["purple"])
        self._drag_pos    = QPoint(0, 0)
        self.result_data  = {}
        self._build_ui()

    def _build_ui(self):
        title_str = "Modifier l'application" if self.is_edit else "Ajouter une application"
        self.setWindowTitle(title_str)
        self.setFixedSize(500, 600)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(f"""
            QDialog{{background:{C['bg2']};border:1px solid {C['border_h']};border-radius:16px;}}
            QLabel{{color:{C['text2']};font-size:12px;background:transparent;}}
            QLineEdit,QComboBox,QTextEdit{{
                background:{C['surface']};border:1px solid {C['border']};border-radius:8px;
                color:{C['text']};padding:7px 12px;font-size:12px;
            }}
            QLineEdit:focus,QComboBox:focus,QTextEdit:focus{{border-color:{C['purple']};}}
            QComboBox::drop-down{{border:none;padding-right:8px;}}
            QComboBox QAbstractItemView{{
                background:{C['surface_h']};border:1px solid {C['border']};
                color:{C['text']};selection-background-color:{C['border']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(0)

        # ── Title bar
        tbar = QHBoxLayout()
        tlbl = QLabel(title_str)
        tlbl.setStyleSheet(f"color:{C['text']};font-size:16px;font-weight:700;")
        tbar.addWidget(tlbl)
        tbar.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C['text3']};border:none;font-size:13px;border-radius:6px;}}
            QPushButton:hover{{background:{C['red']};color:white;}}
        """)
        close_btn.clicked.connect(self.reject)
        tbar.addWidget(close_btn)
        root.addLayout(tbar)
        root.addSpacing(18)

        def lbl(txt):
            l = QLabel(txt)
            l.setStyleSheet(
                f"color:{C['text3']};font-size:9px;font-weight:700;"
                "letter-spacing:1.5px;text-transform:uppercase;")
            return l

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setContentsMargins(0, 0, 0, 0)

        # Nom
        self.name_e = QLineEdit((self.app_data or {}).get("name", ""))
        self.name_e.setPlaceholderText("Ex: Atlas")
        form.addRow(lbl("Nom *"), self.name_e)

        # Description
        self.desc_e = QTextEdit((self.app_data or {}).get("description", ""))
        self.desc_e.setPlaceholderText("Description courte…")
        self.desc_e.setFixedHeight(62)
        form.addRow(lbl("Description"), self.desc_e)

        # Catégorie
        self.cat_cb = QComboBox()
        for cat in CATEGORIES[1:]:
            self.cat_cb.addItem(cat)
        if self.is_edit:
            idx = self.cat_cb.findText(self.app_data.get("category", "Autres"))
            if idx >= 0:
                self.cat_cb.setCurrentIndex(idx)
        form.addRow(lbl("Catégorie"), self.cat_cb)

        # Icône emoji + couleur
        ic_row = QHBoxLayout(); ic_row.setSpacing(10)
        self.emoji_e = QLineEdit((self.app_data or {}).get("icon_emoji", "📦"))
        self.emoji_e.setFixedWidth(78)
        self.emoji_e.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emoji_e.setStyleSheet(
            self.emoji_e.styleSheet() + "font-size:20px;")
        ic_row.addWidget(self.emoji_e)
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(78, 36)
        self._refresh_color_btn()
        self.color_btn.clicked.connect(self._pick_color)
        ic_row.addWidget(self.color_btn)
        ic_row.addStretch()
        form.addRow(lbl("Icône / Couleur"), ic_row)

        # Version
        self.ver_e = QLineEdit((self.app_data or {}).get("version", "0.1.0"))
        form.addRow(lbl("Version"), self.ver_e)

        # Exécutable
        exec_row = QHBoxLayout(); exec_row.setSpacing(8)
        self.exec_e = QLineEdit((self.app_data or {}).get("exec_path", ""))
        self.exec_e.setPlaceholderText("Chemin vers l'exécutable (optionnel)")
        exec_row.addWidget(self.exec_e)
        browse = QPushButton("📂")
        browse.setFixedSize(36, 36)
        browse.setStyleSheet(f"""
            QPushButton{{background:{C['surface_h']};border:1px solid {C['border']};border-radius:8px;color:{C['text']};}}
            QPushButton:hover{{background:{C['border']};}}
        """)
        browse.clicked.connect(self._browse_exec)
        exec_row.addWidget(browse)
        form.addRow(lbl("Exécutable"), exec_row)

        # Git URL
        self.git_e = QLineEdit((self.app_data or {}).get("git_url", ""))
        self.git_e.setPlaceholderText("https://github.com/toi/monapp.git")
        form.addRow(lbl("Git URL"), self.git_e)

        root.addLayout(form)
        root.addStretch()

        # ── Boutons
        btn_row = QHBoxLayout(); btn_row.setSpacing(10); btn_row.addStretch()
        cancel = QPushButton("Annuler")
        cancel.setFixedHeight(38); cancel.setMinimumWidth(100)
        cancel.setStyleSheet(f"""
            QPushButton{{background:{C['surface_h']};color:{C['text2']};border:1px solid {C['border']};
                         border-radius:8px;font-size:12px;}}
            QPushButton:hover{{background:{C['border']};color:{C['text']};}}
        """)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save_lbl = "Enregistrer" if self.is_edit else "Ajouter  +"
        save = QPushButton(save_lbl)
        save.setFixedHeight(38); save.setMinimumWidth(120)
        save.setStyleSheet(f"""
            QPushButton{{background:{C['purple']};color:white;border:none;border-radius:8px;
                         font-size:12px;font-weight:700;}}
            QPushButton:hover{{background:{C['purple_l']};}}
        """)
        save.clicked.connect(self._save)
        btn_row.addWidget(save)
        root.addLayout(btn_row)

    # ── internals
    def _refresh_color_btn(self):
        self.color_btn.setStyleSheet(f"""
            QPushButton{{background:{self._color};border:2px solid {C['border_h']};border-radius:8px;}}
            QPushButton:hover{{border-color:{C['text2']};}}
        """)
        self.color_btn.setText("")

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Choisir une couleur")
        if c.isValid():
            self._color = c.name()
            self._refresh_color_btn()

    def _browse_exec(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner l'exécutable", str(Path.home()))
        if path:
            self.exec_e.setText(path)

    def _save(self):
        name = self.name_e.text().strip()
        if not name:
            QMessageBox.warning(self, "Champ requis", "Le nom est obligatoire.")
            return
        exec_path = self.exec_e.text().strip()
        self.result_data = {
            "id":             (self.app_data or {}).get("id") or str(uuid.uuid4())[:8],
            "name":           name,
            "description":    self.desc_e.toPlainText().strip(),
            "category":       self.cat_cb.currentText(),
            "icon_emoji":     self.emoji_e.text().strip() or "📦",
            "icon_path":      (self.app_data or {}).get("icon_path", ""),
            "accent_color":   self._color,
            "version":        self.ver_e.text().strip() or "0.1.0",
            "installed":      bool(exec_path),
            "exec_path":      exec_path,
            "exec_args":      (self.app_data or {}).get("exec_args", []),
            "install_type":   "manual",
            "install_script": (self.app_data or {}).get("install_script", ""),
            "git_url":        self.git_e.text().strip(),
            "tags":           (self.app_data or {}).get("tags", []),
        }
        self.accept()

    # drag frameless
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)


# ══════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════

class Sidebar(QWidget):
    category_changed  = Signal(str)
    add_app_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(222)
        self._btns: Dict[str, QPushButton] = {}
        self._current = "Toutes"
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            Sidebar{{background:{C['bg2']};border-right:1px solid {C['border']};}}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Logo
        logo_frame = QFrame()
        logo_frame.setFixedHeight(66)
        logo_frame.setStyleSheet(f"background:transparent;border-bottom:1px solid {C['border']};")
        ll = QHBoxLayout(logo_frame)
        ll.setContentsMargins(18, 10, 18, 10)

        star = QLabel("✦")
        star.setStyleSheet(f"color:{C['purple_l']};font-size:22px;background:transparent;")
        ll.addWidget(star)

        nc = QVBoxLayout(); nc.setSpacing(1)
        t1 = QLabel("EXISTENCE")
        t1.setStyleSheet(f"color:{C['text']};font-size:14px;font-weight:700;background:transparent;")
        t2 = QLabel("creative universe")
        t2.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;")
        nc.addWidget(t1); nc.addWidget(t2)
        ll.addLayout(nc); ll.addStretch()
        lay.addWidget(logo_frame)
        lay.addSpacing(14)

        sec = QLabel("CARTOGRAPHIE")
        sec.setStyleSheet(f"""
            color:{C['text3']};font-size:9px;font-weight:700;letter-spacing:1.5px;
            background:transparent;padding:0 18px;
        """)
        lay.addWidget(sec)
        lay.addSpacing(6)

        cat_icons = {
            "Toutes": "✦", "Création": "🎨", "Productivité": "📝",
            "Développement": "💻", "Utilitaires": "🔧", "Autres": "📦",
        }
        for cat in CATEGORIES:
            icon = cat_icons.get(cat, "•")
            btn = QPushButton(f"  {icon}  {cat}")
            btn.setFixedHeight(36)
            btn.setStyleSheet(self._btn_css(False))
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, c=cat: self._select(c, emit=True))
            self._btns[cat] = btn
            lay.addWidget(btn)

        lay.addSpacing(14)
        div = QFrame(); div.setFixedHeight(1)
        div.setStyleSheet(f"background:{C['border']};")
        lay.addWidget(div)
        lay.addSpacing(12)

        add_btn = QPushButton("  + Créer un nouvel astre")
        add_btn.setFixedHeight(38)
        add_btn.setStyleSheet(f"""
            QPushButton{{background:{C['bg2']};color:{C['purple_l']};
                border:1px dashed {C['purple']};border-radius:8px;
                font-size:12px;font-weight:600;margin:0 12px;}}
            QPushButton:hover{{background:#16123a;border-color:{C['purple_l']};}}
        """)
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.clicked.connect(self.add_app_requested.emit)
        lay.addWidget(add_btn)
        lay.addStretch()

        ver = QLabel(f"v{APP_VERSION}")
        ver.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;padding:12px 18px;")
        lay.addWidget(ver)

        self._select("Toutes")

    def _btn_css(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton{{background:#16123a;color:{C['purple_l']};border:none;
                    border-left:3px solid {C['purple']};border-radius:0;text-align:left;
                    padding-left:17px;font-size:13px;font-weight:600;}}
            """
        return f"""
            QPushButton{{background:transparent;color:{C['text2']};border:none;
                border-left:3px solid transparent;border-radius:0;text-align:left;
                padding-left:17px;font-size:13px;}}
            QPushButton:hover{{
                background:{C['surface_h']};
                color:{C['text']};
                border:none;
                border-left:3px solid {C['purple']};
                border-radius:0;
                text-align:left;
                padding-left:17px;
                font-size:13px;
            }}
        """

    def _select(self, cat: str, emit: bool = False):
        if self._current in self._btns:
            self._btns[self._current].setStyleSheet(self._btn_css(False))
        self._current = cat
        if cat in self._btns:
            self._btns[cat].setStyleSheet(self._btn_css(True))
        if emit:
            self.category_changed.emit(cat)


# ══════════════════════════════════════════════════════════════
#  ORBITAL MAP / CONTENT AREA
# ══════════════════════════════════════════════════════════════

class OrbitMap(QWidget):
    """Carte vivante d'Existence : les univers sont des astres, les outils gravitent."""
    app_selected = Signal(dict)
    app_activated = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.apps, self.nodes, self.hovered, self.phase = [], {}, None, 0.0
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(32)

    def set_apps(self, apps):
        self.apps = apps
        self.hovered = None
        self.update()

    def _tick(self):
        self.phase += .018
        self.update()

    def _layout_nodes(self):
        w, h = max(1, self.width()), max(1, self.height())
        universes = [a for a in self.apps if not a.get("orbit_of")]
        tools = [a for a in self.apps if a.get("orbit_of")]
        nodes = {}
        # Les univers se répartissent comme deux grands systèmes stellaires.
        for i, app in enumerate(universes):
            angle = -0.45 + i * (math.pi * 0.9 / max(1, len(universes) - 1))
            cx = w * .5 + math.cos(angle) * w * .24
            cy = h * .5 + math.sin(angle) * h * .17
            nodes[app["id"]] = (cx, cy, 47)
        for i, app in enumerate(tools):
            parent = nodes.get(app.get("orbit_of"))
            if not parent:
                continue
            angle = (hash(app["id"]) % 628) / 100 + self.phase * .45
            radius = 105 + (hash(app["id"] + "orbit") % 55)
            nodes[app["id"]] = (parent[0] + math.cos(angle) * radius,
                                  parent[1] + math.sin(angle) * radius * .58, 18)
        self.nodes = nodes

    def paintEvent(self, event):
        self._layout_nodes()
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Subtle spatial grid / constellation guide.
        p.setPen(QPen(QColor(105, 89, 180, 22), 1))
        for x in range(0, w, 80): p.drawLine(x, 0, x, h)
        for y in range(0, h, 80): p.drawLine(0, y, w, y)
        for app in self.apps:
            if not app.get("orbit_of") or app["id"] not in self.nodes: continue
            x, y, _ = self.nodes[app["id"]]; px, py, _ = self.nodes[app["orbit_of"]]
            color = QColor(app.get("accent_color", C["cyan"])); color.setAlpha(75)
            p.setPen(QPen(color, 1, Qt.PenStyle.DotLine)); p.drawLine(QPointF(px, py), QPointF(x, y))
        # Orbits first, then their bodies.
        for app in self.apps:
            if app.get("orbit_of") not in self.nodes: continue
            px, py, _ = self.nodes[app["orbit_of"]]
            radius = 105 + (hash(app["id"] + "orbit") % 55)
            col = QColor(app.get("accent_color", C["cyan"])); col.setAlpha(58)
            p.setPen(QPen(col, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(px-radius, py-radius*.58, radius*2, radius*1.16))
        for app in self.apps:
            if app["id"] not in self.nodes: continue
            x, y, r = self.nodes[app["id"]]; selected = app["id"] == self.hovered
            color = QColor(app.get("accent_color", C["purple"]))
            glow = QRadialGradient(QPointF(x, y), r * (2.5 if selected else 1.8))
            transparent = QColor(color); transparent.setAlpha(0)
            bright = QColor(color); bright.setAlpha(95 if selected else 45)
            glow.setColorAt(0, bright); glow.setColorAt(1, transparent)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(glow)); p.drawEllipse(QRectF(x-r*2.5, y-r*2.5, r*5, r*5))
            core = QRadialGradient(QPointF(x-r*.25, y-r*.3), r*1.3)
            hi = QColor("#FFFFFF"); hi.setAlpha(220)
            core.setColorAt(0, hi); core.setColorAt(.15, color); core.setColorAt(1, QColor("#171329"))
            p.setBrush(QBrush(core)); p.setPen(QPen(color.lighter(150), 2 if selected else 1))
            p.drawEllipse(QRectF(x-r, y-r, r*2, r*2))
            p.setPen(QColor(C["text"])); p.setFont(QFont("", 12 if r > 20 else 10, QFont.Weight.DemiBold))
            p.drawText(QRectF(x-85, y+r+8, 170, 24), Qt.AlignmentFlag.AlignHCenter, app["name"])
            if r > 20:
                p.setPen(QColor(C["text3"])); p.setFont(QFont("", 9))
                p.drawText(QRectF(x-110, y+r+28, 220, 20), Qt.AlignmentFlag.AlignHCenter, "UNIVERS")
        p.end()

    def _app_at(self, pos):
        for app in reversed(self.apps):
            node = self.nodes.get(app["id"])
            if node and math.hypot(pos.x()-node[0], pos.y()-node[1]) <= node[2] + 12:
                return app
        return None

    def mouseMoveEvent(self, event):
        app = self._app_at(event.position())
        ident = app["id"] if app else None
        if ident != self.hovered:
            self.hovered = ident; self.setCursor(Qt.CursorShape.PointingHandCursor if app else Qt.CursorShape.ArrowCursor); self.update()

    def mousePressEvent(self, event):
        app = self._app_at(event.position())
        if app: self.app_selected.emit(app)

    def mouseDoubleClickEvent(self, event):
        app = self._app_at(event.position())
        if app: self.app_activated.emit(app)


class ContentArea(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QFrame(); hdr.setFixedHeight(84)
        hdr.setStyleSheet(f"background:{C['bg2']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(24, 0, 24, 0)

        titles = QVBoxLayout(); titles.setSpacing(2)
        self.title_lbl = QLabel("La matière prend vie")
        self.title_lbl.setStyleSheet(f"color:{C['text']};font-size:18px;font-weight:700;")
        self.subtitle_lbl = QLabel("Explore tes univers. Les outils orbitent autour de ce qu'ils transforment.")
        self.subtitle_lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;")
        titles.addWidget(self.title_lbl); titles.addWidget(self.subtitle_lbl); hl.addLayout(titles)
        hl.addStretch()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍  Rechercher…")
        self.search_edit.setFixedSize(220, 36)
        self.search_edit.setStyleSheet(f"""
            QLineEdit{{background:{C['surface']};border:1px solid {C['border']};border-radius:18px;
                       color:{C['text']};padding:0 16px;font-size:12px;}}
            QLineEdit:focus{{border-color:{C['purple']};}}
        """)
        hl.addWidget(self.search_edit)
        lay.addWidget(hdr)

        body = QFrame(); body_l = QHBoxLayout(body); body_l.setContentsMargins(22, 12, 22, 22); body_l.setSpacing(16)
        self.orbit_map = OrbitMap(); self.orbit_map.setMinimumWidth(520)
        body_l.addWidget(self.orbit_map, 1)
        self.detail = QLabel("SÉLECTIONNE UN ASTRE\n\nApproche-toi d'un univers pour découvrir sa matière. Double-clique pour l'ouvrir.")
        self.detail.setFixedWidth(210); self.detail.setWordWrap(True); self.detail.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail.setStyleSheet(f"background:{C['surface']};border:1px solid {C['border']};border-radius:16px;padding:18px;color:{C['text2']};font-size:11px;")
        body_l.addWidget(self.detail)
        lay.addWidget(body)


# ══════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════

class GalaxyHub(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg       = ConfigManager()
        self.apps      = self.cfg.load()
        self._cat      = "Toutes"
        self._query    = ""
        self._cards: Dict[str, AppCard] = {}
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._refresh)

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        self.setWindowTitle("Existence — Creative Universe")
        self.setMinimumSize(900, 600)
        self.resize(1180, 740)
        self.setStyleSheet(f"QMainWindow{{background:{C['bg']};}} QWidget{{background:transparent;}}")

        central = QWidget()
        self.setCentralWidget(central)

        # Star field (background layer)
        self.stars = StarField(central)
        self.stars.lower()

        # Overlay panel (sidebar + content) — semi-transparent
        self._overlay = QWidget(central)
        ol = QHBoxLayout(self._overlay)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.category_changed.connect(self._on_cat)
        self.sidebar.add_app_requested.connect(self._add_app)
        ol.addWidget(self.sidebar)

        self.content = ContentArea()
        self.content.search_edit.textChanged.connect(self._on_search)
        self.content.orbit_map.app_selected.connect(self._select_app)
        self.content.orbit_map.app_activated.connect(self._launch)
        ol.addWidget(self.content)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.stars.setGeometry(0, 0, self.width(), self.height())
        self._overlay.setGeometry(0, 0, self.width(), self.height())
        self._resize_timer.start(120)

    # ── Refresh grid
    def _refresh(self):
        filtered = [a for a in self.apps if self._matches(a)]
        cat_title = "Tout Existence" if self._cat == "Toutes" else self._cat
        self.content.title_lbl.setText(f"{cat_title} · {len(filtered)} astre{'s' if len(filtered) != 1 else ''}")
        self.content.orbit_map.set_apps(filtered)

    def _select_app(self, app_data: dict):
        orbit = "UNIVERS" if not app_data.get("orbit_of") else "OUTIL EN ORBITE"
        launch = "Double-clique pour ouvrir." if app_data.get("installed") and app_data.get("exec_path") else "Configure son exécutable dans le menu ⋯ lorsque tu seras prêt."
        self.content.detail.setText(
            f"{orbit}\n\n{app_data['name'].upper()}\n\nv{app_data.get('version', '0.1.0')}\n\n"
            f"{app_data.get('description', '')}\n\n{launch}")

    def _add_placeholder(self) -> QFrame:
        f = QFrame()
        f.setFixedSize(AppCard.CARD_W, AppCard.CARD_H)
        f.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        f.setStyleSheet(f"""
            QFrame{{background:{C['surface']};border:2px dashed {C['border']};border-radius:16px;}}
            QFrame:hover{{border-color:{C['purple']};background:#0f0b28;}}
        """)
        inner = QVBoxLayout(f)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus = QLabel("+")
        plus.setStyleSheet(f"color:{C['text3']};font-size:30px;background:transparent;")
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(plus)
        txt = QLabel("Nouvelle application")
        txt.setStyleSheet(f"color:{C['text3']};font-size:12px;background:transparent;")
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(txt)
        f.mousePressEvent = lambda _: self._add_app()
        return f

    def _matches(self, app: dict) -> bool:
        if self._cat != "Toutes" and app.get("category") != self._cat:
            return False
        if self._query:
            q = self._query.lower()
            return (q in app["name"].lower()
                    or q in app.get("description", "").lower()
                    or any(q in t for t in app.get("tags", [])))
        return True

    # ── Handlers
    def _on_cat(self, cat: str):
        self._cat = cat; self._refresh()

    def _on_search(self, q: str):
        self._query = q; self._refresh()

    def _add_app(self):
        dlg = AppDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.apps.append(dlg.result_data)
            self.cfg.save(self.apps)
            self._refresh()

    def _edit_app(self, app_data: dict):
        dlg = AppDialog(app_data=app_data, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            upd = dlg.result_data
            for i, a in enumerate(self.apps):
                if a["id"] == upd["id"]:
                    self.apps[i] = upd; break
            self.cfg.save(self.apps)
            self._refresh()

    def _remove(self, app_id: str):
        app = next((a for a in self.apps if a["id"] == app_id), None)
        if not app: return
        reply = QMessageBox.question(
            self, "Supprimer ?",
            f"Retirer « {app['name']} » d'Existence ?\n"
            "(L'app ne sera pas désinstallée du système.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.apps = [a for a in self.apps if a["id"] != app_id]
            self.cfg.save(self.apps)
            self._refresh()

    def _launch(self, app_data: dict):
        ep = app_data.get("exec_path", "")
        if not ep:
            QMessageBox.information(
                self, "Aucun exécutable",
                f"Aucun exécutable configuré pour « {app_data['name']} ».\n"
                "Clique sur ⚙ Configurer pour en ajouter un.",
            )
            return
        try:
            args = [ep] + app_data.get("exec_args", [])
            subprocess.Popen(args, start_new_session=True)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur de lancement", str(exc))


# ══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════

def main():
    # Empêche KDE/Kvantum d'injecter ses couleurs par-dessus le QSS
    os.environ["QT_QPA_PLATFORMTHEME"] = ""
    os.environ.pop("QT_STYLE_OVERRIDE", None)

    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet("")  # vide tout stylesheet injecté par la plateforme
    app.setApplicationName("Existence")
    app.setApplicationVersion(APP_VERSION)

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(C["bg"]))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Base,            QColor(C["surface"]))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(C["bg2"]))
    pal.setColor(QPalette.ColorRole.Text,            QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Button,          QColor(C["surface"]))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(C["text"]))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(C["purple"]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    pal.setColor(QPalette.ColorRole.Mid,             QColor(C["surface_h"]))
    pal.setColor(QPalette.ColorRole.Midlight,        QColor(C["surface"]))
    pal.setColor(QPalette.ColorRole.Light,           QColor(C["border"]))
    pal.setColor(QPalette.ColorRole.Dark,            QColor(C["bg"]))
    pal.setColor(QPalette.ColorRole.Shadow,          QColor(C["bg"]))
    app.setPalette(pal)

    win = GalaxyHub()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
