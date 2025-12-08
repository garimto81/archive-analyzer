"""NAS Auto Sync System Tray Application

Issue #43: Windows 앱 패키징 - 시스템 트레이 앱

Usage:
    python -m archive_analyzer.tray_app

Features:
    - 시스템 트레이 아이콘
    - 상태 표시 (Running/Stopped/Syncing)
    - 메뉴: Start/Stop, Settings, Open Dashboard, Exit
    - 설정 GUI (NAS 경로, 동기화 간격)
"""

import json
import logging
import os
import subprocess
import sys
import threading
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================


@dataclass
class TrayConfig:
    """트레이 앱 설정"""

    archive_db: str = "data/output/archive.db"
    pokervod_db: str = "D:/AI/claude01/shared-data/pokervod.db"
    nas_mount_path: str = "Z:/GGPNAs/ARCHIVE"
    sync_interval: int = 1800
    web_port: int = 8080
    auto_start: bool = False
    minimize_to_tray: bool = True

    @classmethod
    def load(cls, path: Optional[str] = None) -> "TrayConfig":
        """설정 파일 로드"""
        if path is None:
            path = cls._default_config_path()

        if Path(path).exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**data)
            except Exception as e:
                logger.warning(f"설정 로드 실패: {e}")

        return cls()

    def save(self, path: Optional[str] = None) -> None:
        """설정 파일 저장"""
        if path is None:
            path = self._default_config_path()

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @staticmethod
    def _default_config_path() -> str:
        """기본 설정 파일 경로"""
        if sys.platform == "win32":
            base = os.environ.get("APPDATA", os.path.expanduser("~"))
        else:
            base = os.path.expanduser("~/.config")
        return os.path.join(base, "NASAutoSync", "config.json")


# =============================================================================
# Service Controller
# =============================================================================


class SyncServiceController:
    """동기화 서비스 컨트롤러"""

    def __init__(self, config: TrayConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._web_process: Optional[subprocess.Popen] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running and self._process is not None

    def start(self) -> bool:
        """서비스 시작"""
        if self.is_running:
            return True

        try:
            # 웹 서버 시작
            self._web_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "archive_analyzer.web.app",
                    "--port",
                    str(self.config.web_port),
                ],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            # 동기화 데몬 시작
            self._process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "archive_analyzer.nas_auto_sync",
                    "--interval",
                    str(self.config.sync_interval),
                    "--archive-db",
                    self.config.archive_db,
                    "--pokervod-db",
                    self.config.pokervod_db,
                ],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            self._running = True
            logger.info("서비스 시작됨")
            return True

        except Exception as e:
            logger.error(f"서비스 시작 실패: {e}")
            return False

    def stop(self) -> bool:
        """서비스 중지"""
        try:
            if self._process:
                self._process.terminate()
                self._process.wait(timeout=5)
                self._process = None

            if self._web_process:
                self._web_process.terminate()
                self._web_process.wait(timeout=5)
                self._web_process = None

            self._running = False
            logger.info("서비스 중지됨")
            return True

        except Exception as e:
            logger.error(f"서비스 중지 실패: {e}")
            return False

    def restart(self) -> bool:
        """서비스 재시작"""
        self.stop()
        return self.start()


# =============================================================================
# Settings GUI (Tkinter)
# =============================================================================


