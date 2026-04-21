
from __future__ import annotations
import sys
from functools import partial
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThreadPool
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import inventory
import auth
import database
import api
from config import ADMIN_PASSWORD, ADMIN_USERNAME, APP_ICON_PNG, APP_TITLE
from ui_shared import APP_STYLESHEET, apply_fade_in, with_alpha
from workers import Worker

from api import get_users

def set_status(label: QLabel, text: str, color: str) -> None:
    label.setText(text)
    label.setStyleSheet(f"color: {color}; font-weight: 600; padding: 6px 0px;")


class AdminAbusePage(QWidget):
    def __init__(self, main_window: "AdminWindow") -> None:
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 34, 34, 34)
        layout.setSpacing(18)

        header = QHBoxLayout()
        back_btn = QPushButton("← Back to Roster")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.main_window.show_panel)
        header.addWidget(back_btn)
        header.addStretch(1)
        layout.addLayout(header)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero)
        title = QLabel("Admin Abuse Panel")
        title.setObjectName("displayTitle")
        subtitle = QLabel("Global controls and chaotic admin tools. Use with caution.")
        subtitle.setObjectName("subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        layout.addWidget(hero)

        # Global Actions
        body = QHBoxLayout()
        body.setSpacing(18)

        actions_panel = QFrame()
        actions_panel.setObjectName("panel")
        actions_layout = QVBoxLayout(actions_panel)
        actions_title = QLabel("GLOBAL ABUSE")
        actions_title.setObjectName("sectionTitle")
        actions_layout.addWidget(actions_title)

        give_all_btn = QPushButton("Give Everyone 1000 Tokens")
        give_all_btn.setObjectName("successButton")
        give_all_btn.clicked.connect(lambda: self.global_abuse("give_all_tokens", 1000))
        
        ban_all_btn = QPushButton("Ban Everyone (Except Admin)")
        ban_all_btn.setObjectName("dangerButton")
        ban_all_btn.clicked.connect(lambda: self.global_abuse("ban_everyone"))
        
        unban_all_btn = QPushButton("Unban Everyone")
        unban_all_btn.setObjectName("secondaryButton")
        unban_all_btn.clicked.connect(lambda: self.global_abuse("unban_everyone"))

        self.announcement_input = QLineEdit()
        self.announcement_input.setPlaceholderText("Enter global announcement...")
        announce_btn = QPushButton("Send Global Announcement")
        announce_btn.clicked.connect(self.send_announcement)

        actions_layout.addWidget(give_all_btn)
        actions_layout.addWidget(ban_all_btn)
        actions_layout.addWidget(unban_all_btn)
        actions_layout.addWidget(self.announcement_input)
        actions_layout.addWidget(announce_btn)
        body.addWidget(actions_panel, 1)

        # Minigames
        games_panel = QFrame()
        games_panel.setObjectName("panel")
        games_layout = QVBoxLayout(games_panel)
        games_title = QLabel("ADMIN MINIGAMES")
        games_title.setObjectName("sectionTitle")
        games_layout.addWidget(games_title)

        chaos_btn = QPushButton("Token Chaos (Random for all)")
        chaos_btn.clicked.connect(lambda: self.global_abuse("token_chaos"))
        
        party_btn = QPushButton("Start Global Party XP")
        party_btn.setStyleSheet("background: #E91E63; color: white;")
        party_btn.clicked.connect(lambda: self.global_abuse("global_announcement", message="🎉 GLOBAL PARTY XP EVENT STARTED! 🎉"))

        # COOLER ABUSE
        extra_title = QLabel("EXTRA CHAOS")
        extra_title.setObjectName("sectionTitle")
        games_layout.addWidget(extra_title)

        nuke_btn = QPushButton("NUKE TOKENS (Everyone to 0)")
        nuke_btn.setObjectName("dangerButton")
        nuke_btn.clicked.connect(lambda: self.global_abuse("set_tokens", amount=0))

        games_layout.addWidget(chaos_btn)
        games_layout.addWidget(party_btn)
        games_layout.addWidget(nuke_btn)
        body.addWidget(games_panel, 1)
        
        layout.addLayout(body)
        layout.addStretch(1)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def global_abuse(self, action: str, amount: int = 0, message: str = "") -> None:
        worker = Worker(api.admin_abuse, action, None, amount, message)
        worker.signals.finished.connect(lambda payload: self._on_global_abuse_finished(action, payload))
        QThreadPool.globalInstance().start(worker)
        set_status(self.status_label, f"Executing '{action}'...", "#F2C14E")

    def send_announcement(self) -> None:
        msg = self.announcement_input.text().strip()
        if not msg: return
        self.announcement_input.clear()
        self.global_abuse("global_announcement", message=msg)

    def _on_global_abuse_finished(self, action: str, payload: dict) -> None:
        if isinstance(payload, dict) and payload.get("status") == "success":
            message = payload.get("message") or f"Abuse action '{action}' executed."
            set_status(self.status_label, message, "#63D471")
            return
        message = payload.get("message", f"Abuse action '{action}' failed.") if isinstance(payload, dict) else "Admin abuse request failed."
        set_status(self.status_label, message, "#F47C7C")


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)


