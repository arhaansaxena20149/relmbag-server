from __future__ import annotations

import sys
from functools import partial

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
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
)

import auth
import combat
import crate_system
import database
import inventory
import trading
from config import APP_ICON_PNG, APP_SUBTITLE, APP_TITLE, BASE_VALUES, CRATE_COST, DROP_RATES, RARITY_COLORS, RARITY_ORDER
from ui_shared import APP_STYLESHEET, apply_fade_in, load_pixmap, with_alpha


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
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(214)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        rarity = QLabel(creature["rarity"])
        rarity.setAlignment(Qt.AlignCenter)
        rarity.setStyleSheet(rarity_badge_stylesheet(creature["rarity_color"]))
        level = QLabel(f"Lv {creature['level']}")
        level.setObjectName("pill")
        top_row.addWidget(rarity, 1)
        top_row.addWidget(level)
        layout.addLayout(top_row)

        image_shell = QFrame()
        image_shell.setStyleSheet(
            f"background: {with_alpha(creature['rarity_color'], 34)}; "
            f"border: 1px solid {with_alpha(creature['rarity_color'], 160)}; border-radius: 18px;"
        )
        image_layout = QVBoxLayout(image_shell)
        image_layout.setContentsMargins(12, 12, 12, 12)

        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        image.setPixmap(load_pixmap(creature["image_path"], 112))
        image_layout.addWidget(image)
        layout.addWidget(image_shell)

        name = QLabel(creature["display_name"])
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet("font-size: 16px; font-weight: 800;")
        layout.addWidget(name)

        stats = QLabel(creature_stat_row(creature))
        stats.setAlignment(Qt.AlignCenter)
        stats.setWordWrap(True)
        stats.setStyleSheet("color: #D2DEED; font-size: 12px;")
        layout.addWidget(stats)

        value = QLabel(f"Value {creature['value']}")
        value.setAlignment(Qt.AlignCenter)
        value.setStyleSheet("color: #AAB6C7; font-weight: 700;")
        layout.addWidget(value)

        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        border = self.creature["rarity_color"] if selected else "#253247"
        glow = with_alpha(self.creature["rarity_color"], 42 if selected else 12)
        self.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {glow}, stop:1 #121B29); "
            f"border: 2px solid {border}; border-radius: 18px;"
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
        action.clicked.connect(on_click)
        action.setMinimumWidth(120)

        layout.addWidget(avatar)
        layout.addLayout(text_col, 1)
        layout.addWidget(action)


class RarityInfoCard(QFrame):
    def __init__(self, rarity: str) -> None:
        super().__init__()
        self.setObjectName("rarityCard")
        color = RARITY_COLORS[rarity]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel(rarity)
        title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {color};")
        chance = QLabel(f"{DROP_RATES[rarity]}% drop rate")
        chance.setStyleSheet("font-weight: 700;")
        value = QLabel(f"Base value: {BASE_VALUES[rarity]}")
        value.setObjectName("mutedText")
        bar = QFrame()
        bar.setFixedHeight(8)
        bar.setStyleSheet(
            f"background: {with_alpha(color, 170)}; border-radius: 4px; border: 1px solid {with_alpha(color, 220)};"
        )

        layout.addWidget(title)
        layout.addWidget(chance)
        layout.addWidget(value)
        layout.addWidget(bar)


