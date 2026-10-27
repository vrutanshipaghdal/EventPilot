"""Renders downloadable high-quality e-ticket PNGs (each with a unique QR code and attendee name)."""
from io import BytesIO
import zipfile

from PIL import Image, ImageDraw

from posters import font, theme
from utils import fmt_date, fmt_price, fmt_time, seat_sort


def _qr(data: str, size: int):
    """Generates an in-memory QR code image."""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=8, border=1)
        qr.add_data(data)
        qr.make(fit=True)
        im = qr.make_image(fill_color="black", back_color="white")
        im = im.get_image() if hasattr(im, "get_image") else im
        return im.convert("RGB").resize((size, size), Image.NEAREST)
    except Exception:
        return None


def make_single_ticket_png(event: dict, booking_code: str, ticket: dict,
                           total_tickets: int = 1, ticket_num: int = 1) -> bytes:
    """Renders a beautiful 1050x420 ticket pass for an individual attendee."""
    W, H = 1050, 420
    accent, _ = theme(event.get("category", "Other"))
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)

    # Outer border
    d.rounded_rectangle([2, 2, W - 3, H - 3], radius=16, outline=(226, 232, 240), width=2)

    # Accent color bar on left edge
    d.rounded_rectangle([0, 0, 24, H], radius=12, fill=accent)
    d.rectangle([12, 0, 24, H], fill=accent)

    grey = (100, 116, 139)
    dark = (15, 23, 42)

    # Header branding
    d.text((56, 30), "EVENTPILOT  ·  OFFICIAL E-TICKET", font=font(18), fill=grey)
    pass_label = f"PASS {ticket_num} OF {total_tickets}" if total_tickets > 1 else "ADMIT ONE"
    pw = d.textlength(pass_label, font=font(16))
    chip_x2 = 680
    chip_x1 = int(chip_x2 - pw - 24)
    d.rounded_rectangle([chip_x1, 24, chip_x2, 52], radius=14, fill=accent)
    d.text((chip_x1 + 12, 30), pass_label, font=font(16), fill="white")

    # Event Title (wrapped)
    title = event.get("title", "Event")
    tf = font(34)
    words, line, lines = title.split(), "", []
    for w in words:
        trial = f"{line} {w}".strip()
        if d.textlength(trial, font=tf) <= 630 or not line:
            line = trial
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)

    y = 66
    for ln in lines[:2]:
        d.text((56, y), ln, font=tf, fill=dark)
        y += 42

    # Date and venue
    dt_str = f"📅 {fmt_date(event['event_date'])}  ·  {fmt_time(event['start_time'])}"
    d.text((56, y + 8), dt_str, font=font(21), fill=(51, 65, 85))
    ven_str = f"📍 {event.get('venue', '')}, {event.get('city', '')}"[:54]
    d.text((56, y + 36), ven_str, font=font(19), fill=grey)

    # Info cards: Attendee Name, Seat, Price
    by = H - 124
    # Card 1: Attendee
    d.rounded_rectangle([56, by, 350, by + 92], radius=12, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((72, by + 12), "ATTENDEE", font=font(14), fill=grey)
    att_name = (ticket.get("attendee_name") or "Guest").strip()
    d.text((72, by + 32), att_name[:20], font=font(26), fill=dark)
    t_code = ticket.get("ticket_code") or f"{booking_code}-{ticket.get('seat', '1')}"
    d.text((72, by + 66), f"Pass ID: {t_code}", font=font(14), fill=grey)

    # Card 2: Seat
    d.rounded_rectangle([366, by, 510, by + 92], radius=12, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((382, by + 12), "SEAT", font=font(14), fill=grey)
    seat = ticket.get("seat", "-")
    d.text((382, by + 32), seat, font=font(30), fill=accent)
    try:
        tier = "Premium" if ord(seat[0].upper()) - 65 < 2 else "Standard"
    except Exception:
        tier = "Standard"
    d.text((382, by + 66), tier, font=font(14), fill=grey)

    # Card 3: Price
    d.rounded_rectangle([526, by, 680, by + 92], radius=12, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((542, by + 12), "STATUS", font=font(14), fill=grey)
    price_val = ticket.get("price", 0)
    d.text((542, by + 32), fmt_price(price_val), font=font(24), fill=dark)
    d.text((542, by + 66), "● Confirmed", font=font(14), fill=(16, 149, 74))

    # Perforation Tear Line with round notches
    cut_x = 730
    notch_r = 18
    # Top cutout notch
    d.pieslice([cut_x - notch_r, -notch_r, cut_x + notch_r, notch_r], 0, 180, fill=(241, 245, 249), outline=(226, 232, 240))
    # Bottom cutout notch
    d.pieslice([cut_x - notch_r, H - notch_r, cut_x + notch_r, H + notch_r], 180, 360, fill=(241, 245, 249), outline=(226, 232, 240))

    # Dashed line
    for yy in range(24, H - 24, 14):
        d.line([(cut_x, yy), (cut_x, yy + 7)], fill=(203, 213, 225), width=2)

    # Right stub: Unique QR Code for this ticket
    qr_data = (f"EVENTPILOT|TICKET:{t_code}|SEAT:{seat}|ATTENDEE:{att_name}|"
               f"EVENT:{event.get('title', '')}|DATE:{event.get('event_date', '')}|REF:{booking_code}")
    qr = _qr(qr_data, 195)
    if qr:
        img.paste(qr, (788, 50))

    d.text((885, 272), t_code, font=font(24), fill=dark, anchor="mm")
    d.text((885, 302), f"Booking Ref: {booking_code}", font=font(15), fill=grey, anchor="mm")
    d.text((885, 332), "Valid for Single Entry", font=font(15), fill=dark, anchor="mm")
    d.text((885, 356), "Scan QR at venue gate", font=font(13), fill=grey, anchor="mm")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_ticket_png(b: dict, seat: str | None = None) -> bytes:
    """Generates an individual ticket pass PNG (backward compatible with make_ticket_png(b))."""
    event = b.get("event") or {}
    code = b.get("code", "EP000000")
    tickets = b.get("tickets")

    if not tickets:
        # Fallback if booking lacks 'tickets' list
        seats = b.get("seats", ["General"])
        tickets = [{"seat": s, "price": b.get("total", 0) / max(len(seats), 1),
                    "attendee_name": b.get("name", "Guest"),
                    "ticket_code": f"{code}-{s}"} for s in seats]

    target = None
    target_idx = 1
    if seat:
        for idx, t in enumerate(tickets):
            if t.get("seat") == seat:
                target = t
                target_idx = idx + 1
                break
    if not target:
        target = tickets[0]
        target_idx = 1

    return make_single_ticket_png(event, code, target, total_tickets=len(tickets), ticket_num=target_idx)


def make_all_tickets(b: dict) -> list[dict]:
    """Returns all ticket objects with their PNG bytes and file names."""
    event = b.get("event") or {}
    code = b.get("code", "EP000000")
    tickets = b.get("tickets") or []
    if not tickets:
        seats = b.get("seats", ["General"])
        tickets = [{"seat": s, "price": b.get("total", 0) / max(len(seats), 1),
                    "attendee_name": b.get("name", "Guest"),
                    "ticket_code": f"{code}-{s}"} for s in seats]

    res = []
    total = len(tickets)
    for idx, t in enumerate(tickets):
        png = make_single_ticket_png(event, code, t, total_tickets=total, ticket_num=idx + 1)
        safe_name = "".join(c for c in t.get("attendee_name", "") if c.isalnum() or c in (" ", "_")).strip()
        fname = f"Ticket_{code}_{t.get('seat', 'seat')}_{safe_name or 'Pass'}.png"
        res.append({
            "seat": t.get("seat", "-"),
            "attendee_name": t.get("attendee_name", "Guest"),
            "ticket_code": t.get("ticket_code", f"{code}-{t.get('seat', '1')}"),
            "png": png,
            "filename": fname
        })
    return res


def make_tickets_zip(b: dict) -> bytes:
    """Bundles all ticket PNGs for a booking into a single ZIP file."""
    all_tickets = make_all_tickets(b)
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in all_tickets:
            zf.writestr(item["filename"], item["png"])
    return buf.getvalue()
