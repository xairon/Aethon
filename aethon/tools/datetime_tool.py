"""Outil — Date et heure actuelles."""

from datetime import datetime
import logging

log = logging.getLogger(__name__)

# Mapping thread-safe pour le formatage en français (évite locale.setlocale)
_DAYS_FR = {
    "Monday": "lundi", "Tuesday": "mardi", "Wednesday": "mercredi",
    "Thursday": "jeudi", "Friday": "vendredi", "Saturday": "samedi",
    "Sunday": "dimanche",
}
_MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai",
    6: "juin", 7: "juillet", 8: "août", 9: "septembre",
    10: "octobre", 11: "novembre", 12: "décembre",
}


class DateTimeTool:
    """Fournit la date et l'heure actuelles."""

    @property
    def name(self) -> str:
        return "get_current_datetime"

    @property
    def description(self) -> str:
        return (
            "Retourne la date et l'heure actuelles. "
            "Utilise cet outil quand l'utilisateur demande l'heure, "
            "la date, le jour de la semaine, ou toute information temporelle."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Fuseau horaire (ex: 'Europe/Paris'). Par défaut: local.",
                }
            },
            "required": [],
        }

    def execute(self, timezone: str = "") -> str:
        """Retourne la date et l'heure formatées en français."""
        try:
            if timezone:
                from zoneinfo import ZoneInfo
                now = datetime.now(ZoneInfo(timezone))
            else:
                now = datetime.now()
        except Exception:
            now = datetime.now()

        day_name = _DAYS_FR.get(now.strftime("%A"), now.strftime("%A"))
        month_name = _MONTHS_FR.get(now.month, now.strftime("%B"))

        return (
            f"Date: {day_name} {now.day} {month_name} {now.year}. "
            f"Heure: {now.strftime('%H:%M:%S')}."
        )
