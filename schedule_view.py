"""
Schedule — Phase 4+5 screen.

Manages print schedules with day toggles, time picker, and Windows
Task Scheduler integration. The "Sync" button creates/updates the
Windows task so it runs even when the GUI is closed.
"""

import tkinter as tk
import ttkbootstrap as tb

try:
    from ttkbootstrap import ScrolledFrame
except ImportError:
    from ttkbootstrap.scrolled import ScrolledFrame

import theme as T
from widgets import Card, FormRow, StatusChip, divider, run_async
from database import DAY_KEYS, DAY_LABELS, ScheduleRepository, DEFAULT_SCHEDULE
from schedule_calc import format_next_run
from task_scheduler import TaskSchedulerService
import esc_pos_renderer


class ScheduleView(tk.Frame):
    TITLE    = "Schedule"
    SUBTITLE = "Choose the days and time your briefing prints."

    def __init__(self, master, app):
        super().__init__(master, bg=T.BG)
        self.app = app
        self.sched_repo = ScheduleRepository(app.db)
        self.task_svc = TaskSchedulerService()
        self._editing_id = None

        # ── top bar ──────────────────────────────────────────────
        top = tk.Frame(self, bg=T.BG)
        top.pack(fill="x", pady=(0, T.S["md"]))

        tk.Label(top, text="Your print schedules", bg=T.BG, fg=T.MUTED,
                 font=T.F["sm"]).pack(side="left")
        tb.Button(top, text="+ New schedule", bootstyle="primary",
                  command=self._new_schedule, width=16).pack(side="right")

        # ── scrollable body ──────────────────────────────────────
        scroller = ScrolledFrame(self, autohide=True,
                                 bootstyle="secondary-round")
        scroller.pack(fill="both", expand=True)
        self._body = tk.Frame(scroller, bg=T.BG)
        self._body.pack(fill="both", expand=True)

        self._list_frame = tk.Frame(self._body, bg=T.BG)
        self._list_frame.pack(fill="x")

        self._editor_frame = tk.Frame(self._body, bg=T.BG)
        self._editor_frame.pack(fill="x")

        self._refresh_list()

    # ════════════════════════════════════════════════════════════
    #  Schedule list
    # ════════════════════════════════════════════════════════════
    def _refresh_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        schedules = self.sched_repo.list_all()
        if not schedules:
            tk.Label(self._list_frame,
                     text='No schedules yet. Press "+ New schedule" to create one.',
                     bg=T.BG, fg=T.MUTED, font=T.F["base"]).pack(
                pady=T.S["xl"])
            return

        for s in schedules:
            self._render_schedule_row(s)

    def _render_schedule_row(self, s):
        row = tk.Frame(self._list_frame, bg=T.SURFACE, bd=0,
                       highlightthickness=0)
        row.pack(fill="x", pady=(0, T.S["sm"]))

        inner = tk.Frame(row, bg=T.SURFACE)
        inner.pack(fill="x", padx=T.S["xl"], pady=T.S["lg"])

        # Left: info
        info = tk.Frame(inner, bg=T.SURFACE)
        info.pack(side="left", fill="x", expand=True)

        name_row = tk.Frame(info, bg=T.SURFACE)
        name_row.pack(fill="x")

        color = T.SUCCESS if s["enabled"] else T.MUTED
        dot = tk.Canvas(name_row, width=10, height=10, bg=T.SURFACE,
                        bd=0, highlightthickness=0)
        dot.create_oval(1, 1, 9, 9, fill=color, outline="")
        dot.pack(side="left", padx=(0, T.S["sm"]), pady=2)

        tk.Label(name_row, text=s["name"], bg=T.SURFACE, fg=T.FG,
                 font=T.F["base_bold"]).pack(side="left")

        status = "Enabled" if s["enabled"] else "Disabled"
        tk.Label(name_row, text=f"  •  {status}", bg=T.SURFACE,
                 fg=T.SUCCESS if s["enabled"] else T.MUTED,
                 font=T.F["sm"]).pack(side="left")

        # Day/time summary
        days = s.get("days", "")
        day_str = self._days_summary(days)
        time_str = f"{s['hour']:02d}:{s['minute']:02d}"
        tk.Label(info, text=f"{day_str}  at  {time_str}",
                 bg=T.SURFACE, fg=T.MUTED, font=T.F["sm"]).pack(
            anchor="w", pady=(2, 0))

        # Next run
        nxt = format_next_run(days, s["hour"], s["minute"])
        nxt_fg = T.ACCENT if s["enabled"] else T.MUTED
        tk.Label(info, text=f"Next: {nxt}", bg=T.SURFACE,
                 fg=nxt_fg, font=T.F["sm"]).pack(anchor="w")

        # Windows task sync status
        task_name = s.get("task_name", "")
        if task_name and s["enabled"]:
            sync_text = f"Task: {task_name}"
            sync_fg = T.SUCCESS
        elif s["enabled"]:
            sync_text = "Not synced to Windows"
            sync_fg = T.WARNING
        else:
            sync_text = ""
            sync_fg = T.MUTED
        if sync_text:
            tk.Label(info, text=sync_text, bg=T.SURFACE,
                     fg=sync_fg, font=T.F["xs"]).pack(anchor="w")

        # Right: action buttons
        btns = tk.Frame(inner, bg=T.SURFACE)
        btns.pack(side="right")

        tb.Button(btns, text="Edit", bootstyle="info-outline",
                  command=lambda sid=s["id"]: self._edit(sid),
                  width=6).pack(side="left", padx=(T.S["xs"], 0))
        tb.Button(btns, text="Sync", bootstyle="warning-outline",
                  command=lambda sid=s["id"]: self._sync_task(sid),
                  width=6).pack(side="left", padx=(T.S["xs"], 0))
        tb.Button(btns, text="Test", bootstyle="success-outline",
                  command=lambda sid=s["id"]: self._test_now(sid),
                  width=6).pack(side="left", padx=(T.S["xs"], 0))

    def _days_summary(self, days_csv):
        if not days_csv:
            return "No days"
        selected = set(days_csv.lower().split(","))
        weekdays = {"mon", "tue", "wed", "thu", "fri"}
        weekends = {"sat", "sun"}
        if selected == set(DAY_KEYS):
            return "Every day"
        if selected == weekdays:
            return "Weekdays"
        if selected == weekends:
            return "Weekends"
        return ", ".join(
            DAY_LABELS[i] for i, k in enumerate(DAY_KEYS) if k in selected)

    # ════════════════════════════════════════════════════════════
    #  Editor
    # ════════════════════════════════════════════════════════════
    def _new_schedule(self):
        self._open_editor(dict(DEFAULT_SCHEDULE))

    def _edit(self, schedule_id):
        s = self.sched_repo.get(schedule_id)
        if s:
            self._open_editor(s)

    def _open_editor(self, data):
        self._editing_id = data.get("id")

        for w in self._editor_frame.winfo_children():
            w.destroy()

        title = f"Edit: {data['name']}" if self._editing_id else "New schedule"
        card = Card(self._editor_frame, title)
        card.pack(fill="x", pady=(T.S["md"], T.S["lg"]))
        b = card.body

        # ── Name ──────────────────────────────────────────────
        r_name = FormRow(b, "Schedule name")
        r_name.pack(fill="x")
        self._name_var = tk.StringVar(value=data.get("name", ""))
        tb.Entry(r_name.control, textvariable=self._name_var).pack(fill="x")

        # ── Enable toggle ────────────────────────────────────
        r_enable = FormRow(b, "Status")
        r_enable.pack(fill="x", pady=(T.S["lg"], 0))
        self._enabled_var = tk.IntVar(value=int(data.get("enabled", 0)))
        tb.Checkbutton(r_enable.control, text="Schedule enabled",
                       variable=self._enabled_var,
                       bootstyle="success-round-toggle").pack(anchor="w")

        # ── Day selection ────────────────────────────────────
        r_days = FormRow(b, "Print days")
        r_days.pack(fill="x", pady=(T.S["lg"], 0))

        selected_days = set((data.get("days") or "").lower().split(","))
        selected_days.discard("")
        self._day_vars = {}

        day_grid = tk.Frame(r_days.control, bg=T.SURFACE)
        day_grid.pack(fill="x")
        for i, (key, label) in enumerate(zip(DAY_KEYS, DAY_LABELS)):
            var = tk.IntVar(value=1 if key in selected_days else 0)
            self._day_vars[key] = var
            tb.Checkbutton(day_grid, text=label, variable=var,
                           bootstyle="primary-outline-toolbutton",
                           width=5).pack(side="left",
                                         padx=(0 if i == 0 else T.S["xs"], 0))

        quick = tk.Frame(r_days.control, bg=T.SURFACE)
        quick.pack(fill="x", pady=(T.S["sm"], 0))
        for label, keys in [
            ("Weekdays", ["mon","tue","wed","thu","fri"]),
            ("Weekends", ["sat","sun"]),
            ("Every day", DAY_KEYS),
            ("Clear", []),
        ]:
            tb.Button(quick, text=label, bootstyle="secondary-outline",
                      command=lambda ks=keys: self._quick_days(ks),
                      width=10).pack(side="left", padx=(0, T.S["sm"]))

        # ── Time ─────────────────────────────────────────────
        r_time = FormRow(b, "Print time", hint="24-hour format")
        r_time.pack(fill="x", pady=(T.S["lg"], 0))

        time_frame = tk.Frame(r_time.control, bg=T.SURFACE)
        time_frame.pack(anchor="w")

        self._hour_var = tk.StringVar(value=f"{data.get('hour', 6):02d}")
        self._min_var = tk.StringVar(value=f"{data.get('minute', 0):02d}")

        tb.Spinbox(time_frame, from_=0, to=23, width=4,
                   textvariable=self._hour_var, format="%02.0f",
                   command=self._update_next).pack(side="left")
        tk.Label(time_frame, text=" : ", bg=T.SURFACE, fg=T.FG,
                 font=T.F["h2"]).pack(side="left")
        tb.Spinbox(time_frame, from_=0, to=59, width=4,
                   textvariable=self._min_var, format="%02.0f",
                   increment=5, command=self._update_next).pack(side="left")

        # ── Next run preview ─────────────────────────────────
        divider(b, pad=(T.S["lg"], T.S["lg"]))
        self._next_lbl = tk.Label(b, text="", bg=T.SURFACE, fg=T.ACCENT,
                                  font=T.F["base_bold"])
        self._next_lbl.pack(anchor="w")

        # Task sync status
        task_name = data.get("task_name", "")
        if task_name:
            tk.Label(b, text=f"Windows task: {task_name}",
                     bg=T.SURFACE, fg=T.SUCCESS, font=T.F["xs"]).pack(
                anchor="w", pady=(T.S["xs"], 0))

        self._update_next()

        # ── Action bar ───────────────────────────────────────
        divider(b, pad=(T.S["lg"], T.S["lg"]))
        actions = tk.Frame(b, bg=T.SURFACE)
        actions.pack(fill="x")

        tb.Button(actions, text="Save & sync", bootstyle="primary",
                  command=self._save_editor, width=12).pack(side="right")
        tb.Button(actions, text="Cancel", bootstyle="secondary-outline",
                  command=self._close_editor, width=10).pack(
            side="right", padx=(0, T.S["sm"]))

        if self._editing_id:
            tb.Button(actions, text="Duplicate", bootstyle="info-outline",
                      command=lambda: self._duplicate(self._editing_id),
                      width=10).pack(side="left")
            tb.Button(actions, text="Delete", bootstyle="danger-outline",
                      command=lambda: self._delete(self._editing_id),
                      width=10).pack(side="left", padx=(T.S["sm"], 0))

    def _quick_days(self, keys):
        for k, var in self._day_vars.items():
            var.set(1 if k in keys else 0)
        self._update_next()

    def _get_days_csv(self):
        return ",".join(k for k in DAY_KEYS if self._day_vars.get(k)
                        and self._day_vars[k].get())

    def _get_hour(self):
        try: return max(0, min(23, int(self._hour_var.get())))
        except ValueError: return 6

    def _get_min(self):
        try: return max(0, min(59, int(self._min_var.get())))
        except ValueError: return 0

    def _update_next(self):
        days = self._get_days_csv()
        h, m = self._get_hour(), self._get_min()
        text = format_next_run(days, h, m)
        self._next_lbl.configure(text=f"Next run:  {text}")

    # ── persistence + sync ───────────────────────────────────
    def _save_editor(self):
        name = self._name_var.get().strip()
        if not name:
            self.app.set_status("Schedule needs a name.", "warning")
            return

        days = self._get_days_csv()
        enabled = self._enabled_var.get()
        if enabled and not days:
            self.app.set_status(
                "Select at least one day before enabling.", "warning")
            return

        data = {
            "name": name,
            "enabled": enabled,
            "days": days,
            "hour": self._get_hour(),
            "minute": self._get_min(),
            "task_name": "",
        }
        if self._editing_id:
            data["id"] = self._editing_id
            old = self.sched_repo.get(self._editing_id)
            if old:
                data["task_name"] = old.get("task_name", "")

        saved = self.sched_repo.save(data)
        self.app.set_status(f'Schedule "{name}" saved.', "success")

        # Auto-sync to Windows Task Scheduler
        result = self.task_svc.sync(saved, self.sched_repo)
        if result.ok:
            if enabled and days:
                self.app.set_status(
                    f'Schedule "{name}" saved and synced to Windows.', "success")
            else:
                self.app.set_status(
                    f'Schedule "{name}" saved (disabled).', "success")
        else:
            self.app.set_status(
                f'Saved, but Windows sync failed: {result.message}', "warning")

        self._close_editor()

    def _close_editor(self):
        for w in self._editor_frame.winfo_children():
            w.destroy()
        self._editing_id = None
        self._refresh_list()

    def _delete(self, sid):
        s = self.sched_repo.get(sid)
        if s:
            # Remove Windows task first
            task = s.get("task_name", "")
            if task:
                self.task_svc.remove(task)
            self.sched_repo.delete(sid)
            self.app.set_status(
                f'Schedule "{s["name"]}" deleted.', "success")
        self._close_editor()

    def _duplicate(self, sid):
        result = self.sched_repo.duplicate(sid)
        if result:
            self.app.set_status(
                f'Duplicated as "{result["name"]}".', "success")
            self._close_editor()

    # ── sync button on list rows ─────────────────────────────
    def _sync_task(self, sid):
        s = self.sched_repo.get(sid)
        if not s:
            return
        result = self.task_svc.sync(s, self.sched_repo)
        if result.ok:
            self.app.set_status(result.message, "success")
        else:
            self.app.set_status(result.message, "warning")
        self._refresh_list()

    # ── test now ─────────────────────────────────────────────
    def _test_now(self, sid):
        s = self.sched_repo.get(sid)
        if not s:
            return

        settings = self.app.repo.load()
        loc = (settings.get("location_query")
               or settings.get("resolved_name") or "")
        printer = settings.get("printer_name", "")

        if not loc:
            self.app.set_status(
                "No location configured. Go to Settings.", "warning")
            return
        if not printer:
            self.app.set_status(
                "No printer configured. Go to Settings.", "warning")
            return

        self.app.set_status(
            f'Testing "{s["name"]}" — fetching weather…', "info")

        unit = settings.get("unit_system", "metric")

        def work():
            from weather_service import WeatherService
            ws = WeatherService()
            result = ws.fetch(loc, unit)
            if not result.ok:
                return result, None, 0
            fc = result.forecast
            payload = esc_pos_renderer.render(fc, settings)
            pr = self.app.printer.send_print(printer, payload)
            return result, pr, len(payload)

        def done(result, error):
            if error:
                self.app.set_status(f"Test failed: {error}", "danger")
                return
            fetch_result, print_result, size = result
            if not fetch_result.ok:
                self.app.set_status(
                    f"Weather fetch failed: {fetch_result.message}", "danger")
                return
            if print_result and print_result.ok:
                self.app.set_status(
                    f'Test print OK — {size} bytes to {printer}.', "success")
                self.app.set_printer_status(True, printer)
            elif print_result:
                self.app.set_status(print_result.message, "danger")
                self.app.set_printer_status(False, printer)

        run_async(self.app.root, work, done)