class AdminLoginPage(QWidget):
    authenticated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 50, 60, 50)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(32, 32, 32, 32)

        title = QLabel("Admin Panel")
        title.setObjectName("title")
        subtitle = QLabel("Private fields and token controls live here only. Token updates work for registered players whether they are online or offline.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        form = QFormLayout()

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.status_label = QLabel()

        form.addRow("Admin Username", self.username_input)
        form.addRow("Admin Password", self.password_input)

        login_button = QPushButton("Log In")
        login_button.clicked.connect(self.handle_login)

        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)
        panel_layout.addLayout(form)
        panel_layout.addWidget(login_button)
        panel_layout.addWidget(self.status_label)
        layout.addStretch(1)
        layout.addWidget(panel, alignment=Qt.AlignCenter)
        layout.addStretch(1)

    def handle_login(self) -> None:
        if (
            self.username_input.text().strip() == ADMIN_USERNAME
            and self.password_input.text().strip() == ADMIN_PASSWORD
        ):
            set_status(self.status_label, "Admin login successful.", "#63D471")
            self.authenticated.emit()
            return
        set_status(self.status_label, "Invalid admin credentials.", "#F47C7C")


class AdminPlayerCard(QFrame):
    def __init__(
        self,
        player: dict,
        selected: bool,
        on_select,
        on_add_one,
        on_add_ten,
        on_kick,
        on_ban,
    ) -> None:
        super().__init__()
        is_banned = player.get("is_banned", False)
        accent = "#E14B4B" if is_banned else ("#63D471" if player["is_online"] else "#F2C14E")
        background = "#15263A" if selected else "#101824"
        border = accent if selected else with_alpha(accent, 155)
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {background};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        avatar = QLabel(player["username"][:1].upper())
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(46, 46)
        avatar.setStyleSheet(
            f"background: {with_alpha(accent, 80)}; border: 1px solid {with_alpha(accent, 190)}; "
            f"border-radius: 23px; color: {accent}; font-size: 18px; font-weight: 800;"
        )

        info_layout = QVBoxLayout()
        name = QLabel(player["username"])
        name.setStyleSheet("font-size: 17px; font-weight: 800;")
        status_text = "BANNED" if is_banned else ("Online" if player["is_online"] else "Offline")
        meta = QLabel(
            f"{status_text}  |  {player['tokens']} tokens  |  "
            f"{player['creature_count']} creature{'s' if player['creature_count'] != 1 else ''}"
        )
        meta.setStyleSheet(f"color: {accent}; font-weight: 700;")
        private_text = QLabel(f"{player['real_name']}  |  {player['email']}")
        private_text.setWordWrap(True)
        private_text.setStyleSheet("color: #AEBBD0;")
        info_layout.addWidget(name)
        info_layout.addWidget(meta)
        info_layout.addWidget(private_text)

        button_layout = QVBoxLayout()
        select_button = QPushButton("View")
        select_button.setObjectName("secondaryButton")
        select_button.clicked.connect(on_select)
        
        token_layout = QHBoxLayout()
        add_one_button = QPushButton("+1")
        add_one_button.setObjectName("successButton")
        add_one_button.clicked.connect(on_add_one)
        add_ten_button = QPushButton("+10")
        add_ten_button.setObjectName("successButton")
        add_ten_button.clicked.connect(on_add_ten)
        token_layout.addWidget(add_one_button)
        token_layout.addWidget(add_ten_button)

        mod_layout = QHBoxLayout()
        kick_button = QPushButton("Kick")
        kick_button.setObjectName("secondaryButton")
        kick_button.setStyleSheet("background: #F2C14E; color: black;")
        kick_button.clicked.connect(on_kick)
        ban_button = QPushButton("Unban" if is_banned else "Ban")
        ban_button.setObjectName("secondaryButton")
        ban_button.setStyleSheet(f"background: {'#63D471' if is_banned else '#E14B4B'}; color: white;")
        ban_button.clicked.connect(on_ban)
        
        mod_layout.addWidget(kick_button)
        mod_layout.addWidget(ban_button)

        button_layout.addWidget(select_button)
        button_layout.addLayout(token_layout)
        button_layout.addLayout(mod_layout)

        layout.addWidget(avatar)
        layout.addLayout(info_layout, 1)
        layout.addLayout(button_layout)


