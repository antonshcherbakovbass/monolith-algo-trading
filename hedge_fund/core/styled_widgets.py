"""Premium styled widgets for Divine Dualism and NY Art Deco themes.

All backgrounds are procedurally generated — no external photo textures.
Visual: mystical Art Deco, sacred geometry, embossed gold, star dust,
pearlescent glow, velvet depth.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QScrollArea, QTabWidget,
)
from PyQt6.QtGui import (
    QPainter, QPixmap, QColor, QPen, QBrush,
    QLinearGradient, QRadialGradient, QFont, QPainterPath,
)
from PyQt6.QtCore import Qt, QRectF, QPointF
try:
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    QSvgRenderer = None

from hedge_fund.assets.textures import (
    create_dark_sanctum, create_card_texture,
    create_sacred_geometry_bg, create_dualism_sun, create_alchemical_circle,
    create_header_gradient, create_axis_line, create_art_deco_frame,
    _velvet_base, _gold_emboss_line, _gold_emboss_circle, _specular_streak,
)

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_ICONS_DIR = _ASSETS_DIR / "icons"


def _icon_path(name: str) -> Path:
    return _ICONS_DIR / name


# ═══════════════════════════════════════════════════════════════
#  PROCEDURAL TEXTURE GENERATORS
# ═══════════════════════════════════════════════════════════════


def _star_dust(p: QPainter, w: int, h: int, seed: int = 42,
               color: str = "#FFD700", density: int = 300,
               max_alpha: int = 90, max_r: float = 1.8) -> None:
    """Scatter glittering star-dust particles across the area."""
    rng = random.Random(seed)
    for _ in range(w * h // density):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        a = rng.randint(15, max_alpha)
        r = rng.uniform(0.3, max_r)
        c = QColor(color)
        c.setAlpha(a)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(c))
        p.drawEllipse(QPointF(x, y), r, r)


def _pearl_shimmer(p: QPainter, w: int, h: int, angle: float = -15,
                   color: str = "#FFFFFF", alpha: int = 8) -> None:
    """Draw diagonal pearlescent shimmer streaks."""
    rng = random.Random(1337)
    for _ in range(6):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        length = rng.randint(80, 300)
        _specular_streak(p, x, y, length, angle + rng.uniform(-10, 10),
                         color, alpha + rng.randint(-3, 3))


def _sacred_rays(p: QPainter, cx: float, cy: float, count: int = 36,
                 length: float = 600, color: str = "#D4AF37",
                 base_alpha: int = 10, bright_alpha: int = 18) -> None:
    """Radial sacred light rays."""
    for i in range(count):
        angle = math.radians(360.0 / count * i)
        a = bright_alpha if i % 4 == 0 else base_alpha
        w = 1.5 if i % 4 == 0 else 0.5
        c = QColor(color)
        c.setAlpha(a)
        p.setPen(QPen(c, w))
        p.drawLine(QPointF(cx, cy),
                   QPointF(cx + length * math.cos(angle),
                           cy + length * math.sin(angle)))


def _concentric_circles(p: QPainter, cx: float, cy: float,
                        max_r: int = 300, step: int = 55,
                        color: str = "#D4AF37", alpha: int = 14) -> None:
    """Concentric sacred geometry circles."""
    c = QColor(color)
    c.setAlpha(alpha)
    p.setPen(QPen(c, 0.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for r in range(step, max_r, step):
        p.drawEllipse(QPointF(cx, cy), r, r)


def _art_deco_chevrons(p: QPainter, w: int, h: int,
                       color: str = "#D4AF37", alpha: int = 25,
                       rows: int = 5, spacing: int = 9, step: int = 22) -> None:
    """Stepped Art Deco chevron bands."""
    c = QColor(color)
    c.setAlpha(alpha)
    p.setPen(QPen(c, 1.2))
    for row in range(rows):
        y = 6 + row * spacing
        for x in range(0, w, step * 2):
            p.drawLine(x, y, x + step, y - 5)
            p.drawLine(x + step, y - 5, x + step * 2, y)


def _wood_grain(p: QPainter, w: int, h: int, seed: int = 42,
                base_color: str = "#2A2014", grain_color: str = "#3A2E1C",
                grain_alpha: int = 35) -> None:
    """Horizontal wood grain lines for warm organic texture."""
    rng = random.Random(seed)
    c = QColor(grain_color)
    for y in range(0, h, 2):
        a = rng.randint(5, grain_alpha)
        c.setAlpha(a)
        p.setPen(QPen(c, rng.uniform(0.3, 1.2)))
        wave = rng.uniform(-2, 2)
        p.drawLine(QPointF(0, y + wave), QPointF(w, y + wave + rng.uniform(-1, 1)))


def _inner_shadow(p: QPainter, w: int, h: int, depth: int = 30,
                  color: str = "#000000", alpha: int = 120) -> None:
    """Volumetric inner shadow on all edges."""
    # Top shadow (strongest)
    top = QLinearGradient(0, 0, 0, depth * 1.5)
    top.setColorAt(0.0, QColor(0, 0, 0, alpha))
    top.setColorAt(0.5, QColor(0, 0, 0, alpha // 3))
    top.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, int(depth * 1.5), top)

    # Bottom highlight (subtle warm glow)
    bot = QLinearGradient(0, h, 0, h - depth)
    bot.setColorAt(0.0, QColor(0, 0, 0, alpha // 2))
    bot.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, h - depth, w, depth, bot)

    # Left shadow
    left = QLinearGradient(0, 0, depth, 0)
    left.setColorAt(0.0, QColor(0, 0, 0, alpha // 2))
    left.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, depth, h, left)

    # Right shadow
    right = QLinearGradient(w, 0, w - depth, 0)
    right.setColorAt(0.0, QColor(0, 0, 0, alpha // 2))
    right.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(w - depth, 0, depth, h, right)


def _warm_vignette(p: QPainter, w: int, h: int, intensity: int = 80) -> None:
    """Warm radial vignette — darker edges, warm center."""
    vig = QRadialGradient(w * 0.5, h * 0.35, max(w, h) * 0.7)
    vig.setColorAt(0.0, QColor(60, 45, 20, 15))
    vig.setColorAt(0.4, QColor(0, 0, 0, 0))
    vig.setColorAt(0.7, QColor(0, 0, 0, intensity // 3))
    vig.setColorAt(1.0, QColor(0, 0, 0, intensity))
    p.fillRect(0, 0, w, h, vig)


@lru_cache(maxsize=4)
def gen_mystic_dark_bg(w: int, h: int) -> QPixmap:
    """Warm dark background: wood grain, inner shadow, sacred geometry, star dust."""
    pm = QPixmap(w, h)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Warm dark base instead of cold blue
    grad = QLinearGradient(0, 0, 0, h)
    grad.setColorAt(0.0, QColor("#1E1810"))
    grad.setColorAt(0.15, QColor("#1A1408"))
    grad.setColorAt(0.5, QColor("#141006"))
    grad.setColorAt(0.85, QColor("#100C04"))
    grad.setColorAt(1.0, QColor("#0C0A04"))
    p.fillRect(0, 0, w, h, grad)

    # Wood grain texture
    _wood_grain(p, w, h, 42, "#2A2014", "#3A2E1C", 30)
    _wood_grain(p, w, h, 99, "#221A0E", "#30261A", 15)

    # Warm center glow
    center = QRadialGradient(w * 0.5, h * 0.3, max(w, h) * 0.6)
    center.setColorAt(0.0, QColor(100, 75, 30, 25))
    center.setColorAt(0.3, QColor(60, 45, 15, 12))
    center.setColorAt(0.7, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, h, center)

    # Sacred geometry
    cx, cy = w * 0.5, h * 0.45
    _sacred_rays(p, cx, cy, 36, max(w, h) * 0.8, "#8B7424", 4, 10)
    _concentric_circles(p, cx, cy, max(w, h), 80, "#8B7424", 6)

    # Star dust
    _star_dust(p, w, h, 42, "#FFD700", 350, 55, 1.2)
    _star_dust(p, w, h, 99, "#FFFFFF", 800, 30, 0.7)

    # Warm vignette
    _warm_vignette(p, w, h, 100)
    _inner_shadow(p, w, h, 40, "#000000", 100)

    # Corner ornaments
    for cx_c, cy_c, dx, dy in [(0, 0, 1, 1), (w, 0, -1, 1),
                                 (0, h, 1, -1), (w, h, -1, -1)]:
        _gold_emboss_line(p, cx_c + 6 * dx, cy_c + 3 * dy,
                          cx_c + 45 * dx, cy_c + 3 * dy, 1.2)
        _gold_emboss_line(p, cx_c + 3 * dx, cy_c + 6 * dy,
                          cx_c + 3 * dx, cy_c + 45 * dy, 1.2)

    p.end()
    return pm


@lru_cache(maxsize=4)
def gen_mystic_card_bg(w: int, h: int) -> QPixmap:
    """Card background: warm wood panel with embossed gold border and inner shadow."""
    pm = QPixmap(w, h)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Warm dark base
    grad = QLinearGradient(0, 0, 0, h)
    grad.setColorAt(0.0, QColor("#201A10"))
    grad.setColorAt(0.03, QColor("#181208"))
    grad.setColorAt(0.5, QColor("#120E06"))
    grad.setColorAt(0.97, QColor("#0E0A04"))
    grad.setColorAt(1.0, QColor("#080604"))
    p.fillRect(0, 0, w, h, grad)

    _wood_grain(p, w, h, 77, "#2A2014", "#30261A", 18)

    _star_dust(p, w, h, 77, "#FFD700", 700, 35, 0.8)
    _star_dust(p, w, h, 88, "#FFFFFF", 1200, 25, 0.5)

    # Top highlight bevel
    gloss = QLinearGradient(0, 0, 0, 4)
    gloss.setColorAt(0.0, QColor(139, 116, 36, 100))
    gloss.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, 4, gloss)

    # Bottom shadow bevel
    shadow = QLinearGradient(0, h - 3, 0, h)
    shadow.setColorAt(0.0, QColor(0, 0, 0, 0))
    shadow.setColorAt(1.0, QColor(0, 0, 0, 160))
    p.fillRect(0, h - 3, w, 3, shadow)

    # Gold emboss border
    _gold_emboss_line(p, 2, 2, w - 2, 2, 1.5)
    _gold_emboss_line(p, 2, h - 2, w - 2, h - 2, 1.0)
    _gold_emboss_line(p, 2, 2, 2, h - 2, 1.2)
    _gold_emboss_line(p, w - 2, 2, w - 2, h - 2, 1.2)

    _inner_shadow(p, w, h, 15, "#000000", 60)

    p.end()
    return pm


@lru_cache(maxsize=4)
def gen_ny_dark_bg(w: int, h: int) -> QPixmap:
    """NY Art Deco dark background: warm leather, bronze columns, skyline, star dust."""
    pm = QPixmap(w, h)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Warm dark leather base
    grad = QLinearGradient(0, 0, 0, h)
    grad.setColorAt(0.0, QColor("#1C1608"))
    grad.setColorAt(0.15, QColor("#181206"))
    grad.setColorAt(0.5, QColor("#120E04"))
    grad.setColorAt(0.85, QColor("#0E0A02"))
    grad.setColorAt(1.0, QColor("#0A0802"))
    p.fillRect(0, 0, w, h, grad)

    # Leather/wood grain
    _wood_grain(p, w, h, 1929, "#28200E", "#342A18", 25)

    # Bronze vertical columns with glow
    for x in range(0, w, 55):
        col_grad = QLinearGradient(x - 2, 0, x + 2, 0)
        col_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        col_grad.setColorAt(0.3, QColor(122, 96, 16, 12))
        col_grad.setColorAt(0.5, QColor(197, 160, 40, 18))
        col_grad.setColorAt(0.7, QColor(122, 96, 16, 12))
        col_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(x - 2, 0, 4, h, col_grad)

    _art_deco_chevrons(p, w, h, "#8B7424", 18, 4, 8, 24)

    # Skyline silhouettes at bottom
    rng = random.Random(1929)
    baseline = h - 20
    x_pos = 0
    while x_pos < w:
        bw = rng.randint(8, 22)
        bh = rng.randint(30, 140)
        sky_grad = QLinearGradient(0, baseline - bh, 0, baseline + 20)
        sky_grad.setColorAt(0.0, QColor("#0A0806"))
        sky_grad.setColorAt(1.0, QColor("#060504"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(sky_grad))
        p.drawRect(QRectF(x_pos, baseline - bh, bw, bh + 20))
        win = QColor("#E8C840")
        win.setAlpha(rng.randint(5, 16))
        p.setBrush(QBrush(win))
        for wy in range(int(baseline - bh + 4), baseline, 9):
            for wx in range(int(x_pos + 2), int(x_pos + bw - 2), 5):
                if rng.random() > 0.55:
                    p.drawRect(QRectF(wx, wy, 2, 3))
        x_pos += bw + rng.randint(2, 5)

    _star_dust(p, w, h, 1920, "#E8C840", 400, 50, 1.0)
    _star_dust(p, w, h, 1929, "#FFFFFF", 900, 30, 0.7)

    _warm_vignette(p, w, h, 90)
    _inner_shadow(p, w, h, 40, "#000000", 90)

    # Corner art deco brackets
    for cx_c, cy_c, dx, dy in [(0, 0, 1, 1), (w, 0, -1, 1),
                                 (0, h, 1, -1), (w, h, -1, -1)]:
        _gold_emboss_line(p, cx_c + 6 * dx, cy_c + 3 * dy,
                          cx_c + 45 * dx, cy_c + 3 * dy, 1.5)
        _gold_emboss_line(p, cx_c + 3 * dx, cy_c + 6 * dy,
                          cx_c + 3 * dx, cy_c + 40 * dy, 1.5)
        _gold_emboss_line(p, cx_c + 45 * dx, cy_c + 3 * dy,
                          cx_c + 45 * dx, cy_c + 15 * dy, 1.5)

    p.end()
    return pm


# ═══════════════════════════════════════════════════════════════
#  SPLIT BACKGROUNDS (Light/Dark hemispheres)
# ═══════════════════════════════════════════════════════════════


def _paint_divine_light(p: QPainter, w: int, h: int) -> None:
    """Left hemisphere: ethereal ivory/pearl — luminous, dreamy, glossy."""
    # Smooth ivory base
    grad = QLinearGradient(0, 0, 0, h)
    grad.setColorAt(0.0, QColor("#FDFBF7"))
    grad.setColorAt(0.3, QColor("#FAF6EE"))
    grad.setColorAt(0.7, QColor("#F5F0E6"))
    grad.setColorAt(1.0, QColor("#EDE6D6"))
    p.fillRect(0, 0, w, h, grad)

    # Mother-of-pearl shimmer (iridescent streaks)
    _pearl_shimmer(p, w, h, -12, "#FFFFFF", 10)
    _pearl_shimmer(p, w, h, 8, "#E6C687", 6)

    # Faint gold geometric starbursts
    cx, cy = w * 0.45, h * 0.4
    _sacred_rays(p, cx, cy, 24, max(w, h) * 0.7, "#D4AF37", 2, 5)
    _concentric_circles(p, cx, cy, min(w, h), 70, "#D4AF37", 4)

    # Thin silver/gold stepped lines
    _art_deco_chevrons(p, w, h, "#C0B490", 8, 3, 12, 28)

    # Faint star vectors as watermarks
    rng = random.Random(777)
    for _ in range(8):
        sx = rng.randint(20, w - 20)
        sy = rng.randint(20, h - 20)
        size = rng.randint(15, 40)
        star_c = QColor("#D4AF37")
        star_c.setAlpha(10)
        p.setPen(QPen(star_c, 0.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        for i in range(5):
            angle = math.radians(-90 + i * 72)
            inner_angle = math.radians(-90 + i * 72 + 36)
            ox = sx + size * math.cos(angle)
            oy = sy + size * math.sin(angle)
            ix = sx + size * 0.4 * math.cos(inner_angle)
            iy = sy + size * 0.4 * math.sin(inner_angle)
            if i == 0:
                path.moveTo(ox, oy)
            else:
                path.lineTo(ox, oy)
            path.lineTo(ix, iy)
        path.closeSubpath()
        p.drawPath(path)

    # Glossy top sheen
    gloss = QLinearGradient(0, 0, 0, h * 0.3)
    gloss.setColorAt(0.0, QColor(255, 255, 255, 40))
    gloss.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillRect(0, 0, w, int(h * 0.3), gloss)


def _paint_divine_dark(p: QPainter, w: int, h: int) -> None:
    """Right hemisphere: heavy velvet darkness — coarse, tactile, ominous."""
    # Deep layered velvet base
    grad = QLinearGradient(0, 0, 0, h)
    grad.setColorAt(0.0, QColor("#0A0A0C"))
    grad.setColorAt(0.3, QColor("#121216"))
    grad.setColorAt(0.5, QColor("#0E0E12"))
    grad.setColorAt(0.7, QColor("#121216"))
    grad.setColorAt(1.0, QColor("#0A0A0C"))
    p.fillRect(0, 0, w, h, grad)

    # Heavy inner shadows
    _inner_shadow(p, w, h, 50, "#000000", 160)

    # Raw obsidian texture
    _wood_grain(p, w, h, 666, "#0C0C10", "#141418", 18)
    _wood_grain(p, w, h, 999, "#08080C", "#101014", 12)

    # Aggressive 45-degree chamfer lines in dark gold
    chamfer_c = QColor("#B3924D")
    chamfer_c.setAlpha(12)
    p.setPen(QPen(chamfer_c, 0.8))
    for i in range(-h, w + h, 18):
        p.drawLine(QPointF(i, 0), QPointF(i + h, h))

    # Dim crimson glare peeking through seams
    for y_pos in range(0, h, 35):
        seam = QLinearGradient(0, y_pos - 1, 0, y_pos + 1)
        seam.setColorAt(0.0, QColor(0, 0, 0, 0))
        seam.setColorAt(0.5, QColor(90, 0, 10, 8))
        seam.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(0, y_pos - 1, w, 2, seam)

    # Crimson core glow
    core = QRadialGradient(w * 0.5, h * 0.5, max(w, h) * 0.4)
    core.setColorAt(0.0, QColor(90, 0, 10, 12))
    core.setColorAt(0.5, QColor(40, 0, 5, 6))
    core.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, h, core)

    _warm_vignette(p, w, h, 100)


def _paint_ny_light(p: QPainter, w: int, h: int) -> None:
    """Left panel: warm tan leather with Art Deco fan and gold accents."""
    grad = QLinearGradient(0, 0, w, 0)
    grad.setColorAt(0.0, QColor("#3A3020"))
    grad.setColorAt(0.3, QColor("#4A3C28"))
    grad.setColorAt(0.6, QColor("#544430"))
    grad.setColorAt(1.0, QColor("#5A4A34"))
    p.fillRect(0, 0, w, h, grad)

    _wood_grain(p, w, h, 1925, "#5A4A34", "#6A5A40", 30)

    # Warm center glow
    center = QRadialGradient(w * 0.5, h * 0.35, max(w, h) * 0.6)
    center.setColorAt(0.0, QColor(120, 90, 35, 30))
    center.setColorAt(0.4, QColor(80, 60, 25, 15))
    center.setColorAt(0.8, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, h, center)

    # Sunburst fan
    cx = w // 2
    fan = QColor("#8B7424")
    fan.setAlpha(15)
    p.setPen(QPen(fan, 1.0))
    for i in range(24):
        angle = math.radians(150 + i * 10)
        length = h * 0.9
        p.drawLine(QPointF(cx, 0),
                   QPointF(cx + length * math.cos(angle), length * math.sin(angle)))

    _art_deco_chevrons(p, w, h, "#8B7424", 20, 5, 9, 22)
    _star_dust(p, w, h, 1925, "#C5A028", 500, 35, 0.8)
    _warm_vignette(p, w, h, 80)


def _paint_ny_dark(p: QPainter, w: int, h: int) -> None:
    """Right panel: dark mahogany with skyline silhouettes and bronze stars."""
    grad = QLinearGradient(0, 0, w, 0)
    grad.setColorAt(0.0, QColor("#181208"))
    grad.setColorAt(0.3, QColor("#120E04"))
    grad.setColorAt(0.7, QColor("#0E0A02"))
    grad.setColorAt(1.0, QColor("#0A0802"))
    p.fillRect(0, 0, w, h, grad)

    _wood_grain(p, w, h, 1920, "#1E1608", "#281E10", 20)

    # Bronze columns with glow
    for x in range(0, w, 50):
        col_grad = QLinearGradient(x - 2, 0, x + 2, 0)
        col_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        col_grad.setColorAt(0.5, QColor(122, 96, 16, 14))
        col_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(x - 2, 0, 4, h, col_grad)

    # Skyline
    rng = random.Random(1929)
    baseline = h - 25
    x_pos = 0
    while x_pos < w:
        bw = rng.randint(8, 22)
        bh = rng.randint(35, 160)
        sky_g = QLinearGradient(0, baseline - bh, 0, baseline + 25)
        sky_g.setColorAt(0.0, QColor("#080604"))
        sky_g.setColorAt(1.0, QColor("#040302"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(sky_g))
        p.drawRect(QRectF(x_pos, baseline - bh, bw, bh + 25))
        win = QColor("#E8C840")
        win.setAlpha(rng.randint(5, 16))
        p.setBrush(QBrush(win))
        for wy in range(int(baseline - bh + 4), baseline, 9):
            for wx in range(int(x_pos + 2), int(x_pos + bw - 2), 5):
                if rng.random() > 0.55:
                    p.drawRect(QRectF(wx, wy, 2, 3))
        x_pos += bw + rng.randint(2, 5)

    _star_dust(p, w, h, 1920, "#E8C840", 400, 45, 1.0)
    _star_dust(p, w, h, 1921, "#FFFFFF", 900, 25, 0.6)
    _warm_vignette(p, w, h, 80)


def _paint_golden_axis(p: QPainter, w: int, h: int) -> None:
    """Central golden axis with diamond jewels."""
    cx = w // 2

    shadow = QColor(0, 0, 0, 120)
    p.setPen(QPen(shadow, 3.0))
    p.drawLine(QPointF(cx + 1, 0), QPointF(cx + 1, h))

    _gold_emboss_line(p, cx - 2, 0, cx - 2, h, 1.2)
    _gold_emboss_line(p, cx + 2, 0, cx + 2, h, 0.8)

    for y in range(40, h, 80):
        glow = QRadialGradient(cx, y, 10)
        glow.setColorAt(0.0, QColor(212, 175, 55, 80))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(cx, y), 8, 8)

        p.setBrush(QBrush(QColor("#D4AF37")))
        path = QPainterPath()
        path.moveTo(cx, y - 6)
        path.lineTo(cx + 6, y)
        path.lineTo(cx, y + 6)
        path.lineTo(cx - 6, y)
        path.closeSubpath()
        p.drawPath(path)

        p.setBrush(QBrush(QColor("#FFE87C")))
        inner = QPainterPath()
        inner.moveTo(cx, y - 2)
        inner.lineTo(cx + 2, y)
        inner.lineTo(cx, y + 2)
        inner.lineTo(cx - 2, y)
        inner.closeSubpath()
        p.drawPath(inner)


# ═══════════════════════════════════════════════════════════════
#  TEXTURED SCROLL AREA — replaces flat black backgrounds
# ═══════════════════════════════════════════════════════════════


class MysticScrollContent(QWidget):
    """Inner content widget that paints a generated mystical texture."""

    def __init__(self, theme: str = "divine", parent: QWidget | None = None):
        super().__init__(parent)
        self._theme = theme
        self._cached_bg: QPixmap | None = None
        self._cached_size: tuple[int, int] = (0, 0)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if (w, h) != self._cached_size or self._cached_bg is None:
            if self._theme == "divine":
                self._cached_bg = gen_mystic_dark_bg(w, h)
            elif self._theme == "ny":
                self._cached_bg = gen_ny_dark_bg(w, h)
            else:
                p.fillRect(0, 0, w, h, QColor("#0D0D14"))
                p.end()
                return
            self._cached_size = (w, h)

        p.drawPixmap(0, 0, self._cached_bg)
        p.end()


class MysticCardFrame(QFrame):
    """QFrame with generated card texture background."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bg = gen_mystic_card_bg(w, h)
        p.drawPixmap(0, 0, bg)
        p.end()
        super().paintEvent(event)


