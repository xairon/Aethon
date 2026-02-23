"""Aethon — Obsidian Design System.

Premium dark theme with deep space palette, electric blue accents,
and glassmorphism-inspired surfaces.
"""

# ═══════════════════════════════════════════════════════════════════
# Color Palette — Obsidian
# ═══════════════════════════════════════════════════════════════════

# Background layers (depth hierarchy)
BG_VOID = "#08090f"        # Deepest — window / app background
BG_BASE = "#0d1017"        # Main surface
BG_SURFACE = "#131720"     # Cards, panels
BG_RAISED = "#1a1f2e"      # Elevated — inputs, buttons
BG_ELEVATED = "#232a3c"    # Highest — hover / active states

# Borders
BORDER_DIM = "#151a26"     # Barely visible
BORDER_DEFAULT = "#1e2436" # Standard borders
BORDER_HOVER = "#2d3550"   # Hover emphasis
BORDER_FOCUS = "#4f8fff"   # Focus ring / active accent

# Text
TEXT = "#e2e8f0"            # Primary text
TEXT_SECONDARY = "#7e8ca2"  # Secondary / descriptions
TEXT_MUTED = "#4a5568"      # Disabled / hints
TEXT_INVERSE = "#0d1017"    # On bright backgrounds

# Accent colors
ACCENT = "#4f8fff"          # Primary — electric blue
ACCENT_HOVER = "#6aa0ff"    # Primary hover
ACCENT_DIM = "#3a6bc5"      # Primary muted (borders, subtle)
ACCENT_VIOLET = "#917cf7"   # Secondary accent
GREEN = "#34d399"           # Success
GREEN_HOVER = "#4eeab5"     # Success hover
AMBER = "#fbbf24"           # Warning
RED = "#f87171"             # Error / danger
RED_HOVER = "#fca5a5"       # Error hover
CYAN = "#22d3ee"            # Info / speaking

# Glass overlay (for card-like surfaces)
GLASS = "rgba(13, 16, 23, 0.92)"

# ═══════════════════════════════════════════════════════════════════
# QSS Stylesheet
# ═══════════════════════════════════════════════════════════════════

