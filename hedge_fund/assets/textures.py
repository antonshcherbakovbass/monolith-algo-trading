"""AAA-quality textures for Divine Dualism theme.

Visual style: black velvet with gold embossing, specular highlights,
depth shadows, and luxurious material feel.
"""
from __future__ import annotations
import math
import random
from functools import lru_cache
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QPainterPath,
    QLinearGradient, QRadialGradient, QConicalGradient, QFont,
)
from PyQt6.QtCore import Qt, QPointF, QRectF


# ─── Utility helpers ───

def _velvet_base(p: QPainter, w: int, h: int,
                 base_color: str = "#0A0A0F",
                 mid_color: str = "#0E0E18",
                 highlight_color: str = "#14142A") -> None:
    """Fill with black velvet: layered radial gradients + subtle grain."""
    p.fillRect(0, 0, w, h, QColor(base_color))

    center_glow = QRadialGradient(w * 0.5, h * 0.4, max(w, h) * 0.6)
    center_glow.setColorAt(0.0, QColor(highlight_color))
    center_glow.setColorAt(0.4, QColor(mid_color))
    center_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, w, h, center_glow)

    vignette = QRadialGradient(w * 0.5, h * 0.5, max(w, h) * 0.7)
    vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
    vignette.setColorAt(0.7, QColor(0, 0, 0, 0))
    vignette.setColorAt(1.0, QColor(0, 0, 0, 80))
    p.fillRect(0, 0, w, h, vignette)

    grain = QColor("#FFFFFF")
    grain.setAlpha(3)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grain))
    rng = random.Random(42)
    for _ in range(w * h // 200):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        p.drawEllipse(QPointF(x, y), 0.5, 0.5)


def _specular_streak(p: QPainter, x: float, y: float,
                     length: float, angle_deg: float,
                     color: str = "#FFFFFF", alpha: int = 15) -> None:
    """Draw a subtle specular highlight streak."""
    c = QColor(color)
    c.setAlpha(alpha)
    rad = math.radians(angle_deg)
    dx = length * math.cos(rad)
    dy = length * math.sin(rad)

    grad = QLinearGradient(x, y, x + dx, y + dy)
    grad.setColorAt(0.0, QColor(0, 0, 0, 0))
    grad.setColorAt(0.3, c)
    grad.setColorAt(0.5, c)
    grad.setColorAt(1.0, QColor(0, 0, 0, 0))

    p.setPen(QPen(QBrush(grad), 2.0))
    p.drawLine(QPointF(x, y), QPointF(x + dx, y + dy))


def _gold_emboss_line(p: QPainter, x1: float, y1: float,
                      x2: float, y2: float, width: float = 1.5) -> None:
    """Draw a gold line with emboss effect (shadow + highlight)."""
    shadow = QColor("#000000")
    shadow.setAlpha(80)
    p.setPen(QPen(shadow, width))
    p.drawLine(QPointF(x1 + 1, y1 + 1), QPointF(x2 + 1, y2 + 1))

    p.setPen(QPen(QColor("#D4AF37"), width))
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    spec = QColor("#FFE87C")
    spec.setAlpha(40)
    p.setPen(QPen(spec, width * 0.5))
    p.drawLine(QPointF(x1, y1 - 0.5), QPointF(x2, y2 - 0.5))


def _gold_emboss_circle(p: QPainter, cx: float, cy: float,
                        r: float, width: float = 1.5) -> None:
    """Circle with embossed gold look."""
    shadow = QColor("#000000")
    shadow.setAlpha(60)
    p.setPen(QPen(shadow, width))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(cx + 1, cy + 1), r, r)

    p.setPen(QPen(QColor("#D4AF37"), width))
    p.drawEllipse(QPointF(cx, cy), r, r)

    spec = QColor("#FFE87C")
    spec.setAlpha(30)
    p.setPen(QPen(spec, width * 0.4))
    p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 200 * 16, 140 * 16)


# ─── Main textures ───

