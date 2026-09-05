import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "communitybridge.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    phone TEXT,
    neighborhood TEXT,
    bio TEXT,
    skills TEXT,
    is_admin INTEGER DEFAULT 0,
    impact_points INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    icon TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    post_type TEXT NOT NULL CHECK(post_type IN ('need','offer')),
    category_id INTEGER,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    neighborhood TEXT,
    urgency TEXT DEFAULT 'normal' CHECK(urgency IN ('normal','urgent','emergency')),
    status TEXT DEFAULT 'open' CHECK(status IN ('open','in_progress','resolved')),
    flagged INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS thanks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER NOT NULL,
    message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (from_user_id) REFERENCES users(id),
    FOREIGN KEY (to_user_id) REFERENCES users(id)
);
"""

CATEGORIES = [
    ("Food & Groceries", "🥫"),
    ("Shelter & Housing", "🏠"),
    ("Medical & Health", "🩺"),
    ("Transportation", "🚗"),
    ("Disaster & Emergency", "🚨"),
    ("Childcare & Eldercare", "🧑‍🍼"),
    ("Tutoring & Skills", "🎓"),
    ("Household Items", "🛋️"),
    ("Mental Health Support", "💬"),
    ("Other", "🤝"),
]

DEMO_USERS = [
    ("maria_h", "maria@example.com", "demo1234", "9841000001", "Riverside District", "Retired nurse, happy to help with basic first aid and check-ins on elderly neighbors.", "First aid, elder care, cooking"),
    ("tomas_r", "tomas@example.com", "demo1234", "9841000002", "Riverside District", "Contractor with a pickup truck — can help move things or haul debris after storms.", "Hauling, carpentry, driving"),
    ("aisha_k", "aisha@example.com", "demo1234", "9841000003", "Lakeview Heights", "College student, free most evenings, love tutoring math and English.", "Tutoring, translation (Spanish/English)"),
    ("ben_c", "ben@example.com", "demo1234", "9841000004", "Lakeview Heights", "Runs the community garden, always have extra produce to share.", "Gardening, food preservation"),
]

DEMO_POSTS = [
    # (username, type, category_idx, title, description, neighborhood, urgency, status)
    ("maria_h", "offer", 0, "Extra home-cooked meals available", "I cook large batches every Sunday and always have extra. Happy to share with anyone who needs a warm meal this week.", "Riverside District", "normal", "open"),
    ("tomas_r", "need", 4, "URGENT: Flooded basement, need pump + hands", "Heavy rain flooded my basement overnight. Need a water pump if anyone has one to lend, plus a couple hours of help moving boxes to higher ground.", "Riverside District", "emergency", "open"),
    ("aisha_k", "offer", 6, "Free math & English tutoring, grades 6-10", "Available Tue/Thu evenings and weekends. Can meet at the library or online.", "Lakeview Heights", "normal", "open"),
    ("ben_c", "offer", 0, "Fresh vegetables from community garden", "Tomatoes, zucchini, and herbs ready to pick. First come first served, just message me.", "Lakeview Heights", "normal", "open"),
    ("maria_h", "need", 3, "Ride needed to dialysis appointments", "Looking for someone who can drive me to my dialysis appointments on Mon/Wed/Fri mornings, 8am. Gas money offered.", "Riverside District", "urgent", "open"),
    ("tomas_r", "offer", 1, "Spare room available for displaced family", "Wildfire evacuees are welcome to stay in our spare room for a few weeks while things settle. Has its own bathroom.", "Riverside District", "urgent", "open"),
    ("aisha_k", "need", 8, "Anyone up for a weekly walk-and-talk?", "New to the area and feeling isolated. Would love a walking buddy once a week, nothing fancy, just company.", "Lakeview Heights", "normal", "open"),
    ("ben_c", "need", 7, "Borrow a ladder for gutter cleaning", "Need to clear my gutters before the next storm hits. Just need to borrow a tall ladder for an afternoon.", "Lakeview Heights", "normal", "resolved"),
]


def init_db(reset=False):
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()

    if conn.execute("SELECT COUNT(*) c FROM categories").fetchone()["c"] == 0:
        conn.executemany("INSERT INTO categories (name, icon) VALUES (?, ?)", CATEGORIES)
        conn.commit()

    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        for username, email, pw, phone, hood, bio, skills in DEMO_USERS:
            conn.execute(
                """INSERT INTO users (username, email, password_hash, phone, neighborhood, bio, skills)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (username, email, generate_password_hash(pw), phone, hood, bio, skills),
            )
        conn.execute(
            "INSERT INTO users (username, email, password_hash, is_admin, neighborhood) VALUES (?, ?, ?, 1, ?)",
            ("admin", "admin@communitybridge.org", generate_password_hash("admin123"), "HQ"),
        )
        conn.commit()

    if conn.execute("SELECT COUNT(*) c FROM posts").fetchone()["c"] == 0:
        user_ids = {r["username"]: r["id"] for r in conn.execute("SELECT id, username FROM users")}
        cat_ids = [r["id"] for r in conn.execute("SELECT id FROM categories ORDER BY id")]
        for username, ptype, cat_idx, title, desc, hood, urgency, status in DEMO_POSTS:
            conn.execute(
                """INSERT INTO posts (user_id, post_type, category_id, title, description, neighborhood, urgency, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_ids[username], ptype, cat_ids[cat_idx], title, desc, hood, urgency, status),
            )
        conn.commit()

    conn.close()
