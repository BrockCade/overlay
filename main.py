import sys
import os
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PySide6.QtGui import QIcon, QPainter, QColor, QPixmap, QAction
from PySide6.QtCore import Qt
from overlay_window import OverlayWindow


def _make_icon():
    pm = QPixmap(20, 20)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(79, 195, 247))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, 18, 18)
    p.end()
    return QIcon(pm)


def _check_updates():
    from updater import get_current_version, check_remote_version, apply_update, restart_app

    current = get_current_version()
    remote = check_remote_version("BrockCade", "overlay")

    if remote is None:
        QMessageBox.information(None, "Update Check", "Could not reach GitHub. Check your internet connection.")
        return

    if remote == current:
        QMessageBox.information(None, "Update Check", f"You're up to date (v{current}).")
        return

    reply = QMessageBox.question(
        None, "Update Available",
        f"Version v{remote} available (current: v{current}).\nUpdate now?",
        QMessageBox.Yes | QMessageBox.No
    )

    if reply == QMessageBox.Yes:
        result = apply_update()
        if result["success"]:
            QMessageBox.information(
                None, "Update Complete",
                f"Updated to v{result.get('version', remote)}. Restarting..."
            )
            restart_app()
        else:
            msg = {
                "uncommitted_changes": "You have unsaved changes. Commit or stash them first.",
                "git_not_found": "Git is not installed on this system.",
            }.get(result["error"], f"Update failed: {result['error']}")
            QMessageBox.warning(None, "Update Failed", msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    overlay = OverlayWindow(config_path)
    overlay.show()

    tray = QSystemTrayIcon()
    tray.setIcon(_make_icon())
    tray.setToolTip("Desktop Overlay")

    menu = QMenu()

    toggle_act = QAction("Toggle Visibility")
    toggle_act.triggered.connect(lambda: overlay.setVisible(not overlay.isVisible()))
    menu.addAction(toggle_act)

    reload_act = QAction("Reload Config")
    reload_act.triggered.connect(overlay.reload_config)
    menu.addAction(reload_act)

    update_act = QAction("Check for Updates")
    update_act.triggered.connect(_check_updates)
    menu.addAction(update_act)

    menu.addSeparator()

    quit_act = QAction("Quit")
    quit_act.triggered.connect(app.quit)
    menu.addAction(quit_act)

    tray.setContextMenu(menu)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
