"""
Polished empty-state views for nav areas not yet implemented.
All classic tk widgets — no ttkbootstrap style names.
"""

import tkinter as tk
import theme as T


class PlaceholderView(tk.Frame):
    def __init__(self, master, glyph, title, subtitle, phase,
                 header_title="", header_sub=""):
        super().__init__(master, bg=T.BG)
        self.TITLE    = header_title or title
        self.SUBTITLE = header_sub

        c = tk.Frame(self, bg=T.BG)
        c.place(relx=0.5, rely=0.44, anchor="center")
        tk.Label(c, text=glyph, bg=T.BG, fg=T.SURFACE2,
                 font=T.F["glyph"]).pack()
        tk.Label(c, text=title, bg=T.BG, fg=T.FG,
                 font=T.F["h2"]).pack(pady=(T.S["md"], 0))
        tk.Label(c, text=subtitle, bg=T.BG, fg=T.MUTED,
                 font=T.F["base"], justify="center",
                 wraplength=380).pack(pady=(T.S["sm"], T.S["lg"]))
        tk.Label(c, text=phase, bg=T.SURFACE2, fg=T.ACCENT,
                 font=T.F["xs"], padx=8, pady=3).pack()


def briefing_view(m):
    return PlaceholderView(m, "◔", "Weather briefing",
        "Fetch a live forecast and preview the exact 58 mm report "
        "before it touches paper.", "ARRIVES IN PHASE 2",
        "Briefing", "Fetch and preview the forecast before printing.")

def schedule_view(m):
    return PlaceholderView(m, "◷", "Print schedule",
        "Pick the days and time your briefing prints automatically, "
        "then let Windows Task Scheduler handle the rest.", "ARRIVES IN PHASE 4",
        "Schedule", "Choose the days and time your briefing prints.")

def history_view(m):
    return PlaceholderView(m, "◧", "Print history",
        "Every scheduled and manual run, with a clear result and "
        "diagnostics when something goes wrong.", "ARRIVES IN PHASE 6",
        "History", "A traceable record of every print run.")
