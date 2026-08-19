"""One-time builder: grade real Wikimedia wood photos and embed them as a zip pack."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "assets" / "woods"


def _hex(hex_color: str) -> np.ndarray:
    value = hex_color.lstrip("#")
    return np.array([int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)], dtype=np.float32)


def _load(name: str) -> Image.Image:
    return Image.open(SRC / name).convert("RGB")


def _cover(image: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = image.size
    target = width / height
    ratio = src_w / src_h
    if ratio > target:
        new_w = max(1, int(src_h * target))
        left = (src_w - new_w) // 2
        image = image.crop((left, 0, left + new_w, src_h))
    else:
        new_h = max(1, int(src_w / target))
        top = (src_h - new_h) // 2
        image = image.crop((0, top, src_w, top + new_h))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _crop_frac(image: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    width, height = image.size
    left, top, right, bottom = box
    return image.crop(
        (
            int(left * width),
            int(top * height),
            int(right * width),
            int(bottom * height),
        )
    )


def _tint(image: Image.Image, hex_color: str, amount: float) -> Image.Image:
    rgb = np.asarray(image, dtype=np.float32)
    multiply = np.clip(rgb * (_hex(hex_color) / 255.0), 0, 255)
    mixed = rgb * (1.0 - amount) + multiply * amount
    return Image.fromarray(np.clip(mixed, 0, 255).astype(np.uint8), mode="RGB")


def _finish(image: Image.Image, contrast: float, color: float, brightness: float) -> Image.Image:
    image = ImageEnhance.Contrast(image).enhance(contrast)
    image = ImageEnhance.Color(image).enhance(color)
    return ImageEnhance.Brightness(image).enhance(brightness)


def _jpeg(image: Image.Image, quality: int = 82) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def build() -> dict[str, bytes]:
    ash = _load("ash.jpg")
    maple = _load("maple.jpg")
    bubinga = _load("bubinga.jpg")
    burl = _load("burl.jpg")
    ebony = _load("ebony.jpg")

    buckeye = _cover(_tint(ash, "#6a5344", 0.22), 1920, 1080)
    buckeye = _finish(buckeye, 1.22, 0.92, 0.96)

    zebrano = _cover(_crop_frac(maple, (0.00, 0.08, 1.00, 0.92)), 1800, 720)
    zebrano = _finish(_tint(zebrano, "#c4882a", 0.20), 1.18, 1.12, 1.04)

    redwood = _cover(bubinga, 1100, 1400)
    redwood = _finish(_tint(redwood, "#5a1c16", 0.18), 1.20, 1.12, 0.98)

    poplar = _cover(_crop_frac(burl, (0.08, 0.06, 0.92, 0.94)), 1100, 1400)
    poplar = _finish(_tint(poplar, "#8a6a3a", 0.10), 1.16, 1.04, 1.02)

    spalted = _cover(ebony, 1100, 1400)
    spalted = _finish(_tint(spalted, "#3a2a18", 0.12), 1.28, 0.96, 1.00)

    files = {
        "buckeye_backdrop.jpg": _jpeg(buckeye, 83),
        "zebrano_top.jpg": _jpeg(zebrano, 83),
        "redwood_left.jpg": _jpeg(redwood, 83),
        "poplar_center.jpg": _jpeg(poplar, 83),
        "spalted_right.jpg": _jpeg(spalted, 83),
    }
    for name, data in files.items():
        (SRC / name).write_bytes(data)
        print(f"{name}: {len(data)} bytes")
    return files


def write_pack(files: dict[str, bytes]) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    payload = base64.b85encode(buf.getvalue()).decode("ascii")
    dest = ROOT / "woods_pack.py"
    dest.write_text(
        '"""Embedded real Wikimedia tonewood photographs. Offline only."""\n\n'
        f'PACK_B85 = """{payload}"""\n',
        encoding="utf-8",
    )
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    write_pack(build())
