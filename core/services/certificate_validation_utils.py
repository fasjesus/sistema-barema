import logging
import re
import unicodedata
from typing import Optional


LOGGER = logging.getLogger("certificate-validation")


def debug(component: str, message: str):
    LOGGER.debug("DEBUG [%s]: %s", component, message)
    print(f"DEBUG [{component}]: {message}")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip().casefold()


def format_hours(value: float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def parse_hours(value) -> Optional[float]:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text.replace(",", "."))
    except (TypeError, ValueError):
        return None
