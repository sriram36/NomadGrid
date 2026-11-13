"""S1 quick request: read a short sentence with RULES (regular expressions and word lists — no AI).

    "Japan 10 Apr 6 nights 2 adults 1 child 6 from Bengaluru 3.5 lakh"

becomes the 7 form fields. Anything it cannot read is reported as missing, never guessed.
"""
import re
from datetime import date
from typing import Dict, List, Optional, Tuple

DEFAULT_YEAR = 2027      # the data covers April 2027, so a date without a year means 2027

MONTHS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
          "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
          "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))

DEPARTURE_ALIASES = {
    "bengaluru": "Bengaluru", "bangalore": "Bengaluru", "blr": "Bengaluru",
    "delhi": "Delhi", "new delhi": "Delhi", "del": "Delhi",
    "mumbai": "Mumbai", "bombay": "Mumbai", "bom": "Mumbai",
    "chennai": "Chennai", "madras": "Chennai", "maa": "Chennai",
}
COUNTRY_ALIASES = {
    "japan": "Japan", "tokyo": "Japan", "kyoto": "Japan", "osaka": "Japan",
    "united arab emirates": "United Arab Emirates", "uae": "United Arab Emirates", "emirates": "United Arab Emirates",
    "dubai": "United Arab Emirates", "abu dhabi": "United Arab Emirates",
}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "a": 1, "an": 1}
NUM = r"(\d+|" + "|".join(NUMBER_WORDS) + r")"
STOP = {"the", "and", "for", "with", "from", "to", "in", "on", "of", "trip", "holiday", "vacation", "want", "need",
        "plan", "please", "my", "our", "we", "i", "a", "an", "at", "by", "around", "about", "total", "budget",
        "starting", "start", "leaving", "travel", "traveling", "travelling", "going", "go", "family", "is", "are"}


def _num(text: str) -> Optional[int]:
    t = text.lower()
    return int(t) if t.isdigit() else NUMBER_WORDS.get(t)


def _safe_date(y: int, m: int, d: int) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


DATE_PATTERNS = [
    (r"\b(20\d\d)-(\d{1,2})-(\d{1,2})\b", lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3)))),
    (r"\b(\d{1,2})/(\d{1,2})/(20\d\d)\b", lambda m: (int(m.group(3)), int(m.group(2)), int(m.group(1)))),   # day/month/year
    (r"\b(\d{1,2})(?:st|nd|rd|th)?[\s\-/]*(?:of\s+)?(" + MONTH_RE + r")\b\.?(?:[\s,\-/]*(20\d\d))?",
     lambda m: (int(m.group(3) or DEFAULT_YEAR), MONTHS[m.group(2)], int(m.group(1)))),
    (r"\b(" + MONTH_RE + r")\b\.?\s*(\d{1,2})(?:st|nd|rd|th)?(?:[\s,]*(20\d\d))?",
     lambda m: (int(m.group(3) or DEFAULT_YEAR), MONTHS[m.group(1)], int(m.group(2)))),
]


def _find_date(work: str):
    for pattern, parts in DATE_PATTERNS:
        for m in re.finditer(pattern, work):
            d = _safe_date(*parts(m))
            if d:
                return d, m
    return None, None