def show_settings_dialog(config: TrayConfig, on_save: callable) -> None:
    """설정 다이얼로그 표시"""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError:
        logger.error("Tkinter not available")
        return

    root = tk.Tk()
    root.title("NAS Auto Sync - Settings")
    root.geometry("500x400")
    root.resizable(False, False)

    # 스타일
    style = ttk.Style()
    style.theme_use("clam")

    # 메인 프레임
    main_frame = ttk.Frame(root, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Archive DB
    ttk.Label(main_frame, text="Archive DB:").grid(row=0, column=0, sticky=tk.W, pady=5)
    archive_db_var = tk.StringVar(value=config.archive_db)
    archive_db_entry = ttk.Entry(main_frame, textvariable=archive_db_var, width=40)
    archive_db_entry.grid(row=0, column=1, padx=5, pady=5)
    ttk.Button(
        main_frame,
        text="...",
        width=3,
        command=lambda: archive_db_var.set(
            filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db")])
            or archive_db_var.get()
        ),
    ).grid(row=0, column=2)

    # Pokervod DB
    ttk.Label(main_frame, text="Pokervod DB:").grid(row=1, column=0, sticky=tk.W, pady=5)
    pokervod_db_var = tk.StringVar(value=config.pokervod_db)
    pokervod_db_entry = ttk.Entry(main_frame, textvariable=pokervod_db_var, width=40)
    pokervod_db_entry.grid(row=1, column=1, padx=5, pady=5)
    ttk.Button(
        main_frame,
        text="...",
        width=3,
        command=lambda: pokervod_db_var.set(
            filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db")])
            or pokervod_db_var.get()
        ),
    ).grid(row=1, column=2)

    # NAS Mount Path
    ttk.Label(main_frame, text="NAS Mount Path:").grid(row=2, column=0, sticky=tk.W, pady=5)
    nas_path_var = tk.StringVar(value=config.nas_mount_path)
    nas_path_entry = ttk.Entry(main_frame, textvariable=nas_path_var, width=40)
    nas_path_entry.grid(row=2, column=1, padx=5, pady=5)
    ttk.Button(
        main_frame,
        text="...",
        width=3,
        command=lambda: nas_path_var.set(
            filedialog.askdirectory() or nas_path_var.get()
        ),
    ).grid(row=2, column=2)

    # Sync Interval
    ttk.Label(main_frame, text="Sync Interval (sec):").grid(row=3, column=0, sticky=tk.W, pady=5)
    interval_var = tk.IntVar(value=config.sync_interval)
    interval_spin = ttk.Spinbox(
        main_frame,
        from_=60,
        to=7200,
        increment=60,
        textvariable=interval_var,
        width=10,
    )
    interval_spin.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
    ttk.Label(main_frame, text="(1분 ~ 2시간)").grid(row=3, column=2, sticky=tk.W)

    # Web Port
    ttk.Label(main_frame, text="Web Port:").grid(row=4, column=0, sticky=tk.W, pady=5)
    port_var = tk.IntVar(value=config.web_port)
    port_spin = ttk.Spinbox(
        main_frame,
        from_=1024,
        to=65535,
        textvariable=port_var,
        width=10,
    )
    port_spin.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

    # Auto Start
    auto_start_var = tk.BooleanVar(value=config.auto_start)
    ttk.Checkbutton(
        main_frame,
        text="Start automatically with Windows",
        variable=auto_start_var,
    ).grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=10)

    # Minimize to Tray
    minimize_var = tk.BooleanVar(value=config.minimize_to_tray)
    ttk.Checkbutton(
        main_frame,
        text="Minimize to system tray",
        variable=minimize_var,
    ).grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=5)

    # 버튼 프레임
    btn_frame = ttk.Frame(main_frame)
    btn_frame.grid(row=7, column=0, columnspan=3, pady=20)

    def save_settings():
        config.archive_db = archive_db_var.get()
        config.pokervod_db = pokervod_db_var.get()
        config.nas_mount_path = nas_path_var.get()
        config.sync_interval = interval_var.get()
        config.web_port = port_var.get()
        config.auto_start = auto_start_var.get()
        config.minimize_to_tray = minimize_var.get()
        config.save()
        on_save(config)
        messagebox.showinfo("Settings", "Settings saved successfully!")
        root.destroy()

    ttk.Button(btn_frame, text="Save", command=save_settings, width=15).pack(side=tk.LEFT, padx=10)
    ttk.Button(btn_frame, text="Cancel", command=root.destroy, width=15).pack(side=tk.LEFT, padx=10)

    root.mainloop()


