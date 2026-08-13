"""
LocationService — validates and normalises the forecast location.

Phase 1 performs structural validation only. Full resolution (turning
"Boston" into coordinates via the weather provider) comes in Phase 2.
"""

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    ok: bool
    message: str
    data: dict = field(default_factory=dict)


class LocationService:

    def validate(self, mode, query="", lat=None, lon=None):
        if mode == "coords":
            return self._coords(lat, lon)
        return self._query(query)

    def _query(self, q):
        q = (q or "").strip()
        if len(q) < 2:
            return ValidationResult(False, "Enter a city name or postal code.")
        if len(q) > 80:
            return ValidationResult(False, "Location text is too long.")
        return ValidationResult(True,
            f'Looks good — "{q}". Full resolution happens in Phase 2.',
            {"location_mode": "query", "location_query": q, "resolved_name": q})

    def _coords(self, lat, lon):
        try:
            la, lo = float(str(lat).strip()), float(str(lon).strip())
        except (TypeError, ValueError):
            return ValidationResult(False, "Latitude and longitude must be numbers.")
        if not -90 <= la <= 90:
            return ValidationResult(False, "Latitude must be between −90 and 90.")
        if not -180 <= lo <= 180:
            return ValidationResult(False, "Longitude must be between −180 and 180.")
        return ValidationResult(True, f"Coordinates valid — {la:.4f}, {lo:.4f}.",
            {"location_mode": "coords", "latitude": la, "longitude": lo,
             "resolved_name": f"{la:.4f}, {lo:.4f}"})
