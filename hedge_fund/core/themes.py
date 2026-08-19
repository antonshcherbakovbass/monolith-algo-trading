"""Theme engine with skins for the MONOLITH GUI."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class Theme:
    id: str
    name_ru: str
    name_en: str
    description_ru: str
    description_en: str
    colors: dict[str, str]
    fonts: dict[str, str] = field(default_factory=dict)
    icons: dict[str, str] = field(default_factory=dict)
    decorations: dict[str, str] = field(default_factory=dict)
    icon_paths: dict[str, str] = field(default_factory=dict)


class ThemeManager:
    _current_theme: str = "dark_alchemy"
    _themes: dict[str, Theme] = {}

    @classmethod
    def register(cls, theme: Theme) -> None:
        cls._themes[theme.id] = theme

    @classmethod
    def set_theme(cls, theme_id: str) -> None:
        if theme_id in cls._themes:
            cls._current_theme = theme_id

    @classmethod
    def get_theme(cls) -> Theme:
        return cls._themes[cls._current_theme]

    @classmethod
    def get_color(cls, key: str) -> str:
        return cls._themes[cls._current_theme].colors.get(key, "#FFFFFF")

    @classmethod
    def get_icon(cls, key: str) -> str:
        return cls._themes[cls._current_theme].icons.get(key, "")

    @classmethod
    def get_icon_path(cls, key: str) -> str:
        return cls._themes[cls._current_theme].icon_paths.get(key, "")

    @classmethod
    def available_themes(cls) -> list[dict]:
        return [
            {"id": t.id, "name_ru": t.name_ru, "name_en": t.name_en,
             "description_ru": t.description_ru, "description_en": t.description_en}
            for t in cls._themes.values()
        ]

    @classmethod
    def save_preference(cls) -> None:
        path = Path(__file__).parent.parent / "config" / "theme.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"theme": cls._current_theme}, f)

    @classmethod
    def load_preference(cls) -> None:
        path = Path(__file__).parent.parent / "config" / "theme.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                theme_id = data.get("theme", "dark_alchemy")
                if theme_id in cls._themes:
                    cls._current_theme = theme_id
            except (json.JSONDecodeError, OSError):
                pass


def C(key: str) -> str:
    return ThemeManager.get_color(key)


def IC(key: str) -> str:
    return ThemeManager.get_icon(key)


# ── Theme 1: Dark Alchemy ─────────────────────────────────────

_dark_alchemy = Theme(
    id="dark_alchemy",
    name_ru="Тёмная Алхимия",
    name_en="Dark Alchemy",
    description_ru="Тёмная тема в стиле Арт-Деко с золотыми акцентами",
    description_en="Dark Art Deco theme with golden accents",
    colors={
        "bg_void": "#0A0A0F",
        "bg_dark": "#0D0D14",
        "bg_card": "#13131F",
        "bg_card_hover": "#1A1A2A",
        "gold": "#D4AF37",
        "gold_light": "#F0D060",
        "gold_dim": "#8B7424",
        "crimson": "#8B0000",
        "crimson_bright": "#DC143C",
        "crimson_dim": "#4A0010",
        "ivory": "#FAEBD7",
        "ivory_dim": "#B8A88A",
        "obsidian": "#1A1A2E",
        "emerald": "#50C878",
        "emerald_bright": "#50C878",
        "bronze": "#CD7F32",
        "silver": "#C0C0C0",
        "positive": "#50C878",
        "negative": "#DC143C",
        "neutral": "#B8A88A",
        "accent": "#D4AF37",
        "text_primary": "#FAEBD7",
        "text_secondary": "#B8A88A",
        "border": "#8B7424",
        "border_active": "#D4AF37",
    },
    fonts={
        "primary": "Segoe UI",
        "mono": "Consolas",
        "size_title": "16px",
        "size_normal": "12px",
        "size_small": "10px",
    },
    icons={
        "orchestrator": "⚜",
        "scalping": "⚡",
        "day_trading": "☀",
        "long_term": "Ω",
        "news": "☿",
        "risk": "⚖",
        "quant": "◎",
        "hedging": "☊",
        "sre": "⚙",
        "buy": "△",
        "sell": "▽",
        "stop": "⛔",
        "health_ok": "🟢",
        "health_warn": "🟡",
        "health_bad": "🔴",
        "separator": "◆",
        "section": "◇",
    },
    decorations={
        "card_border_radius": "4px",
        "card_border_width": "1px",
    },
)

# ── Theme 2: Clear Vision (Colorblind) ───────────────────────

_colorblind = Theme(
    id="colorblind",
    name_ru="Чистое Зрение — для дальтоников",
    name_en="Clear Vision — Colorblind Friendly",
    description_ru="Высококонтрастная тема с безопасными цветами для людей с нарушением цветового восприятия",
    description_en="High contrast theme with safe colors for color vision deficiency",
    colors={
        "bg_void": "#FAFAFA",
        "bg_dark": "#F0F0F0",
        "bg_card": "#FFFFFF",
        "bg_card_hover": "#E8E8E8",
        "gold": "#0072B2",
        "gold_light": "#56B4E9",
        "gold_dim": "#005580",
        "crimson": "#D55E00",
        "crimson_bright": "#E69F00",
        "crimson_dim": "#A04000",
        "ivory": "#1A1A1A",
        "ivory_dim": "#555555",
        "obsidian": "#E0E0E8",
        "emerald": "#009E73",
        "emerald_bright": "#009E73",
        "bronze": "#CC79A7",
        "silver": "#666666",
        "positive": "#009E73",
        "negative": "#D55E00",
        "neutral": "#555555",
        "accent": "#0072B2",
        "text_primary": "#1A1A1A",
        "text_secondary": "#555555",
        "border": "#BBBBBB",
        "border_active": "#0072B2",
    },
    fonts={
        "primary": "Segoe UI",
        "mono": "Consolas",
        "size_title": "16px",
        "size_normal": "13px",
        "size_small": "11px",
    },
    icons={
        "orchestrator": "👑",
        "scalping": "⚡",
        "day_trading": "📊",
        "long_term": "📈",
        "news": "📰",
        "risk": "🛡",
        "quant": "🔬",
        "hedging": "🔒",
        "sre": "⚙",
        "buy": "▲ BUY",
        "sell": "▼ SELL",
        "stop": "■ STOP",
        "health_ok": "✔ OK",
        "health_warn": "⚠ WARN",
        "health_bad": "✖ ALERT",
        "separator": "─",
        "section": "■",
    },
    decorations={
        "card_border_radius": "4px",
        "card_border_width": "1px",
    },
)

# ── Theme 3: Divine Dualism ───────────────────────────────────

_divine_dualism = Theme(
    id="divine_dualism",
    name_ru="Божественный Дуализм — Свет и Тьма",
    name_en="Divine Dualism — Light & Shadow",
    description_ru="Мистическая тема — священная геометрия, алхимия, дуализм света и тени.",
    description_en="Mystical Art Deco — sacred geometry, alchemy, dualism of light and shadow.",
    colors={
        "bg_void": "#08080C",
        "bg_dark": "#0C0C12",
        "bg_card": "#14121E",
        "bg_card_hover": "#1C1A2A",
        "light_bg": "#F5F0E0",
        "light_bg_soft": "#EDE6D0",
        "light_card": "#FAF8F0",
        "light_text": "#1A1A1A",
        "light_text_dim": "#555544",
        "light_accent": "#D4AF37",
        "light_accent_bright": "#FFD700",
        "light_accent_dim": "#B8960C",
        "light_border": "#D4AF37",
        "dark_bg": "#140808",
        "dark_bg_soft": "#1E0C0C",
        "dark_card": "#1A0606",
        "dark_text": "#E8D5D5",
        "dark_text_dim": "#8B6666",
        "dark_accent": "#8B4513",
        "dark_accent_bright": "#CD7F32",
        "dark_accent_dim": "#5C3317",
        "dark_border": "#6B0000",
        "dark_crimson": "#3A0000",
        "dark_crimson_bright": "#8B0000",
        "gold": "#D4AF37",
        "gold_light": "#FFD700",
        "gold_dim": "#8B7424",
        "crimson": "#6B0000",
        "crimson_bright": "#8B0000",
        "ivory": "#EDE6D6",
        "ivory_dim": "#C8B888",
        "obsidian": "#08080C",
        "emerald": "#2E8B57",
        "emerald_bright": "#3CB371",
        "bronze": "#CD7F32",
        "copper": "#B87333",
        "gunmetal": "#2C3539",
        "silver": "#C0C0C0",
        "purple": "#4A0040",
        "positive": "#3CB371",
        "negative": "#8B0000",
        "neutral": "#C8B888",
        "accent": "#D4AF37",
        "text_primary": "#EDE6D6",
        "text_secondary": "#C8B888",
        "border": "#8B7424",
        "border_active": "#FFD700",
        "axis_line": "#D4AF37",
    },
    fonts={
        "display": "Cinzel Decorative",
        "header": "Cinzel",
        "primary": "Marcellus",
        "mono": "Consolas",
        "size_title": "20px",
        "size_header": "14px",
        "size_normal": "12px",
        "size_small": "10px",
    },
    icons={
        "orchestrator": "☥",
        "scalping": "⚡",
        "day_trading": "☉",
        "long_term": "∞",
        "news": "☿",
        "risk": "⚖",
        "quant": "⊛",
        "hedging": "☊",
        "sre": "⚙",
        "buy": "▲",
        "sell": "▼",
        "stop": "✝",
        "health_ok": "☮",
        "health_warn": "⚠",
        "health_bad": "☠",
        "separator": "✧",
        "section": "❖",
        "ornament_left": "╠═══",
        "ornament_right": "═══╣",
        "title_ornament": "⟐",
        "sacred_bull": "𓃾",
        "sacred_eye": "𓂀",
        "phoenix": "🔥",
        "serpent": "🐍",
        "chalice": "🏆",
        "skull": "💀",
        "yin_yang": "☯",
    },
    decorations={
        "card_border_radius": "4px",
        "card_border_width": "2px",
        "title_letter_spacing": "8px",
        "header_letter_spacing": "4px",
        "use_gradients": "true",
        "gradient_dark": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0C0C14, stop:1 #1C1C28)",
        "gradient_gold": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #B8860B, stop:0.5 #FFD700, stop:1 #B8860B)",
        "gradient_light": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFF8EE, stop:1 #F5F0E8)",
        "ornament_style": "double_line_diamond",
    },
    icon_paths={
        "orchestrator": "assets/icons/crown.svg",
        "scalping": "assets/icons/zap.svg",
        "day_trading": "assets/icons/sun.svg",
        "long_term": "assets/icons/infinity.svg",
        "news": "assets/icons/newspaper.svg",
        "risk": "assets/icons/shield.svg",
        "quant": "assets/icons/atom.svg",
        "hedging": "assets/icons/lock.svg",
        "sre": "assets/icons/settings.svg",
        "buy": "assets/icons/trending-up.svg",
        "sell": "assets/icons/trending-down.svg",
        "stop": "assets/icons/octagon-x.svg",
        "health_ok": "assets/icons/circle-check.svg",
        "health_warn": "assets/icons/triangle-alert.svg",
        "health_bad": "assets/icons/circle-x.svg",
        "wallet": "assets/icons/wallet.svg",
        "chart": "assets/icons/bar-chart-3.svg",
        "activity": "assets/icons/activity.svg",
        "agents": "assets/icons/users.svg",
        "monitor": "assets/icons/eye.svg",
        "alerts": "assets/icons/bell.svg",
        "save": "assets/icons/save.svg",
        "launch": "assets/icons/play.svg",
        "close": "assets/icons/x.svg",
        "language": "assets/icons/languages.svg",
        "theme": "assets/icons/palette.svg",
        "help": "assets/icons/help-circle.svg",
        "broker": "assets/icons/globe.svg",
        "telegram": "assets/icons/send.svg",
        "ai": "assets/icons/brain.svg",
        "safety": "assets/icons/shield-check.svg",
        "instruments": "assets/icons/list.svg",
        "mode": "assets/icons/sliders.svg",
    },
)

_ny_art_deco = Theme(
    id="ny_art_deco",
    name_ru="NY Art Deco 1920s",
    name_en="NY Art Deco 1920s",
    description_ru="Симметричный раскол Свет/Тьма в стиле Art Deco Нью-Йорка 1920-х",
    description_en="Symmetric Light/Dark split inspired by 1920s Manhattan Art Deco",
    colors={
        "bg_void": "#0A0A12",
        "bg_dark": "#12121E",
        "bg_card": "#1A1A2C",
        "bg_card_hover": "#222236",
        "bg_light": "#FAF5EB",
        "bg_light_card": "#F0E8D8",
        "gold": "#C9A84C",
        "gold_light": "#E8C859",
        "gold_dim": "#8B7532",
        "gold_bright": "#E8C859",
        "crimson": "#6B2020",
        "crimson_bright": "#C45555",
        "crimson_dim": "#3A1010",
        "ivory": "#FFFFF0",
        "ivory_dim": "#A89878",
        "text_light": "#FAF5EB",
        "text_dark": "#1A1A2C",
        "text_muted": "#8888AA",
        "text_primary": "#FFFFF0",
        "text_secondary": "#A89878",
        "accent_warm": "#D4A574",
        "accent_cool": "#7B9EB8",
        "divine_white": "#FFFDF5",
        "chaos_black": "#08080E",
        "success": "#5B9E5B",
        "danger": "#C45555",
        "warning": "#D4A84C",
        "info": "#6B8EB8",
        "positive": "#5B9E5B",
        "negative": "#C45555",
        "neutral": "#A89878",
        "accent": "#C9A84C",
        "copper": "#B87333",
        "marble": "#E8E0D0",
        "obsidian": "#0E0E18",
        "chrome": "#C0C8D0",
        "emerald": "#2D6B4A",
        "emerald_bright": "#3D8B5A",
        "ruby": "#8B2D4A",
        "bronze": "#B87333",
        "silver": "#C0C8D0",
        "border": "#8B7532",
        "border_active": "#C9A84C",
        "border_gold": "#C9A84C55",
    },
    fonts={
        "display": "Playfair Display",
        "header": "Cormorant Garamond",
        "primary": "Lato",
        "mono": "Consolas",
        "size_title": "22px",
        "size_header": "15px",
        "size_normal": "12px",
        "size_small": "10px",
    },
    icons={
        "orchestrator": "♚",
        "scalping": "⚡",
        "day_trading": "☀",
        "long_term": "∞",
        "news": "✉",
        "risk": "⚖",
        "quant": "⊛",
        "hedging": "☊",
        "sre": "⚙",
        "buy": "△",
        "sell": "▽",
        "stop": "■",
        "health_ok": "◉",
        "health_warn": "◈",
        "health_bad": "◎",
        "separator": "◆",
        "section": "❖",
        "ornament_left": "╔═══",
        "ornament_right": "═══╗",
        "title_ornament": "◆",
        "chrysler": "🏙",
        "eagle": "🦅",
        "compass": "🧭",
        "fanlight": "☀",
        "keystone": "🔑",
        "chevron": "❯",
    },
    decorations={
        "card_border_radius": "2px",
        "card_border_width": "1px",
        "title_letter_spacing": "10px",
        "header_letter_spacing": "5px",
        "use_gradients": "true",
        "gradient_dark": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A0A12, stop:1 #1A1A2C)",
        "gradient_gold": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B7532, stop:0.5 #C9A84C, stop:1 #8B7532)",
        "gradient_light": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FAF5EB, stop:1 #F0E8D8)",
        "gradient_chrome": "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #D0D8E0, stop:0.5 #F0F0F0, stop:1 #C0C8D0)",
        "ornament_style": "chevron_sunburst",
        "split_mode": "vertical_50_50",
    },
    icon_paths={
        "orchestrator": "assets/icons/crown.svg",
        "scalping": "assets/icons/zap.svg",
        "day_trading": "assets/icons/sun.svg",
        "long_term": "assets/icons/infinity.svg",
        "news": "assets/icons/newspaper.svg",
        "risk": "assets/icons/shield.svg",
        "quant": "assets/icons/atom.svg",
        "hedging": "assets/icons/lock.svg",
        "sre": "assets/icons/settings.svg",
        "buy": "assets/icons/trending-up.svg",
        "sell": "assets/icons/trending-down.svg",
        "stop": "assets/icons/octagon-x.svg",
        "health_ok": "assets/icons/circle-check.svg",
        "health_warn": "assets/icons/triangle-alert.svg",
        "health_bad": "assets/icons/circle-x.svg",
        "wallet": "assets/icons/wallet.svg",
        "chart": "assets/icons/bar-chart-3.svg",
        "activity": "assets/icons/activity.svg",
        "agents": "assets/icons/users.svg",
        "monitor": "assets/icons/eye.svg",
        "alerts": "assets/icons/bell.svg",
        "save": "assets/icons/save.svg",
        "launch": "assets/icons/play.svg",
        "close": "assets/icons/x.svg",
        "language": "assets/icons/languages.svg",
        "theme": "assets/icons/palette.svg",
        "help": "assets/icons/help-circle.svg",
        "broker": "assets/icons/globe.svg",
        "telegram": "assets/icons/send.svg",
        "ai": "assets/icons/brain.svg",
        "safety": "assets/icons/shield-check.svg",
        "instruments": "assets/icons/list.svg",
        "mode": "assets/icons/sliders.svg",
    },
)

# ── Register all themes on import ─────────────────────────────

ThemeManager.register(_dark_alchemy)
ThemeManager.register(_colorblind)
ThemeManager.register(_divine_dualism)
ThemeManager.register(_ny_art_deco)
ThemeManager.load_preference()
