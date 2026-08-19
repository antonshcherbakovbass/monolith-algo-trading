"""Ensure all required assets are available."""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiohttp

ASSETS_DIR = Path(__file__).parent
ICONS_DIR = ASSETS_DIR / "icons"

_ALL_ICONS = {
    "crown.svg", "zap.svg", "sun.svg", "infinity.svg",
    "newspaper.svg", "shield.svg", "atom.svg", "lock.svg",
    "settings.svg", "trending-up.svg", "trending-down.svg",
    "octagon-x.svg", "circle-check.svg", "triangle-alert.svg",
    "circle-x.svg", "wallet.svg", "bar-chart-3.svg",
    "activity.svg", "users.svg", "eye.svg", "bell.svg",
    "save.svg", "play.svg", "x.svg", "languages.svg",
    "palette.svg", "help-circle.svg", "globe.svg",
    "send.svg", "brain.svg", "shield-check.svg",
    "list.svg", "sliders.svg",
}


async def ensure_icons() -> None:
    """Download missing icons from unpkg/lucide."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    base_url = "https://unpkg.com/lucide-static@latest/icons"

    async with aiohttp.ClientSession() as session:
        for icon in _ALL_ICONS:
            path = ICONS_DIR / icon
            if path.exists():
                continue
            url = f"{base_url}/{icon}"
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        path.write_bytes(data)
            except Exception:
                pass


def ensure_icons_sync() -> None:
    """Synchronous wrapper."""
    asyncio.run(ensure_icons())


if __name__ == "__main__":
    ensure_icons_sync()
    print("Assets downloaded.")
