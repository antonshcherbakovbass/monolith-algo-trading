"""Download free icons from Lucide (ISC license) for the Divine Dualism theme."""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiohttp

ICONS_DIR = Path(__file__).parent / "icons"

ICONS_TO_DOWNLOAD = {
    # Agent icons
    "crown.svg": "crown",
    "zap.svg": "zap",
    "sun.svg": "sun",
    "infinity.svg": "infinity",
    "newspaper.svg": "newspaper",
    "shield.svg": "shield",
    "atom.svg": "atom",
    "lock.svg": "lock",
    "settings.svg": "settings",
    # Action icons
    "trending-up.svg": "trending-up",
    "trending-down.svg": "trending-down",
    "octagon-x.svg": "octagon-x",
    "circle-check.svg": "circle-check",
    "triangle-alert.svg": "triangle-alert",
    "circle-x.svg": "circle-x",
    # UI icons
    "wallet.svg": "wallet",
    "bar-chart-3.svg": "bar-chart-3",
    "activity.svg": "activity",
    "users.svg": "users",
    "eye.svg": "eye",
    "bell.svg": "bell",
    "save.svg": "save",
    "play.svg": "play",
    "x.svg": "x",
    "languages.svg": "languages",
    "palette.svg": "palette",
    "help-circle.svg": "help-circle",
    "globe.svg": "globe",
    "send.svg": "send",
    "brain.svg": "brain",
    "shield-check.svg": "shield-check",
    "list.svg": "list",
    "sliders.svg": "sliders",
}

BASE_URL = "https://unpkg.com/lucide-static@latest/icons"


async def download_icons() -> None:
    """Download all missing icons from unpkg/lucide."""
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        tasks = []
        for filename, icon_name in ICONS_TO_DOWNLOAD.items():
            path = ICONS_DIR / filename
            if path.exists():
                continue
            tasks.append(_download_one(session, icon_name, path))
        if tasks:
            await asyncio.gather(*tasks)


async def _download_one(
    session: aiohttp.ClientSession, icon_name: str, path: Path
) -> None:
    url = f"{BASE_URL}/{icon_name}.svg"
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.read()
                path.write_bytes(data)
                print(f"  ✓ {path.name}")
            else:
                print(f"  ✗ {path.name} (HTTP {resp.status})")
    except Exception as exc:
        print(f"  ✗ {path.name} ({exc})")


def download_icons_sync() -> None:
    """Synchronous wrapper."""
    asyncio.run(download_icons())


if __name__ == "__main__":
    print("Downloading Lucide icons…")
    download_icons_sync()
    print("Done.")
