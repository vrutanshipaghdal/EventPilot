"""RAG chatbot: LangChain + FAISS over live event data and the FAQ."""
import hashlib
import json
import os
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils import PREMIUM_ROWS, fmt_date, fmt_duration, fmt_price, fmt_time, price_for_row

FAQ_PATH = Path(__file__).parent / "data" / "faq.md"

SYSTEM_PROMPT = """You are EventPilot, a friendly assistant for an event booking platform.
Answer ONLY using the context below. If the answer is not in the context, say you are not
sure and suggest contacting the organiser at support@eventpilot.example.
Be concise. When relevant mention date, time, venue, price and seats left.
Seats left of 0 means the event is sold out. To book, tell the user to open the
'Browse & Book' page. Reply in the same language the user writes in
(English, Hindi or Gujarati).

Context:
{context}
"""


def load_embeddings():
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    except Exception as exc:
        print(f"[rag] HuggingFaceEmbeddings failed ({exc}), falling back to lightweight embeddings")
        import numpy as np
        from langchain_core.embeddings import Embeddings

        class FallbackEmbeddings(Embeddings):
            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                res = []
                for t in texts:
                    vec = np.zeros(384, dtype=np.float32)
                    for word in t.lower().split():
                        h = abs(hash(word)) % 384
                        vec[h] += 1.0
                    norm = np.linalg.norm(vec)
                    if norm > 0:
                        vec /= norm
                    res.append(vec.tolist())
                return res

            def embed_query(self, text: str) -> list[float]:
                return self.embed_documents([text])[0]

        return FallbackEmbeddings()


def get_llm():
    """Pick an LLM from env vars. Returns None => retrieval-only mode."""
    provider = os.getenv("LLM_PROVIDER", "none").lower()
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.2)
        if provider == "groq":
            from langchain_groq import ChatGroq
            return ChatGroq(model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                            temperature=0.2)
        if provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=os.environ["ANTHROPIC_MODEL"], temperature=0.2)
        if provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3.1"), temperature=0.2)
    except Exception as exc:  # missing package / key
        print(f"[rag] LLM init failed ({exc}); falling back to retrieval-only mode")
    return None


def event_to_text(e: dict) -> str:
    if e["base_price"]:
        price = (f"Standard seats {fmt_price(e['base_price'])}, premium front rows "
                 f"(A-{chr(64 + PREMIUM_ROWS)}) {fmt_price(price_for_row(e['base_price'], 0))}")
    else:
        price = "Free entry"
    seats = "SOLD OUT" if e["seats_left"] <= 0 else f"{e['seats_left']} of {e['capacity']} seats left"
    return (f"Event: {e['title']} | Category: {e['category']} | City: {e['city']} | "
            f"Venue: {e['venue']} | Date: {fmt_date(e['event_date'])} at {fmt_time(e['start_time'])} | "
            f"Duration: {fmt_duration(e['duration_min'])} | Language: {e['language']} | "
            f"Price: {price} | Availability: {seats}. {e['description']}")


def build_documents(events: list[dict]) -> list[Document]:
    docs = [Document(page_content=event_to_text(e),
                     metadata={"source": f"event:{e['title']}", "event_id": e["id"],
                               "title": e["title"]}) for e in events]
    if FAQ_PATH.exists():
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        for chunk in splitter.split_text(FAQ_PATH.read_text(encoding="utf-8")):
            docs.append(Document(page_content=chunk, metadata={"source": "faq"}))
    return docs


class EventBot:
    def __init__(self, embeddings, k: int = 4):
        self.embeddings = embeddings
        self.llm = get_llm()
        self.k = k
        self.store = None
        self._sig = None

    @property
    def mode(self) -> str:
        return "LLM + RAG" if self.llm else "Retrieval only (no LLM key set)"

    def refresh(self, events: list[dict]) -> None:
        """Rebuild the index only when events or seat counts changed."""
        sig = hashlib.md5(json.dumps(events, sort_keys=True, default=str).encode()).hexdigest()
        if sig == self._sig and self.store is not None:
            return
        self.store = FAISS.from_documents(build_documents(events), self.embeddings)
        self._sig = sig

    def answer(self, question: str, history: list[dict] | None = None):
        """Return (answer_text, sources, event_refs)."""
        docs = self.store.as_retriever(search_kwargs={"k": self.k}).invoke(question)
        sources = sorted({d.metadata.get("source", "?") for d in docs})
        refs, seen = [], set()
        for d in docs:
            eid = d.metadata.get("event_id")
            if eid and eid not in seen:
                seen.add(eid)
                refs.append({"id": eid, "title": d.metadata.get("title", "event")})
        context = "\n\n".join(d.page_content for d in docs)

        if self.llm is None:
            text = "Here is what I found:\n\n" + "\n\n".join(f"- {d.page_content}" for d in docs[:3])
            return text, sources, refs

        messages = [SystemMessage(content=SYSTEM_PROMPT.format(context=context))]
        for m in (history or [])[-6:]:
            cls = HumanMessage if m["role"] == "user" else AIMessage
            messages.append(cls(content=m["content"]))
        messages.append(HumanMessage(content=question))
        try:
            return self.llm.invoke(messages).content, sources, refs
        except Exception as exc:
            text = (f"(LLM unavailable: {exc.__class__.__name__}) Closest matches:\n\n"
                    + "\n\n".join(f"- {d.page_content}" for d in docs[:3]))
            return text, sources, refs
