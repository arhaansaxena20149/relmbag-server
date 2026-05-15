from __future__ import annotations

import os
import sys

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QListView,
    QWidget,
)

UI_EFFECTS_DISABLED = os.environ.get(
    "RELMBAG_LIGHTWEIGHT_UI",
    "true" if sys.platform != "win32" else "false",
).lower() == "true"
_PIXMAP_CACHE: dict[tuple[str, int, bool], QPixmap] = {}


def load_pixmap(path: str, size: int, from_sprite_sheet: bool = False) -> QPixmap:
    """Loads a pixmap from a file or the cache."""
    cache_key = (path, size, from_sprite_sheet)
    if cache_key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[cache_key]
    
    if from_sprite_sheet:
        # This part needs a proper sprite sheet implementation
        # For now, we'll just return a placeholder
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setBrush(QColor("#2D1F16"))
        painter.drawRect(0, 0, size, size)
        painter.end()
    else:
        pixmap = QPixmap(path)
    
    if pixmap.isNull():
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
    else:
        pixmap = pixmap.scaled(
            size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        
    _PIXMAP_CACHE[cache_key] = pixmap
    return pixmap


APP_STYLESHEET = """
QWidget {
    background: transparent;
    color: #F5EBD5;
    font-family: "Palatino", "Book Antiqua", "Georgia", serif;
    font-size: 14px;
    selection-background-color: #7B57D1;
    selection-color: #FFF8EA;
}
QMainWindow, QDialog {
    background:
        qradialgradient(cx: 0.18, cy: 0.16, radius: 0.9, fx: 0.18, fy: 0.16, stop: 0 #3D2E3A, stop: 0.32 #221922, stop: 0.72 #140F17, stop: 1 #0A0810);
}
QWidget#appRoot,
QWidget#shellRoot,
QWidget#authRoot {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #1D1520, stop: 0.35 #130F16, stop: 1 #08070B);
}
QWidget#authRoot {
    background:
        qradialgradient(cx: 0.18, cy: 0.2, radius: 0.9, fx: 0.18, fy: 0.2, stop: 0 #53425C, stop: 0.22 #2E2440, stop: 0.5 #16121F, stop: 1 #09080D);
}
QFrame#shellFrame {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #1B1622, stop: 0.45 #120E16, stop: 1 #09070C);
    border: 2px solid #6E4C35;
    border-radius: 28px;
}
QFrame#sidebarPanel {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #261D2A, stop: 0.5 #19131E, stop: 1 #110D14);
    border: 2px solid #7E5A3B;
    border-radius: 24px;
}
QFrame#contentPanel {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #130F16, stop: 0.65 #0C0A10, stop: 1 #08070B);
    border: 2px solid #7E5A3B;
    border-radius: 24px;
}
QFrame#titlePlaque {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #6B4F63, stop: 0.48 #3C2D43, stop: 1 #241A2A);
    border: 3px solid #C89F62;
    border-radius: 22px;
}
QFrame#stonePanel,
QFrame#panel,
QFrame#accentPanel,
QFrame#heroPanel,
QFrame#onlineCard,
QFrame#rarityCard,
QFrame#creatureCard,
QFrame#tradePanel,
QFrame#tradeStatusPanel,
QFrame#statTile {
    color: #F5EBD5;
}
QFrame#panel,
QFrame#stonePanel,
QFrame#accentPanel,
QFrame#tradePanel {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0.95, y2: 1, stop: 0 #221A27, stop: 0.5 #17111A, stop: 1 #100C12);
    border: 2px solid #866042;
    border-radius: 20px;
}
QFrame#heroPanel {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #544561, stop: 0.18 #332740, stop: 0.58 #1C1826, stop: 1 #100D14);
    border: 2px solid #CAA068;
    border-radius: 24px;
}
QFrame#parchmentPanel {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #F6E9C8, stop: 0.45 #E9D8B4, stop: 1 #D6C09B);
    color: #2A1D16;
    border: 2px solid #B68557;
    border-radius: 22px;
}
QFrame#accentPanel {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #211821, stop: 0.6 #150F16, stop: 1 #0E0B11);
}
QFrame#onlineCard,
QFrame#rarityCard,
QFrame#creatureCard,
QFrame#statTile {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #2A2030, stop: 0.52 #19131E, stop: 1 #120D14);
    border: 2px solid #7E5A3B;
    border-radius: 20px;
}
QFrame#tradeStatusPanel {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #392A43, stop: 1 #1C1521);
    border: 2px solid #D2A568;
    border-radius: 18px;
}
QLabel#title {
    background: transparent;
    color: #FFF3D9;
    font-size: 34px;
    font-weight: 900;
    letter-spacing: 1px;
}
QLabel#displayTitle {
    background: transparent;
    color: #FFF3D9;
    font-size: 46px;
    font-weight: 900;
    letter-spacing: 1px;
}
QLabel#subtitle {
    background: transparent;
    color: #D0B594;
    font-size: 15px;
    font-weight: 600;
    line-height: 1.35;
}
QLabel#sectionTitle {
    background: transparent;
    color: #FFE8C2;
    font-size: 22px;
    font-weight: 900;
    padding-bottom: 6px;
    border-bottom: 1px solid #896447;
}
QLabel#mutedText {
    background: transparent;
    color: #B8A48B;
    font-size: 12px;
    font-weight: 600;
}
QLabel#sidebarTitle {
    background: transparent;
    color: #FFF0D4;
    font-size: 24px;
    font-weight: 900;
}
QLabel#sidebarMeta {
    background: transparent;
    color: #B99D79;
    font-size: 12px;
    font-weight: 700;
}
QLabel#statusBadge,
QLabel#pill,
QLabel#infoChip {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #2D2434, stop: 1 #17111B);
    border: 1px solid #AA8153;
    border-radius: 13px;
    color: #F4E8D4;
    padding: 8px 14px;
    font-weight: 800;
}
QLabel#pill {
    border-radius: 999px;
}
QLabel#panelLabel {
    background: transparent;
    color: #BFA27B;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#panelValue {
    background: transparent;
    color: #FFF4DF;
    font-size: 28px;
    font-weight: 900;
}
QFrame#parchmentPanel QLabel#sectionTitle {
    color: #3A281B;
    border-bottom: 1px solid #A27A51;
}
QFrame#parchmentPanel QLabel#mutedText,
QFrame#parchmentPanel QLabel#panelLabel {
    color: #6E5037;
}
QFrame#parchmentPanel QLabel#statusBadge,
QFrame#parchmentPanel QLabel#pill,
QFrame#parchmentPanel QLabel#infoChip {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #D8C29A, stop: 1 #C1A16E);
    color: #2A1D16;
    border: 1px solid #996C43;
}
QLabel#parchmentBody,
QFrame#parchmentPanel QLabel {
    color: #2A1D16;
}
QPushButton {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #A17A4F, stop: 0.52 #7E5935, stop: 1 #523824);
    color: #FFF1D3;
    border: 2px solid #D9AE71;
    border-radius: 16px;
    padding: 12px 22px;
    font-size: 14px;
    font-weight: 900;
    min-height: 18px;
}
QPushButton:hover {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #B98C58, stop: 0.55 #8F653A, stop: 1 #5B3D25);
    border-color: #F4C883;
}
QComboBox {
    background: #1A121F;
    border: 1px solid #866042;
    border-radius: 8px;
    padding: 6px 12px;
    color: #F5EBD5;
    min-width: 120px;
}
QComboBox:on {
    border-bottom-left-radius: 0px;
    border-bottom-right-radius: 0px;
}
QComboBox QAbstractItemView {
    background: #1A121F;
    border: 1px solid #866042;
    border-top: none;
    selection-background-color: #7B57D1;
    selection-color: #FFF8EA;
    outline: none;
}
QScrollBar:vertical {
    background: #0D0912;
    width: 12px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #523824;
    min-height: 20px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #7E5935;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: #0D0912;
    height: 12px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #523824;
    min-width: 20px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QPushButton:pressed {
    background: #4A3220;
    padding-top: 14px;
    padding-bottom: 10px;
}
QPushButton:disabled {
    background: #3A3038;
    color: #9D8E82;
    border-color: #695543;
}
QPushButton#secondaryButton {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #587AA7, stop: 1 #35506E);
    border-color: #8AB4E2;
}
QPushButton#secondaryButton:hover {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #6990C3, stop: 1 #416487);
}
QPushButton#successButton {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #6CBD57, stop: 0.55 #3D8F46, stop: 1 #245B2E);
    border-color: #B8F59E;
    color: #F6FFEA;
}
QPushButton#successButton:hover {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #82D164, stop: 0.55 #4AA551, stop: 1 #2B6A35);
}
QPushButton#dangerButton {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #D96B55, stop: 0.52 #A64335, stop: 1 #6E231E);
    border-color: #FFAE9A;
    color: #FFF4EE;
}
QPushButton#dangerButton:hover {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #EA7A61, stop: 0.52 #BA4D3D, stop: 1 #7C2A22);
}
QPushButton#ghostButton {
    background: transparent;
    border: 1px solid #9A7652;
    color: #F6E9D6;
}
QPushButton#ghostButton:hover {
    background: rgba(217, 174, 113, 0.10);
    border-color: #E3B873;
    color: #FFF3D9;
}
QPushButton#ghostButton:pressed {
    background: rgba(217, 174, 113, 0.18);
}

QListWidget {
    background: transparent;
    border: none;
}
QListWidget::item {
    border: 1px solid transparent;
}
QListWidget::item:hover {
    border: 1px solid rgba(217, 174, 113, 0.22);
    background: rgba(0, 0, 0, 0.10);
}
QPushButton#navButton {
    text-align: left;
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #261D2A, stop: 1 #140F16);
    border: 1px solid #6B4A33;
    border-radius: 16px;
    color: #D1B38A;
    padding: 13px 16px;
    font-size: 14px;
    font-weight: 800;
}
QPushButton#navButton:hover {
    border-color: #D9AE71;
    color: #FFF0D4;
}
QPushButton#navButton:checked {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #5D4B72, stop: 1 #2C2336);
    border: 2px solid #E3B873;
    color: #FFF4DC;
    padding-left: 18px;
}
QLineEdit, QComboBox, QListWidget, QTextEdit, QSpinBox {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #150F16, stop: 1 #0C090F);
    color: #F8EDD8;
    border: 2px solid #7D5A3B;
    border-radius: 15px;
    padding: 10px 12px;
}
QFrame#parchmentPanel QLineEdit,
QFrame#parchmentPanel QComboBox,
QFrame#parchmentPanel QListWidget,
QFrame#parchmentPanel QTextEdit,
QFrame#parchmentPanel QSpinBox {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #EADAB5, stop: 1 #D7BF96);
    color: #2B1E16;
    border: 2px solid #B68758;
}
QLineEdit:focus, QComboBox:focus, QListWidget:focus, QTextEdit:focus, QSpinBox:focus {
    border-color: #E1B56A;
}
QCheckBox {
    background: transparent;
    color: #F7EAD4;
    spacing: 10px;
    font-weight: 800;
}
QFrame#parchmentPanel QCheckBox {
    color: #342317;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid #A97D4B;
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #1A1318, stop: 1 #0F0B11);
}
QFrame#parchmentPanel QCheckBox::indicator {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #EAD8B5, stop: 1 #D1B384);
    border: 2px solid #A87B4B;
}
QCheckBox::indicator:checked {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #7AD465, stop: 1 #397F44);
    border-color: #C9F9A8;
}
QCheckBox::indicator:hover {
    border-color: #E0B777;
}
QListWidget {
    outline: none;
    padding: 8px;
}
QListWidget::item {
    margin: 4px 0;
    padding: 10px 12px;
    border-radius: 12px;
}
QListWidget::item:selected {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #5A446A, stop: 1 #30243B);
    color: #FFF5E4;
}
QFrame#parchmentPanel QListWidget::item:selected {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #B08C63, stop: 1 #8A6846);
    color: #FFF4E2;
}
QComboBox::drop-down {
    border: none;
    width: 26px;
}
QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 8px solid #DDB270;
    margin-right: 10px;
}
QComboBox QAbstractItemView {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #1B1520, stop: 1 #0E0A11);
    color: #F8EDD8;
    border: 2px solid #A4794D;
    border-radius: 16px;
    outline: none;
    padding: 6px;
    selection-background-color: #6A4F84;
    selection-color: #FFF5E4;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 8px 12px;
    margin: 2px 0;
    border-radius: 10px;
}
QComboBox QAbstractItemView::item:selected {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #6B4F84, stop: 1 #352842);
    color: #FFF6E7;
}
QFrame#parchmentPanel QComboBox QAbstractItemView {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #F3E4C3, stop: 1 #DABD92);
    color: #2B1E16;
    border: 2px solid #B68758;
    selection-background-color: #B79262;
    selection-color: #2B1E16;
}
QFrame#parchmentPanel QComboBox QAbstractItemView::item:selected {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #CCAB78, stop: 1 #A37A4E);
    color: #2B1E16;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 26px;
    border-left: 1px solid #7D5A3B;
}
QTabWidget::pane {
    border: 2px solid #B68758;
    border-radius: 18px;
    top: -2px;
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #F6E9C8, stop: 1 #D9C39E);
}
QTabBar::tab {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #D8C19A, stop: 1 #B99B73);
    color: #3A291D;
    min-width: 130px;
    padding: 11px 18px;
    margin-right: 8px;
    border: 2px solid #B68658;
    border-bottom: none;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    font-weight: 900;
}
QTabBar::tab:selected {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #F8EACA, stop: 1 #E1C99F);
    color: #221712;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #120D13;
    width: 12px;
    margin: 10px 0 10px 0;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: #795534;
    min-height: 30px;
    border-radius: 6px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar:horizontal,
QScrollBar::handle:horizontal,
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
    width: 0;
    height: 0;
}
QProgressBar {
    border: 2px solid #866042;
    border-radius: 12px;
    background: #0D0A10;
    color: #FFF0D2;
    text-align: center;
    min-height: 24px;
    padding: 2px;
}
QProgressBar::chunk {
    border-radius: 8px;
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 #64A6FF, stop: 0.55 #9168F6, stop: 1 #F4A1FF);
}
QMessageBox {
    background:
        qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1, stop: 0 #1B141E, stop: 1 #0B0910);
}
"""


def load_pixmap(image_path: str, size: int) -> QPixmap:
    cache_key = (str(image_path or ""), int(size), UI_EFFECTS_DISABLED)
    cached = _PIXMAP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    pixmap = QPixmap(image_path)
    if pixmap.isNull():
        placeholder = QPixmap(size, size)
        placeholder.fill(Qt.transparent)
        painter = QPainter(placeholder)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#1A1520"))
        painter.setPen(QColor("#B88A5A"))
        painter.drawRoundedRect(0, 0, size - 1, size - 1, 22, 22)
        painter.setPen(QColor("#F5D8A5"))
        painter.drawText(placeholder.rect(), Qt.AlignCenter, "?")
        painter.end()
        _PIXMAP_CACHE[cache_key] = placeholder
        return placeholder
    scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    _PIXMAP_CACHE[cache_key] = scaled
    return scaled


def with_alpha(color: str, alpha: int) -> str:
    color = color.lstrip("#")
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def configure_combo_box(combo: QComboBox, max_visible_items: int = 8) -> QComboBox:
    combo.setFocusPolicy(Qt.StrongFocus)
    combo.setMaxVisibleItems(max_visible_items)
    popup = QListView(combo)
    popup.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
    popup.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    popup.setUniformItemSizes(True)
    popup.setSpacing(2)
    combo.setView(popup)
    return combo


def apply_fade_in(widget: QWidget) -> None:
    if UI_EFFECTS_DISABLED:
        return
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(220)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    animation.start()
    widget._fade_animation = animation


def apply_shadow(widget: QWidget, color: str = "#040307", blur: int = 42, x_offset: int = 0, y_offset: int = 12) -> None:
    if UI_EFFECTS_DISABLED:
        widget.setGraphicsEffect(None)
        return
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(x_offset, y_offset)
    shadow.setColor(QColor(with_alpha(color, 180)))
    widget.setGraphicsEffect(shadow)
    widget._shadow_effect = shadow
