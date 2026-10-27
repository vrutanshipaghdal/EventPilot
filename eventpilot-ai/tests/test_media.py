import database as db
import posters
from tickets import make_ticket_png


def test_poster_banner_ticket(tmp_path, monkeypatch):
    monkeypatch.setenv("EVENT_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(posters, "POSTER_DIR", tmp_path / "posters")
    db.init_db()
    eid = db.add_event("A Very Long Event Title For Testing Wrap", "d", "Cultural", "Surat",
                       "Venue", "2030-01-01", "18:00", 90, "Hindi", 3, 4, 250)
    ev = db.get_event(eid)
    assert posters.make_poster(ev).endswith(".jpg")
    assert posters.make_banner(ev).endswith(".jpg")
    _, _, code = db.book_seats(eid, ["A1"], "Test", "t@x.com", "1")
    assert make_ticket_png(db.get_booking(code))[:4] == b"\x89PNG"


def test_multiple_tickets_distinct_qr_and_zip(tmp_path, monkeypatch):
    from tickets import make_all_tickets, make_tickets_zip
    monkeypatch.setenv("EVENT_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(posters, "POSTER_DIR", tmp_path / "posters")
    db.init_db()
    eid = db.add_event("Multi Attendee Concert", "Desc", "Music", "Mumbai",
                       "Stadium", "2030-01-01", "19:00", 120, "English", 5, 5, 500)
    ok, _, code = db.book_seats(eid, ["A1", "A2"], "Main Booker", "main@x.com", "999",
                                attendees={"A1": "Person One", "A2": "Person Two"})
    assert ok
    b = db.get_booking(code)
    all_t = make_all_tickets(b)
    assert len(all_t) == 2
    assert all_t[0]["attendee_name"] == "Person One"
    assert all_t[1]["attendee_name"] == "Person Two"
    assert all_t[0]["png"][:4] == b"\x89PNG"
    assert all_t[1]["png"][:4] == b"\x89PNG"
    assert all_t[0]["png"] != all_t[1]["png"]  # Unique QR and attendee on each ticket!
    zip_bytes = make_tickets_zip(b)
    assert zip_bytes[:4] == b"PK\x03\x04"  # Valid ZIP archive
