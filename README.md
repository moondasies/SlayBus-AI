# slaybus✦

**Classroom-ready papers. Powered by your syllabus.**

SLAYBUS is an AI copilot for teachers. A teacher uploads a textbook PDF. SLAYBUS reads it, finds the chapters, and builds question papers, worksheets, quizzes and answer keys from that book. Each question records the page it came from.

> 🚧 **Status:** Phase 1 (the agent) is being built. Database schema and API scaffold are done.

---

## The problem

- Teachers in India (Classes 6–12, CBSE / ICSE / State boards) spend hours every week writing test papers and answer keys by hand.
- General chatbots write questions that don't follow the textbook, the chapter or the board pattern, and they sometimes get facts wrong.
- Real papers need a set format: sections, a marks split, a mix of MCQ, short and long answers, and a balance of difficulty.

## How SLAYBUS solves it

| Feature | What it means |
|---|---|
| **Grounded generation (RAG)** | Questions come only from the teacher's own book, and each one is linked to a page |
| **Blueprint control** | Teacher picks chapters, total marks, sections, question types and difficulty mix |
| **Editable output** | Edit, regenerate, reorder or delete any single question |
| **Answer key** | Answers, explanations and marking points are created with the paper |
| **Export** | Printable PDF / DOCX, with or without answers |
| **Question bank** | Every question is saved and can be reused |

---

## Architecture

```
 Teacher ──► Next.js app (frontend/) ──JWT──► FastAPI agent (agent/) ──► Gemini
                   │                                │                  (generate + embed)
                   └──────── Supabase ◄─────────────┘
                     Auth · Storage (PDFs) · Postgres + pgvector
```

**Ingestion** (when a book is uploaded)
PDF → text page by page (pymupdf) → find chapters → split into overlapping chunks → embed each chunk (`gemini-embedding-001`, 768-dim) → save in `chunks`.

**Generation** (when a paper is requested)
Blueprint → for each section and chapter, use vector search to find the closest chunks, spread across the chapter → Gemini (`gemini-2.5-flash`) returns strict JSON → check it against a Pydantic schema, retrying once if it fails → save questions with `source_chunk_ids`.

### What is RAG? (in one paragraph)
*Retrieval-Augmented Generation* is like an open-book exam for the AI. The AI does not answer from memory. We first **retrieve** the few textbook passages that matter most, then give them to the model with the instruction "write questions using only this text". That keeps questions accurate and true to the syllabus. To find those passages we use **embeddings**: each chunk of text becomes a list of 768 numbers that captures its meaning, and passages with similar meanings get similar numbers. pgvector finds the closest ones quickly.

---

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router, TypeScript), Tailwind CSS, framer-motion |
| Agent / API | Python, FastAPI |
| Database | Supabase Postgres + pgvector |
| Auth & storage | Supabase Auth (email + Google), Supabase Storage |
| LLM | Google Gemini `gemini-2.5-flash` |
| Embeddings | `gemini-embedding-001` (768 dimensions) |
| PDF parsing | pymupdf |
| Export | HTML → PDF, `python-docx` |

## Repo structure

```
SlayBus-AI/
├── README.md
├── supabase/
│   └── schema.sql        # tables, RLS, vector index, match_chunks(), storage bucket
├── agent/                # FastAPI service (Phase 1)
│   ├── app/
│   │   ├── main.py       # app + routes
│   │   ├── config.py     # env settings
│   │   └── db.py         # Supabase client
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
└── frontend/             # Next.js app (Phase 2)
```

---

## Setup

### 1. Database (Supabase)
1. Create a project at [supabase.com](https://supabase.com).
2. Open **SQL Editor → New query**, paste all of [`supabase/schema.sql`](supabase/schema.sql) and click **Run**. The script is safe to run again.
3. Check that **Table Editor** shows `profiles, textbooks, chapters, chunks, papers, questions` and that **Storage** shows a private `textbooks` bucket.

### 2. Agent
```bash
cd agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in your keys
uvicorn app.main:app --reload --port 8000
```
- Health check: <http://localhost:8000/health>
- Database check: <http://localhost:8000/health?check_db=true>
- Interactive API docs: <http://localhost:8000/docs>

### 3. Tests
```bash
cd agent
pytest -q
```

## Security
- Row Level Security on every table means a teacher can read and write only their own rows.
- PDFs are stored in a private bucket, inside a folder for each teacher (`<user_id>/...`).
- The agent uses the service-role key on the server only, and filters every query by the user ID from the verified JWT.
- Secrets live in `.env` files, which git ignores.

## Roadmap
- [x] Database schema + RLS + vector search
- [x] Agent scaffold + `/health`
- [ ] Ingestion: PDF → chapters → chunks → embeddings
- [ ] Retrieval
- [ ] Paper generation + answer key
- [ ] Edit / regenerate a single question
- [ ] Export PDF / DOCX
- [ ] Frontend app
- [ ] Auth + onboarding
