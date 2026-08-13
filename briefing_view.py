"""
Briefing — weather preview + Print Now screen (Phase 3).

Fetches live weather via WeatherService and displays it in a compact
paper-width preview. The Print Now button renders the forecast to ESC/POS
and sends it to the configured printer on a background thread.
"""

import tkinter as tk
import ttkbootstrap as tb
from datetime import datetime

try:
    from ttkbootstrap import ScrolledFrame
except ImportError:
    from ttkbootstrap.scrolled import ScrolledFrame

import theme as T
from widgets import Card, FormRow, StatusChip, divider, run_async
from weather_service import WeatherService, Forecast, wind_compass
import esc_pos_renderer


# ── Condition icon mapping (Unicode glyphs for the preview) ─────────────
_ICON_MAP = {
    "clear-day": "☀",  "clear-night": "☾",
    "partly-cloudy-day": "⛅", "partly-cloudy-night": "☁",
    "cloudy": "☁",  "rain": "🌧",  "showers-day": "🌦",
    "showers-night": "🌧",  "snow": "❄",  "snow-showers-day": "🌨",
    "snow-showers-night": "🌨",  "thunder-rain": "⛈",
    "thunder-showers-day": "⛈",  "fog": "🌫",  "wind": "💨",
}

def _icon(code): return _ICON_MAP.get(code, "•")
def _deg(ug):    return "°F" if ug == "us" else "°C"
def _speed(ug):  return "mph" if ug == "us" else "km/h"
def _pru(ug):    return "in" if ug == "us" else "mm"


