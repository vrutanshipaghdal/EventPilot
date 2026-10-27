"""SQLite data layer: events, bookings and seat-level inventory."""
import os
import secrets
import sqlite3
import string
from contextlib import contextmanager
from datetime import date

from utils import MAX_SEATS, price_for_row, seat_sort


def _path() -> str:
    env = os.getenv("EVENT_DB_PATH")
    if env:
        return env
    if os.path.exists("data/eventpilot.db"):
        return "data/eventpilot.db"
    if os.path.exists("eventpilot-ai/data/eventpilot.db"):
        return "eventpilot-ai/data/eventpilot.db"
    return "data/eventpilot.db"


@contextmanager
def get_conn():
    path = _path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    city TEXT NOT NULL,
    venue TEXT NOT NULL,
    event_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    duration_min INTEGER NOT NULL DEFAULT 120,
    language TEXT NOT NULL DEFAULT 'English',
    seat_rows INTEGER NOT NULL CHECK (seat_rows BETWEEN 1 AND 20),
    seat_cols INTEGER NOT NULL CHECK (seat_cols BETWEEN 1 AND 20),
    base_price REAL NOT NULL DEFAULT 0 CHECK (base_price >= 0),
    image_url TEXT NOT NULL DEFAULT '',
    featured INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    total REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS booked_seats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    seat TEXT NOT NULL,
    price REAL NOT NULL,
    attendee_name TEXT DEFAULT '',
    ticket_code TEXT DEFAULT '',
    UNIQUE (event_id, seat)
);
"""

EVENTS_SQL = """
SELECT e.*, e.seat_rows * e.seat_cols AS capacity,
       (SELECT COUNT(*) FROM booked_seats s WHERE s.event_id = e.id) AS booked
