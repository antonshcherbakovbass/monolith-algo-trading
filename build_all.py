"""
Platform installer builder.

Windows can be fully built on this PC.
macOS .app/.dmg and iOS .ipa must be compiled on an Apple computer.
Android APK needs the Android SDK / Qt for Android on a machine with those tools.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist_installers"
APP_VERSION = "1.0.1"


def run(command: list[str], **kwargs) -> None:
    print("->", " ".join(command))
    subprocess.check_call(command, cwd=ROOT, **kwargs)


def generate_icons() -> None:
    run([sys.executable, str(ROOT / "generate_icon.py")])


def find_iscc() -> Path | None:
    names = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 7\ISCC.exe"),
        Path.home() / r"AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    ]
    for path in names:
        if path.is_file():
            return path
    return None


def build_windows() -> Path:
    generate_icons()
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "pyinstaller"])
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "GrooveTrainer.spec"])
    exe = ROOT / "dist" / "GrooveTrainer.exe"
    if not exe.is_file():
        raise SystemExit("Windows EXE was not created")
    portable = DIST / "windows"
    portable.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe, portable / "GrooveTrainer.exe")
    shutil.copy2(ROOT / "app_icon.ico", portable / "app_icon.ico")
    iscc = find_iscc()
    if iscc is None:
        print("Inno Setup not found — portable EXE copied to dist_installers/windows/")
        print("Install Inno Setup 6 and re-run: python build_all.py --windows")
        return portable / "GrooveTrainer.exe"
    run([str(iscc), str(ROOT / "installer_setup.iss")])
    setup = DIST / "windows" / "GrooveTrainer-Windows-Setup.exe"
    if not setup.is_file():
        raise SystemExit("Windows installer was not created")
    return setup


def copy_mobile_icon_packs() -> None:
    generate_icons()
    android = DIST / "android"
    ios = DIST / "ios"
    macos = DIST / "macos"
    if android.exists():
        shutil.rmtree(android)
    if ios.exists():
        shutil.rmtree(ios)
    if macos.exists():
        shutil.rmtree(macos)
    shutil.copytree(ROOT / "packaging" / "android", android)
    shutil.copytree(ROOT / "packaging" / "ios", ios)
    shutil.copytree(ROOT / "packaging" / "macos", macos)
    shutil.copy2(ROOT / "packaging" / "icons" / "app_icon.icns", macos / "app_icon.icns")
    shutil.copy2(ROOT / "logo.png", DIST / "sun-logo.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", action="store_true")
    parser.add_argument("--icons", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    DIST.mkdir(parents=True, exist_ok=True)
    if args.icons or args.all or not any([args.windows]):
        generate_icons()
        copy_mobile_icon_packs()
    if args.windows or args.all:
        built = build_windows()
        print("Windows package:", built)
    print("Output folder:", DIST)


if __name__ == "__main__":
    main()