class BriefingView(tk.Frame):
    TITLE    = "Briefing"
    SUBTITLE = "Fetch, preview, and print your weather dispatch."

    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app
        self.weather = WeatherService()
        self._forecast = None

        # ── top bar: status + actions ────────────────────────────
        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", pady=(0, T.S["md"]))

        self.fetch_chip = StatusChip(top, "No data yet", T.MUTED, T.BG)
        self.fetch_chip._lbl.configure(bg=T.BG)
        self.fetch_chip._dot.configure(bg=T.BG)
        self.fetch_chip.configure(bg=T.BG)
        self.fetch_chip.pack(side="left")

        # Print Now (disabled until a forecast is loaded)
        self.print_btn = tb.Button(
            top, text="Print now", bootstyle="success",
            command=self._do_print, width=12, state="disabled")
        self.print_btn.pack(side="right", padx=(T.S["sm"], 0))

        self.refresh_btn = tb.Button(
            top, text="Fetch forecast", bootstyle="primary",
            command=self._do_fetch, width=16)
        self.refresh_btn.pack(side="right")

        # ── scrollable preview area ──────────────────────────────
        scroller = ScrolledFrame(self, autohide=True,
                                 bootstyle="secondary-round")
        scroller.pack(fill="both", expand=True)
        self._preview_parent = tk.Frame(scroller, bg=T.BG)
        self._preview_parent.pack(fill="both", expand=True)

        self._empty = tk.Label(
            self._preview_parent,
            text='Press "Fetch forecast" to load weather data.',
            bg=T.BG, fg=T.MUTED, font=T.F["base"])
        self._empty.pack(pady=T.S["xxl"])

    # ════════════════════════════════════════════════════════════
    #  Fetch
    # ════════════════════════════════════════════════════════════
    def _do_fetch(self):
        settings = self.app.repo.load()
        loc = (settings.get("location_query")
               or settings.get("resolved_name") or "")
        if not loc:
            self.app.set_status(
                "No location set. Go to Settings first.", "warning")
            return

        self.refresh_btn.configure(state="disabled", text="Fetching…")
        self.print_btn.configure(state="disabled")
        self.fetch_chip.set("Fetching forecast…", T.WARNING)
        self.app.set_status("Fetching weather…", "info")
        unit = settings.get("unit_system", "metric")

        def work():
            return self.weather.fetch(loc, unit)

        def done(result, error):
            self.refresh_btn.configure(state="normal", text="Refresh")
            if error:
                self.fetch_chip.set("Fetch failed", T.DANGER)
                self.app.set_status(f"Error: {error}", "danger")
                return
            if not result.ok:
                self.fetch_chip.set("Fetch failed", T.DANGER)
                self.app.set_status(result.message, "danger")
                return

            self._forecast = result.forecast
            fc = result.forecast
            if fc.is_cached:
                self.fetch_chip.set(
                    f"Cached — {fc.fetched_at}", T.WARNING)
            else:
                self.fetch_chip.set(
                    f"Live — {fc.fetched_at}", T.SUCCESS)
            self.app.set_status(result.message, "success")
            self.print_btn.configure(state="normal")
            self._render_preview(fc)

        run_async(self.app.root, work, done)

    # ════════════════════════════════════════════════════════════
    #  Print Now
    # ════════════════════════════════════════════════════════════
    def _do_print(self):
        if not self._forecast:
            self.app.set_status("Fetch a forecast first.", "warning")
            return

        settings = self.app.repo.load()
        printer_name = settings.get("printer_name") or ""
        if not printer_name:
            self.app.set_status(
                "No printer configured. Go to Settings.", "warning")
            return

        fc = self._forecast
        self.print_btn.configure(state="disabled", text="Printing…")
        self.app.set_status(
            f"Rendering and sending to {printer_name}…", "info")

        def work():
            payload = esc_pos_renderer.render(fc, settings)
            result = self.app.printer.send_print(printer_name, payload)
            return result, len(payload)

        def done(result, error):
            self.print_btn.configure(state="normal", text="Print now")
            if error:
                self.app.set_status(
                    f"Print failed: {error}", "danger")
                self.app.set_printer_status(False, printer_name)
                return
            pr, size = result
            if pr.ok:
                self.app.set_status(
                    f"Printed {size} bytes to {printer_name}.", "success")
                self.app.set_printer_status(True, printer_name)
            else:
                self.app.set_status(pr.message, "danger")
                self.app.set_printer_status(False, printer_name)

        run_async(self.app.root, work, done)

    # ════════════════════════════════════════════════════════════
    #  Preview renderer
    # ════════════════════════════════════════════════════════════
    def _render_preview(self, fc: Forecast):
        for w in self._preview_parent.winfo_children():
            w.destroy()

        parent = self._preview_parent
        deg = _deg(fc.unit_group)
        spd = _speed(fc.unit_group)
        pru = _pru(fc.unit_group)

        # ── Header card ──────────────────────────────────────────
        hdr = Card(parent, "Daily Dispatch — Weather Briefing")
        hdr.pack(fill="x", pady=(0, T.S["md"]))
        b = hdr.body
        tk.Label(b, text=fc.location, bg=T.SURFACE, fg=T.ACCENT,
                 font=T.F["h2"], anchor="w").pack(fill="x")
        meta = f"{fc.timezone}  •  Retrieved {fc.fetched_at}"
        if fc.is_cached:
            meta += "  (CACHED)"
        tk.Label(b, text=meta, bg=T.SURFACE, fg=T.MUTED,
                 font=T.F["xs"], anchor="w").pack(fill="x", pady=(2, 0))

        # ── Current conditions card ──────────────────────────────
        if fc.current:
            cc = fc.current
            cur_card = Card(parent, "Current conditions")
            cur_card.pack(fill="x", pady=(0, T.S["md"]))
            cb = cur_card.body

            temp_row = tk.Frame(cb, bg=T.SURFACE)
            temp_row.pack(fill="x")
            tk.Label(temp_row, text=f"{_icon(cc.icon)}  {cc.temp:.0f}{deg}",
                     bg=T.SURFACE, fg=T.FG,
                     font=T.F["h1"], anchor="w").pack(side="left")
            right_col = tk.Frame(temp_row, bg=T.SURFACE)
            right_col.pack(side="right")
            tk.Label(right_col, text=cc.conditions, bg=T.SURFACE,
                     fg=T.FG, font=T.F["base_bold"],
                     anchor="e").pack(fill="x")
            tk.Label(right_col, text=f"Feels like {cc.feels_like:.0f}{deg}",
                     bg=T.SURFACE, fg=T.MUTED, font=T.F["sm"],
                     anchor="e").pack(fill="x")

            divider(cb, pad=(T.S["md"], T.S["md"]))

            details = tk.Frame(cb, bg=T.SURFACE)
            details.pack(fill="x")
            details.columnconfigure((0, 1, 2), weight=1)
            items = [
                ("Wind", f"{cc.wind_speed:.0f} {spd} {wind_compass(cc.wind_dir)}"),
                ("Humidity", f"{cc.humidity:.0f}%"),
                ("Precip", f"{cc.precip_prob:.0f}%"),
                ("Pressure", f"{cc.pressure:.0f} hPa"),
                ("UV Index", f"{cc.uv_index}"),
                ("Cloud cover", f"{cc.cloud_cover:.0f}%"),
            ]
            for i, (label, val) in enumerate(items):
                r, c = divmod(i, 3)
                cell = tk.Frame(details, bg=T.SURFACE)
                cell.grid(row=r, column=c, sticky="w",
                          padx=(0, T.S["lg"]), pady=T.S["xs"])
                tk.Label(cell, text=label, bg=T.SURFACE, fg=T.MUTED,
                         font=T.F["xs"]).pack(anchor="w")
                tk.Label(cell, text=val, bg=T.SURFACE, fg=T.FG,
                         font=T.F["base_bold"]).pack(anchor="w")

        # ── Today summary card ───────────────────────────────────
        if fc.today:
            td = fc.today
            day_card = Card(parent, f"Today — {td.date}", td.description)
            day_card.pack(fill="x", pady=(0, T.S["md"]))
            db = day_card.body

            summary = tk.Frame(db, bg=T.SURFACE)
            summary.pack(fill="x")
            summary.columnconfigure((0, 1, 2, 3), weight=1)
            for c, (label, val) in enumerate([
                ("High", f"{td.temp_max:.0f}{deg}"),
                ("Low", f"{td.temp_min:.0f}{deg}"),
                ("Precip", f"{td.precip_prob:.0f}%  ({td.precip:.2f} {pru})"),
                ("Wind", f"{td.wind_speed:.0f} {spd} {wind_compass(td.wind_dir)}"),
            ]):
                cell = tk.Frame(summary, bg=T.SURFACE)
                cell.grid(row=0, column=c, sticky="w",
                          padx=(0, T.S["md"]), pady=T.S["xs"])
                tk.Label(cell, text=label, bg=T.SURFACE, fg=T.MUTED,
                         font=T.F["xs"]).pack(anchor="w")
                tk.Label(cell, text=val, bg=T.SURFACE, fg=T.FG,
                         font=T.F["base_bold"]).pack(anchor="w")

            divider(db, pad=(T.S["md"], T.S["md"]))

            sun_row = tk.Frame(db, bg=T.SURFACE)
            sun_row.pack(fill="x")
            sun_row.columnconfigure((0, 1, 2, 3), weight=1)
            for c, (label, val) in enumerate([
                ("Sunrise", f"☀  {td.sunrise}"),
                ("Sunset", f"☾  {td.sunset}"),
                ("UV Index", str(td.uv_index)),
                ("Cloud cover", f"{td.cloud_cover:.0f}%"),
            ]):
                cell = tk.Frame(sun_row, bg=T.SURFACE)
                cell.grid(row=0, column=c, sticky="w",
                          padx=(0, T.S["md"]), pady=T.S["xs"])
                tk.Label(cell, text=label, bg=T.SURFACE, fg=T.MUTED,
                         font=T.F["xs"]).pack(anchor="w")
                tk.Label(cell, text=val, bg=T.SURFACE, fg=T.FG,
                         font=T.F["base"]).pack(anchor="w")

        # ── Hourly forecast card ─────────────────────────────────
        if fc.today and fc.today.hours:
            hr_card = Card(parent, "Hourly forecast")
            hr_card.pack(fill="x", pady=(0, T.S["md"]))
            hb = hr_card.body

            hdr_frame = tk.Frame(hb, bg=T.SURFACE)
            hdr_frame.pack(fill="x")
            for label, w in [("Time",7),("",3),("Temp",7),("Feels",7),
                             ("Precip",6),("Wind",12),("Conditions",18)]:
                tk.Label(hdr_frame, text=label, bg=T.SURFACE, fg=T.MUTED,
                         font=T.F["xs"], width=w, anchor="w").pack(side="left")
            divider(hb, pad=(T.S["xs"], T.S["xs"]))

            now_h = datetime.now().hour
            key_hours = sorted(set(
                [0, 3, 6, 9, 12, 15, 18, 21] +
                [max(0, now_h), min(23, now_h + 1)]))

            for h in fc.today.hours:
                hour_num = int(h.time.split(":")[0])
                if hour_num not in key_hours:
                    continue
                fg = T.ACCENT if hour_num == now_h else T.FG
                row = tk.Frame(hb, bg=T.SURFACE)
                row.pack(fill="x", pady=1)
                for val, w in [
                    (h.time,7), (_icon(h.icon),3),
                    (f"{h.temp:.0f}{deg}",7), (f"{h.feels_like:.0f}{deg}",7),
                    (f"{h.precip_prob:.0f}%",6),
                    (f"{h.wind_speed:.0f} {spd} {wind_compass(h.wind_dir)}",12),
                    (h.conditions,18),
                ]:
                    tk.Label(row, text=val, bg=T.SURFACE, fg=fg,
                             font=T.F["mono"] if val==h.time else T.F["sm"],
                             width=w, anchor="w").pack(side="left")

        # ── Tomorrow teaser card ─────────────────────────────────
        if fc.tomorrow:
            tm = fc.tomorrow
            tom_card = Card(parent, f"Tomorrow — {tm.date}",
                            tm.description or tm.conditions)
            tom_card.pack(fill="x", pady=(0, T.S["lg"]))
            tb2 = tom_card.body
            tom_s = tk.Frame(tb2, bg=T.SURFACE)
            tom_s.pack(fill="x")
            tom_s.columnconfigure((0, 1, 2, 3), weight=1)
            for c, (label, val) in enumerate([
                ("High", f"{tm.temp_max:.0f}{deg}"),
                ("Low", f"{tm.temp_min:.0f}{deg}"),
                ("Precip", f"{tm.precip_prob:.0f}%"),
                ("Wind", f"{tm.wind_speed:.0f} {spd}"),
            ]):
                cell = tk.Frame(tom_s, bg=T.SURFACE)
                cell.grid(row=0, column=c, sticky="w",
                          padx=(0, T.S["md"]), pady=T.S["xs"])
                tk.Label(cell, text=label, bg=T.SURFACE, fg=T.MUTED,
                         font=T.F["xs"]).pack(anchor="w")
                tk.Label(cell, text=val, bg=T.SURFACE, fg=T.FG,
                         font=T.F["base_bold"]).pack(anchor="w")