FROM events e {where}
ORDER BY e.event_date, e.start_time
"""


def init_db() -> None:
    with get_conn() as c:
        c.executescript(SCHEMA)
        # Safe migration for existing databases
        cols = [r["name"] for r in c.execute("PRAGMA table_info(booked_seats)")]
        if "attendee_name" not in cols:
            c.execute("ALTER TABLE booked_seats ADD COLUMN attendee_name TEXT DEFAULT ''")
        if "ticket_code" not in cols:
            c.execute("ALTER TABLE booked_seats ADD COLUMN ticket_code TEXT DEFAULT ''")


def _event(row) -> dict:
    d = dict(row)
    d["seats_left"] = d["capacity"] - d["booked"]
    return d


# ---------------- events ----------------
def add_event(title, description, category, city, venue, event_date, start_time,
              duration_min, language, seat_rows, seat_cols, base_price,
              image_url="", featured=False) -> int:
    with get_conn() as c:
        cur = c.execute(
            "INSERT INTO events (title, description, category, city, venue, event_date,"
            " start_time, duration_min, language, seat_rows, seat_cols, base_price,"
            " image_url, featured) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, description, category, city, venue, str(event_date), str(start_time),
             int(duration_min), language, int(seat_rows), int(seat_cols),
             float(base_price), image_url or "", int(bool(featured))),
        )
        return cur.lastrowid


def list_events(upcoming_only: bool = False) -> list[dict]:
    where, params = "", ()
    if upcoming_only:
        where, params = "WHERE e.event_date >= ?", (date.today().isoformat(),)
    with get_conn() as c:
        rows = c.execute(EVENTS_SQL.format(where=where), params).fetchall()
    return [_event(r) for r in rows]


def get_event(event_id: int) -> dict | None:
    with get_conn() as c:
        row = c.execute(EVENTS_SQL.format(where="WHERE e.id = ?"), (event_id,)).fetchone()
    return _event(row) if row else None


def set_image(event_id: int, image_url: str) -> None:
    with get_conn() as c:
        c.execute("UPDATE events SET image_url = ? WHERE id = ?", (image_url, event_id))


def set_featured(event_id: int, featured: bool) -> None:
    with get_conn() as c:
        c.execute("UPDATE events SET featured = ? WHERE id = ?", (int(featured), event_id))


def delete_event(event_id: int) -> None:
    with get_conn() as c:
        c.execute("DELETE FROM events WHERE id = ?", (event_id,))


# ---------------- seats & bookings ----------------
def booked_seats(event_id: int) -> set[str]:
    with get_conn() as c:
        rows = c.execute("SELECT seat FROM booked_seats WHERE event_id = ?",
                         (event_id,)).fetchall()
    return {r["seat"] for r in rows}


def _new_code(c) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "EP" + "".join(secrets.choice(alphabet) for _ in range(6))
        if not c.execute("SELECT 1 FROM bookings WHERE code = ?", (code,)).fetchone():
            return code


def book_seats(event_id: int, seats: list[str], name: str, email: str, phone: str,
               attendees: dict[str, str] | list[str] | None = None):
    """Atomically book specific seats with per-seat attendee names and ticket codes."""
    seats = sorted({s.strip().upper() for s in seats if s.strip()}, key=seat_sort)
    if not seats:
        return False, "Select at least one seat.", None
    if len(seats) > MAX_SEATS:
        return False, f"Maximum {MAX_SEATS} seats per booking.", None

    att_map = {}
    if isinstance(attendees, dict):
        att_map = {k.strip().upper(): v.strip() for k, v in attendees.items()}
    elif isinstance(attendees, (list, tuple)):
        for s, a in zip(seats, attendees):
            att_map[s] = str(a).strip()

    with get_conn() as c:
        c.execute("BEGIN IMMEDIATE")
        ev = c.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if ev is None:
            return False, "Event not found.", None
        priced, total = [], 0.0
        for s in seats:
            try:
                r_idx, num = ord(s[0]) - 65, int(s[1:])
            except (ValueError, IndexError):
                return False, f"Invalid seat {s}.", None
            if not (0 <= r_idx < ev["seat_rows"] and 1 <= num <= ev["seat_cols"]):
                return False, f"Invalid seat {s}.", None
            price = price_for_row(ev["base_price"], r_idx)
            att_name = att_map.get(s) or name.strip()
            priced.append((s, price, att_name))
            total += price
        marks = ",".join("?" * len(seats))
        taken = [r["seat"] for r in c.execute(
            f"SELECT seat FROM booked_seats WHERE event_id = ? AND seat IN ({marks})",
            (event_id, *seats))]
        if taken:
            return False, "Sorry, just booked by someone else: " + ", ".join(taken), None
        code = _new_code(c)
        cur = c.execute(
            "INSERT INTO bookings (code, event_id, name, email, phone, total)"
            " VALUES (?,?,?,?,?,?)",
            (code, event_id, name.strip(), email.strip().lower(), phone.strip(), total))
        booking_id = cur.lastrowid
        c.executemany(
            "INSERT INTO booked_seats (event_id, booking_id, seat, price, attendee_name, ticket_code) VALUES (?,?,?,?,?,?)",
            [(event_id, booking_id, s, p, a_name, f"{code}-{s}") for s, p, a_name in priced])
    return True, "Booking confirmed!", code


def get_booking(code: str) -> dict | None:
    with get_conn() as c:
        b = c.execute("SELECT * FROM bookings WHERE code = ?",
                      (code.strip().upper(),)).fetchone()
        if b is None:
            return None
        rows = c.execute(
            "SELECT * FROM booked_seats WHERE booking_id = ?", (b["id"],)).fetchall()
    d = dict(b)
    col_names = set(rows[0].keys()) if rows else set()
    seats = []
    tickets = []
    for r in rows:
        s = r["seat"]
        seats.append(s)
        a_name = r["attendee_name"] if ("attendee_name" in col_names and r["attendee_name"]) else d["name"]
        t_code = r["ticket_code"] if ("ticket_code" in col_names and r["ticket_code"]) else f"{d['code']}-{s}"
        tickets.append({
            "seat": s,
            "price": r["price"],
            "attendee_name": a_name,
            "ticket_code": t_code
        })
    d["seats"] = sorted(seats, key=seat_sort)
    d["tickets"] = sorted(tickets, key=lambda t: seat_sort(t["seat"]))
    d["event"] = get_event(d["event_id"])
    return d


def bookings_by_email(email: str) -> list[dict]:
    with get_conn() as c:
        codes = [r["code"] for r in c.execute(
            "SELECT code FROM bookings WHERE email = ? ORDER BY created_at DESC",
            (email.strip().lower(),))]
    return [b for b in (get_booking(code) for code in codes) if b]


def list_bookings() -> list[dict]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT b.code, e.title AS event, b.name, b.email, b.phone,"
            " (SELECT group_concat(seat || CASE WHEN attendee_name != '' AND attendee_name != b.name THEN ' (' || attendee_name || ')' ELSE '' END, ', ') FROM booked_seats s WHERE s.booking_id = b.id) AS seats,"
            " b.total, b.created_at FROM bookings b JOIN events e ON e.id = b.event_id"
            " ORDER BY b.created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ---------------- analytics ----------------
def stats() -> dict:
    today = date.today().isoformat()
    with get_conn() as c:
        events = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        upcoming = c.execute("SELECT COUNT(*) FROM events WHERE event_date >= ?",
                             (today,)).fetchone()[0]
        bookings = c.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        tickets = c.execute("SELECT COUNT(*) FROM booked_seats").fetchone()[0]
        revenue = c.execute("SELECT COALESCE(SUM(total), 0) FROM bookings").fetchone()[0]
    return {"events": events, "upcoming": upcoming, "bookings": bookings,
            "tickets": tickets, "revenue": revenue}


def tickets_by_event() -> list[dict]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT e.title, COUNT(s.id) AS sold FROM events e"
            " LEFT JOIN booked_seats s ON s.event_id = e.id GROUP BY e.id ORDER BY sold DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def revenue_by_category() -> list[dict]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT e.category, COALESCE(SUM(b.total), 0) AS revenue FROM events e"
            " LEFT JOIN bookings b ON b.event_id = e.id GROUP BY e.category"
            " ORDER BY revenue DESC").fetchall()
    return [dict(r) for r in rows]
