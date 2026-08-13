"""
Headless runner — the entry point Windows Task Scheduler calls.

Usage:
    python run_schedule.py --schedule-id <id>
    python run_schedule.py --schedule-id <id> --dry-run

Loads saved settings, fetches weather, renders to ESC/POS, sends to the
configured printer, and exits. No GUI is opened. Shares the same services
as the GUI — no duplicate weather or printing logic.
"""

import argparse
import sys
import os
from datetime import datetime

# Ensure imports work when run from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database, SettingsRepository, ScheduleRepository
from weather_service import WeatherService
from printer_service import PrinterService
import esc_pos_renderer


def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def run(schedule_id: int, dry_run: bool = False) -> int:
    """Execute a scheduled print. Returns 0 on success, 1 on failure."""
    log(f"Daily Dispatch headless runner — schedule {schedule_id}")

    db = Database()
    settings = SettingsRepository(db).load()
    sched_repo = ScheduleRepository(db)
    schedule = sched_repo.get(schedule_id)

    if not schedule:
        log(f"ERROR: Schedule {schedule_id} not found.")
        db.close()
        return 1

    if not schedule["enabled"]:
        log(f"Schedule '{schedule['name']}' is disabled. Skipping.")
        db.close()
        return 0

    # Validate configuration
    location = (settings.get("location_query")
                or settings.get("resolved_name") or "")
    printer = settings.get("printer_name", "")

    if not location:
        log("ERROR: No location configured in settings.")
        db.close()
        return 1
    if not printer:
        log("ERROR: No printer configured in settings.")
        db.close()
        return 1

    log(f"Schedule: '{schedule['name']}' | Location: {location} | "
        f"Printer: {printer}")

    # Fetch weather
    ws = WeatherService()
    unit = settings.get("unit_system", "metric")
    log("Fetching weather…")
    result = ws.fetch(location, unit)

    if not result.ok:
        log(f"ERROR: Weather fetch failed — {result.message}")
        db.close()
        return 1

    fc = result.forecast
    log(f"Forecast for {fc.location} "
        f"({'cached' if fc.is_cached else 'live'})")

    # Render ESC/POS
    payload = esc_pos_renderer.render(fc, settings)
    log(f"Rendered {len(payload)} bytes of ESC/POS")

    if dry_run:
        log("DRY RUN — skipping actual print.")
        db.close()
        return 0

    # Print
    ps = PrinterService()
    log(f"Sending to '{printer}'…")
    pr = ps.send_print(printer, payload)

    if pr.ok:
        log(f"SUCCESS: {pr.message}")
        db.close()
        return 0
    else:
        log(f"ERROR: {pr.message}")
        db.close()
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Daily Dispatch — headless scheduled print runner")
    parser.add_argument("--schedule-id", type=int, required=True,
                        help="ID of the schedule to execute")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and render but don't print")
    args = parser.parse_args()
    sys.exit(run(args.schedule_id, args.dry_run))


if __name__ == "__main__":
    main()
