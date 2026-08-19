"""Download real photo textures for premium themes."""
import asyncio
import aiohttp
from pathlib import Path

TEXTURES_DIR = Path(__file__).parent / "textures_photo"

TEXTURE_URLS = {
    "black_velvet.jpg": "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800&q=80",
    "black_marble.jpg": "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?w=800&q=80",
    "gold_metal.jpg": "https://images.unsplash.com/photo-1624913503386-6af0a0c4f6c1?w=800&q=80",
    "parchment.jpg": "https://images.unsplash.com/photo-1541701494587-cb58502866ab?w=800&q=80",
    "dark_leather.jpg": "https://images.unsplash.com/photo-1531685250784-7569952593d2?w=800&q=80",
    "art_deco_gold.jpg": "https://images.unsplash.com/photo-1534120247760-c44c3e4a62f1?w=800&q=80",
    "dark_wood.jpg": "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=800&q=80",
    "cream_fabric.jpg": "https://images.unsplash.com/photo-1558171813-4c088753af8f?w=800&q=80",
    "manhattan_night.jpg": "https://images.unsplash.com/photo-1534430480872-3498386e7856?w=800&q=80",
    "bronze_metal.jpg": "https://images.unsplash.com/photo-1519638399535-1b036603ac77?w=800&q=80",
    "dark_stone.jpg": "https://images.unsplash.com/photo-1549317661-bd32c8ce0afa?w=800&q=80",
    "crimson_velvet.jpg": "https://images.unsplash.com/photo-1557682250-33bd709cbe85?w=800&q=80",
}


async def download_textures():
    """Download all texture photos."""
    TEXTURES_DIR.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        for filename, url in TEXTURE_URLS.items():
            path = TEXTURES_DIR / filename
            if path.exists():
                print(f"  ✓ {filename} (already exists)")
                continue
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        path.write_bytes(data)
                        print(f"  ✓ {filename} ({len(data) // 1024}KB)")
                    else:
                        print(f"  ✗ {filename} (HTTP {resp.status})")
            except Exception as e:
                print(f"  ✗ {filename} ({e})")


def main():
    print("Downloading photo textures...")
    asyncio.run(download_textures())
    print("Done!")


if __name__ == "__main__":
    main()