# =============================================================================
# System Tray Icon
# =============================================================================


def create_icon_image(color: str = "green"):
    """트레이 아이콘 이미지 생성"""
    from PIL import Image, ImageDraw

    # 64x64 이미지
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 색상 설정
    colors = {
        "green": "#22c55e",
        "yellow": "#eab308",
        "red": "#ef4444",
        "gray": "#6b7280",
    }
    fill_color = colors.get(color, "#22c55e")

    # 원 그리기
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=fill_color,
        outline="#1f2937",
        width=2,
    )

    # 동기화 아이콘 (화살표)
    arrow_color = "#ffffff"
    # 간단한 화살표 모양
    center = size // 2
    draw.polygon(
        [
            (center - 10, center - 5),
            (center + 5, center - 5),
            (center + 5, center - 12),
            (center + 15, center),
            (center + 5, center + 12),
            (center + 5, center + 5),
            (center - 10, center + 5),
        ],
        fill=arrow_color,
    )

    return img


def run_tray_app():
    """시스템 트레이 앱 실행"""
    try:
        import pystray
        from pystray import MenuItem as Item
    except ImportError:
        logger.error("pystray not installed. Install with: pip install pystray Pillow")
        print("Error: pystray not installed")
        print("Install with: pip install pystray Pillow")
        return

    # 설정 로드
    config = TrayConfig.load()
    controller = SyncServiceController(config)

    # 아이콘 업데이트 함수
    def update_icon(icon):
        if controller.is_running:
            icon.icon = create_icon_image("green")
            icon.title = "NAS Auto Sync - Running"
        else:
            icon.icon = create_icon_image("gray")
            icon.title = "NAS Auto Sync - Stopped"

    # 메뉴 액션
    def on_start(icon, item):
        if controller.start():
            update_icon(icon)

    def on_stop(icon, item):
        if controller.stop():
            update_icon(icon)

    def on_restart(icon, item):
        if controller.restart():
            update_icon(icon)

    def on_open_dashboard(icon, item):
        url = f"http://localhost:{config.web_port}"
        webbrowser.open(url)

    def on_settings(icon, item):
        def on_save(new_config):
            nonlocal config
            config = new_config
            controller.config = new_config
            if controller.is_running:
                controller.restart()
                update_icon(icon)

        # 별도 스레드에서 설정 다이얼로그 실행
        threading.Thread(
            target=show_settings_dialog,
            args=(config, on_save),
            daemon=True,
        ).start()

    def on_exit(icon, item):
        controller.stop()
        icon.stop()

    # 메뉴 구성
    def get_menu():
        return pystray.Menu(
            Item(
                "Start Service",
                on_start,
                enabled=lambda item: not controller.is_running,
            ),
            Item(
                "Stop Service",
                on_stop,
                enabled=lambda item: controller.is_running,
            ),
            Item("Restart Service", on_restart),
            pystray.Menu.SEPARATOR,
            Item("Open Dashboard", on_open_dashboard),
            Item("Settings...", on_settings),
            pystray.Menu.SEPARATOR,
            Item("Exit", on_exit),
        )

    # 아이콘 생성
    icon = pystray.Icon(
        name="NASAutoSync",
        icon=create_icon_image("gray"),
        title="NAS Auto Sync - Stopped",
        menu=get_menu(),
    )

    # 자동 시작
    if config.auto_start:
        controller.start()
        update_icon(icon)

    logger.info("System Tray App started")
    icon.run()


# =============================================================================
# CLI
# =============================================================================


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    import argparse

    parser = argparse.ArgumentParser(description="NAS Auto Sync System Tray App")
    parser.add_argument("--settings", action="store_true", help="Open settings dialog only")

    args = parser.parse_args()

    if args.settings:
        config = TrayConfig.load()
        show_settings_dialog(config, lambda c: c.save())
    else:
        run_tray_app()


if __name__ == "__main__":
    main()