@lru_cache(maxsize=4)
def create_dark_sanctum(width: int = 600, height: int = 600) -> QPixmap:
    """Premium dark background with velvet depth and sacred geometry."""
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    _velvet_base(p, width, height)

    cx, cy = width // 2, height // 2
    for r_mult in [0.35, 0.25, 0.15]:
        _gold_emboss_circle(p, cx, cy, min(width, height) * r_mult, 0.8)

    r = min(width, height) * 0.35
    for i in range(3):
        a1 = math.radians(90 + 120 * i)
        a2 = math.radians(90 + 120 * (i + 1))
        _gold_emboss_line(p,
            cx + r * math.cos(a1), cy - r * math.sin(a1),
            cx + r * math.cos(a2), cy - r * math.sin(a2), 0.8)

    _specular_streak(p, width * 0.1, height * 0.2, 200, -15, "#D4AF37", 8)
    _specular_streak(p, width * 0.6, height * 0.7, 150, 10, "#FFFFFF", 6)

    orn = 35
    for cx_c, cy_c, dx, dy in [(0, 0, 1, 1), (width, 0, -1, 1),
                                 (0, height, 1, -1), (width, height, -1, -1)]:
        _gold_emboss_line(p, cx_c + 4*dx, cy_c + 2*dy, cx_c + orn*dx, cy_c + 2*dy, 1.2)
        _gold_emboss_line(p, cx_c + 2*dx, cy_c + 4*dy, cx_c + 2*dx, cy_c + orn*dy, 1.2)

    p.end()
    return pm