STYLESHEET = f"""

/* ── Global ─────────────────────────────────────────────── */

QMainWindow, QDialog {{
    background-color: {BG_VOID};
    color: {TEXT};
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}}

QWidget {{
    color: {TEXT};
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}}

/* ── Tabs ───────────────────────────────────────────────── */

QTabWidget::pane {{
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    background-color: {BG_BASE};
    top: -1px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    padding: 10px 22px;
    margin-right: 0px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 500;
    font-size: 13px;
}}

QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
}}

QTabBar::tab:hover:!selected {{
    color: {TEXT};
    border-bottom: 2px solid {BORDER_HOVER};
}}

/* ── Buttons ────────────────────────────────────────────── */

QPushButton {{
    background-color: {BG_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 500;
    font-size: 13px;
}}

QPushButton:hover {{
    background-color: {BG_ELEVATED};
    border-color: {BORDER_HOVER};
    color: {TEXT};
}}

QPushButton:pressed {{
    background-color: {BG_SURFACE};
    border-color: {ACCENT_DIM};
}}

QPushButton:disabled {{
    background-color: {BG_SURFACE};
    color: {TEXT_MUTED};
    border-color: {BORDER_DIM};
}}

/* Start button — vibrant green */
QPushButton#startBtn {{
    background-color: {GREEN};
    color: {TEXT_INVERSE};
    font-weight: 700;
    font-size: 14px;
    border: none;
    border-radius: 10px;
    padding: 10px 24px;
}}

QPushButton#startBtn:hover {{
    background-color: {GREEN_HOVER};
}}

QPushButton#startBtn:pressed {{
    background-color: #2cb885;
}}

QPushButton#startBtn:disabled {{
    background-color: {BG_RAISED};
    color: {TEXT_MUTED};
}}

/* Stop button — subtle red */
QPushButton#stopBtn {{
    background-color: {RED};
    color: {TEXT_INVERSE};
    font-weight: 700;
    font-size: 14px;
    border: none;
    border-radius: 10px;
    padding: 10px 24px;
}}

QPushButton#stopBtn:hover {{
    background-color: {RED_HOVER};
}}

QPushButton#stopBtn:pressed {{
    background-color: #e05050;
}}

QPushButton#stopBtn:disabled {{
    background-color: {BG_RAISED};
    color: {TEXT_MUTED};
}}

/* Settings button — ghost style */
QPushButton#settingsBtn {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_DEFAULT};
    font-weight: 400;
    font-size: 13px;
    border-radius: 8px;
    padding: 8px 18px;
}}

QPushButton#settingsBtn:hover {{
    color: {ACCENT};
    border-color: {ACCENT_DIM};
    background-color: rgba(79, 143, 255, 0.06);
}}

/* ── Inputs ─────────────────────────────────────────────── */

QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {BG_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    padding: 7px 12px;
    selection-background-color: {ACCENT};
    selection-color: {TEXT_INVERSE};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
    background-color: {BG_ELEVATED};
}}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background-color: {BG_SURFACE};
    color: {TEXT_MUTED};
    border-color: {BORDER_DIM};
}}

/* ── ComboBox ───────────────────────────────────────────── */

QComboBox {{
    background-color: {BG_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    padding: 7px 12px;
    min-width: 120px;
}}

QComboBox:hover {{
    border-color: {BORDER_HOVER};
}}

QComboBox:focus {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
    subcontrol-position: right center;
}}

QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_SURFACE};
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: {TEXT_INVERSE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    padding: 4px;
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    padding: 6px 12px;
    border-radius: 4px;
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {BG_ELEVATED};
}}

/* ── TextEdit ───────────────────────────────────────────── */

QTextEdit, QPlainTextEdit {{
    background-color: {BG_RAISED};
    color: {TEXT};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    padding: 8px;
    selection-background-color: {ACCENT};
    selection-color: {TEXT_INVERSE};
}}

QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {ACCENT};
}}

/* ── GroupBox ────────────────────────────────────────────── */

QGroupBox {{
    color: {ACCENT};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 18px;
    font-weight: 600;
    font-size: 13px;
    background-color: {BG_BASE};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    left: 14px;
    color: {TEXT};
    font-weight: 600;
    letter-spacing: 0.3px;
}}

/* ── CheckBox ───────────────────────────────────────────── */

QCheckBox {{
    color: {TEXT};
    spacing: 10px;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 5px;
    border: 2px solid {BORDER_HOVER};
    background-color: {BG_RAISED};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT_DIM};
    background-color: {BG_ELEVATED};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QCheckBox::indicator:checked:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QCheckBox::indicator:disabled {{
    background-color: {BG_SURFACE};
    border-color: {BORDER_DIM};
}}

/* ── RadioButton ────────────────────────────────────────── */

QRadioButton {{
    color: {TEXT};
    spacing: 10px;
    font-size: 13px;
}}

QRadioButton::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 10px;
    border: 2px solid {BORDER_HOVER};
    background-color: {BG_RAISED};
}}

QRadioButton::indicator:hover {{
    border-color: {ACCENT_DIM};
    background-color: {BG_ELEVATED};
}}

QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QRadioButton::indicator:checked:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

/* ── Labels ─────────────────────────────────────────────── */

QLabel {{
    color: {TEXT};
    background: transparent;
}}

QLabel#sectionLabel {{
    color: {ACCENT};
    font-weight: 600;
    font-size: 14px;
    letter-spacing: 0.5px;
}}

/* ── Slider ─────────────────────────────────────────────── */

QSlider::groove:horizontal {{
    background-color: {BG_RAISED};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background-color: {ACCENT};
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
    border: 2px solid {BG_VOID};
}}

QSlider::handle:horizontal:hover {{
    background-color: {ACCENT_HOVER};
}}

QSlider::sub-page:horizontal {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

/* ── ScrollBars ─────────────────────────────────────────── */

QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 4px 0;
}}

QScrollBar::handle:vertical {{
    background-color: {BORDER_HOVER};
    border-radius: 4px;
    min-height: 32px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0 4px;
}}

QScrollBar::handle:horizontal {{
    background-color: {BORDER_HOVER};
    border-radius: 4px;
    min-width: 32px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_MUTED};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* ── StatusBar ──────────────────────────────────────────── */

QStatusBar {{
    background-color: {BG_BASE};
    color: {TEXT_SECONDARY};
    border-top: 1px solid {BORDER_DIM};
    font-size: 12px;
}}

/* ── Menu ───────────────────────────────────────────────── */

QMenu {{
    background-color: {BG_SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 24px;
    border-radius: 6px;
}}

QMenu::item:selected {{
    background-color: {ACCENT};
    color: {TEXT_INVERSE};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER_DEFAULT};
    margin: 4px 10px;
}}

/* ── Tooltip ────────────────────────────────────────────── */

QToolTip {{
    background-color: {BG_SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ── Dialog Buttons ─────────────────────────────────────── */

QDialogButtonBox QPushButton {{
    min-width: 120px;
    padding: 9px 24px;
    border-radius: 8px;
}}

/* ── ScrollArea (transparent) ───────────────────────────── */

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

/* ── FormLayout labels ──────────────────────────────────── */

QFormLayout QLabel {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}
"""