def parse_quick_request(text: str) -> dict:
    """Returns {"fields", "understood", "missing", "unparsed", "notes", "ready"}."""
    original = text or ""
    work = " " + re.sub(r"\s+", " ", original.lower()) + " "
    understood: List[dict] = []
    notes: List[str] = []
    fields: Dict[str, object] = {}

    def take(field, value, span: Tuple[int, int], shown: str):
        """Record a value and blank its text out so later rules can't read it twice."""
        nonlocal work
        fields[field] = value
        understood.append({"field": field, "text": shown.strip(), "value": value})
        work = work[:span[0]] + " " * (span[1] - span[0]) + work[span[1]:]

    # ---- budget (before anything numeric: "3.5 lakh", "350k", "₹3,50,000", "budget 4 lakhs")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lks?)\b|(\d+(?:\.\d+)?)\s*l\b(?!\w)", work)
    if m:
        take("budget_inr", int(round(float(m.group(1) or m.group(2)) * 100000)), m.span(), m.group(0))
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*k\b", work)
        if m:
            take("budget_inr", int(round(float(m.group(1)) * 1000)), m.span(), m.group(0))
        else:
            m = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+)|budget\D{0,12}?([\d,]{4,})", work)
            if m:
                digits = (m.group(1) or m.group(2)).replace(",", "")
                if digits.isdigit():
                    take("budget_inr", int(digits), m.span(), m.group(0))

    # ---- date
    d, m = _find_date(work)
    if d and m:
        take("start_date", d.isoformat(), m.span(), m.group(0))
        if not re.search(r"20\d\d", m.group(0)):
            notes.append(f"No year given, so {DEFAULT_YEAR} was assumed (our data covers April {DEFAULT_YEAR}).")

    # ---- nights ("6 nights", "6-night", "for 7 days" = 6 nights)
    m = re.search(r"\b" + NUM + r"[\s\-]*nights?\b", work)
    if m and _num(m.group(1)):
        take("nights", _num(m.group(1)), m.span(), m.group(0))
    else:
        m = re.search(r"\b" + NUM + r"[\s\-]*days?\b", work)
        n = _num(m.group(1)) if m else None
        if m and n and n >= 2:
            take("nights", n - 1, m.span(), m.group(0))
            notes.append(f"Read {n} days as {n - 1} nights (you land on day 1 and fly home on the last day).")
    if "nights" not in fields:
        m = re.search(r"\b(\d{1,2})\s*n\b", work)                     # shorthand: "6n"
        if m and int(m.group(1)) > 0:
            take("nights", int(m.group(1)), m.span(), m.group(0))
    if "nights" not in fields and "start_date" in fields:                 # a date range: "10 Apr to 16 Apr"
        d2, m2 = _find_date(work)
        start = date.fromisoformat(str(fields["start_date"]))
        if d2 and m2 and d2 > start:
            take("nights", (d2 - start).days, m2.span(), m2.group(0))
            notes.append(f"Read the dates as a range of {(d2 - start).days} nights (the second date is the day you fly home).")

    # ---- adults ("2 adults", "couple", "solo")
    m = re.search(r"\b" + NUM + r"\s*adults?\b", work)
    if not (m and _num(m.group(1))):
        m = re.search(r"\badults?\s*[:=\-]?\s*(\d{1,2})\b(?!\s*(?:\.|lakh|lac|l\b|k\b|night|day))", work)
    if m and _num(m.group(1)):
        take("adults", _num(m.group(1)), m.span(), m.group(0))
    elif (m := re.search(r"\b" + NUM + r"\s*(?:pax|people|persons?|travell?ers|members)\b", work)) \
            and _num(m.group(1)):
        take("adults", _num(m.group(1)), m.span(), m.group(0))
        notes.append(f"Read “{m.group(0).strip()}” as adults — tell us if any of them are children, please check.")
    else:
        m = re.search(r"\b(couple|honeymoon|solo|alone|myself|by myself)\b", work)
        if m:
            take("adults", 2 if m.group(1) in ("couple", "honeymoon") else 1, m.span(), m.group(0))

    # ---- children: "1 child 6", "2 kids aged 4 and 9", "child (7)", "a 6 year old child"
    ages: List[int] = []
    count: Optional[int] = None
    m = re.search(r"\b" + NUM + r"\s*(?:children|child|kids|kid)\b(?:\s*(?:aged?|of age|:|\()\s*|\s+)?"
                  r"((?:\d{1,2})(?:\s*(?:,|and|&)\s*\d{1,2})*)?\)?"
                  r"(?!\s*(?:\.|\d|lakh|lac|l\b|k\b|night|day|adult))", work)
    if not m:
        m = re.search(r"\b()(?:children|child|kids|kid)\b(?:\s*(?:aged?|of age|:|\()\s*|\s+)"
                      r"((?:\d{1,2})(?:\s*(?:,|and|&)\s*\d{1,2})*)\)?"
                      r"(?!\s*(?:\.|\d|lakh|lac|l\b|k\b|night|day|adult))", work)
    if m:
        count = _num(m.group(1)) if m.group(1) else None
        if m.group(2):
            ages = [int(x) for x in re.findall(r"\d{1,2}", m.group(2))]
    y = re.search(r"\b(\d{1,2})[\s\-]*(?:years?|yrs?)[\s\-]*olds?\b", work)
    if y and not ages:
        ages = [int(y.group(1))]
        if not m:
            m = y
    if m:
        span = m.span()
        if count is None and ages and not re.search(r"aged?|year|yr|of age|\(", m.group(0)):
            notes.append(f"Read “{m.group(0).strip()}” as one child aged {ages[0]} — please check the age.")
        if count is None:
            count = len(ages) if ages else 1
        if any(a > 17 for a in ages):
            notes.append("A child must be 0 to 17 years old; check the ages.")
        if len(ages) < count:
            notes.append(f"{count} child(ren) mentioned but only {len(ages)} age(s) understood; add the missing ages.")
        else:
            ages = ages[:count]
        take("child_ages", ages, span, m.group(0))
        if len(ages) < count:
            fields["children_count"] = count          # told to the caller so the form can ask for the rest
    # ---- where from / where to
    m = re.search(r"\bfrom\s+(new delhi|[a-z]+)\b", work)
    dep = DEPARTURE_ALIASES.get(m.group(1)) if m else None
    if dep and m:
        take("departure_city", dep, m.span(1), m.group(1))
    else:
        for alias in sorted(DEPARTURE_ALIASES, key=len, reverse=True):
            m = re.search(r"\b" + re.escape(alias) + r"\b", work)
            if m:
                take("departure_city", DEPARTURE_ALIASES[alias], m.span(), alias)
                break
    for alias in sorted(COUNTRY_ALIASES, key=len, reverse=True):
        m = re.search(r"\b" + re.escape(alias) + r"\b", work)
        if m:
            take("country", COUNTRY_ALIASES[alias], m.span(), alias)
            if alias not in ("japan", "united arab emirates"):
                notes.append(f"Read “{alias}” as a trip to {COUNTRY_ALIASES[alias]}; the app chooses the cities itself.")
            break

    # ---- results
    if "child_ages" not in fields and "adults" in fields:
        fields["child_ages"] = []                      # no children mentioned
    form_fields = ["departure_city", "country", "start_date", "nights", "adults", "child_ages", "budget_inr"]
    missing = [f for f in form_fields if f not in fields or (f == "child_ages" and fields.get("children_count"))]
    leftovers = [w for w in re.findall(r"[a-z][a-z'\-]{2,}", work) if w not in STOP]
    clean = {k: v for k, v in fields.items() if k in form_fields}
    return {"fields": clean, "understood": understood, "missing": missing, "unparsed": leftovers,
            "notes": notes, "ready": not missing and not notes_blocking(notes)}


def notes_blocking(notes: List[str]) -> bool:
    return any("must be 0 to 17" in n or ("only" in n and "age(s)" in n) or "please check" in n for n in notes)
