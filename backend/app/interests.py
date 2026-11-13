"""S1: interest tags and deterministic keyword matching (no AI).

An attraction matches a tag when its CATEGORY is in the tag's category list, or its name / aliases contain one of the
tag's keywords. Only attractions.json fields are used. Matching never relaxes a rule: it only changes which
valid attractions are preferred and which are highlighted.
"""
import re
from typing import Dict, Iterable, List, Optional, Tuple

# tag id -> label, categories, name keywords (lower case)
TAGS: Dict[str, dict] = {
    "HISTORY_CULTURE": {
        "label": "History & Culture",
        "categories": {"TEMPLE", "SHRINE", "CASTLE", "PALACE", "MOSQUE", "MONUMENT"},
        "keywords": ("heritage", "historical", "national museum", "etihad", "imperial", "edo", "gion"),
    },
    "NATURE": {
        "label": "Nature & Outdoors",
        "categories": {"PARK", "NATURE", "BEACH"},
        "keywords": ("garden", "bamboo", "mangrove", "seaside", "philosopher"),
    },
    "FAMILY": {
        "label": "Family Fun",
        "categories": {"THEME_PARK", "AQUARIUM"},
        "keywords": ("toy", "zoo", "science", "railway", "miracle garden", "disney"),
    },
    "ART": {
        "label": "Art & Design",
        "categories": set(),
        "keywords": ("art", "louvre", "teamlab", "craft", "future", "gallery", "design"),
    },
    "FOOD_MARKETS": {
        "label": "Food & Markets",
        "categories": {"MARKET"},
        "keywords": ("market", "souk", "ichiba", "dotonbori", "shinsekai"),
    },
    "VIEWS_ADVENTURE": {
        "label": "Views & Adventure",
        "categories": {"VIEWPOINT"},
        "keywords": ("kayak", "ski", "skytree", "sky building", "frame", "top"),
    },
}


def tag_list() -> List[dict]:
    return [{"id": k, "label": v["label"]} for k, v in TAGS.items()]


def normalise(raw) -> Optional[str]:
    """'History & Culture', 'history_culture', 'HISTORY-CULTURE' -> 'HISTORY_CULTURE'; None if not a known tag."""
    if not isinstance(raw, str):
        return None
    key = re.sub(r"[^A-Za-z]+", "_", raw.strip()).strip("_").upper()
    if key in TAGS:
        return key
    for k, v in TAGS.items():
        if re.sub(r"[^A-Za-z]+", "_", v["label"]).strip("_").upper() == key:
            return k
    return None


def _word(keyword: str, text: str) -> bool:
    return re.search("(?<![a-z])" + re.escape(keyword) + "(?![a-z])", text) is not None


def tags_of(attraction: dict) -> Tuple[str, ...]:
    """Every tag this attraction matches, in the fixed TAGS order."""
    text = " ".join([attraction["name"], *attraction.get("aliases", [])]).lower()
    out = []
    for tag, rule in TAGS.items():
        if attraction["category"] in rule["categories"] or any(_word(k, text) for k in rule["keywords"]):
            out.append(tag)
    return tuple(out)


def matched(attraction: dict, interests: Iterable[str]) -> Tuple[str, ...]:
    """The traveler's chosen tags that this attraction matches."""
    have = set(tags_of(attraction))
    return tuple(t for t in interests if t in have)
