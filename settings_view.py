"""
Settings — the functional Phase 1 screen.

Containers and labels are classic tk widgets (immune to ttkbootstrap's
style-name parser). Interactive controls use ttkbootstrap via bootstyle=.
"""

import tkinter as tk
import ttkbootstrap as tb

try:                                       # 2.x
    from ttkbootstrap import ScrolledFrame
except ImportError:                        # 1.x
    from ttkbootstrap.scrolled import ScrolledFrame

import theme as T
from widgets import Card, FormRow, StatusChip, run_async


def _segmented(parent, variable, options):
    """Row of toolbutton radios (bootstyle segmented control)."""
    f = tk.Frame(parent, bg=T.SURFACE)
    for i, (label, value) in enumerate(options):
        tb.Radiobutton(f, text=label, value=value, variable=variable,
                       bootstyle="toolbutton").pack(
            side="left", padx=(0 if i == 0 else T.S["sm"], 0))
    return f


class SettingsView(tk.Frame):
    TITLE    = "Settings"
    SUBTITLE = "Configure your printer, location, and report options."

    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app

        # ── form variables ───────────────────────────────────────────
        self.printer_var  = tk.StringVar()
        self.mode_var     = tk.StringVar(value="query")
        self.query_var    = tk.StringVar()
        self.lat_var      = tk.StringVar()
        self.lon_var      = tk.StringVar()
        self.resolved_var = tk.StringVar(value="Not validated yet")
        self.units_var    = tk.StringVar(value="metric")
        self.timefmt_var  = tk.StringVar(value="24h")
        self.qr_var       = tk.IntVar(value=1)
        self.logo_var     = tk.IntVar(value=0)
        self.barcode_var  = tk.IntVar(value=0)

        # ── scrollable body ──────────────────────────────────────────
        scroller = ScrolledFrame(self, autohide=True, bootstyle="secondary-round")
        scroller.pack(fill="both", expand=True)
        body = tk.Frame(scroller, bg=T.BG)
        body.pack(fill="both", expand=True, padx=T.S["xs"])

        self._build_printer(body)
        self._build_location(body)
        self._build_options(body)
        self._build_actions(body)

        self._load()
        self.mode_var.trace_add("write", lambda *_: self._sync_mode())

    # ── Printer card ─────────────────────────────────────────────────
    def _build_printer(self, parent):
        c = Card(parent, "Printer",
                 "Where briefings are sent. Defaults to POS-58 when found.")
        c.pack(fill="x", pady=(0, T.S["lg"]))
        b = c.body

        row = FormRow(b, "Print queue", hint="Installed Windows printers")
        row.pack(fill="x")
        pick = tk.Frame(row.control, bg=T.SURFACE)
        pick.pack(fill="x")
        self.combo = tb.Combobox(pick, textvariable=self.printer_var,
                                 state="readonly")
        self.combo.pack(side="left", fill="x", expand=True)
        tb.Button(pick, text="Refresh", bootstyle="secondary-outline",
                  command=self._refresh, width=9).pack(
            side="left", padx=(T.S["sm"], 0))

        acts = tk.Frame(b, bg=T.SURFACE)
        acts.pack(fill="x", pady=(T.S["lg"], 0))
        self.chip = StatusChip(acts, "No test run yet", T.MUTED, T.SURFACE)
        self.chip.pack(side="left")
        self.test_btn = tb.Button(acts, text="Test printer",
                                  bootstyle="info-outline",
                                  command=self._test)
        self.test_btn.pack(side="right")

    # ── Location card ────────────────────────────────────────────────
    def _build_location(self, parent):
        c = Card(parent, "Location",
                 "The forecast point for your briefing.")
        c.pack(fill="x", pady=(0, T.S["lg"]))
        b = c.body

        mr = FormRow(b, "Input method")
        mr.pack(fill="x")
        _segmented(mr.control, self.mode_var,
                   [("City / Postal", "query"),
                    ("Coordinates", "coords")]).pack(anchor="w")

        self.loc_slot = tk.Frame(b, bg=T.SURFACE)
        self.loc_slot.pack(fill="x", pady=(T.S["lg"], 0))

        # query row
        self.qf = FormRow(self.loc_slot, "City or postal code",
                          hint="e.g. Boston or 02108")
        tb.Entry(self.qf.control, textvariable=self.query_var).pack(fill="x")

        # coords row
        self.cf = FormRow(self.loc_slot, "Latitude / Longitude",
                          hint="decimal degrees")
        cw = tk.Frame(self.cf.control, bg=T.SURFACE)
        cw.pack(fill="x")
        tb.Entry(cw, textvariable=self.lat_var).pack(
            side="left", fill="x", expand=True)
        tb.Entry(cw, textvariable=self.lon_var).pack(
            side="left", fill="x", expand=True, padx=(T.S["sm"], 0))

        af = tk.Frame(b, bg=T.SURFACE)
        af.pack(fill="x", pady=(T.S["lg"], 0))
        rl = tk.Frame(af, bg=T.SURFACE)
        rl.pack(side="left", fill="x", expand=True)
        tk.Label(rl, text="Resolved", bg=T.SURFACE, fg=T.MUTED,
                 font=T.F["sm"]).pack(anchor="w")
        tk.Label(rl, textvariable=self.resolved_var, bg=T.SURFACE,
                 fg=T.ACCENT, font=T.F["base_bold"]).pack(anchor="w")
        tb.Button(af, text="Validate", bootstyle="info-outline",
                  command=self._validate).pack(side="right")

    # ── Report options card ──────────────────────────────────────────
    def _build_options(self, parent):
        c = Card(parent, "Report options",
                 "How the briefing is presented on 58 mm paper.")
        c.pack(fill="x", pady=(0, T.S["lg"]))
        b = c.body

        r1 = FormRow(b, "Units")
        r1.pack(fill="x")
        _segmented(r1.control, self.units_var,
                   [("Metric  °C", "metric"),
                    ("Imperial  °F", "imperial")]).pack(anchor="w")

        r2 = FormRow(b, "Time format")
        r2.pack(fill="x", pady=(T.S["lg"], 0))
        _segmented(r2.control, self.timefmt_var,
                   [("24-hour", "24h"), ("12-hour", "12h")]).pack(anchor="w")

        r3 = FormRow(b, "Optional elements",
                     hint="Printed if the printer supports them")
        r3.pack(fill="x", pady=(T.S["lg"], 0))
        tog = tk.Frame(r3.control, bg=T.SURFACE)
        tog.pack(fill="x")
        for text, var in [("QR code", self.qr_var),
                          ("Logo", self.logo_var),
                          ("Barcode", self.barcode_var)]:
            tb.Checkbutton(tog, text=text, variable=var,
                           bootstyle="primary-round-toggle").pack(
                side="left", padx=(0, T.S["xl"]))

    # ── Save / Revert bar ────────────────────────────────────────────
    def _build_actions(self, parent):
        bar = tk.Frame(parent, bg=T.BG)
        bar.pack(fill="x", pady=(T.S["sm"], T.S["lg"]))
        tb.Button(bar, text="Save settings", bootstyle="primary",
                  command=self._save, width=16).pack(side="right")
        tb.Button(bar, text="Revert", bootstyle="secondary-outline",
                  command=self._load, width=10).pack(
            side="right", padx=(0, T.S["sm"]))

    # ── behaviour ────────────────────────────────────────────────────
    def _refresh(self):
        names = self.app.printer.list_printers()
        self.combo.configure(values=names)
        if self.printer_var.get() not in names:
            self.printer_var.set(self.app.printer.default_printer_name(names))
        self.app.set_status(f"Found {len(names)} printer(s).", "info")

    def _sync_mode(self):
        self.qf.pack_forget()
        self.cf.pack_forget()
        (self.cf if self.mode_var.get() == "coords" else self.qf).pack(fill="x")

    def _test(self):
        name = self.printer_var.get()
        if not name:
            self.app.set_status("Select a printer first.", "warning")
            return
        self.test_btn.configure(state="disabled", text="Testing…")
        self.chip.set("Sending test receipt…", T.WARNING)

        def work():
            return self.app.printer.test_print(name)

        def done(result, error):
            self.test_btn.configure(state="normal", text="Test printer")
            if error:
                self.chip.set("Test failed", T.DANGER)
                self.app.set_status(f"Printer error: {error}", "danger")
                self.app.set_printer_status(False, name)
            elif result.ok:
                self.chip.set("Connection OK", T.SUCCESS)
                self.app.set_printer_status(True, name)
                self.app.set_status(result.message, "success")
            else:
                self.chip.set("Not reachable", T.DANGER)
                self.app.set_printer_status(False, name)
                self.app.set_status(result.message, "danger")

        run_async(self.app.root, work, done)

    def _validate(self):
        r = self.app.location.validate(
            self.mode_var.get(), self.query_var.get(),
            self.lat_var.get(), self.lon_var.get())
        if r.ok:
            self.resolved_var.set(r.data.get("resolved_name", "—"))
            self.app.set_status(r.message, "success")
        else:
            self.resolved_var.set("Not validated yet")
            self.app.set_status(r.message, "warning")

    # ── persistence ──────────────────────────────────────────────────
    def _load(self):
        d = self.app.repo.load()
        names = self.app.printer.list_printers()
        self.combo.configure(values=names)
        self.printer_var.set(d["printer_name"] or
                             self.app.printer.default_printer_name(names))
        self.mode_var.set(d["location_mode"] or "query")
        self.query_var.set(d["location_query"] or "")
        self.lat_var.set("" if d["latitude"] is None else str(d["latitude"]))
        self.lon_var.set("" if d["longitude"] is None else str(d["longitude"]))
        self.resolved_var.set(d["resolved_name"] or "Not validated yet")
        self.units_var.set(d["unit_system"] or "metric")
        self.timefmt_var.set(d["time_format"] or "24h")
        self.qr_var.set(int(d["opt_qr"]))
        self.logo_var.set(int(d["opt_logo"]))
        self.barcode_var.set(int(d["opt_barcode"]))
        self._sync_mode()

    def _save(self):
        r = self.app.location.validate(
            self.mode_var.get(), self.query_var.get(),
            self.lat_var.get(), self.lon_var.get())
        if not r.ok:
            self.app.set_status(f"Can't save — {r.message}", "warning")
            return
        self.app.repo.save({
            "printer_name": self.printer_var.get(),
            "location_mode": self.mode_var.get(),
            "location_query": self.query_var.get().strip(),
            "latitude": r.data.get("latitude"),
            "longitude": r.data.get("longitude"),
            "resolved_name": r.data.get("resolved_name", ""),
            "unit_system": self.units_var.get(),
            "time_format": self.timefmt_var.get(),
            "opt_qr": self.qr_var.get(),
            "opt_logo": self.logo_var.get(),
            "opt_barcode": self.barcode_var.get(),
        })
        self.resolved_var.set(r.data.get("resolved_name", "—"))
        self.app.set_status("Settings saved.", "success")
