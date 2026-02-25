# --- File paths ---
import os
LAST_DIR_FILE = os.path.join(os.path.expanduser("~"), ".gitbash6dir")

# --- App window configuration ---
APP_TITLE = "Git Bash Automatico"
APP_GEOMETRY = "500x375"
MAIN_PAD = 30

# --- Caching configuration ---
CACHE_TIMEOUT = 30.0  # seconds
CACHE_DEFAULTS = {
    'branch': None,
    'origin': None,
    'github_user': None,
    'is_repo': None,
    'cache_time': 0,
    'github_user_needs_update': False,
    'branches_fetched_on_startup': False,
    'login_in_progress': False,
}

# --- UI constants ---
# Fonts
DEFAULT_FONT = ("Segoe UI", 10)
BOLD_FONT = ("Segoe UI", 10, "bold")

# Entry and button sizes
ENTRY_WIDTH_SHORT = 24
BUTTON_WIDTH_DEFAULT = 20
BUTTON_HEIGHT_DEFAULT = 2
TEXT_HEIGHT_COMMIT = 5
TEXT_WIDTH_COMMIT = 60

# Padding and spacing
PAD_X_DEFAULT = 10
PAD_X_BUTTON = 6
PAD_Y_DEFAULT = 5
PAD_Y_BUTTON = 6
PAD_Y_SECTION = 16
PAD_Y_MENU_ROW = 0
PAD_Y_MENU_BTN = 6
PAD_Y_ACCOUNT_BTN = 6
PAD_X_ACCOUNT_BTN = 10
PAD_Y_DIR_LABEL = (15, 0)
PAD_Y_MAIN_CONTAINER = (0, MAIN_PAD)
PAD_Y_SUGG_CONTAINER = (10, 0)  # uniforma con PAD_Y_SECTION
PAD_X_SUGG_CONTAINER = 10
BUTTON_PAD_Y_SUGG = 1
BUTTON_PAD_INNER = 8

# Colors
COLOR_ERROR = "red"

# --- Scroll and canvas settings ---
SCROLL_THRESHOLD = 5
CANVAS_HEIGHT = 130
SCROLLBAR_FILE_THRESHOLD = 7
FILESELECTION_SCROLL_THRESHOLD = 9
FILESELECTION_CANVAS_HEIGHT = 180
