"""Load and blend photo textures for premium themes."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path

from PyQt6.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QRadialGradient, QBrush, QPen
from PyQt6.QtCore import Qt, QRectF

TEXTURES_DIR = Path(__file__).parent / "textures_photo"


def _load_texture(name: str, width: int, height: int) -> QPixmap | None:
    """Load a photo texture, scaled to fill the given dimensions."""
    path = TEXTURES_DIR / name
    if not path.exists():
        return None
    pm = QPixmap(str(path))
    if pm.isNull():
        return None
    return pm.scaled(width, height,
                     Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation).copy(0, 0, width, height)


def _darken(pm: QPixmap, alpha: int = 180) -> QPixmap:
    """Overlay a dark tint on a pixmap to make it usable as background."""
    result = QPixmap(pm)
    p = QPainter(result)
    p.fillRect(0, 0, result.width(), result.height(), QColor(0, 0, 0, alpha))
    p.end()
    return result


def _tint(pm: QPixmap, color: str, alpha: int = 100) -> QPixmap:
    """Add a color tint overlay."""
    result = QPixmap(pm)
    p = QPainter(result)
    c = QColor(color)
    c.setAlpha(alpha)
    p.fillRect(0, 0, result.width(), result.height(), c)
    p.end()
    return result


def _vignette(pm: QPixmap, strength: int = 120) -> QPixmap:
    """Add vignette (dark edges) for depth."""
    result = QPixmap(pm)
    p = QPainter(result)
    w, h = result.width(), result.height()
    vig = QRadialGradient(w * 0.5, h * 0.5, max(w, h) * 0.6)
    vig.setColorAt(0.0, QColor(0, 0, 0, 0))
    vig.setColorAt(0.7, QColor(0, 0, 0, 0))
    vig.setColorAt(1.0, QColor(0, 0, 0, strength))
    p.fillRect(0, 0, w, h, vig)
    p.end()
    return result


@lru_cache(maxsize=4)
def photo_velvet_bg(width: int = 800, height: int = 600) -> QPixmap:
    """Black velvet photo texture, darkened and vignetted for background use."""
    tex = _load_texture("black_velvet.jpg", width, height)
    if tex is None:
        from hedge_fund.assets.textures import create_dark_sanctum
        return create_dark_sanctum(width, height)
    tex = _darken(tex, 160)
    tex = _vignette(tex, 100)
    return tex


@lru_cache(maxsize=4)
def photo_marble_bg(width: int = 800, height: int = 600) -> QPixmap:
    """Dark marble with gold veins, heavily darkened for readability."""
    tex = _load_texture("black_marble.jpg", width, height)
    if tex is None:
        from hedge_fund.assets.textures import create_dark_sanctum
        return create_dark_sanctum(width, height)
    tex = _darken(tex, 170)
    tex = _tint(tex, "#D4AF37", 15)
    tex = _vignette(tex)
    return tex


@lru_cache(maxsize=4)
def photo_gold_header(width: int = 800, height: int = 80) -> QPixmap:
    """Brushed gold metal for headers, darkened to be subtle."""
    tex = _load_texture("gold_metal.jpg", width, height)
    if tex is None:
        from hedge_fund.assets.textures import create_header_gradient
        return create_header_gradient(width, height)
    tex = _darken(tex, 200)
    tex = _tint(tex, "#0A0A0F", 140)
    p = QPainter(tex)
    gold = QColor("#D4AF37")
    gold.setAlpha(180)
    p.setPen(QPen(gold, 2.0))
    p.drawLine(0, height - 1, width, height - 1)
    p.end()
    return tex


@lru_cache(maxsize=4)
def photo_parchment_bg(width: int = 400, height: int = 600) -> QPixmap:
    """Aged parchment for light-side panels."""
    tex = _load_texture("parchment.jpg", width, height)
    if tex is None:
        from hedge_fund.assets.textures import create_light_hemisphere
        return create_light_hemisphere(width, height)
    tex = _tint(tex, "#F5F0E0", 60)
    tex = _vignette(tex, 60)
    return tex


@lru_cache(maxsize=4)
def photo_leather_card(width: int = 400, height: int = 300) -> QPixmap:
    """Dark leather for card backgrounds."""
    tex = _load_texture("dark_leather.jpg", width, height)
    if tex is None:
        from hedge_fund.assets.textures import create_card_texture
        return create_card_texture(width, height)
    tex = _darken(tex, 180)
    tex = _vignette(tex, 80)
    return tex


@lru_cache(maxsize=4)
def photo_crimson_bg(width: int = 400, height: int = 600) -> QPixmap:
    """Crimson velvet for dark-side panels."""
    tex = _load_texture("crimson_velvet.jpg", width, height)
    if tex is None:
        from hedge_fund.assets.textures import create_dark_hemisphere
        return create_dark_hemisphere(width, height)
    tex = _darken(tex, 170)
    tex = _tint(tex, "#1A0303", 120)
    tex = _vignette(tex)
    return tex


@lru_cache(maxsize=4)
def photo_manhattan_bg(width: int = 400, height: int = 600) -> QPixmap:
    """Manhattan night skyline for NY Art Deco dark side."""
    tex = _load_texture("manhattan_night.jpg", width, height)
    if tex is None:
        from hedge_fund.assets.textures import create_ny_dark_panel
        return create_ny_dark_panel(width, height)
    tex = _darken(tex, 140)
    tex = _vignette(tex, 100)
    return tex


@lru_cache(maxsize=4)
def photo_cream_fabric(width: int = 400, height: int = 600) -> QPixmap:
    """Cream/ivory fabric for NY Art Deco light side."""
    tex = _load_texture("cream_fabric.jpg", width, height)
    if tex is None:
        from hedge_fund.assets.textures import create_ny_light_panel
        return create_ny_light_panel(width, height)
    tex = _tint(tex, "#F8F4E8", 80)
    tex = _vignette(tex, 40)
    return tex


@lru_cache(maxsize=4)
def photo_bronze_metal(width: int = 400, height: int = 80) -> QPixmap:
    """Bronze metal for dark-side headers/accents."""
    tex = _load_texture("bronze_metal.jpg", width, height)
    if tex is None:
        from hedge_fund.assets.textures import create_header_gradient
        return create_header_gradient(width, height)
    tex = _darken(tex, 180)
    return tex
