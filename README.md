# Daily Dispatch

A Windows desktop app that fetches weather, formats it as a compact
daily briefing, and prints it to a POS-58 thermal printer on a schedule.

## Running it

```
pip install -r requirements.txt
python app.py
```

## What works (through Phase 5)

- **Briefing**: fetch live weather, preview, and Print Now
- **Schedule**: create multiple schedules with day/time selection,
  and **sync to Windows Task Scheduler** so they run when the GUI is closed
- **Settings**: printer, location, units, report options — persisted to SQLite
- **Headless runner**: `python run_schedule.py --schedule-id <id>` fetches
  weather + prints without opening the GUI (this is what Task Scheduler calls)
- **History**: placeholder (Phase 6)

## How scheduling works

1. Create a schedule in the Schedule tab (pick days, time, enable it)
2. Click **Save & sync** — this creates a Windows Task Scheduler entry
3. The task runs `python run_schedule.py --schedule-id <id>` at the
   configured time, even when the GUI is closed
4. The computer must be powered on or sleeping in a wakeable state

You can also click **Sync** on any schedule row to push changes to
Windows, or **Test** to do an immediate fetch + print.

## Files

```
app.py                Application shell / entry point
theme.py              Palette, spacing, fonts, ttkbootstrap theme
widgets.py            Card, FormRow, StatusChip, divider, run_async
briefing_view.py      Weather preview + Print Now
schedule_view.py      Schedule list + editor + Task Scheduler sync
schedule_calc.py      Next-run calculator
task_scheduler.py     Windows Task Scheduler via schtasks.exe
run_schedule.py       Headless runner (Task Scheduler entry point)
settings_view.py      Printer, location, and report options
placeholders.py       Empty-state view for History
weather_service.py    Visual Crossing API + Forecast model + cache
esc_pos_renderer.py   Forecast → ESC/POS byte payload
printer_service.py    Enumerate printers + RAW spooler
location_service.py   Validate / normalise location input
database.py           SQLite + Settings/Schedule repositories
requirements.txt      Dependencies
```

## Roadmap

| Phase | Status | Adds |
|------:|--------|------|
| 1 | ✅ | GUI shell + settings |
| 2 | ✅ | Live weather fetch + preview |
| 3 | ✅ | Print Now |
| 4 | ✅ | Weekday/time scheduler |
| 5 | ✅ | Windows Task Scheduler integration |
| 6 | | Print history and error logging |