# ═══════════════════════════════════════════════════════════════
#  GLOW LABEL — gold/silver text with luminous halo + star dust
# ═══════════════════════════════════════════════════════════════


class GlowLabel(QLabel):
    """Label with gold/silver text glow, pearlescent shimmer, star dust.

    glow_color: color of the text halo (e.g. "#D4AF37" for gold)
    text_color: main text color
    glow_radius: how far the glow extends (1-5)
    stars: whether to scatter tiny stars around text
    """

    def __init__(self, text: str = "", glow_color: str = "#D4AF37",
                 text_color: str = "#FFD700", glow_radius: int = 3,
                 stars: bool = True, parent: QWidget | None = None):
        super().__init__(text, parent)
        self._glow_color = glow_color
        self._text_color = text_color
        self._glow_radius = glow_radius
        self._stars = stars
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setFont(self.font())

        rect = self.rect()
        text = self.text()
        alignment = self.alignment()

        # Star dust behind text
        if self._stars:
            _star_dust(p, rect.width(), rect.height(), hash(text) & 0xFFFF,
                       self._glow_color, 800, 40, 0.8)

        # Glow layers (outer to inner, decreasing alpha)
        gc = QColor(self._glow_color)
        for i in range(self._glow_radius, 0, -1):
            gc.setAlpha(12 + (self._glow_radius - i) * 8)
            p.setPen(gc)
            for dx in range(-i, i + 1):
                for dy in range(-i, i + 1):
                    if dx * dx + dy * dy <= i * i:
                        p.drawText(rect.adjusted(dx, dy, dx, dy), alignment, text)

        # Main text
        p.setPen(QColor(self._text_color))
        p.drawText(rect, alignment, text)

        # Specular highlight on text (top half brighter)
        spec = QColor("#FFFFFF")
        spec.setAlpha(30)
        p.setPen(spec)
        clip_rect = QRectF(0, 0, rect.width(), rect.height() * 0.45)
        p.setClipRect(clip_rect)
        p.drawText(rect, alignment, text)
        p.setClipping(False)

        p.end()