class AdminPanelPage(QWidget):
    def __init__(self, main_window: "AdminWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.current_user_id: int | None = None
        self._all_players: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(34, 34, 34, 34)
        root.setSpacing(18)

        header = QHBoxLayout()
        title = QLabel("Admin Player Roster")
        title.setObjectName("displayTitle")
        header.addWidget(title)
        header.addStretch(1)

        abuse_btn = QPushButton("Admin Abuse")
        abuse_btn.setObjectName("dangerButton")
        abuse_btn.clicked.connect(self.main_window.show_abuse_panel)
        header.addWidget(abuse_btn)

        logout_btn = QPushButton("Logout")
        logout_btn.setObjectName("secondaryButton")
        logout_btn.clicked.connect(self.main_window.logout)
        header.addWidget(logout_btn)
        root.addLayout(header)

        hero_panel = QFrame()
        hero_panel.setObjectName("heroPanel")
        hero_layout = QVBoxLayout(hero_panel)
        title = QLabel("Admin Roster")
        title.setObjectName("title")
        helper = QLabel(
            "Every player appears here whether they are online or offline. Use the quick token buttons to reward players instantly."
        )
        helper.setObjectName("subtitle")
        helper.setWordWrap(True)
        controls = QHBoxLayout()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter by username, real name, or email")
        self.filter_input.textChanged.connect(lambda _text: self._render_roster(refresh_details=False))
        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(lambda: self.refresh_roster(announce=True))
        logout_button = QPushButton("Log Out")
        logout_button.setObjectName("secondaryButton")
        logout_button.clicked.connect(self.main_window.logout)
        controls.addWidget(self.filter_input, 1)
        controls.addWidget(refresh_button)
        controls.addWidget(logout_button)
        self.roster_summary = QLabel("Loading players...")
        self.roster_summary.setObjectName("subtitle")
        self.status_label = QLabel("Choose a player from the list to inspect their private details and inventory.")
        self.status_label.setWordWrap(True)
        hero_layout.addWidget(title)
        hero_layout.addWidget(helper)
        hero_layout.addLayout(controls)
        hero_layout.addWidget(self.roster_summary)
        hero_layout.addWidget(self.status_label)
        root.addWidget(hero_panel)

        body = QHBoxLayout()

        roster_panel = QFrame()
        roster_panel.setObjectName("panel")
        roster_layout = QVBoxLayout(roster_panel)
        roster_title = QLabel("All Players")
        roster_title.setObjectName("sectionTitle")
        roster_hint = QLabel("Online players float to the top. New signups appear here automatically after refresh.")
        roster_hint.setObjectName("subtitle")
        roster_hint.setWordWrap(True)
        self.roster_scroll = QScrollArea()
        self.roster_scroll.setWidgetResizable(True)
        self.roster_container = QWidget()
        self.roster_list_layout = QVBoxLayout(self.roster_container)
        self.roster_list_layout.setSpacing(12)
        self.roster_list_layout.setAlignment(Qt.AlignTop)
        self.roster_scroll.setWidget(self.roster_container)
        roster_layout.addWidget(roster_title)
        roster_layout.addWidget(roster_hint)
        roster_layout.addWidget(self.roster_scroll)
        body.addWidget(roster_panel, 2)

        user_panel = QFrame()
        user_panel.setObjectName("panel")
        user_layout = QVBoxLayout(user_panel)
        details_title = QLabel("Player Details")
        details_title.setObjectName("sectionTitle")
        self.detail_hint = QLabel("Select a player to view everything the admin can see.")
        self.detail_hint.setWordWrap(True)
        self.username_label = QLabel("Username: -")
        self.presence_label = QLabel("Status: -")
        self.real_name_label = QLabel("Real Name: -")
        self.email_label = QLabel("Email: -")
        self.tokens_label = QLabel("Tokens: -")
        user_layout.addWidget(details_title)
        user_layout.addWidget(self.detail_hint)
        user_layout.addWidget(self.username_label)
        user_layout.addWidget(self.presence_label)
        user_layout.addWidget(self.real_name_label)
        user_layout.addWidget(self.email_label)
        user_layout.addWidget(self.tokens_label)
        quick_actions = QHBoxLayout()
        self.detail_add_one_button = QPushButton("Add 1 Token")
        self.detail_add_one_button.setObjectName("successButton")
        self.detail_add_one_button.clicked.connect(partial(self.adjust_selected_tokens, 1))
        self.detail_add_ten_button = QPushButton("Add 10 Tokens")
        self.detail_add_ten_button.clicked.connect(partial(self.adjust_selected_tokens, 10))
        quick_actions.addWidget(self.detail_add_one_button)
        quick_actions.addWidget(self.detail_add_ten_button)
        user_layout.addLayout(quick_actions)
        
        self.give_creature_button = QPushButton("Give Creature")
        self.give_creature_button.setObjectName("secondaryButton")
        self.give_creature_button.clicked.connect(self.give_creature_to_selected)
        user_layout.addWidget(self.give_creature_button)

        abuse_label = QLabel("QUICK ABUSE")
        abuse_label.setObjectName("sectionTitle")
        user_layout.addWidget(abuse_label)
        
        abuse_grid = QGridLayout()
        self.max_level_btn = QPushButton("Max Level")
        self.max_level_btn.setStyleSheet("background: #63D471; color: white;")
        self.max_level_btn.clicked.connect(lambda: self.player_abuse("max_level_creatures"))
        
        self.reset_inv_btn = QPushButton("Nuke Inv")
        self.reset_inv_btn.setStyleSheet("background: #E14B4B; color: white;")
        self.reset_inv_btn.clicked.connect(lambda: self.player_abuse("reset_creatures"))
        
        self.godly_set_btn = QPushButton("Godly Set")
        self.godly_set_btn.setStyleSheet("background: #F2C14E; color: black;")
        self.godly_set_btn.clicked.connect(lambda: self.player_abuse("give_godly_set"))
        
        self.chaos_mut_btn = QPushButton("Chaos Mut")
        self.chaos_mut_btn.setStyleSheet("background: #7B57D1; color: white;")
        self.chaos_mut_btn.clicked.connect(lambda: self.player_abuse("chaos_mutation"))
        
        self.reset_tokens_btn = QPushButton("Reset Tokens")
        self.reset_tokens_btn.setStyleSheet("background: #E14B4B; color: white;")
        self.reset_tokens_btn.clicked.connect(lambda: self.player_abuse("set_tokens", amount=0))
        
        abuse_grid.addWidget(self.max_level_btn, 0, 0)
        abuse_grid.addWidget(self.reset_inv_btn, 0, 1)
        abuse_grid.addWidget(self.godly_set_btn, 1, 0)
        abuse_grid.addWidget(self.chaos_mut_btn, 1, 1)
        abuse_grid.addWidget(self.reset_tokens_btn, 2, 0, 1, 2)
        user_layout.addLayout(abuse_grid)

        inventory_panel = QFrame()
        inventory_panel.setObjectName("accentPanel")
        inventory_layout = QVBoxLayout(inventory_panel)
        inventory_title = QLabel("Inventory")
        inventory_title.setObjectName("sectionTitle")
        self.inventory_box = QTextEdit()
        self.inventory_box.setReadOnly(True)
        inventory_layout.addWidget(inventory_title)
        inventory_layout.addWidget(self.inventory_box)
        user_layout.addWidget(inventory_panel, 1)
        body.addWidget(user_panel, 1)
        root.addLayout(body)
        self._set_detail_buttons_enabled(False)

    def activate(self) -> None:
        self.refresh_roster(announce=True)

    def deactivate(self) -> None:
        # This method is called on logout, but no specific cleanup is needed for the panel.
        pass

    def refresh_roster(self, announce: bool = False) -> None:
        worker = Worker(get_users)
        worker.signals.finished.connect(lambda users: self._on_roster_fetched(users, announce))
        QThreadPool.globalInstance().start(worker)

    def _on_roster_fetched(self, raw_users: list[dict], announce: bool) -> None:
        self._all_players = self._normalize_players(raw_users)
        self._render_roster(announce=announce)

    def _normalize_players(self, raw_users: list[dict]) -> list[dict]:
        players: list[dict] = []
        for user in raw_users:
            if not isinstance(user, dict) or user.get("username") is None:
                continue

            uid = user.get("id") or user.get("username")
            players.append({
                "id": uid,
                "username": user.get("username"),
                "real_name": user.get("real_name") or "",
                "email": user.get("email") or "",
                "tokens": int(user.get("tokens", 0) or 0),
                "is_online": bool(user.get("online", False) or user.get("is_online", False)),
                "is_banned": bool(user.get("is_banned", False)),
                "creature_count": int(user.get("creature_count", 0)),
            })
        return players

    def _filtered_players(self) -> list[dict]:
        players = list(self._all_players)

        query = self.filter_input.text().strip().lower()
        if query:
            players = [
                player
                for player in players
                if query in player["username"].lower()
                or query in player["real_name"].lower()
                or query in player["email"].lower()
            ]
        return players

    def _find_player(self, players: list[dict], identifier: int | str | None) -> dict | None:
        if identifier is None:
            return None
        for player in players:
            if player.get("id") == identifier:
                return player
        identifier_text = str(identifier).strip().lower()
        for player in players:
            username = str(player.get("username", "")).strip().lower()
            if username == identifier_text:
                return player
        return None

    def _render_roster(self, announce: bool = False, refresh_details: bool = True) -> None:
        players = self._filtered_players()

        online_count = sum(1 for player in players if player["is_online"])
        self.roster_summary.setText(
            f"{len(players)} player{'s' if len(players) != 1 else ''} shown  |  "
            f"{online_count} online"
        )

        clear_layout(self.roster_list_layout)
        if not players:
            empty = QLabel("No players match the current filter yet. If you just created an account, press Refresh and it should appear here.")
            empty.setWordWrap(True)
            empty.setObjectName("subtitle")
            self.roster_list_layout.addWidget(empty)
            self.current_user_id = None
            self._clear_user_display()
            set_status(self.status_label, "No matching players to display.", "#F2C14E")
            return

        selected_player = self._find_player(players, self.current_user_id)
        if selected_player is None:
            self.current_user_id = players[0]["id"]
            selected_player = players[0]

        for player in players:
            card = AdminPlayerCard(
                player=player,
                selected=player["id"] == self.current_user_id,
                on_select=partial(self.select_user, player["id"]),
                on_add_one=partial(self.adjust_tokens, player["id"], 1),
                on_add_ten=partial(self.adjust_tokens, player["id"], 10),
                on_kick=partial(self.kick_user, player["id"]),
                on_ban=partial(self.toggle_ban, player["id"], not player["is_banned"]),
            )
            self.roster_list_layout.addWidget(card)
        self.roster_list_layout.addStretch(1)
        if selected_player is not None and refresh_details:
            self._render_user(selected_player)
        if announce:
            set_status(self.status_label, "Player roster refreshed.", "#63D471")

    def kick_user(self, user_id: int) -> None:
        worker = Worker(api.kick_user, user_id)
        worker.signals.finished.connect(lambda success: self._on_simple_admin_action(success, "Player kicked.", "Could not kick player."))
        QThreadPool.globalInstance().start(worker)
        set_status(self.status_label, f"Kicking user {user_id}...", "#F2C14E")

    def toggle_ban(self, user_id: int, should_ban: bool) -> None:
        worker = Worker(api.ban_user, user_id, should_ban)
        worker.signals.finished.connect(
            lambda success: self._on_simple_admin_action(
                success,
                "Player banned." if should_ban else "Player unbanned.",
                "Could not update ban status.",
            )
        )
        QThreadPool.globalInstance().start(worker)
        action = "Banning" if should_ban else "Unbanning"
        set_status(self.status_label, f"{action} user {user_id}...", "#E14B4B")

    def select_user(self, user_id: int) -> None:
        self.current_user_id = user_id
        self._render_roster(refresh_details=True)
        set_status(self.status_label, "Player selected.", "#63D471")

    def refresh_current_user(self, silent: bool = False) -> None:
        if self.current_user_id is None:
            self._clear_user_display()
            return
        worker = Worker(get_users)
        worker.signals.finished.connect(lambda users: self._on_current_user_fetched(users, silent))
        QThreadPool.globalInstance().start(worker)

    def _on_current_user_fetched(self, raw_users: list[dict], silent: bool) -> None:
        if self.current_user_id is None:
            self._clear_user_display()
            return

        players = self._normalize_players(raw_users)
        user_meta = self._find_player(players, self.current_user_id)
        if user_meta is None:
            self.current_user_id = None
            self._clear_user_display()
            set_status(self.status_label, "That player no longer exists.", "#F47C7C")
            return

        self._all_players = players
        self.current_user_id = user_meta["id"]
        self._render_user(user_meta)
        if not silent:
            set_status(self.status_label, "Player details updated.", "#63D471")

    def _clear_user_display(self) -> None:
        self.username_label.setText("Username: -")
        self.presence_label.setText("Status: -")
        self.presence_label.setStyleSheet("")
        self.real_name_label.setText("Real Name: -")
        self.email_label.setText("Email: -")
        self.tokens_label.setText("Tokens: -")
        self.inventory_box.clear()
        self.detail_hint.setText("Select a player to view everything the admin can see.")
        self._set_detail_buttons_enabled(False)

    def _render_user(self, user: dict) -> None:
        online = bool(user.get("is_online", False))
        banned = bool(user.get("is_banned", False))
        self.username_label.setText(f"Username: {user.get('username', '-')}")
        status_text = "Banned" if banned else ("Online" if online else "Offline")
        status_color = "#E14B4B" if banned else ("#63D471" if online else "#F2C14E")
        self.presence_label.setText(f"Status: {status_text}")
        self.presence_label.setStyleSheet(
            f"color: {status_color}; font-weight: 700;"
        )
        self.real_name_label.setText(f"Real Name: {user.get('real_name', '-')}")
        self.email_label.setText(f"Email: {user.get('email', '-')}")
        self.tokens_label.setText(f"Tokens: {user.get('tokens', 0)}")
        self.inventory_box.setPlainText(inventory.admin_inventory_text(user.get("id")))
        self.detail_hint.setText("Private identity fields stay here in the admin app only.")
        self._set_detail_buttons_enabled(True)

    def _set_detail_buttons_enabled(self, enabled: bool) -> None:
        self.detail_add_one_button.setEnabled(enabled)
        self.detail_add_ten_button.setEnabled(enabled)
        self.give_creature_button.setEnabled(enabled)
        self.max_level_btn.setEnabled(enabled)
        self.reset_inv_btn.setEnabled(enabled)
        self.godly_set_btn.setEnabled(enabled)
        self.chaos_mut_btn.setEnabled(enabled)
        self.reset_tokens_btn.setEnabled(enabled)

    def player_abuse(self, action: str, amount: int = 0) -> None:
        if self.current_user_id is None: return
        worker = Worker(api.admin_abuse, action, self.current_user_id, amount, "")
        worker.signals.finished.connect(lambda payload: self._on_player_abuse_finished(action, payload))
        QThreadPool.globalInstance().start(worker)
        set_status(self.status_label, f"Executing '{action}' on user...", "#F2C14E")

    def adjust_selected_tokens(self, delta: int) -> None:
        if self.current_user_id is None:
            return
        self.adjust_tokens(self.current_user_id, delta)

    def adjust_tokens(self, user_id: int | str, delta: int) -> None:
        worker = Worker(api.add_tokens, user_id, delta)
        worker.signals.finished.connect(
            lambda success: self._on_simple_admin_action(
                success,
                "Token balance updated.",
                "Could not update tokens.",
            )
        )
        QThreadPool.globalInstance().start(worker)
        set_status(self.status_label, f"Adjusting tokens for user {user_id}...", "#F2C14E")

    def _on_tokens_adjusted(self, payload: dict | None) -> None:
        if not payload or payload.get("status") != "success":
            QMessageBox.warning(self, "Error", "Could not adjust tokens.")
            return
        self.refresh_roster()
        set_status(
            self.status_label,
            "Token balance updated.",
            "#63D471",
        )

    def give_creature_to_selected(self) -> None:
        if self.current_user_id is None:
            return
            
        from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QSpinBox, QDialogButtonBox, QComboBox
        from config import CREATURE_CATALOG, RARITY_ORDER, RARITY_CREATURES
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Give Creature")
        layout = QFormLayout(dialog)
        
        # Improved dropdown for creature selection
        creature_dropdown = QComboBox()
        # Sort creatures by rarity then name
        all_creatures = []
        for rarity in RARITY_ORDER:
            for name, theme in RARITY_CREATURES[rarity]:
                all_creatures.append(f"{name} ({rarity})")
        creature_dropdown.addItems(all_creatures)
        layout.addRow("Select Creature:", creature_dropdown)
        
        level_input = QSpinBox()
        level_input.setRange(1, 100)
        level_input.setValue(1)
        layout.addRow("Level:", level_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            selected_text = creature_dropdown.currentText()
            creature_name = selected_text.split(" (")[0]
            level = level_input.value()
            
            worker = Worker(api.admin_give_creature, self.current_user_id, creature_name, level)
            worker.signals.finished.connect(self._on_creature_given)
            QThreadPool.globalInstance().start(worker)
            set_status(self.status_label, f"Giving {creature_name} to user...", "#F2C14E")

    def _on_creature_given(self, res) -> None:
        if isinstance(res, dict) and res.get("status") == "success":
            set_status(self.status_label, "Creature given successfully!", "#63D471")
            self.refresh_current_user()
        else:
            msg = res.get("message", "Failed to give creature.") if isinstance(res, dict) else "Error"
            set_status(self.status_label, msg, "#F47C7C")

    def _on_simple_admin_action(self, success: bool, success_message: str, error_message: str) -> None:
        if success:
            self.refresh_roster()
            self.refresh_current_user(silent=True)
            set_status(self.status_label, success_message, "#63D471")
            return
        set_status(self.status_label, error_message, "#F47C7C")

    def _on_player_abuse_finished(self, action: str, payload: dict) -> None:
        if isinstance(payload, dict) and payload.get("status") == "success":
            self.refresh_roster()
            self.refresh_current_user(silent=True)
            message = payload.get("message") or f"Executed '{action}'."
            set_status(self.status_label, message, "#63D471")
            return
        message = payload.get("message", f"Could not execute '{action}'.") if isinstance(payload, dict) else "Admin abuse request failed."
        set_status(self.status_label, message, "#F47C7C")


class AdminWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        from config import APP_VERSION
        self.setWindowTitle(f"{APP_TITLE} Admin v{APP_VERSION}")
        self.setWindowIcon(QIcon(str(APP_ICON_PNG)))
        self.resize(1100, 760)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_page = AdminLoginPage()
        self.login_page.authenticated.connect(self.show_panel)
        self.stack.addWidget(self.login_page)

        self.panel_page = AdminPanelPage(self)
        self.stack.addWidget(self.panel_page)

        self.abuse_page = AdminAbusePage(self)
        self.stack.addWidget(self.abuse_page)

    def show_panel(self) -> None:
        self.stack.setCurrentWidget(self.panel_page)
        self.panel_page.activate()
        apply_fade_in(self.panel_page)

    def show_abuse_panel(self) -> None:
        self.stack.setCurrentWidget(self.abuse_page)
        apply_fade_in(self.abuse_page)

    def logout(self) -> None:
        self.panel_page.deactivate()
        self.stack.setCurrentWidget(self.login_page)
        apply_fade_in(self.login_page)


def main() -> None:
    # Diagnostic for Windows bundling issues
    if getattr(sys, 'frozen', False):
        print(f"[INFO] Running in bundled mode. Temp path: {getattr(sys, '_MEIPASS', 'N/A')}")
        
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    app.setWindowIcon(QIcon(str(APP_ICON_PNG)))
    window = AdminWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
