"""
app/api/agent.py — AI Agent endpoint for the APII Database project.

Mount in main.py with:
    from app.api.agent import router as agent_router
    app.include_router(agent_router, prefix="/api/agent")
"""

import os
import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from groq import Groq

from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Groq client
# ---------------------------------------------------------------------------
_groq_client: Groq | None = None


def get_groq() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable is not set")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SQL_SYSTEM_PROMPT = """
You are a MySQL query generator for a database of Tunisian industrial companies.
You MUST output ONLY a raw SQL SELECT statement — no markdown, no code fences,
no explanation, no semicolons at the end.

If the user's question is not about looking up companies in this database,
output the single word: INVALID

=== TABLE SCHEMA ===
Table name: companies

Columns:
  id            INT          primary key
  name          VARCHAR(512) company name
  activity      VARCHAR(512) activity description
  governorate   VARCHAR(128) e.g. "Tunis", "Bizerte", "Sfax", "Sousse" ...
  phone         VARCHAR(64)
  linkedin_url  VARCHAR(1024)
  website       VARCHAR(1024)
  description   TEXT
  size          VARCHAR(128) FREE-TEXT French string, e.g. "51-200 employés",
                             "1 001-5 000 employés", "11-50 employés"
                             → ALWAYS use LIKE for size filters, never exact match
  sector        VARCHAR(256)
  headquarters  VARCHAR(256)
  company_type  VARCHAR(128)
  founded       VARCHAR(32)
  source        VARCHAR(64)
  scrape_stage  VARCHAR(32)  values: scraped | linkedin_found | linkedin_enriched
  created_at    DATETIME
  updated_at    DATETIME

=== TUNISIAN GEOGRAPHY ===
North governorates : Tunis, Ariana, Ben Arous, Manouba, Bizerte, Nabeul,
                     Zaghouan, Béja, Jendouba, Le Kef, Siliana
Centre governorates: Sousse, Monastir, Mahdia, Kairouan, Kasserine,
                     Sidi Bouzid, Sfax
South governorates : Gabès, Médenine, Tataouine, Gafsa, Tozeur, Kébili

When the user refers to a region (north / centre / south), translate it into
the corresponding governorate list and use: governorate IN ('Tunis', 'Ariana', ...)

=== SAFETY RULES ===
• Only SELECT statements are allowed.
• Never include INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, or any DDL/DML.
• Always add LIMIT 50 at the end.
• Select at minimum: id, name, governorate, linkedin_url, size, sector, activity.
• When filtering on size, always use LIKE with % wildcards, e.g.:
    size LIKE '%201%' OR size LIKE '%500%' OR size LIKE '%1 001%' ...
  Do not try to parse the number; match substrings that appear in real values.

Output only the SQL query. Nothing else.
""".strip()

ANSWER_SYSTEM_PROMPT = """
You are a helpful business intelligence assistant for a Tunisian industrial
companies database. Given a user's question and the raw SQL results, write a
concise, helpful answer.

Rules:
- Match the language the user wrote in (French or English).
- Mention the total count of results.
- Highlight a few notable companies if relevant.
- Keep the answer under 150 words.
- Do NOT include the SQL query in your answer.
- Do NOT repeat every company name — the UI will display the full list.
""".strip()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    companies: list[dict[str, Any]]
    sql_used: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_groq(client: Groq, system: str, user: str, max_tokens: int = 512) -> str:
    """Call Groq with a simple single-turn prompt and return the text."""
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return completion.choices[0].message.content.strip()


def _rows_to_dicts(result) -> list[dict[str, Any]]:
    """Convert SQLAlchemy CursorResult rows to plain dicts."""
    keys = list(result.keys())
    return [dict(zip(keys, row)) for row in result.fetchall()]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def agent_chat(body: ChatRequest, db: Session = Depends(get_db)):
    groq = get_groq()
    user_message = body.message.strip()

    # ── Step 1: Generate SQL ──────────────────────────────────────────────
    raw_sql = _call_groq(
        groq,
        system=SQL_SYSTEM_PROMPT,
        user=user_message,
        max_tokens=512,
    )

    # Strip accidental code fences the model might add despite instructions
    for fence in ("```sql", "```mysql", "```", "`"):
        raw_sql = raw_sql.replace(fence, "")
    raw_sql = raw_sql.strip().rstrip(";")

    if raw_sql.upper() == "INVALID" or not raw_sql.lower().startswith("select"):
        return ChatResponse(
            answer=(
                "Je suis désolé, je peux uniquement répondre aux questions concernant "
                "les entreprises de la base de données. / "
                "I can only answer questions about companies in the database."
            ),
            companies=[],
            sql_used=raw_sql,
        )

    # ── Step 2: Execute SQL ───────────────────────────────────────────────
    try:
        result = db.execute(text(raw_sql))
        companies = _rows_to_dicts(result)
    except Exception as exc:
        logger.exception("SQL execution error: %s", exc)
        return ChatResponse(
            answer=(
                "Une erreur s'est produite lors de l'exécution de la requête. "
                "Veuillez réessayer ou reformuler votre question. / "
                "An error occurred while executing the query. Please try again."
            ),
            companies=[],
            sql_used=raw_sql,
        )

    # ── Step 3: Generate natural-language answer ──────────────────────────
    results_summary = (
        f"Total results: {len(companies)}\n"
        + "\n".join(
            f"- {c.get('name', 'N/A')} | {c.get('governorate', '')} | "
            f"{c.get('sector', '')} | {c.get('size', '')}"
            for c in companies[:20]           # send at most 20 rows to the LLM
        )
    )

    answer = _call_groq(
        groq,
        system=ANSWER_SYSTEM_PROMPT,
        user=(
            f"User question: {user_message}\n\n"
            f"Database results:\n{results_summary}"
        ),
        max_tokens=300,
    )

    return ChatResponse(
        answer=answer,
        companies=companies,
        sql_used=raw_sql,
    )