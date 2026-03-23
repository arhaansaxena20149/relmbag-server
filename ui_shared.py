from __future__ import annotations

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QWidget


APP_STYLESHEET = """
QWidget {
    background: #091019;
    color: #F4F7FC;
    font-family: "Avenir Next";
    font-size: 14px;
}
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #091019, stop:1 #111D2B);
}
QFrame#panel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #152131, stop:1 #101927);
    border: 1px solid #28384D;
    border-radius: 20px;
}
QFrame#heroPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1A2A40, stop:1 #0E1622);
    border: 1px solid #3D567A;
    border-radius: 22px;
}
QFrame#accentPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #13263D, stop:1 #142236);
    border: 1px solid #36537A;
    border-radius: 18px;
}
QFrame#softPanel {
    background: #0F1724;
    border: 1px solid #243349;
    border-radius: 16px;
}
QFrame#onlineCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #121E2E, stop:1 #101824);
    border: 1px solid #304761;
    border-radius: 18px;
}
QFrame#rarityCard {
    border-radius: 18px;
    background: #111B29;
    border: 1px solid #31435E;
}
QLabel#title {
    font-size: 32px;
    font-weight: 700;
}
QLabel#subtitle {
    color: #AEBBD0;
    font-size: 14px;
}
QLabel#sectionTitle {
    font-size: 20px;
    font-weight: 700;
}
QLabel#statusBadge {
    background: #182435;
    border: 1px solid #385275;
    border-radius: 999px;
    padding: 5px 11px;
}
QLabel#mutedText {
    color: #95A6BF;
}
QLabel#pill {
    background: #182435;
    border: 1px solid #385275;
    border-radius: 999px;
    padding: 6px 10px;
    font-weight: 700;
}
QLineEdit, QComboBox, QListWidget, QTextEdit, QSpinBox {
    background: #0D1622;
    border: 1px solid #324765;
    border-radius: 14px;
    padding: 8px 10px;
    selection-background-color: #1F6FEB;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QSpinBox:focus, QListWidget:focus {
    border: 1px solid #5A8BFF;
}
QComboBox QAbstractItemView, QListWidget {
    outline: 0;
}
QListWidget {
    padding: 6px;
}
QListWidget::item {
    padding: 10px;
    border-radius: 10px;
}
QListWidget::item:selected {
    background: #1A2B41;
    border: 1px solid #4A73A8;
}
QTabWidget::pane {
    border: 1px solid #27384F;
    border-radius: 16px;
    background: #111B29;
    top: -1px;
}
QTabBar::tab {
    background: #101A27;
    border: 1px solid #223248;
    border-bottom: none;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    padding: 11px 18px;
    margin-right: 6px;
}
QTabBar::tab:selected {
    background: #1A283B;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2576FF, stop:1 #3C8DFF);
    border: none;
    border-radius: 13px;
    padding: 10px 16px;
    font-weight: 700;
}
QPushButton:hover {
    background: #4C98FF;
}
QPushButton:pressed {
    background: #1E5FCA;
}
QPushButton:disabled {
    background: #243246;
    color: #8090A8;
}
QPushButton#secondaryButton {
    background: #172332;
    border: 1px solid #38506E;
}
QPushButton#secondaryButton:hover {
    background: #22344B;
}
QPushButton#dangerButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #A73434, stop:1 #D65050);
}
QPushButton#dangerButton:hover {
    background: #DB5858;
}
QPushButton#successButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D9B59, stop:1 #34C978);
}
QPushButton#successButton:hover {
    background: #3AD784;
}
QPushButton#ghostButton {
    background: transparent;
    border: 1px solid #3A5275;
}
QPushButton#ghostButton:hover {
    background: #162335;
}
QPushButton#navButton {
    text-align: left;
    background: transparent;
    border: 1px solid transparent;
    padding: 13px 14px;
}
QPushButton#navButton:checked {
    background: #16263B;
    border: 1px solid #4670A7;
}
QScrollArea {
    border: none;
}
QProgressBar {
    border: 1px solid #304B6C;
    border-radius: 10px;
    background: #0E1723;
    text-align: center;
    min-height: 18px;
}
QProgressBar::chunk {
    border-radius: 9px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2AB96E, stop:1 #69E094);
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
