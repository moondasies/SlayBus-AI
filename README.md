# slaybus✦

**Classroom-ready papers. Powered by your syllabus.**

SLAYBUS is an AI copilot for school teachers. A teacher uploads a textbook PDF. SLAYBUS reads it, finds the chapters, and builds question papers, worksheets, quizzes and answer keys from that book. Each question records the page it came from.

> **Status:** working MVP. Agent, frontend and auth are built and tested end to end (36 API/unit tests, plus a 19-step browser test of the full teacher journey).

---

## The problem

- Teachers in India (Classes 6–12, CBSE / ICSE / State boards) spend **hours every week** writing test papers, worksheets and answer keys by hand.
- General chatbots write questions that **don't follow the textbook, the chapter or the board pattern**, and they sometimes get facts wrong.
- Real papers need a **set format**: sections, a marks split, a mix of MCQ, short and long answers, and a balance of difficulty.

## How SLAYBUS solves it

| Feature | What the teacher gets |
|---|---|
| **Grounded generation (RAG)** | Questions are written only from the teacher's own book. Each one links to its source page ("p. 42"), and the original passage is one click away. |
| **Blueprint control** | Teacher picks chapters, paper type (question paper / worksheet / quiz), sections, question types, counts, marks, duration and the easy/medium/hard mix. The marks total is checked live. |
| **Six question types** | MCQ, fill in the blank, true/false, short answer, long answer, case-based |
| **Answer key & marking scheme** | Answers, explanations and per-mark marking points are created with every paper |
| **Editable output** | Edit, regenerate (with a new difficulty or instruction), delete, reorder, or add from the bank |
| **Export** | Print-ready A4 PDF or editable Word (DOCX), with or without the answer key. Worksheets include answer lines. |
| **Question bank** | Every question is saved and can be searched by book, chapter, type and difficulty, then reused |
| **Private by design** | Each teacher sees only their own books, papers and questions |

---

## Architecture

```
                         ┌────────────────────────────── Supabase ───────────────────────────┐
                         │  Auth (email + Google)   Storage (private PDFs)   Postgres+pgvector │
                         └──────▲───────────────────────────▲─────────────────────▲──────────┘
                                │ login (JWT)               │ PDFs                │ SQL (+ vector search)
 Teacher ──► Next.js app ───────┴── Bearer JWT ──► FastAPI agent ─────────────────┘
            (frontend/)                            (agent/)  ──────► Google Gemini
                                                                      gemini-2.5-flash (questions)
                                                                      gemini-embedding-001 (vectors)
```

**1. Ingestion** runs in the background after upload:
`PDF → text page by page (pymupdf) → find chapters → split into overlapping chunks → embed each chunk (768-dim) → save in pgvector`

Chapter detection tries three strategies, best first: the PDF's **bookmarks**, then **"Chapter N" headings** on the page, then **Gemini reading the contents page**. If all three fail, the whole book becomes one chapter.

**2. Generation** runs in the background too, while the UI shows a live status:
`blueprint → plan every question slot (section × chapter × difficulty) → for each group, retrieve passages → Gemini writes JSON → validate → retry or top up → dedupe → save with source chunk ids`

**3. Editing / export:** single-question regenerate uses the same pipeline with "avoid these existing questions". Export renders the same layout to PDF (reportlab) or DOCX (python-docx).

### The AI ideas, in plain words

- **RAG (Retrieval-Augmented Generation)** works like an open-book exam for the AI. It doesn't answer from memory. We first **retrieve** the textbook passages that matter, then tell the model to "write questions using only this text". That keeps questions accurate and true to the syllabus.
- **Embeddings** turn each passage into 768 numbers that capture its meaning, like a spot on a map. Passages about similar ideas sit close together, so "how plants make food" lands near "photosynthesis".
- **Chunking** cuts the book into small overlapping "index cards" (~600 tokens each, with ~100 tokens of overlap) so search is precise and no idea gets lost at a cut line.
- **Retrieval with spread:** we mix the *most similar* chunks with chunks spaced *evenly through the chapter*, and prefer chunks not used yet. That way a paper covers the whole chapter, not just page 1.
- **Structured output:** the model must fill in a fixed JSON shape (a Pydantic schema). Then every question is **validated**. For example, an MCQ needs exactly 4 distinct options and its answer must be one of them, and a fill-in-the-blank needs a blank. Bad output triggers a retry that includes the error messages.
- **Prompt-injection guard:** textbook text goes inside `<excerpt>` tags and is marked as data. Instructions hidden in a PDF are ignored.

