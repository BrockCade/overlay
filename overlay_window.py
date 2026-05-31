import json
import datetime
import ctypes
import subprocess
import sys
import re
from ctypes import c_int, c_short, c_ushort, c_void_p, POINTER, Structure
from pathlib import Path
import psutil
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QHBoxLayout
from PySide6.QtGui import QPainter, QColor, QPen


_X11 = None
_Xext = None
_X11_DISPLAY = None


class _XRectangle(Structure):
    _fields_ = [
        ("x", c_short),
        ("y", c_short),
        ("width", c_ushort),
        ("height", c_ushort),
    ]


def _x11_init():
    global _X11, _Xext
    if _X11 is not None:
        return True
    try:
        _X11 = ctypes.cdll.LoadLibrary("libX11.so.6")
        _X11.XOpenDisplay.restype = c_void_p
        _X11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        _X11.XCloseDisplay.restype = c_int
        _X11.XCloseDisplay.argtypes = [c_void_p]
        _X11.XFlush.restype = c_int
        _X11.XFlush.argtypes = [c_void_p]

        _Xext = ctypes.cdll.LoadLibrary("libXext.so.6")
        _Xext.XShapeCombineRectangles.restype = None
        _Xext.XShapeCombineRectangles.argtypes = [
            c_void_p, c_ulong, c_int, c_int, c_int,
            POINTER(_XRectangle), c_int, c_int, c_int,
        ]
        return True
    except Exception:
        _X11 = _Xext = None
        return False


def _x11_display():
    global _X11_DISPLAY
    if _X11_DISPLAY is None and _x11_init():
        ptr = _X11.XOpenDisplay(None)
        _X11_DISPLAY = ptr if ptr else None
    return _X11_DISPLAY


def _read_windows_temp():
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature).CurrentTemperature"],
            timeout=5, text=True, stderr=subprocess.DEVNULL
        ).strip()
        if out:
            match = re.search(r"\d+", out)
            if match:
                temp_k = int(match.group()) / 10.0
                return temp_k - 273.15
    except Exception:
        pass
    return None


