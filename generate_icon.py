"""Build the sun logo into every installer / launcher icon format."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
LOGO = SCRIPT_DIR / "logo.png"

WINDOWS_ICO = SCRIPT_DIR / "app_icon.ico"
PACKAGING = SCRIPT_DIR / "packaging"
ICONS = PACKAGING / "icons"
MACOS_ICONSET = PACKAGING / "macos" / "AppIcon.iconset"
IOS_APPICON = PACKAGING / "ios" / "AppIcon.appiconset"
ANDROID_RES = PACKAGING / "android" / "res"

ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
MASTER_SIZES = (16, 20, 24, 29, 32, 40, 48, 58, 60, 64, 72, 76, 80, 87, 96, 108, 120, 128, 144, 152, 167, 180, 192, 256, 320, 432, 512, 1024)

ANDROID_LAUNCHERS = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
ANDROID_FOREGROUND = {
    "mipmap-mdpi": 108,
    "mipmap-hdpi": 162,
    "mipmap-xhdpi": 216,
    "mipmap-xxhdpi": 324,
    "mipmap-xxxhdpi": 432,
}
MAC_ICONSET = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}
IOS_ICONS = [
    ("icon-20.png", 20),
    ("icon-20@2x.png", 40),
    ("icon-20@3x.png", 60),
    ("icon-29.png", 29),
    ("icon-29@2x.png", 58),
    ("icon-29@3x.png", 87),
    ("icon-40.png", 40),
    ("icon-40@2x.png", 80),
    ("icon-40@3x.png", 120),
    ("icon-60@2x.png", 120),
    ("icon-60@3x.png", 180),
    ("icon-76.png", 76),
    ("icon-76@2x.png", 152),
    ("icon-83.5@2x.png", 167),
    ("icon-1024.png", 1024),
]


def center_square_crop(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def load_master(logo_path: Path = LOGO) -> Image.Image:
    if not logo_path.is_file():
        raise FileNotFoundError(f"Sun logo not found: {logo_path}")
    image = Image.open(logo_path).convert("RGBA")
    square = center_square_crop(image)
    return square.resize((1024, 1024), Image.Resampling.LANCZOS)


def opaque_black(image: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", image.size, (0, 0, 0))
    canvas.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
    return canvas


def save_png(image: Image.Image, path: Path, size: int, *, opaque: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resized = image.resize((size, size), Image.Resampling.LANCZOS)
    if opaque:
        opaque_black(resized).save(path, format="PNG")
    else:
        resized.save(path, format="PNG")


def write_ico(master: Image.Image, output_path: Path = WINDOWS_ICO) -> Path:
    frames = [master.resize((size, size), Image.Resampling.LANCZOS) for size in ICO_SIZES]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output_path,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        append_images=frames[1:],
    )
    return output_path


def write_bmp(image: Image.Image, path: Path, size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resized = image.resize(size, Image.Resampling.LANCZOS)
    opaque_black(resized).save(path, format="BMP")


def write_android(master: Image.Image) -> None:
    for folder, size in ANDROID_LAUNCHERS.items():
        directory = ANDROID_RES / folder
        save_png(master, directory / "ic_launcher.png", size, opaque=True)
        save_png(master, directory / "ic_launcher_round.png", size, opaque=True)
    for folder, size in ANDROID_FOREGROUND.items():
        save_png(master, ANDROID_RES / folder / "ic_launcher_foreground.png", size)
    anydpi = ANDROID_RES / "mipmap-anydpi-v26"
    anydpi.mkdir(parents=True, exist_ok=True)
    adaptive = """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>
"""
    (anydpi / "ic_launcher.xml").write_text(adaptive, encoding="utf-8")
    (anydpi / "ic_launcher_round.xml").write_text(adaptive, encoding="utf-8")
    values = ANDROID_RES / "values"
    values.mkdir(parents=True, exist_ok=True)
    (values / "colors.xml").write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="ic_launcher_background">#000000</color>
</resources>
""",
        encoding="utf-8",
    )


