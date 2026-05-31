import sys
import os
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
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

    menu.addSeparator()

    quit_act = QAction("Quit")
    quit_act.triggered.connect(app.quit)
    menu.addAction(quit_act)

    tray.setContextMenu(menu)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
