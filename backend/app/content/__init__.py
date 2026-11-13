"""S2 / S3: read-only static content that lives OUTSIDE the provided catalog (data/catalog is never touched):
pocket city guides (city_guides.json) and nearby dining suggestions (restaurants.json).

Nothing here is part of a package's price or of the exported trip JSON.
"""
import json
from pathlib import Path
from typing import List, Optional

CONTENT_DIR = Path(__file__).resolve().parent


class Content:
    def __init__(self, directory=None):
        base = Path(directory or CONTENT_DIR)

        def load(name: str) -> dict:
            path = base / name
            if not path.is_file():
                return {"cities": {}}          # content is optional: the app still works without it
            return json.loads(path.read_text(encoding="utf-8"))

        guides, dining = load("city_guides.json"), load("restaurants.json")
        self._guides = guides.get("cities", {})
        self._guide_source = guides.get("source")
        self._dining = dining.get("cities", {})
        self.dining_disclaimer = dining.get("disclaimer", "Estimated prices, not included in the package total.")

    def guide(self, city: str) -> Optional[dict]:
        g = self._guides.get(city)
        return None if g is None else {"city": city, **g, "source": self._guide_source}

    def restaurants(self, city: str, area: Optional[str] = None) -> Optional[List[dict]]:
        """Dining spots in a city, for one area if given. None when the city/area has no data."""
        areas = self._dining.get(city)
        if areas is None:
            return None
        if area is None:
            return [dict(s, area=a) for a, rows in areas.items() for s in rows]
        rows = areas.get(area)
        return None if rows is None else [dict(s, area=area) for s in rows]
