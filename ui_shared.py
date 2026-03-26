from __future__ import annotations

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QWidget


APP_STYLESHEET = """
QWidget {
    background: #2D1F16;
    color: #EAD2AC;
    font-family: "Palatino", "Georgia", serif;
    font-size: 14px;
}
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1A120B, stop:1 #2D1F16);
}
QFrame#panel {
    background: #3E2C1C;
    border: 3px solid #8B5E3C;
    border-radius: 12px;
}
QFrame#parchmentPanel {
    background: #F4E4BC;
    color: #2D1F16;
    border: 2px solid #C19A6B;
    border-radius: 15px;
}
QFrame#heroPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4E3B24, stop:1 #2D1F16);
    border: 4px solid #C19A6B;
    border-radius: 15px;
}
QFrame#accentPanel {
    background: #2D1F16;
    border: 2px solid #8B5E3C;
    border-radius: 8px;
}
QFrame#softPanel {
    background: #F4E4BC;
    color: #2D1F16;
    border: 1px solid #C19A6B;
    border-radius: 6px;
}
QFrame#onlineCard {
    background: #4E3B24;
    border: 2px solid #8B5E3C;
    border-radius: 10px;
}
QLabel#title {
    font-size: 42px;
    font-weight: 800;
    color: #F4E4BC;
    text-shadow: 3px 3px #1A120B;
}
QLabel#subtitle {
    color: #C19A6B;
    font-size: 18px;
    font-style: italic;
}
QLabel#sectionTitle {
    font-size: 26px;
    font-weight: 800;
    color: #F4E4BC;
    border-bottom: 2px solid #8B5E3C;
    margin-bottom: 10px;
}
QLabel#statusBadge {
    background: #1A120B;
    border: 2px solid #C19A6B;
    border-radius: 6px;
    padding: 6px 14px;
    color: #F4E4BC;
    font-weight: 700;
}
QLineEdit, QComboBox, QListWidget, QTextEdit, QSpinBox {
    background: #1A120B;
    color: #F4E4BC;
    border: 2px solid #8B5E3C;
    border-radius: 6px;
    padding: 10px 12px;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8B5E3C, stop:1 #4E3B24);
    color: #F4E4BC;
    border: 3px solid #C19A6B;
    border-radius: 8px;
    padding: 12px 20px;
    font-weight: 800;
    font-size: 15px;
}
QPushButton:hover {
    background: #A67B5B;
    border-color: #F4E4BC;
}
QPushButton:pressed {
    background: #3E2C1C;
    padding-top: 14px;
    padding-bottom: 10px;
}
QPushButton#navButton {
    text-align: left;
    background: transparent;
    border: none;
    color: #C19A6B;
    font-size: 16px;
    padding: 15px 20px;
}
QPushButton#navButton:checked {
    background: #4E3B24;
    color: #F4E4BC;
    border-left: 6px solid #C19A6B;
}
QProgressBar {
    border: 2px solid #8B5E3C;
    background: #1A120B;
    height: 24px;
    text-align: center;
    border-radius: 6px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5E3C, stop:1 #C19A6B);
}
"""


def load_pixmap(image_path: str, size: int) -> QPixmap:
    pixmap = QPixmap(image_path)
    if pixmap.isNull():
        placeholder = QPixmap(size, size)
        placeholder.fill(Qt.transparent)
        painter = QPainter(placeholder)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#1A2433"))
        painter.setPen(QColor("#365173"))
        painter.drawRoundedRect(0, 0, size - 1, size - 1, 18, 18)
        painter.setPen(QColor("#8EA3C1"))
        painter.drawText(placeholder.rect(), Qt.AlignCenter, "?")
        painter.end()
        return placeholder
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def with_alpha(color: str, alpha: int) -> str:
    color = color.lstrip("#")
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def apply_fade_in(widget: QWidget) -> None:
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(220)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.start()
    widget._fade_animation = animation
