"""
WeatherService — fetches, normalises, and caches weather data.

Uses the Visual Crossing Timeline API. The Forecast data model is
provider-neutral so the GUI and (later) the printer never depend on a
particular API's response shape.

The API key is loaded from the environment variable DISPATCH_WEATHER_KEY,
falling back to a built-in default for convenience during early development.
"""

import json, os, time, urllib.request, urllib.parse, urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ── API key ──────────────────────────────────────────────────────────────
_DEFAULT_KEY = "MX6LV98NZXW4BCQZBAV5WASH3"

def _api_key() -> str:
    return os.environ.get("DISPATCH_WEATHER_KEY", _DEFAULT_KEY)

# ── Provider-neutral forecast model ─────────────────────────────────────

@dataclass
class HourForecast:
    time: str              # "06:00", "14:00"
    temp: float
    feels_like: float
    humidity: float
    precip: float          # inches or mm
    precip_prob: float     # 0-100
    wind_speed: float
    wind_dir: int          # degrees
    conditions: str
    icon: str

@dataclass
class DayForecast:
    date: str              # "2026-08-13"
    temp_max: float
    temp_min: float
    temp_avg: float
    feels_like_max: float
    humidity: float
    precip: float
    precip_prob: float
    precip_types: list
    wind_speed: float
    wind_gust: float
    wind_dir: int
    pressure: float
    cloud_cover: float
    uv_index: int
    sunrise: str           # "05:52"
    sunset: str            # "19:58"
    moon_phase: float
    conditions: str
    description: str
    icon: str
    hours: list            # list[HourForecast]

@dataclass
class CurrentConditions:
    time: str
    temp: float
    feels_like: float
    humidity: float
    precip: float
    precip_prob: float
    wind_speed: float
    wind_gust: float
    wind_dir: int
    pressure: float
    cloud_cover: float
    uv_index: int
    conditions: str
    icon: str

@dataclass
class Forecast:
    location: str          # resolved address
    latitude: float
    longitude: float
    timezone: str
    fetched_at: str        # ISO timestamp of when we fetched
    unit_group: str        # "us" or "metric"
    current: CurrentConditions | None
    today: DayForecast | None
    tomorrow: DayForecast | None
    is_cached: bool = False

@dataclass
class FetchResult:
    ok: bool
    forecast: Forecast | None = None
    message: str = ""

# ── Wind direction helper ───────────────────────────────────────────────
_DIRS = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
         "S","SSW","SW","WSW","W","WNW","NW","NNW"]

def wind_compass(deg: int | float) -> str:
    if deg is None:
        return "—"
    return _DIRS[int((float(deg) + 11.25) / 22.5) % 16]

def _fmt_time(t: str) -> str:
    """'05:52:18' → '05:52'"""
    if t and len(t) >= 5:
        return t[:5]
    return t or "—"

# ── Normaliser ──────────────────────────────────────────────────────────

def _parse_hour(h: dict) -> HourForecast:
    return HourForecast(
        time=_fmt_time(h.get("datetime", "")),
        temp=h.get("temp", 0),
        feels_like=h.get("feelslike", 0),
        humidity=h.get("humidity", 0),
        precip=h.get("precip", 0) or 0,
        precip_prob=h.get("precipprob", 0) or 0,
        wind_speed=h.get("windspeed", 0) or 0,
        wind_dir=int(h.get("winddir", 0) or 0),
        conditions=h.get("conditions", ""),
        icon=h.get("icon", ""),
    )

def _parse_day(d: dict) -> DayForecast:
    return DayForecast(
        date=d.get("datetime", ""),
        temp_max=d.get("tempmax", 0),
        temp_min=d.get("tempmin", 0),
        temp_avg=d.get("temp", 0),
        feels_like_max=d.get("feelslikemax", 0),
        humidity=d.get("humidity", 0) or 0,
        precip=d.get("precip", 0) or 0,
        precip_prob=d.get("precipprob", 0) or 0,
        precip_types=d.get("preciptype") or [],
        wind_speed=d.get("windspeed", 0) or 0,
        wind_gust=d.get("windgust", 0) or 0,
        wind_dir=int(d.get("winddir", 0) or 0),
        pressure=d.get("pressure", 0) or 0,
        cloud_cover=d.get("cloudcover", 0) or 0,
        uv_index=int(d.get("uvindex", 0) or 0),
        sunrise=_fmt_time(d.get("sunrise", "")),
        sunset=_fmt_time(d.get("sunset", "")),
        moon_phase=d.get("moonphase", 0) or 0,
        conditions=d.get("conditions", ""),
        description=d.get("description", ""),
        icon=d.get("icon", ""),
        hours=[_parse_hour(h) for h in d.get("hours", [])],
    )