@lru_cache(maxsize=8)
def create_card_texture(width: int = 400, height: int = 300) -> QPixmap:
    """Premium card: velvet bg, embossed gold double border, gloss header band."""
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    _velvet_base(p, width, height, "#0C0C14", "#10101C", "#161628")

    gloss = QLinearGradient(0, 0, 0, 20)
    gloss.setColorAt(0.0, QColor(255, 255, 255, 8))
    gloss.setColorAt(0.5, QColor(255, 255, 255, 3))
    gloss.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, width, 20, gloss)

    _gold_emboss_line(p, 3, 3, width - 3, 3, 1.5)
    _gold_emboss_line(p, 3, height - 3, width - 3, height - 3, 1.5)
    _gold_emboss_line(p, 3, 3, 3, height - 3, 1.5)
    _gold_emboss_line(p, width - 3, 3, width - 3, height - 3, 1.5)

    inner_gold = QColor("#D4AF37")
    inner_gold.setAlpha(30)
    p.setPen(QPen(inner_gold, 0.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(QRectF(8, 8, width - 16, height - 16))

    for cx_d, cy_d in [(3, 3), (width-3, 3), (3, height-3), (width-3, height-3)]:
        glow = QRadialGradient(cx_d, cy_d, 10)
        glow.setColorAt(0.0, QColor("#D4AF37"))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx_d, cy_d), 8, 8)

        p.setBrush(QBrush(QColor("#D4AF37")))
        path = QPainterPath()
        path.moveTo(cx_d, cy_d - 4)
        path.lineTo(cx_d + 4, cy_d)
        path.lineTo(cx_d, cy_d + 4)
        path.lineTo(cx_d - 4, cy_d)
        path.closeSubpath()
        p.drawPath(path)

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_light_hemisphere(width: int = 400, height: int = 600) -> QPixmap:
    """Left side: Domain of Light. Velvet transitioning to warm ivory with depth."""
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    grad = QLinearGradient(0, 0, width, 0)
    grad.setColorAt(0.0, QColor("#0A0A0F"))
    grad.setColorAt(0.3, QColor("#1A1810"))
    grad.setColorAt(0.7, QColor("#3A3520"))
    grad.setColorAt(1.0, QColor("#4A4530"))
    p.fillRect(0, 0, width, height, grad)

    warm = QRadialGradient(width * 0.7, height * 0.3, max(width, height) * 0.5)
    warm.setColorAt(0.0, QColor(212, 175, 55, 20))
    warm.setColorAt(0.5, QColor(212, 175, 55, 5))
    warm.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, width, height, warm)

    grain = QColor("#D4AF37")
    grain.setAlpha(2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grain))
    rng = random.Random(101)
    for _ in range(width * height // 300):
        p.drawEllipse(QPointF(rng.randint(0, width), rng.randint(0, height)), 0.5, 0.5)

    cx_r, cy_r = width * 0.3, height * 0.5
    for i in range(24):
        angle = math.radians(15 * i)
        length = max(width, height) * 0.7
        ray_color = QColor("#D4AF37")
        ray_color.setAlpha(12 if i % 3 == 0 else 5)
        p.setPen(QPen(ray_color, 1.5 if i % 3 == 0 else 0.5))
        p.drawLine(QPointF(cx_r, cy_r),
                   QPointF(cx_r + length * math.cos(angle), cy_r + length * math.sin(angle)))

    for r in range(50, 250, 45):
        _gold_emboss_circle(p, cx_r, cy_r, r, 0.4)

    tri = QColor("#D4AF37")
    tri.setAlpha(8)
    p.setPen(QPen(tri, 0.5))
    for tx in range(40, width, 90):
        for ty in range(40, height, 110):
            s = 18
            p.drawLine(QPointF(tx, ty - s), QPointF(tx - s*0.6, ty + s*0.3))
            p.drawLine(QPointF(tx - s*0.6, ty + s*0.3), QPointF(tx + s*0.6, ty + s*0.3))
            p.drawLine(QPointF(tx + s*0.6, ty + s*0.3), QPointF(tx, ty - s))

    _specular_streak(p, width*0.2, height*0.1, 180, -10, "#FFE87C", 10)

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_dark_hemisphere(width: int = 400, height: int = 600) -> QPixmap:
    """Right side: Domain of Darkness. Velvet to blood crimson with depth."""
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    grad = QLinearGradient(0, 0, width, 0)
    grad.setColorAt(0.0, QColor("#0A0A0F"))
    grad.setColorAt(0.3, QColor("#140808"))
    grad.setColorAt(0.7, QColor("#200C0C"))
    grad.setColorAt(1.0, QColor("#2A1010"))
    p.fillRect(0, 0, width, height, grad)

    blood = QRadialGradient(width * 0.7, height * 0.6, max(width, height) * 0.5)
    blood.setColorAt(0.0, QColor(107, 0, 0, 25))
    blood.setColorAt(0.5, QColor(74, 0, 0, 10))
    blood.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, width, height, blood)

    grain = QColor("#8B0000")
    grain.setAlpha(2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grain))
    rng = random.Random(202)
    for _ in range(width * height // 300):
        p.drawEllipse(QPointF(rng.randint(0, width), rng.randint(0, height)), 0.5, 0.5)

    for y_start in range(0, height, 80):
        copper = QColor("#5C3317")
        copper.setAlpha(20)
        p.setPen(QPen(copper, 0.8))
        p.drawLine(QPointF(0, y_start), QPointF(width * 0.5, y_start + 40))
        p.drawLine(QPointF(width, y_start), QPointF(width * 0.5, y_start + 40))

    cx_o, cy_o = width * 0.65, height * 0.5
    for r in range(35, 220, 40):
        ouro = QColor("#6B0000")
        ouro.setAlpha(18)
        p.setPen(QPen(ouro, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(cx_o - r, cy_o - r, r * 2, r * 2), 30 * 16, 300 * 16)
        glow_c = QColor("#8B0000")
        glow_c.setAlpha(6)
        p.setPen(QPen(glow_c, 3.0))
        p.drawArc(QRectF(cx_o - r, cy_o - r, r * 2, r * 2), 30 * 16, 300 * 16)

    tri = QColor("#6B0000")
    tri.setAlpha(10)
    p.setPen(QPen(tri, 0.5))
    for tx in range(40, width, 90):
        for ty in range(40, height, 110):
            s = 18
            p.drawLine(QPointF(tx, ty + s), QPointF(tx - s*0.6, ty - s*0.3))
            p.drawLine(QPointF(tx - s*0.6, ty - s*0.3), QPointF(tx + s*0.6, ty - s*0.3))
            p.drawLine(QPointF(tx + s*0.6, ty - s*0.3), QPointF(tx, ty + s))

    _specular_streak(p, width*0.3, height*0.8, 150, 15, "#8B0000", 8)

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_header_gradient(width: int = 800, height: int = 80) -> QPixmap:
    """Premium header with glossy metallic effect and velvet depth."""
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    _velvet_base(p, width, height, "#080810", "#0C0C18", "#101020")

    gloss = QLinearGradient(0, 0, 0, height * 0.5)
    gloss.setColorAt(0.0, QColor(255, 255, 255, 12))
    gloss.setColorAt(0.3, QColor(255, 255, 255, 6))
    gloss.setColorAt(0.6, QColor(255, 255, 255, 2))
    gloss.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, width, int(height * 0.5), gloss)

    glow_line = QLinearGradient(0, height - 4, 0, height)
    glow_line.setColorAt(0.0, QColor("#D4AF37"))
    glow_line.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, height - 3, width, 3, glow_line)

    _gold_emboss_line(p, 0, height - 1, width, height - 1, 1.5)

    p.end()
    return pm