---

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router, TypeScript), Tailwind CSS, framer-motion, lucide icons |
| Agent / API | Python 3.11+, FastAPI, Pydantic v2, psycopg 3 (connection pool) |
| Database | Supabase Postgres + pgvector (HNSW cosine index), Row Level Security |
| Auth & storage | Supabase Auth (email + Google), Supabase Storage (private bucket) |
| LLM | Google Gemini `gemini-2.5-flash` via `google-genai` |
| Embeddings | `gemini-embedding-001` at 768 dimensions |
| PDF parsing | pymupdf |
| Export | reportlab (PDF, DejaVu fonts for symbols like °, ₹, Greek), python-docx |
| Testing | pytest (real Postgres + pgvector), Playwright (browser user journey) |

## Repo structure

```
SlayBus-AI/
├── README.md
├── supabase/schema.sql          # tables, RLS, HNSW index, match_chunks(), storage bucket + policies
├── agent/                       # FastAPI service
│   ├── app/
│   │   ├── main.py              # app, routers, /health, startup clean-up
│   │   ├── config.py · db.py · auth.py · storage.py
│   │   ├── llm/                 # gemini.py (real) · fake.py (offline) · base.py (contract)
│   │   ├── ingest/              # pdf_reader · chapters · chunker · embedder · pipeline
│   │   ├── rag/retriever.py     # similarity + spread retrieval
│   │   ├── generate/            # schemas · prompts · validate · paper (orchestrator)
│   │   ├── export/              # layout · pdf · docx (+ fonts)
│   │   └── routers/             # textbooks · papers · questions · profile
│   ├── scripts/                 # setup_local_db.py · make_sample_textbook.py · supabase_stubs.sql
│   ├── tests/                   # unit, Gemini-adapter and end-to-end API tests
│   ├── requirements.txt
│   └── .env.example
└── frontend/                    # Next.js app
    ├── app/                     # landing, login, (app)/dashboard, books, papers, bank, onboarding
    ├── components/ · lib/       # UI kit, question card, preview, API client, auth
    ├── e2e/user-journey.mjs     # Playwright user test
    └── .env.example
```

---

## Setup

