"""Create the SQLite database and seed sample evaluation criteria."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rfp_eval import db  # noqa: E402

if __name__ == "__main__":
    db.init_db()
    for c in db.load_criteria(active_only=False):
        print(c)
    print(f"Database ready at {db.DB_PATH}")
