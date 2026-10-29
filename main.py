import sys
import os
import json
from pathlib import Path
from urllib.parse import quote, urlparse

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QMessageBox,
    QInputDialog,
    QLabel,
    QMenu,
    QDialog,
    QListWidget,
    QProgressBar,
    QAbstractItemView,
)
from PySide6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineDownloadRequest,
)
from PySide6.QtWebEngineWidgets import QWebEngineView


# ==================================================
# ZOHRAN BROWSER 3.0
# ==================================================

APP_NAME = "ZOHRAN Browser 3.0"

DATA_DIR = Path.home() / "ZohranBrowserData"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BOOKMARKS_FILE = DATA_DIR / "bookmarks.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

DOWNLOADS_FOLDER = Path.home() / "Downloads"
DOWNLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

HOME_URL = "https://www.google.com/?hl=en"


# ==================================================
# THEMES
# ==================================================

THEMES = {
    "Purple Galaxy": {
        "background": "#171324",
        "panel": "#241d38",
        "button": "#7546c8",
        "text": "#ffffff",
        "border": "#493665",
    },
    "Ocean Blue": {
        "background": "#101c2c",
        "panel": "#192c43",
        "button": "#167ac6",
        "text": "#ffffff",
        "border": "#315475",
    },
    "Emerald Green": {
        "background": "#10251e",
        "panel": "#19382c",
        "button": "#23865b",
        "text": "#ffffff",
        "border": "#32694e",
    },
    "Sunset Orange": {
        "background": "#2a1b18",
        "panel": "#422821",
        "button": "#d86b35",
        "text": "#ffffff",
        "border": "#70432f",
    },
    "Pink Dream": {
        "background": "#291b2a",
        "panel": "#422942",
        "button": "#c34f9a",
        "text": "#ffffff",
        "border": "#70466c",
    },
}


# ==================================================
# FILE HELPERS
# ==================================================

def read_json(path, default):
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
    except (OSError, json.JSONDecodeError):
        pass

    return default


def write_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
    except OSError as error:
        print("Could not save:", error)


def safe_filename(name):
    invalid = '<>:"/\\|?*'

    for character in invalid:
        name = name.replace(character, "_")

    name = name.strip().rstrip(".")

    return name or "download"


# ==================================================
# DOWNLOADS WINDOW
# ==================================================

class DownloadsManager(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("ZOHRAN Downloads")
        self.resize(700, 450)

        self.setModal(False)

        layout = QVBoxLayout(self)

        title = QLabel("📥 ZOHRAN Downloads")
        title.setStyleSheet(
            "font-size: 23px; font-weight: bold; padding: 8px;"
        )
        layout.addWidget(title)

        description = QLabel(
            "Files downloaded from websites appear here."
        )
        layout.addWidget(description)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        layout.addWidget(self.file_list)

        self.open_file_button = QPushButton("📄 Open Selected File")
        self.open_file_button.clicked.connect(self.open_selected_file)
        layout.addWidget(self.open_file_button)

        self.open_folder_button = QPushButton(
            "📂 Open Windows Downloads Folder"
        )
        self.open_folder_button.clicked.connect(
            self.open_download_folder
        )
        layout.addWidget(self.open_folder_button)

        self.clear_button = QPushButton("Clear Download List")
        self.clear_button.clicked.connect(self.clear_list)
        layout.addWidget(self.clear_button)

        self.download_rows = {}

    def add_download(self, filename, path):
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(6, 6, 6, 6)

        name_label = QLabel(filename)
        name_label.setWordWrap(True)

        status_label = QLabel("Waiting for download...")

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)

        row_layout.addWidget(name_label)
        row_layout.addWidget(status_label)
        row_layout.addWidget(progress)

        from PySide6.QtWidgets import QListWidgetItem

        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        self.file_list.addItem(item)
        self.file_list.setItemWidget(item, row)

        index = self.file_list.count() - 1

        self.download_rows[index] = {
            "item": item,
            "name": name_label,
            "status": status_label,
            "progress": progress,
            "path": path,
        }

        return index

    def update_download(self, index, message, percent=None):
        row = self.download_rows.get(index)

        if not row:
            return

        row["status"].setText(message)

        if percent is not None:
            row["progress"].setValue(
                max(0, min(100, int(percent)))
            )

    def open_selected_file(self):
        index = self.file_list.currentRow()

        if index < 0:
            QMessageBox.information(
                self,
                "Select a File",
                "Select a download first."
            )
            return

        row = self.download_rows.get(index)

        if not row:
            return

        path = Path(row["path"])

        if path.exists():
            os.startfile(str(path))
        else:
            QMessageBox.warning(
                self,
                "File Not Found",
                "This file has not finished downloading or no longer exists."
            )

    def open_download_folder(self):
        os.startfile(str(DOWNLOADS_FOLDER))

    def clear_list(self):
        self.file_list.clear()
        self.download_rows.clear()


