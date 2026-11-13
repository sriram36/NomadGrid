"""Settings and planning constants. Everything tunable lives here."""
import os
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
PACK_DIR = REPO_DIR / "hackathon-problem-1-holiday-package"

DATA_DIR = Path(os.environ.get("DATA_DIR", PACK_DIR / "data"))
IMAGES_DIR = Path(os.environ.get("IMAGES_DIR", PACK_DIR / "images"))
DB_PATH = Path(os.environ.get("DB_PATH", BACKEND_DIR / "storage" / "nomadgrid.sqlite"))
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST", REPO_DIR / "frontend" / "dist"))

# --- statement rules (never relax) ---
WINDOW_FIRST, WINDOW_LAST = date(2027, 4, 1), date(2027, 4, 20)   # the only days flights and rooms exist
ARRIVAL_PICKUP_BUFFER_MIN = 60     # pickup >= landing + 60
AIRPORT_ARRIVE_BEFORE_MIN = 180    # reach airport >= 180 min before departure

# --- comfort rules (only for system-suggested plans, never for user edits / validator) ---
DAY_START_MIN = 8 * 60 + 30        # 08:30
DAY_END_MIN = 21 * 60 + 30         # 21:30
VISIT_GAP_MIN = 30
SETTLE_MIN = 30
EARLIEST_INTERCITY_DEPARTURE_MIN = 8 * 60
TIME_TOLERANCE_MIN = 120
