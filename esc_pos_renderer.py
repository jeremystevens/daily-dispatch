"""
EscPosRenderer — turns a Forecast into a byte payload for the POS-58.

Uses the ESC/POS command subset verified on the hardware:
  ESC @        initialise
  ESC a n      alignment (0=left, 1=centre, 2=right)
  GS ! n       character size (bit 0-3 width, 4-7 height; 0x11 = double both)
  ESC E n      bold on/off
  ESC M n      font select (0=A 12×24, 1=B 9×17)
  ESC - n      underline on/off

POS-58 printable width: 32 chars Font A, 42 chars Font B.
"""

from datetime import datetime
from weather_service import Forecast, wind_compass

ESC = b"\x1b"
GS  = b"\x1d"

# POS-58 column widths
COLS_A = 32   # Font A characters per line
COLS_B = 42   # Font B characters per line


def _init():
    return ESC + b"@"

def _centre():
    return ESC + b"a\x01"

def _left():
    return ESC + b"a\x00"

def _bold(on=True):
    return ESC + b"E\x01" if on else ESC + b"E\x00"

def _underline(on=True):
    return ESC + b"-\x01" if on else ESC + b"-\x00"

def _double():
    return GS + b"!\x11"

def _normal():
    return GS + b"!\x00"

def _font_a():
    return ESC + b"M\x00"

def _font_b():
    return ESC + b"M\x01"

def _feed(lines=3):
    return b"\n" * lines

def _line_a(char="="):
    return (char * COLS_A).encode("ascii") + b"\n"

def _line_b(char="-"):
    return (char * COLS_B).encode("ascii") + b"\n"

def _text(s: str) -> bytes:
    return s.encode("ascii", "replace")

def _row_b(left: str, right: str) -> bytes:
    """A two-column row in Font B: left-aligned label, right-aligned value.
    Always exactly COLS_B characters wide."""
    # Truncate right side if both together can't fit
    max_right = COLS_B - len(left) - 1
    if len(right) > max_right:
        right = right[:max_right]
    gap = COLS_B - len(left) - len(right)
    return _text(left + " " * gap + right + "\n")