# Keep backward compat aliases
create_dark_marble = create_dark_sanctum
create_parchment = create_light_hemisphere


@lru_cache(maxsize=4)
def create_dualism_sun(width: int = 200, height: int = 200) -> QPixmap:
    """Dualism sun with premium metallic gold/cyan emboss."""
    pm = QPixmap(width, height)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    cx, cy = width // 2, height // 2
    face_r = min(width, height) * 0.3

    # Left (Sun) with emboss
    p.save()
    p.setClipRect(QRectF(0, 0, width / 2, height))

    glow = QRadialGradient(cx, cy, face_r * 1.6)
    glow.setColorAt(0.0, QColor(255, 215, 0, 30))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, width, height, glow)

    for i in range(12):
        angle = math.radians(30 * i)
        _gold_emboss_line(p,
            cx + face_r * 1.1 * math.cos(angle), cy + face_r * 1.1 * math.sin(angle),
            cx + face_r * 1.5 * math.cos(angle), cy + face_r * 1.5 * math.sin(angle), 2.0)
    _gold_emboss_circle(p, cx, cy, face_r, 2.5)

    p.restore()

    # Right (Skull) with crimson glow
    p.save()
    p.setClipRect(QRectF(width / 2, 0, width / 2, height))

    glow2 = QRadialGradient(cx, cy, face_r * 1.6)
    glow2.setColorAt(0.0, QColor(0, 206, 209, 20))
    glow2.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, width, height, glow2)

    cyan = QColor("#00CED1")
    p.setPen(QPen(cyan, 2.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(cx, cy), face_r, face_r)

    p.drawEllipse(QPointF(cx + face_r * 0.25, cy - face_r * 0.15), 8, 10)
    p.setPen(QPen(cyan, 1.0))
    teeth_y = cy + face_r * 0.35
    for j in range(-2, 4):
        p.drawLine(QPointF(cx + j * 5, teeth_y), QPointF(cx + j * 5, teeth_y + 6))

    p.restore()

    # Dividing line
    p.setPen(QPen(QColor(255, 255, 255, 100), 1.0))
    p.drawLine(QPointF(cx, cy - face_r * 1.6), QPointF(cx, cy + face_r * 1.6))

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_ornamental_border(width: int = 800, height: int = 8) -> QPixmap:
    """Embossed gold ornamental border."""
    pm = QPixmap(width, height)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    mid_y = height // 2
    mid_x = width // 2

    _gold_emboss_line(p, 30, mid_y, mid_x - 15, mid_y, 1.0)
    _gold_emboss_line(p, mid_x + 15, mid_y, width - 30, mid_y, 1.0)

    glow = QRadialGradient(mid_x, mid_y, 12)
    glow.setColorAt(0.0, QColor("#D4AF37"))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setBrush(QBrush(glow))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(mid_x, mid_y), 10, 10)

    p.setBrush(QBrush(QColor("#D4AF37")))
    path = QPainterPath()
    path.moveTo(mid_x, mid_y - 4)
    path.lineTo(mid_x + 5, mid_y)
    path.lineTo(mid_x, mid_y + 4)
    path.lineTo(mid_x - 5, mid_y)
    path.closeSubpath()
    p.drawPath(path)

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_sacred_geometry_bg(width: int = 400, height: int = 400) -> QPixmap:
    """Sacred geometry on velvet with embossed gold."""
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _velvet_base(p, width, height)

    cx, cy = width // 2, height // 2
    r = min(width, height) * 0.15

    _gold_emboss_circle(p, cx, cy, r, 0.6)
    for i in range(6):
        angle = math.radians(60 * i)
        _gold_emboss_circle(p, cx + r * math.cos(angle), cy + r * math.sin(angle), r, 0.4)

    points = [(cx, cy)]
    for i in range(6):
        angle = math.radians(60 * i)
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            _gold_emboss_line(p, points[i][0], points[i][1],
                            points[j][0], points[j][1], 0.3)

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_alchemical_circle(width: int = 300, height: int = 300) -> QPixmap:
    """Alchemical transmutation circle with embossed gold on velvet."""
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _velvet_base(p, width, height)

    cx, cy = width // 2, height // 2
    R = min(width, height) * 0.42

    _gold_emboss_circle(p, cx, cy, R, 1.2)
    _gold_emboss_circle(p, cx, cy, R * 0.95, 0.6)

    for i in range(3):
        a1 = math.radians(90 + 120 * i)
        a2 = math.radians(90 + 120 * (i + 1))
        _gold_emboss_line(p,
            cx + R * 0.75 * math.cos(a1), cy - R * 0.75 * math.sin(a1),
            cx + R * 0.75 * math.cos(a2), cy - R * 0.75 * math.sin(a2), 1.0)

    for i in range(4):
        a1 = math.radians(45 + 90 * i)
        a2 = math.radians(45 + 90 * (i + 1))
        _gold_emboss_line(p,
            cx + R * 0.55 * math.cos(a1), cy - R * 0.55 * math.sin(a1),
            cx + R * 0.55 * math.cos(a2), cy - R * 0.55 * math.sin(a2), 0.8)

    glow = QRadialGradient(cx, cy, 15)
    glow.setColorAt(0.0, QColor("#D4AF37"))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(glow))
    p.drawEllipse(QPointF(cx, cy), 12, 12)

    _gold_emboss_circle(p, cx, cy, 8, 1.5)
    p.setBrush(QBrush(QColor("#D4AF37")))
    p.drawEllipse(QPointF(cx, cy), 3, 3)

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_axis_line(height: int = 800) -> QPixmap:
    """Central axis with embossed gold and diamond glow."""
    pm = QPixmap(16, height)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    cx = 8
    _gold_emboss_line(p, cx - 2, 0, cx - 2, height, 1.0)
    _gold_emboss_line(p, cx + 2, 0, cx + 2, height, 0.8)

    for y in range(50, height, 100):
        glow = QRadialGradient(cx, y, 8)
        glow.setColorAt(0.0, QColor("#D4AF37"))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(cx, y), 6, 6)

        p.setBrush(QBrush(QColor("#D4AF37")))
        path = QPainterPath()
        path.moveTo(cx, y - 5)
        path.lineTo(cx + 5, y)
        path.lineTo(cx, y + 5)
        path.lineTo(cx - 5, y)
        path.closeSubpath()
        p.drawPath(path)

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_art_deco_frame(width: int = 800, height: int = 80) -> QPixmap:
    """Premium Art Deco frame with embossed gold and gloss."""
    pm = QPixmap(width, height)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    _gold_emboss_line(p, 45, 4, width - 45, 4, 2.0)
    _gold_emboss_line(p, 45, height - 4, width - 45, height - 4, 2.0)

    for cx_c, cy_c, dx, dy in [(0, 0, 1, 1), (width, 0, -1, 1),
                                 (0, height, 1, -1), (width, height, -1, -1)]:
        _gold_emboss_line(p, cx_c+4*dx, cy_c, cx_c+4*dx, cy_c+22*dy, 2.0)
        _gold_emboss_line(p, cx_c+4*dx, cy_c+22*dy, cx_c+18*dx, cy_c+22*dy, 2.0)
        _gold_emboss_line(p, cx_c+18*dx, cy_c+22*dy, cx_c+18*dx, cy_c+12*dy, 2.0)
        _gold_emboss_line(p, cx_c+18*dx, cy_c+12*dy, cx_c+45*dx, cy_c+12*dy, 2.0)
        _gold_emboss_line(p, cx_c+45*dx, cy_c+12*dy, cx_c+45*dx, cy_c+4*dy, 2.0)

    mid_x = width // 2
    glow = QRadialGradient(mid_x, 4, 12)
    glow.setColorAt(0.0, QColor(212, 175, 55, 60))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(glow))
    p.drawEllipse(QPointF(mid_x, 4), 10, 10)

    p.setBrush(QBrush(QColor("#D4AF37")))
    path = QPainterPath()
    path.moveTo(mid_x, -2)
    path.lineTo(mid_x + 7, 4)
    path.lineTo(mid_x, 10)
    path.lineTo(mid_x - 7, 4)
    path.closeSubpath()
    p.drawPath(path)

    p.end()
    return pm


