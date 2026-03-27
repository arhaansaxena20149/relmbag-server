from __future__ import annotations
import sys
from functools import partial
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThreadPool
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
    QDialog,
)

import auth
import crate_system
import database
import inventory
import api
from config import APP_ICON_PNG, APP_SUBTITLE, APP_TITLE, BASE_VALUES, CRATE_COST, DROP_RATES, RARITY_COLORS, RARITY_ORDER, CREATURES_BY_RARITY
from ui_shared import APP_STYLESHEET, apply_fade_in, load_pixmap, with_alpha
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
        self.setFixedWidth(180)
        self.setFixedHeight(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        rarity_color = creature["rarity_color"]
        
        # Level Badge
        level = QLabel(f"Lv {creature['level']}")
        level.setStyleSheet(
            f"background: {with_alpha(rarity_color, 200)}; color: #1A120B; "
            "border-radius: 4px; padding: 2px 6px; font-weight: 800; font-size: 11px;"
        )
        layout.addWidget(level, 0, Qt.AlignRight)

        # Image
        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        image.setPixmap(load_pixmap(creature["image_path"], 100))
        image.setStyleSheet(
            f"background: {with_alpha(rarity_color, 30)}; "
            f"border: 2px solid {with_alpha(rarity_color, 100)}; border-radius: 10px;"
        )
        layout.addWidget(image, 1)

        # Name
        name = QLabel(creature["display_name"])
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {rarity_color};")
        layout.addWidget(name)

        # Rarity
        rarity = QLabel(creature["rarity"])
        rarity.setAlignment(Qt.AlignCenter)
        rarity.setStyleSheet(f"color: {with_alpha(rarity_color, 180)}; font-size: 11px; font-weight: 700;")
        layout.addWidget(rarity)

        # Stats
        stats = QLabel(f"ATK {creature['stats']['Attack']} | DEF {creature['stats']['Defense']}")
        stats.setAlignment(Qt.AlignCenter)
        stats.setStyleSheet("color: #C19A6B; font-size: 10px;")
        layout.addWidget(stats)

        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        color = self.creature["rarity_color"]
        if selected:
            self.setStyleSheet(
                f"background: #3E2C1C; border: 3px solid {color}; border-radius: 12px;"
            )
        else:
            self.setStyleSheet(
                f"background: #1A120B; border: 2px solid #4E3B24; border-radius: 12px;"
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
        chance.setStyleSheet("font-weight: 700;")
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


class AuthPage(QWidget):
    authenticated = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        
        # Background or Overlay
        self.bg = QFrame(self)
        self.bg.setObjectName("heroPanel")
        self.bg.setStyleSheet("border-radius: 0px; border: none;")
        outer.addWidget(self.bg)
        
        card_container = QVBoxLayout(self.bg)
        card_container.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("parchmentPanel")
        card.setFixedSize(500, 650)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(20)

        title = QLabel("RELMBAG ARENA")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 48px; color: #2D1F16; text-shadow: none;")
        
        subtitle = QLabel("THE GREAT SUMMONING")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #8B5E3C; font-weight: 800; letter-spacing: 2px;")

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #C19A6B; background: transparent; }
            QTabBar::tab { background: #EAD2AC; color: #8B5E3C; padding: 10px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; font-weight: 800; }
            QTabBar::tab:selected { background: #F4E4BC; color: #2D1F16; border-bottom: 2px solid #F4E4BC; }
        """)
        tabs.addTab(self._build_login_tab(), "LOGIN")
        tabs.addTab(self._build_signup_tab(), "SIGN UP")

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background: #C19A6B;")
        card_layout.addWidget(line)
        
        card_layout.addWidget(tabs)
        card_container.addWidget(card)

    def _build_login_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(15)

        self.login_identifier = QLineEdit()
        self.login_identifier.setPlaceholderText("Username or Email")
        self.login_identifier.setStyleSheet("background: #F4E4BC; color: #2D1F16; border-color: #C19A6B;")
        
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Password")
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.setStyleSheet("background: #F4E4BC; color: #2D1F16; border-color: #C19A6B;")
        
        self.login_status = QLabel()
        self.login_status.setAlignment(Qt.AlignCenter)

        login_button = QPushButton("ENTER THE ARENA")
        login_button.clicked.connect(self.handle_login)

        layout.addWidget(QLabel("<b>IDENTIFIER</b>"))
        layout.addWidget(self.login_identifier)
        layout.addWidget(QLabel("<b>PASSWORD</b>"))
        layout.addWidget(self.login_password)
        layout.addWidget(login_button)
        layout.addWidget(self.login_status)
        layout.addStretch()
        return widget

    def _build_signup_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(10)

        self.signup_email = QLineEdit()
        self.signup_real_name = QLineEdit()
        self.signup_username = QLineEdit()
        self.signup_password = QLineEdit()
        self.signup_password.setEchoMode(QLineEdit.Password)
        
        for field in [self.signup_email, self.signup_real_name, self.signup_username, self.signup_password]:
            field.setStyleSheet("background: #F4E4BC; color: #2D1F16; border-color: #C19A6B;")

        self.signup_status = QLabel()
        self.signup_status.setAlignment(Qt.AlignCenter)

        signup_button = QPushButton("CLAIM YOUR TITLE")
        signup_button.clicked.connect(self.handle_signup)

        layout.addWidget(QLabel("<b>EMAIL</b>"))
        layout.addWidget(self.signup_email)
        layout.addWidget(QLabel("<b>FULL NAME</b>"))
        layout.addWidget(self.signup_real_name)
        layout.addWidget(QLabel("<b>USERNAME</b>"))
        layout.addWidget(self.signup_username)
        layout.addWidget(QLabel("<b>PASSWORD</b>"))
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
        layout.setContentsMargins(40, 40, 40, 40)

        # Welcome Portal
        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(40, 40, 40, 40)
        
        self.welcome_label = QLabel("Welcome back, Traveler")
        self.welcome_label.setObjectName("title")
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
            button.clicked.connect(partial(self.game_window.navigate, page_key))
            buttons.addWidget(button, index // 2, index % 2)
        quick_layout.addLayout(buttons)
        layout.addWidget(quick_panel)
        layout.addStretch(1)

    def _stat_card(self, heading: str, value: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("accentPanel")
        card.setFixedHeight(120)
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignCenter)
        
        label = QLabel(heading)
        label.setStyleSheet("color: #C19A6B; font-weight: 800; font-size: 12px; letter-spacing: 1px;")
        label.setAlignment(Qt.AlignCenter)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 32px; font-weight: 800; color: #F4E4BC;")
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
        
        self.consecutive_button = QPushButton("Consecutive Open")
        self.consecutive_button.setObjectName("secondaryButton")
        self.consecutive_button.clicked.connect(self.show_consecutive_dialog)
        
        self.auto_sell_combo = QComboBox()
        self.auto_sell_combo.addItems(["Auto Sell: None"] + [f"Auto Sell: {r}" for r in RARITY_ORDER[:5]]) # Up to Legendary
        self.auto_sell_combo.setFixedWidth(200)
        
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.open_button)
        btn_row.addWidget(self.consecutive_button)
        btn_row.addWidget(self.auto_sell_combo)
        btn_row.addStretch()
        
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addLayout(badge_row)
        hero_layout.addWidget(self.feedback_label)
        
        # Daily Reward Section
        self.daily_reward_panel = QFrame()
        self.daily_reward_panel.setObjectName("accentPanel")
        self.daily_reward_panel.setStyleSheet("background: #F4E4BC; border: 1px solid #C19A6B; border-radius: 10px;")
        daily_layout = QHBoxLayout(self.daily_reward_panel)
        daily_layout.setContentsMargins(15, 10, 15, 10)
        
        self.daily_status_label = QLabel("Daily Reward: Available!")
        self.daily_status_label.setStyleSheet("font-weight: 800; color: #2D1F16;")
        self.claim_daily_btn = QPushButton("Claim Daily")
        self.claim_daily_btn.setObjectName("secondaryButton")
        self.claim_daily_btn.clicked.connect(self.claim_daily_reward)
        
        daily_layout.addWidget(self.daily_status_label)
        daily_layout.addStretch()
        daily_layout.addWidget(self.claim_daily_btn)
        
        hero_layout.addWidget(self.daily_reward_panel)
        hero_layout.addLayout(btn_row)
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

    def claim_daily_reward(self) -> None:
        user = self.game_window.current_user
        if not user: return
        
        self.claim_daily_btn.setEnabled(False)
        worker = Worker(api.safe_request, "post", "claim_daily", json={"user_id": user.get("id")})
        worker.signals.finished.connect(self._on_daily_claimed)
        worker.signals.error.connect(lambda e: self._on_daily_error(str(e)))
        QThreadPool.globalInstance().start(worker)

    def _on_daily_claimed(self, res) -> None:
        if isinstance(res, dict) and res.get("status") == "success":
            earned = res.get("tokens_earned", 0)
            streak = res.get("new_streak", 1)
            self.daily_status_label.setText(f"Claimed {earned} tokens! Day {streak} Streak.")
            self.daily_status_label.setStyleSheet("font-weight: 800; color: #63D471;")
            self.game_window.refresh_session()
        else:
            msg = res.get("message", "Error claiming reward") if isinstance(res, dict) else "Error"
            self.daily_status_label.setText(msg)
            self.daily_status_label.setStyleSheet("font-weight: 800; color: #F47C7C;")

    def _on_daily_error(self, err: str) -> None:
        self.daily_status_label.setText("Already claimed today!")
        self.daily_status_label.setStyleSheet("font-weight: 800; color: #F47C7C;")

    def open_crate(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        if user["tokens"] < CRATE_COST:
            status_message(self.feedback_label, "Not enough tokens.", "#F47C7C")
            return
        self.roll_ticks = 0
        self.open_button.setEnabled(False)
        self.consecutive_button.setEnabled(False)
        status_message(self.feedback_label, "Crate spinning up...", "#F2C14E")
        self.roll_timer.start(80)

    def _advance_roll_animation(self) -> None:
        self.roll_ticks += 1
        
        # Shuffle through random creatures
        all_creatures = []
        for rarity_list in CREATURES_BY_RARITY.values():
            all_creatures.extend(rarity_list)
        
        random_creature = random.choice(all_creatures)
        self.result_image.setPixmap(load_pixmap("", 180)) # Clear while shuffling or show blurred?
        self.result_name.setText(random_creature["name"])
        self.result_name.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {RARITY_COLORS[random_creature['rarity']]};")
        self.result_rarity.setText(random_creature["rarity"])
        self.result_rarity.setStyleSheet(rarity_badge_stylesheet(RARITY_COLORS[random_creature['rarity']]))

        if self.roll_ticks >= 15:
            self.roll_timer.stop()
            self.open_button.setEnabled(True)
            self.consecutive_button.setEnabled(True)
            self._finish_roll()

    def show_consecutive_dialog(self) -> None:
        from PyQt5.QtWidgets import QInputDialog
        user = self.game_window.current_user
        if not user: return
        
        max_possible = user["tokens"] // CRATE_COST
        if max_possible <= 0:
            show_error(self, "Not enough tokens for even one crate!")
            return
            
        count, ok = QInputDialog.getInt(self, "Consecutive Open", "How many crates to open?", 1, 1, min(max_possible, 100), 1)
        if ok:
            self._run_consecutive_open(count)

    def _run_consecutive_open(self, count: int) -> None:
        user = self.game_window.current_user
        if not user: return
        
        status_message(self.feedback_label, f"Opening {count} crates...", "#F2C14E")
        self.open_button.setEnabled(False)
        self.consecutive_button.setEnabled(False)
        
        auto_sell_idx = self.auto_sell_combo.currentIndex()
        auto_sell_rarity = None
        if auto_sell_idx > 0:
            auto_sell_rarity = RARITY_ORDER[auto_sell_idx - 1]

        def _bulk_open(username: str, n: int, sell_rarity: str | None):
            results = []
            for _ in range(n):
                res = crate_system.open_crate(username)
                if sell_rarity and res.get("creature", {}).get("rarity") == sell_rarity:
                    # Auto-sell logic
                    creature_id = res["creature"]["id"]
                    sell_res = api.safe_request("post", "sell_creature", json={"user_id": username, "creature_id": creature_id})
                    res["auto_sold"] = True
                results.append(res)
            return results

        worker = Worker(_bulk_open, user.get("username"), count, auto_sell_rarity)
        worker.signals.finished.connect(self._on_bulk_opened)
        worker.signals.error.connect(lambda e: self._on_bulk_error(str(e)))
        QThreadPool.globalInstance().start(worker)

    def _on_bulk_opened(self, results: list) -> None:
        self.open_button.setEnabled(True)
        self.consecutive_button.setEnabled(True)
        self.game_window.refresh_session()
        
        if not results: return
        
        # Show summary of bulk open
        last_res = results[-1]
        self._on_crate_opened(last_res)
        
        rarity_counts = {}
        total_tokens_back = 0
        sold_count = 0
        for r in results:
            rarity = r.get("creature", {}).get("rarity", "Unknown")
            rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
            if r.get("auto_sold"):
                sold_count += 1
        
        summary = ", ".join([f"{count} {rarity}" for rarity, count in rarity_counts.items()])
        msg = f"Opened {len(results)} crates: {summary}."
        if sold_count > 0:
            msg += f" (Auto-sold {sold_count} creatures)"
            
        status_message(self.feedback_label, msg, "#63D471")
        
        self.game_window.pages["inventory"].refresh_page()

    def _on_bulk_error(self, err: str) -> None:
        self.open_button.setEnabled(True)
        self.consecutive_button.setEnabled(True)
        status_message(self.feedback_label, err, "#F47C7C")

    def _finish_roll(self) -> None:
        user = self.game_window.current_user
        if not user:
            return
        
        # FIX: Move network call to worker thread to prevent UI freeze
        worker = Worker(crate_system.open_crate, user.get("username"))
        worker.signals.finished.connect(self._on_crate_opened)
        worker.signals.error.connect(lambda e: status_message(self.feedback_label, str(e), "#F47C7C"))
        QThreadPool.globalInstance().start(worker)

    def _on_crate_opened(self, result: dict) -> None:
        try:
            if not isinstance(result, dict) or not self.isVisible():
                return
            
            creature = result.get("creature")
            if not creature:
                return

            self.game_window.refresh_session()
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
            status_message(self.feedback_label, "Crate opened successfully.", "#63D471")
            self.game_window.pages["inventory"].refresh_page()
            self.game_window.pages["dashboard"].refresh_page()
            self.game_window.pages["profile"].refresh_page()
        except RuntimeError:
            pass


class InventoryPage(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        self.current_cards: dict[int, CreatureCard] = {}
        self.current_creatures: dict[int, dict] = {}
        self.selected_creature_id: int | None = None

        root = QHBoxLayout(self)
        root.setSpacing(25)
        root.setContentsMargins(20, 20, 20, 20)

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
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Rarity", "Value", "Level"])
        self.sort_combo.currentTextChanged.connect(self.refresh_page)
        self.filter_combo = QComboBox()
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
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(25, 25, 25, 25)
        detail_layout.setSpacing(15)

        self.detail_image = QLabel()
        self.detail_image.setAlignment(Qt.AlignCenter)
        self.detail_image.setFixedSize(200, 200)
        self.detail_image.setStyleSheet("background: rgba(0,0,0,0.05); border-radius: 15px;")
        
        self.detail_name = QLabel("Select a Creature")
        self.detail_name.setAlignment(Qt.AlignCenter)
        self.detail_name.setStyleSheet("font-size: 28px; font-weight: 800; color: #2D1F16;")
        
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
        
        self.sell_button = QPushButton("Sell for 50% Value")
        self.sell_button.setObjectName("secondaryButton")
        self.sell_button.setStyleSheet("background: #E14B4B; color: white; font-weight: 800; padding: 10px;")
        self.sell_button.clicked.connect(self.sell_selected_creature)
        self.sell_button.setVisible(False)
        detail_layout.addWidget(self.sell_button)
        
        detail_layout.addWidget(self.detail_value)

        root.addWidget(self.detail_panel, 2)

    def refresh_page(self) -> None:
        user = self.game_window.current_user
        if user is None:
            return
        
        sort_map = {"Rarity": "rarity", "Value": "value", "Level": "level"}
        rarity_filter = self.filter_combo.currentText()
        selected_filter = None if rarity_filter == "All Rarities" else rarity_filter
        
        worker = Worker(
            inventory.get_inventory,
            user.get("username"),
            sort_by=sort_map.get(self.sort_combo.currentText(), "rarity"),
            rarity_filter=selected_filter
        )
        worker.signals.finished.connect(self._on_inventory_fetched)
        QThreadPool.globalInstance().start(worker)

    def _on_inventory_fetched(self, creatures: list[dict]) -> None:
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
            return

        self.sell_button.setVisible(True)
        for card_id, card in self.current_cards.items():
            card.set_selected(card_id == creature_id)

        self.detail_image.setPixmap(load_pixmap(creature["image_path"], 180))
        self.detail_name.setText(creature["display_name"])
        self.detail_name.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {creature['rarity_color']};")
        
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
            worker = Worker(api.safe_request, "post", "sell_creature", json={
                "user_id": self.game_window.current_user.get("username"),
                "creature_id": self.selected_creature_id
            })
            worker.signals.finished.connect(self._on_sold)
            QThreadPool.globalInstance().start(worker)

    def _on_sold(self, res) -> None:
        self.game_window.refresh_session()
        self.refresh_page()
        status_message(self.inventory_summary, "Creature sold successfully.", "#63D471")


class TradingLobby(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        layout = QVBoxLayout(self)
        layout.setSpacing(25)
        layout.setContentsMargins(40, 40, 40, 40)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("Trading Hall")
        title.setObjectName("title")
        subtitle = QLabel("Choose an online player to initiate a secure creature trade.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        selection_panel = QFrame()
        selection_panel.setObjectName("panel")
        sel_layout = QVBoxLayout(selection_panel)
        sel_layout.setContentsMargins(30, 30, 30, 30)
        sel_layout.setSpacing(20)

        sel_layout.addWidget(QLabel("<b>SELECT TRADING PARTNER</b>"))
        self.player_dropdown = QComboBox()
        self.player_dropdown.setPlaceholderText("Scanning for online players...")
        sel_layout.addWidget(self.player_dropdown)

        self.send_request_button = QPushButton("Send Trade Request")
        self.send_request_button.clicked.connect(self.initiate_trade)
        sel_layout.addWidget(self.send_request_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        sel_layout.addWidget(self.status_label)
        
        layout.addWidget(selection_panel)
        layout.addStretch()

    def refresh_page(self) -> None:
        worker = Worker(get_users)
        worker.signals.finished.connect(self._on_users_fetched)
        QThreadPool.globalInstance().start(worker)

    def _on_users_fetched(self, users: list[dict]) -> None:
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
            print(f"[ERROR] TradingLobby data refresh failed: {e}")

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
            status_message(self.status_label, "Request sent! Waiting for acceptance...", "#63D471")


class FightingLobby(BasePage):
    def __init__(self, game_window: "GameWindow") -> None:
        super().__init__(game_window)
        layout = QVBoxLayout(self)
        layout.setSpacing(25)
        layout.setContentsMargins(40, 40, 40, 40)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel("Battle Arena")
        title.setObjectName("title")
        subtitle = QLabel("Challenge a rival to a tactical creature duel.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        selection_panel = QFrame()
        selection_panel.setObjectName("panel")
        sel_layout = QVBoxLayout(selection_panel)
        sel_layout.setContentsMargins(30, 30, 30, 30)
        sel_layout.setSpacing(20)

        sel_layout.addWidget(QLabel("<b>CHOOSE YOUR CHAMPION</b>"))
        self.creature_dropdown = QComboBox()
        sel_layout.addWidget(self.creature_dropdown)

        sel_layout.addWidget(QLabel("<b>SELECT OPPONENT</b>"))
        self.player_dropdown = QComboBox()
        self.player_dropdown.setPlaceholderText("Scanning for rivals...")
        sel_layout.addWidget(self.player_dropdown)

        self.send_request_button = QPushButton("Issue Challenge")
        self.send_request_button.clicked.connect(self.initiate_battle)
        sel_layout.addWidget(self.send_request_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        sel_layout.addWidget(self.status_label)
        
        layout.addWidget(selection_panel)
        
        # Pending Challenges Section
        pending_panel = QFrame()
        pending_panel.setObjectName("panel")
        pending_layout = QVBoxLayout(pending_panel)
        pending_layout.setContentsMargins(30, 30, 30, 30)
        pending_layout.setSpacing(10)
        
        pending_title = QLabel("<b>PENDING CHALLENGES</b>")
        pending_layout.addWidget(pending_title)
        
        self.pending_list = QListWidget()
        self.pending_list.setFixedHeight(180)
        self.pending_list.itemDoubleClicked.connect(self._on_pending_clicked)
        pending_layout.addWidget(self.pending_list)
        
        layout.addWidget(pending_panel)
        layout.addStretch()

    def refresh_page(self) -> None:
        def _get_lobby_data(username: str, user_id: int):
            users = get_users()
            creatures = inventory.get_inventory(username, sort_by="rarity")
            pending_battles = api.list_incoming_battle_requests(user_id)
            return users, creatures, pending_battles

        worker = Worker(_get_lobby_data, self.game_window.current_user.get("username"), self.game_window.current_user.get("id"))
        worker.signals.finished.connect(self._on_data_fetched)
        QThreadPool.globalInstance().start(worker)

    def _on_data_fetched(self, data: tuple) -> None:
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
            print(f"[ERROR] FightingLobby data refresh failed: {e}")

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
            status_message(self.status_label, "Challenge issued! Waiting for acceptance...", "#63D471")


class BattleRequestDialog(QDialog):
    def __init__(self, parent: "GameWindow", request: dict) -> None:
        super().__init__(parent)
        self.game_window = parent
        self.request = request
        self.setWindowTitle("Battle Challenge")
        self.setFixedWidth(400)
        self.setStyleSheet(APP_STYLESHEET)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"⚔️ <b>{request['from_username']}</b> has challenged you!"))
        layout.addWidget(QLabel("Select your defender:"))
        
        self.creature_combo = QComboBox()
        self.creature_combo.addItem("Fetching creatures...")
        self.creature_combo.setEnabled(False)
        layout.addWidget(self.creature_combo)
        
        btns = QHBoxLayout()
        self.fight_btn = QPushButton("FIGHT")
        self.fight_btn.setEnabled(False)
        self.decline_btn = QPushButton("DECLINE")
        btns.addWidget(self.fight_btn)
        btns.addWidget(self.decline_btn)
        layout.addLayout(btns)
        
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
        self.setFixedSize(1000, 750)
        self.setModal(True)
        
        # Apply global style to dialog
        self.setStyleSheet(APP_STYLESHEET)
        
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        # Header Area (Stone-like)
        header = QFrame()
        header.setObjectName("heroPanel")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 15, 20, 15)
        self.title_label = QLabel("Active Trade")
        self.title_label.setObjectName("title")
        self.title_label.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        self.close_btn = QPushButton("CANCEL TRADE")
        self.close_btn.setObjectName("dangerButton")
        self.close_btn.clicked.connect(self.cancel_trade)
        header_layout.addWidget(self.close_btn)
        root.addWidget(header)
        
        # Main Body (Parchment-like)
        body = QFrame()
        body.setObjectName("parchmentPanel")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(25, 25, 25, 25)
        body_layout.setSpacing(25)
        
        # Left: Your Offer
        left_side = QVBoxLayout()
        left_side.addWidget(QLabel("<b>YOUR OFFER</b>"))
        self.your_creatures_list = QListWidget()
        left_side.addWidget(self.your_creatures_list)
        
        self.your_token_spin = QSpinBox()
        self.your_token_spin.setMaximum(99999999) # Set a high limit
        self.your_token_spin.setPrefix("Tokens: ")
        self.your_token_spin.valueChanged.connect(self.update_token_offer)
        left_side.addWidget(self.your_token_spin)
        
        self.confirm_btn = QPushButton("CONFIRM OFFER")
        self.confirm_btn.clicked.connect(self.confirm_trade)
        left_side.addWidget(self.confirm_btn)
        body_layout.addLayout(left_side, 1)
        
        # Middle: Inventory to Add
        mid_side = QVBoxLayout()
        mid_side.addWidget(QLabel("<b>YOUR COLLECTION</b>"))
        self.inventory_list = QListWidget()
        mid_side.addWidget(self.inventory_list)
        self.add_btn = QPushButton("ADD SELECTED")
        self.add_btn.clicked.connect(self.add_creature)
        mid_side.addWidget(self.add_btn)
        self.remove_btn = QPushButton("REMOVE SELECTED")
        self.remove_btn.clicked.connect(self.remove_creature)
        mid_side.addWidget(self.remove_btn)
        body_layout.addLayout(mid_side, 1)
        
        # Right: Their Offer
        right_side = QVBoxLayout()
        right_side.addWidget(QLabel("<b>THEIR OFFER</b>"))
        self.their_creatures_list = QListWidget()
        right_side.addWidget(self.their_creatures_list)
        self.their_token_label = QLabel("Tokens: 0")
        right_side.addWidget(self.their_token_label)
        
        self.status_msg = QLabel("Waiting for confirmation...")
        self.status_msg.setAlignment(Qt.AlignCenter)
        self.status_msg.setStyleSheet("font-style: italic; color: #4E3B24;")
        right_side.addWidget(self.status_msg)
        body_layout.addLayout(right_side, 1)
        
        root.addWidget(body)
        
        # Polling Timer
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_trade)
        self.poll_timer.start(2000)
        
        self.refresh_trade()

    def refresh_trade(self) -> None:
        if not self.game_window.current_user: return
        def _get_trade_data(trade_id: int, user_id: int, username: str):
            snapshot = api.get_trade(trade_id, user_id)
            user_inventory = inventory.get_inventory(username, sort_by="rarity")
            return snapshot, user_inventory

        worker = Worker(_get_trade_data, self.trade_id, self.game_window.current_user['id'], self.game_window.current_user['username'])
        worker.signals.finished.connect(self._on_data_fetched)
        QThreadPool.globalInstance().start(worker)

    def _on_data_fetched(self, data: tuple) -> None:
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
            self.confirm_btn.setText("OFFER LOCKED")
            self.confirm_btn.setEnabled(False)
            self.add_btn.setEnabled(False)
            self.remove_btn.setEnabled(False)
            self.your_token_spin.setEnabled(False)
        else:
            self.confirm_btn.setText("CONFIRM OFFER")
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
        self.setStyleSheet(APP_STYLESHEET)
        
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        # Header Area
        header = QFrame()
        header.setObjectName("heroPanel")
        header_layout = QHBoxLayout(header)
        self.title_label = QLabel("Battle Initiated")
        self.title_label.setObjectName("title")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        self.forfeit_btn = QPushButton("FORFEIT")
        self.forfeit_btn.setObjectName("dangerButton")
        self.forfeit_btn.clicked.connect(self.forfeit_battle)
        header_layout.addWidget(self.forfeit_btn)
        root.addWidget(header)
        
        # Arena Area
        arena = QFrame()
        arena.setObjectName("panel")
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
        
        root.addWidget(arena, 2)
        
        # Moves & Log
        bottom = QHBoxLayout()
        bottom.setContentsMargins(20, 20, 20, 20)
        bottom.setSpacing(20)
        
        # Moves
        moves_frame = QFrame()
        moves_frame.setObjectName("parchmentPanel")
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
        log_layout = QVBoxLayout(log_frame)
        log_layout.addWidget(QLabel("<b>BATTLE CHRONICLE</b>"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background: #1A120B; color: #AEBBD0; border: none;")
        log_layout.addWidget(self.log_box)
        bottom.addWidget(log_frame, 1)
        
        root.addLayout(bottom, 1)
        
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.refresh_battle)
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
        if not self.game_window.current_user: return
        worker = Worker(api.get_battle, self.battle_id, self.game_window.current_user['id'])
        worker.signals.finished.connect(self._on_snapshot_fetched)
        QThreadPool.globalInstance().start(worker)

    def _on_snapshot_fetched(self, snapshot: dict) -> None:
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
        
        title = QLabel("Global Leaderboards")
        title.setObjectName("title")
        layout.addWidget(title)
        
        body = QHBoxLayout()
        
        # Tokens Leaderboard
        tokens_panel = QFrame()
        tokens_panel.setObjectName("panel")
        tokens_layout = QVBoxLayout(tokens_panel)
        tokens_layout.addWidget(QLabel("<b>TOP TOKENS</b>"))
        self.tokens_list = QListWidget()
        tokens_layout.addWidget(self.tokens_list)
        body.addWidget(tokens_panel)
        
        # Creatures Leaderboard
        creatures_panel = QFrame()
        creatures_panel.setObjectName("panel")
        creatures_layout = QVBoxLayout(creatures_panel)
        creatures_layout.addWidget(QLabel("<b>TOP CREATURE COUNTS</b>"))
        self.creatures_list = QListWidget()
        creatures_layout.addWidget(self.creatures_list)
        body.addWidget(creatures_panel)
        
        layout.addLayout(body)
        
        refresh_btn = QPushButton("Refresh Leaderboards")
        refresh_btn.clicked.connect(self.refresh_page)
        layout.addWidget(refresh_btn)

    def refresh_page(self) -> None:
        worker = Worker(api.safe_request, "get", "leaderboard")
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
        
        title = QLabel("Player Search")
        title.setObjectName("title")
        layout.addWidget(title)
        
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter username or email...")
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.search_player)
        search_row.addWidget(self.search_input)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)
        
        self.results_panel = QFrame()
        self.results_panel.setObjectName("panel")
        self.results_layout = QVBoxLayout(self.results_panel)
        self.results_panel.setVisible(False)
        
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("font-size: 16px; font-weight: 800;")
        self.creatures_list = QListWidget()
        
        self.results_layout.addWidget(self.stats_label)
        self.results_layout.addWidget(QLabel("<b>CREATURES</b>"))
        self.results_layout.addWidget(self.creatures_list)
        
        layout.addWidget(self.results_panel)
        layout.addStretch()

    def search_player(self) -> None:
        query = self.search_input.text().strip()
        if not query: return
        
        worker = Worker(api.safe_request, "get", f"player_stats/{query}")
        worker.signals.finished.connect(self._on_search_result)
        QThreadPool.globalInstance().start(worker)

    def _on_search_result(self, data: dict) -> None:
        if not isinstance(data, dict) or data.get("status") == "error":
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
        layout = QVBoxLayout(self)
        
        title = QLabel("Global Chat")
        title.setObjectName("title")
        layout.addWidget(title)
        
        self.chat_display = QListWidget()
        self.chat_display.setStyleSheet("background: #F4E4BC; color: #2D1F16;")
        layout.addWidget(self.chat_display)
        
        input_row = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.returnPressed.connect(self.send_message)
        send_btn = QPushButton("Send")
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
        worker = Worker(api.safe_request, "get", "chat")
        worker.signals.finished.connect(self._on_chat_fetched)
        QThreadPool.globalInstance().start(worker)

    def _on_chat_fetched(self, data: list) -> None:
        if not isinstance(data, list): return
        
        # Only update if new messages
        if self.chat_display.count() == len(data): return
        
        self.chat_display.clear()
        for msg in reversed(data): # Show newest at bottom
            item = f"[{msg['created_at'][11:16]}] {msg['username']}: {msg['message']}"
            self.chat_display.addItem(item)
        self.chat_display.scrollToBottom()

    def send_message(self) -> None:
        text = self.message_input.text().strip()
        if not text: return
        
        self.message_input.clear()
        worker = Worker(api.safe_request, "post", "chat", json={
            "user_id": self.game_window.current_user.get("id"),
            "message": text
        })
        worker.signals.finished.connect(self.refresh_page)
        QThreadPool.globalInstance().start(worker)


class GameWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_user: dict | None = None
        self.seen_trade_notifications: set[int] = set()
        self.seen_battle_notifications: set[int] = set()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon(str(APP_ICON_PNG)))
        self.resize(1520, 940)

        # FIX: Replace unreliable presence_timer with HeartbeatWorker
        self.heartbeat_worker = None
        self.last_battle_statuses: dict[int, str] = {}
        self.last_trade_statuses: dict[int, str] = {}

        self.notification_timer = QTimer(self)
        self.notification_timer.setInterval(10000)
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
            ("leaderboard", "Leaderboard"),
            ("search", "Player Search"),
            ("chat", "Chat"),
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

    def set_current_user(self, user: dict) -> None:
        self.seen_trade_notifications.clear()
        self.seen_battle_notifications.clear()
        self.current_user = user
        
        # FIX: Use HeartbeatWorker
        if self.heartbeat_worker:
            self.heartbeat_worker.stop()
        self.heartbeat_worker = HeartbeatWorker(self.current_user["username"], self.current_user.get("session_token"))
        self.heartbeat_worker.kicked.connect(self.logout)
        self.heartbeat_worker.banned.connect(self.logout)
        self.heartbeat_worker.start()

        self.refresh_session()
        self.notification_timer.start()
        self.root_stack.setCurrentWidget(self.app_shell)
        self.navigate("dashboard")

    def refresh_session(self) -> None:
        if self.current_user is None:
            return

        # FIX: Move network calls to a worker thread
        worker = Worker(get_users)
        worker.signals.finished.connect(self._on_session_refreshed)
        QThreadPool.globalInstance().start(worker)

    def _on_session_refreshed(self, users: list[dict]) -> None:
        if self.current_user is None:
            return

        if not users:
            print("[DEBUG] User list is empty, skipping session refresh.")
            return

        username = str(self.current_user.get("username", "")).strip().lower()
        user_meta = next((u for u in users if str(u.get("username", "")).strip().lower() == username), None)

        if user_meta is None:
            # Skip update if user is not in the current online list snapshot
            return

        if user_meta.get("is_banned"):
            print(f"[DEBUG] User {username} is banned, logging out.")
            QMessageBox.critical(self, "Banned", "Your account has been banned.")
            self.logout()
            return

        self.current_user["tokens"] = int(user_meta.get("tokens", self.current_user.get("tokens", 0)) or 0)
        self.current_user["real_name"] = user_meta.get("real_name", self.current_user.get("real_name", ""))
        self.current_user["email"] = user_meta.get("email", self.current_user.get("email", ""))
        if "id" in user_meta and user_meta["id"]:
            self.current_user["id"] = user_meta["id"]

        self.session_label.setText(f"Player: {self.current_user['username']}")
        self.balance_label.setText(f"Tokens: {self.current_user['tokens']}")

        online_count = sum(1 for u in users if u.get("is_online"))

        try:
            id_to_check = self.current_user.get("id")
            print(f"[DEBUG] Refreshing session for {self.current_user.get('username')} (ID: {id_to_check})")
            incoming_trades = len(api.list_incoming_trade_requests(id_to_check))
        except Exception as e:
            print(f"[ERROR] Failed to list incoming trades: {e}")
            incoming_trades = 0
        try:
            incoming_battles = len(api.list_incoming_battle_requests(id_to_check))
        except Exception as e:
            print(f"[ERROR] Failed to list incoming battles: {e}")
            incoming_battles = 0

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
        if self.heartbeat_worker:
            self.heartbeat_worker.stop()
            self.heartbeat_worker = None
        self.notification_timer.stop()
        self.current_user = None
        self.root_stack.setCurrentWidget(self.auth_page)

    def check_notifications(self) -> None:
        if self.current_user is None or self.root_stack.currentWidget() is self.auth_page:
            return
        
        user_id = self.current_user.get("id")
        
        # FIX: Also trigger a refresh on the active page if it's trading or fighting
        # This ensures that both players see status changes (e.g., when a request is accepted)
        current_page = self.page_stack.currentWidget()
        if current_page in (self.pages.get("trading"), self.pages.get("fighting")):
            current_page.refresh_page()
        
        # FIX: Move notification fetching to a worker thread
        def fetch_notifications(uid: int):
            incoming_trades = api.list_incoming_trade_requests(uid)
            incoming_battles = api.list_incoming_battle_requests(uid)
            
            # Fetch full lists to detect status changes for outgoing requests
            all_trades = api.list_user_trades(uid)
            all_battles = api.list_user_battles(uid)
            
            return incoming_trades, incoming_battles, all_trades, all_battles

        worker = Worker(fetch_notifications, user_id)
        worker.signals.finished.connect(self._on_notifications_fetched)
        QThreadPool.globalInstance().start(worker)
        
        # We still call refresh_session separately as it updates the sidebar
        self.refresh_session()

    def _on_notifications_fetched(self, data: tuple) -> None:
        if self.current_user is None or not isinstance(data, tuple) or len(data) != 4:
            return
            
        incoming_trades, incoming_battles, all_trades, all_battles = data
        
        # 1. Handle NEW incoming requests
        for request in incoming_trades:
            if request.get("id") in self.seen_trade_notifications:
                continue
            self.seen_trade_notifications.add(request.get("id"))
            self._handle_trade_request_popup(request)

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