# ==================================================
# MAIN BROWSER
# ==================================================

class ZohranBrowser(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.resize(1300, 850)

        self.bookmarks = read_json(BOOKMARKS_FILE, [])

        if not isinstance(self.bookmarks, list):
            self.bookmarks = []

        self.settings = read_json(
            SETTINGS_FILE,
            {"theme": "Purple Galaxy", "profile": "Default"},
        )

        self.current_theme = self.settings.get(
            "theme", "Purple Galaxy"
        )

        if self.current_theme not in THEMES:
            self.current_theme = "Purple Galaxy"

        self.current_profile_name = self.settings.get(
            "profile", "Default"
        )

        self.profiles = {}
        self.active_downloads = []

        self.downloads_manager = DownloadsManager(self)

        self.create_profile(self.current_profile_name)

        self.build_interface()
        self.create_shortcuts()
        self.apply_theme()

        self.new_tab(HOME_URL)

    # ==================================================
    # PROFILES
    # ==================================================

    def create_profile(self, name):
        if name in self.profiles:
            return self.profiles[name]

        folder_name = safe_filename(name)

        profile_folder = (
            DATA_DIR / "profiles" / folder_name
        )

        profile_folder.mkdir(parents=True, exist_ok=True)

        profile = QWebEngineProfile(name, self)

        profile.setPersistentStoragePath(
            str(profile_folder / "storage")
        )

        profile.setCachePath(
            str(profile_folder / "cache")
        )

        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy
            .AllowPersistentCookies
        )

        profile.downloadRequested.connect(
            self.handle_download
        )

        self.profiles[name] = profile

        return profile

    def current_profile(self):
        return self.profiles[self.current_profile_name]

    def create_new_profile(self):
        name, accepted = QInputDialog.getText(
            self,
            "Create Profile",
            "Enter a name for the new profile:",
        )

        if not accepted or not name.strip():
            return

        name = name.strip()

        if name in self.profiles:
            QMessageBox.information(
                self,
                "Profile Exists",
                "A profile with that name already exists."
            )
            return

        self.create_profile(name)
        self.switch_profile(name)

    def switch_profile(self, name):
        if name not in self.profiles:
            self.create_profile(name)

        self.current_profile_name = name
        self.update_profile_label()
        self.new_tab(HOME_URL)
        self.save_settings()

    def update_profile_label(self):
        if hasattr(self, "profile_label"):
            self.profile_label.setText(
                "Profile: " + self.current_profile_name
            )

    # ==================================================
    # INTERFACE
    # ==================================================

    def build_interface(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 9, 12, 9)

        self.logo = QLabel("◈ ZOHRAN")
        self.logo.setStyleSheet(
            "font-size: 23px; font-weight: bold;"
        )

        self.version_label = QLabel("BROWSER 3.0")

        self.profile_label = QLabel()

        self.profile_button = QPushButton("👤 Profile")
        self.profile_button.clicked.connect(
            self.show_profile_menu
        )

        self.theme_button = QPushButton("🎨 Themes")
        self.theme_button.clicked.connect(
            self.show_theme_menu
        )

        self.fullscreen_button = QPushButton("⛶ Fullscreen")
        self.fullscreen_button.clicked.connect(
            self.toggle_fullscreen
        )

        header_layout.addWidget(self.logo)
        header_layout.addWidget(self.version_label)
        header_layout.addStretch()
        header_layout.addWidget(self.profile_label)
        header_layout.addWidget(self.profile_button)
        header_layout.addWidget(self.theme_button)
        header_layout.addWidget(self.fullscreen_button)

        main_layout.addWidget(header)

        # Navigation
        navigation = QHBoxLayout()
        navigation.setContentsMargins(10, 5, 10, 8)
        navigation.setSpacing(6)

        self.back_button = QPushButton("←")
        self.back_button.setToolTip("Back")
        self.back_button.clicked.connect(self.go_back)

        self.forward_button = QPushButton("→")
        self.forward_button.setToolTip("Forward")
        self.forward_button.clicked.connect(self.go_forward)

        self.reload_button = QPushButton("⟳")
        self.reload_button.setToolTip("Reload")
        self.reload_button.clicked.connect(self.reload_page)

        self.home_button = QPushButton("⌂")
        self.home_button.setToolTip("Home")
        self.home_button.clicked.connect(
            lambda: self.navigate(HOME_URL)
        )

        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText(
            "Search Google or enter a website..."
        )
        self.address_bar.returnPressed.connect(
            self.navigate_from_bar
        )

        self.bookmark_button = QPushButton("☆")
        self.bookmark_button.setToolTip("Bookmark page")
        self.bookmark_button.clicked.connect(self.add_bookmark)

        self.bookmarks_button = QPushButton("★ Bookmarks")
        self.bookmarks_button.clicked.connect(self.show_bookmarks)

        self.downloads_button = QPushButton("📥 Downloads")
        self.downloads_button.clicked.connect(self.show_downloads)

        self.menu_button = QPushButton("☰")
        self.menu_button.clicked.connect(self.show_browser_menu)

        navigation.addWidget(self.back_button)
        navigation.addWidget(self.forward_button)
        navigation.addWidget(self.reload_button)
        navigation.addWidget(self.home_button)
        navigation.addWidget(self.address_bar, 1)
        navigation.addWidget(self.bookmark_button)
        navigation.addWidget(self.bookmarks_button)
        navigation.addWidget(self.downloads_button)
        navigation.addWidget(self.menu_button)

        main_layout.addLayout(navigation)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)

        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_address_bar)

        main_layout.addWidget(self.tabs, 1)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.setContentsMargins(10, 5, 10, 8)

        self.new_tab_button = QPushButton("+ New Tab")
        self.new_tab_button.clicked.connect(
            lambda: self.new_tab(HOME_URL)
        )

        self.status_label = QLabel("Ready to browse")

        bottom.addWidget(self.new_tab_button)
        bottom.addStretch()
        bottom.addWidget(self.status_label)

        main_layout.addLayout(bottom)

        self.update_profile_label()

    # ==================================================
    # SHORTCUTS
    # ==================================================

    def create_shortcuts(self):
        shortcuts = [
            ("Ctrl+T", lambda: self.new_tab(HOME_URL)),
            ("Ctrl+W", self.close_current_tab),
            ("Ctrl+L", self.focus_address_bar),
            ("Ctrl+R", self.reload_page),
            ("F11", self.toggle_fullscreen),
            ("Ctrl+J", self.show_downloads),
        ]

        for key, function in shortcuts:
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(function)
            self.addAction(action)

    # ==================================================
    # TABS
    # ==================================================

    def new_tab(self, url=None):
        if not isinstance(url, str):
            url = HOME_URL

        browser = QWebEngineView()

        page = QWebEnginePage(
            self.current_profile(),
            browser
        )

        browser.setPage(page)

        index = self.tabs.addTab(browser, "New Tab")
        self.tabs.setCurrentIndex(index)

        browser.urlChanged.connect(
            lambda changed_url, view=browser:
            self.update_address_for_page(view, changed_url)
        )

        browser.titleChanged.connect(
            lambda title, view=browser:
            self.update_tab_title(view, title)
        )

        browser.loadStarted.connect(
            lambda view=browser: self.show_loading(view)
        )

        browser.loadFinished.connect(
            lambda success, view=browser:
            self.page_finished(view, success)
        )

        browser.setUrl(QUrl(url))

        return browser

    def current_browser(self):
        return self.tabs.currentWidget()

    def navigate(self, text):
        browser = self.current_browser()

        if not browser:
            return

        text = text.strip()

        if not text:
            return

        if text.startswith(("http://", "https://")):
            url = text

        elif " " in text:
            url = (
                "https://www.google.com/search?hl=en&q="
                + quote(text)
            )

        elif "." in text:
            url = "https://" + text

        else:
            url = (
                "https://www.google.com/search?hl=en&q="
                + quote(text)
            )

        browser.setUrl(QUrl(url))

    def navigate_from_bar(self):
        self.navigate(self.address_bar.text())

    def go_back(self):
        browser = self.current_browser()
        if browser:
            browser.back()

    def go_forward(self):
        browser = self.current_browser()
        if browser:
            browser.forward()

    def reload_page(self):
        browser = self.current_browser()
        if browser:
            browser.reload()

    def close_tab(self, index):
        if self.tabs.count() <= 1:
            browser = self.current_browser()

            if browser:
                browser.setUrl(QUrl(HOME_URL))

            return

        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)

        if widget:
            widget.deleteLater()

    def close_current_tab(self):
        index = self.tabs.currentIndex()

        if index >= 0:
            self.close_tab(index)

    # ==================================================
    # PAGE UPDATES
    # ==================================================

    def update_address_for_page(self, browser, url):
        if browser == self.current_browser():
            self.address_bar.setText(url.toString())

    def update_address_bar(self, index):
        browser = self.current_browser()

        if browser:
            self.address_bar.setText(
                browser.url().toString()
            )
            self.status_label.setText("Ready to browse")

    def update_tab_title(self, browser, title):
        index = self.tabs.indexOf(browser)

        if index >= 0:
            title = title.strip() or "New Tab"
            self.tabs.setTabText(index, title[:22])
            self.tabs.setTabToolTip(index, title)

            if browser == self.current_browser():
                self.setWindowTitle(
                    title + " — ZOHRAN Browser 3.0"
                )

    def show_loading(self, browser):
        if browser == self.current_browser():
            self.status_label.setText("Loading page...")

    def page_finished(self, browser, success):
        if browser == self.current_browser():
            if success:
                self.status_label.setText("Page loaded")
            else:
                self.status_label.setText(
                    "Could not load page. Check your internet."
                )

    def focus_address_bar(self):
        self.address_bar.setFocus()
        self.address_bar.selectAll()

    # ==================================================
    # BOOKMARKS
    # ==================================================

    def add_bookmark(self):
        browser = self.current_browser()

        if not browser:
            return

        url = browser.url().toString()
        title = browser.title() or url

        if not url:
            return

        for bookmark in self.bookmarks:
            if bookmark.get("url") == url:
                QMessageBox.information(
                    self,
                    "Bookmark",
                    "This page is already bookmarked."
                )
                return

        self.bookmarks.append({
            "title": title,
            "url": url,
        })

        write_json(BOOKMARKS_FILE, self.bookmarks)

        QMessageBox.information(
            self,
            "Bookmark Saved",
            "Your bookmark has been saved!"
        )

    def show_bookmarks(self):
        menu = QMenu(self)

        if not self.bookmarks:
            empty = menu.addAction("No bookmarks yet")
            empty.setEnabled(False)

        else:
            for bookmark in self.bookmarks:
                title = bookmark.get("title", "Bookmark")
                url = bookmark.get("url", HOME_URL)

                action = menu.addAction(title[:40])
                action.triggered.connect(
                    lambda checked=False, address=url:
                    self.navigate(address)
                )

        menu.addSeparator()

        remove_action = menu.addAction("Remove All Bookmarks")
        remove_action.triggered.connect(
            self.remove_all_bookmarks
        )

        menu.exec(
            self.bookmarks_button.mapToGlobal(
                self.bookmarks_button.rect().bottomLeft()
            )
        )

    def remove_all_bookmarks(self):
        answer = QMessageBox.question(
            self,
            "Remove Bookmarks",
            "Remove all saved bookmarks?"
        )

        if answer == QMessageBox.StandardButton.Yes:
            self.bookmarks = []
            write_json(BOOKMARKS_FILE, self.bookmarks)

    # ==================================================
    # DOWNLOADS
    # ==================================================

    def show_downloads(self):
        self.downloads_manager.show()
        self.downloads_manager.raise_()
        self.downloads_manager.activateWindow()

    def handle_download(self, download):
        filename = safe_filename(
            download.downloadFileName()
        )

        if not filename:
            filename = "download"

        destination = DOWNLOADS_FOLDER / filename

        counter = 1

        while destination.exists():
            destination = DOWNLOADS_FOLDER / (
                f"{Path(filename).stem}_{counter}"
                f"{Path(filename).suffix}"
            )
            counter += 1

        download.setDownloadDirectory(
            str(DOWNLOADS_FOLDER)
        )

        download.setDownloadFileName(
            destination.name
        )

        row_index = self.downloads_manager.add_download(
            destination.name,
            str(destination)
        )

        self.active_downloads.append(download)

        def update_progress():
            received = download.receivedBytes()
            total = download.totalBytes()

            if total > 0:
                percent = received * 100 / total

                self.downloads_manager.update_download(
                    row_index,
                    f"Downloading... {int(percent)}%",
                    percent
                )
            else:
                self.downloads_manager.update_download(
                    row_index,
                    "Downloading...",
                    0
                )

        def update_state(state):
            if state == (
                QWebEngineDownloadRequest.DownloadState.Completed
            ):
                self.downloads_manager.update_download(
                    row_index,
                    f"✅ Completed: {destination.name}",
                    100
                )

            elif state == (
                QWebEngineDownloadRequest.DownloadState.Cancelled
            ):
                self.downloads_manager.update_download(
                    row_index,
                    f"Cancelled: {destination.name}"
                )

            elif state == (
                QWebEngineDownloadRequest.DownloadState.DownloadInProgress
            ):
                self.downloads_manager.update_download(
                    row_index,
                    "Downloading...",
                    0
                )

            elif state == (
                QWebEngineDownloadRequest.DownloadState.DownloadInterrupted
            ):
                self.downloads_manager.update_download(
                    row_index,
                    f"❌ Download failed: {destination.name}"
                )

        download.receivedBytesChanged.connect(update_progress)
        download.totalBytesChanged.connect(update_progress)
        download.stateChanged.connect(update_state)

        download.accept()

    # ==================================================
    # THEMES
    # ==================================================

    def show_theme_menu(self):
        menu = QMenu(self)

        for name in THEMES:
            action = menu.addAction(name)
            action.triggered.connect(
                lambda checked=False, theme=name:
                self.change_theme(theme)
            )

        menu.exec(
            self.theme_button.mapToGlobal(
                self.theme_button.rect().bottomLeft()
            )
        )

    def change_theme(self, name):
        if name not in THEMES:
            return

        self.current_theme = name
        self.apply_theme()
        self.save_settings()

    def apply_theme(self):
        theme = THEMES.get(
            self.current_theme,
            THEMES["Purple Galaxy"]
        )

        background = theme["background"]
        panel = theme["panel"]
        button = theme["button"]
        text = theme["text"]
        border = theme["border"]

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {background};
                color: {text};
            }}

            QWidget {{
                color: {text};
                font-family: "Segoe UI";
                font-size: 13px;
            }}

            QLabel {{
                background: transparent;
            }}

            QLineEdit {{
                background-color: {background};
                color: {text};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 10px;
            }}

            QPushButton {{
                background-color: {panel};
                color: {text};
                border: 1px solid {border};
                border-radius: 9px;
                padding: 8px 12px;
            }}

            QPushButton:hover {{
                background-color: {button};
            }}

            QTabWidget::pane {{
                border: none;
                background: white;
            }}

            QTabBar::tab {{
                background-color: {panel};
                color: {text};
                padding: 10px 16px;
                margin-right: 3px;
                border-radius: 7px;
            }}

            QTabBar::tab:selected {{
                background-color: {button};
            }}

            QTabBar::tab:hover {{
                background-color: {button};
            }}

            QMenu {{
                background-color: {panel};
                color: {text};
                border: 1px solid {border};
                padding: 5px;
            }}

            QMenu::item {{
                padding: 8px 20px;
            }}

            QMenu::item:selected {{
                background-color: {button};
            }}

            QProgressBar {{
                border: 1px solid {border};
                border-radius: 5px;
                text-align: center;
                min-height: 16px;
            }}

            QProgressBar::chunk {{
                background-color: {button};
                border-radius: 4px;
            }}
        """)

    # ==================================================
    # PROFILE MENU
    # ==================================================

    def show_profile_menu(self):
        menu = QMenu(self)

        create_action = menu.addAction("＋ Create New Profile")
        create_action.triggered.connect(
            self.create_new_profile
        )

        menu.addSeparator()

        for name in self.profiles:
            action = menu.addAction(name)
            action.triggered.connect(
                lambda checked=False, profile_name=name:
                self.switch_profile(profile_name)
            )

        menu.exec(
            self.profile_button.mapToGlobal(
                self.profile_button.rect().bottomLeft()
            )
        )

    # ==================================================
    # BROWSER MENU
    # ==================================================

    def show_browser_menu(self):
        menu = QMenu(self)

        new_tab_action = menu.addAction("＋ New Tab")
        new_tab_action.triggered.connect(
            lambda: self.new_tab(HOME_URL)
        )

        bookmarks_action = menu.addAction("★ Bookmarks")
        bookmarks_action.triggered.connect(self.show_bookmarks)

        downloads_action = menu.addAction("📥 Downloads")
        downloads_action.triggered.connect(self.show_downloads)

        theme_action = menu.addAction("🎨 Change Theme")
        theme_action.triggered.connect(self.show_theme_menu)

        menu.addSeparator()

        privacy_action = menu.addAction(
            "🛡 Clear Cache and Cookies"
        )
        privacy_action.triggered.connect(
            self.clear_browsing_data
        )

        fullscreen_action = menu.addAction(
            "⛶ Toggle Fullscreen"
        )
        fullscreen_action.triggered.connect(
            self.toggle_fullscreen
        )

        menu.addSeparator()

        about_action = menu.addAction("About ZOHRAN Browser")
        about_action.triggered.connect(self.show_about)

        menu.exec(
            self.menu_button.mapToGlobal(
                self.menu_button.rect().bottomLeft()
            )
        )

    # ==================================================
    # PRIVACY
    # ==================================================

    def clear_browsing_data(self):
        answer = QMessageBox.question(
            self,
            "Clear Browsing Data",
            "Clear cached files and cookies for this profile?"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        profile = self.current_profile()

        profile.clearHttpCache()
        profile.cookieStore().deleteAllCookies()

        QMessageBox.information(
            self,
            "Privacy",
            "The request to clear cached files and cookies was sent."
        )

    # ==================================================
    # FULLSCREEN
    # ==================================================

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("⛶ Fullscreen")
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("⛶ Exit Fullscreen")

    # ==================================================
    # ABOUT
    # ==================================================

    def show_about(self):
        QMessageBox.about(
            self,
            "About ZOHRAN Browser",
            """
            <h2>◈ ZOHRAN Browser 3.0</h2>
            <p>Your personal Python browser project!</p>
            <ul>
                <li>Google search in English</li>
                <li>Multiple tabs</li>
                <li>Bookmarks</li>
                <li>Five themes</li>
                <li>Browser profiles</li>
                <li>Downloads Manager</li>
                <li>Download progress</li>
                <li>Fullscreen mode</li>
                <li>Privacy controls</li>
            </ul>
            <p>Built with Python and PySide6.</p>
            """
        )

    # ==================================================
    # SETTINGS
    # ==================================================

    def save_settings(self):
        self.settings = {
            "theme": self.current_theme,
            "profile": self.current_profile_name,
        }

        write_json(SETTINGS_FILE, self.settings)

    def closeEvent(self, event):
        self.save_settings()
        event.accept()


# ==================================================
# START THE APP
# ==================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    window = ZohranBrowser()
    window.showMaximized()

    sys.exit(app.exec())