# ── NY Art Deco 1920s Textures ────────────────────────────────

@lru_cache(maxsize=4)
def create_ny_light_panel(width: int = 400, height: int = 600) -> QPixmap:
    """Left panel: Gatsby white & gold."""
    import random as _rng_mod
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    grad = QLinearGradient(0, 0, width, 0)
    grad.setColorAt(0.0, QColor("#E8E0CC"))
    grad.setColorAt(0.5, QColor("#F8F4E8"))
    grad.setColorAt(1.0, QColor("#F0EAD6"))
    p.fillRect(0, 0, width, height, grad)

    stripe = QColor("#C5A028")
    stripe.setAlpha(8)
    p.setPen(QPen(stripe, 0.5))
    for x in range(0, width, 12):
        p.drawLine(x, 0, x, height)

    cx_fan = width // 2
    fan_gold = QColor("#C5A028")
    fan_gold.setAlpha(20)
    p.setPen(QPen(fan_gold, 1.0))
    for i in range(20):
        angle = math.radians(160 + i * (220 - 160) / 20)
        length = height * 0.8
        p.drawLine(QPointF(cx_fan, 0),
                   QPointF(cx_fan + length * math.cos(angle), length * math.sin(angle)))

    chev_gold = QColor("#C5A028")
    chev_gold.setAlpha(40)
    p.setPen(QPen(chev_gold, 1.5))
    for row in range(4):
        y_base = 8 + row * 10
        step = 20
        for x in range(0, width, step * 2):
            p.drawLine(x, y_base, x + step, y_base - 5)
            p.drawLine(x + step, y_base - 5, x + step * 2, y_base)

    dia = QColor("#9A7B15")
    dia.setAlpha(10)
    p.setPen(QPen(dia, 0.5))
    for x in range(0, width, 40):
        for y in range(0, height, 40):
            s = 8
            p.drawLine(QPointF(x + 20, y + 20 - s), QPointF(x + 20 + s, y + 20))
            p.drawLine(QPointF(x + 20 + s, y + 20), QPointF(x + 20, y + 20 + s))
            p.drawLine(QPointF(x + 20, y + 20 + s), QPointF(x + 20 - s, y + 20))
            p.drawLine(QPointF(x + 20 - s, y + 20), QPointF(x + 20, y + 20 - s))

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_ny_dark_panel(width: int = 400, height: int = 600) -> QPixmap:
    """Right panel: Manhattan Noir."""
    import random
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    _velvet_base(p, width, height, "#0A0A12", "#0E0E1A", "#121225")

    bronze = QColor("#8B5E3C")
    bronze.setAlpha(25)
    p.setPen(QPen(bronze, 1.0))
    for x in range(0, width, 50):
        p.drawLine(x, 0, x, height)
    for y in range(0, height, 80):
        p.drawLine(0, y, width, y)
        for x in range(10, width - 10, 50):
            p.drawLine(x, y, x + 10, y - 5)
            p.drawLine(x + 10, y - 5, x + 20, y)

    zig = QColor("#A0522D")
    zig.setAlpha(15)
    p.setPen(QPen(zig, 1.5))
    for cx_z in range(width // 4, width, width // 2):
        base_y = height * 0.3
        for step_i in range(5):
            w_step = 60 - step_i * 10
            y_step = base_y - step_i * 15
            p.drawLine(QPointF(cx_z - w_step, y_step), QPointF(cx_z + w_step, y_step))
            if step_i > 0:
                prev_w = 60 - (step_i - 1) * 10
                p.drawLine(QPointF(cx_z - prev_w, y_step + 15), QPointF(cx_z - w_step, y_step))
                p.drawLine(QPointF(cx_z + prev_w, y_step + 15), QPointF(cx_z + w_step, y_step))

    sky = QColor("#1A1A30")
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(sky))
    rng = random.Random(1920)
    baseline = height - 30
    x_pos = 0
    while x_pos < width:
        bw = rng.randint(8, 25)
        bh = rng.randint(30, 150)
        p.drawRect(QRectF(x_pos, baseline - bh, bw, bh + 30))
        win = QColor("#E8C840")
        win.setAlpha(rng.randint(5, 20))
        p.setBrush(QBrush(win))
        for wy in range(int(baseline - bh + 5), baseline, 10):
            for wx in range(int(x_pos + 2), int(x_pos + bw - 2), 5):
                if rng.random() > 0.6:
                    p.drawRect(QRectF(wx, wy, 2, 3))
        p.setBrush(QBrush(sky))
        x_pos += bw + rng.randint(2, 6)

    _specular_streak(p, width * 0.2, height * 0.15, 120, -20, "#CD853F", 10)

    p.end()
    return pm


