from __future__ import annotations

import sys
from functools import partial

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
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

import database
import inventory
from config import ADMIN_PASSWORD, ADMIN_USERNAME, APP_ICON_PNG, APP_TITLE
from ui_shared import APP_STYLESHEET, apply_fade_in, with_alpha


def set_status(label: QLabel, text: str, color: str) -> None:
    label.setText(text)
    label.setStyleSheet(f"color: {color}; font-weight: 600; padding: 6px 0px;")


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
    ) -> None:
        super().__init__()
        accent = "#63D471" if player["is_online"] else "#F2C14E"
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
        status_text = "Online" if player["is_online"] else "Offline"
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
        add_one_button = QPushButton("+1 Token")
        add_one_button.setObjectName("successButton")
        add_one_button.clicked.connect(on_add_one)
        add_ten_button = QPushButton("+10 Tokens")
        add_ten_button.clicked.connect(on_add_ten)
        button_layout.addWidget(select_button)
        button_layout.addWidget(add_one_button)
        button_layout.addWidget(add_ten_button)

        layout.addWidget(avatar)
        layout.addLayout(info_layout, 1)
        layout.addLayout(button_layout)


class AdminPanelPage(QWidget):
    def __init__(self, main_window: "AdminWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self.current_user_id: int | None = None
        self.roster_timer = QTimer(self)
        self.roster_timer.setInterval(3000)
        self.roster_timer.timeout.connect(lambda: self.refresh_roster())

        root = QVBoxLayout(self)
        root.setSpacing(18)

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
        self.filter_input.textChanged.connect(lambda _text: self.refresh_roster())
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
        if not self.roster_timer.isActive():
            self.roster_timer.start()

    def deactivate(self) -> None:
        self.roster_timer.stop()

    def refresh_roster(self, announce: bool = False) -> None:
        players = database.list_admin_players()
        query = self.filter_input.text().strip().lower()
        if query:
            players = [
                player
                for player in players
                if query in player["username"].lower()
                or query in player["real_name"].lower()
                or query in player["email"].lower()
            ]

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

        current_ids = {player["id"] for player in players}
        if self.current_user_id not in current_ids:
            self.current_user_id = players[0]["id"]

        for player in players:
            card = AdminPlayerCard(
                player=player,
                selected=player["id"] == self.current_user_id,
                on_select=partial(self.select_user, player["id"]),
                on_add_one=partial(self.adjust_tokens, player["id"], 1),
                on_add_ten=partial(self.adjust_tokens, player["id"], 10),
            )
            self.roster_list_layout.addWidget(card)
        self.roster_list_layout.addStretch(1)
        self.refresh_current_user(silent=True)
        if announce:
            set_status(self.status_label, "Player roster refreshed.", "#63D471")

    def select_user(self, user_id: int) -> None:
        self.current_user_id = user_id
        self.refresh_roster()
        set_status(self.status_label, "Player selected.", "#63D471")

    def refresh_current_user(self, silent: bool = False) -> None:
        if self.current_user_id is None:
            self._clear_user_display()
            return
        user = database.get_user_by_id(self.current_user_id)
        if user is None:
            self.current_user_id = None
            self._clear_user_display()
            set_status(self.status_label, "That player no longer exists.", "#F47C7C")
            return
        self._render_user(user)
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
        online = database.is_user_online(user["id"])
        self.username_label.setText(f"Username: {user['username']}")
        self.presence_label.setText(f"Status: {'Online' if online else 'Offline'}")
        self.presence_label.setStyleSheet(
            f"color: {'#63D471' if online else '#F2C14E'}; font-weight: 700;"
        )
        self.real_name_label.setText(f"Real Name: {user['real_name']}")
        self.email_label.setText(f"Email: {user['email']}")
        self.tokens_label.setText(f"Tokens: {user['tokens']}")
        self.inventory_box.setPlainText(inventory.admin_inventory_text(user["id"]))
        self.detail_hint.setText("Private identity fields stay here in the admin app only.")
        self._set_detail_buttons_enabled(True)

    def _set_detail_buttons_enabled(self, enabled: bool) -> None:
        self.detail_add_one_button.setEnabled(enabled)
        self.detail_add_ten_button.setEnabled(enabled)

    def adjust_selected_tokens(self, delta: int) -> None:
        if self.current_user_id is None:
            QMessageBox.warning(self, APP_TITLE, "Select a player first.")
            return
        self.adjust_tokens(self.current_user_id, delta)

    def adjust_tokens(self, user_id: int, delta: int) -> None:
        try:
            new_balance = database.adjust_user_tokens(user_id, delta)
        except ValueError as error:
            QMessageBox.warning(self, APP_TITLE, str(error))
            return
        self.current_user_id = user_id
        self.refresh_roster()
        set_status(
            self.status_label,
            f"Added {delta} token{'s' if delta != 1 else ''}. New balance: {new_balance}.",
            "#63D471",
        )


class AdminWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} - Admin Panel")
        self.setWindowIcon(QIcon(str(APP_ICON_PNG)))
        self.resize(1100, 760)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_page = AdminLoginPage()
        self.login_page.authenticated.connect(self.show_panel)
        self.stack.addWidget(self.login_page)

        self.panel_page = AdminPanelPage(self)
        self.stack.addWidget(self.panel_page)

    def show_panel(self) -> None:
        self.stack.setCurrentWidget(self.panel_page)
        self.panel_page.activate()
        apply_fade_in(self.panel_page)

    def logout(self) -> None:
        self.panel_page.deactivate()
        self.stack.setCurrentWidget(self.login_page)
        apply_fade_in(self.login_page)


def main() -> None:
    database.initialize_database()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    app.setWindowIcon(QIcon(str(APP_ICON_PNG)))
    window = AdminWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
