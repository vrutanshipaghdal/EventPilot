import database as db
from utils import price_for_row, price_for_seat


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("EVENT_DB_PATH", str(tmp_path / "t.db"))
    db.init_db()
    return db.add_event("T", "d", "Music", "Pune", "V", "2030-01-01", "10:00",
                        120, "English", 4, 5, 100)


def test_booking_prices_and_capacity(tmp_path, monkeypatch):
    eid = _setup(tmp_path, monkeypatch)
    ev = db.get_event(eid)
    assert ev["capacity"] == 20 and ev["seats_left"] == 20
    ok, _, code = db.book_seats(eid, ["A1", "C2"], "A", "a@x.com", "1")
    assert ok and code.startswith("EP")
    b = db.get_booking(code)
    assert b["seats"] == ["A1", "C2"]
    assert b["total"] == price_for_seat(100, "A1") + 100 == 250
    assert db.get_event(eid)["seats_left"] == 18


def test_no_double_booking(tmp_path, monkeypatch):
    eid = _setup(tmp_path, monkeypatch)
    assert db.book_seats(eid, ["B3"], "A", "a@x.com", "1")[0]
    ok, msg, _ = db.book_seats(eid, ["B3", "B4"], "B", "b@x.com", "2")
    assert not ok and "B3" in msg
    assert db.booked_seats(eid) == {"B3"}  # B4 must not be half-booked


def test_invalid_seats(tmp_path, monkeypatch):
    eid = _setup(tmp_path, monkeypatch)
    assert not db.book_seats(eid, ["Z9"], "A", "a@x.com", "1")[0]
    assert not db.book_seats(eid, ["A6"], "A", "a@x.com", "1")[0]
    assert not db.book_seats(eid, [], "A", "a@x.com", "1")[0]


def test_stats_and_lookup(tmp_path, monkeypatch):
    eid = _setup(tmp_path, monkeypatch)
    db.book_seats(eid, ["D1"], "A", "A@X.com", "1")
    assert db.stats()["tickets"] == 1
    assert len(db.bookings_by_email("a@x.com")) == 1
    assert price_for_row(0, 0) == 0


def test_delete_cascades(tmp_path, monkeypatch):
    eid = _setup(tmp_path, monkeypatch)
    db.book_seats(eid, ["D1"], "A", "a@x.com", "1")
    db.delete_event(eid)
    assert db.stats()["tickets"] == 0 and db.stats()["bookings"] == 0


def test_multiple_attendees(tmp_path, monkeypatch):
    eid = _setup(tmp_path, monkeypatch)
    ok, _, code = db.book_seats(eid, ["A1", "A2"], "Main Booker", "main@x.com", "123",
                                attendees={"A1": "Person One", "A2": "Person Two"})
    assert ok
    b = db.get_booking(code)
    assert len(b["tickets"]) == 2
    assert b["tickets"][0]["attendee_name"] == "Person One"
    assert b["tickets"][0]["ticket_code"] == f"{code}-A1"
    assert b["tickets"][1]["attendee_name"] == "Person Two"
    assert b["tickets"][1]["ticket_code"] == f"{code}-A2"