class AuthPage(QWidget):
    authenticated = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(60, 50, 60, 50)
        outer.setSpacing(18)

        card = QFrame()
        card.setObjectName("panel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 36, 36, 36)
        card_layout.setSpacing(18)

        title = QLabel(APP_TITLE)
        title.setObjectName("title")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("subtitle")
        helper = QLabel(
            "Create at least two player accounts for trading and PvP-style battles, or run `python3 database.py --seed-demo`."
        )
        helper.setWordWrap(True)
        helper.setStyleSheet("color: #8FA0B8;")

        tabs = QTabWidget()
        tabs.addTab(self._build_login_tab(), "Login")
        tabs.addTab(self._build_signup_tab(), "Sign Up")

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(helper)
        card_layout.addWidget(tabs)
        outer.addStretch(1)
        outer.addWidget(card, alignment=Qt.AlignCenter)
        outer.addStretch(1)

    def _build_login_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form = QFormLayout()

        self.login_identifier = QLineEdit()
        self.login_identifier.setPlaceholderText("Username or email")
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Password")
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_status = QLabel()

        form.addRow("Username / Email", self.login_identifier)
        form.addRow("Password", self.login_password)

        login_button = QPushButton("Log In")
        login_button.clicked.connect(self.handle_login)

        layout.addLayout(form)
        layout.addWidget(login_button)
        layout.addWidget(self.login_status)
        layout.addStretch(1)
        return widget

    def _build_signup_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form = QFormLayout()

        self.signup_email = QLineEdit()
        self.signup_real_name = QLineEdit()
        self.signup_username = QLineEdit()
        self.signup_password = QLineEdit()
        self.signup_password.setEchoMode(QLineEdit.Password)
        self.signup_password.setPlaceholderText("At least 8 characters")
        self.signup_status = QLabel()

        form.addRow("Email", self.signup_email)
        form.addRow("Real Name", self.signup_real_name)
        form.addRow("Username", self.signup_username)
        form.addRow("Password", self.signup_password)

        signup_button = QPushButton("Create Account")
        signup_button.clicked.connect(self.handle_signup)

        layout.addLayout(form)
        layout.addWidget(signup_button)
        layout.addWidget(self.signup_status)
        layout.addStretch(1)
        return widget

    def handle_login(self) -> None:
        try:
            user = auth.login_user(self.login_identifier.text(), self.login_password.text())
        except auth.AuthError as error:
            status_message(self.login_status, str(error), "#F47C7C")
            return
        status_message(self.login_status, "Login successful.", "#63D471")
        self.authenticated.emit(user)

    def handle_signup(self) -> None:
        try:
            user = auth.signup_user(
                self.signup_email.text(),
                self.signup_real_name.text(),
                self.signup_username.text(),
                self.signup_password.text(),
            )
        except auth.AuthError as error:
            status_message(self.signup_status, str(error), "#F47C7C")
            return
        status_message(self.signup_status, "Account created. You are now signed in.", "#63D471")
        self.authenticated.emit(user)


class DashboardPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)

        layout = QVBoxLayout(self)
        layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(26, 24, 26, 24)

        self.welcome_label = QLabel("Welcome")
        self.welcome_label.setObjectName("title")
        self.summary_label = QLabel("Open crates, manage your collection, and line up your next battle.")
        self.summary_label.setObjectName("subtitle")
        hero_layout.addWidget(self.welcome_label)
        hero_layout.addWidget(self.summary_label)
        layout.addWidget(hero)

        stats_row = QHBoxLayout()
        self.creature_count = self._stat_card("Creatures", "0")
        self.total_value = self._stat_card("Collection Value", "0")
        self.highest_rarity = self._stat_card("Top Rarity", "None")
        stats_row.addWidget(self.creature_count[0])
        stats_row.addWidget(self.total_value[0])
        stats_row.addWidget(self.highest_rarity[0])
        layout.addLayout(stats_row)

        quick_panel = QFrame()
        quick_panel.setObjectName("accentPanel")
        quick_layout = QVBoxLayout(quick_panel)
        quick_title = QLabel("Quick Actions")
        quick_title.setObjectName("sectionTitle")
        quick_layout.addWidget(quick_title)

        buttons = QGridLayout()
        actions = [
            ("Open a Crate", "crate"),
            ("View Inventory", "inventory"),
            ("Manage Trades", "trading"),
            ("Start Battle", "fighting"),
            ("Check Profile", "profile"),
        ]
        for index, (label, page_key) in enumerate(actions):
            button = QPushButton(label)
            button.clicked.connect(partial(self.game_window.navigate, page_key))
            buttons.addWidget(button, index // 2, index % 2)
        quick_layout.addLayout(buttons)
        layout.addWidget(quick_panel)
        layout.addStretch(1)

    def _stat_card(self, heading: str, value: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("panel")
        card_layout = QVBoxLayout(card)
        label = QLabel(heading)
        label.setStyleSheet("color: #9FB0C8;")
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 24px; font-weight: 700;")
        card_layout.addWidget(label)
        card_layout.addWidget(value_label)
        return card, value_label

    def refresh_page(self) -> None:
        user = self.game_window.current_user
        if not user:
            return
        summary = inventory.get_inventory_summary(user["id"])
        self.welcome_label.setText(f"Welcome back, {user['username']}")
        self.creature_count[1].setText(str(summary["count"]))
        self.total_value[1].setText(str(summary["total_value"]))
        self.highest_rarity[1].setText(summary["highest_rarity"])


class CratePage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self.roll_timer = QTimer(self)
        self.roll_timer.timeout.connect(self._advance_roll_animation)
        self.roll_ticks = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(18)

        hero_panel = QFrame()
        hero_panel.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero_panel)
        title = QLabel("Summon Chamber")
        title.setObjectName("title")
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
        self.open_button.clicked.connect(self.open_crate)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(badge_row)
        hero_layout.addWidget(self.feedback_label)
        hero_layout.addWidget(self.open_button, alignment=Qt.AlignLeft)
        layout.addWidget(hero_panel)

        body = QHBoxLayout()

        self.result_panel = QFrame()
        self.result_panel.setObjectName("accentPanel")
        result_layout = QVBoxLayout(self.result_panel)
        result_layout.setContentsMargins(24, 24, 24, 24)
        result_title = QLabel("Latest Pull")
        result_title.setObjectName("sectionTitle")
        self.result_rarity = QLabel("No creature pulled yet")
        self.result_rarity.setAlignment(Qt.AlignCenter)
        self.result_rarity.setObjectName("pill")
        self.result_image = QLabel()
        self.result_image.setAlignment(Qt.AlignCenter)
        self.result_image.setPixmap(load_pixmap("", 180))
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
        odds_container = QWidget()
        odds_grid = QGridLayout(odds_container)
        odds_grid.setSpacing(12)
        for index, rarity in enumerate(RARITY_ORDER):
            odds_grid.addWidget(RarityInfoCard(rarity), index // 2, index % 2)
        odds_scroll.setWidget(odds_container)
        odds_layout.addWidget(odds_scroll)
        body.addWidget(odds_panel, 1)

        layout.addLayout(body)
        layout.addStretch(1)

    def refresh_page(self) -> None:
        user = self.game_window.current_user
        if user:
            self.token_label.setText(f"Balance: {user['tokens']} tokens")
        if not self.feedback_label.text():
            status_message(self.feedback_label, "Browse the odds or spend tokens to summon.", "#AEBBD0")

    def open_crate(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        if user["tokens"] < CRATE_COST:
            status_message(self.feedback_label, "Not enough tokens.", "#F47C7C")
            return
        self.roll_ticks = 0
        self.open_button.setEnabled(False)
        status_message(self.feedback_label, "Crate spinning up...", "#F2C14E")
        self.roll_timer.start(120)

    def _advance_roll_animation(self) -> None:
        stages = [
            "Scanning token balance...",
            "Rolling rarity table...",
            "Selecting creature...",
            "Locking reward...",
        ]
        self.roll_ticks += 1
        status_message(self.feedback_label, stages[self.roll_ticks % len(stages)], "#F2C14E")
        if self.roll_ticks >= 7:
            self.roll_timer.stop()
            self.open_button.setEnabled(True)
            self._finish_roll()

    def _finish_roll(self) -> None:
        try:
            result = crate_system.open_crate(self.game_window.current_user["id"])
        except crate_system.CrateError as error:
            status_message(self.feedback_label, str(error), "#F47C7C")
            return

        creature = result["creature"]
        self.game_window.refresh_session()
        self.result_image.setPixmap(load_pixmap(creature["image_path"], 180))
        self.result_panel.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {with_alpha(creature['rarity_color'], 68)}, stop:1 #142236); "
            f"border: 1px solid {with_alpha(creature['rarity_color'], 205)}; border-radius: 18px;"
        )
        self.result_rarity.setText(creature["rarity"])
        self.result_rarity.setStyleSheet(rarity_badge_stylesheet(creature["rarity_color"]))
        self.result_name.setText(creature["display_name"])
        self.result_name.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {creature['rarity_color']};")
        self.result_meta.setText(
            f"Summon Chance: {DROP_RATES[creature['rarity']]}%  |  Level {creature['level']}  |  Trade Value {creature['value']}\n"
            f"Remaining Tokens: {result['remaining_tokens']}  |  Crate Cost: {result['crate_cost']}"
        )
        self.result_stats.setText(
            "Combat Stats\n"
            f"{creature_stat_row(creature)}\n"
            f"Unlocked Moves: {', '.join(move['name'] for move in creature['moves'] if move['unlocked'])}"
        )
        self.result_glow.setText(
            f"You summoned a {creature['rarity']} creature. Sprite, rarity, and drop chance stay visible here after every pull."
        )
        self.result_glow.setStyleSheet(
            f"background: {with_alpha(creature['rarity_color'], 70)}; border: 1px solid {with_alpha(creature['rarity_color'], 190)}; "
            "border-radius: 14px; padding: 8px 10px; font-weight: 700;"
        )
        status_message(self.feedback_label, "Crate opened successfully.", "#63D471")
        self.game_window.pages["inventory"].refresh_page()
        self.game_window.pages["dashboard"].refresh_page()
        self.game_window.pages["profile"].refresh_page()


class InventoryPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self.current_cards: dict[int, CreatureCard] = {}
        self.current_creatures: dict[int, dict] = {}
        self.selected_creature_id: int | None = None

        root = QHBoxLayout(self)
        root.setSpacing(18)

        left_panel = QFrame()
        left_panel.setObjectName("panel")
        left_layout = QVBoxLayout(left_panel)
        title = QLabel("Creature Inventory")
        title.setObjectName("sectionTitle")
        hint = QLabel("Every card shows the creature sprite, rarity, level, and value. Click a card for the full profile.")
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        self.inventory_summary = QLabel("Collection loading...")
        self.inventory_summary.setObjectName("statusBadge")
        left_layout.addWidget(title)
        left_layout.addWidget(hint)
        left_layout.addWidget(self.inventory_summary)

        controls = QHBoxLayout()
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Rarity", "Value", "Level"])
        self.sort_combo.currentTextChanged.connect(self.refresh_page)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All"] + RARITY_ORDER)
        self.filter_combo.currentTextChanged.connect(self.refresh_page)
        controls.addWidget(QLabel("Sort"))
        controls.addWidget(self.sort_combo)
        controls.addWidget(QLabel("Filter"))
        controls.addWidget(self.filter_combo)
        left_layout.addLayout(controls)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.grid_container)
        left_layout.addWidget(self.scroll_area)
        root.addWidget(left_panel, 3)

        right_panel = QFrame()
        right_panel.setObjectName("accentPanel")
        self.detail_panel = right_panel
        right_layout = QVBoxLayout(right_panel)
        self.detail_image = QLabel()
        self.detail_image.setAlignment(Qt.AlignCenter)
        self.detail_image.setPixmap(load_pixmap("", 180))
        self.detail_name = QLabel("Select a creature")
        self.detail_name.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.detail_rarity = QLabel("Rarity")
        self.detail_rarity.setAlignment(Qt.AlignCenter)
        self.detail_chance = QLabel("Summon Chance")
        self.detail_chance.setAlignment(Qt.AlignCenter)
        self.detail_level = QLabel("Level")
        self.detail_value = QLabel("Value")
        self.detail_stats = QLabel("Stats")
        self.detail_stats.setWordWrap(True)
        self.detail_moves = QLabel("Moves")
        self.detail_moves.setWordWrap(True)
        right_layout.addWidget(self.detail_image)
        right_layout.addWidget(self.detail_name)
        right_layout.addWidget(self.detail_rarity)
        right_layout.addWidget(self.detail_chance)
        right_layout.addWidget(self.detail_level)
        right_layout.addWidget(self.detail_value)
        right_layout.addWidget(self.detail_stats)
        right_layout.addWidget(self.detail_moves)
        right_layout.addStretch(1)
        root.addWidget(right_panel, 2)

    def refresh_page(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        sort_map = {"Rarity": "rarity", "Value": "value", "Level": "level"}
        rarity_filter = self.filter_combo.currentText()
        selected_filter = None if rarity_filter == "All" else rarity_filter
        creatures = inventory.get_inventory(user["id"], sort_by=sort_map[self.sort_combo.currentText()], rarity_filter=selected_filter)
        self.current_creatures = {creature["id"]: creature for creature in creatures}
        total_value = sum(creature["value"] for creature in creatures)
        self.inventory_summary.setText(
            f"{len(creatures)} creature{'s' if len(creatures) != 1 else ''} shown  |  Total Value {total_value}"
        )
        clear_layout(self.grid_layout)
        self.current_cards = {}

        if not creatures:
            empty = QLabel("No creatures match this view yet.")
            empty.setStyleSheet("color: #9FB0C8; padding: 18px;")
            self.grid_layout.addWidget(empty, 0, 0)
            self._clear_details()
            return

        for index, creature in enumerate(creatures):
            card = CreatureCard(creature)
            card.clicked.connect(self.select_creature)
            self.current_cards[creature["id"]] = card
            self.grid_layout.addWidget(card, index // 4, index % 4)

        if self.selected_creature_id not in self.current_creatures:
            self.selected_creature_id = creatures[0]["id"]
        self.select_creature(self.selected_creature_id)

    def _clear_details(self) -> None:
        self.detail_panel.setStyleSheet("")
        self.detail_image.setPixmap(load_pixmap("", 180))
        self.detail_name.setText("Select a creature")
        self.detail_rarity.setText("Rarity")
        self.detail_rarity.setStyleSheet("")
        self.detail_chance.setText("Summon Chance")
        self.detail_level.setText("Level")
        self.detail_value.setText("Value")
        self.detail_stats.setText("Stats")
        self.detail_moves.setText("Moves")

    def select_creature(self, creature_id: int) -> None:
        self.selected_creature_id = creature_id
        creature = self.current_creatures.get(creature_id)
        if creature is None:
            return

        for card_id, card in self.current_cards.items():
            card.set_selected(card_id == creature_id)

        self.detail_panel.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {with_alpha(creature['rarity_color'], 64)}, stop:1 #142236); "
            f"border: 1px solid {with_alpha(creature['rarity_color'], 205)}; border-radius: 18px;"
        )
        self.detail_image.setPixmap(load_pixmap(creature["image_path"], 180))
        self.detail_name.setText(creature["display_name"])
        self.detail_name.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {creature['rarity_color']};")
        self.detail_rarity.setText(creature["rarity"])
        self.detail_rarity.setStyleSheet(rarity_badge_stylesheet(creature["rarity_color"]))
        self.detail_chance.setText(f"Summon Chance: {DROP_RATES[creature['rarity']]}%")
        self.detail_chance.setStyleSheet("font-weight: 700; color: #E7EEF9;")
        self.detail_level.setText(f"Level {creature['level']}  |  XP {creature['xp']}")
        self.detail_value.setText(f"Trade Value: {creature['value']}  |  Sprite Stored")
        self.detail_stats.setText(
            "Combat Stats\n"
            f"HP: {creature['stats']['HP']}\n"
            f"Attack: {creature['stats']['Attack']}\n"
            f"Defense: {creature['stats']['Defense']}\n"
            f"Speed: {creature['stats']['Speed']}"
        )
        self.detail_moves.setText("Moves\n" + "\n".join(creature_move_lines(creature)))


class TradingPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self.current_trade_id: int | None = None
        self.current_snapshot: dict | None = None

        root = QVBoxLayout(self)
        root.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero)
        title = QLabel("Trading Hub")
        title.setObjectName("title")
        subtitle = QLabel("Browse online players, send a trade request in one click, and accept incoming offers from your inbox.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        self.trade_banner = QLabel()
        self.trade_banner.setWordWrap(True)
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_page)
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addWidget(self.trade_banner)
        hero_layout.addWidget(refresh_button, alignment=Qt.AlignLeft)
        root.addWidget(hero)

        body = QHBoxLayout()

        online_panel = QFrame()
        online_panel.setObjectName("panel")
        online_layout = QVBoxLayout(online_panel)
        online_title = QLabel("Online Players")
        online_title.setObjectName("sectionTitle")
        online_hint = QLabel("Send a trade request directly from the live player list.")
        online_hint.setObjectName("subtitle")
        online_hint.setWordWrap(True)
        self.online_scroll = QScrollArea()
        self.online_scroll.setWidgetResizable(True)
        self.online_container = QWidget()
        self.online_layout = QVBoxLayout(self.online_container)
        self.online_layout.setSpacing(12)
        self.online_layout.setAlignment(Qt.AlignTop)
        self.online_scroll.setWidget(self.online_container)
        online_layout.addWidget(online_title)
        online_layout.addWidget(online_hint)
        online_layout.addWidget(self.online_scroll)
        body.addWidget(online_panel, 1)

        trades_panel = QFrame()
        trades_panel.setObjectName("panel")
        trades_layout = QVBoxLayout(trades_panel)
        trades_title = QLabel("Requests & Trades")
        trades_title.setObjectName("sectionTitle")
        trades_hint = QLabel("Incoming requests stay on top, then active trades, then history.")
        trades_hint.setObjectName("subtitle")
        trades_hint.setWordWrap(True)
        self.trade_list = QListWidget()
        self.trade_list.itemSelectionChanged.connect(self.on_trade_selected)
        trades_layout.addWidget(trades_title)
        trades_layout.addWidget(trades_hint)
        trades_layout.addWidget(self.trade_list)
        body.addWidget(trades_panel, 1)

        detail_panel = QFrame()
        detail_panel.setObjectName("panel")
        detail_layout = QVBoxLayout(detail_panel)
        self.trade_header = QLabel("Select or create a trade.")
        self.trade_header.setObjectName("sectionTitle")
        self.trade_status = QLabel()
        self.trade_status.setWordWrap(True)
        detail_layout.addWidget(self.trade_header)
        detail_layout.addWidget(self.trade_status)

        self.request_panel = QFrame()
        self.request_panel.setObjectName("softPanel")
        request_layout = QHBoxLayout(self.request_panel)
        self.accept_trade_button = QPushButton("Accept Trade")
        self.accept_trade_button.setObjectName("successButton")
        self.accept_trade_button.clicked.connect(self.accept_trade_request)
        self.decline_trade_button = QPushButton("Decline Trade")
        self.decline_trade_button.setObjectName("dangerButton")
        self.decline_trade_button.clicked.connect(self.decline_trade_request)
        self.cancel_request_button = QPushButton("Cancel Request")
        self.cancel_request_button.setObjectName("dangerButton")
        self.cancel_request_button.clicked.connect(self.cancel_trade)
        request_layout.addWidget(self.accept_trade_button)
        request_layout.addWidget(self.decline_trade_button)
        request_layout.addWidget(self.cancel_request_button)
        detail_layout.addWidget(self.request_panel)

        self.offer_panel = QFrame()
        self.offer_panel.setObjectName("accentPanel")
        offer_layout = QVBoxLayout(self.offer_panel)
        self.inventory_list = QListWidget()
        self.my_offer_list = QListWidget()
        self.their_offer_list = QListWidget()
        self.your_offer_title = QLabel("Your Offer")
        self.their_offer_title = QLabel("Their Offer")
        self.offer_tokens = QSpinBox()
        self.offer_tokens.setMaximum(99999999)
        self.offer_tokens.setPrefix("Tokens: ")

        offer_layout.addWidget(QLabel("Your Inventory"))
        offer_layout.addWidget(self.inventory_list)

        controls = QHBoxLayout()
        add_button = QPushButton("Add Creature")
        add_button.clicked.connect(self.add_selected_creature)
        remove_button = QPushButton("Remove Offered Creature")
        remove_button.setObjectName("secondaryButton")
        remove_button.clicked.connect(self.remove_selected_creature)
        controls.addWidget(add_button)
        controls.addWidget(remove_button)
        offer_layout.addLayout(controls)

        token_row = QHBoxLayout()
        update_tokens_button = QPushButton("Update Token Offer")
        update_tokens_button.setObjectName("secondaryButton")
        update_tokens_button.clicked.connect(self.update_token_offer)
        token_row.addWidget(self.offer_tokens)
        token_row.addWidget(update_tokens_button)
        offer_layout.addLayout(token_row)

        offer_layout.addWidget(self.your_offer_title)
        offer_layout.addWidget(self.my_offer_list)
        offer_layout.addWidget(self.their_offer_title)
        offer_layout.addWidget(self.their_offer_list)

        confirm_row = QHBoxLayout()
        self.confirm_button = QPushButton("Confirm Trade")
        self.confirm_button.clicked.connect(self.confirm_trade)
        self.cancel_trade_button = QPushButton("Cancel Trade")
        self.cancel_trade_button.setObjectName("dangerButton")
        self.cancel_trade_button.clicked.connect(self.cancel_trade)
        confirm_row.addWidget(self.confirm_button)
        confirm_row.addWidget(self.cancel_trade_button)
        offer_layout.addLayout(confirm_row)

        self.your_value_label = QLabel("Your Value: 0")
        self.their_value_label = QLabel("Their Value: 0")
        self.fairness_label = QLabel("Fairness")
        self.fairness_label.setAlignment(Qt.AlignCenter)
        offer_layout.addWidget(self.your_value_label)
        offer_layout.addWidget(self.their_value_label)
        offer_layout.addWidget(self.fairness_label)
        detail_layout.addWidget(self.offer_panel)
        body.addWidget(detail_panel, 2)

        root.addLayout(body)

    def refresh_page(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        self._populate_online_players()
        trades = trading.list_user_trades(user["id"])
        self.trade_list.blockSignals(True)
        self.trade_list.clear()
        selected_row = 0
        for index, trade_row in enumerate(trades):
            if trade_row["status"] == "pending":
                direction = "Incoming" if trade_row["direction"] == "incoming" else "Sent"
            elif trade_row["status"] == "open":
                direction = "Active"
            else:
                direction = trade_row["status"].title()
            item = QListWidgetItem(f"{direction}  |  {trade_row['counterpart_username']}")
            item.setData(Qt.UserRole, trade_row["id"])
            self.trade_list.addItem(item)
            if trade_row["id"] == self.current_trade_id:
                selected_row = index
        self.trade_list.blockSignals(False)

        incoming_count = sum(1 for trade_row in trades if trade_row["status"] == "pending" and trade_row["direction"] == "incoming")
        active_count = sum(1 for trade_row in trades if trade_row["status"] == "open")
        status_message(
            self.trade_banner,
            f"{incoming_count} incoming request{'s' if incoming_count != 1 else ''}  |  {active_count} active trade{'s' if active_count != 1 else ''}",
            "#AEBBD0",
        )

        if trades:
            if self.current_trade_id not in {row["id"] for row in trades}:
                self.current_trade_id = trades[0]["id"]
                selected_row = 0
            self.trade_list.setCurrentRow(selected_row)
            self.load_trade_snapshot()
        else:
            self.current_trade_id = None
            self.current_snapshot = None
            self.clear_trade_display()

    def _populate_online_players(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        clear_layout(self.online_layout)
        online_players = database.list_online_users(user["id"])
        if not online_players:
            empty = QLabel("No other players are online right now. Open a second player window or have another player log in.")
            empty.setWordWrap(True)
            empty.setObjectName("mutedText")
            self.online_layout.addWidget(empty)
            return

        for player in online_players:
            self.online_layout.addWidget(
                PlayerActionCard(
                    username=player["username"],
                    creature_count=player["creature_count"],
                    accent="#58C96B",
                    button_text="Trade",
                    on_click=partial(self.create_trade, player["username"]),
                )
            )
        self.online_layout.addStretch(1)

    def create_trade(self, username: str) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        try:
            snapshot = trading.create_trade(user["id"], username)
        except trading.TradeError as error:
            show_error(self, str(error))
            return
        self.current_trade_id = snapshot["id"]
        self.refresh_page()

    def on_trade_selected(self) -> None:
        item = self.trade_list.currentItem()
        if item is None:
            return
        self.current_trade_id = item.data(Qt.UserRole)
        self.load_trade_snapshot()

    def load_trade_snapshot(self) -> None:
        if self.current_trade_id is None:
            self.clear_trade_display()
            return
        try:
            self.current_snapshot = trading.get_trade(self.current_trade_id, self.game_window.current_user["id"])
        except trading.TradeError as error:
            show_error(self, str(error))
            self.current_snapshot = None
            return
        self.render_snapshot()

    def clear_trade_display(self) -> None:
        self.trade_header.setText("Select or create a trade.")
        self.trade_status.setText("Online players appear on the left. Click Trade to send a request.")
        self.request_panel.hide()
        self.offer_panel.hide()
        self.inventory_list.clear()
        self.my_offer_list.clear()
        self.their_offer_list.clear()
        self.your_value_label.setText("Your Value: 0")
        self.their_value_label.setText("Their Value: 0")
        self.fairness_label.setText("Fairness")
        self.fairness_label.setStyleSheet("")

    def render_snapshot(self) -> None:
        snapshot = self.current_snapshot
        if snapshot is None:
            self.clear_trade_display()
            return
        your_side = snapshot["your_side"]
        their_side = snapshot["their_side"]
        self.trade_header.setText(f"Trade with {their_side['username']}")
        self.trade_status.setText(self._describe_trade(snapshot))
        self.offer_tokens.setMaximum(self.game_window.current_user["tokens"])
        self.offer_tokens.setValue(your_side["tokens"])
        self.your_offer_title.setText(f"Your Offer ({'Confirmed' if your_side['confirmed'] else 'Open'})")
        self.their_offer_title.setText(f"Their Offer ({'Confirmed' if their_side['confirmed'] else 'Open'})")

        self.request_panel.setVisible(snapshot["status"] == "pending")
        self.accept_trade_button.setVisible(snapshot["can_accept"])
        self.decline_trade_button.setVisible(snapshot["can_decline"])
        self.cancel_request_button.setVisible(snapshot["can_cancel_request"])

        self.offer_panel.setVisible(snapshot["status"] in {"open", "completed"})
        self.confirm_button.setVisible(snapshot["status"] == "open")
        self.cancel_trade_button.setVisible(snapshot["status"] == "open")
        self.inventory_list.setEnabled(snapshot["status"] == "open")
        self.offer_tokens.setEnabled(snapshot["status"] == "open")
        self.populate_inventory_list()
        self.populate_offer_lists(snapshot)

    def _describe_trade(self, snapshot: dict) -> str:
        your_side = snapshot["your_side"]
        their_side = snapshot["their_side"]
        if snapshot["status"] == "pending":
            if snapshot["can_accept"]:
                return f"{their_side['username']} wants to trade. Accept to open the trade builder, or decline the request."
            return f"Trade request sent to {their_side['username']}. Waiting for a response."
        if snapshot["status"] == "open":
            return (
                f"You {'have' if your_side['confirmed'] else 'have not'} confirmed. "
                f"{their_side['username']} {'has' if their_side['confirmed'] else 'has not'} confirmed."
            )
        if snapshot["status"] == "completed":
            return f"Trade completed with {their_side['username']}."
        if snapshot["status"] == "declined":
            return f"{their_side['username']} declined this trade request."
        return "This trade is no longer active."

    def populate_inventory_list(self) -> None:
        self.inventory_list.clear()
        if self.current_snapshot is None or self.current_snapshot["status"] != "open":
            return
        offered_ids = {creature["id"] for creature in self.current_snapshot["your_side"]["creatures"]}
        creatures = inventory.get_inventory(self.game_window.current_user["id"], sort_by="rarity")
        for creature in creatures:
            suffix = " [OFFERED]" if creature["id"] in offered_ids else ""
            item = QListWidgetItem(
                f"{creature['display_name']} | {creature['rarity']} | Lv {creature['level']} | Value {creature['value']}{suffix}"
            )
            item.setData(Qt.UserRole, creature["id"])
            self.inventory_list.addItem(item)

    def populate_offer_lists(self, snapshot: dict) -> None:
        your_side = snapshot["your_side"]
        their_side = snapshot["their_side"]
        self.my_offer_list.clear()
        self.their_offer_list.clear()
        for creature in your_side["creatures"]:
            item = QListWidgetItem(
                f"{creature['display_name']} | {creature['rarity']} | Lv {creature['level']} | Value {creature['value']}"
            )
            item.setData(Qt.UserRole, creature["id"])
            self.my_offer_list.addItem(item)
        if your_side["tokens"]:
            self.my_offer_list.addItem(QListWidgetItem(f"Tokens: {your_side['tokens']}"))
        for creature in their_side["creatures"]:
            self.their_offer_list.addItem(
                QListWidgetItem(
                    f"{creature['display_name']} | {creature['rarity']} | Lv {creature['level']} | Value {creature['value']}"
                )
            )
        if their_side["tokens"]:
            self.their_offer_list.addItem(QListWidgetItem(f"Tokens: {their_side['tokens']}"))

        fairness = snapshot["fairness"]
        self.your_value_label.setText(f"Your Value: {fairness['initiator_value'] if snapshot['initiator']['id'] == self.game_window.current_user['id'] else fairness['recipient_value']}")
        self.their_value_label.setText(f"Their Value: {fairness['recipient_value'] if snapshot['initiator']['id'] == self.game_window.current_user['id'] else fairness['initiator_value']}")
        self.fairness_label.setText(f"{fairness['label']} ({fairness['delta_percent']}% difference)")
        self.fairness_label.setStyleSheet(
            f"background: {fairness['color']}; color: #081018; border-radius: 999px; padding: 8px 12px; font-weight: 700;"
        )

    def accept_trade_request(self) -> None:
        if self.current_trade_id is None:
            return
        try:
            self.current_snapshot = trading.accept_trade_request(
                self.current_trade_id,
                self.game_window.current_user["id"],
            )
        except trading.TradeError as error:
            show_error(self, str(error))
            return
        self.render_snapshot()
        self.refresh_page()

    def decline_trade_request(self) -> None:
        if self.current_trade_id is None:
            return
        try:
            trading.decline_trade_request(
                self.current_trade_id,
                self.game_window.current_user["id"],
            )
        except trading.TradeError as error:
            show_error(self, str(error))
            return
        self.current_trade_id = None
        self.refresh_page()

    def add_selected_creature(self) -> None:
        if self.current_trade_id is None:
            return
        item = self.inventory_list.currentItem()
        if item is None:
            show_error(self, "Select a creature from your inventory first.")
            return
        try:
            self.current_snapshot = trading.add_creature_to_trade(
                self.current_trade_id,
                self.game_window.current_user["id"],
                item.data(Qt.UserRole),
            )
        except trading.TradeError as error:
            show_error(self, str(error))
            return
        self.load_trade_snapshot()

    def remove_selected_creature(self) -> None:
        if self.current_trade_id is None:
            return
        item = self.my_offer_list.currentItem()
        if item is None or item.data(Qt.UserRole) is None:
            show_error(self, "Select one of your offered creatures first.")
            return
        try:
            self.current_snapshot = trading.remove_creature_from_trade(
                self.current_trade_id,
                self.game_window.current_user["id"],
                item.data(Qt.UserRole),
            )
        except trading.TradeError as error:
            show_error(self, str(error))
            return
        self.load_trade_snapshot()

    def update_token_offer(self) -> None:
        if self.current_trade_id is None:
            return
        try:
            self.current_snapshot = trading.set_trade_tokens(
                self.current_trade_id,
                self.game_window.current_user["id"],
                self.offer_tokens.value(),
            )
        except trading.TradeError as error:
            show_error(self, str(error))
            return
        self.load_trade_snapshot()

    def confirm_trade(self) -> None:
        if self.current_trade_id is None:
            return
        try:
            self.current_snapshot = trading.confirm_trade(
                self.current_trade_id,
                self.game_window.current_user["id"],
            )
        except trading.TradeError as error:
            show_error(self, str(error))
            return
        self.game_window.refresh_session()
        self.load_trade_snapshot()
        if self.current_snapshot["status"] == "completed":
            QMessageBox.information(self, "Trade Complete", "Both sides confirmed. The trade has been executed.")
            self.game_window.pages["inventory"].refresh_page()
            self.game_window.pages["profile"].refresh_page()
            self.game_window.pages["dashboard"].refresh_page()

    def cancel_trade(self) -> None:
        if self.current_trade_id is None:
            return
        try:
            trading.cancel_trade(self.current_trade_id, self.game_window.current_user["id"])
        except trading.TradeError as error:
            show_error(self, str(error))
            return
        self.current_trade_id = None
        self.refresh_page()


class FightingPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self.current_battle_id: int | None = None
        self.current_snapshot: dict | None = None

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(2500)
        self.poll_timer.timeout.connect(self.poll_updates)
        self.poll_timer.start()

        root = QVBoxLayout(self)
        root.setSpacing(18)

        hero_panel = QFrame()
        hero_panel.setObjectName("heroPanel")
        hero_layout = QGridLayout(hero_panel)
        self.challenge_creature_combo = QComboBox()
        refresh_button = QPushButton("Refresh Battles")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh_page)
        self.battle_status = QLabel()
        self.battle_status.setWordWrap(True)
        title = QLabel("PvP Battle Arena")
        title.setObjectName("title")
        helper = QLabel(
            "Choose one creature to represent you, challenge an online player, and then lock one move per round until someone faints."
        )
        helper.setWordWrap(True)
        helper.setObjectName("subtitle")
        hero_layout.addWidget(title, 0, 0, 1, 2)
        hero_layout.addWidget(helper, 1, 0, 1, 2)
        hero_layout.addWidget(QLabel("Your Battle Creature"), 2, 0)
        hero_layout.addWidget(self.challenge_creature_combo, 2, 1)
        hero_layout.addWidget(refresh_button, 3, 0)
        hero_layout.addWidget(self.battle_status, 3, 1)
        root.addWidget(hero_panel)

        body = QHBoxLayout()

        online_panel = QFrame()
        online_panel.setObjectName("panel")
        online_layout = QVBoxLayout(online_panel)
        online_title = QLabel("Online Players")
        online_title.setObjectName("sectionTitle")
        online_hint = QLabel("Challenge from the live list. The other player picks one defending creature when they accept.")
        online_hint.setObjectName("subtitle")
        online_hint.setWordWrap(True)
        self.online_battle_scroll = QScrollArea()
        self.online_battle_scroll.setWidgetResizable(True)
        self.online_battle_container = QWidget()
        self.online_battle_layout = QVBoxLayout(self.online_battle_container)
        self.online_battle_layout.setSpacing(12)
        self.online_battle_layout.setAlignment(Qt.AlignTop)
        self.online_battle_scroll.setWidget(self.online_battle_container)
        online_layout.addWidget(online_title)
        online_layout.addWidget(online_hint)
        online_layout.addWidget(self.online_battle_scroll)
        body.addWidget(online_panel, 1)

        battles_panel = QFrame()
        battles_panel.setObjectName("panel")
        battles_layout = QVBoxLayout(battles_panel)
        battles_title = QLabel("Challenges & Battles")
        battles_title.setObjectName("sectionTitle")
        battles_hint = QLabel("Incoming requests stay near the top, followed by active and completed battles.")
        battles_hint.setObjectName("subtitle")
        battles_hint.setWordWrap(True)
        self.battle_list = QListWidget()
        self.battle_list.itemSelectionChanged.connect(self.on_battle_selected)
        battles_layout.addWidget(battles_title)
        battles_layout.addWidget(battles_hint)
        battles_layout.addWidget(self.battle_list)
        body.addWidget(battles_panel, 1)

        detail_panel = QFrame()
        detail_panel.setObjectName("panel")
        detail_layout = QVBoxLayout(detail_panel)
        self.battle_header = QLabel("Select or create a battle challenge.")
        self.battle_header.setObjectName("sectionTitle")
        self.battle_meta = QLabel()
        self.battle_meta.setWordWrap(True)
        detail_layout.addWidget(self.battle_header)
        detail_layout.addWidget(self.battle_meta)

        self.pending_panel = QFrame()
        self.pending_panel.setObjectName("softPanel")
        pending_layout = QHBoxLayout(self.pending_panel)
        self.accept_creature_combo = QComboBox()
        self.accept_button = QPushButton("Accept Challenge")
        self.accept_button.setObjectName("successButton")
        self.accept_button.clicked.connect(self.accept_battle)
        self.cancel_button = QPushButton("Decline / Cancel")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.clicked.connect(self.cancel_battle)
        pending_layout.addWidget(QLabel("Your Creature"))
        pending_layout.addWidget(self.accept_creature_combo)
        pending_layout.addWidget(self.accept_button)
        pending_layout.addWidget(self.cancel_button)
        detail_layout.addWidget(self.pending_panel)

        battle_row = QHBoxLayout()
        self.player_panel = self._combatant_panel("Your Creature")
        self.opponent_panel = self._combatant_panel("Opponent")
        battle_row.addWidget(self.player_panel[0])
        battle_row.addWidget(self.opponent_panel[0])
        detail_layout.addLayout(battle_row)

        self.moves_panel = QFrame()
        self.moves_panel.setObjectName("panel")
        moves_layout = QGridLayout(self.moves_panel)
        self.move_buttons: list[QPushButton] = []
        for index in range(4):
            button = QPushButton(f"Move {index + 1}")
            button.clicked.connect(partial(self.submit_move, index))
            button.setEnabled(False)
            self.move_buttons.append(button)
            moves_layout.addWidget(button, index // 2, index % 2)
        detail_layout.addWidget(self.moves_panel)

        action_row = QHBoxLayout()
        self.forfeit_button = QPushButton("Forfeit Battle")
        self.forfeit_button.setObjectName("dangerButton")
        self.forfeit_button.clicked.connect(self.forfeit_battle)
        action_row.addStretch(1)
        action_row.addWidget(self.forfeit_button)
        detail_layout.addLayout(action_row)

        log_panel = QFrame()
        log_panel.setObjectName("panel")
        log_layout = QVBoxLayout(log_panel)
        log_title = QLabel("Battle Log")
        log_title.setObjectName("sectionTitle")
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log_box)
        detail_layout.addWidget(log_panel)

        body.addWidget(detail_panel, 2)
        root.addLayout(body)

    def _combatant_panel(self, heading: str) -> tuple[QFrame, QLabel, QLabel, QProgressBar, QLabel, QLabel]:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        title = QLabel(heading)
        title.setObjectName("sectionTitle")
        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        name = QLabel("No creature selected")
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet("font-size: 18px; font-weight: 700;")
        hp_bar = QProgressBar()
        hp_text = QLabel("HP")
        stats = QLabel("Stats")
        stats.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(image)
        layout.addWidget(name)
        layout.addWidget(hp_bar)
        layout.addWidget(hp_text)
        layout.addWidget(stats)
        layout.addStretch(1)
        return panel, image, name, hp_bar, hp_text, stats

    def refresh_page(self) -> None:
        self.game_window.refresh_session()
        self._load_user_creatures()
        self._populate_online_players()
        self._refresh_battle_list()
        if self.current_battle_id is not None:
            self.load_battle_snapshot()
        else:
            self.clear_battle_display()
        self._set_battle_status("Choose a creature, then challenge someone from the online list.", "#9FB0C8")

    def _load_user_creatures(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        creatures = inventory.get_inventory(user["id"], sort_by="rarity")
        self.challenge_creature_combo.clear()
        self.accept_creature_combo.clear()
        for creature in creatures:
            label = f"{creature['display_name']} | {creature['rarity']} | Lv {creature['level']}"
            self.challenge_creature_combo.addItem(label, creature["id"])
            self.accept_creature_combo.addItem(
                f"{creature['display_name']} | {creature['rarity']} | Lv {creature['level']}",
                creature["id"],
            )

    def _populate_online_players(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        clear_layout(self.online_battle_layout)
        online_players = database.list_online_users(user["id"])
        if not online_players:
            empty = QLabel("No opponents are online right now. Open another player window or wait for another login.")
            empty.setWordWrap(True)
            empty.setObjectName("mutedText")
            self.online_battle_layout.addWidget(empty)
            return

        for player in online_players:
            self.online_battle_layout.addWidget(
                PlayerActionCard(
                    username=player["username"],
                    creature_count=player["creature_count"],
                    accent="#44A4FF",
                    button_text="Battle",
                    on_click=partial(self.create_battle, player["username"]),
                )
            )
        self.online_battle_layout.addStretch(1)

    def _refresh_battle_list(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        battles = combat.list_user_battles(user["id"])
        selected_index = 0
        self.battle_list.blockSignals(True)
        self.battle_list.clear()
        for index, battle in enumerate(battles):
            if battle["status"] == "pending":
                relation = "Incoming" if battle["direction"] == "incoming" else "Sent"
            elif battle["status"] == "active":
                relation = "Active"
            else:
                relation = battle["status"].title()
            item = QListWidgetItem(f"{relation}  |  {battle['counterpart_username']}")
            item.setData(Qt.UserRole, battle["id"])
            self.battle_list.addItem(item)
            if battle["id"] == self.current_battle_id:
                selected_index = index
        self.battle_list.blockSignals(False)

        available_ids = {battle["id"] for battle in battles}
        if battles:
            if self.current_battle_id not in available_ids:
                self.current_battle_id = battles[0]["id"]
                selected_index = 0
            self.battle_list.setCurrentRow(selected_index)
        else:
            self.current_battle_id = None

    def _set_battle_status(self, text: str, color: str) -> None:
        status_message(self.battle_status, text, color)

    def create_battle(self, username: str) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        creature_id = self.challenge_creature_combo.currentData()
        if creature_id is None:
            self._set_battle_status("You need at least one creature to challenge another player.", "#F47C7C")
            return
        try:
            snapshot = combat.create_battle(user["id"], username, creature_id)
        except combat.CombatError as error:
            self._set_battle_status(str(error), "#F47C7C")
            return
        self.current_battle_id = snapshot["id"]
        self._refresh_battle_list()
        self.load_battle_snapshot()
        self._set_battle_status("Battle challenge sent.", "#63D471")

    def on_battle_selected(self) -> None:
        item = self.battle_list.currentItem()
        if item is None:
            return
        self.current_battle_id = item.data(Qt.UserRole)
        self.load_battle_snapshot()

    def load_battle_snapshot(self) -> None:
        if self.current_battle_id is None:
            self.clear_battle_display()
            return
        try:
            self.current_snapshot = combat.get_battle(self.current_battle_id, self.game_window.current_user["id"])
        except combat.CombatError as error:
            self.current_snapshot = None
            self.clear_battle_display()
            self._set_battle_status(str(error), "#F47C7C")
            return
        self.render_snapshot()

    def clear_battle_display(self) -> None:
        self.current_snapshot = None
        self.battle_header.setText("Select or create a battle challenge.")
        self.battle_meta.setText("")
        self.pending_panel.hide()
        self.moves_panel.hide()
        self.forfeit_button.hide()
        self.log_box.clear()
        self._render_side(self.player_panel, None, None)
        self._render_side(self.opponent_panel, None, None)
        self._update_move_buttons()

    def _render_side(self, widgets, creature_data: dict | None, state: dict | None) -> None:
        _panel, image, name, hp_bar, hp_text, stats = widgets
        if creature_data is None and state is None:
            image.clear()
            name.setText("No creature selected")
            hp_bar.setMaximum(100)
            hp_bar.setValue(0)
            hp_bar.setFormat("")
            hp_text.setText("HP")
            stats.setText("Stats")
            return

        image_path = creature_data["image_path"] if creature_data else state["image_path"]
        display_name = creature_data["display_name"] if creature_data else state["name"]
        rarity = creature_data["rarity"] if creature_data else state["rarity"]
        level = creature_data["level"] if creature_data else state["level"]
        rarity_color = creature_data["rarity_color"] if creature_data else RARITY_COLORS[rarity]

        image.setPixmap(load_pixmap(image_path, 140))
        name.setText(f"{display_name} | {rarity} | Lv {level}")
        name.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {rarity_color};")

        if state:
            hp_bar.setMaximum(state["max_hp"])
            hp_bar.setValue(state["current_hp"])
            hp_bar.setFormat(f"{state['current_hp']} / {state['max_hp']}")
            stat_block = state["stats"]
            hp_value = state["current_hp"]
            max_hp = state["max_hp"]
        else:
            hp_bar.setMaximum(creature_data["stats"]["HP"])
            hp_bar.setValue(creature_data["stats"]["HP"])
            hp_bar.setFormat(f"{creature_data['stats']['HP']} / {creature_data['stats']['HP']}")
            stat_block = creature_data["stats"]
            hp_value = creature_data["stats"]["HP"]
            max_hp = creature_data["stats"]["HP"]
        hp_text.setText("Hit Points")
        stats.setText(
            f"HP {hp_value}/{max_hp}  |  Attack {stat_block['Attack']}  |  Defense {stat_block['Defense']}  |  Speed {stat_block['Speed']}"
        )

    def render_snapshot(self) -> None:
        snapshot = self.current_snapshot
        if snapshot is None:
            self.clear_battle_display()
            return

        your_side = snapshot["your_side"]
        their_side = snapshot["their_side"]
        self.battle_header.setText(f"Battle with {their_side['username']}")
        self.battle_meta.setText(self._describe_snapshot(snapshot))
        self.pending_panel.setVisible(snapshot["status"] == "pending")
        self.accept_creature_combo.setEnabled(snapshot["can_accept"])
        self.accept_button.setVisible(snapshot["can_accept"])
        self.cancel_button.setVisible(snapshot["can_cancel"])
        self.moves_panel.setVisible(snapshot["status"] == "active")
        self.forfeit_button.setVisible(snapshot["can_forfeit"])
        self._render_side(self.player_panel, your_side["creature"], your_side["combatant"])
        self._render_side(self.opponent_panel, their_side["creature"], their_side["combatant"])
        self.log_box.setPlainText("\n".join(snapshot["log"]))
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())
        self._update_move_buttons()

    def _update_move_buttons(self) -> None:
        move_options = self.current_snapshot["your_move_options"] if self.current_snapshot else []
        pending_move = self.current_snapshot["your_pending_move"] if self.current_snapshot else None
        active = bool(self.current_snapshot and self.current_snapshot["can_submit_moves"])

        if not move_options:
            for button in self.move_buttons:
                button.setEnabled(False)
                button.setText("Move Slot")
            return

        for index, button in enumerate(self.move_buttons):
            if index >= len(move_options):
                button.setEnabled(False)
                button.setText("Locked")
                continue

            move = move_options[index]
            suffix = "Ready" if move["available"] else f"Ready in {move['remaining_cooldown']}"
            button = self.move_buttons[index]
            button.setText(f"{move['name']}\nDMG {move['damage']} | CD {move['cooldown']} | {suffix}")
            button.setEnabled(active and pending_move is None and move["available"])

    def _describe_snapshot(self, snapshot: dict) -> str:
        their_side = snapshot["their_side"]
        if snapshot["status"] == "pending":
            if snapshot["can_accept"]:
                return (
                    f"Incoming battle request from {their_side['username']}. "
                    "Choose one creature to represent you, then accept or decline."
                )
            return f"Battle request sent to {their_side['username']}. Waiting for them to lock in one creature."
        if snapshot["status"] == "active":
            if snapshot["your_pending_move"]:
                return f"You locked in {snapshot['your_pending_move']}. Waiting for {their_side['username']}."
            if snapshot["their_move_submitted"]:
                return f"{their_side['username']} is ready. Choose your move for round {snapshot['round_number'] + 1}."
            return f"Round {snapshot['round_number'] + 1}. Both players choose a move."
        if snapshot["status"] == "completed":
            if snapshot["you_won"] is True:
                return f"Battle complete. You defeated {their_side['username']}."
            if snapshot["you_won"] is False:
                return f"Battle complete. {their_side['username']} won this battle."
            return "Battle complete."
        return "This battle is no longer active."

    def accept_battle(self) -> None:
        if self.current_battle_id is None:
            return
        creature_id = self.accept_creature_combo.currentData()
        if creature_id is None:
            self._set_battle_status("You need a creature to accept the battle.", "#F47C7C")
            return
        try:
            self.current_snapshot = combat.accept_battle(
                self.current_battle_id,
                self.game_window.current_user["id"],
                creature_id,
            )
        except combat.CombatError as error:
            self._set_battle_status(str(error), "#F47C7C")
            return
        self.render_snapshot()
        self._set_battle_status("Battle accepted. Both players can choose moves now.", "#63D471")

    def cancel_battle(self) -> None:
        if self.current_battle_id is None:
            return
        try:
            combat.cancel_battle(self.current_battle_id, self.game_window.current_user["id"])
        except combat.CombatError as error:
            self._set_battle_status(str(error), "#F47C7C")
            return
        self.current_battle_id = None
        self._refresh_battle_list()
        if self.current_battle_id is not None:
            self.load_battle_snapshot()
        else:
            self.clear_battle_display()
        self._set_battle_status("Pending challenge removed.", "#F2C14E")

    def submit_move(self, index: int) -> None:
        if self.current_snapshot is None or self.current_battle_id is None:
            return
        move_options = self.current_snapshot["your_move_options"]
        if index >= len(move_options):
            return
        move = move_options[index]
        if not move["available"]:
            return
        try:
            self.current_snapshot = combat.submit_move(
                self.current_battle_id,
                self.game_window.current_user["id"],
                move["name"],
            )
        except combat.CombatError as error:
            self._set_battle_status(str(error), "#F47C7C")
            return
        self.render_snapshot()
        self._handle_post_battle_updates()
        if self.current_snapshot["status"] == "active":
            self._set_battle_status("Move submitted.", "#63D471")
        else:
            self._set_battle_status("Battle resolved.", "#63D471")

    def forfeit_battle(self) -> None:
        if self.current_battle_id is None:
            return
        try:
            self.current_snapshot = combat.forfeit_battle(
                self.current_battle_id,
                self.game_window.current_user["id"],
            )
        except combat.CombatError as error:
            self._set_battle_status(str(error), "#F47C7C")
            return
        self.render_snapshot()
        self._handle_post_battle_updates()
        self._set_battle_status("You forfeited the battle.", "#F2C14E")

    def _handle_post_battle_updates(self) -> None:
        if self.current_snapshot and self.current_snapshot["status"] == "completed":
            self.game_window.refresh_session()
            self.game_window.pages["inventory"].refresh_page()
            self.game_window.pages["profile"].refresh_page()
            self.game_window.pages["dashboard"].refresh_page()
            self._refresh_battle_list()

    def poll_updates(self) -> None:
        if not self.isVisible():
            return
        if self.game_window.page_stack.currentWidget() is not self:
            return
        previous_round = self.current_snapshot["round_number"] if self.current_snapshot else 0
        previous_status = self.current_snapshot["status"] if self.current_snapshot else None
        self._refresh_battle_list()
        if self.current_battle_id is None:
            return
        self.load_battle_snapshot()
        if self.current_snapshot is None:
            return
        if self.current_snapshot["round_number"] > previous_round or self.current_snapshot["status"] != previous_status:
            self._handle_post_battle_updates()
            self._set_battle_status("Battle state updated.", "#63D471")


class ProfilePage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)

        layout = QVBoxLayout(self)
        layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero)
        self.username_label = QLabel("Profile")
        self.username_label.setObjectName("title")
        self.privacy_label = QLabel("Your public identity is your username. Private email and real name stay out of the player app.")
        self.privacy_label.setObjectName("subtitle")
        hero_layout.addWidget(self.username_label)
        hero_layout.addWidget(self.privacy_label)
        layout.addWidget(hero)

        summary = QFrame()
        summary.setObjectName("accentPanel")
        summary_layout = QVBoxLayout(summary)
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
        summary = inventory.get_inventory_summary(user["id"])
        trades = trading.list_user_trades(user["id"])
        open_trades = sum(1 for trade_row in trades if trade_row["status"] in {"pending", "open"})
        top_creatures = inventory.get_inventory(user["id"], sort_by="value")[:5]

        self.username_label.setText(user["username"])
        self.tokens_label.setText(f"Tokens: {user['tokens']}")
        self.collection_label.setText(f"Creatures: {summary['count']}")
        self.value_label.setText(f"Collection Value: {summary['total_value']}")
        self.rarity_label.setText(f"Highest Rarity: {summary['highest_rarity']}")
        self.trade_label.setText(f"Trade Activity: {open_trades}")

        self.top_list.clear()
        for creature in top_creatures:
            self.top_list.addItem(
                f"{creature['display_name']} | {creature['rarity']} | Lv {creature['level']} | Value {creature['value']}"
            )


class GameWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_user: dict | None = None
        self.seen_trade_notifications: set[int] = set()
        self.seen_battle_notifications: set[int] = set()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon(str(APP_ICON_PNG)))
        self.resize(1520, 940)

        self.presence_timer = QTimer(self)
        self.presence_timer.setInterval(15000)
        self.presence_timer.timeout.connect(self._heartbeat)

        self.notification_timer = QTimer(self)
        self.notification_timer.setInterval(3500)
        self.notification_timer.timeout.connect(self.check_notifications)

        self.root_stack = QStackedWidget()
        self.setCentralWidget(self.root_stack)

        self.auth_page = AuthPage()
        self.auth_page.authenticated.connect(self.set_current_user)
        self.root_stack.addWidget(self.auth_page)

        self.app_shell = QWidget()
        shell_layout = QHBoxLayout(self.app_shell)
        shell_layout.setContentsMargins(18, 18, 18, 18)
        shell_layout.setSpacing(18)

        sidebar = QFrame()
        sidebar.setObjectName("accentPanel")
        sidebar_layout = QVBoxLayout(sidebar)
        brand = QLabel(APP_TITLE)
        brand.setObjectName("sectionTitle")
        subtitle = QLabel("Player Game App")
        subtitle.setObjectName("subtitle")
        self.session_label = QLabel("Not signed in")
        self.session_label.setObjectName("statusBadge")
        self.balance_label = QLabel("Tokens: 0")
        self.balance_label.setObjectName("statusBadge")
        self.online_label = QLabel("Online Players: 0")
        self.online_label.setObjectName("statusBadge")
        self.notifications_label = QLabel("Requests: 0")
        self.notifications_label.setObjectName("statusBadge")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addWidget(self.session_label)
        sidebar_layout.addWidget(self.balance_label)
        sidebar_layout.addWidget(self.online_label)
        sidebar_layout.addWidget(self.notifications_label)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("dashboard", "Main Menu"),
            ("crate", "Crate Opening"),
            ("inventory", "Inventory"),
            ("trading", "Trading"),
            ("fighting", "Fighting"),
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
        shell_layout.addWidget(sidebar, 0)

        content_panel = QFrame()
        content_panel.setObjectName("panel")
        content_layout = QVBoxLayout(content_panel)
        self.page_stack = QStackedWidget()
        content_layout.addWidget(self.page_stack)
        shell_layout.addWidget(content_panel, 1)

        self.pages = {
            "dashboard": DashboardPage(self),
            "crate": CratePage(self),
            "inventory": InventoryPage(self),
            "trading": TradingPage(self),
            "fighting": FightingPage(self),
            "profile": ProfilePage(self),
        }
        for page in self.pages.values():
            self.page_stack.addWidget(page)

        self.root_stack.addWidget(self.app_shell)
        self.root_stack.setCurrentWidget(self.auth_page)

    def set_current_user(self, user: dict) -> None:
        self.seen_trade_notifications.clear()
        self.seen_battle_notifications.clear()
        self.current_user = database.get_user_by_id(user["id"])
        self.refresh_session()
        self.presence_timer.start()
        self.notification_timer.start()
        self.root_stack.setCurrentWidget(self.app_shell)
        self.navigate("dashboard")

    def refresh_session(self) -> None:
        if self.current_user is None:
            return
        database.touch_user_presence(self.current_user["id"])
        refreshed = database.get_user_by_id(self.current_user["id"])
        if refreshed is None:
            self.logout()
            return
        self.current_user = refreshed
        self.session_label.setText(f"Player: {self.current_user['username']}")
        self.balance_label.setText(f"Tokens: {self.current_user['tokens']}")
        online_count = len(database.list_online_users(self.current_user["id"]))
        incoming_trades = len(trading.list_incoming_trade_requests(self.current_user["id"]))
        incoming_battles = len(combat.list_incoming_battle_requests(self.current_user["id"]))
        self.online_label.setText(f"Online Players: {online_count}")
        self.notifications_label.setText(f"Requests: {incoming_trades + incoming_battles}")

    def navigate(self, key: str) -> None:
        if key not in self.pages:
            return
        self.refresh_session()
        self.page_stack.setCurrentWidget(self.pages[key])
        self.nav_buttons[key].setChecked(True)
        self.pages[key].refresh_page()
        apply_fade_in(self.pages[key])

    def logout(self) -> None:
        self.presence_timer.stop()
        self.notification_timer.stop()
        self.current_user = None
        self.root_stack.setCurrentWidget(self.auth_page)

    def _heartbeat(self) -> None:
        if self.current_user is None:
            return
        self.refresh_session()

    def check_notifications(self) -> None:
        if self.current_user is None or self.root_stack.currentWidget() is self.auth_page:
            return
        user_id = self.current_user["id"]
        self.refresh_session()

        for request in trading.list_incoming_trade_requests(user_id):
            if request["id"] in self.seen_trade_notifications:
                continue
            self.seen_trade_notifications.add(request["id"])
            self._handle_trade_request_popup(request)

        for request in combat.list_incoming_battle_requests(user_id):
            if request["id"] in self.seen_battle_notifications:
                continue
            self.seen_battle_notifications.add(request["id"])
            self._handle_battle_request_popup(request)

    def _handle_trade_request_popup(self, request: dict) -> None:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Trade Request")
        message_box.setText(f"{request['from_username']} sent you a trade request.")
        accept_button = message_box.addButton("Accept", QMessageBox.AcceptRole)
        decline_button = message_box.addButton("Decline", QMessageBox.RejectRole)
        later_button = message_box.addButton("Later", QMessageBox.ActionRole)
        message_box.exec_()

        clicked = message_box.clickedButton()
        if clicked is accept_button:
            try:
                snapshot = trading.accept_trade_request(request["id"], self.current_user["id"])
            except trading.TradeError:
                return
            self.pages["trading"].current_trade_id = snapshot["id"]
            self.pages["trading"].refresh_page()
        elif clicked is decline_button:
            try:
                trading.decline_trade_request(request["id"], self.current_user["id"])
            except trading.TradeError:
                return
            self.pages["trading"].refresh_page()
        else:
            self.pages["trading"].current_trade_id = request["id"]

    def _handle_battle_request_popup(self, request: dict) -> None:
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Battle Request")
        message_box.setText(f"{request['from_username']} challenged you to a PvP battle.")
        open_button = message_box.addButton("Open Fighting Tab", QMessageBox.AcceptRole)
        decline_button = message_box.addButton("Decline", QMessageBox.RejectRole)
        later_button = message_box.addButton("Later", QMessageBox.ActionRole)
        message_box.exec_()

        clicked = message_box.clickedButton()
        if clicked is decline_button:
            try:
                combat.cancel_battle(request["id"], self.current_user["id"])
            except combat.CombatError:
                return
            self.pages["fighting"].refresh_page()
            return
        self.pages["fighting"].current_battle_id = request["id"]
        if clicked is open_button:
            self.navigate("fighting")


def main() -> None:
    database.initialize_database()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    app.setWindowIcon(QIcon(str(APP_ICON_PNG)))
    window = GameWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
