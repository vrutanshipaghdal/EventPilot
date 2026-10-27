# 🎟️ EventPilot – BookMyShow-style Event Booking + AI Assistant (RAG)

Browse events with posters, pick exact seats on a seat map, book instantly and download a
QR e-ticket. An AI assistant (LangChain + FAISS RAG) answers questions about live events,
seat availability, prices and policies, and jumps users straight to the booking page.

## Features
- Home with hero banner, poster cards, city filter, category filter, search, sorting
- Event page with seat map (premium rows +50%, sold seats locked, max 10 per booking)
- Atomic booking in SQLite (UNIQUE seat constraint + transaction, so no double booking)
- E-ticket PNG with QR code, "My Bookings" lookup by booking ID or email
- RAG chatbot: event data + FAQ, source citations, chat memory, EN/HI/GU replies,
  "View & book" buttons for events it mentions
- Admin: dashboard (revenue, sales charts), create events with poster upload/URL,
  feature/delete events, bookings table + CSV export
- Posters and banners are auto-generated (no internet needed); upload real images in Admin

## Tech stack
Python · Streamlit · SQLite · LangChain · FAISS · Sentence-Transformers · Pillow · qrcode
· LLM via Groq / OpenAI / Anthropic / Ollama (or retrieval-only mode without a key)

## Run (VS Code terminal, inside this folder)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env              # Mac/Linux: cp .env.example .env
streamlit run app.py
```
Add `GROQ_API_KEY` (free at console.groq.com) in `.env`, or set `LLM_PROVIDER=none`.
Admin password: `admin123`. Tests: `pytest -q`.

## Architecture
```
Streamlit UI ─► database.py (events, bookings, booked_seats)
   │                 │ live events + seats left
   │                 ▼
   ├─ posters.py / tickets.py (Pillow, QR)
   └─ rag.py: events + FAQ ► embeddings ► FAISS ► top-k ► LLM ► answer + sources
```

## Using real event photos
Admin → Create event → upload a poster (jpg/png/webp) or paste an image URL.

## Resume bullets (edit to match what you actually did)
- Built **EventPilot**, a BookMyShow-style event booking platform with seat-level selection, QR e-tickets and an admin dashboard (Python, Streamlit, SQLite).
- Implemented a LangChain + FAISS RAG assistant over live event inventory and policy docs, with source citations, multilingual replies and deep links into the booking flow.
- Guaranteed double-booking safety using transactional inserts and a UNIQUE(event, seat) constraint; added hash-based vector index refresh so chatbot answers stay in sync with seat availability.

## Interview talking points
- Why RAG over fine-tuning: seat availability changes every minute.
- Concurrency: BEGIN IMMEDIATE + UNIQUE constraint; what you'd change with Postgres (row locks / SELECT FOR UPDATE).
- Chunking: one document per event, FAQ split at 500 chars / 50 overlap.
- Production next steps: payment gateway (Razorpay), email/SMS tickets, seat-hold timers, auth, Docker + cloud deploy.



cd eventpilot-ai
.\.venv\Scripts\streamlit.exe run app.py