def write_ios_contents() -> None:
    contents = {
        "images": [
            {"idiom": "iphone", "scale": "2x", "size": "20x20", "filename": "icon-20@2x.png"},
            {"idiom": "iphone", "scale": "3x", "size": "20x20", "filename": "icon-20@3x.png"},
            {"idiom": "iphone", "scale": "2x", "size": "29x29", "filename": "icon-29@2x.png"},
            {"idiom": "iphone", "scale": "3x", "size": "29x29", "filename": "icon-29@3x.png"},
            {"idiom": "iphone", "scale": "2x", "size": "40x40", "filename": "icon-40@2x.png"},
            {"idiom": "iphone", "scale": "3x", "size": "40x40", "filename": "icon-40@3x.png"},
            {"idiom": "iphone", "scale": "2x", "size": "60x60", "filename": "icon-60@2x.png"},
            {"idiom": "iphone", "scale": "3x", "size": "60x60", "filename": "icon-60@3x.png"},
            {"idiom": "ipad", "scale": "1x", "size": "20x20", "filename": "icon-20.png"},
            {"idiom": "ipad", "scale": "2x", "size": "20x20", "filename": "icon-20@2x.png"},
            {"idiom": "ipad", "scale": "1x", "size": "29x29", "filename": "icon-29.png"},
            {"idiom": "ipad", "scale": "2x", "size": "29x29", "filename": "icon-29@2x.png"},
            {"idiom": "ipad", "scale": "1x", "size": "40x40", "filename": "icon-40.png"},
            {"idiom": "ipad", "scale": "2x", "size": "40x40", "filename": "icon-40@2x.png"},
            {"idiom": "ipad", "scale": "1x", "size": "76x76", "filename": "icon-76.png"},
            {"idiom": "ipad", "scale": "2x", "size": "76x76", "filename": "icon-76@2x.png"},
            {"idiom": "ipad", "scale": "2x", "size": "83.5x83.5", "filename": "icon-83.5@2x.png"},
            {"idiom": "ios-marketing", "scale": "1x", "size": "1024x1024", "filename": "icon-1024.png"},
        ],
        "info": {"author": "xcode", "version": 1},
    }
    IOS_APPICON.mkdir(parents=True, exist_ok=True)
    (IOS_APPICON / "Contents.json").write_text(json.dumps(contents, indent=2), encoding="utf-8")


def write_icns(master: Image.Image) -> Path:
    icns_path = ICONS / "app_icon.icns"
    icns_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from icnsutil import IcnsFile

        archive = IcnsFile()
        for name, size in MAC_ICONSET.items():
            png_path = MACOS_ICONSET / name
            archive.add_media(file=str(png_path))
        archive.write(str(icns_path), toc=True)
        return icns_path
    except Exception:
        # Pillow can write a basic ICNS from the 256 master if icnsutil is missing.
        master.resize((256, 256), Image.Resampling.LANCZOS).save(icns_path, format="ICNS")
        return icns_path


def build_icon(logo_path: Path = LOGO, output_path: Path = WINDOWS_ICO) -> Path:
    master = load_master(logo_path)
    write_ico(master, output_path)
    ICONS.mkdir(parents=True, exist_ok=True)
    for size in MASTER_SIZES:
        save_png(master, ICONS / f"icon_{size}.png", size)
    save_png(master, ICONS / "icon_1024.png", 1024, opaque=True)
    write_bmp(master, PACKAGING / "windows" / "wizard.bmp", (164, 314))
    write_bmp(master, PACKAGING / "windows" / "wizard-small.bmp", (55, 58))
    write_bmp(master, PACKAGING / "windows" / "wizard-modern.bmp", (273, 556))
    for name, size in MAC_ICONSET.items():
        save_png(master, MACOS_ICONSET / name, size)
    write_icns(master)
    write_android(master)
    write_ios_contents()
    for name, size in IOS_ICONS:
        save_png(master, IOS_APPICON / name, size, opaque=True)
    return output_path


def main() -> None:
    output = build_icon()
    print(f"Sun icon set written: {output}")
    print(f"macOS: {ICONS / 'app_icon.icns'}")
    print(f"Android: {ANDROID_RES}")
    print(f"iOS: {IOS_APPICON}")


if __name__ == "__main__":
    main()
