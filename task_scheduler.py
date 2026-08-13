"""
TaskSchedulerService — manages Windows Task Scheduler entries.

Uses ``schtasks.exe`` to create, update, query, and remove tasks.
Each schedule gets one task named ``DailyDispatch-<id>``.

The task runs ``python run_schedule.py --schedule-id <id>`` from the
application directory.
"""

import os
import sys
import subprocess
from dataclasses import dataclass

from database import DAY_KEYS, DAY_FULL


@dataclass
class TaskResult:
    ok: bool
    message: str
    task_name: str = ""


def _app_dir() -> str:
    """Directory containing the application files."""
    return os.path.dirname(os.path.abspath(__file__))


def _python_exe() -> str:
    """Path to the Python interpreter."""
    return sys.executable


def _task_name(schedule_id: int) -> str:
    return f"DailyDispatch-{schedule_id}"


def _schtasks_days(days_csv: str) -> str:
    """Convert 'mon,tue,wed' → 'MON,TUE,WED' for schtasks /D."""
    if not days_csv:
        return ""
    selected = set(days_csv.lower().split(","))
    # Check if every day is selected — schtasks uses * for daily
    if selected == set(DAY_KEYS):
        return "*"
    return ",".join(k.upper() for k in DAY_KEYS if k in selected)


def _run_schtasks(args: list[str]) -> tuple[int, str, str]:
    """Run schtasks.exe with the given args. Returns (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["schtasks.exe"] + args,
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "schtasks.exe not found (not on Windows?)"
    except subprocess.TimeoutExpired:
        return -1, "", "schtasks.exe timed out"
    except Exception as e:
        return -1, "", str(e)


class TaskSchedulerService:
    """Create, update, query, and remove Windows scheduled tasks."""

    def create_or_update(self, schedule: dict) -> TaskResult:
        """Create or update a Windows task for the given schedule dict.
        The schedule must have: id, days, hour, minute, enabled."""
        sid = schedule.get("id")
        if not sid:
            return TaskResult(False, "Schedule has no ID.")

        days = schedule.get("days", "")
        if not days:
            return TaskResult(False, "No days selected.")

        task = _task_name(sid)
        hour = int(schedule.get("hour", 6))
        minute = int(schedule.get("minute", 0))
        time_str = f"{hour:02d}:{minute:02d}"
        sched_days = _schtasks_days(days)

        app_dir = _app_dir()
        py = _python_exe()
        runner = os.path.join(app_dir, "run_schedule.py")

        # Build the command the task will execute
        action = f'"{py}" "{runner}" --schedule-id {sid}'

        # schtasks /Create with /F to overwrite if exists
        args = [
            "/Create", "/F",
            "/TN", task,
            "/TR", action,
            "/SC", "WEEKLY",
            "/D", sched_days,
            "/ST", time_str,
            "/RL", "LIMITED",       # run with limited privileges
        ]

        rc, out, err = _run_schtasks(args)
        if rc == 0:
            return TaskResult(True,
                f"Task '{task}' created for {sched_days} at {time_str}.",
                task)

        # Common error: access denied
        detail = err or out
        if "access" in detail.lower() or "denied" in detail.lower():
            return TaskResult(False,
                f"Access denied creating task. Try running the app "
                f"as administrator, or create the task manually.", task)

        return TaskResult(False,
            f"Failed to create task '{task}': {detail}", task)

    def remove(self, task_name: str) -> TaskResult:
        """Remove a Windows scheduled task by name."""
        if not task_name:
            return TaskResult(True, "No task to remove.")

        rc, out, err = _run_schtasks(["/Delete", "/TN", task_name, "/F"])
        if rc == 0:
            return TaskResult(True, f"Task '{task_name}' removed.")
        if "does not exist" in (err + out).lower():
            return TaskResult(True, f"Task '{task_name}' already removed.")
        return TaskResult(False,
            f"Failed to remove task '{task_name}': {err or out}", task_name)

    def disable(self, task_name: str) -> TaskResult:
        """Disable a Windows scheduled task."""
        if not task_name:
            return TaskResult(True, "No task to disable.")

        rc, out, err = _run_schtasks(["/Change", "/TN", task_name, "/DISABLE"])
        if rc == 0:
            return TaskResult(True, f"Task '{task_name}' disabled.")
        return TaskResult(False,
            f"Failed to disable task '{task_name}': {err or out}", task_name)

    def enable(self, task_name: str) -> TaskResult:
        """Enable a Windows scheduled task."""
        if not task_name:
            return TaskResult(False, "No task name provided.")

        rc, out, err = _run_schtasks(["/Change", "/TN", task_name, "/ENABLE"])
        if rc == 0:
            return TaskResult(True, f"Task '{task_name}' enabled.")
        return TaskResult(False,
            f"Failed to enable task '{task_name}': {err or out}", task_name)

    def query(self, task_name: str) -> TaskResult:
        """Check if a task exists and its status."""
        if not task_name:
            return TaskResult(False, "No task name.", "")

        rc, out, err = _run_schtasks(
            ["/Query", "/TN", task_name, "/FO", "LIST", "/V"])
        if rc != 0:
            if "does not exist" in (err + out).lower():
                return TaskResult(False, "Task not found in Windows.", task_name)
            return TaskResult(False, f"Query failed: {err or out}", task_name)

        # Parse status from the verbose output
        status = "Unknown"
        next_run_time = ""
        for line in out.splitlines():
            if "Status:" in line:
                status = line.split(":", 1)[1].strip()
            if "Next Run Time:" in line:
                next_run_time = line.split(":", 1)[1].strip()

        return TaskResult(True,
            f"Task '{task_name}': {status}"
            + (f" | Next: {next_run_time}" if next_run_time else ""),
            task_name)

    def sync(self, schedule: dict, sched_repo) -> TaskResult:
        """Synchronise a schedule with Windows Task Scheduler.

        If enabled and has days: create/update the task.
        If disabled: disable or remove the task.
        Updates task_name in the database.
        """
        sid = schedule.get("id")
        enabled = schedule.get("enabled", 0)
        current_task = schedule.get("task_name", "")

        if enabled and schedule.get("days"):
            result = self.create_or_update(schedule)
            if result.ok:
                schedule["task_name"] = result.task_name
                sched_repo.save(schedule)
            return result
        else:
            # Disabled — remove the Windows task if it exists
            if current_task:
                result = self.remove(current_task)
                if result.ok:
                    schedule["task_name"] = ""
                    sched_repo.save(schedule)
                return result
            return TaskResult(True, "Schedule disabled, no task to remove.")