def render(fc: Forecast, settings: dict | None = None) -> bytes:
    """Build the complete ESC/POS byte payload for a weather briefing."""
    settings = settings or {}
    ug = fc.unit_group
    deg = "F" if ug == "us" else "C"
    spd = "mph" if ug == "us" else "km/h"
    pru = "in" if ug == "us" else "mm"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    out = bytearray()
    out += _init()

    # ── Header ───────────────────────────────────────────────────
    out += _centre()
    out += _double()
    out += _text("DAILY DISPATCH\n")
    out += _normal()
    out += _text("WEATHER BRIEFING\n")
    out += _font_a()
    out += _line_a("=")
    out += _left()

    # ── Location + timestamp ─────────────────────────────────────
    out += _font_b()
    out += _bold()
    loc = fc.location
    # Wrap long location names to Font B width at word boundaries
    while loc:
        if len(loc) <= COLS_B:
            out += _text(loc + "\n")
            break
        split = loc[:COLS_B].rfind(",")
        if split < 10:
            split = loc[:COLS_B].rfind(" ")
        if split < 5:
            split = COLS_B
        out += _text(loc[:split].rstrip() + "\n")
        loc = loc[split:].lstrip(", ")
    out += _bold(False)
    out += _text(f"Printed  {stamp}\n")
    fetched = fc.fetched_at[:26]  # cap timestamp length
    out += _text(f"Fetched  {fetched}\n")
    if fc.is_cached:
        out += _text("** CACHED DATA **\n")
    out += _line_b("-")

    # ── Current conditions ───────────────────────────────────────
    if fc.current:
        cc = fc.current
        out += _font_a()
        out += _bold()
        out += _text("CURRENT CONDITIONS\n")
        out += _bold(False)
        out += _font_b()
        out += _row_b("Temperature", f"{cc.temp:.0f}{deg}")
        out += _row_b("Feels like", f"{cc.feels_like:.0f}{deg}")
        out += _row_b("Conditions", cc.conditions[:24])
        out += _row_b("Humidity", f"{cc.humidity:.0f}%")
        out += _row_b("Wind",
            f"{cc.wind_speed:.0f} {spd} {wind_compass(cc.wind_dir)}")
        if cc.wind_gust:
            out += _row_b("Gusts", f"{cc.wind_gust:.0f} {spd}")
        out += _row_b("Pressure", f"{cc.pressure:.0f} hPa")
        out += _row_b("UV Index", str(cc.uv_index))
        out += _row_b("Precip chance", f"{cc.precip_prob:.0f}%")
        out += _line_b("-")

    # ── Today summary ────────────────────────────────────────────
    if fc.today:
        td = fc.today
        out += _font_a()
        out += _bold()
        out += _text(f"TODAY  {td.date}\n")
        out += _bold(False)
        out += _font_b()

        out += _row_b("High / Low", f"{td.temp_max:.0f} / {td.temp_min:.0f}{deg}")
        out += _row_b("Precip",
            f"{td.precip_prob:.0f}% ({td.precip:.2f} {pru})")
        if td.precip_types:
            out += _row_b("Type", ", ".join(td.precip_types[:3]))
        out += _row_b("Wind",
            f"{td.wind_speed:.0f} {spd} {wind_compass(td.wind_dir)}")
        if td.wind_gust:
            out += _row_b("Gusts", f"{td.wind_gust:.0f} {spd}")
        out += _row_b("Sunrise / Sunset", f"{td.sunrise} / {td.sunset}")
        out += _row_b("UV Index", str(td.uv_index))

        # Description
        if td.description:
            out += _text("\n")
            desc = td.description
            # Word-wrap to Font B width
            while desc:
                if len(desc) <= COLS_B:
                    out += _text(desc + "\n")
                    break
                split = desc[:COLS_B].rfind(" ")
                if split < 10:
                    split = COLS_B
                out += _text(desc[:split].rstrip() + "\n")
                desc = desc[split:].lstrip()
        out += _line_b("-")

    # ── Hourly forecast (key hours) ──────────────────────────────
    if fc.today and fc.today.hours:
        out += _font_a()
        out += _bold()
        out += _text("HOURLY FORECAST\n")
        out += _bold(False)
        out += _font_b()

        # Header row
        hdr = f"{'Time':<6}{'Temp':>5} {'Prcp':>4} {'Wind':>8}  {'Cond'}"
        out += _underline()
        out += _text(hdr[:COLS_B] + "\n")
        out += _underline(False)

        key_hours = [0, 3, 6, 9, 12, 15, 18, 21]
        for h in fc.today.hours:
            hour_num = int(h.time.split(":")[0])
            if hour_num not in key_hours:
                continue
            cond = h.conditions[:12]
            line = (f"{h.time:<6}"
                    f"{h.temp:>4.0f}{deg} "
                    f"{h.precip_prob:>3.0f}% "
                    f"{h.wind_speed:>3.0f}{spd[:1]:>1}"
                    f" {wind_compass(h.wind_dir):<3}"
                    f"  {cond}")
            out += _text(line[:COLS_B] + "\n")
        out += _line_b("-")

    # ── Tomorrow teaser ──────────────────────────────────────────
    if fc.tomorrow:
        tm = fc.tomorrow
        out += _font_a()
        out += _bold()
        out += _text(f"TOMORROW  {tm.date}\n")
        out += _bold(False)
        out += _font_b()
        out += _row_b("High / Low", f"{tm.temp_max:.0f} / {tm.temp_min:.0f}{deg}")
        out += _row_b("Precip", f"{tm.precip_prob:.0f}%")
        out += _row_b("Conditions", tm.conditions[:28])
        out += _line_b("-")

    # ── Footer ───────────────────────────────────────────────────
    out += _font_b()
    out += _centre()
    out += _text("Daily Dispatch v1.0\n")
    out += _text(f"{fc.timezone}\n")
    out += _left()
    out += _font_a()

    # Paper feed for safe tearing
    out += _feed(4)

    return bytes(out)