def _parse_current(c: dict) -> CurrentConditions:
    return CurrentConditions(
        time=_fmt_time(c.get("datetime", "")),
        temp=c.get("temp", 0),
        feels_like=c.get("feelslike", 0),
        humidity=c.get("humidity", 0),
        precip=c.get("precip", 0) or 0,
        precip_prob=c.get("precipprob", 0) or 0,
        wind_speed=c.get("windspeed", 0) or 0,
        wind_gust=c.get("windgust", 0) or 0,
        wind_dir=int(c.get("winddir", 0) or 0),
        pressure=c.get("pressure", 0) or 0,
        cloud_cover=c.get("cloudcover", 0) or 0,
        uv_index=int(c.get("uvindex", 0) or 0),
        conditions=c.get("conditions", ""),
        icon=c.get("icon", ""),
    )

def _normalise(raw: dict, unit_group: str) -> Forecast:
    days = [_parse_day(d) for d in raw.get("days", [])]
    cc = raw.get("currentConditions")
    return Forecast(
        location=raw.get("resolvedAddress", raw.get("address", "Unknown")),
        latitude=raw.get("latitude", 0),
        longitude=raw.get("longitude", 0),
        timezone=raw.get("timezone", ""),
        fetched_at=datetime.now().isoformat(timespec="seconds"),
        unit_group=unit_group,
        current=_parse_current(cc) if cc else None,
        today=days[0] if len(days) > 0 else None,
        tomorrow=days[1] if len(days) > 1 else None,
    )

# ── Cache ───────────────────────────────────────────────────────────────

def _cache_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    p = Path(base) / "DailyDispatch" / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p

_CACHE_FILE = "last_forecast.json"

def _save_cache(raw: dict, unit_group: str):
    try:
        path = _cache_dir() / _CACHE_FILE
        data = {"raw": raw, "unit_group": unit_group,
                "cached_at": datetime.now().isoformat(timespec="seconds")}
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass

def _load_cache() -> FetchResult | None:
    try:
        path = _cache_dir() / _CACHE_FILE
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        fc = _normalise(data["raw"], data.get("unit_group", "us"))
        fc.fetched_at = data.get("cached_at", fc.fetched_at)
        fc.is_cached = True
        return FetchResult(True, fc, f"Cached data from {fc.fetched_at}")
    except Exception:
        return None

# ── Service ─────────────────────────────────────────────────────────────

class WeatherService:
    """Fetches weather for a location, normalises the result, and caches it."""

    _BASE = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    _TIMEOUT = 15  # seconds

    def fetch(self, location: str, unit_system: str = "metric") -> FetchResult:
        """Fetch a forecast. Returns FetchResult with a Forecast on success,
        or a friendly error message + cached fallback on failure."""
        if not location or not location.strip():
            return FetchResult(False, message="No location configured. "
                               "Set one in Settings first.")

        unit_group = "metric" if unit_system == "metric" else "us"
        encoded = urllib.parse.quote(location.strip(), safe="")
        url = (f"{self._BASE}/{encoded}"
               f"?unitGroup={unit_group}"
               f"&include=days,hours,current"
               f"&key={_api_key()}"
               f"&contentType=json")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DailyDispatch/1.0"})
            with urllib.request.urlopen(req, timeout=self._TIMEOUT) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            cached = _load_cache()
            msg = f"Weather API error {e.code}."
            if e.code == 401:
                msg = "Invalid API key. Check DISPATCH_WEATHER_KEY."
            elif e.code == 429:
                msg = "API rate limit reached. Try again shortly."
            if cached:
                return FetchResult(True, cached.forecast,
                                   f"{msg} Showing cached data.")
            return FetchResult(False, message=msg)
        except Exception as e:
            cached = _load_cache()
            msg = f"Could not reach weather service. ({type(e).__name__})"
            if cached:
                return FetchResult(True, cached.forecast,
                                   f"{msg} Showing cached data.")
            return FetchResult(False, message=msg)

        _save_cache(raw, unit_group)
        fc = _normalise(raw, unit_group)
        return FetchResult(True, fc,
                           f"Live forecast for {fc.location}")

    def fetch_from_json(self, raw: dict, unit_system: str = "metric") -> FetchResult:
        """Build a Forecast from already-loaded JSON (for testing)."""
        ug = "metric" if unit_system == "metric" else "us"
        fc = _normalise(raw, ug)
        return FetchResult(True, fc, f"Forecast for {fc.location}")
