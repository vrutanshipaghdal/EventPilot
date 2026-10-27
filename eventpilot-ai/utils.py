"""Small pure helpers shared by the whole app."""
from datetime import datetime

MAX_SEATS = 10          # max seats per booking
PREMIUM_ROWS = 2        # first 2 rows (A, B) are premium
PREMIUM_MULT = 1.5      # premium seats cost 50% extra


def row_letter(i: int) -> str:
    return chr(ord("A") + i)


def seat_label(row_idx: int, col_idx: int) -> str:
    return f"{row_letter(row_idx)}{col_idx + 1}"


def seat_sort(seat: str):
    return (seat[0], int(seat[1:]))


def price_for_row(base: float, row_idx: int) -> float:
    if base > 0 and row_idx < PREMIUM_ROWS:
        return float(round(base * PREMIUM_MULT))
    return float(base)


def price_for_seat(base: float, seat: str) -> float:
    return price_for_row(base, ord(seat[0]) - 65)


def fmt_date(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%a, %d %b %Y")


def fmt_date_short(iso: str) -> str:
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%a, %d %b")


def fmt_time(hhmm: str) -> str:
    return datetime.strptime(hhmm, "%H:%M").strftime("%I:%M %p").lstrip("0")


def fmt_price(p: float) -> str:
    return "Free" if not p else f"₹{p:,.0f}"


def fmt_duration(mins: int) -> str:
    h, m = divmod(int(mins), 60)
    return f"{h}h {m}m" if h and m else (f"{h}h" if h else f"{m}m")
