"""EventPilot - BookMyShow-style event booking with an AI assistant.
Run: streamlit run app.py"""
import io
import os
from datetime import date, time
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

import database as db  # noqa: E402
from posters import POSTER_DIR, make_banner, poster_for  # noqa: E402
from rag import EventBot, load_embeddings  # noqa: E402
from seed import seed_if_empty  # noqa: E402
from tickets import (make_all_tickets, make_single_ticket_png, make_ticket_png,  # noqa: E402
                     make_tickets_zip)
from utils import (MAX_SEATS, PREMIUM_ROWS, fmt_date, fmt_date_short, fmt_duration,  # noqa: E402
                   fmt_price, fmt_time, price_for_row, price_for_seat, row_letter, seat_label,
                   seat_sort)

st.set_page_config(page_title="EventPilot - Book events", page_icon="🎟️", layout="wide",
                   initial_sidebar_state="collapsed")
seed_if_empty()

CATEGORIES = ["Workshop", "Networking", "Cultural", "Career", "Music", "Sports", "Comedy", "Other"]
NAV = ["🏠 Home", "🤖 Ask AI", "🎫 My Bookings", "⚙️ Admin"]
SUGGESTIONS = ["Any free events this week?", "Comedy shows in Mumbai?", "What is the refund policy?"]

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; max-width: 1250px;}
header[data-testid="stHeader"] {background: transparent;}
div.stButton > button {width: 100%; border-radius: 8px; font-weight: 600;}
img {border-radius: 12px;}
.brand {font-size: 2rem; font-weight: 800; color: #f84464; letter-spacing: -0.5px;}
.brand span {color: #fafafa;}
.chip {display:inline-block; padding:4px 14px; border-radius:999px; background:#1e293b;
       border: 1px solid rgba(255,255,255,0.12); font-size:.82rem; margin: 0 6px 6px 0; color:#e2e8f0;}
.price {color:#f84464; font-weight:700;}
.screen {height:12px; width:72%; margin:12px auto 6px; border-radius:50% 50% 0 0/100% 100% 0 0;
         background:linear-gradient(180deg,#f84464,rgba(248,68,100,.08));
         box-shadow:0 8px 30px rgba(248,68,100,.55);}
.screen-label {text-align:center; font-size:.72rem; letter-spacing:.25em; color:#94a3b8; margin-bottom:14px; font-weight:600;}
.legend {display:flex; gap:18px; justify-content:center; font-size:.82rem; color:#cbd5e1; margin:8px 0 14px;}
.legend i {display:inline-block; width:14px; height:14px; border-radius:4px; margin-right:6px; vertical-align:-2px;}
.st-key-seatmap [data-testid="stHorizontalBlock"] {flex-wrap: nowrap !important; gap:.3rem !important; overflow-x:auto;}
.st-key-seatmap [data-testid="stColumn"], .st-key-seatmap [data-testid="column"] {min-width:0 !important;}
.st-key-seatmap [data-testid="stVerticalBlock"] {gap:.3rem !important;}
.st-key-seatmap div.stButton > button {padding:.15rem 0; min-height:2rem; font-size:.78rem;}
</style>
""", unsafe_allow_html=True)


# ---------------- state helpers ----------------
def open_event(eid: int):
    st.session_state.selected = eid
    st.session_state.confirmed = None
    st.session_state.nav = NAV[0]


def close_event():
    st.session_state.selected = None
    st.session_state.confirmed = None


def toggle_seat(eid: int, seat: str):
    sel = st.session_state.setdefault(f"sel_{eid}", [])
    if seat in sel:
        sel.remove(seat)
    elif len(sel) < MAX_SEATS:
        sel.append(seat)
    else:
        st.session_state.flash = f"You can book at most {MAX_SEATS} seats at a time."


@st.cache_resource(show_spinner="Loading AI model (first time only)...")
def get_embeddings():
    return load_embeddings()


def get_bot() -> EventBot:
    if "bot" not in st.session_state:
        st.session_state.bot = EventBot(get_embeddings())
    return st.session_state.bot


def valid_email(s: str) -> bool:
    s = s.strip()
    return "@" in s and "." in s.split("@")[-1] and " " not in s


# ---------------- home ----------------
def event_card(e: dict):
    with st.container(border=True):
        st.image(poster_for(e))
        st.markdown(f"**{e['title']}**")
        st.caption(f"📅 {fmt_date_short(e['event_date'])} · {fmt_time(e['start_time'])}  \n"
                   f"📍 {e['venue']}, {e['city']}")
        left = e["seats_left"]
        if left <= 0:
            badge = "🔴 Sold out"
        elif left / e["capacity"] < 0.25:
            badge = "🟠 Filling fast"
        else:
            badge = "🟢 Available"
        st.markdown(f"<span class='price'>{'Free' if not e['base_price'] else 'from ' + fmt_price(e['base_price'])}"
                    f"</span> &nbsp; {badge}", unsafe_allow_html=True)
        st.button("Book tickets" if left > 0 else "Sold out", key=f"card_{e['id']}",
                  disabled=left <= 0, on_click=open_event, args=(e["id"],))


def home():
    if st.session_state.get("confirmed"):
        return confirmation_view(st.session_state.confirmed)
    if st.session_state.get("selected"):
        return event_page(st.session_state.selected)

    events = db.list_events(upcoming_only=True)
    c1, c2, c3 = st.columns([2, 1, 1])
    q = c1.text_input("Search", placeholder="🔍 Search events, venues, artists...",
                      label_visibility="collapsed").strip().lower()
    city = c2.selectbox("City", ["All cities"] + sorted({e["city"] for e in events}),
                        label_visibility="collapsed")
    sort = c3.selectbox("Sort", ["Date", "Popularity", "Price: low to high"],
                        label_visibility="collapsed")

    shown = [e for e in events
             if (city == "All cities" or e["city"] == city)
             and (not q or q in " ".join([e["title"], e["venue"], e["city"], e["category"],
                                          e["description"]]).lower())]
    if not shown:
        st.info("No events match your search. Try another city or keyword.")
        return

    hero = next((e for e in shown if e["featured"]), shown[0])
    st.image(make_banner(hero))
    b1, _ = st.columns([1, 4])
    b1.button("🎟️ Book now", key="hero_book", type="primary", on_click=open_event, args=(hero["id"],))

    cat = st.radio("Category", ["All"] + sorted({e["category"] for e in shown}),
                   horizontal=True, label_visibility="collapsed")
    if cat != "All":
        shown = [e for e in shown if e["category"] == cat]
    if sort == "Popularity":
        shown.sort(key=lambda e: -e["booked"])
    elif sort.startswith("Price"):
        shown.sort(key=lambda e: e["base_price"])

    st.subheader("Recommended events" if city == "All cities" else f"Events in {city}")
    for i in range(0, len(shown), 4):
        for col, e in zip(st.columns(4), shown[i:i + 4]):
            with col:
                event_card(e)


# ---------------- event page + seat selection ----------------
def event_page(eid: int):
    e = db.get_event(eid)
    if not e:
        close_event()
        st.rerun()
    st.button("← Back to events", on_click=close_event, key="back_top")
    left, right = st.columns([1, 2.2])
    with left:
        st.image(poster_for(e))
    with right:
        st.title(e["title"])
        st.markdown(f"<span class='chip'>{e['category']}</span><span class='chip'>{e['language']}</span>"
                    f"<span class='chip'>{fmt_duration(e['duration_min'])}</span>"
                    f"<span class='chip'>{e['seats_left']} seats left</span>", unsafe_allow_html=True)
        st.markdown(f"📅 **{fmt_date(e['event_date'])}** at **{fmt_time(e['start_time'])}**  \n"
                    f"📍 {e['venue']}, {e['city']}")
        st.write(e["description"])
        if e["base_price"]:
            st.markdown(f"💺 Standard **{fmt_price(e['base_price'])}**  ·  "
                        f"Premium (rows A-{row_letter(PREMIUM_ROWS - 1)}) "
                        f"**{fmt_price(price_for_row(e['base_price'], 0))}**")
        else:
            st.markdown("💺 **Free entry** - just reserve your seat")
    st.divider()
    seat_section(e)


def seat_section(e: dict):
    eid = e["id"]
    st.subheader("Select your seats")
    if st.session_state.get("flash"):
        st.warning(st.session_state.pop("flash"))
    booked = db.booked_seats(eid)
    sel = st.session_state.setdefault(f"sel_{eid}", [])
    sel[:] = [s for s in sel if s not in booked]

    st.markdown("<div class='legend'><span><i style='background:#2a2e3a;border:1px solid #555'></i>Available</span>"
                "<span><i style='background:#f84464'></i>Selected</span>"
                "<span><i style='background:#3a3d46;opacity:.5'></i>Sold</span></div>",
                unsafe_allow_html=True)
    rows, cols = e["seat_rows"], e["seat_cols"]
    half = cols // 2
    with st.container(key="seatmap"):
        st.markdown("<div class='screen'></div><div class='screen-label'>ALL EYES THIS WAY · STAGE / SCREEN</div>",
                    unsafe_allow_html=True)
        for r in range(rows):
            if not e["base_price"]:
                if r == 0:
                    st.caption("FREE SEATING")
            elif r == 0:
                st.caption(f"PREMIUM · {fmt_price(price_for_row(e['base_price'], 0))}")
            elif r == PREMIUM_ROWS:
                st.caption(f"STANDARD · {fmt_price(e['base_price'])}")
            cs = st.columns([1.2] + [1] * half + [0.6] + [1] * (cols - half))
            cs[0].markdown(f"**{row_letter(r)}**")
            for c in range(cols):
                label = seat_label(r, c)
                idx = 1 + c + (1 if c >= half else 0)
                cs[idx].button(
                    str(c + 1), key=f"s_{eid}_{label}",
                    type="primary" if label in sel else "secondary",
                    disabled=label in booked, on_click=toggle_seat, args=(eid, label),
                    help=f"{label} · {fmt_price(price_for_row(e['base_price'], r))}")
    st.divider()
    if not sel:
        st.info(f"👆 Tap seats on the map to select them (max {MAX_SEATS}).")
        return
    sorted_seats = sorted(sel, key=seat_sort)
    total = sum(price_for_seat(e["base_price"], s) for s in sorted_seats)
    num_tickets = len(sorted_seats)
    st.markdown(f"**Selected seats ({num_tickets}):** {', '.join(sorted_seats)}  ·  "
                f"**Total: {fmt_price(total)}**")
    with st.form(f"checkout_{eid}"):
        st.markdown("##### 👤 Primary Contact Details")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Booker Full Name *", placeholder="e.g. Vrutanshi Patel")
        email = c2.text_input("Email Address *", placeholder="e.g. you@example.com")
        phone = c3.text_input("Phone Number (optional)", placeholder="e.g. 9876543210")

        att_inputs = {}
        if num_tickets > 1:
            st.markdown(f"##### 👥 Attendee Names ({num_tickets} Tickets — each ticket gets its own individual QR pass)")
            st.caption("Enter the name of each guest attending. Their individual entry pass and unique QR code will be generated under their name.")
            att_cols = st.columns(2 if num_tickets <= 4 else 3)
            for idx, s in enumerate(sorted_seats):
                col = att_cols[idx % len(att_cols)]
                hint = " (Booker)" if idx == 0 else f" (Guest {idx + 1})"
                att_inputs[s] = col.text_input(
                    f"Seat {s}{hint}",
                    placeholder=f"Name for {s}",
                    key=f"att_in_{eid}_{s}")
        else:
            st.caption(f"Ticket for Seat {sorted_seats[0]} will be issued under the Booker Full Name.")

        st.caption("🔒 Demo checkout - instant confirmation, no real payment.")
        pay = st.form_submit_button(
            f"Pay {fmt_price(total)} & Issue {num_tickets} Ticket{'s' if num_tickets > 1 else ''}"
            if total else f"Confirm Free Booking ({num_tickets} Ticket{'s' if num_tickets > 1 else ''})",
            type="primary")

    if pay:
        if not name.strip() or not valid_email(email):
            st.error("Please enter your name and a valid email address.")
        else:
            attendees = {}
            for idx, s in enumerate(sorted_seats):
                custom = att_inputs.get(s, "").strip() if att_inputs else ""
                if custom:
                    attendees[s] = custom
                elif idx == 0:
                    attendees[s] = name.strip()
                else:
                    attendees[s] = f"{name.strip()} (Guest {idx + 1})"

            ok, msg, code = db.book_seats(eid, sorted_seats, name, email, phone, attendees=attendees)
            if ok:
                st.session_state[f"sel_{eid}"] = []
                st.session_state.confirmed = code
                st.rerun()
            else:
                st.error(msg)


def confirmation_view(code: str):
    b = db.get_booking(code)
    if not b:
        st.session_state.confirmed = None
        st.rerun()
    if st.session_state.get("balloons_for") != code:
        st.balloons()
        st.session_state.balloons_for = code

    tickets = b.get("tickets", [])
    num_tickets = len(tickets)
    st.success(f"🎉 Booking confirmed! Booking ID: **{code}**")
    st.markdown(f"### {b['event']['title']}  \n"
                f"📅 **{fmt_date(b['event']['event_date'])}** at **{fmt_time(b['event']['start_time'])}**  ·  "
                f"📍 **{b['event']['venue']}, {b['event']['city']}**  \n"
                f"🎟️ **{num_tickets} Ticket{'s' if num_tickets > 1 else ''} Generated** ({', '.join(b['seats'])})  ·  "
                f"Total: **{fmt_price(b['total'])}**")

    if num_tickets <= 1:
        png = make_ticket_png(b)
        st.image(png)
        att_name = tickets[0]["attendee_name"] if tickets else b["name"]
        seat_label = tickets[0]["seat"] if tickets else b["seats"][0]
        st.download_button(f"⬇️ Download Ticket (Seat {seat_label} - {att_name})", png,
                           f"ticket_{code}_{seat_label}.png", "image/png", type="primary")
    else:
        st.info("💡 **Each ticket has its own attendee name and unique QR code pass.** "
                "Download them individually or download all at once as a ZIP package.")
        zip_bytes = make_tickets_zip(b)
        st.download_button(f"📦 Download All {num_tickets} Tickets (ZIP)", zip_bytes,
                           f"tickets_{code}.zip", "application/zip", type="primary")
        st.write("")
        tab_titles = [f"🎟️ Seat {t['seat']} ({t['attendee_name']})" for t in tickets]
        tabs = st.tabs(tab_titles)
        for idx, (tab, t) in enumerate(zip(tabs, tickets)):
            with tab:
                png = make_single_ticket_png(b["event"], b["code"], t,
                                             total_tickets=num_tickets, ticket_num=idx + 1)
                st.image(png)
                safe_name = t['attendee_name'].replace(' ', '_')
                st.download_button(
                    f"⬇️ Download Ticket (Seat {t['seat']} - {t['attendee_name']})",
                    png, f"ticket_{code}_{t['seat']}_{safe_name}.png", "image/png",
                    key=f"dl_conf_{idx}")

    st.divider()
    st.button("← Back to events", on_click=close_event, key="back_conf")


# ---------------- my bookings ----------------
def my_bookings():
    st.subheader("🎫 My Bookings")
    q = st.text_input("Booking ID or email", placeholder="e.g. EPAB12CD or you@example.com").strip()
    if not q:
        st.caption("Enter the booking ID from your confirmation, or the email you booked with.")
        return
    if "@" in q:
        found = db.bookings_by_email(q)
    else:
        b = db.get_booking(q)
        found = [b] if b else []
    if not found:
        st.warning("No bookings found.")
    for b in found:
        tickets = b.get("tickets", [])
        num_t = len(tickets)
        title = f"{b['code']} · {b['event']['title']} · {num_t} Ticket{'s' if num_t > 1 else ''} ({', '.join(b['seats'])}) · Total: {fmt_price(b['total'])}"
        with st.expander(title, expanded=True):
            st.markdown(f"📅 **{fmt_date(b['event']['event_date'])}** at **{fmt_time(b['event']['start_time'])}**  ·  "
                        f"📍 {b['event']['venue']}, {b['event']['city']}")
            if num_t > 1:
                st.info(f"👥 **{num_t} Individual Tickets** — each with distinct attendee name & QR code")
                zip_bytes = make_tickets_zip(b)
                st.download_button(f"📦 Download All {num_t} Tickets (ZIP)", zip_bytes,
                                   f"tickets_{b['code']}.zip", "application/zip",
                                   key=f"zip_{b['code']}", type="primary")
                tabs = st.tabs([f"Seat {t['seat']} ({t['attendee_name']})" for t in tickets])
                for idx, (tab, t) in enumerate(zip(tabs, tickets)):
                    with tab:
                        png = make_single_ticket_png(b["event"], b["code"], t,
                                                     total_tickets=num_t, ticket_num=idx + 1)
                        st.image(png)
                        safe_name = t['attendee_name'].replace(' ', '_')
                        st.download_button(
                            f"⬇️ Download Ticket (Seat {t['seat']} - {t['attendee_name']})",
                            png, f"ticket_{b['code']}_{t['seat']}_{safe_name}.png", "image/png",
                            key=f"dl_{b['code']}_{idx}")
            else:
                png = make_ticket_png(b)
                st.image(png)
                st.download_button(f"⬇️ Download Ticket ({b['seats'][0]})", png,
                                   f"ticket_{b['code']}.png", "image/png",
                                   key=f"dl_{b['code']}", type="primary")


# ---------------- AI assistant ----------------
def chat_page():
    st.subheader("🤖 Ask EventPilot")
    bot = get_bot()
    st.caption(f"Ask about events, seats, prices or policies in English, Hindi or Gujarati · Mode: {bot.mode}")
    msgs = st.session_state.setdefault("messages", [])
    for i, m in enumerate(msgs):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            for r in m.get("refs", [])[:3]:
                st.button(f"🎟️ View & book: {r['title']}", key=f"hist_{i}_{r['id']}",
                          on_click=open_event, args=(r["id"],))

    prompt = st.chat_input("Ask anything about events...")
    cols = st.columns(len(SUGGESTIONS))
    for i, s in enumerate(SUGGESTIONS):
        if cols[i].button(s, key=f"sug{i}"):
            prompt = s
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                bot.refresh(db.list_events(upcoming_only=True))
                text, sources, refs = bot.answer(prompt, msgs)
            st.markdown(text)
            st.caption("Sources: " + ", ".join(sources))
        msgs += [{"role": "user", "content": prompt},
                 {"role": "assistant", "content": text, "refs": refs}]
        st.rerun()


# ---------------- admin ----------------
def save_upload(eid: int, up) -> bool:
    ext = Path(up.name).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return False
    data = up.getvalue()
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        return False
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    path = POSTER_DIR / f"upload_{eid}{ext}"
    path.write_bytes(data)
    db.set_image(eid, str(path))
    return True


def admin():
    st.subheader("⚙️ Admin panel")
    if not st.session_state.get("is_admin"):
        pwd = st.text_input("Admin password", type="password")
        if st.button("Login"):
            if pwd == os.getenv("ADMIN_PASSWORD", "admin123"):
                st.session_state.is_admin = True
                st.rerun()
            st.error("Wrong password.")
        st.caption("Demo password: admin123 (change it in .env)")
        return
    t1, t2, t3, t4 = st.tabs(["📊 Dashboard", "➕ Create event", "🗂️ Manage events", "📋 Bookings"])

    with t1:
        s = db.stats()
        a, b, c, d = st.columns(4)
        a.metric("Events", s["events"])
        b.metric("Bookings", s["bookings"])
        c.metric("Tickets sold", s["tickets"])
        d.metric("Revenue", f"₹{s['revenue']:,.0f}")
        st.markdown("**Tickets sold per event**")
        st.bar_chart(pd.DataFrame(db.tickets_by_event()).set_index("title"))
        st.markdown("**Revenue by category (₹)**")
        st.bar_chart(pd.DataFrame(db.revenue_by_category()).set_index("category"))

    with t2:
        with st.form("new_event", clear_on_submit=True):
            title = st.text_input("Title")
            desc = st.text_area("Description")
            c1, c2, c3 = st.columns(3)
            category = c1.selectbox("Category", CATEGORIES)
            city = c2.text_input("City")
            venue = c3.text_input("Venue")
            d1, d2, d3 = st.columns(3)
            dt = d1.date_input("Date", min_value=date.today())
            tm = d2.time_input("Start time", value=time(18, 0))
            mins = d3.number_input("Duration (minutes)", 15, 1440, 120, step=15)
            e1, e2, e3, e4 = st.columns(4)
            lang = e1.text_input("Language", value="English")
            nrows = e2.number_input("Seat rows", 1, 20, 8)
            ncols = e3.number_input("Seats per row", 1, 20, 12)
            price = e4.number_input("Base price (₹, 0 = free)", 0, 100000, 0)
            featured = st.checkbox("Feature on home banner")
            up = st.file_uploader("Poster image (optional)", type=["jpg", "jpeg", "png", "webp"])
            url = st.text_input("...or image URL (optional)")
            go = st.form_submit_button("Create event", type="primary")
        if go:
            if not (title.strip() and desc.strip() and city.strip() and venue.strip()):
                st.error("Title, description, city and venue are required.")
            else:
                eid = db.add_event(title.strip(), desc.strip(), category, city.strip(), venue.strip(),
                                   dt.isoformat(), tm.strftime("%H:%M"), mins, lang.strip() or "English",
                                   nrows, ncols, price, url.strip(), featured)
                if up is not None and not save_upload(eid, up):
                    st.warning("Event created, but the image could not be used (use jpg/png/webp).")
                st.success("Event created! It is live on the Home page and the chatbot already knows it.")

    with t3:
        for e in db.list_events():
            a, b, c = st.columns([5, 1.3, 1])
            a.markdown(f"**{e['title']}** · {e['city']} · {fmt_date_short(e['event_date'])} · "
                       f"{e['booked']}/{e['capacity']} sold{'  ⭐' if e['featured'] else ''}")
            if b.button("Unfeature" if e["featured"] else "Feature", key=f"ft_{e['id']}"):
                db.set_featured(e["id"], not e["featured"])
                st.rerun()
            if c.button("Delete", key=f"dl_{e['id']}"):
                db.delete_event(e["id"])
                st.rerun()

    with t4:
        rows = db.list_bookings()
        if not rows:
            st.info("No bookings yet.")
        else:
            df = pd.DataFrame(rows)
            st.dataframe(df)
            st.download_button("Download CSV", df.to_csv(index=False), "bookings.csv", "text/csv")
    if st.button("Log out", key="logout"):
        st.session_state.is_admin = False
        st.rerun()


# ---------------- layout ----------------
st.session_state.setdefault("nav", NAV[0])
h1, h2 = st.columns([1, 2.2])
h1.markdown("<div class='brand'>🎟️ Event<span>Pilot</span></div>", unsafe_allow_html=True)
page = h2.radio("Navigation", NAV, horizontal=True, label_visibility="collapsed", key="nav")
{"🏠 Home": home, "🤖 Ask AI": chat_page, "🎫 My Bookings": my_bookings, "⚙️ Admin": admin}[page]()
