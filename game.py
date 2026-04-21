from __future__ import annotations
import sys
import time
from functools import partial
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThreadPool
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QCheckBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QDialog,
)

import auth
import crate_system
import database
import inventory
import api
from network import debug_log
from config import APP_ICON_PNG, APP_SUBTITLE, APP_TITLE, BASE_VALUES, CRATE_COST, DROP_RATES, RARITY_COLORS, RARITY_ORDER, CREATURES_BY_RARITY, MUTATION_COST, MUTATION_COLORS, MUTATION_RATES
from ui_shared import APP_STYLESHEET, apply_fade_in, apply_shadow, configure_combo_box, load_pixmap, with_alpha
from workers import Worker, HeartbeatWorker
from api import get_users

def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


def status_message(label: QLabel, text: str, color: str) -> None:
    label.setText(text)
    label.setStyleSheet(
        f"color: {color}; font-weight: 600; padding: 6px 0px;"
    )


def show_error(parent: QWidget, message: str) -> None:
    QMessageBox.warning(parent, "RelmBag Arena", message)


def rarity_badge_stylesheet(color: str) -> str:
    return (
        f"background: {color}; color: #081018; border-radius: 999px; "
        "padding: 6px 12px; font-weight: 800;"
    )


def creature_stat_row(creature: dict) -> str:
    stats = creature["stats"]
    return (
        f"HP {stats['HP']}  |  ATK {stats['Attack']}  |  "
        f"DEF {stats['Defense']}  |  SPD {stats['Speed']}"
    )


def creature_move_lines(
    creature: dict,
    unlocked_only: bool = False,
    limit: int | None = None,
) -> list[str]:
    lines: list[str] = []
    for move in creature["moves"]:
        if unlocked_only and not move["unlocked"]:
            continue
        if move["unlocked"]:
            lines.append(
                f"{move['name']}  |  Damage {move['damage']}  |  Cooldown {move['cooldown']}"
            )
        else:
            lines.append(f"{move['name']}  |  Unlocks at level {move['unlock_level']}")
    return lines[:limit] if limit is not None else lines


class GameComboBox(QComboBox):
    def __init__(self, *args, max_visible_items: int = 8, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        configure_combo_box(self, max_visible_items=max_visible_items)

    def wheelEvent(self, event) -> None:
        if not self.view().isVisible() and not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


class BasePage(QWidget):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__()
        self.game_window = game_window

    def refresh_page(self) -> None:
        return


class CreatureCard(QFrame):
    clicked = pyqtSignal(int)

    def __init__(self, creature: dict) -> None:
        super().__init__()
        self.creature = creature
        self.setObjectName("creatureCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(188)
        self.setFixedHeight(258)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        rarity_color = creature["rarity_color"]
        
        # Badge Row
        badge_row = QHBoxLayout()
        mutation = creature.get("mutation", "None")
        if mutation != "None":
            mutation_color = creature.get("mutation_color", "#A0A0A0")
            mut_badge = QLabel(mutation.upper())
            mut_badge.setStyleSheet(
                f"background: {with_alpha(mutation_color, 210)}; color: #120D10; "
                f"border: 1px solid {with_alpha(mutation_color, 255)}; border-radius: 9px; "
                "padding: 2px 8px; font-weight: 900; font-size: 9px;"
            )
            badge_row.addWidget(mut_badge)
        else:
            badge_row.addStretch()

        # Level Badge
        level = QLabel(f"Lv {creature['level']}")
        level.setObjectName("pill")
        level.setStyleSheet(
            f"background: {with_alpha(rarity_color, 210)}; color: #120D10; "
            f"border: 1px solid {with_alpha(rarity_color, 255)}; border-radius: 11px; "
            "padding: 4px 10px; font-weight: 900; font-size: 11px;"
        )
        badge_row.addWidget(level)
        layout.addLayout(badge_row)

        # Image
        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        image.setPixmap(load_pixmap(creature["image_path"], 112))
        image.setStyleSheet(
            f"background: qradialgradient(cx:0.5, cy:0.45, radius:0.9, stop:0 {with_alpha(rarity_color, 80)}, stop:1 rgba(11, 8, 15, 0)); "
            f"border: 2px solid {with_alpha(rarity_color, 135)}; border-radius: 18px;"
        )
        layout.addWidget(image, 1)

        # Name
        name = QLabel(creature["display_name"])
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet(f"font-size: 15px; font-weight: 900; color: {rarity_color};")
        layout.addWidget(name)

        # Rarity
        rarity = QLabel(creature["rarity"])
        rarity.setAlignment(Qt.AlignCenter)
        rarity.setStyleSheet(f"color: {with_alpha(rarity_color, 210)}; font-size: 11px; font-weight: 800;")
        layout.addWidget(rarity)

        # Stats
        stats = QLabel(
            f"ATK {creature['stats']['Attack']}  |  DEF {creature['stats']['Defense']}\n"
            f"Value {creature.get('value', 0)}"
        )
        stats.setAlignment(Qt.AlignCenter)
        stats.setStyleSheet("color: #C7AF8D; font-size: 11px; font-weight: 700;")
        layout.addWidget(stats)

        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        color = self.creature["rarity_color"]
        if selected:
            self.setStyleSheet(
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {with_alpha(color, 58)}, stop:1 #120D14); "
                f"border: 3px solid {color}; border-radius: 20px;"
            )
        else:
            self.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #271D2D, stop:1 #120D14); "
                "border: 2px solid #725237; border-radius: 20px;"
            )

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.creature["id"])
        super().mousePressEvent(event)


class PlayerActionCard(QFrame):
    def __init__(self, username: str, creature_count: int, accent: str, button_text: str, on_click) -> None:
        super().__init__()
        self.setObjectName("onlineCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        avatar = QLabel(username[:1].upper())
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(44, 44)
        avatar.setStyleSheet(
            f"background: {with_alpha(accent, 80)}; border: 1px solid {with_alpha(accent, 180)}; "
            f"border-radius: 22px; color: {accent}; font-size: 18px; font-weight: 800;"
        )

        text_col = QVBoxLayout()
        name = QLabel(username)
        name.setStyleSheet("font-size: 17px; font-weight: 700;")
        meta = QLabel(f"Online now  |  {creature_count} creature{'s' if creature_count != 1 else ''}")
        meta.setObjectName("mutedText")
        text_col.addWidget(name)
        text_col.addWidget(meta)

        action = QPushButton(button_text)
        action.setObjectName("secondaryButton")
        action.clicked.connect(on_click)
        action.setMinimumWidth(120)

        layout.addWidget(avatar)
        layout.addLayout(text_col, 1)
        layout.addWidget(action)


class RarityInfoCard(QFrame):
    def __init__(self, rarity: str) -> None:
        super().__init__()
        self.setObjectName("rarityCard")
        self.rarity = rarity
        color = RARITY_COLORS[rarity]
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 14, 14, 14)
        self.layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel(rarity)
        title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {color};")
        title_row.addWidget(title)
        title_row.addStretch()
        self.arrow = QLabel("▼")
        self.arrow.setStyleSheet(f"color: {color}; font-weight: 800;")
        title_row.addWidget(self.arrow)
        self.layout.addLayout(title_row)

        chance = QLabel(f"{DROP_RATES[rarity]}% drop rate")
        chance.setStyleSheet("font-weight: 800; color: #FFF1D8;")
        value = QLabel(f"Base value: {BASE_VALUES[rarity]}")
        value.setObjectName("mutedText")
        
        self.layout.addWidget(chance)
        self.layout.addWidget(value)

        self.creature_list = QLabel()
        self.creature_list.setWordWrap(True)
        self.creature_list.setStyleSheet(f"color: {with_alpha(color, 200)}; font-size: 12px; margin-top: 5px;")
        names = [c["name"] for c in CREATURES_BY_RARITY.get(rarity, [])]
        self.creature_list.setText("• " + "\n• ".join(names))
        self.creature_list.setVisible(False)
        self.layout.addWidget(self.creature_list)

        bar = QFrame()
        bar.setFixedHeight(8)
        bar.setStyleSheet(
            f"background: {with_alpha(color, 170)}; border-radius: 4px; border: 1px solid {with_alpha(color, 220)};"
        )
        self.layout.addWidget(bar)
        
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        is_visible = self.creature_list.isVisible()
        self.creature_list.setVisible(not is_visible)
        self.arrow.setText("▲" if not is_visible else "▼")
        super().mousePressEvent(event)


