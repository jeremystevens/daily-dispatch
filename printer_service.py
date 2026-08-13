"""
PrinterService — the only module that talks to the Windows print spooler.

On Windows it uses pywin32 (win32print) and the RAW spooler path verified
with the POS-58 hardware. On other platforms it degrades gracefully to a
simulated mode so the GUI can run anywhere.
"""

from dataclasses import dataclass
from datetime import datetime

try:
    import win32print          # type: ignore
    WIN32 = True
except Exception:
    win32print = None
    WIN32 = False

ESC, GS = b"\x1b", b"\x1d"


@dataclass
class PrintResult:
    ok: bool
    message: str


def _test_receipt(name: str) -> bytes:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        ESC + b"@"               # init
        + ESC + b"a\x01"         # centre
        + GS  + b"!\x11"         # double w+h
        + b"DAILY DISPATCH\n"
        + GS  + b"!\x00"         # normal
        + b"PRINTER TEST\n"
        + b"========================\n"
        + ESC + b"a\x00"         # left
        + ESC + b"M\x01"         # Font B
        + f"Printer : {name}\n".encode("ascii", "replace")
        + f"Time    : {stamp}\n".encode("ascii", "replace")
        + b"Status  : Connection OK\n"
        + ESC + b"M\x00"         # Font A
        + ESC + b"a\x01"         # centre
        + b"------------------------\n"
        + b"Ready for briefings\n"
        + b"\n\n\n"              # feed for tearing
    )


class PrinterService:

    def list_printers(self) -> list[str]:
        if WIN32:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            return [p[2] for p in win32print.EnumPrinters(flags)]
        return ["POS-58", "Microsoft Print to PDF", "OneNote (Desktop)"]

    def default_printer_name(self, names: list[str]) -> str:
        for n in names:
            if "pos-58" in n.lower().replace(" ", ""):
                return n
        if WIN32:
            try:
                d = win32print.GetDefaultPrinter()
                if d in names:
                    return d
            except Exception:
                pass
        return names[0] if names else ""

    def send_raw(self, printer_name: str, payload: bytes) -> int:
        h = win32print.OpenPrinter(printer_name)
        js = ps = False
        try:
            win32print.StartDocPrinter(h, 1, ("Daily Dispatch", None, "RAW"))
            js = True
            win32print.StartPagePrinter(h)
            ps = True
            return win32print.WritePrinter(h, payload)
        finally:
            if ps: win32print.EndPagePrinter(h)
            if js: win32print.EndDocPrinter(h)
            win32print.ClosePrinter(h)

    def test_print(self, printer_name: str) -> PrintResult:
        if not printer_name:
            return PrintResult(False, "No printer selected.")
        payload = _test_receipt(printer_name)
        if not WIN32:
            return PrintResult(True,
                f"Simulated test for '{printer_name}' ({len(payload)} bytes). "
                "Live printing requires Windows + pywin32.")
        try:
            n = self.send_raw(printer_name, payload)
            return PrintResult(True, f"Test sent to '{printer_name}' ({n} bytes).")
        except Exception as exc:
            return PrintResult(False,
                f"Could not print to '{printer_name}'. "
                f"Is it connected and powered on? ({exc})")

    def send_print(self, printer_name: str, payload: bytes) -> PrintResult:
        """Send an arbitrary ESC/POS payload. Never raises."""
        if not printer_name:
            return PrintResult(False, "No printer selected.")
        if not WIN32:
            return PrintResult(True,
                f"Simulated print to '{printer_name}' ({len(payload)} bytes). "
                "Live printing requires Windows + pywin32.")
        try:
            n = self.send_raw(printer_name, payload)
            return PrintResult(True,
                f"Briefing sent to '{printer_name}' ({n} bytes).")
        except Exception as exc:
            return PrintResult(False,
                f"Could not print to '{printer_name}'. "
                f"Is it connected and powered on? ({exc})")
