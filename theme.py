"""
Design system — palette, spacing, fonts.

The visual shell uses classic tk widgets with direct bg/fg/font.
ttkbootstrap is only used for interactive controls via bootstyle=.
Theme 'bg' = SURFACE so themed controls sit flush on cards.
"""

import tkinter.font as tkfont
from ttkbootstrap.style import ThemeDefinition

# ── App identity ─────────────────────────────────────────────────────────
APP_NAME    = "Daily Dispatch"
APP_SHORT   = "DISPATCH"
APP_TAGLINE = "DAILY BRIEFING"
VERSION     = "1.0.0 — Phase 5"

# ── Colour palette ───────────────────────────────────────────────────────
BG       = "#0F1620"
SIDEBAR  = "#0B1017"
SURFACE  = "#182430"
SURFACE2 = "#1E2A38"
BORDER   = "#263340"
FG       = "#E4EAF1"
MUTED    = "#8A97A6"
ACCENT   = "#22D3EE"
ACCENT_D = "#0B1017"
SUCCESS  = "#34D399"
WARNING  = "#FBBF24"
DANGER   = "#F87171"
INFO     = "#38BDF8"

_THEME_COLORS = {
    "primary": ACCENT, "secondary": MUTED, "success": SUCCESS,
    "info": INFO, "warning": WARNING, "danger": DANGER,
    "light": FG, "dark": SIDEBAR,
    "bg": SURFACE, "fg": FG,
    "selectbg": ACCENT, "selectfg": ACCENT_D,
    "border": BORDER, "inputfg": FG, "inputbg": BG, "active": SURFACE2,
}

S = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
F: dict = {}

def _pick(root, candidates, fallback):
    avail = set(tkfont.families(root))
    for c in candidates:
        if c in avail:
            return c
    return fallback

def build_fonts(root):
    ui   = _pick(root, ["Segoe UI", "Inter", "Helvetica Neue", "Arial"], "DejaVu Sans")
    mono = _pick(root, ["Cascadia Mono", "Consolas", "JetBrains Mono"],  "DejaVu Sans Mono")
    F.update({
        "ui": ui, "mono_fam": mono,
        "base":       tkfont.Font(root=root, family=ui, size=10),
        "base_bold":  tkfont.Font(root=root, family=ui, size=10, weight="bold"),
        "sm":         tkfont.Font(root=root, family=ui, size=9),
        "xs":         tkfont.Font(root=root, family=ui, size=8),
        "h1":         tkfont.Font(root=root, family=ui, size=20, weight="bold"),
        "h2":         tkfont.Font(root=root, family=ui, size=13, weight="bold"),
        "card_title": tkfont.Font(root=root, family=ui, size=12, weight="bold"),
        "nav":        tkfont.Font(root=root, family=ui, size=11),
        "brand":      tkfont.Font(root=root, family=ui, size=15, weight="bold"),
        "glyph":      tkfont.Font(root=root, family=ui, size=42),
        "mono":       tkfont.Font(root=root, family=mono, size=10),
    })

def register_theme(style):
    try:
        td = ThemeDefinition("dispatch", _THEME_COLORS, mode="dark")
    except TypeError:
        td = ThemeDefinition("dispatch", _THEME_COLORS, themetype="dark")
    style.register_theme(td)
    style.theme_use("dispatch")

def init(style):
    build_fonts(style.master)