class AutoSellDialog(QDialog):
    def __init__(self, selected_rarities: set[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto Sell Preferences")
        self.setModal(True)
        self.setFixedWidth(420)

        self.checkboxes: dict[str, QCheckBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)

        panel = QFrame()
        panel.setObjectName("parchmentPanel")
        apply_shadow(panel, blur=30, y_offset=10)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        title = QLabel("Auto Sell Rarities")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Choose every rarity you want to auto-sell after a pull. This now applies to both single opens and consecutive openings.")
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        for rarity in RARITY_ORDER:
            box = QCheckBox(rarity)
            if rarity in selected_rarities:
                box.setChecked(True)
            box.setStyleSheet(f"font-weight: 800; color: {RARITY_COLORS[rarity]}; padding: 4px 0;")
            self.checkboxes[rarity] = box
            layout.addWidget(box)

        button_row = QHBoxLayout()
        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("ghostButton")
        clear_btn.clicked.connect(self._clear_all)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("successButton")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(clear_btn)
        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        root.addWidget(panel)

    def _clear_all(self) -> None:
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)

    def selected_rarities(self) -> set[str]:
        return {rarity for rarity, checkbox in self.checkboxes.items() if checkbox.isChecked()}


class ConsecutiveOpenDialog(QDialog):
    def __init__(self, max_count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Consecutive Open")
        self.setModal(True)
        self.setFixedWidth(400)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)

        panel = QFrame()
        panel.setObjectName("parchmentPanel")
        apply_shadow(panel, blur=26, y_offset=8)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        title = QLabel("Consecutive Summon")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Choose how many crates to open in one run. Consecutive opens are capped at 10 to keep the client responsive.")
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.count_spin = QSpinBox()
        self.count_spin.setMinimum(1)
        self.count_spin.setMaximum(max(1, min(max_count, 10)))
        self.count_spin.setValue(min(10, max_count))
        self.count_spin.setSuffix(" crates")
        layout.addWidget(self.count_spin)

        button_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.clicked.connect(self.reject)
        open_btn = QPushButton("Start")
        open_btn.setObjectName("successButton")
        open_btn.clicked.connect(self.accept)
        button_row.addStretch(1)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(open_btn)
        layout.addLayout(button_row)

        root.addWidget(panel)

    def selected_count(self) -> int:
        return int(self.count_spin.value())


class AuthPage(QWidget):
    authenticated = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("authRoot")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)

        stage = QFrame()
        stage.setObjectName("shellFrame")
        apply_shadow(stage)
        outer.addWidget(stage)

        stage_layout = QHBoxLayout(stage)
        stage_layout.setContentsMargins(26, 26, 26, 26)
        stage_layout.setSpacing(24)

        self.bg = QFrame(self)
        self.bg.setObjectName("heroPanel")
        self.bg.setMinimumWidth(360)
        apply_shadow(self.bg, blur=50, y_offset=16)
        left_col = QVBoxLayout(self.bg)
        left_col.setContentsMargins(30, 30, 30, 30)
        left_col.setSpacing(18)

        plaque = QFrame()
        plaque.setObjectName("titlePlaque")
        plaque_layout = QVBoxLayout(plaque)
        plaque_layout.setContentsMargins(18, 16, 18, 16)
        icon = QLabel()
        icon.setAlignment(Qt.AlignCenter)
        icon.setPixmap(load_pixmap(str(APP_ICON_PNG), 78))
        title = QLabel("RelmBag Arena")
        title.setObjectName("displayTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("A collectible-creature world of summoning, trading, and tactical battles.")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        plaque_layout.addWidget(icon)
        plaque_layout.addWidget(title)
        plaque_layout.addWidget(subtitle)
        left_col.addWidget(plaque)

        left_intro = QLabel(
            "Step through the gate, claim your account, and start building a vault of creatures worth showing off."
        )
        left_intro.setObjectName("statusBadge")
        left_intro.setWordWrap(True)
        left_col.addWidget(left_intro)

        feature_panel = QFrame()
        feature_panel.setObjectName("accentPanel")
        feature_layout = QVBoxLayout(feature_panel)
        feature_layout.setContentsMargins(20, 20, 20, 20)
        feature_layout.setSpacing(12)
        feature_title = QLabel("Inside The Arena")
        feature_title.setObjectName("sectionTitle")
        feature_layout.addWidget(feature_title)
        for line in [
            "Weighted summons across ten rarities",
            "Creature vault with stats, moves, and value",
            "Player trading and live battle requests",
            "Global chat, profile tracking, and leaderboards",
        ]:
            bullet = QLabel(f"• {line}")
            bullet.setObjectName("mutedText")
            bullet.setWordWrap(True)
            feature_layout.addWidget(bullet)
        left_col.addWidget(feature_panel)
        left_col.addStretch(1)

        tabs = QTabWidget()
        tabs.addTab(self._build_login_tab(), "LOGIN")
        tabs.addTab(self._build_signup_tab(), "SIGN UP")

        card = QFrame()
        card.setObjectName("parchmentPanel")
        card.setMinimumWidth(520)
        apply_shadow(card, color="#0A0810", blur=40, y_offset=14)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 34, 34, 34)
        card_layout.setSpacing(18)

        auth_title = QLabel("Enter The Realm")
        auth_title.setObjectName("sectionTitle")
        auth_title.setAlignment(Qt.AlignCenter)
        auth_subtitle = QLabel("Sign in to continue your run, or create a fresh account and start summoning.")
        auth_subtitle.setObjectName("mutedText")
        auth_subtitle.setAlignment(Qt.AlignCenter)
        auth_subtitle.setWordWrap(True)

        card_layout.addWidget(auth_title)
        card_layout.addWidget(auth_subtitle)
        card_layout.addWidget(tabs)

        stage_layout.addWidget(self.bg, 5)
        stage_layout.addWidget(card, 6)

    def _build_login_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 18, 10, 10)
        layout.setSpacing(14)

        self.login_identifier = QLineEdit()
        self.login_identifier.setPlaceholderText("Username or Email")
        
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Password")
        self.login_password.setEchoMode(QLineEdit.Password)
        
        self.login_status = QLabel()
        self.login_status.setAlignment(Qt.AlignCenter)
        self.login_status.setWordWrap(True)

        login_button = QPushButton("ENTER THE ARENA")
        login_button.setObjectName("successButton")
        login_button.clicked.connect(self.handle_login)

        label = QLabel("IDENTIFIER")
        label.setObjectName("panelLabel")
        layout.addWidget(label)
        layout.addWidget(self.login_identifier)
        label = QLabel("PASSWORD")
        label.setObjectName("panelLabel")
        layout.addWidget(label)
        layout.addWidget(self.login_password)
        layout.addWidget(login_button)
        layout.addWidget(self.login_status)
        layout.addStretch()
        return widget

    def _build_signup_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 18, 10, 10)
        layout.setSpacing(10)

        self.signup_email = QLineEdit()
        self.signup_email.setPlaceholderText("you@example.com")
        self.signup_real_name = QLineEdit()
        self.signup_real_name.setPlaceholderText("Your full name")
        self.signup_username = QLineEdit()
        self.signup_username.setPlaceholderText("Choose a username")
        self.signup_password = QLineEdit()
        self.signup_password.setPlaceholderText("At least 8 characters")
        self.signup_password.setEchoMode(QLineEdit.Password)

        self.signup_status = QLabel()
        self.signup_status.setAlignment(Qt.AlignCenter)
        self.signup_status.setWordWrap(True)

        signup_button = QPushButton("CLAIM YOUR TITLE")
        signup_button.setObjectName("secondaryButton")
        signup_button.clicked.connect(self.handle_signup)

        label = QLabel("EMAIL")
        label.setObjectName("panelLabel")
        layout.addWidget(label)
        layout.addWidget(self.signup_email)
        label = QLabel("FULL NAME")
        label.setObjectName("panelLabel")
        layout.addWidget(label)
        layout.addWidget(self.signup_real_name)
        label = QLabel("USERNAME")
        label.setObjectName("panelLabel")
        layout.addWidget(label)
        layout.addWidget(self.signup_username)
        label = QLabel("PASSWORD")
        label.setObjectName("panelLabel")
        layout.addWidget(label)
        layout.addWidget(self.signup_password)
        layout.addWidget(signup_button)
        layout.addWidget(self.signup_status)
        layout.addStretch()
        return widget

    def handle_login(self) -> None:
        self.login_status.setText("Logging in...")
        self.login_status.setStyleSheet("color: #F2C14E;")
        worker = Worker(auth.login_user, self.login_identifier.text(), self.login_password.text())
        worker.signals.finished.connect(self._on_auth_success)
        worker.signals.error.connect(lambda e: status_message(self.login_status, str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def handle_signup(self) -> None:
        self.signup_status.setText("Creating account...")
        self.signup_status.setStyleSheet("color: #F2C14E;")
        worker = Worker(
            auth.signup_user,
            self.signup_email.text(),
            self.signup_real_name.text(),
            self.signup_username.text(),
            self.signup_password.text(),
        )
        worker.signals.finished.connect(self._on_auth_success)
        worker.signals.error.connect(lambda e: status_message(self.signup_status, str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def _on_auth_success(self, user: dict) -> None:
        self.authenticated.emit(user)


class DashboardPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        layout = QVBoxLayout(self)
        layout.setSpacing(25)
        layout.setContentsMargins(34, 34, 34, 34)

        # Welcome Portal
        hero = QFrame()
        hero.setObjectName("heroPanel")
        apply_shadow(hero, blur=36, y_offset=12)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(40, 40, 40, 40)
        
        self.welcome_label = QLabel("Welcome back, Traveler")
        self.welcome_label.setObjectName("displayTitle")
        subtitle = QLabel("The Realm awaits your next command. Manage your collection or challenge rivals.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(self.welcome_label)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        # Stats Grid
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)
        
        self.creature_count = self._stat_card("CREATURES", "0")
        self.total_value = self._stat_card("TOTAL VALUE", "0")
        self.highest_rarity = self._stat_card("PEAK RARITY", "None")
        
        stats_layout.addWidget(self.creature_count[0])
        stats_layout.addWidget(self.total_value[0])
        stats_layout.addWidget(self.highest_rarity[0])
        layout.addLayout(stats_layout)

        # Quick Actions
        quick_panel = QFrame()
        quick_panel.setObjectName("panel")
        apply_shadow(quick_panel, blur=34, y_offset=10)
        quick_layout = QVBoxLayout(quick_panel)
        quick_layout.setContentsMargins(30, 30, 30, 30)
        
        quick_title = QLabel("Quick Travel")
        quick_title.setObjectName("sectionTitle")
        quick_layout.addWidget(quick_title)

        buttons = QGridLayout()
        buttons.setSpacing(15)
        actions = [
            ("Summon Chamber", "crate"),
            ("View Inventory", "inventory"),
            ("Trading Hall", "trading"),
            ("Battle Arena", "fighting"),
        ]
        for index, (label, page_key) in enumerate(actions):
            button = QPushButton(label)
            if page_key in {"crate", "trading", "fighting"}:
                button.setObjectName("secondaryButton")
            button.clicked.connect(partial(self.game_window.navigate, page_key))
            buttons.addWidget(button, index // 2, index % 2)
        quick_layout.addLayout(buttons)
        layout.addWidget(quick_panel)
        layout.addStretch(1)

    def _stat_card(self, heading: str, value: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("statTile")
        card.setFixedHeight(136)
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setContentsMargins(18, 14, 18, 14)
        
        label = QLabel(heading)
        label.setObjectName("panelLabel")
        label.setAlignment(Qt.AlignCenter)
        
        value_label = QLabel(value)
        value_label.setObjectName("panelValue")
        value_label.setAlignment(Qt.AlignCenter)
        
        card_layout.addWidget(label)
        card_layout.addWidget(value_label)
        return card, value_label

    def refresh_page(self) -> None:
        user = self.game_window.current_user
        if not user:
            return
        
        # FIX: Move inventory summary to worker thread
        worker = Worker(inventory.get_inventory_summary, user.get("username"))
        worker.signals.finished.connect(self._on_summary_fetched)
        QThreadPool.globalInstance().start(worker)

    def _on_summary_fetched(self, summary: dict) -> None:
        try:
            user = self.game_window.current_user
            if not user or not isinstance(summary, dict) or not self.isVisible():
                return
            
            self.welcome_label.setText(f"Welcome back, {user.get('username', 'Player')}")
            self.creature_count[1].setText(str(summary.get("count", 0)))
            self.total_value[1].setText(str(summary.get("total_value", 0)))
            self.highest_rarity[1].setText(summary.get("highest_rarity", "None"))
        except RuntimeError:
            pass


class CratePage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self.roll_timer = QTimer(self)
        self.roll_timer.timeout.connect(self._advance_roll_animation)
        self.roll_ticks = 0
        self.auto_sell_rarities: set[str] = set()
        self._summon_in_flight = False
        self._result_placeholder = load_pixmap("", 180)

        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(34, 34, 34, 34)

        hero_panel = QFrame()
        hero_panel.setObjectName("heroPanel")
        apply_shadow(hero_panel, blur=36, y_offset=12)
        hero_layout = QVBoxLayout(hero_panel)
        title = QLabel("Summon Chamber")
        title.setObjectName("displayTitle")
        subtitle = QLabel("One crate. Ten rarities. Every pull uses the weighted table below, and every reward lands in your collection instantly.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        badge_row = QHBoxLayout()
        self.token_label = QLabel()
        self.token_label.setObjectName("statusBadge")
        self.cost_label = QLabel(f"Crate Cost: {CRATE_COST} tokens")
        self.cost_label.setObjectName("statusBadge")
        self.feedback_label = QLabel()
        self.feedback_label.setWordWrap(True)
        badge_row.addWidget(self.token_label)
        badge_row.addWidget(self.cost_label)
        badge_row.addStretch(1)

        self.open_button = QPushButton("Open Crate")
        self.open_button.setObjectName("successButton")
        self.open_button.clicked.connect(self.open_crate)
        
        self.consecutive_button = QPushButton("Consecutive Open")
        self.consecutive_button.setObjectName("secondaryButton")
        self.consecutive_button.clicked.connect(self.show_consecutive_dialog)
        
        self.auto_sell_button = QPushButton()
        self.auto_sell_button.setObjectName("secondaryButton")
        self.auto_sell_button.setFixedWidth(220)
        self.auto_sell_button.clicked.connect(self.show_auto_sell_dialog)
        self._refresh_auto_sell_button()
        
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.open_button)
        btn_row.addWidget(self.consecutive_button)
        btn_row.addWidget(self.auto_sell_button)
        btn_row.addStretch()
        
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(badge_row)
        hero_layout.addWidget(self.feedback_label)
        
        # Daily Reward Section
        self.daily_reward_panel = QFrame()
        self.daily_reward_panel.setObjectName("parchmentPanel")
        daily_layout = QHBoxLayout(self.daily_reward_panel)
        daily_layout.setContentsMargins(15, 10, 15, 10)
        
        self.daily_status_label = QLabel("Daily Reward: Available!")
        self.daily_status_label.setStyleSheet("font-weight: 900; color: #2A1D16;")
        self.claim_daily_btn = QPushButton("Claim Daily")
        self.claim_daily_btn.setObjectName("successButton")
        self.claim_daily_btn.clicked.connect(self.claim_daily_reward)
        
        daily_layout.addWidget(self.daily_status_label)
        daily_layout.addStretch()
        daily_layout.addWidget(self.claim_daily_btn)
        
        hero_layout.addWidget(self.daily_reward_panel)
        hero_layout.addLayout(btn_row)
        layout.addWidget(hero_panel)

        body = QHBoxLayout()

        self.result_panel = QFrame()
        self.result_panel.setObjectName("panel")
        apply_shadow(self.result_panel, blur=34, y_offset=10)
        result_layout = QVBoxLayout(self.result_panel)
        result_layout.setContentsMargins(24, 24, 24, 24)
        result_title = QLabel("Latest Pull")
        result_title.setObjectName("sectionTitle")
        self.result_rarity = QLabel("No creature pulled yet")
        self.result_rarity.setAlignment(Qt.AlignCenter)
        self.result_rarity.setObjectName("pill")
        self.result_image = QLabel()
        self.result_image.setAlignment(Qt.AlignCenter)
        self.result_image.setPixmap(self._result_placeholder)
        self.result_name = QLabel("Your next creature will appear here.")
        self.result_name.setAlignment(Qt.AlignCenter)
        self.result_name.setStyleSheet("font-size: 22px; font-weight: 700;")
        self.result_meta = QLabel("Spend tokens to roll.")
        self.result_meta.setAlignment(Qt.AlignCenter)
        self.result_meta.setWordWrap(True)
        self.result_stats = QLabel("Summoned stats will appear after a pull.")
        self.result_stats.setWordWrap(True)
        self.result_stats.setAlignment(Qt.AlignCenter)
        self.result_glow = QLabel("Weighted odds live on the right.")
        self.result_glow.setAlignment(Qt.AlignCenter)
        self.result_glow.setObjectName("mutedText")
        result_layout.addWidget(result_title)
        result_layout.addWidget(self.result_rarity, alignment=Qt.AlignCenter)
        result_layout.addWidget(self.result_image)
        result_layout.addWidget(self.result_name)
        result_layout.addWidget(self.result_meta)
        result_layout.addWidget(self.result_stats)
        result_layout.addWidget(self.result_glow)
        body.addWidget(self.result_panel, 1)

        odds_panel = QFrame()
        odds_panel.setObjectName("panel")
        apply_shadow(odds_panel, blur=34, y_offset=10)
        odds_layout = QVBoxLayout(odds_panel)
        odds_title = QLabel("Drop Table")
        odds_title.setObjectName("sectionTitle")
        odds_hint = QLabel("Rarity color, exact chance, and base value are always visible while you summon.")
        odds_hint.setObjectName("subtitle")
        odds_hint.setWordWrap(True)
        odds_layout.addWidget(odds_title)
        odds_layout.addWidget(odds_hint)

        odds_scroll = QScrollArea()
        odds_scroll.setWidgetResizable(True)
        odds_scroll.setFrameShape(QFrame.NoFrame)
        odds_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        odds_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        odds_container = QWidget()
        odds_grid = QGridLayout(odds_container)
        odds_grid.setContentsMargins(0, 0, 10, 0)
        odds_grid.setSpacing(12)
        for index, rarity in enumerate(RARITY_ORDER):
            odds_grid.addWidget(RarityInfoCard(rarity), index // 2, index % 2)
        odds_scroll.setWidget(odds_container)
        odds_scroll.verticalScrollBar().setSingleStep(24)
        odds_layout.addWidget(odds_scroll)
        body.addWidget(odds_panel, 1)

        layout.addLayout(body)
        layout.addStretch(1)

    def refresh_page(self) -> None:
        user = self.game_window.current_user
        if user:
            self.sync_token_balance(int(user.get("tokens", 0) or 0))
        if not self.feedback_label.text():
            status_message(self.feedback_label, "Browse the odds or spend tokens to summon.", "#AEBBD0")

    def sync_token_balance(self, tokens: int) -> None:
        self.token_label.setText(f"Balance: {max(0, int(tokens))} tokens")

    def _set_summon_controls_enabled(self, enabled: bool) -> None:
        self._summon_in_flight = not enabled
        self.open_button.setEnabled(enabled)
        self.consecutive_button.setEnabled(enabled)
        self.auto_sell_button.setEnabled(enabled)

    def claim_daily_reward(self) -> None:
        user = self.game_window.current_user
        if not user: return
        
        self.claim_daily_btn.setEnabled(False)
        worker = Worker(api.request_json, "post", "claim_daily", json={"user_id": user.get("id")})
        worker.signals.finished.connect(self._on_daily_claimed)
        worker.signals.error.connect(lambda e: self._on_daily_error(str(e)))
        QThreadPool.globalInstance().start(worker)

    def _on_daily_claimed(self, res) -> None:
        if isinstance(res, dict) and res.get("status") == "success":
            earned = res.get("tokens_earned", 0)
            streak = res.get("new_streak", 1)
            self.daily_status_label.setText(f"Claimed {earned} tokens! Day {streak} Streak.")
            self.daily_status_label.setStyleSheet("font-weight: 800; color: #63D471;")
            new_balance = res.get("current_tokens")
            if new_balance is None and self.game_window.current_user is not None:
                new_balance = int(self.game_window.current_user.get("tokens", 0) or 0) + int(earned or 0)
            if new_balance is not None:
                self.game_window.update_token_balance(int(new_balance))
            self.game_window.refresh_page_if_visible("profile")
        else:
            msg = res.get("message", "Error claiming reward") if isinstance(res, dict) else "Error"
            self.daily_status_label.setText(msg)
            self.daily_status_label.setStyleSheet("font-weight: 800; color: #F47C7C;")
            self.claim_daily_btn.setEnabled(True)

    def _on_daily_error(self, err: str) -> None:
        self.daily_status_label.setText("Already claimed today!")
        self.daily_status_label.setStyleSheet("font-weight: 800; color: #F47C7C;")
        self.claim_daily_btn.setEnabled(True)

    def open_crate(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        if self._summon_in_flight:
            return
        if user["tokens"] < CRATE_COST:
            status_message(self.feedback_label, "Not enough tokens.", "#F47C7C")
            return
        self.roll_ticks = 0
        self._set_summon_controls_enabled(False)
        status_message(self.feedback_label, "Crate spinning up...", "#F2C14E")
        self.roll_timer.start(80)

    def _advance_roll_animation(self) -> None:
        self.roll_ticks += 1
        
        # Shuffle through random creatures
        all_creatures = []
        for rarity_list in CREATURES_BY_RARITY.values():
            all_creatures.extend(rarity_list)
        
        random_creature = random.choice(all_creatures)
        self.result_image.setPixmap(self._result_placeholder)
        self.result_name.setText(random_creature["name"])
        self.result_name.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {RARITY_COLORS[random_creature['rarity']]};")
        self.result_rarity.setText(random_creature["rarity"])
        self.result_rarity.setStyleSheet(rarity_badge_stylesheet(RARITY_COLORS[random_creature['rarity']]))

        if self.roll_ticks >= 15:
            self.roll_timer.stop()
            self._finish_roll()

    def show_consecutive_dialog(self) -> None:
        user = self.game_window.current_user
        if not user:
            return

        max_possible = user["tokens"] // CRATE_COST
        if max_possible <= 0:
            show_error(self, "Not enough tokens for even one crate!")
            return

        dialog = ConsecutiveOpenDialog(min(max_possible, 10), self)
        if dialog.exec_() == QDialog.Accepted:
            self._run_consecutive_open(dialog.selected_count())

    def show_auto_sell_dialog(self) -> None:
        dialog = AutoSellDialog(self.auto_sell_rarities, self)
        if dialog.exec_() == QDialog.Accepted:
            self.auto_sell_rarities = dialog.selected_rarities()
            self._refresh_auto_sell_button()

    def _refresh_auto_sell_button(self) -> None:
        if not self.auto_sell_rarities:
            self.auto_sell_button.setText("Auto Sell: None")
            return

        ordered = [rarity for rarity in RARITY_ORDER if rarity in self.auto_sell_rarities]
        if len(ordered) <= 2:
            self.auto_sell_button.setText("Auto Sell: " + ", ".join(ordered))
        else:
            self.auto_sell_button.setText(f"Auto Sell: {len(ordered)} rarities")

    def _run_consecutive_open(self, count: int) -> None:
        user = self.game_window.current_user
        if not user:
            return
        if self._summon_in_flight:
            return

        max_possible = max(0, user["tokens"] // CRATE_COST)
        if max_possible <= 0:
            status_message(self.feedback_label, "Not enough tokens.", "#F47C7C")
            return

        count = max(1, min(int(count), 10, max_possible))
        status_message(self.feedback_label, f"Opening {count} crates...", "#F2C14E")
        self._set_summon_controls_enabled(False)
        
        selected_auto_sell = set(self.auto_sell_rarities)

        def _bulk_open(username: str, n: int, sell_rarities: set[str]):
            results = []
            for _ in range(n):
                res = crate_system.open_crate(username)
                if res.get("creature", {}).get("rarity") in sell_rarities:
                    creature_id = res["creature"]["id"]
                    sell_result = api.request_json("post", "sell_creature", json={"user_id": username, "creature_id": creature_id}) or {}
                    if sell_result.get("status") == "success":
                        refund = int(sell_result.get("refund", 0) or 0)
                        res["auto_sold"] = True
                        res["sell_refund"] = refund
                        updated_tokens = sell_result.get("remaining_tokens")
                        if updated_tokens is None:
                            updated_tokens = int(res.get("remaining_tokens", 0) or 0) + refund
                        res["remaining_tokens"] = int(updated_tokens)
                    else:
                        res["auto_sell_error"] = sell_result.get("message", "Auto-sell failed.")
                results.append(res)
            return results

        worker = Worker(_bulk_open, user.get("username"), count, selected_auto_sell)
        worker.signals.finished.connect(self._on_bulk_opened)
        worker.signals.error.connect(lambda e: self._on_bulk_error(str(e)))
        QThreadPool.globalInstance().start(worker)

    def _refresh_post_summon_pages(self) -> None:
        self.game_window.refresh_page_if_visible("inventory")
        self.game_window.refresh_page_if_visible("dashboard")
        self.game_window.refresh_page_if_visible("profile")

    def _apply_crate_result(self, result: dict, *, update_feedback: bool) -> bool:
        if not isinstance(result, dict):
            return False

        creature = result.get("creature")
        if not creature:
            return False

        remaining_tokens = result.get("remaining_tokens")
        if remaining_tokens is not None:
            self.game_window.update_token_balance(int(remaining_tokens))

        if not self.isVisible():
            return True

        self.result_image.setPixmap(load_pixmap(creature.get("image_path"), 180))

        rarity_color = creature.get("rarity_color", "#FFFFFF")
        self.result_panel.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {with_alpha(rarity_color, 68)}, stop:1 #142236); "
            f"border: 1px solid {with_alpha(rarity_color, 205)}; border-radius: 18px;"
        )

        rarity = creature.get("rarity", "Common")
        self.result_rarity.setText(rarity)
        self.result_rarity.setStyleSheet(rarity_badge_stylesheet(rarity_color))

        display_name = creature.get("display_name", "Unknown")
        self.result_name.setText(display_name)
        self.result_name.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {rarity_color};")

        self.result_meta.setText(
            f"Summon Chance: {DROP_RATES.get(rarity, 0)}%  |  Level {creature.get('level', 1)}  |  Trade Value {creature.get('value', 0)}\n"
            f"Remaining Tokens: {result.get('remaining_tokens', 0)}  |  Crate Cost: {result.get('crate_cost', 0)}"
        )
        self.result_stats.setText(
            "Combat Stats\n"
            f"{creature_stat_row(creature)}\n"
            f"Unlocked Moves: {', '.join(move.get('name', 'move') for move in creature.get('moves', []) if move.get('unlocked'))}"
        )
        self.result_glow.setText(
            f"You summoned a {rarity} creature. Sprite, rarity, and drop chance stay visible here after every pull."
        )
        self.result_glow.setStyleSheet(
            f"background: {with_alpha(rarity_color, 70)}; border: 1px solid {with_alpha(rarity_color, 190)}; "
            "border-radius: 14px; padding: 8px 10px; font-weight: 700;"
        )

        if result.get("auto_sold"):
            refund = int(result.get("sell_refund", 0) or 0)
            self.result_glow.setText(
                f"You summoned a {rarity} creature and auto-sold it immediately because that rarity is selected."
            )
            if update_feedback:
                status_message(self.feedback_label, f"Crate opened and auto-sold successfully for {refund} tokens.", "#63D471")
        elif result.get("auto_sell_error"):
            if update_feedback:
                status_message(self.feedback_label, f"Crate opened, but auto-sell failed: {result['auto_sell_error']}", "#F2C14E")
        elif update_feedback:
            status_message(self.feedback_label, "Crate opened successfully.", "#63D471")

        return True

    def _on_bulk_opened(self, results: list) -> None:
        self._set_summon_controls_enabled(True)

        if not results:
            return

        last_res = results[-1]
        self._apply_crate_result(last_res, update_feedback=False)
        
        rarity_counts = {}
        sold_count = 0
        auto_sell_failures = 0
        for r in results:
            rarity = r.get("creature", {}).get("rarity", "Unknown")
            rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
            if r.get("auto_sold"):
                sold_count += 1
            if r.get("auto_sell_error"):
                auto_sell_failures += 1
        
        summary = ", ".join([f"{count} {rarity}" for rarity, count in rarity_counts.items()])
        msg = f"Opened {len(results)} crates: {summary}."
        if sold_count > 0:
            msg += f" (Auto-sold {sold_count} creatures)"
        if auto_sell_failures > 0:
            msg += f" ({auto_sell_failures} auto-sell issue{'s' if auto_sell_failures != 1 else ''})"

        status_message(self.feedback_label, msg, "#63D471")
        self._refresh_post_summon_pages()

    def _on_bulk_error(self, err: str) -> None:
        self._set_summon_controls_enabled(True)
        status_message(self.feedback_label, err, "#F47C7C")

    def _finish_roll(self) -> None:
        user = self.game_window.current_user
        if not user:
            return

        selected_auto_sell = set(self.auto_sell_rarities)

        def _open_and_maybe_sell(username: str, sell_rarities: set[str]) -> dict:
            result = api.request_json("post", "open_crate", json={"username": username}) or {}
            if result.get("status") != "success":
                raise ValueError(result.get("message", "Failed to open crate."))
            creature = result.get("creature", {})
            creature_id = creature.get("id")
            if creature.get("rarity") in sell_rarities and creature_id is not None:
                sell_result = api.request_json("post", "sell_creature", json={"user_id": username, "creature_id": creature_id}) or {}
                if sell_result.get("status") == "success":
                    refund = int(sell_result.get("refund", 0) or 0)
                    result["auto_sold"] = True
                    result["sell_refund"] = refund
                    # remaining_tokens from sell_result is correct
                    updated_tokens = sell_result.get("remaining_tokens")
                    if updated_tokens is None:
                        updated_tokens = int(result.get("remaining_tokens", 0) or 0) + refund
                    result["remaining_tokens"] = int(updated_tokens)
                else:
                    result["auto_sell_error"] = sell_result.get("message", "Auto-sell failed.")
            return result

        worker = Worker(_open_and_maybe_sell, user.get("username"), selected_auto_sell)
        worker.signals.finished.connect(self._on_crate_opened)
        worker.signals.error.connect(self._on_crate_open_error)
        QThreadPool.globalInstance().start(worker)

    def _on_crate_opened(self, result: dict) -> None:
        try:
            self._set_summon_controls_enabled(True)
            if not self._apply_crate_result(result, update_feedback=True):
                return
            self._refresh_post_summon_pages()
        except RuntimeError:
            pass

    def _on_crate_open_error(self, error: Exception) -> None:
        self._set_summon_controls_enabled(True)
        status_message(self.feedback_label, str(error), "#F47C7C")


class InventoryPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self.current_cards: dict[int, CreatureCard] = {}
        self.current_creatures: dict[int, dict] = {}
        self.selected_creature_id: int | None = None
        self._refresh_in_flight = False

        root = QHBoxLayout(self)
        root.setSpacing(25)
        root.setContentsMargins(28, 28, 28, 28)

        # Left side: Grid
        left_side = QVBoxLayout()
        
        header = QVBoxLayout()
        title = QLabel("Creature Collection")
        title.setObjectName("sectionTitle")
        self.inventory_summary = QLabel("Loading creatures...")
        self.inventory_summary.setObjectName("statusBadge")
        header.addWidget(title)
        header.addWidget(self.inventory_summary)
        
        controls = QHBoxLayout()
        self.sort_combo = GameComboBox()
        self.sort_combo.addItems(["Rarity", "Value", "Level"])
        self.sort_combo.currentTextChanged.connect(self.refresh_page)
        self.filter_combo = GameComboBox(max_visible_items=10)
        self.filter_combo.addItems(["All Rarities"] + RARITY_ORDER)
        self.filter_combo.currentTextChanged.connect(self.refresh_page)
        controls.addWidget(QLabel("Sort:"))
        controls.addWidget(self.sort_combo)
        controls.addWidget(QLabel("Filter:"))
        controls.addWidget(self.filter_combo)
        controls.addStretch()
        header.addLayout(controls)
        left_side.addLayout(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.grid_container)
        left_side.addWidget(self.scroll_area)
        
        root.addLayout(left_side, 3)

        # Right side: Parchment Detail
        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("parchmentPanel")
        self.detail_panel.setFixedWidth(350)
        apply_shadow(self.detail_panel, color="#08060A", blur=32, y_offset=10)
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(25, 25, 25, 25)
        detail_layout.setSpacing(15)

        self.detail_image = QLabel()
        self.detail_image.setAlignment(Qt.AlignCenter)
        self.detail_image.setFixedSize(200, 200)
        self.detail_image.setStyleSheet("background: rgba(0,0,0,0.05); border-radius: 15px;")
        
        self.detail_name = QLabel("Select a Creature")
        self.detail_name.setAlignment(Qt.AlignCenter)
        self.detail_name.setStyleSheet("font-size: 24px; font-weight: 800; color: #2D1F16;")
        self.detail_name.setWordWrap(True)
        self.detail_name.setTextFormat(Qt.RichText)
        
        self.detail_rarity = QLabel("-")
        self.detail_rarity.setAlignment(Qt.AlignCenter)
        self.detail_rarity.setStyleSheet("font-weight: 700; font-size: 16px;")

        self.detail_stats = QLabel("")
        self.detail_stats.setStyleSheet("color: #4E3B24; font-size: 14px; font-family: 'Palatino';")
        self.detail_stats.setWordWrap(True)

        self.detail_moves = QLabel("")
        self.detail_moves.setStyleSheet("color: #4E3B24; font-size: 13px; font-style: italic;")
        self.detail_moves.setWordWrap(True)

        self.detail_value = QLabel("")
        self.detail_value.setAlignment(Qt.AlignCenter)
        self.detail_value.setStyleSheet("font-weight: 800; color: #8B5E3C; font-size: 18px;")

        detail_layout.addWidget(self.detail_image, 0, Qt.AlignCenter)
        detail_layout.addWidget(self.detail_name)
        detail_layout.addWidget(self.detail_rarity)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background: #C19A6B;")
        detail_layout.addWidget(line)
        
        detail_layout.addWidget(QLabel("<b>BASE ATTRIBUTES</b>"))
        detail_layout.addWidget(self.detail_stats)
        
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("background: #C19A6B;")
        detail_layout.addWidget(line2)
        
        detail_layout.addWidget(QLabel("<b>ABILITIES</b>"))
        detail_layout.addWidget(self.detail_moves)
        
        detail_layout.addStretch()
        
        self.mutate_button = QPushButton(f"Mutation Chamber ({MUTATION_COST} Tokens)")
        self.mutate_button.setObjectName("secondaryButton")
        self.mutate_button.clicked.connect(self.mutate_selected_creature)
        self.mutate_button.setVisible(False)
        detail_layout.addWidget(self.mutate_button)

        self.sell_button = QPushButton("Sell for 50% Value")
        self.sell_button.setObjectName("dangerButton")
        self.sell_button.clicked.connect(self.sell_selected_creature)
        self.sell_button.setVisible(False)
        detail_layout.addWidget(self.sell_button)
        
        detail_layout.addWidget(self.detail_value)

        root.addWidget(self.detail_panel, 2)

    def refresh_page(self) -> None:
        user = self.game_window.current_user
        if user is None or self._refresh_in_flight:
            return
        
        sort_map = {"Rarity": "rarity", "Value": "value", "Level": "level"}
        rarity_filter = self.filter_combo.currentText()
        selected_filter = None if rarity_filter == "All Rarities" else rarity_filter
        
        self._refresh_in_flight = True
        worker = Worker(
            inventory.get_inventory,
            user.get("username"),
            sort_by=sort_map.get(self.sort_combo.currentText(), "rarity"),
            rarity_filter=selected_filter
        )
        worker.signals.finished.connect(self._on_inventory_fetched)
        worker.signals.error.connect(self._on_inventory_error)
        QThreadPool.globalInstance().start(worker)

    def _on_inventory_fetched(self, creatures: list[dict]) -> None:
        self._refresh_in_flight = False
        try:
            if not isinstance(creatures, list) or not self.isVisible():
                return
                
            self.current_creatures = {creature.get("id"): creature for creature in creatures if creature.get("id") is not None}
            total_value = sum(creature.get("value", 0) for creature in creatures)
            
            self.inventory_summary.setText(
                f"{len(creatures)} Creatures Found | Collection Value: {total_value} Tokens"
            )
            clear_layout(self.grid_layout)
            self.current_cards = {}

            if not creatures:
                empty = QLabel("Your collection is empty. Visit the Summon Chamber!")
                empty.setStyleSheet("color: #C19A6B; padding: 40px; font-size: 18px;")
                self.grid_layout.addWidget(empty, 0, 0, Qt.AlignCenter)
                self._clear_details()
                return

            for index, creature in enumerate(creatures):
                card = CreatureCard(creature)
                card.clicked.connect(self.select_creature)
                self.current_cards[creature.get("id")] = card
                self.grid_layout.addWidget(card, index // 4, index % 4)

            if self.selected_creature_id not in self.current_creatures:
                self.selected_creature_id = creatures[0].get("id")
            self.select_creature(self.selected_creature_id)
        except RuntimeError:
            pass

    def _on_inventory_error(self, error: Exception) -> None:
        self._refresh_in_flight = False
        status_message(self.inventory_summary, "Could not refresh collection right now.", "#F47C7C")

    def _clear_details(self) -> None:
        self.detail_image.setPixmap(load_pixmap("", 180))
        self.detail_name.setText("Select a Creature")
        self.detail_rarity.setText("-")
        self.detail_stats.setText("")
        self.detail_moves.setText("")
        self.detail_value.setText("")

    def select_creature(self, creature_id: int) -> None:
        self.selected_creature_id = creature_id
        creature = self.current_creatures.get(creature_id)
        if creature is None:
            self.sell_button.setVisible(False)
            self.mutate_button.setVisible(False)
            return

        self.sell_button.setVisible(True)
        self.mutate_button.setVisible(True)
        for card_id, card in self.current_cards.items():
            card.set_selected(card_id == creature_id)

        self.detail_image.setPixmap(load_pixmap(creature["image_path"], 180))
        
        mutation = creature.get("mutation", "None")
        mutation_color = creature.get("mutation_color", "#A0A0A0")
        if mutation != "None":
            name_text = f"{creature['display_name']}<br><span style='font-size: 16px; color: {mutation_color};'>[{mutation}]</span>"
            self.detail_name.setText(name_text)
        else:
            self.detail_name.setText(creature["display_name"])
            
        self.detail_name.setStyleSheet(f"font-size: 24px; font-weight: 800; color: {creature['rarity_color']};")
        
        self.detail_rarity.setText(creature["rarity"].upper())
        self.detail_rarity.setStyleSheet(f"color: {creature['rarity_color']}; font-weight: 800; font-size: 18px;")
        
        stats = creature["stats"]
        self.detail_stats.setText(
            f"<b>HEALTH:</b> {stats['HP']}<br>"
            f"<b>ATTACK:</b> {stats['Attack']}<br>"
            f"<b>DEFENSE:</b> {stats['Defense']}<br>"
            f"<b>SPEED:</b> {stats['Speed']}"
        )
        
        moves_text = "<br>".join([f"• {line}" for line in creature_move_lines(creature, limit=4)])
        self.detail_moves.setText(moves_text)
        
        self.detail_value.setText(f"VALUE: {creature['value']} TOKENS")

    def mutate_selected_creature(self) -> None:
        if self.selected_creature_id is None:
            return
            
        user = self.game_window.current_user
        if not user or user.get("tokens", 0) < MUTATION_COST:
            show_error(self, f"Insufficient tokens. Mutation costs {MUTATION_COST} tokens.")
            return
            
        confirm = QMessageBox.question(
            self, "Confirm Mutation",
            f"Are you sure you want to mutate this creature for {MUTATION_COST} tokens?\n"
            "This will apply a permanent random mutation (Primal, Abyssal, Void, etc.)",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
            
        worker = Worker(api.request_json, "post", "mutate", json={
            "user_id": user["id"],
            "creature_id": self.selected_creature_id
        })
        worker.signals.finished.connect(self._on_mutation_result)
        QThreadPool.globalInstance().start(worker)

    def _on_mutation_result(self, data) -> None:
        try:
            if not self.isVisible(): return
            if not isinstance(data, dict):
                show_error(self, "Invalid response from server.")
                return
            if data.get("status") == "success":
                mutation = data.get("mutation", "None")
                QMessageBox.information(self, "Mutation Success!", f"Your creature has evolved! Mutation: {mutation}")
                self.game_window.refresh_session_data()
                self.refresh_page()
            else:
                show_error(self, data.get("message", "Mutation failed."))
        except RuntimeError:
            pass

    def sell_selected_creature(self) -> None:
        creature = self.current_creatures.get(self.selected_creature_id)
        if not creature: return
        
        refund = creature["value"] // 2
        reply = QMessageBox.question(
            self, "Sell Creature",
            f"Are you sure you want to sell {creature['display_name']} for {refund} tokens?\n(50% of its trade value)",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            worker = Worker(api.request_json, "post", "sell_creature", json={
                "user_id": self.game_window.current_user.get("username"),
                "creature_id": self.selected_creature_id
            })
            worker.signals.finished.connect(self._on_sold)
            QThreadPool.globalInstance().start(worker)

    def _on_sold(self, res) -> None:
        if isinstance(res, dict) and res.get("status") == "success":
            new_balance = res.get("remaining_tokens")
            if new_balance is None and self.game_window.current_user is not None:
                new_balance = int(self.game_window.current_user.get("tokens", 0) or 0) + int(res.get("refund", 0) or 0)
            if new_balance is not None:
                self.game_window.update_token_balance(int(new_balance))
        self.refresh_page()
        self.game_window.refresh_page_if_visible("profile")
        status_message(self.inventory_summary, "Creature sold successfully.", "#63D471")


class TradingLobby(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self._refresh_in_flight = False
        layout = QVBoxLayout(self)
        layout.setSpacing(25)
        layout.setContentsMargins(34, 34, 34, 34)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        apply_shadow(hero, blur=34, y_offset=12)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("Trading Hall")
        title.setObjectName("displayTitle")
        subtitle = QLabel("Choose an online player to initiate a secure creature trade, then lock in your offer inside a dedicated trading board.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        selection_panel = QFrame()
        selection_panel.setObjectName("panel")
        apply_shadow(selection_panel, blur=30, y_offset=10)
        sel_layout = QVBoxLayout(selection_panel)
        sel_layout.setContentsMargins(30, 30, 30, 30)
        sel_layout.setSpacing(20)

        label = QLabel("SELECT TRADING PARTNER")
        label.setObjectName("sectionTitle")
        sel_layout.addWidget(label)
        self.player_dropdown = GameComboBox(max_visible_items=10)
        self.player_dropdown.setPlaceholderText("Scanning for online players...")
        sel_layout.addWidget(self.player_dropdown)

        self.send_request_button = QPushButton("Send Trade Request")
        self.send_request_button.setObjectName("secondaryButton")
        self.send_request_button.clicked.connect(self.initiate_trade)
        sel_layout.addWidget(self.send_request_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        sel_layout.addWidget(self.status_label)
        
        layout.addWidget(selection_panel)
        layout.addStretch()

    def refresh_page(self) -> None:
        if self._refresh_in_flight:
            return
        self._refresh_in_flight = True
        worker = Worker(get_users)
        worker.signals.finished.connect(self._on_users_fetched)
        worker.signals.error.connect(self._on_users_error)
        QThreadPool.globalInstance().start(worker)

    def _on_users_fetched(self, users: list[dict]) -> None:
        self._refresh_in_flight = False
        try:
            if not self.isVisible() or not isinstance(users, list):
                return
            
            self.player_dropdown.clear()
            current_username = self.game_window.current_user.get("username") if self.game_window.current_user else ""
            online_count = 0
            for user in users:
                if not isinstance(user, dict): continue
                username = user.get("username")
                is_online = bool(user.get("online") or user.get("is_online"))
                if username and username != current_username and is_online:
                    self.player_dropdown.addItem(f"Player: {username}", username)
                    online_count += 1
            
            if online_count == 0:
                self.player_dropdown.setPlaceholderText("No other traders online.")
                self.player_dropdown.setEnabled(False)
                self.send_request_button.setEnabled(False)
                self.status_label.setText("No other players online.")
                self.status_label.setStyleSheet("color: #8B5E3C;")
            else:
                self.player_dropdown.setEnabled(True)
                self.send_request_button.setEnabled(True)
                self.status_label.setText("")
        except Exception as e:
            debug_log(f"[ERROR] TradingLobby data refresh failed: {e}")

    def _on_users_error(self, error: Exception) -> None:
        self._refresh_in_flight = False
        status_message(self.status_label, "Could not load online traders.", "#F47C7C")

    def initiate_trade(self) -> None:
        target = self.player_dropdown.currentData()
        if not target:
            return
        
        self.status_label.setText(f"Sending request to {target}...")
        self.status_label.setStyleSheet("color: #F2C14E;")
        
        worker = Worker(api.create_trade, self.game_window.current_user.get("id"), target)
        worker.signals.finished.connect(self._on_trade_created)
        worker.signals.error.connect(lambda e: status_message(self.status_label, str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def _on_trade_created(self, snapshot: dict) -> None:
        if snapshot.get("status") == "error":
            status_message(self.status_label, snapshot.get("message", "Error"), "#F47C7C")
        else:
            trade_id = snapshot.get("id")
            if trade_id is not None:
                self.game_window.last_trade_statuses[int(trade_id)] = snapshot.get("status", "pending")
            status_message(self.status_label, "Request sent! Waiting for acceptance...", "#63D471")


class FightingLobby(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self._refresh_in_flight = False
        layout = QVBoxLayout(self)
        layout.setSpacing(25)
        layout.setContentsMargins(34, 34, 34, 34)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        apply_shadow(hero, blur=34, y_offset=12)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("Battle Arena")
        title.setObjectName("displayTitle")
        subtitle = QLabel("Challenge a rival to a tactical creature duel.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        selection_panel = QFrame()
        selection_panel.setObjectName("panel")
        apply_shadow(selection_panel, blur=30, y_offset=10)
        sel_layout = QVBoxLayout(selection_panel)
        sel_layout.setContentsMargins(30, 30, 30, 30)
        sel_layout.setSpacing(20)

        label = QLabel("CHOOSE YOUR CHAMPION")
        label.setObjectName("sectionTitle")
        sel_layout.addWidget(label)
        self.creature_dropdown = GameComboBox(max_visible_items=10)
        sel_layout.addWidget(self.creature_dropdown)

        label = QLabel("SELECT OPPONENT")
        label.setObjectName("panelLabel")
        sel_layout.addWidget(label)
        self.player_dropdown = GameComboBox(max_visible_items=10)
        self.player_dropdown.setPlaceholderText("Scanning for rivals...")
        sel_layout.addWidget(self.player_dropdown)

        self.send_request_button = QPushButton("Issue Challenge")
        self.send_request_button.setObjectName("dangerButton")
        self.send_request_button.clicked.connect(self.initiate_battle)
        sel_layout.addWidget(self.send_request_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        sel_layout.addWidget(self.status_label)
        
        layout.addWidget(selection_panel)
        
        # Pending Challenges Section
        pending_panel = QFrame()
        pending_panel.setObjectName("panel")
        apply_shadow(pending_panel, blur=30, y_offset=10)
        pending_layout = QVBoxLayout(pending_panel)
        pending_layout.setContentsMargins(30, 30, 30, 30)
        pending_layout.setSpacing(10)
        
        pending_title = QLabel("PENDING CHALLENGES")
        pending_title.setObjectName("sectionTitle")
        pending_layout.addWidget(pending_title)
        
        self.pending_list = QListWidget()
        self.pending_list.setFixedHeight(180)
        self.pending_list.itemDoubleClicked.connect(self._on_pending_clicked)
        pending_layout.addWidget(self.pending_list)
        
        layout.addWidget(pending_panel)
        layout.addStretch()

    def refresh_page(self) -> None:
        if self._refresh_in_flight or not self.game_window.current_user:
            return
        def _get_lobby_data(username: str, user_id: int):
            users = get_users()
            creatures = inventory.get_inventory(username, sort_by="rarity")
            pending_battles = api.list_incoming_battle_requests(user_id)
            return users, creatures, pending_battles

        self._refresh_in_flight = True
        worker = Worker(_get_lobby_data, self.game_window.current_user.get("username"), self.game_window.current_user.get("id"))
        worker.signals.finished.connect(self._on_data_fetched)
        worker.signals.error.connect(self._on_data_error)
        QThreadPool.globalInstance().start(worker)

    def _on_data_fetched(self, data: tuple) -> None:
        self._refresh_in_flight = False
        try:
            if not self.isVisible() or not isinstance(data, tuple) or len(data) != 3:
                return
            
            users, creatures, pending_battles = data
            
            # Populate Creatures
            self.creature_dropdown.clear()
            if not creatures:
                self.creature_dropdown.addItem("No creatures found!", None)
                self.creature_dropdown.setEnabled(False)
            else:
                self.creature_dropdown.setEnabled(True)
                for c in creatures:
                    self.creature_dropdown.addItem(f"{c.get('display_name', '?')} (Lv {c.get('level', 1)})", c.get('id'))
            
            # Populate Players
            self.player_dropdown.clear()
            current_username = str(self.game_window.current_user.get("username", "")).strip().lower() if self.game_window.current_user else ""
            online_count = 0
            for user in users:
                if not isinstance(user, dict): continue
                username = user.get("username")
                if not username: continue
                
                is_online = bool(user.get("online") or user.get("is_online"))
                if username.strip().lower() != current_username and is_online:
                    # Explicitly use the username string from the DB to avoid any confusion
                    self.player_dropdown.addItem(f"Player: {username}", username)
                    online_count += 1
            
            if online_count == 0:
                self.player_dropdown.setPlaceholderText("No other rivals online.")
                self.player_dropdown.setEnabled(False)
            else:
                self.player_dropdown.setEnabled(True)
            
            # Populate Pending Challenges
            self.pending_list.clear()
            if not pending_battles:
                self.pending_list.addItem("No pending challenges.")
            else:
                for b in pending_battles:
                    item = QListWidgetItem(f"⚔️ {b.get('from_username', 'Unknown')} has challenged you!")
                    item.setData(Qt.UserRole, b)
                    self.pending_list.addItem(item)

            can_fight = online_count > 0 and len(creatures) > 0
            self.send_request_button.setEnabled(can_fight)
            
            if not can_fight:
                msg = "Waiting for rivals..."
                if len(creatures) == 0:
                    msg = "Visit Summon Chamber first!"
                elif online_count == 0:
                    msg = "No other players online."
                self.status_label.setText(msg)
                self.status_label.setStyleSheet("color: #8B5E3C;")
        except Exception as e:
            debug_log(f"[ERROR] FightingLobby data refresh failed: {e}")

    def _on_data_error(self, error: Exception) -> None:
        self._refresh_in_flight = False
        status_message(self.status_label, "Could not load the battle lobby.", "#F47C7C")

    def _on_pending_clicked(self, item: QListWidgetItem) -> None:
        request = item.data(Qt.UserRole)
        if not isinstance(request, dict): return
        
        dialog = BattleRequestDialog(self.game_window, request)
        dialog.exec_()
        self.refresh_page()

    def initiate_battle(self) -> None:
        target = self.player_dropdown.currentData()
        creature_id = self.creature_dropdown.currentData()
        if not target or not creature_id:
            return
        
        status_message(self.status_label, f"Challenging {target}...", "#F2C14E")
        
        worker = Worker(api.create_battle, self.game_window.current_user.get("id"), target, creature_id)
        worker.signals.finished.connect(self._on_battle_created)
        worker.signals.error.connect(lambda e: status_message(self.status_label, str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def _on_battle_created(self, snapshot: dict) -> None:
        if snapshot.get("status") == "error":
            status_message(self.status_label, snapshot.get("message", "Error"), "#F47C7C")
        else:
            battle_id = snapshot.get("id")
            if battle_id is not None:
                self.game_window.last_battle_statuses[int(battle_id)] = snapshot.get("status", "pending")
            status_message(self.status_label, "Challenge issued! Waiting for acceptance...", "#63D471")


class BattleRequestDialog(QDialog):
    def __init__(self, parent: "GameWindow", request: dict) -> None:
        super().__init__(parent)
        self.game_window = parent
        self.request = request
        self.setWindowTitle("Battle Challenge")
        self.setFixedWidth(460)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        shell = QFrame()
        shell.setObjectName("parchmentPanel")
        apply_shadow(shell, blur=32, y_offset=10)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(22, 22, 22, 22)
        shell_layout.setSpacing(12)

        title = QLabel(f"{request['from_username']} has challenged you!")
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)
        shell_layout.addWidget(title)
        shell_layout.addWidget(QLabel("Select your defender:"))
        
        self.creature_combo = GameComboBox(max_visible_items=10)
        self.creature_combo.addItem("Fetching creatures...")
        self.creature_combo.setEnabled(False)
        shell_layout.addWidget(self.creature_combo)
        
        btns = QHBoxLayout()
        self.fight_btn = QPushButton("Fight")
        self.fight_btn.setObjectName("dangerButton")
        self.fight_btn.setEnabled(False)
        self.decline_btn = QPushButton("Decline")
        self.decline_btn.setObjectName("secondaryButton")
        btns.addWidget(self.fight_btn)
        btns.addWidget(self.decline_btn)
        shell_layout.addLayout(btns)
        layout.addWidget(shell)
        
        self.fight_btn.clicked.connect(self.accept_fight)
        self.decline_btn.clicked.connect(self.reject)
        
        # Start inventory fetch
        self.worker = Worker(inventory.get_inventory, self.game_window.current_user["username"])
        self.worker.signals.finished.connect(self._on_inventory_fetched)
        QThreadPool.globalInstance().start(self.worker)

    def _on_inventory_fetched(self, creatures: list[dict]) -> None:
        # Check if dialog still exists (PyQt object might be deleted)
        try:
            if not self.isVisible(): return
            self.creature_combo.clear()
            self.creature_combo.setEnabled(True)
            if not creatures:
                self.creature_combo.addItem("No creatures found!")
                return
            
            for c in creatures:
                self.creature_combo.addItem(f"{c['display_name']} (Lv {c['level']})", c['id'])
            self.fight_btn.setEnabled(True)
        except RuntimeError: # C++ object deleted
            pass

    def accept_fight(self) -> None:
        c_id = self.creature_combo.currentData()
        if not c_id: return
        
        self.fight_btn.setEnabled(False)
        self.fight_btn.setText("PREPARING...")
        
        # We start the accept worker. If it finishes, we'll open the dialog and close this one.
        worker = Worker(api.accept_battle, self.request["id"], self.game_window.current_user["id"], c_id)
        worker.signals.finished.connect(self._on_accepted)
        worker.signals.error.connect(lambda e: show_error(self, str(e)))
        QThreadPool.globalInstance().start(worker)

    def _on_accepted(self, snap: dict) -> None:
        try:
            if snap.get("id"):
                self.game_window.launch_battle_dialog(snap["id"])
            self.accept()
        except RuntimeError:
            pass


class TradeDialog(QDialog):
    def __init__(self, parent: "GameWindow", trade_id: int) -> None:
        super().__init__(parent)
        self.game_window = parent
        self.trade_id = trade_id
        self.current_snapshot = None
        self.user_inventory = []
        
        self.setWindowTitle("Creature Trading Interface")
        self.setFixedSize(1180, 780)
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._refresh_in_flight = False
        
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        shell = QFrame()
        shell.setObjectName("shellFrame")
        apply_shadow(shell, blur=44, y_offset=14)
        shell_root = QVBoxLayout(shell)
        shell_root.setContentsMargins(18, 18, 18, 18)
        shell_root.setSpacing(18)
        root.addWidget(shell)

        header = QFrame()
        header.setObjectName("titlePlaque")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 16, 22, 16)
        self.title_label = QLabel("Creature Trading Interface")
        self.title_label.setObjectName("title")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        self.close_btn = QPushButton("Decline Trade")
        self.close_btn.setObjectName("dangerButton")
        self.close_btn.clicked.connect(self.cancel_trade)
        header_layout.addWidget(self.close_btn)
        shell_root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(18)

        left_panel = QFrame()
        left_panel.setObjectName("tradePanel")
        apply_shadow(left_panel, blur=28, y_offset=8)
        left_side = QVBoxLayout(left_panel)
        left_side.setContentsMargins(20, 20, 20, 20)
        left_side.setSpacing(12)
        label = QLabel("YOUR OFFER")
        label.setObjectName("sectionTitle")
        left_side.addWidget(label)
        self.your_creatures_list = QListWidget()
        left_side.addWidget(self.your_creatures_list)
        
        self.your_token_spin = QSpinBox()
        self.your_token_spin.setMaximum(99999999)
        self.your_token_spin.setPrefix("Tokens: ")
        self.your_token_spin.valueChanged.connect(self.update_token_offer)
        left_side.addWidget(self.your_token_spin)
        
        self.confirm_btn = QPushButton("Approve Trade")
        self.confirm_btn.setObjectName("successButton")
        self.confirm_btn.clicked.connect(self.confirm_trade)
        left_side.addWidget(self.confirm_btn)
        body.addWidget(left_panel, 1)

        middle_panel = QFrame()
        middle_panel.setObjectName("parchmentPanel")
        apply_shadow(middle_panel, color="#0A0810", blur=28, y_offset=8)
        mid_side = QVBoxLayout(middle_panel)
        mid_side.setContentsMargins(20, 20, 20, 20)
        mid_side.setSpacing(12)
        label = QLabel("YOUR COLLECTION")
        label.setObjectName("sectionTitle")
        mid_side.addWidget(label)
        self.inventory_list = QListWidget()
        mid_side.addWidget(self.inventory_list)
        self.add_btn = QPushButton("Add Selected")
        self.add_btn.setObjectName("secondaryButton")
        self.add_btn.clicked.connect(self.add_creature)
        mid_side.addWidget(self.add_btn)
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setObjectName("ghostButton")
        self.remove_btn.clicked.connect(self.remove_creature)
        mid_side.addWidget(self.remove_btn)
        body.addWidget(middle_panel, 1)

        right_panel = QFrame()
        right_panel.setObjectName("tradePanel")
        apply_shadow(right_panel, blur=28, y_offset=8)
        right_side = QVBoxLayout(right_panel)
        right_side.setContentsMargins(20, 20, 20, 20)
        right_side.setSpacing(12)
        label = QLabel("THEIR OFFER")
        label.setObjectName("sectionTitle")
        right_side.addWidget(label)
        self.their_creatures_list = QListWidget()
        right_side.addWidget(self.their_creatures_list)
        self.their_token_label = QLabel("Tokens: 0")
        self.their_token_label.setObjectName("statusBadge")
        right_side.addWidget(self.their_token_label)

        right_side.addStretch(1)
        body.addWidget(right_panel, 1)

        shell_root.addLayout(body, 1)

        footer = QFrame()
        footer.setObjectName("tradeStatusPanel")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 14, 18, 14)
        footer_layout.setSpacing(16)
        footer_label = QLabel("Status")
        footer_label.setObjectName("panelLabel")
        self.status_msg = QLabel("Waiting for confirmation...")
        self.status_msg.setObjectName("statusBadge")
        self.status_msg.setAlignment(Qt.AlignCenter)
        footer_layout.addWidget(footer_label)
        footer_layout.addWidget(self.status_msg, 1)
        shell_root.addWidget(footer)
        
        # Polling Timer
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_trade)
        self.finished.connect(self.poll_timer.stop)
        self.poll_timer.start(2000)
        
        self.refresh_trade()

    def refresh_trade(self) -> None:
        if not self.game_window.current_user or self._refresh_in_flight:
            return
        def _get_trade_data(trade_id: int, user_id: int, username: str):
            snapshot = api.get_trade(trade_id, user_id)
            user_inventory = inventory.get_inventory(username, sort_by="rarity")
            return snapshot, user_inventory

        self._refresh_in_flight = True
        worker = Worker(_get_trade_data, self.trade_id, self.game_window.current_user['id'], self.game_window.current_user['username'])
        worker.signals.finished.connect(self._on_data_fetched)
        worker.signals.error.connect(self._on_refresh_error)
        QThreadPool.globalInstance().start(worker)

    def _on_data_fetched(self, data: tuple) -> None:
        self._refresh_in_flight = False
        try:
            if not self.isVisible(): return
            snapshot, inv = data
            self.current_snapshot = snapshot
            self.user_inventory = inv
            
            if snapshot.get("status") == "completed":
                self.poll_timer.stop()
                QMessageBox.information(self, "Trade Executed", "The trade has been completed successfully!")
                self.accept()
                return
            
            if snapshot.get("status") in ("cancelled", "declined"):
                self.poll_timer.stop()
                QMessageBox.warning(self, "Trade Ended", "This trade has been cancelled or declined.")
                self.reject()
                return

            self.render_snapshot()
        except (RuntimeError, TypeError, KeyError):
            pass

    def _on_refresh_error(self, error: Exception) -> None:
        self._refresh_in_flight = False

    def render_snapshot(self) -> None:
        snap = self.current_snapshot
        if not snap or "your_side" not in snap: return
        your_side = snap['your_side']
        their_side = snap['their_side']
        
        self.title_label.setText(f"Trading with {their_side.get('username', 'Unknown')}")
        
        # Update Your Offer
        self.your_creatures_list.clear()
        for c in your_side.get('creatures', []):
            self.your_creatures_list.addItem(f"{c.get('display_name', '?')} (Lv {c.get('level', 1)})")
        
        # Update Their Offer
        self.their_creatures_list.clear()
        for c in their_side.get('creatures', []):
            self.their_creatures_list.addItem(f"{c.get('display_name', '?')} (Lv {c.get('level', 1)})")
        self.their_token_label.setText(f"Tokens: {their_side.get('tokens', 0)}")
        
        # Update Inventory
        self.inventory_list.clear()
        offered_ids = {c.get('id') for c in your_side.get('creatures', [])}
        for c in self.user_inventory:
            if c.get('id') not in offered_ids:
                self.inventory_list.addItem(f"{c.get('display_name', '?')} (Lv {c.get('level', 1)})")
                self.inventory_list.item(self.inventory_list.count()-1).setData(Qt.UserRole, c.get('id'))

        # Status & Buttons
        is_confirmed = your_side.get('confirmed', False)
        if is_confirmed:
            self.confirm_btn.setText("Offer Locked")
            self.confirm_btn.setEnabled(False)
            self.add_btn.setEnabled(False)
            self.remove_btn.setEnabled(False)
            self.your_token_spin.setEnabled(False)
        else:
            self.confirm_btn.setText("Approve Trade")
            self.confirm_btn.setEnabled(True)
            self.add_btn.setEnabled(True)
            self.remove_btn.setEnabled(True)
            self.your_token_spin.setEnabled(True)

        status_text = "Waiting for partner..."
        if is_confirmed and their_side.get('confirmed', False):
            status_text = "Executing trade..."
        elif is_confirmed:
            status_text = "Waiting for their confirmation..."
        elif their_side.get('confirmed', False):
            status_text = f"{their_side.get('username', 'Partner')} HAS CONFIRMED!"
            
        self.status_msg.setText(status_text)

    def add_creature(self) -> None:
        item = self.inventory_list.currentItem()
        if not item: return
        worker = Worker(api.add_creature_to_trade, self.trade_id, self.game_window.current_user['id'], item.data(Qt.UserRole))
        worker.signals.finished.connect(self.refresh_trade)
        QThreadPool.globalInstance().start(worker)

    def remove_creature(self) -> None:
        if not self.current_snapshot or not self.current_snapshot['your_side']['creatures']: return
        c_id = self.current_snapshot['your_side']['creatures'][0]['id']
        worker = Worker(api.remove_creature_from_trade, self.trade_id, self.game_window.current_user['id'], c_id)
        worker.signals.finished.connect(self.refresh_trade)
        QThreadPool.globalInstance().start(worker)

    def update_token_offer(self) -> None:
        worker = Worker(api.set_trade_tokens, self.trade_id, self.game_window.current_user['id'], self.your_token_spin.value())
        worker.signals.finished.connect(self.refresh_trade)
        QThreadPool.globalInstance().start(worker)

    def confirm_trade(self) -> None:
        worker = Worker(api.confirm_trade, self.trade_id, self.game_window.current_user['id'])
        worker.signals.finished.connect(self.refresh_trade)
        QThreadPool.globalInstance().start(worker)

    def cancel_trade(self) -> None:
        worker = Worker(api.cancel_trade, self.trade_id, self.game_window.current_user['id'])
        worker.signals.finished.connect(self.reject)
        QThreadPool.globalInstance().start(worker)


class BattleDialog(QDialog):
    def __init__(self, parent: "GameWindow", battle_id: int) -> None:
        super().__init__(parent)
        self.game_window = parent
        self.battle_id = battle_id
        self.current_snapshot = None
        
        self.setWindowTitle("Battle Arena")
        self.setFixedSize(1100, 800)
        self.setModal(True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._refresh_in_flight = False
        
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        shell = QFrame()
        shell.setObjectName("shellFrame")
        apply_shadow(shell, blur=44, y_offset=14)
        shell_root = QVBoxLayout(shell)
        shell_root.setContentsMargins(18, 18, 18, 18)
        shell_root.setSpacing(16)
        root.addWidget(shell)
        
        # Header Area
        header = QFrame()
        header.setObjectName("titlePlaque")
        header_layout = QHBoxLayout(header)
        self.title_label = QLabel("Battle Initiated")
        self.title_label.setObjectName("title")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        self.forfeit_btn = QPushButton("FORFEIT")
        self.forfeit_btn.setObjectName("dangerButton")
        self.forfeit_btn.clicked.connect(self.forfeit_battle)
        header_layout.addWidget(self.forfeit_btn)
        shell_root.addWidget(header)
        
        # Arena Area
        arena = QFrame()
        arena.setObjectName("panel")
        apply_shadow(arena, blur=30, y_offset=10)
        arena_layout = QHBoxLayout(arena)
        arena_layout.setContentsMargins(30, 30, 30, 30)
        
        # Player Side
        self.player_side = self._create_combatant_ui("YOU")
        arena_layout.addLayout(self.player_side['layout'], 1)
        
        # VS Label
        vs = QLabel("VS")
        vs.setStyleSheet("font-size: 48px; font-weight: 900; color: #8B5E3C;")
        arena_layout.addWidget(vs)
        
        # Opponent Side
        self.opponent_side = self._create_combatant_ui("OPPONENT")
        arena_layout.addLayout(self.opponent_side['layout'], 1)
        
        shell_root.addWidget(arena, 2)
        
        # Moves & Log
        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 20, 20, 20)
        bottom.setSpacing(20)
        
        # Moves
        moves_frame = QFrame()
        moves_frame.setObjectName("parchmentPanel")
        apply_shadow(moves_frame, color="#0A0810", blur=26, y_offset=8)
        self.moves_layout = QGridLayout(moves_frame)
        self.move_btns = []
        for i in range(4):
            btn = QPushButton(f"MOVE {i+1}")
            btn.setFixedSize(200, 80)
            btn.clicked.connect(partial(self.submit_move, i))
            self.move_btns.append(btn)
            self.moves_layout.addWidget(btn, i//2, i%2)
        bottom.addWidget(moves_frame, 1)
        
        # Log
        log_frame = QFrame()
        log_frame.setObjectName("panel")
        apply_shadow(log_frame, blur=26, y_offset=8)
        log_layout = QVBoxLayout(log_frame)
        log_layout.addWidget(QLabel("<b>BATTLE CHRONICLE</b>"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background: #1A120B; color: #AEBBD0; border: none;")
        log_layout.addWidget(self.log_box)
        bottom.addWidget(log_frame, 1)
        
        shell_root.addLayout(bottom, 1)
        
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_battle)
        self.finished.connect(self.poll_timer.stop)
        self.poll_timer.start(1500)
        
        self.refresh_battle()

    def _create_combatant_ui(self, label: str):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel(label)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 800; color: #C19A6B;")
        
        img = QLabel()
        img.setFixedSize(200, 200)
        img.setStyleSheet("background: rgba(255,255,255,0.05); border-radius: 100px; border: 4px solid #4E3B24;")
        img.setAlignment(Qt.AlignCenter)
        
        name = QLabel("-")
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet("font-size: 22px; font-weight: 800;")
        
        hp_bar = QProgressBar()
        hp_bar.setFixedWidth(300)
        hp_bar.setFixedHeight(30)
        
        stats = QLabel("-")
        stats.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(title)
        layout.addWidget(img)
        layout.addWidget(name)
        layout.addWidget(hp_bar)
        layout.addWidget(stats)
        
        return {'layout': layout, 'img': img, 'name': name, 'hp': hp_bar, 'stats': stats}

    def refresh_battle(self) -> None:
        if not self.game_window.current_user or self._refresh_in_flight:
            return
        self._refresh_in_flight = True
        worker = Worker(api.get_battle, self.battle_id, self.game_window.current_user['id'])
        worker.signals.finished.connect(self._on_snapshot_fetched)
        worker.signals.error.connect(self._on_refresh_error)
        QThreadPool.globalInstance().start(worker)

    def _on_snapshot_fetched(self, snapshot: dict) -> None:
        self._refresh_in_flight = False
        try:
            if not self.isVisible(): return
            self.current_snapshot = snapshot
            
            if snapshot.get("status") == "completed":
                self.poll_timer.stop()
                self.render_snapshot()
                winner = "YOU WON!" if snapshot.get("you_won") else "YOU LOST!"
                QMessageBox.information(self, "Battle Over", f"The battle has concluded. {winner}")
                self.accept()
                return
                
            self.render_snapshot()
        except (RuntimeError, TypeError, KeyError):
            pass

    def _on_refresh_error(self, error: Exception) -> None:
        self._refresh_in_flight = False

    def render_snapshot(self) -> None:
        snap = self.current_snapshot
        if not snap or "your_side" not in snap: return
        your = snap['your_side']
        their = snap['their_side']
        
        self.title_label.setText(f"Dueling {their.get('username', 'Opponent')}")
        
        # Render Sides
        self._render_side(self.player_side, your)
        self._render_side(self.opponent_side, their)
        
        # Log
        self.log_box.setPlainText("\n".join(snap.get("log", [])))
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())
        
        # Moves
        options = snap.get("your_move_options", [])
        can_move = snap.get("can_submit_moves") and not snap.get("your_pending_move")
        
        for i, btn in enumerate(self.move_btns):
            if i < len(options):
                move = options[i]
                btn.setText(f"{move.get('name', 'Move')}\nDMG {move.get('damage', 0)}")
                btn.setEnabled(can_move and move.get('available', False))
                if not move.get('available'):
                    btn.setText(f"CD: {move.get('remaining_cooldown', 0)}")
            else:
                btn.setText("LOCKED")
                btn.setEnabled(False)

    def _render_side(self, ui, side):
        if not side: return
        creature = side.get("creature")
        combatant = side.get("combatant")
        username = side.get("username", "Unknown")
        if not creature: return
        
        ui['img'].setPixmap(load_pixmap(creature.get('image_path', ''), 180))
        ui['name'].setText(f"{username}'s {creature.get('display_name', '?')}\n(Lv {creature.get('level', 1)})")
        ui['name'].setStyleSheet(f"color: {creature.get('rarity_color', '#FFFFFF')}; font-size: 18px; font-weight: 800;")
        
        if combatant:
            ui['hp'].setMaximum(combatant.get('max_hp', 100))
            ui['hp'].setValue(combatant.get('current_hp', 0))
            ui['hp'].setFormat(f"{combatant.get('current_hp', 0)} / {combatant.get('max_hp', 100)} HP")
            stats = combatant.get('stats', {})
            ui['stats'].setText(f"ATK {stats.get('Attack', 0)} | DEF {stats.get('Defense', 0)} | SPD {stats.get('Speed', 0)}")
        else:
            stats = creature.get('stats', {})
            hp = stats.get('HP', 100)
            ui['hp'].setMaximum(hp)
            ui['hp'].setValue(hp)
            ui['hp'].setFormat(f"{hp} / {hp} HP")
            ui['stats'].setText(f"ATK {stats.get('Attack', 0)} | DEF {stats.get('Defense', 0)} | SPD {stats.get('Speed', 0)}")

    def submit_move(self, index: int) -> None:
        if not self.current_snapshot or "your_move_options" not in self.current_snapshot: return
        options = self.current_snapshot['your_move_options']
        if index >= len(options): return
        move = options[index]['name']
        worker = Worker(api.submit_move, self.battle_id, self.game_window.current_user['id'], move)
        worker.signals.finished.connect(self.refresh_battle)
        QThreadPool.globalInstance().start(worker)

    def forfeit_battle(self) -> None:
        worker = Worker(api.forfeit_battle, self.battle_id, self.game_window.current_user['id'])
        worker.signals.finished.connect(self.reject)
        QThreadPool.globalInstance().start(worker)


# Removed old FightingPage as it's replaced by FightingLobby and BattleDialog
        creature_id = self.accept_creature_combo.currentData()
        if creature_id is None:
            self._set_battle_status("You need a creature to accept the battle.", "#F47C7C")
            return
        
        # FIX: Move battle acceptance to worker thread
        worker = Worker(api.accept_battle, self.current_battle_id, self.game_window.current_user.get("id"), creature_id)
        worker.signals.finished.connect(self._on_battle_accepted)
        worker.signals.error.connect(lambda e: self._set_battle_status(str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def _on_battle_accepted(self, snapshot: dict) -> None:
        if isinstance(snapshot, dict):
            self.current_snapshot = snapshot
            self.render_snapshot()
            self._set_battle_status("Battle accepted. Both players can choose moves now.", "#63D471")

    def cancel_battle(self) -> None:
        if self.current_battle_id is None:
            return
        
        # FIX: Move battle cancellation to worker thread
        worker = Worker(api.cancel_battle, self.current_battle_id, self.game_window.current_user.get("id"))
        worker.signals.finished.connect(self._on_battle_cancelled)
        worker.signals.error.connect(lambda e: self._set_battle_status(str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def _on_battle_cancelled(self, _) -> None:
        self.current_battle_id = None
        self.refresh_page()
        self.clear_battle_display()
        self._set_battle_status("Pending challenge removed.", "#F2C14E")

    def submit_move(self, index: int) -> None:
        if self.current_snapshot is None or self.current_battle_id is None:
            return
        move_options = self.current_snapshot.get("your_move_options", [])
        if index >= len(move_options):
            return
        move = move_options[index]
        if not move.get("available"):
            return
        
        # FIX: Move move submission to worker thread
        worker = Worker(api.submit_move, self.current_battle_id, self.game_window.current_user.get("id"), move.get("name"))
        worker.signals.finished.connect(self._on_move_submitted)
        worker.signals.error.connect(lambda e: self._set_battle_status(str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def _on_move_submitted(self, snapshot: dict) -> None:
        if not isinstance(snapshot, dict):
            return
        self.current_snapshot = snapshot
        self.render_snapshot()
        self._handle_post_battle_updates()
        if snapshot.get("status") == "active":
            self._set_battle_status("Move submitted.", "#63D471")
        else:
            self._set_battle_status("Battle resolved.", "#63D471")

    def forfeit_battle(self) -> None:
        if self.current_battle_id is None:
            return
        
        # FIX: Move battle forfeit to worker thread
        worker = Worker(api.forfeit_battle, self.current_battle_id, self.game_window.current_user.get("id"))
        worker.signals.finished.connect(self._on_battle_forfeited)
        worker.signals.error.connect(lambda e: self._set_battle_status(str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def _on_battle_forfeited(self, snapshot: dict) -> None:
        if isinstance(snapshot, dict):
            self.current_snapshot = snapshot
            self.render_snapshot()
            self._handle_post_battle_updates()
            self._set_battle_status("You forfeited the battle.", "#F2C14E")

    def _handle_post_battle_updates(self) -> None:
        if self.current_snapshot and self.current_snapshot["status"] == "completed":
            self.game_window.refresh_session()
            self.game_window.pages["inventory"].refresh_page()
            self.game_window.pages["profile"].refresh_page()
            self.game_window.pages["dashboard"].refresh_page()
            self.refresh_page()


    def load_battle_snapshot(self) -> None:
        if self.current_battle_id is None:
            self.clear_battle_display()
            return
            
        # FIX: Move DB/Network call to worker thread to prevent UI freeze
        # Fetch both the battle and the user's inventory for the selector
        def get_battle_and_inventory(battle_id: int, user_id: int, username: str):
            snapshot = api.get_battle(battle_id, user_id)
            user_inventory = inventory.get_inventory(username, sort_by="rarity")
            return snapshot, user_inventory

        worker = Worker(
            get_battle_and_inventory,
            self.current_battle_id,
            self.game_window.current_user.get("id"),
            self.game_window.current_user.get("username")
        )
        worker.signals.finished.connect(self._on_battle_data_fetched)
        worker.signals.error.connect(lambda e: self._set_battle_status(str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def _on_battle_data_fetched(self, data: tuple) -> None:
        if not isinstance(data, tuple) or len(data) != 2:
            self.current_snapshot = None
            self.clear_battle_display()
            return
            
        snapshot, self.user_inventory = data
        previous_round = self.current_snapshot.get("round_number", 0) if self.current_snapshot else 0
        previous_status = self.current_snapshot.get("status") if self.current_snapshot else None
        
        self.current_snapshot = snapshot
        self.render_snapshot()
        
        if snapshot.get("round_number", 0) > previous_round or snapshot.get("status") != previous_status:
            self._handle_post_battle_updates()
            self._set_battle_status("Battle state updated.", "#63D471")


class ProfilePage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)

        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(34, 34, 34, 34)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        apply_shadow(hero, blur=34, y_offset=12)
        hero_layout = QVBoxLayout(hero)
        self.username_label = QLabel("Profile")
        self.username_label.setObjectName("displayTitle")
        self.privacy_label = QLabel("Your public identity is your username. Private email and real name stay out of the player app.")
        self.privacy_label.setObjectName("subtitle")
        hero_layout.addWidget(self.username_label)
        hero_layout.addWidget(self.privacy_label)
        layout.addWidget(hero)

        summary = QFrame()
        summary.setObjectName("panel")
        apply_shadow(summary, blur=30, y_offset=10)
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(26, 24, 26, 24)
        summary_title = QLabel("Collection Summary")
        summary_title.setObjectName("sectionTitle")
        summary_layout.addWidget(summary_title)
        self.tokens_label = QLabel("Tokens: 0")
        self.collection_label = QLabel("Creatures: 0")
        self.value_label = QLabel("Collection Value: 0")
        self.rarity_label = QLabel("Highest Rarity: None")
        self.trade_label = QLabel("Trade Activity: 0")
        summary_layout.addWidget(self.tokens_label)
        summary_layout.addWidget(self.collection_label)
        summary_layout.addWidget(self.value_label)
        summary_layout.addWidget(self.rarity_label)
        summary_layout.addWidget(self.trade_label)
        layout.addWidget(summary)

        top_panel = QFrame()
        top_panel.setObjectName("panel")
        apply_shadow(top_panel, blur=30, y_offset=10)
        top_layout = QVBoxLayout(top_panel)
        top_title = QLabel("Top Creatures")
        top_title.setObjectName("sectionTitle")
        self.top_list = QListWidget()
        top_layout.addWidget(top_title)
        top_layout.addWidget(self.top_list)
        layout.addWidget(top_panel)
        layout.addStretch(1)

    def refresh_page(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
            
        # FIX: Move inventory and trade fetching to worker threads
        self._fetch_profile_data(user)

    def _fetch_profile_data(self, user: dict) -> None:
        # We'll use a single worker that returns a tuple of results for efficiency
        def get_profile_data(username: str, user_id: int):
            summary = inventory.get_inventory_summary(username)
            trades = api.list_user_trades(user_id)
            top_creatures = inventory.get_inventory(username, sort_by="value")[:5]
            return summary, trades, top_creatures

        worker = Worker(get_profile_data, user.get("username"), user.get("id"))
        worker.signals.finished.connect(self._on_profile_data_fetched)
        QThreadPool.globalInstance().start(worker)

    def _on_profile_data_fetched(self, data: tuple) -> None:
        try:
            user = self.game_window.current_user
            if user is None or not isinstance(data, tuple) or len(data) != 3 or not self.isVisible():
                return
                
            summary, trades, top_creatures = data
            open_trades = sum(1 for trade_row in trades if trade_row.get("status") in {"pending", "open"})

            self.username_label.setText(user.get("username", "Profile"))
            self.tokens_label.setText(f"Tokens: {user.get('tokens', 0)}")
            self.collection_label.setText(f"Creatures: {summary.get('count', 0)}")
            self.value_label.setText(f"Collection Value: {summary.get('total_value', 0)}")
            self.rarity_label.setText(f"Highest Rarity: {summary.get('highest_rarity', 'None')}")
            self.trade_label.setText(f"Trade Activity: {open_trades}")

            self.top_list.clear()
            for creature in top_creatures:
                self.top_list.addItem(
                    f"{creature.get('display_name')} | {creature.get('rarity')} | Lv {creature.get('level')} | Value {creature.get('value')}"
                )
        except RuntimeError:
            pass


class LeaderboardPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(34, 34, 34, 34)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        apply_shadow(hero, blur=34, y_offset=12)
        hero_layout = QVBoxLayout(hero)
        title = QLabel("Global Leaderboards")
        title.setObjectName("displayTitle")
        subtitle = QLabel("Track the wealthiest players and the largest collections across the realm.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)
        
        body = QHBoxLayout()
        body.setSpacing(18)
        
        # Tokens Leaderboard
        tokens_panel = QFrame()
        tokens_panel.setObjectName("panel")
        apply_shadow(tokens_panel, blur=30, y_offset=10)
        tokens_layout = QVBoxLayout(tokens_panel)
        label = QLabel("TOP TOKENS")
        label.setObjectName("sectionTitle")
        tokens_layout.addWidget(label)
        self.tokens_list = QListWidget()
        tokens_layout.addWidget(self.tokens_list)
        body.addWidget(tokens_panel)
        
        # Creatures Leaderboard
        creatures_panel = QFrame()
        creatures_panel.setObjectName("panel")
        apply_shadow(creatures_panel, blur=30, y_offset=10)
        creatures_layout = QVBoxLayout(creatures_panel)
        label = QLabel("TOP CREATURE COUNTS")
        label.setObjectName("sectionTitle")
        creatures_layout.addWidget(label)
        self.creatures_list = QListWidget()
        creatures_layout.addWidget(self.creatures_list)
        body.addWidget(creatures_panel)
        
        layout.addLayout(body)
        
        refresh_btn = QPushButton("Refresh Leaderboards")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self.refresh_page)
        layout.addWidget(refresh_btn)

    def refresh_page(self) -> None:
        worker = Worker(api.request_json, "get", "leaderboard")
        worker.signals.finished.connect(self._on_leaderboard_fetched)
        QThreadPool.globalInstance().start(worker)

    def _on_leaderboard_fetched(self, data: dict) -> None:
        if not isinstance(data, dict): return
        
        self.tokens_list.clear()
        for i, user in enumerate(data.get("top_tokens", []), 1):
            self.tokens_list.addItem(f"#{i} {user['username']} - {user['tokens']} tokens")
            
        self.creatures_list.clear()
        for i, user in enumerate(data.get("top_creatures", []), 1):
            self.creatures_list.addItem(f"#{i} {user['username']} - {user['creature_count']} creatures")


class SearchPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(34, 34, 34, 34)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        apply_shadow(hero, blur=34, y_offset=12)
        hero_layout = QVBoxLayout(hero)
        title = QLabel("Player Search")
        title.setObjectName("displayTitle")
        subtitle = QLabel("Look up another player, inspect their collection size, and see what creatures they own.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)
        
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter username or email...")
        search_btn = QPushButton("Search")
        search_btn.setObjectName("secondaryButton")
        search_btn.clicked.connect(self.search_player)
        search_row.addWidget(self.search_input)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)
        
        self.results_panel = QFrame()
        self.results_panel.setObjectName("panel")
        apply_shadow(self.results_panel, blur=30, y_offset=10)
        self.results_layout = QVBoxLayout(self.results_panel)
        self.results_panel.setVisible(False)
        
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("font-size: 16px; font-weight: 900; color: #FFF2D9;")
        self.creatures_list = QListWidget()
        
        self.results_layout.addWidget(self.stats_label)
        label = QLabel("CREATURES")
        label.setObjectName("sectionTitle")
        self.results_layout.addWidget(label)
        self.results_layout.addWidget(self.creatures_list)
        
        layout.addWidget(self.results_panel)
        layout.addStretch()

    def search_player(self) -> None:
        query = self.search_input.text().strip()
        if not query: return
        
        worker = Worker(api.request_json, "get", f"player_stats/{query}")
        worker.signals.finished.connect(self._on_search_result)
        QThreadPool.globalInstance().start(worker)

    def _on_search_result(self, data: dict) -> None:
        if not isinstance(data, dict):
            show_error(self, "Player search failed. Please try again.")
            self.results_panel.setVisible(False)
            return

        if data.get("status") == "error":
            show_error(self, data.get("message", "Player not found."))
            self.results_panel.setVisible(False)
            return
            
        self.results_panel.setVisible(True)
        self.stats_label.setText(f"Player: {data['username']} | Tokens: {data['tokens']} | Collection: {data['creature_count']}")
        
        self.creatures_list.clear()
        for c in data.get("creatures", []):
            self.creatures_list.addItem(f"{c['display_name']} ({c['rarity']}) - Lv {c['level']}")


class ChatPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self._refresh_in_flight = False
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(34, 34, 34, 34)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        apply_shadow(hero, blur=34, y_offset=12)
        hero_layout = QVBoxLayout(hero)
        title = QLabel("Global Chat")
        title.setObjectName("displayTitle")
        subtitle = QLabel("Talk with other players, trade rumors, and celebrate your latest pulls.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)
        
        chat_panel = QFrame()
        chat_panel.setObjectName("parchmentPanel")
        apply_shadow(chat_panel, blur=30, y_offset=10)
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(24, 24, 24, 24)
        chat_title = QLabel("Town Feed")
        chat_title.setObjectName("sectionTitle")
        chat_layout.addWidget(chat_title)

        self.chat_display = QListWidget()
        chat_layout.addWidget(self.chat_display)
        layout.addWidget(chat_panel)
        
        input_row = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.returnPressed.connect(self.send_message)
        send_btn = QPushButton("Send")
        send_btn.setObjectName("secondaryButton")
        send_btn.clicked.connect(self.send_message)
        input_row.addWidget(self.message_input)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)
        
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(5000)
        self.refresh_timer.timeout.connect(self.refresh_page)

    def showEvent(self, event) -> None:
        self.refresh_page()
        self.refresh_timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self.refresh_timer.stop()
        super().hideEvent(event)

    def refresh_page(self) -> None:
        if self._refresh_in_flight or self.game_window.current_user is None:
            return
        self._refresh_in_flight = True
        worker = Worker(api.request_json, "get", "chat")
        worker.signals.finished.connect(self._on_chat_fetched)
        worker.signals.error.connect(self._on_chat_error)
        QThreadPool.globalInstance().start(worker)

    def _on_chat_fetched(self, data: list) -> None:
        self._refresh_in_flight = False
        if not isinstance(data, list) or not self.isVisible():
            return

        self.chat_display.clear()
        for msg in reversed(data): # Show newest at bottom
            item = f"[{msg['created_at'][11:16]}] {msg['username']}: {msg['message']}"
            self.chat_display.addItem(item)
        self.chat_display.scrollToBottom()

    def _on_chat_error(self, error: Exception) -> None:
        self._refresh_in_flight = False

    def send_message(self) -> None:
        text = self.message_input.text().strip()
        if not text: return
        
        self.message_input.clear()
        worker = Worker(api.request_json, "post", "chat", json={
            "user_id": self.game_window.current_user.get("id"),
            "message": text
        })
        worker.signals.finished.connect(lambda _: self.refresh_page())
        QThreadPool.globalInstance().start(worker)


class GamesPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 34, 34, 34)
        layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        apply_shadow(hero, blur=34, y_offset=12)
        hero_layout = QVBoxLayout(hero)
        title = QLabel("Gaming District")
        title.setObjectName("displayTitle")
        subtitle = QLabel("Play unique minigames to earn extra tokens for your summons.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        body = QHBoxLayout()
        body.setSpacing(18)

        # RelmFishing
        fishing_panel = QFrame()
        fishing_panel.setObjectName("panel")
        apply_shadow(fishing_panel, blur=30, y_offset=10)
        fishing_layout = QVBoxLayout(fishing_panel)
        fishing_title = QLabel("Relm Fishing")
        fishing_title.setObjectName("sectionTitle")
        fishing_desc = QLabel("Cast your line and reel in the rare catches! Keep the hook in the fish zone.")
        fishing_desc.setWordWrap(True)
        fishing_desc.setStyleSheet("color: #A67B5B;")
        
        self.fishing_game_btn = QPushButton("GO FISHING")
        self.fishing_game_btn.setObjectName("secondaryButton")
        self.fishing_game_btn.clicked.connect(self.start_fishing_game)
        
        fishing_layout.addWidget(fishing_title)
        fishing_layout.addWidget(fishing_desc)
        fishing_layout.addStretch()
        fishing_layout.addWidget(self.fishing_game_btn, 0, Qt.AlignCenter)
        fishing_layout.addStretch()
        body.addWidget(fishing_panel, 1)

        # RelmSlayer (Fruit Ninja style)
        slayer_panel = QFrame()
        slayer_panel.setObjectName("panel")
        apply_shadow(slayer_panel, blur=30, y_offset=10)
        slayer_layout = QVBoxLayout(slayer_panel)
        slayer_title = QLabel("Relm Slayer")
        slayer_title.setObjectName("sectionTitle")
        slayer_desc = QLabel("Shadow creatures are invading! Slash them before they disappear.")
        slayer_desc.setWordWrap(True)
        slayer_desc.setStyleSheet("color: #A67B5B;")
        
        self.slayer_game_btn = QPushButton("START SLAYING")
        self.slayer_game_btn.setObjectName("dangerButton")
        self.slayer_game_btn.clicked.connect(self.start_slayer_game)
        
        slayer_layout.addWidget(slayer_title)
        slayer_layout.addWidget(slayer_desc)
        slayer_layout.addStretch()
        slayer_layout.addWidget(self.slayer_game_btn, 0, Qt.AlignCenter)
        slayer_layout.addStretch()
        body.addWidget(slayer_panel, 1)

        # Rune Quiz Rush
        quiz_panel = QFrame()
        quiz_panel.setObjectName("panel")
        apply_shadow(quiz_panel, blur=30, y_offset=10)
        quiz_layout = QVBoxLayout(quiz_panel)
        quiz_title = QLabel("Rune Quiz Rush")
        quiz_title.setObjectName("sectionTitle")
        quiz_desc = QLabel("Answer server-generated quiz rounds for verified rewards. Blooket-style, but RelmBag themed.")
        quiz_desc.setWordWrap(True)
        quiz_desc.setStyleSheet("color: #A67B5B;")

        self.quiz_game_btn = QPushButton("START QUIZ")
        self.quiz_game_btn.setObjectName("successButton")
        self.quiz_game_btn.clicked.connect(self.start_quiz_game)

        quiz_layout.addWidget(quiz_title)
        quiz_layout.addWidget(quiz_desc)
        quiz_layout.addStretch()
        quiz_layout.addWidget(self.quiz_game_btn, 0, Qt.AlignCenter)
        quiz_layout.addStretch()
        body.addWidget(quiz_panel, 1)
        layout.addLayout(body)

        body2 = QHBoxLayout()
        body2.setSpacing(18)

        # Memory Match
        memory_panel = QFrame()
        memory_panel.setObjectName("panel")
        apply_shadow(memory_panel, blur=30, y_offset=10)
        memory_layout = QVBoxLayout(memory_panel)
        memory_title = QLabel("Memory Match")
        memory_title.setObjectName("sectionTitle")
        memory_desc = QLabel("Match the ancient runes to clear the board. Sharpens the mind!")
        memory_desc.setWordWrap(True)
        memory_desc.setStyleSheet("color: #A67B5B;")
        
        self.memory_game_btn = QPushButton("MATCH RUNES")
        self.memory_game_btn.setObjectName("secondaryButton")
        self.memory_game_btn.clicked.connect(self.start_memory_game)
        
        memory_layout.addWidget(memory_title)
        memory_layout.addWidget(memory_desc)
        memory_layout.addStretch()
        memory_layout.addWidget(self.memory_game_btn, 0, Qt.AlignCenter)
        memory_layout.addStretch()
        body2.addWidget(memory_panel, 1)

        # Relm Runner
        runner_panel = QFrame()
        runner_panel.setObjectName("panel")
        apply_shadow(runner_panel, blur=30, y_offset=10)
        runner_layout = QVBoxLayout(runner_panel)
        runner_title = QLabel("Relm Runner")
        runner_title.setObjectName("sectionTitle")
        runner_desc = QLabel("Sprint through the void! Jump over obstacles to reach the end.")
        runner_desc.setWordWrap(True)
        runner_desc.setStyleSheet("color: #A67B5B;")
        
        self.runner_game_btn = QPushButton("GO RUNNING")
        self.runner_game_btn.setObjectName("secondaryButton")
        self.runner_game_btn.clicked.connect(self.start_runner_game)
        
        runner_layout.addWidget(runner_title)
        runner_layout.addWidget(runner_desc)
        runner_layout.addStretch()
        runner_layout.addWidget(self.runner_game_btn, 0, Qt.AlignCenter)
        runner_layout.addStretch()
        body2.addWidget(runner_panel, 1)

        # Token Catcher
        catcher_panel = QFrame()
        catcher_panel.setObjectName("panel")
        apply_shadow(catcher_panel, blur=30, y_offset=10)
        catcher_layout = QVBoxLayout(catcher_panel)
        catcher_title = QLabel("Token Catcher")
        catcher_title.setObjectName("sectionTitle")
        catcher_desc = QLabel("Catch falling tokens from the celestial rift. Don't let them drop!")
        catcher_desc.setWordWrap(True)
        catcher_desc.setStyleSheet("color: #A67B5B;")
        
        self.catcher_game_btn = QPushButton("CATCH TOKENS")
        self.catcher_game_btn.setObjectName("secondaryButton")
        self.catcher_game_btn.clicked.connect(self.start_catcher_game)
        
        catcher_layout.addWidget(catcher_title)
        catcher_layout.addWidget(catcher_desc)
        catcher_layout.addStretch()
        catcher_layout.addWidget(self.catcher_game_btn, 0, Qt.AlignCenter)
        catcher_layout.addStretch()
        body2.addWidget(catcher_panel, 1)

        layout.addLayout(body2)
        layout.addStretch(1)
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        self._game_in_flight = False
        self.game_buttons = [
            self.fishing_game_btn,
            self.slayer_game_btn,
            self.quiz_game_btn,
            self.memory_game_btn,
            self.runner_game_btn,
            self.catcher_game_btn,
        ]

    def start_fishing_game(self) -> None:
        self.start_server_game("RelmFishing", FishingGameDialog)

    def start_slayer_game(self) -> None:
        self.start_server_game("RelmSlayer", SlayerGameDialog)

    def start_quiz_game(self) -> None:
        self.start_server_game("RuneQuiz", QuizRushDialog)

    def start_memory_game(self) -> None:
        self.start_server_game("MemoryMatch", MemoryGameDialog)

    def start_runner_game(self) -> None:
        self.start_server_game("RelmRunner", RunnerGameDialog)

    def start_catcher_game(self) -> None:
        self.start_server_game("TokenCatcher", CatcherGameDialog)

    def _set_game_buttons_enabled(self, enabled: bool) -> None:
        for button in self.game_buttons:
            button.setEnabled(enabled)

    def start_server_game(self, game_name: str, dialog_cls) -> None:
        user = self.game_window.current_user
        if self._game_in_flight:
            set_status(self.status_label, "Finish the current minigame first.", "#F2C14E")
            return
        if not user:
            show_error(self, "Please log in before playing minigames.")
            return

        self._game_in_flight = True
        self._set_game_buttons_enabled(False)
        set_status(self.status_label, f"Starting verified {game_name} session...", "#F2C14E")
        worker = Worker(api.start_minigame, user["id"], user.get("session_token"), game_name)
        worker.signals.finished.connect(
            lambda payload, name=game_name, cls=dialog_cls: self._on_game_session_started(name, cls, payload)
        )
        worker.signals.error.connect(lambda e: self._on_game_error(str(e)))
        QThreadPool.globalInstance().start(worker)

    def _on_game_session_started(self, game_name: str, dialog_cls, payload: dict) -> None:
        if not isinstance(payload, dict) or payload.get("status") != "success":
            message = payload.get("message", "Could not start minigame.") if isinstance(payload, dict) else "Could not start minigame."
            self._on_game_error(message)
            return

        if dialog_cls is QuizRushDialog:
            dialog = dialog_cls(self, payload.get("challenge", {}))
        else:
            dialog = dialog_cls(self)

        if dialog.exec_() != QDialog.Accepted:
            self._game_in_flight = False
            self._set_game_buttons_enabled(True)
            set_status(self.status_label, "Minigame cancelled. No reward was claimed.", "#AEBBD0")
            return

        result = dialog.result_payload()
        set_status(self.status_label, "Verifying reward with the server...", "#F2C14E")
        user = self.game_window.current_user
        worker = Worker(
            api.finish_minigame,
            user["id"],
            user.get("session_token"),
            payload["session_id"],
            int(result.get("score", 0) or 0),
            int(result.get("elapsed_ms", 0) or 0),
            result.get("answers"),
        )
        worker.signals.finished.connect(lambda reward_payload, name=game_name: self._on_game_finished(name, reward_payload))
        worker.signals.error.connect(lambda e: self._on_game_error(str(e)))
        QThreadPool.globalInstance().start(worker)

    def _on_game_finished(self, game_name: str, payload: dict) -> None:
        self._game_in_flight = False
        self._set_game_buttons_enabled(True)
        if not isinstance(payload, dict) or payload.get("status") != "success":
            message = payload.get("message", "Reward verification failed.") if isinstance(payload, dict) else "Reward verification failed."
            set_status(self.status_label, message, "#F47C7C")
            return

        reward = int(payload.get("reward", 0) or 0)
        score = int(payload.get("score", 0) or 0)
        current_tokens = payload.get("current_tokens")
        if current_tokens is not None:
            self.game_window.update_token_balance(int(current_tokens))
        set_status(self.status_label, f"{game_name} verified! Score {score}. Earned {reward} tokens.", "#63D471")

    def _on_game_error(self, message: str) -> None:
        self._game_in_flight = False
        self._set_game_buttons_enabled(True)
        set_status(self.status_label, message or "Minigame failed.", "#F47C7C")


class QuizRushDialog(QDialog):
    def __init__(self, parent=None, challenge: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rune Quiz Rush")
        self.resize(640, 520)
        self.setStyleSheet(parent.window().styleSheet() if parent else "")
        self.started_at = time.monotonic()
        self.questions = list((challenge or {}).get("questions", []))
        self.answers: list[int] = []
        self.index = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(16)

        title = QLabel("RUNE QUIZ RUSH")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.progress_label = QLabel()
        self.progress_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.progress_label)

        self.prompt_label = QLabel()
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setAlignment(Qt.AlignCenter)
        self.prompt_label.setStyleSheet("font-size: 20px; font-weight: 900; color: #F5EBD5;")
        layout.addWidget(self.prompt_label)

        self.option_buttons: list[QPushButton] = []
        for idx in range(4):
            button = QPushButton()
            button.setObjectName("secondaryButton")
            button.clicked.connect(partial(self.choose_answer, idx))
            layout.addWidget(button)
            self.option_buttons.append(button)

        hint = QLabel("Questions are issued by the server, and rewards are verified after the round.")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #AEBBD0;")
        layout.addWidget(hint)

        if not self.questions:
            QTimer.singleShot(0, self.reject)
        else:
            self.render_question()

    def render_question(self) -> None:
        question = self.questions[self.index]
        self.progress_label.setText(f"Question {self.index + 1} / {len(self.questions)}")
        self.prompt_label.setText(question.get("prompt", "Choose the best answer."))
        options = list(question.get("options", []))[:4]
        for idx, button in enumerate(self.option_buttons):
            if idx < len(options):
                button.setText(options[idx])
                button.setEnabled(True)
                button.show()
            else:
                button.hide()

    def choose_answer(self, option_index: int) -> None:
        self.answers.append(option_index)
        self.index += 1
        if self.index >= len(self.questions):
            self.accept()
            return
        self.render_question()

    def result_payload(self) -> dict:
        return {
            "score": 0,
            "answers": self.answers,
            "elapsed_ms": int((time.monotonic() - self.started_at) * 1000),
        }


class FishingGameDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Relm Fishing")
        self.resize(300, 500)
        self.setStyleSheet(parent.window().styleSheet() if parent else "")
        self.started_at = time.monotonic()
        self.final_score = 0
        layout = QVBoxLayout(self)
        
        title = QLabel("RELM FISHING")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        instr = QLabel("HOLD SPACE to raise your hook. KEEP IT ON THE FISH!")
        instr.setWordWrap(True)
        instr.setAlignment(Qt.AlignCenter)
        layout.addWidget(instr)

        # Game Area
        self.game_frame = QFrame()
        self.game_frame.setFixedSize(200, 300)
        self.game_frame.setObjectName("panel")
        self.game_frame.setStyleSheet("background: #0D1B2A; border: 2px solid #1B263B;")
        layout.addWidget(self.game_frame, 0, Qt.AlignCenter)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Objects
        self.fish_y = 150
        self.hook_y = 150
        self.fish_velocity = 2
        self.hook_velocity = 0
        self.progress = 0
        
        self.fish_marker = QFrame(self.game_frame)
        self.fish_marker.setFixedSize(40, 40)
        self.fish_marker.setStyleSheet("background: #E91E63; border-radius: 20px;")
        
        self.hook_marker = QFrame(self.game_frame)
        self.hook_marker.setFixedSize(60, 60)
        self.hook_marker.setStyleSheet("background: rgba(0, 255, 255, 0.3); border: 2px solid #00FFFF; border-radius: 10px;")
        
        self.space_pressed = False
        
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update_game)
        self.timer.start()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space:
            self.space_pressed = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key_Space:
            self.space_pressed = False
        super().keyReleaseEvent(event)

    def update_game(self) -> None:
        # Fish movement
        import random
        if random.random() < 0.05:
            self.fish_velocity = random.uniform(-4, 4)
        
        self.fish_y += self.fish_velocity
        self.fish_y = max(0, min(260, self.fish_y))
        
        # Hook movement (gravity vs space)
        if self.space_pressed:
            self.hook_velocity -= 0.6
        else:
            self.hook_velocity += 0.4
            
        self.hook_velocity = max(-6, min(6, self.hook_velocity))
        self.hook_y += self.hook_velocity
        self.hook_y = max(0, min(240, self.hook_y))
        
        # Update visuals
        self.fish_marker.move(80, int(self.fish_y))
        self.hook_marker.move(70, int(self.hook_y))
        
        # Check collision
        if abs((self.hook_y + 30) - (self.fish_y + 20)) < 40:
            self.progress += 0.5
        else:
            self.progress -= 0.3
            
        self.progress = max(0, min(100, self.progress))
        self.progress_bar.setValue(int(self.progress))
        
        if self.progress >= 100:
            self.timer.stop()
            self.final_score = 100
            self.accept()

    def result_payload(self) -> dict:
        return {
            "score": self.final_score,
            "elapsed_ms": int((time.monotonic() - self.started_at) * 1000),
        }


class SlayerGameDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Relm Slayer")
        self.resize(600, 600)
        self.setStyleSheet(parent.window().styleSheet() if parent else "")
        self.started_at = time.monotonic()
        layout = QVBoxLayout(self)
        
        title = QLabel("RELM SLAYER")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.score = 0
        self.score_label = QLabel("Shadows Slain: 0 / 20")
        self.score_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.score_label)

        self.game_area = QFrame()
        self.game_area.setFixedSize(500, 400)
        self.game_area.setObjectName("panel")
        self.game_area.setStyleSheet("background: #120D10; border: 2px solid #E14B4B;")
        layout.addWidget(self.game_area, 0, Qt.AlignCenter)
        
        self.target = QPushButton("SHADOW", self.game_area)
        self.target.setFixedSize(80, 80)
        self.target.setStyleSheet("background: #E14B4B; color: white; border-radius: 40px; font-weight: 900;")
        self.target.clicked.connect(self.hit_target)
        self.target.hide()
        
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.spawn_target)
        self.timer.start()
        
        self.spawn_target()

    def spawn_target(self) -> None:
        import random
        x = random.randint(0, 420)
        y = random.randint(0, 320)
        self.target.move(x, y)
        self.target.show()
        
    def hit_target(self) -> None:
        self.target.hide()
        self.score += 1
        self.score_label.setText(f"Shadows Slain: {self.score} / 20")
        
        if self.score >= 20:
            self.timer.stop()
            self.accept()

    def result_payload(self) -> dict:
        return {
            "score": self.score,
            "elapsed_ms": int((time.monotonic() - self.started_at) * 1000),
        }


class MemoryGameDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Memory Match")
        self.resize(500, 600)
        self.setStyleSheet(parent.window().styleSheet() if parent else "")
        self.started_at = time.monotonic()
        layout = QVBoxLayout(self)
        
        title = QLabel("MEMORY MATCH")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        layout.addLayout(self.grid)
        
        # 4x4 grid of 8 pairs
        symbols = ["ᚠ", "ᚢ", "ᚦ", "ᚨ", "ᚱ", "ᚲ", "ᚷ", "ᚹ"] * 2
        import random
        random.shuffle(symbols)
        
        self.buttons = []
        self.first_selection = None
        self.second_selection = None
        self.matches = 0
        
        for i in range(16):
            btn = QPushButton("?")
            btn.setFixedSize(80, 80)
            btn.setObjectName("secondaryButton")
            btn.setStyleSheet("font-size: 32px; font-weight: 800;")
            btn.symbol = symbols[i]
            btn.index = i
            btn.clicked.connect(partial(self.handle_click, btn))
            self.grid.addWidget(btn, i // 4, i % 4)
            self.buttons.append(btn)
            
    def handle_click(self, btn: QPushButton) -> None:
        if btn == self.first_selection or btn.text() != "?":
            return
            
        btn.setText(btn.symbol)
        
        if self.first_selection is None:
            self.first_selection = btn
        else:
            self.second_selection = btn
            # Disable all buttons temporarily
            for b in self.buttons: b.setEnabled(False)
            QTimer.singleShot(500, self.check_match)
            
    def check_match(self) -> None:
        if self.first_selection.symbol == self.second_selection.symbol:
            self.matches += 1
            if self.matches == 8:
                self.accept()
        else:
            self.first_selection.setText("?")
            self.second_selection.setText("?")
            
        self.first_selection = None
        self.second_selection = None
        for b in self.buttons: b.setEnabled(True)

    def result_payload(self) -> dict:
        return {
            "score": self.matches,
            "elapsed_ms": int((time.monotonic() - self.started_at) * 1000),
        }


class RunnerGameDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Relm Runner")
        self.resize(600, 300)
        self.setStyleSheet(parent.window().styleSheet() if parent else "")
        self.started_at = time.monotonic()
        layout = QVBoxLayout(self)
        
        title = QLabel("RELM RUNNER")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.game_area = QFrame()
        self.game_area.setFixedSize(500, 150)
        self.game_area.setObjectName("panel")
        self.game_area.setStyleSheet("background: #0D0912; border: 2px solid #7B57D1;")
        layout.addWidget(self.game_area, 0, Qt.AlignCenter)
        
        self.player = QFrame(self.game_area)
        self.player.setFixedSize(30, 30)
        self.player.setStyleSheet("background: #6EEB83; border-radius: 15px;")
        self.player_y = 120
        self.player_velocity = 0
        self.is_jumping = False
        
        self.obstacles = []
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.update_game)
        self.timer.start()
        
        self.spawn_timer = QTimer(self)
        self.spawn_timer.setInterval(1500)
        self.spawn_timer.timeout.connect(self.spawn_obstacle)
        self.spawn_timer.start()
        
        self.distance = 0
        self.dist_label = QLabel("Distance: 0 / 1000")
        layout.addWidget(self.dist_label)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space and not self.is_jumping:
            self.player_velocity = -12
            self.is_jumping = True
        super().keyPressEvent(event)

    def spawn_obstacle(self) -> None:
        obs = QFrame(self.game_area)
        obs.setFixedSize(20, 30)
        obs.setStyleSheet("background: #E14B4B;")
        obs.move(500, 120)
        self.obstacles.append(obs)

    def update_game(self) -> None:
        self.distance += 2
        self.dist_label.setText(f"Distance: {self.distance} / 1000")
        
        # Player gravity
        self.player_velocity += 0.8
        self.player_y += self.player_velocity
        if self.player_y >= 120:
            self.player_y = 120
            self.is_jumping = False
            
        self.player.move(50, int(self.player_y))
        
        # Obstacles
        for obs in self.obstacles[:]:
            obs.move(obs.x() - 5, obs.y())
            if obs.x() < -20:
                self.obstacles.remove(obs)
                obs.deleteLater()
            
            # Collision
            if abs(obs.x() - 50) < 25 and abs(obs.y() - self.player_y) < 25:
                self.distance = 0 # Reset distance on hit
                
        if self.distance >= 1000:
            self.timer.stop()
            self.spawn_timer.stop()
            self.accept()

    def result_payload(self) -> dict:
        return {
            "score": self.distance,
            "elapsed_ms": int((time.monotonic() - self.started_at) * 1000),
        }


class CatcherGameDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Token Catcher")
        self.resize(400, 500)
        self.setStyleSheet(parent.window().styleSheet() if parent else "")
        self.started_at = time.monotonic()
        layout = QVBoxLayout(self)
        
        title = QLabel("TOKEN CATCHER")
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.score = 0
        self.score_label = QLabel("Tokens Caught: 0 / 20")
        layout.addWidget(self.score_label)

        self.game_area = QFrame()
        self.game_area.setFixedSize(350, 400)
        self.game_area.setObjectName("panel")
        self.game_area.setStyleSheet("background: #0D0912; border: 2px solid #F2C14E;")
        layout.addWidget(self.game_area, 0, Qt.AlignCenter)
        
        self.basket = QFrame(self.game_area)
        self.basket.setFixedSize(60, 20)
        self.basket.setStyleSheet("background: #F2C14E; border-radius: 5px;")
        self.basket_x = 145
        self.basket.move(self.basket_x, 370)
        
        self.tokens = []
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.update_game)
        self.timer.start()
        
        self.spawn_timer = QTimer(self)
        self.spawn_timer.setInterval(800)
        self.spawn_timer.timeout.connect(self.spawn_token)
        self.spawn_timer.start()
        
        self.setMouseTracking(True)
        self.game_area.setMouseTracking(True)

    def mouseMoveEvent(self, event) -> None:
        pos = self.game_area.mapFromGlobal(QCursor.pos())
        self.basket_x = max(0, min(290, pos.x() - 30))
        self.basket.move(self.basket_x, 370)

    def spawn_token(self) -> None:
        import random
        t = QLabel("●", self.game_area)
        t.setStyleSheet("color: #F2C14E; font-size: 20px;")
        t.move(random.randint(0, 330), 0)
        self.tokens.append(t)

    def update_game(self) -> None:
        for t in self.tokens[:]:
            t.move(t.x(), t.y() + 4)
            if t.y() > 400:
                self.tokens.remove(t)
                t.deleteLater()
            elif t.y() > 360 and abs(t.x() - self.basket_x) < 40:
                self.tokens.remove(t)
                t.deleteLater()
                self.score += 1
                self.score_label.setText(f"Tokens Caught: {self.score} / 20")
                
        if self.score >= 20:
            self.timer.stop()
            self.spawn_timer.stop()
            self.accept()

    def result_payload(self) -> dict:
        return {
            "score": self.score,
            "elapsed_ms": int((time.monotonic() - self.started_at) * 1000),
        }


class GameWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        from config import APP_VERSION
        self.current_user: dict | None = None
        self.seen_trade_notifications: set[int] = set()
        self.seen_battle_notifications: set[int] = set()
        self.setWindowTitle(f"{APP_TITLE} v{APP_VERSION}")
        self.setWindowIcon(QIcon(str(APP_ICON_PNG)))
        self.resize(1520, 940)

        # FIX: Replace unreliable presence_timer with HeartbeatWorker
        self.heartbeat_worker = None
        self.last_battle_statuses: dict[int, str] = {}
        self.last_trade_statuses: dict[int, str] = {}
        self.last_announcement_time = 0
        self._session_refresh_in_flight = False
        self._notification_fetch_in_flight = False
        self._pending_request_total = 0

        self.notification_timer = QTimer(self)
        self.notification_timer.setInterval(20000)
        self.notification_timer.timeout.connect(self.check_notifications)

        self.root_stack = QStackedWidget()
        self.setCentralWidget(self.root_stack)

        self.auth_page = AuthPage()
        self.auth_page.authenticated.connect(self.set_current_user)
        self.root_stack.addWidget(self.auth_page)

        self.app_shell = QWidget()
        self.app_shell.setObjectName("shellRoot")
        shell_layout = QVBoxLayout(self.app_shell)
        shell_layout.setContentsMargins(18, 18, 18, 18)
        shell_layout.setSpacing(0)

        shell_frame = QFrame()
        shell_frame.setObjectName("shellFrame")
        apply_shadow(shell_frame, blur=44, y_offset=14)
        shell_layout.addWidget(shell_frame)

        frame_layout = QHBoxLayout(shell_frame)
        frame_layout.setContentsMargins(18, 18, 18, 18)
        frame_layout.setSpacing(18)

        sidebar = QFrame()
        sidebar.setObjectName("sidebarPanel")
        apply_shadow(sidebar, blur=34, y_offset=8)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(12)

        brand_plaque = QFrame()
        brand_plaque.setObjectName("titlePlaque")
        brand_layout = QVBoxLayout(brand_plaque)
        brand_layout.setContentsMargins(16, 16, 16, 16)
        brand_icon = QLabel()
        brand_icon.setAlignment(Qt.AlignCenter)
        brand_icon.setPixmap(load_pixmap(str(APP_ICON_PNG), 58))
        brand = QLabel(APP_TITLE)
        brand.setObjectName("sidebarTitle")
        brand.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Collector's desktop gateway")
        subtitle.setObjectName("sidebarMeta")
        subtitle.setAlignment(Qt.AlignCenter)
        brand_layout.addWidget(brand_icon)
        brand_layout.addWidget(brand)
        brand_layout.addWidget(subtitle)

        self.session_label = QLabel("Not signed in")
        self.session_label.setObjectName("statusBadge")
        self.balance_label = QLabel("Tokens: 0")
        self.balance_label.setObjectName("statusBadge")
        self.online_label = QLabel("Online Players: 0")
        self.online_label.setObjectName("statusBadge")
        self.notifications_label = QLabel("Requests: 0")
        self.notifications_label.setObjectName("statusBadge")
        sidebar_layout.addWidget(brand_plaque)
        sidebar_layout.addWidget(self.session_label)
        sidebar_layout.addWidget(self.balance_label)
        sidebar_layout.addWidget(self.online_label)
        sidebar_layout.addWidget(self.notifications_label)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("dashboard", "Main Menu"),
            ("crate", "Summon Chamber"),
            ("inventory", "Collection Vault"),
            ("games", "Gaming District"),
            ("trading", "Trading Hall"),
            ("fighting", "Battle Arena"),
            ("leaderboard", "Hall of Legends"),
            ("search", "Scry Search"),
            ("chat", "Town Chat"),
            ("profile", "Profile"),
        ]:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setObjectName("navButton")
            button.clicked.connect(partial(self.navigate, key))
            sidebar_layout.addWidget(button)
            self.nav_buttons[key] = button

        sidebar_layout.addStretch(1)
        logout_button = QPushButton("Log Out")
        logout_button.setObjectName("secondaryButton")
        logout_button.clicked.connect(self.logout)
        sidebar_layout.addWidget(logout_button)
        frame_layout.addWidget(sidebar, 0)

        content_panel = QFrame()
        content_panel.setObjectName("contentPanel")
        apply_shadow(content_panel, blur=34, y_offset=8)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(18, 18, 18, 18)
        self.page_stack = QStackedWidget()
        content_layout.addWidget(self.page_stack)
        frame_layout.addWidget(content_panel, 1)

        self.pages = {
            "dashboard": DashboardPage(self),
            "crate": CratePage(self),
            "inventory": InventoryPage(self),
            "games": GamesPage(self),
            "trading": TradingLobby(self),
            "fighting": FightingLobby(self),
            "leaderboard": LeaderboardPage(self),
            "search": SearchPage(self),
            "chat": ChatPage(self),
            "profile": ProfilePage(self),
        }
        for page in self.pages.values():
            self.page_stack.addWidget(page)

        self.root_stack.addWidget(self.app_shell)
        self.root_stack.setCurrentWidget(self.auth_page)
        
        # Track active dialogs to prevent duplicates
        self.active_trade_dialogs: dict[int, TradeDialog] = {}
        self.active_battle_dialogs: dict[int, BattleDialog] = {}

    def launch_trade_dialog(self, trade_id: int) -> None:
        if trade_id in self.active_trade_dialogs:
            self.active_trade_dialogs[trade_id].raise_()
            self.active_trade_dialogs[trade_id].activateWindow()
            return
            
        dialog = TradeDialog(self, trade_id)
        self.active_trade_dialogs[trade_id] = dialog
        dialog.finished.connect(lambda: self.active_trade_dialogs.pop(trade_id, None))
        dialog.show()

    def launch_battle_dialog(self, battle_id: int) -> None:
        if battle_id in self.active_battle_dialogs:
            self.active_battle_dialogs[battle_id].raise_()
            self.active_battle_dialogs[battle_id].activateWindow()
            return
            
        dialog = BattleDialog(self, battle_id)
        self.active_battle_dialogs[battle_id] = dialog
        dialog.finished.connect(lambda: self.active_battle_dialogs.pop(battle_id, None))
        dialog.show()

    def update_token_balance(self, tokens: int) -> None:
        if self.current_user is None:
            return

        self.current_user["tokens"] = max(0, int(tokens))
        self.session_label.setText(f"Player: {self.current_user['username']}")
        self.balance_label.setText(f"Tokens: {self.current_user['tokens']}")

        crate_page = self.pages.get("crate")
        if crate_page is not None:
            crate_page.sync_token_balance(self.current_user["tokens"])

        profile_page = self.pages.get("profile")
        if profile_page is not None:
            profile_page.tokens_label.setText(f"Tokens: {self.current_user['tokens']}")

    def refresh_page_if_visible(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        if self.root_stack.currentWidget() is not self.app_shell:
            return
        if self.page_stack.currentWidget() is page:
            page.refresh_page()

    def _on_heartbeat_sync(self, status: dict) -> None:
        """FIX: Instant synchronization from heartbeat response."""
        if not self.current_user: return
        
        # Sync tokens
        if "tokens" in status:
            new_tokens = int(status["tokens"])
            if new_tokens != self.current_user.get("tokens"):
                self.update_token_balance(new_tokens)
        
        # Sync announcements
        announcement = status.get("global_announcement")
        if isinstance(announcement, dict) and announcement.get("message"):
            t = announcement.get("timestamp", 0)
            if t > self.last_announcement_time:
                self.last_announcement_time = t
                QMessageBox.information(self, "📢 Global Announcement", announcement["message"])

        # Sync ban status
        if status.get("is_banned"):
            self.logout()

    def set_current_user(self, user: dict) -> None:
        self.seen_trade_notifications.clear()
        self.seen_battle_notifications.clear()
        self.last_trade_statuses.clear()
        self.last_battle_statuses.clear()
        self.current_user = user
        self.update_token_balance(int(user.get("tokens", 0) or 0))
        
        # FIX: Use HeartbeatWorker
        if self.heartbeat_worker:
            self.heartbeat_worker.stop()
        self.heartbeat_worker = HeartbeatWorker(self.current_user["username"], self.current_user.get("session_token"))
        self.heartbeat_worker.kicked.connect(self.logout)
        self.heartbeat_worker.banned.connect(self.logout)
        # FIX: Connect to status_updated for instant token/state sync
        self.heartbeat_worker.status_updated.connect(self._on_heartbeat_sync)
        self.heartbeat_worker.start()

        self.refresh_session()
        self.check_notifications()
        self.notification_timer.start()
        self.root_stack.setCurrentWidget(self.app_shell)
        self.navigate("dashboard")

    def refresh_session(self) -> None:
        if self.current_user is None:
            return
        if self._session_refresh_in_flight:
            return

        self._session_refresh_in_flight = True
        worker = Worker(get_users)
        worker.signals.finished.connect(self._on_session_refreshed)
        worker.signals.error.connect(self._on_session_refresh_error)
        QThreadPool.globalInstance().start(worker)

    def _on_session_refreshed(self, users: list[dict]) -> None:
        self._session_refresh_in_flight = False
        if self.current_user is None:
            return

        if not users:
            debug_log("[DEBUG] User list is empty, skipping session refresh.")
            return

        username = str(self.current_user.get("username", "")).strip().lower()
        user_meta = next((u for u in users if str(u.get("username", "")).strip().lower() == username), None)

        if user_meta is None:
            # Skip update if user is not in the current online list snapshot
            return

        if user_meta.get("is_banned"):
            debug_log(f"[DEBUG] User {username} is banned, logging out.")
            QMessageBox.critical(self, "Banned", "Your account has been banned.")
            self.logout()
            return

        refreshed_tokens = int(user_meta.get("tokens", self.current_user.get("tokens", 0)) or 0)
        self.current_user["tokens"] = refreshed_tokens
        self.current_user["real_name"] = user_meta.get("real_name", self.current_user.get("real_name", ""))
        self.current_user["email"] = user_meta.get("email", self.current_user.get("email", ""))
        if "id" in user_meta and user_meta["id"]:
            self.current_user["id"] = user_meta["id"]

        self.update_token_balance(refreshed_tokens)

        online_count = sum(1 for u in users if u.get("is_online"))

        self.online_label.setText(f"Online Players: {online_count}")
        self.notifications_label.setText(f"Requests: {self._pending_request_total}")

    def _on_session_refresh_error(self, error: Exception) -> None:
        self._session_refresh_in_flight = False
        debug_log(f"[ERROR] Session refresh failed: {error}")

    def navigate(self, key: str) -> None:
        if key not in self.pages:
            return
        self.page_stack.setCurrentWidget(self.pages[key])
        self.nav_buttons[key].setChecked(True)
        self.pages[key].refresh_page()
        apply_fade_in(self.pages[key])

    def logout(self) -> None:
        if self.heartbeat_worker:
            self.heartbeat_worker.stop()
            self.heartbeat_worker = None
        self.notification_timer.stop()
        self.current_user = None
        self.root_stack.setCurrentWidget(self.auth_page)

    def check_notifications(self) -> None:
        if self.current_user is None or self.root_stack.currentWidget() is self.auth_page:
            return
        if self._notification_fetch_in_flight:
            return
        
        user_id = self.current_user.get("id")
        
        current_page = self.page_stack.currentWidget()
        current_key_is_live = current_page in (self.pages.get("trading"), self.pages.get("fighting"))
        if current_key_is_live:
            current_page.refresh_page()
        
        needs_status_scan = current_key_is_live or bool(self.last_trade_statuses) or bool(self.last_battle_statuses)

        def fetch_notifications(uid: int, include_outgoing_statuses: bool):
            incoming_trades = api.list_incoming_trade_requests(uid)
            incoming_battles = api.list_incoming_battle_requests(uid)

            all_trades = api.list_user_trades(uid) if include_outgoing_statuses else []
            all_battles = api.list_user_battles(uid) if include_outgoing_statuses else []

            return incoming_trades, incoming_battles, all_trades, all_battles

        self._notification_fetch_in_flight = True
        worker = Worker(fetch_notifications, user_id, needs_status_scan)
        worker.signals.finished.connect(self._on_notifications_fetched)
        worker.signals.error.connect(self._on_notifications_error)
        QThreadPool.globalInstance().start(worker)

    def _on_notifications_fetched(self, data: tuple) -> None:
        self._notification_fetch_in_flight = False
        if self.current_user is None or not isinstance(data, tuple) or len(data) != 4:
            return
            
        incoming_trades, incoming_battles, all_trades, all_battles = data
        self._pending_request_total = len(incoming_trades) + len(incoming_battles)
        self.notifications_label.setText(f"Requests: {self._pending_request_total}")
        
        # 1. Handle NEW incoming requests
        for request in incoming_trades:
            if request.get("id") in self.seen_trade_notifications:
                continue
            self.seen_trade_notifications.add(request.get("id"))
            self._handle_trade_request_popup(request)

        for request in incoming_battles:
            if request.get("id") in self.seen_battle_notifications:
                continue
            self.seen_battle_notifications.add(request.get("id"))
            self._handle_battle_request_popup(request)

        # 2. Detect transitions from 'pending' to 'active' or 'open' for outgoing requests
        for trade in all_trades:
            trade_id = trade.get("id")
            if trade_id is None:
                continue
            status = trade.get("status")
            old_status = self.last_trade_statuses.get(trade_id)
            
            if old_status == "pending" and status == "open":
                # Trade just became active!
                self.launch_trade_dialog(trade_id)
            
            self.last_trade_statuses[trade_id] = status

        for battle in all_battles:
            battle_id = battle.get("id")
            if battle_id is None:
                continue
            status = battle.get("status")
            old_status = self.last_battle_statuses.get(battle_id)
            
            if old_status == "pending" and status == "active":
                # Battle just became active!
                self.launch_battle_dialog(battle_id)
            
            self.last_battle_statuses[battle_id] = status

    def _on_notifications_error(self, error: Exception) -> None:
        self._notification_fetch_in_flight = False
        debug_log(f"[ERROR] Notification refresh failed: {error}")

    def _handle_trade_request_popup(self, request: dict) -> None:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Trade Request")
        message_box.setText(f"📜 {request['from_username']} has sent you a trade request scroll.")
        accept_button = message_box.addButton("ACCEPT", QMessageBox.AcceptRole)
        decline_button = message_box.addButton("DECLINE", QMessageBox.RejectRole)
        message_box.exec_()

        clicked = message_box.clickedButton()
        if clicked is accept_button:
            worker = Worker(api.accept_trade_request, request["id"], self.current_user["id"])
            # Use a safe callback that checks if GameWindow still exists
            worker.signals.finished.connect(lambda snap: self.launch_trade_dialog(snap["id"]) if self.current_user else None)
            QThreadPool.globalInstance().start(worker)
        elif clicked is decline_button:
            worker = Worker(api.cancel_trade, request["id"], self.current_user["id"])
            QThreadPool.globalInstance().start(worker)

    def _handle_battle_request_popup(self, request: dict) -> None:
        # Use the new class to handle the dialog and its workers safely
        dialog = BattleRequestDialog(self, request)
        dialog.exec_()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    app.setWindowIcon(QIcon(str(APP_ICON_PNG)))
    window = GameWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