### 1. Supabase
1. Create a project at [supabase.com](https://supabase.com).
2. **SQL Editor → New query**, paste all of [`supabase/schema.sql`](supabase/schema.sql) and click **Run**. The script is safe to run again, and running it again also applies upgrades.
3. **Authentication → Sign In / Providers**: Email is on by default. To add Google, enable it and paste a Google OAuth client ID and secret.
4. **Authentication → URL Configuration**: set Site URL to `http://localhost:3000` and add `http://localhost:3000/**` to the Redirect URLs.
5. Collect these values:
   - **Project Settings → API**: Project URL, `anon` key, `service_role` key
   - **Project Settings → JWT Keys**: the legacy JWT secret (if your project uses the new signing keys, leave it empty; the agent then verifies tokens with the project's public keys)
   - **Connect** (top bar) **→ Session pooler**: the Postgres URI for `DATABASE_URL`

### 2. Gemini
Create an API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

### 3. Agent
```bash
cd agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in the values from steps 1 and 2
uvicorn app.main:app --reload --port 8000
```
Check it at <http://localhost:8000/health?check_db=true>. You want `"status": "ok"` and an empty `missing_env`. The API docs are at <http://localhost:8000/docs>.

### 4. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local  # NEXT_PUBLIC_SUPABASE_URL / ANON_KEY, API URL
npm run dev
```
Open <http://localhost:3000>, sign up, upload a textbook and create a paper.

### Offline demo mode (no Supabase or Gemini keys)
For trying the app on a laptop: plain Postgres with pgvector, local file storage, a fake AI that copies sentences out of the book, and a dev login.
```bash
# Postgres with pgvector, e.g. brew install postgresql@16 pgvector
createdb slaybus
python agent/scripts/setup_local_db.py postgresql://localhost/slaybus
```
In `agent/.env` set: `DATABASE_URL=postgresql://localhost/slaybus`, `LLM_PROVIDER=fake`, `STORAGE_BACKEND=local`, `DEV_AUTH=true`, `SUPABASE_JWT_SECRET=<any long string>`.
In `frontend/.env.local` set: `NEXT_PUBLIC_DEV_AUTH=true`.
⚠️ Never enable `DEV_AUTH` in production. It lets anyone log in as any email.

---

## Testing

**Agent: 36 tests.** These cover blueprint maths, validation rules, chunk overlap, chapter detection, JWT checks, and the Gemini adapter against the real SDK types with a mocked network. They also include a two-teacher API journey: upload → ingest → 50-mark paper → edit → regenerate → reorder → bank → PDF/DOCX → privacy checks.
```bash
cd agent
export TEST_DATABASE_URL=postgresql://localhost/slaybus_test   # empty DB with pgvector
pytest -q
```

**User journey (browser): 19 steps.** Run the agent and frontend in offline mode, then:
```bash
python agent/scripts/make_sample_textbook.py /tmp/book.pdf
cd frontend && npx playwright install chromium
npm run build && npm start   # in another terminal
SAMPLE_PDF=/tmp/book.pdf npm run test:e2e
```
It covers landing → sign-in → onboarding → upload → chapters → 5-step builder (including a blocked invalid difficulty mix) → generation → source passage → edit → rejected bad MCQ edit → regenerate → reorder (survives reload) → delete and re-add from bank → preview → PDF/DOCX download with answer-key toggle → bank filters → second teacher blocked from the paper → iPhone layout → logout. It fails on any unexpected browser console error or failed request.

---

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health?check_db=true` | Health, config and DB check |
| GET / PUT | `/me` | Profile + onboarding |
| POST | `/textbooks` | Upload a PDF (multipart) and start ingestion |
| GET | `/textbooks` · `/textbooks/{id}` | List books / book with chapters and progress |
| POST · DELETE | `/textbooks/{id}/reprocess` · `/textbooks/{id}` | Retry ingestion / delete book |
| POST | `/papers/generate` | Generate from a blueprint (returns 202, poll the paper) |
| GET · PATCH · DELETE | `/papers` · `/papers/{id}` | List / get with questions / rename / delete |
| POST | `/papers/{id}/reorder` · `/papers/{id}/questions` | Reorder / add a question from the bank |
| GET | `/papers/{id}/export?format=pdf\|docx&answers=true\|false` | Download |
| GET | `/questions` | Question bank (filters: textbook, chapter, type, difficulty, search) |
| GET · PATCH · DELETE | `/questions/{id}` | Get / edit / remove (`keep_in_bank=true` by default) |
| POST | `/questions/{id}/regenerate` | New question of the same type and marks |
| GET | `/questions/{id}/sources` | Textbook passages behind a question |

## Security

- **Row Level Security** on every table and on storage. Even through the vector-search function, a teacher only sees their own rows. This is tested.
- The agent verifies Supabase JWTs: HS256 secret, or ES256/RS256 via JWKS, with audience and expiry checks. It filters **every** query by the caller's user id. Other teachers' ids return 404, not 403, so ids can't be probed.
- PDFs are stored in a private bucket under `<user_id>/`. Uploads are checked for PDF magic bytes and a size limit.
- Secrets live in `.env` files, which git ignores. The service-role key never reaches the browser.

## Design decisions

- **The agent talks to Postgres directly** (psycopg pool) instead of through the Supabase REST client. This gives transactions, `executemany` for bulk chunk inserts, and real-database tests.
- **Uploads go through the agent** rather than straight to Storage. One request handles validation, storage and starting ingestion.
- **A pluggable LLM provider** (`LLM_PROVIDER=gemini|fake`) keeps the pipeline testable offline and makes it easy to swap models later.
- **Generation runs in the background, and the UI polls.** A 50-mark paper takes several AI calls. They run 3 at a time, with exponential backoff, to stay within Gemini free-tier rate limits.

## Known limitations / roadmap

- Scanned (image-only) PDFs need OCR, which isn't supported yet. They fail with a clear message.
- Page numbers are PDF page numbers, which can differ from the numbers printed in the book.
- Background jobs run inside the API process. For multiple servers, move them to a job queue.
- Later: diagrams and image questions, Hindi and regional languages, school/team accounts, lesson plans, auto-grading.