@lru_cache(maxsize=4)
def create_ny_header(width: int = 800, height: int = 80) -> QPixmap:
    """1920s hotel lobby header: polished black marble with gold inlay."""
    pm = QPixmap(width, height)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    _velvet_base(p, width, height, "#060608", "#0A0A10", "#0E0E16")

    gloss = QLinearGradient(0, 0, 0, height)
    gloss.setColorAt(0.0, QColor(255, 255, 255, 15))
    gloss.setColorAt(0.25, QColor(255, 255, 255, 8))
    gloss.setColorAt(0.26, QColor(255, 255, 255, 2))
    gloss.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(0, 0, width, height, gloss)

    _gold_emboss_line(p, 50, 5, width - 50, 5, 2.0)
    _gold_emboss_line(p, 50, height - 5, width - 50, height - 5, 2.0)

    mid = width // 2
    p.setPen(QPen(QColor("#C5A028"), 1.5))
    for i in range(5):
        offset = i * 25
        y_chev = 5
        p.drawLine(QPointF(mid - offset, y_chev + 8), QPointF(mid, y_chev))
        p.drawLine(QPointF(mid, y_chev), QPointF(mid + offset, y_chev + 8))

    for cx_c, cy_c, dx, dy in [(0, 0, 1, 1), (width, 0, -1, 1),
                                 (0, height, 1, -1), (width, height, -1, -1)]:
        _gold_emboss_line(p, cx_c+4*dx, cy_c+2*dy, cx_c+4*dx, cy_c+25*dy, 1.5)
        _gold_emboss_line(p, cx_c+4*dx, cy_c+25*dy, cx_c+20*dx, cy_c+25*dy, 1.5)
        _gold_emboss_line(p, cx_c+20*dx, cy_c+25*dy, cx_c+20*dx, cy_c+14*dy, 1.5)
        _gold_emboss_line(p, cx_c+20*dx, cy_c+14*dy, cx_c+50*dx, cy_c+14*dy, 1.5)
        _gold_emboss_line(p, cx_c+50*dx, cy_c+14*dy, cx_c+50*dx, cy_c+5*dy, 1.5)

    p.end()
    return pm