# ═══════════════════════════════════════════════════════════════
#  ORIGINAL WIDGETS (updated, no photo_textures)
# ═══════════════════════════════════════════════════════════════


class GoldBorderFrame(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        _gold_emboss_line(p, 1, 1, w - 1, 1, 1.5)
        _gold_emboss_line(p, 1, h - 1, w - 1, h - 1, 1.5)
        _gold_emboss_line(p, 1, 1, 1, h - 1, 1.5)
        _gold_emboss_line(p, w - 1, 1, w - 1, h - 1, 1.5)

        p.setPen(QPen(QColor("#D4AF37"), 0.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(4, 4, w - 8, h - 8))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#D4AF37")))
        for cx_c, cy_c, sx, sy in [(0, 0, 1, 1), (w, 0, -1, 1),
                                     (0, h, 1, -1), (w, h, -1, -1)]:
            path = QPainterPath()
            path.moveTo(cx_c + 2 * sx, cy_c + 2 * sy)
            path.lineTo(cx_c + 14 * sx, cy_c + 2 * sy)
            path.lineTo(cx_c + 2 * sx, cy_c + 14 * sy)
            path.closeSubpath()
            p.drawPath(path)

        mid = w / 2
        diamond = QPainterPath()
        diamond.moveTo(mid, 0)
        diamond.lineTo(mid + 6, 4)
        diamond.lineTo(mid, 8)
        diamond.lineTo(mid - 6, 4)
        diamond.closeSubpath()
        p.drawPath(diamond)
        p.end()


class TexturedCard(QFrame):
    def __init__(self, texture: str = "dark", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._texture_type = texture

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bg = gen_mystic_card_bg(w, h)
        p.drawPixmap(0, 0, bg)
        _gold_emboss_line(p, 3, 3, w - 3, 3, 1.5)
        _gold_emboss_line(p, 3, h - 3, w - 3, h - 3, 1.5)
        _gold_emboss_line(p, 3, 3, 3, h - 3, 1.5)
        _gold_emboss_line(p, w - 3, 3, w - 3, h - 3, 1.5)
        p.end()


class AgentCard(QFrame):
    def __init__(self, icon_path: str, agent_name: str, agent_title: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(62)
        self._icon_file = _icon_path(icon_path) if not Path(icon_path).is_absolute() else Path(icon_path)
        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(36, 36)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_icon()
        layout.addWidget(self._icon_label)

        info = QVBoxLayout()
        info.setSpacing(1)
        name_lbl = GlowLabel(agent_name, "#D4AF37", "#FFD700", 2, True)
        name_lbl.setFont(QFont("Georgia", 9, QFont.Weight.Bold))
        info.addWidget(name_lbl)

        title_lbl = GlowLabel(agent_title, "#C0C0C0", "#EDE6D6", 1, False)
        title_lbl.setFont(QFont("Georgia", 8))
        info.addWidget(title_lbl)

        self._detail_label = QLabel()
        self._detail_label.setStyleSheet(
            "color: #D2B48C; font-size: 10px; font-family: Consolas; border: none; background: transparent;"
        )
        info.addWidget(self._detail_label)
        layout.addLayout(info, stretch=1)

        self._status_dot = QLabel("●")
        self._status_dot.setFixedWidth(20)
        self._status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_dot.setStyleSheet("color: #3CB371; font-size: 14px; border: none; background: transparent;")
        layout.addWidget(self._status_dot)

    @property
    def detail_label(self) -> QLabel:
        return self._detail_label

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = gen_mystic_card_bg(self.width(), self.height())
        p.drawPixmap(0, 0, bg)
        p.end()
        super().paintEvent(event)

    def _load_icon(self) -> None:
        if self._icon_file.exists() and QSvgRenderer is not None:
            renderer = QSvgRenderer(str(self._icon_file))
            pm = QPixmap(32, 32)
            pm.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pm)
            renderer.render(painter)
            painter.end()

            geo_bg = create_sacred_geometry_bg(36, 36)
            final = QPixmap(36, 36)
            final.fill(QColor(0, 0, 0, 0))
            fp = QPainter(final)
            fp.setRenderHint(QPainter.RenderHint.Antialiasing)
            fp.setOpacity(0.3)
            fp.drawPixmap(0, 0, geo_bg)
            fp.setOpacity(1.0)
            fp.setPen(Qt.PenStyle.NoPen)
            fp.setBrush(QBrush(QColor("#8B7424")))
            fp.drawEllipse(0, 0, 36, 36)
            fp.drawPixmap(2, 2, pm)
            fp.end()
            self._icon_label.setPixmap(final)
        else:
            self._icon_label.setText("?")
            self._icon_label.setStyleSheet(
                "color: #FFD700; font-size: 18px; background: #8B7424; border-radius: 18px; border: none;"
            )


class SacredSeparator(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(20)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        mid_y = self.height() / 2
        mid_x = w / 2

        _gold_emboss_line(p, 20, mid_y, mid_x - 30, mid_y, 0.8)
        _gold_emboss_line(p, mid_x + 30, mid_y, w - 20, mid_y, 0.8)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#D4AF37")))
        diamond = QPainterPath()
        diamond.moveTo(mid_x, mid_y - 6)
        diamond.lineTo(mid_x + 6, mid_y)
        diamond.lineTo(mid_x, mid_y + 6)
        diamond.lineTo(mid_x - 6, mid_y)
        diamond.closeSubpath()
        p.drawPath(diamond)

        p.setBrush(QBrush(QColor("#8B7424")))
        for ox in [mid_x - 22, mid_x + 22]:
            star = QPainterPath()
            star.moveTo(ox, mid_y - 4)
            star.lineTo(ox + 4, mid_y)
            star.lineTo(ox, mid_y + 4)
            star.lineTo(ox - 4, mid_y)
            star.closeSubpath()
            p.drawPath(star)
        p.end()


class DualismHeader(QWidget):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(48)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        header_bg = create_header_gradient(w, h)
        p.drawPixmap(0, 0, header_bg)
        _star_dust(p, w, h, 333, "#FFD700", 400, 50, 1.0)

        sun_size = min(h - 8, 40)
        sun_pm = create_dualism_sun(sun_size, sun_size)
        p.setOpacity(0.6)
        p.drawPixmap((w - sun_size) // 2, (h - sun_size) // 2, sun_pm)
        p.setOpacity(1.0)

        font = QFont("Georgia", 14, QFont.Weight.Bold)
        p.setFont(font)

        # Glow
        gc = QColor("#D4AF37")
        for r in range(3, 0, -1):
            gc.setAlpha(15 + (3 - r) * 10)
            p.setPen(gc)
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if dx * dx + dy * dy <= r * r:
                        p.drawText(QRectF(dx, dy, w, h), Qt.AlignmentFlag.AlignCenter, self._text)

        p.setPen(QColor("#FFD700"))
        p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self._text)
        p.end()


class IconLabel(QLabel):
    def __init__(self, icon_path: str, size: int = 24,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        svg_file = _icon_path(icon_path) if not Path(icon_path).is_absolute() else Path(icon_path)
        if svg_file.exists() and QSvgRenderer is not None:
            renderer = QSvgRenderer(str(svg_file))
            pm = QPixmap(size, size)
            pm.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pm)
            renderer.render(painter)
            painter.end()
            self.setPixmap(pm)
        else:
            self.setText("?")
            self.setStyleSheet(f"color: #D4AF37; font-size: {size // 2}px;")


class DualismSplitBackground(QWidget):
    """Main bg: Light (left) / Dark (right) + golden axis. Fully procedural."""
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        half = w // 2

        _paint_divine_light(p, half, h)
        p.save()
        p.translate(half, 0)
        _paint_divine_dark(p, half, h)
        p.restore()
        _paint_golden_axis(p, w, h)
        p.end()


class ArtDecoFrameHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)

    def paintEvent(self, event):
        p = QPainter(self)
        frame = create_art_deco_frame(self.width(), self.height())
        p.drawPixmap(0, 0, frame)
        p.end()


class LightSideButton(QPushButton):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(
            "QPushButton { background: #1A1A1A; color: #D4AF37; "
            "border: 1px solid #D4AF37; border-radius: 6px; "
            "padding: 6px 14px; font-family: 'Cinzel', 'Georgia'; "
            "font-size: 11px; letter-spacing: 2px; }"
            "QPushButton:hover { background: #2A2A20; border: 2px solid #FFD700; color: #FFD700; }"
            "QPushButton:pressed { background: #D4AF37; color: #0D0D0D; }"
        )


class DarkSideButton(QPushButton):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(
            "QPushButton { background: #1A0303; color: #CD7F32; "
            "border: 1px solid #6B0000; padding: 6px 14px; "
            "font-family: 'Cinzel', 'Georgia'; font-size: 11px; letter-spacing: 2px; }"
            "QPushButton:hover { background: #2A0808; border: 2px solid #8B0000; color: #E8D5D5; }"
            "QPushButton:pressed { background: #4A0000; color: #E8D5D5; }"
        )


class AlchemicalCircleWidget(QWidget):
    def __init__(self, size: int = 200, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawPixmap(0, 0, create_alchemical_circle(self._size, self._size))
        p.end()


class NYArtDecoBackground(QWidget):
    """Split bg: Gatsby cream (left) + Manhattan noir (right). Fully procedural."""
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        half = w // 2

        _paint_ny_light(p, half, h)
        p.save()
        p.translate(half, 0)
        _paint_ny_dark(p, half, h)
        p.restore()
        _paint_golden_axis(p, w, h)
        p.end()
