#!/usr/bin/env python
"""NAS Auto Sync Windows Installer Build Script

Issue #43: Windows 앱 패키징

Usage:
    python scripts/build_installer.py
    python scripts/build_installer.py --onefile
    python scripts/build_installer.py --debug

Output:
    dist/NASAutoSync/         - Directory bundle
    dist/NASAutoSync.exe      - Single file (with --onefile)
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

# 앱 정보
APP_NAME = "NASAutoSync"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "NAS Auto Sync Service with Web Monitoring"
APP_AUTHOR = "GGP Team"


def clean_build():
    """빌드 디렉토리 정리"""
    print("Cleaning build directories...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
    print("Done.")


def check_dependencies():
    """의존성 확인"""
    print("Checking dependencies...")

    # PyInstaller
    try:
        import PyInstaller
        print(f"  PyInstaller: {PyInstaller.__version__}")
    except ImportError:
        print("  PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # pystray, Pillow
    for pkg in ["pystray", "PIL"]:
        try:
            __import__(pkg)
            print(f"  {pkg}: OK")
        except ImportError:
            print(f"  {pkg} not found. Installing...")
            pip_name = "Pillow" if pkg == "PIL" else pkg
            subprocess.run([sys.executable, "-m", "pip", "install", pip_name], check=True)


def create_icon():
    """앱 아이콘 생성 (.ico)"""
    icon_path = PROJECT_ROOT / "assets" / "icon.ico"
    if icon_path.exists():
        print(f"Using existing icon: {icon_path}")
        return icon_path

    print("Creating app icon...")

    try:
        from PIL import Image, ImageDraw

        # 아이콘 디렉토리 생성
        icon_path.parent.mkdir(parents=True, exist_ok=True)

        # 여러 크기의 아이콘 생성
        sizes = [16, 32, 48, 64, 128, 256]
        images = []

        for size in sizes:
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 배경 원
            margin = max(1, size // 16)
            draw.ellipse(
                [margin, margin, size - margin, size - margin],
                fill="#22c55e",
                outline="#1f2937",
                width=max(1, size // 32),
            )

            images.append(img)

        # ICO 파일로 저장
        images[0].save(
            icon_path,
            format="ICO",
            sizes=[(s, s) for s in sizes],
            append_images=images[1:],
        )

        print(f"Icon created: {icon_path}")
        return icon_path

    except ImportError:
        print("Pillow not available, skipping icon creation")
        return None


def build_exe(onefile: bool = False, debug: bool = False):
    """PyInstaller로 실행 파일 빌드"""
    print(f"\nBuilding {'single file' if onefile else 'directory'} executable...")

    # PyInstaller 옵션
    opts = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name", APP_NAME,
        "--windowed",  # GUI 앱 (콘솔 숨김)
        "--noconfirm",
    ]

    # 아이콘
    icon_path = create_icon()
    if icon_path:
        opts.extend(["--icon", str(icon_path)])

    # 단일 파일 vs 디렉토리
    if onefile:
        opts.append("--onefile")
    else:
        opts.append("--onedir")

    # 디버그 모드
    if debug:
        opts.append("--debug=all")
    else:
        opts.extend(["--log-level", "WARN"])

    # Hidden imports (자동 감지 안 되는 모듈)
    hidden_imports = [
        "archive_analyzer",
        "archive_analyzer.web",
        "archive_analyzer.web.app",
        "archive_analyzer.nas_auto_sync",
        "archive_analyzer.path_tracker",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "pystray._win32",
    ]
    for imp in hidden_imports:
        opts.extend(["--hidden-import", imp])

    # 데이터 파일 (템플릿, 정적 파일)
    datas = [
        (str(PROJECT_ROOT / "src" / "archive_analyzer" / "web" / "templates"), "archive_analyzer/web/templates"),
        (str(PROJECT_ROOT / "src" / "archive_analyzer" / "web" / "static"), "archive_analyzer/web/static"),
    ]
    for src, dst in datas:
        if Path(src).exists():
            opts.extend(["--add-data", f"{src};{dst}"])

    # 엔트리 포인트
    opts.append(str(PROJECT_ROOT / "src" / "archive_analyzer" / "tray_app.py"))

    # 빌드 실행
    print(f"Running: {' '.join(opts)}")
    result = subprocess.run(opts, cwd=PROJECT_ROOT)

    if result.returncode == 0:
        print(f"\nBuild successful!")
        if onefile:
            print(f"Output: {DIST_DIR / f'{APP_NAME}.exe'}")
        else:
            print(f"Output: {DIST_DIR / APP_NAME}")
    else:
        print(f"\nBuild failed with code {result.returncode}")
        sys.exit(1)


def create_inno_setup_script():
    """Inno Setup 스크립트 생성"""
    script_path = PROJECT_ROOT / "installer" / "setup.iss"
    script_path.parent.mkdir(parents=True, exist_ok=True)

    script = f'''
; NAS Auto Sync Installer Script
; Generated by build_installer.py

#define MyAppName "{APP_NAME}"
#define MyAppVersion "{APP_VERSION}"
#define MyAppPublisher "{APP_AUTHOR}"
#define MyAppURL "https://github.com/garimto81/archive-analyzer"
#define MyAppExeName "{APP_NAME}.exe"

[Setup]
AppId={{{{B8A2F3C4-D5E6-4F7A-8B9C-0D1E2F3A4B5C}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes
OutputDir=..\\dist
OutputBaseFilename={APP_NAME}_Setup_v{APP_VERSION}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean"; MessagesFile: "compiler:Languages\\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked
Name: "startup"; Description: "Start with Windows"; GroupDescription: "Startup options:"

[Files]
Source: "..\\dist\\{APP_NAME}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueType: string; ValueName: "{{#MyAppName}}"; ValueData: """{{app}}\\{{#MyAppExeName}}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{#StringChange(MyAppName, '&', '&&')}}}}"; Flags: nowait postinstall skipifsilent
'''

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    print(f"Inno Setup script created: {script_path}")
    return script_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build NAS Auto Sync Windows Installer")
    parser.add_argument("--onefile", action="store_true", help="Create single executable file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--clean", action="store_true", help="Clean build directories only")
    parser.add_argument("--inno", action="store_true", help="Generate Inno Setup script")

    args = parser.parse_args()

    print("=" * 60)
    print(f"NAS Auto Sync Installer Builder")
    print(f"Version: {APP_VERSION}")
    print("=" * 60)

    if args.clean:
        clean_build()
        return

    if args.inno:
        create_inno_setup_script()
        return

    # 전체 빌드 과정
    clean_build()
    check_dependencies()
    build_exe(onefile=args.onefile, debug=args.debug)
    create_inno_setup_script()

    print("\n" + "=" * 60)
    print("Build complete!")
    print("")
    print("Next steps:")
    print("  1. Test the executable:")
    print(f"     {DIST_DIR / APP_NAME / f'{APP_NAME}.exe'}")
    print("")
    print("  2. Create installer (requires Inno Setup):")
    print(f"     iscc installer/setup.iss")
    print("=" * 60)


if __name__ == "__main__":
    main()
