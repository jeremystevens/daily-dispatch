"""
Daily Dispatch — Phase 1 application shell.

Window chrome (sidebar, header, status bar, nav) is classic tk widgets with
direct bg/fg/font so ttkbootstrap's style-name parser never touches them.
The root is a ttkbootstrap Window so the theme engine powers interactive
controls (Entry, Combobox, toggles, buttons) via bootstyle=.
"""

import tkinter as tk
import ttkbootstrap as tb

import theme as T
from widgets import StatusChip, divider
from settings_view import SettingsView
from briefing_view import BriefingView
from schedule_view import ScheduleView
import placeholders
from printer_service import PrinterService
from location_service import LocationService
from database import Database, SettingsRepository


NAV = [
    ("briefing", "Briefing"),
    ("schedule", "Schedule"),
    ("history",  "History"),
    ("settings", "Settings"),
]

_SCOLORS = {"info": T.FG, "success": T.SUCCESS,
            "warning": T.WARNING, "danger": T.DANGER}


class App:
    def __init__(self):
        # ── root window ─────────────────────────────────────────
        self.root = tb.Window()
        T.register_theme(self.root.style)
        T.init(self.root.style)

        self.root.title(T.APP_NAME)
        self.root.geometry("1140x740")
        self.root.minsize(980, 660)
        self.root.configure(background=T.BG)
        self._center()

        # ── services ────────────────────────────────────────────
        self.db       = Database()
        self.repo     = SettingsRepository(self.db)
        self.printer  = PrinterService()
        self.location = LocationService()

        self._views = {}
        self._nav   = {}            # key → (indicator_frame, btn_widget)
        self._active_key = None

        self._build()
        self._init_printer()
        self._nav_select("settings")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ════════════════════════════════════════════════════════════
    #  Layout
    # ════════════════════════════════════════════════════════════
    def _build(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # ── sidebar (fixed 234 px) ──────────────────────────────
        sb = tk.Frame(self.root, bg=T.SIDEBAR, width=234, bd=0,
                      highlightthickness=0)
        sb.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sb.grid_propagate(False)
        self._build_sidebar(sb)

        # ── main area ───────────────────────────────────────────
        main = tk.Frame(self.root, bg=T.BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        hdr = tk.Frame(main, bg=T.BG)
        hdr.grid(row=0, column=0, sticky="ew",
                 padx=T.S["xl"], pady=(T.S["xl"], T.S["md"]))
        self.pg_title = tk.Label(hdr, text="", bg=T.BG, fg=T.FG,
                                 font=T.F["h1"], anchor="w")
        self.pg_title.pack(fill="x")
        self.pg_sub = tk.Label(hdr, text="", bg=T.BG, fg=T.MUTED,
                               font=T.F["base"], anchor="w")
        self.pg_sub.pack(fill="x", pady=(2, 0))

        self.content = tk.Frame(main, bg=T.BG)
        self.content.grid(row=1, column=0, sticky="nsew",
                          padx=T.S["xl"], pady=(0, T.S["md"]))

        # ── status bar ──────────────────────────────────────────
        sbar = tk.Frame(self.root, bg=T.SIDEBAR, height=28, bd=0,
                        highlightthickness=0)
        sbar.grid(row=1, column=1, sticky="ew")
        self.status_lbl = tk.Label(sbar, text="Ready", bg=T.SIDEBAR,
                                   fg=T.MUTED, font=T.F["sm"])
        self.status_lbl.pack(side="left", padx=T.S["lg"], pady=T.S["xs"])
        tk.Label(sbar, text=T.VERSION, bg=T.SIDEBAR, fg=T.MUTED,
                 font=T.F["sm"]).pack(side="right", padx=T.S["lg"],
                                      pady=T.S["xs"])

    # ── sidebar ──────────────────────────────────────────────────
    def _build_sidebar(self, sb):
        p = T.S
        # brand lockup
        brand = tk.Frame(sb, bg=T.SIDEBAR)
        brand.pack(fill="x", padx=p["xl"], pady=(p["xl"], p["lg"]))
        line = tk.Frame(brand, bg=T.SIDEBAR)
        line.pack(anchor="w")
        tk.Label(line, text=T.APP_SHORT, bg=T.SIDEBAR, fg=T.FG,
                 font=T.F["brand"]).pack(side="left")
        tk.Label(line, text=" ●", bg=T.SIDEBAR, fg=T.ACCENT,
                 font=T.F["brand"]).pack(side="left")
        tk.Label(brand, text=T.APP_TAGLINE, bg=T.SIDEBAR, fg=T.MUTED,
                 font=T.F["xs"]).pack(anchor="w", pady=(3, 0))

        tk.Label(sb, text="MENU", bg=T.SIDEBAR, fg=T.MUTED,
                 font=T.F["xs"]).pack(anchor="w", padx=p["xl"],
                                      pady=(p["sm"], p["xs"]))

        nav_box = tk.Frame(sb, bg=T.SIDEBAR)
        nav_box.pack(fill="x", padx=p["md"])
        for key, label in NAV:
            self._add_nav(nav_box, key, label)

        # bottom printer chip
        bot = tk.Frame(sb, bg=T.SIDEBAR)
        bot.pack(side="bottom", fill="x", padx=p["xl"], pady=p["xl"])
        divider(bot, pad=(0, p["md"]))
        tk.Label(bot, text="PRINTER", bg=T.SIDEBAR, fg=T.MUTED,
                 font=T.F["xs"]).pack(anchor="w")
        self.pr_chip = StatusChip(bot, "—", T.MUTED, T.SIDEBAR)
        self.pr_chip.pack(anchor="w", pady=(p["sm"], 0))

    def _add_nav(self, parent, key, label):
        row = tk.Frame(parent, bg=T.SIDEBAR)
        row.pack(fill="x", pady=2)

        ind = tk.Frame(row, width=3, bg=T.SIDEBAR, bd=0,
                       highlightthickness=0)
        ind.pack(side="left", fill="y")

        btn = tk.Button(row, text=label, font=T.F["nav"],
                        bg=T.SIDEBAR, fg=T.MUTED,
                        activebackground=T.SURFACE2, activeforeground=T.FG,
                        bd=0, highlightthickness=0, relief="flat",
                        anchor="w", padx=14, pady=8, cursor="hand2",
                        command=lambda k=key: self._nav_select(k))
        btn.pack(side="left", fill="x", expand=True)
        btn.bind("<Enter>", lambda e, b=btn: self._nav_hover(b, True))
        btn.bind("<Leave>", lambda e, b=btn: self._nav_hover(b, False))

        self._nav[key] = (ind, btn)

    def _nav_hover(self, btn, enter):
        """Hover highlight — but not for the active button."""
        for k, (_, b) in self._nav.items():
            if b is btn and k == self._active_key:
                return
        btn.configure(bg=T.SURFACE2 if enter else T.SIDEBAR,
                      fg=T.FG if enter else T.MUTED)

    # ════════════════════════════════════════════════════════════
    #  Navigation
    # ════════════════════════════════════════════════════════════
    def _nav_select(self, key):
        self._active_key = key
        for k, (ind, btn) in self._nav.items():
            active = k == key
            ind.configure(bg=T.ACCENT if active else T.SIDEBAR)
            btn.configure(bg=T.SURFACE2 if active else T.SIDEBAR,
                          fg=T.ACCENT if active else T.MUTED)

        for w in self.content.winfo_children():
            w.pack_forget()

        view = self._get_view(key)
        self.pg_title.configure(text=view.TITLE)
        self.pg_sub.configure(text=view.SUBTITLE)
        view.pack(fill="both", expand=True)

    def _get_view(self, key):
        if key not in self._views:
            if key == "settings":
                v = SettingsView(self.content, self)
            elif key == "briefing":
                v = BriefingView(self.content, self)
            elif key == "schedule":
                v = ScheduleView(self.content, self)
            else:
                v = placeholders.history_view(self.content)
            self._views[key] = v
        return self._views[key]

    # ════════════════════════════════════════════════════════════
    #  Public API for views
    # ════════════════════════════════════════════════════════════
    def set_status(self, msg, kind="info"):
        self.status_lbl.configure(text=msg,
                                  fg=_SCOLORS.get(kind, T.FG))

    def set_printer_status(self, ok, name):
        self.pr_chip.set(name or "—", T.SUCCESS if ok else T.DANGER)

    def _init_printer(self):
        names = self.printer.list_printers()
        self.pr_chip.set(self.printer.default_printer_name(names) or
                         "No printer", T.MUTED)

    # ════════════════════════════════════════════════════════════
    #  Window management
    # ════════════════════════════════════════════════════════════
    def _center(self):
        self.root.update_idletasks()
        w, h = 1140, 740
        x = max(0, (self.root.winfo_screenwidth()  - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 3)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _on_close(self):
        self.db.close()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
