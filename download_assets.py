"""
One-time helper: fetch Unsplash photos into assets/musicians/.
Run this BEFORE compiling. Groove Trainer itself never goes online.

Usage:
    python download_assets.py
"""

from __future__ import annotations

import io
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parent
DEST = ROOT / "assets" / "musicians"
SIZE = 300

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/jpeg,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Referer": "https://unsplash.com/",
}

# filename -> (search keywords, direct Unsplash photo id fallback)
CATALOG: list[tuple[str, str, str]] = [
    ("paul_chambers.jpg", "jazz bass player upright", "photo-1511671782779-c97d3d27a1d4"),
    ("ron_carter.jpg", "jazz double bass concert", "photo-1487180144351-b8472da7d491"),
    ("charlie_haden.jpg", "acoustic jazz bassist stage", "photo-1514320291840-2e0a9bf2a9ae"),
    ("ray_brown.jpg", "jazz upright bass closeup", "photo-1470225620780-dba8ba36b745"),
    ("christian_mcbride.jpg", "modern jazz bass player", "photo-1519892300165-cb5542fb7c1c"),
    ("oscar_pettiford.jpg", "vintage jazz bass club", "photo-1415201364774-f6f0bb35cff6"),
    ("niels_henning_orsted_pedersen.jpg", "nordic jazz bass player", "photo-1507838153414-b4b713455d94"),
    ("scott_lafaro.jpg", "jazz trio bass wooden", "photo-1520523839897-bd0b52f945a0"),
    ("pino_palladino.jpg", "soul bass guitar player", "photo-1571330735066-03aaa9429d89"),
    ("bootsy_collins.jpg", "funk bassist live concert", "photo-1510915228340-29c85a43dcfe"),
    ("larry_graham.jpg", "slap bass funk stage", "photo-1564186763535-ebb7cd248465"),
    ("george_porter_jr.jpg", "new orleans funk bass", "photo-1525201548942-d8732f6617f0"),
    ("louis_johnson.jpg", "studio funk bass guitar", "photo-1511379938547-c1f69419868d"),
    ("verdine_white.jpg", "disco funk bass live", "photo-1513825585800-c47151016d35"),
    ("rocco_prestia.jpg", "funk bass fingers close", "photo-1598488035139-bdbb2231ce04"),
    ("flea.jpg", "rock concert bass player", "photo-1493225457124-a3eb161ffa5f"),
    ("robert_trujillo.jpg", "metal bass guitar live", "photo-1501612780327-450866c3840d"),
    ("john_entwistle.jpg", "classic rock bass concert", "photo-1459749411177-04de0392083f"),
    ("geezer_butler.jpg", "heavy rock bass amp", "photo-1446057032654-9d8885db76c4"),
    ("roger_waters.jpg", "arena rock bass stage", "photo-1470229722913-7c0e2dbb8d3b"),
    ("john_paul_jones.jpg", "rock bass guitar spotlight", "photo-1514525253161-7a46d19cd819"),
    ("geddy_lee.jpg", "prog rock bass live", "photo-1429962714451-bb934ec0ead4"),
    ("michael_anthony.jpg", "hard rock bass concert", "photo-1460036521480-b0b3cd1df6df"),
    ("cliff_burton.jpg", "metal bass player dark", "photo-1614613535308-eb5fbd3d2c17"),
    ("jason_newsted.jpg", "thrash metal bass guitar", "photo-1605020420620-24e54693b2bd"),
    ("lemmy_kilmister.jpg", "rock bass microphone stage", "photo-1510915361894-db8b60106cb1"),
    ("jimmy_haslip.jpg", "fusion bass guitar close up", "photo-1598653227244-c32719c1ec94"),
    ("gary_willis.jpg", "jazz fusion bass fretboard", "photo-1593697821028-7cc59cfd7399"),
    ("lincoln_goines.jpg", "studio fusion bass player", "photo-1593697909683-bccb5b44943e"),
    ("victor_wooten.jpg", "virtuoso bass guitar hands", "photo-1550985616-10810253b84d"),
    ("richard_bona.jpg", "world jazz bass concert", "photo-1485579149621-3123dd979885"),
    ("matthew_garrison.jpg", "modern fusion bass closeup", "photo-1483412036650-74d31e5c3593"),
    ("jaco_pastorius.jpg", "fretless bass guitar stage", "photo-1516280440614-37939bbacd81"),
    ("hadrien_feraud.jpg", "fusion bass guitar close up", "photo-1461783436728-0ddfea2f8e0b"),
    ("anton_davidyants.jpg", "slap bass fusion live", "photo-1574169208507-84376144848b"),
    ("anton_shcherbakov.jpg", "custom shop bass guitar wood", "photo-1556449895-a33c9dba33dd"),
]


def _urls_for(keywords: str, photo_id: str, seed: int) -> list[str]:
    q = quote_plus(keywords)
    return [
        f"https://source.unsplash.com/300x300/?{q}&sig={seed}",
        f"https://source.unsplash.com/featured/300x300/?{q}",
        f"https://source.unsplash.com/random/300x300/?{q}",
        (
            f"https://images.unsplash.com/{photo_id}"
            f"?auto=format&fit=crop&w=800&h=800&q=80"
        ),
    ]


def _fetch(url: str) -> bytes:
    req = Request(url, headers=BROWSER_HEADERS)
    with urlopen(req, timeout=35) as resp:
        data = resp.read()
        content_type = (resp.headers.get("Content-Type") or "").lower()
    if len(data) < 2000:
        raise ValueError("payload too small")
    if "html" in content_type or data.lstrip()[:15].lower().startswith(b"<!doctype html"):
        raise ValueError("received HTML instead of an image")
    return data


def _to_square_jpeg(raw: bytes, dest: Path) -> None:
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    square = image.crop((left, top, left + side, top + side))
    square = square.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    square.save(dest, format="JPEG", quality=90, optimize=True)


def _download_one(filename: str, keywords: str, photo_id: str, seed: int) -> None:
    errors: list[str] = []
    for url in _urls_for(keywords, photo_id, seed):
        try:
            raw = _fetch(url)
            _to_square_jpeg(raw, DEST / filename)
            return
        except (HTTPError, URLError, OSError, ValueError) as exc:
            errors.append(f"{url} -> {exc}")
    raise RuntimeError(" | ".join(errors))


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    ok = 0
    skipped = 0
    failed: list[str] = []
    total = len(CATALOG)
    print(f"Fetching {total} Unsplash portraits into {DEST}")
    for index, (filename, keywords, photo_id) in enumerate(CATALOG, start=1):
        dest = DEST / filename
        if dest.is_file() and dest.stat().st_size > 4_000:
            print(f"[{index:02d}/{total}] skip  {filename}")
            skipped += 1
            continue
        try:
            _download_one(filename, keywords, photo_id, seed=index * 17)
            size = dest.stat().st_size
            print(f"[{index:02d}/{total}] saved {filename}  ({size} bytes)  [{keywords}]")
            ok += 1
        except Exception as exc:
            print(f"[{index:02d}/{total}] FAIL  {filename}: {exc}")
            failed.append(filename)
    print()
    print(f"Downloaded: {ok}  Skipped: {skipped}  Failed: {len(failed)}")
    if failed:
        print("The app will show initials until these files exist:")
        for name in failed:
            print(f"  - {name}")
        raise SystemExit(1)
    print("All musician assets are ready for the offline installer.")


if __name__ == "__main__":
    main()
