"""Sample events + a few demo bookings so the app looks alive on first run."""
import os
import random
from datetime import date, timedelta

import database as db
from utils import seat_label


def _events():
    d = date.today()
    # title, desc, category, city, venue, date, time, mins, lang, rows, cols, price, featured
    return [
        ("Garba & Dandiya Night", "Live band, traditional Garba and Dandiya rounds, food stalls and "
         "a best-dressed contest. Come in traditional wear!", "Cultural", "Ahmedabad",
         "GMDC Ground", d + timedelta(days=12), "19:00", 240, "Gujarati", 8, 12, 350, 1),
        ("Stand-Up Comedy Night", "Four of the city's sharpest comics, one stage, zero filters. "
         "Recommended for 16+.", "Comedy", "Mumbai", "Comedy Club, Andheri",
         d + timedelta(days=5), "20:00", 90, "Hindi", 8, 12, 599, 0),
        ("AI & RAG Hands-on Workshop", "Build a Retrieval Augmented Generation app with LangChain, "
         "FAISS and open-source LLMs. Laptop required, certificate included.", "Workshop",
         "Ahmedabad", "Tech Hub, Prahlad Nagar", d + timedelta(days=7), "10:00", 360, "English",
         6, 10, 499, 0),
        ("Indie Music Fest", "Six indie bands, open-air arena, food trucks and a sunset stage. "
         "Bring your friends and your energy.", "Music", "Bangalore",
         "Open Air Arena, Whitefield", d + timedelta(days=20), "17:00", 300, "English",
         10, 14, 1299, 1),
        ("Startup Pitch Night", "Ten early-stage startups pitch to investors, followed by a "
         "networking dinner.", "Networking", "Delhi", "Convention Centre, Aerocity",
         d + timedelta(days=14), "18:30", 180, "English", 8, 12, 299, 0),
        ("Sunrise 10K Run", "Timed 10K along the river with medals for all finishers, breakfast "
         "and a warm-up session. Free registration.", "Sports", "Ahmedabad",
         "Riverfront Promenade", d + timedelta(days=9), "05:30", 120, "English", 5, 12, 0, 0),
        ("Poetry & Open Mic Evening", "Poets, singers and storytellers take the mic. Sign up on "
         "the day to perform or just come to listen.", "Cultural", "Mumbai",
         "Cafe Lounge, Bandra", d + timedelta(days=10), "17:00", 150, "Hindi", 5, 8, 0, 0),
        ("Data Science Career Meetup", "Talks from working data scientists, resume review booths "
         "and mock interviews for students and freshers.", "Career", "Bangalore",
         "University Auditorium, Indiranagar", d + timedelta(days=28), "11:00", 240, "English",
         10, 12, 199, 0),
    ]


def seed_if_empty() -> None:
    db.init_db()
    if db.list_events():
        return
    ids = []
    for t, desc, cat, city, venue, dt, tm, mins, lang, rows, cols, price, feat in _events():
        ids.append(db.add_event(t, desc, cat, city, venue, dt.isoformat(), tm, mins, lang,
                                rows, cols, price, "", bool(feat)))
    if os.getenv("SEED_DEMO_BOOKINGS", "1") != "1":
        return
    rng = random.Random(7)
    for eid in ids:
        ev = db.get_event(eid)
        seats = [seat_label(r, c) for r in range(ev["seat_rows"]) for c in range(ev["seat_cols"])]
        rng.shuffle(seats)
        take, i = int(len(seats) * rng.uniform(0.15, 0.55)), 0
        while i < take:
            n = rng.randint(1, 4)
            db.book_seats(eid, seats[i:i + n], "Demo Guest", "demo@example.com", "0000000000")
            i += n