class OverlayWindow(QWidget):
    def __init__(self, config_path):
        super().__init__()
        self.config_path = config_path
        self.config = self._load_config()

        self.time_format_24h = self.config.get("time_format_24h", False)

        self._moving = False
        self._drag_start_pos = None

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._setup_ui()
        self._setup_timers()

        pos = self.config.get("position", {"x": 100, "y": 100})
        sz = self.config.get("size", {"width": 280, "height": 180})
        self.setGeometry(pos["x"], pos["y"], sz["width"], sz["height"])

    def _load_config(self):
        try:
            with open(self.config_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"position": {"x": 100, "y": 100}, "custom_text": "", "refresh_interval_seconds": 2}

    def _save_config(self):
        g = self.geometry()
        self.config["position"] = {"x": g.x(), "y": g.y()}
        self.config["size"] = {"width": g.width(), "height": g.height()}
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def reload_config(self):
        self.config = self._load_config()
        self.time_format_24h = self.config.get("time_format_24h", False)
        self._update_clock()
        self._update_custom_text()
        interval = max(1, self.config.get("refresh_interval_seconds", 2)) * 1000
        self.stats_timer.setInterval(interval)
        self._update_input_shape()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_input_shape()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_input_shape()

    def _setup_ui(self):
        font_family = self.config.get("font_family", "sans-serif")
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet(
            f"font-family: '{font_family}'; font-size: 40px; font-weight: bold; color: #ffffff;"
        )
        layout.addWidget(self.time_label)

        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_label.setStyleSheet(
            f"font-family: '{font_family}'; font-size: 12px; color: rgba(255,255,255,180);"
        )
        layout.addWidget(self.date_label)

        sep1 = QLabel()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet("background: rgba(255,255,255,25);")
        sep1.setContentsMargins(0, 4, 0, 4)
        layout.addWidget(sep1)

        cpu_row = QHBoxLayout()
        cpu_row.setContentsMargins(0, 0, 0, 0)
        cpu_label = QLabel("CPU")
        cpu_label.setStyleSheet(f"font-family: '{font_family}'; font-size: 11px; color: rgba(255,255,255,200);")
        cpu_row.addWidget(cpu_label)
        cpu_row.addStretch()
        self.cpu_value = QLabel("0%")
        self.cpu_value.setStyleSheet(f"font-family: '{font_family}'; font-size: 11px; font-weight: bold; color: #4fc3f7;")
        cpu_row.addWidget(self.cpu_value)
        layout.addLayout(cpu_row)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setFixedHeight(3)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,20); border-radius: 1px; }"
            "QProgressBar::chunk { background: #4fc3f7; border-radius: 1px; }"
        )
        layout.addWidget(self.cpu_bar)

        ram_row = QHBoxLayout()
        ram_row.setContentsMargins(0, 0, 0, 0)
        ram_label = QLabel("RAM")
        ram_label.setStyleSheet(f"font-family: '{font_family}'; font-size: 11px; color: rgba(255,255,255,200);")
        ram_row.addWidget(ram_label)
        ram_row.addStretch()
        self.ram_value = QLabel("0%")
        self.ram_value.setStyleSheet(f"font-family: '{font_family}'; font-size: 11px; font-weight: bold; color: #81c784;")
        ram_row.addWidget(self.ram_value)
        layout.addLayout(ram_row)

        self.ram_bar = QProgressBar()
        self.ram_bar.setFixedHeight(3)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,20); border-radius: 1px; }"
            "QProgressBar::chunk { background: #81c784; border-radius: 1px; }"
        )
        layout.addWidget(self.ram_bar)

        temp_row = QHBoxLayout()
        temp_row.setContentsMargins(0, 0, 0, 0)
        temp_label = QLabel("TEMP")
        temp_label.setStyleSheet(f"font-family: '{font_family}'; font-size: 11px; color: rgba(255,255,255,200);")
        temp_row.addWidget(temp_label)
        temp_row.addStretch()
        self.temp_value = QLabel("--")
        self.temp_value.setStyleSheet(f"font-family: '{font_family}'; font-size: 11px; font-weight: bold; color: #ff9800;")
        temp_row.addWidget(self.temp_value)
        layout.addLayout(temp_row)

        self.temp_bar = QProgressBar()
        self.temp_bar.setFixedHeight(3)
        self.temp_bar.setTextVisible(False)
        self.temp_bar.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,20); border-radius: 1px; }"
            "QProgressBar::chunk { background: #ff9800; border-radius: 1px; }"
        )
        layout.addWidget(self.temp_bar)

        sep2 = QLabel()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: rgba(255,255,255,25);")
        sep2.setContentsMargins(0, 4, 0, 4)
        layout.addWidget(sep2)

        self.quote_label = QLabel()
        self.quote_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quote_label.setWordWrap(True)
        self.quote_label.setStyleSheet(
            f"font-family: '{font_family}'; font-size: 12px; font-style: italic; color: rgba(255,255,255,200);"
        )
        self.quote_label.setText(self.config.get("custom_text", ""))
        layout.addWidget(self.quote_label)

        ver = "?"
        try:
            ver = Path(__file__).resolve().parent.joinpath("version.txt").read_text().strip()
        except Exception:
            pass
        self.version_label = QLabel(f"v{ver}")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setStyleSheet(
            f"font-family: '{font_family}'; font-size: 9px; color: rgba(255,255,255,60);"
        )
        self.version_label.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self.version_label)

        self.setLayout(layout)
        self._content_widgets = [
            self.time_label, self.date_label,
            self.cpu_value, self.cpu_bar,
            self.ram_value, self.ram_bar,
            self.temp_value, self.temp_bar,
            self.quote_label, self.version_label,
        ]

    def _setup_timers(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

        interval = max(1, self.config.get("refresh_interval_seconds", 2)) * 1000
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self._update_stats)
        self.stats_timer.start(interval)
        self._update_stats()

    def _update_clock(self):
        now = datetime.datetime.now()
        if self.time_format_24h:
            self.time_label.setText(now.strftime("%H:%M:%S"))
        else:
            self.time_label.setText(now.strftime("%I:%M:%S %p").lstrip("0"))
        self.date_label.setText(now.strftime("%A, %B %d, %Y"))
        self._update_input_shape()

    def _update_stats(self):
        try:
            cpu = psutil.cpu_percent(interval=0)
            self.cpu_bar.setValue(int(cpu))
            self.cpu_value.setText(f"{cpu:.0f}%")

            ram = psutil.virtual_memory()
            pct = ram.percent
            self.ram_bar.setValue(int(pct))
            self.ram_value.setText(f"{pct:.0f}%")
        except Exception:
            pass

        try:
            best = None
            if sys.platform == "win32":
                best = _read_windows_temp()
            else:
                temps = psutil.sensors_temperatures()
                if temps:
                    cpu_keys = ["coretemp", "cpu_thermal", "k10temp", "cpu"]
                    for key in cpu_keys:
                        if key in temps and temps[key]:
                            best = max(best or 0, temps[key][0].current)
                    if best is None:
                        for entries in temps.values():
                            if entries:
                                best = max(best or 0, entries[0].current)
            if best is not None:
                self.temp_bar.setValue(min(int(best), 100))
                self.temp_value.setText(f"{best:.0f}°C")
        except Exception:
            pass

        self._update_input_shape()

    def _update_custom_text(self):
        self.quote_label.setText(self.config.get("custom_text", ""))
        self._update_input_shape()

    def toggle_time_format(self, *args):
        self.time_format_24h = not self.time_format_24h
        self._update_clock()
        self._save_config()

    def _content_rects(self):
        rects = []
        for w in self._content_widgets:
            if not w.isVisible():
                continue
            g = w.geometry()
            if isinstance(w, QProgressBar):
                rects.append((g.x(), g.y(), g.width(), g.height()))
                continue
            text = w.text().strip()
            if not text:
                continue
            if w.wordWrap():
                rects.append((g.x(), g.y(), g.width(), g.height()))
                continue
            br = w.fontMetrics().boundingRect(text)
            tw, th = br.width(), br.height()
            if tw >= g.width() - 4:
                rects.append((g.x(), g.y(), g.width(), g.height()))
                continue
            align = w.alignment()
            if align & Qt.AlignmentFlag.AlignCenter:
                rx = g.x() + (g.width() - tw) // 2
            elif align & Qt.AlignmentFlag.AlignRight:
                rx = g.right() - tw
            else:
                rx = g.x()
            ry = g.y() + (g.height() - th) // 2
            rects.append((rx, ry, tw, th))
        return rects

    def _update_input_shape(self):
        if not self.isVisible():
            return
        display = _x11_display()
        if not display:
            return
        display_p = ctypes.c_void_p(display)
        raw_rects = self._content_rects()
        if not raw_rects:
            return
        xrects = (_XRectangle * len(raw_rects))()
        for i, (x, y, w, h) in enumerate(raw_rects):
            xrects[i] = _XRectangle(x, y, w, h)
        _Xext.XShapeCombineRectangles(
            display_p,
            ctypes.c_ulong(self.winId()),
            0,  # ShapeInput
            0, 0,  # x_off, y_off
            xrects,
            len(raw_rects),
            0,  # ShapeSet
            2,  # YXBanded
        )
        _X11.XFlush(display_p)

    def paintEvent(self, event):
        if self._moving:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._moving = True
            self._drag_start_pos = event.globalPosition().toPoint() - self.pos()
            self.update()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._moving:
            self.move(event.globalPosition().toPoint() - self._drag_start_pos)
            self.update()
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._moving:
            self._moving = False
            self._drag_start_pos = None
            self.update()
            self._save_config()
