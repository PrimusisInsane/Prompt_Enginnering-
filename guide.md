# GenAI App — Full Build Guide

A full-stack GenAI content generator for **Last Call** (nightclub horde-survivor game): generates enemy bark lines using Google's Gemini API, validated, cached, persisted, and served through a GraphQL API to a React frontend.

---

## Architecture Overview

```
React (Vite) frontend
        │  fetch() → GraphQL mutation
        ▼
FastAPI + Ariadne (GraphQL layer)
        │
        ▼
generation.py (retry-on-bad-JSON wrapper)
        │
        ├──► Redis (cache check by enemy_type)
        │
        ▼
llm_client.py → Gemini API (google-genai SDK)
        │
        ▼
schemas.py (Pydantic validation: BarkResponse)
        │
        ▼
storage.py → Postgres (generations table, full history)
```

**Core principle used throughout:** build every layer against a **fake stub** first (no cost, no API key needed), prove the pipeline end-to-end, then swap the stub for the real LLM call as the very last step. Everything downstream of `call_llm()` never needed to change.

---

## Repo Structure

```
main-gen/
├── genai_app/                  # backend (separate git repo)
│   ├── app/
│   │   ├── main.py              # FastAPI app + CORS + GraphQL mount
│   │   ├── config.py             # pydantic-settings, reads .env
│   │   ├── db.py                 # async SQLAlchemy engine + session
│   │   ├── models.py             # Generation model (Mapped[] style)
│   │   ├── schemas.py            # BarkResponse Pydantic schema
│   │   ├── graphql_schema.py     # Ariadne type_defs + resolvers
│   │   ├── services/
│   │   │   ├── llm_client.py     # real Gemini call + markdown-fence stripper
│   │   │   ├── prompts.py        # BARK_SYSTEM_PROMPT + user prompt builder
│   │   │   ├── generation.py     # retry logic + Redis caching wrapper
│   │   │   └── storage.py        # save validated bark to Postgres
│   │   └── scripts/
│   │       └── test_llm.py       # manual smoke-test script
│   ├── alembic/                  # migrations (async env.py)
│   ├── docker-compose.yml        # Postgres + Redis
│   ├── pyproject.toml            # Poetry, PEP 621 format
│   └── .env                      # secrets, never committed
│
└── genai-app-frontend/          # frontend (separate git repo)
    └── src/
        └── App.jsx               # form → GraphQL mutation → rendered results
```

---

## Backend, Step by Step

### 1. Project scaffolding
- Poetry-managed FastAPI project (`poetry init`, `poetry add fastapi uvicorn[standard]`)
- `pydantic-settings` for typed `.env` config instead of loose `os.getenv()`
- Bare `/health` endpoint to prove the server boots

### 2. Docker Compose: Postgres + Redis
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: genai_user
      POSTGRES_PASSWORD: genai_pass
      POSTGRES_DB: genai_app
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7
    ports: ["6379:6379"]

volumes:
  pgdata:
```
Verified independently with `psql -c "SELECT 1;"` and `redis-cli ping`.

### 3. SQLAlchemy async + first model
```python
# db.py
engine = create_async_engine(settings.database_url, echo=True)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass
```
```python
# models.py
class Generation(Base):
    __tablename__ = "generations"
    id: Mapped[int] = mapped_column(primary_key=True)
    content_type: Mapped[str] = mapped_column(String(50))
    prompt_input: Mapped[str] = mapped_column(Text)
    generated_output: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

**Alembic gotcha:** the default template is sync-oriented. For an async engine, `env.py` needs:
- `async_engine_from_config` instead of `engine_from_config`
- `run_migrations_online()` as `async def`, using `connection.run_sync(do_run_migrations)`
- `asyncio.run(run_migrations_online())` at the bottom

Migrated with `alembic revision --autogenerate` + `alembic upgrade head`.

### 4. LLM service, mocked first
```python
# llm_client.py (stub version)
async def call_llm(prompt: str) -> str:
    await asyncio.sleep(0.3)  # simulates real network latency
    return json.dumps({
        "content_type": "enemy_bark",
        "enemy_type": "regular_zombie",
        "lines": ["Last call, sweetheart — for you, it's forever.", ...],
    })
```
Isolating this in its own file meant the *entire rest of the app* could be built and tested with zero API cost, and swapping to the real call later was a one-function change.

### 5. Prompt engineering artifact (`prompts.py`)
Written and refined *before* the real API was wired in:
```python
BARK_SYSTEM_PROMPT = """You are a content generator for "Last Call"...
Tone rules:
- Dark comedy, nightclub/bar-themed wordplay
- CRITICAL: Do not use the same sentence structure twice...
- Vary WHERE the humor lives: threat, setup, wordplay, observation, callback...

Example of GOOD variety:
- "Buy you a drink? Too late for that."
- "Ugh... the DJ's playlist killed me first."

Output ONLY valid JSON matching this schema...
"""
```
**Lesson learned from real output:** the first version produced six lines all following `"[nightclub noun]! [threat to a body part]!"` — same joke, different nouns. Fixed by:
1. Naming the exact failure pattern explicitly (not just "be more varied")
2. Adding real few-shot examples showing structurally different lines
3. Listing categories to draw humor from

### 6. Pydantic validation
```python
class BarkResponse(BaseModel):
    content_type: str
    enemy_type: str
    lines: list[str]
```
Turns "LLM returned a string" into "app has a typed, guaranteed-shape object."

### 7. Retry-on-bad-JSON logic
```python
async def get_validated_bark(prompt: str) -> BarkResponse:
    raw = await call_llm(prompt)
    try:
        return BarkResponse.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError):
        raw_retry = await call_llm(prompt)
        return BarkResponse.model_validate(json.loads(raw_retry))  # raises if this fails too
```
Tested against a simulated malformed response before it ever mattered for real.

### 8. Postgres persistence
```python
async def save_bark_generation(session, prompt_input, validated: BarkResponse) -> Generation:
    record = Generation(
        content_type=validated.content_type,
        prompt_input=prompt_input,
        generated_output=validated.model_dump_json(),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
```

### 9. GraphQL layer (Ariadne)
```graphql
type Query {
  hello: String!
  generations: [GenerationRecord!]!
}
type Mutation {
  generateBark(enemyType: String!): BarkResult!
}
```
Mounted into FastAPI:
```python
app.mount("/graphql", GraphQL(schema, debug=True))
```

### 10. Redis caching
```python
async def get_cached_or_generate_bark(enemy_type: str, prompt: str) -> tuple[BarkResponse, bool]:
    cache_key = f"bark:{enemy_type}"
    cached = await redis_client.get(cache_key)
    if cached:
        return BarkResponse.model_validate(json.loads(cached)), True
    validated = await get_validated_bark(prompt)
    await redis_client.set(cache_key, validated.model_dump_json(), ex=3600)
    return validated, False
```
Postgres still logs every generation (full history); Redis only skips *re-calling the LLM* on a cache hit.

### 11. Flipping to the real Gemini API

**Package:** `google-genai` (current) — NOT `google-generativeai` (deprecated, no more updates).

```python
from google import genai
client = genai.Client(api_key=settings.gemini_api_key)

async def call_llm(prompt: str) -> str:
    full_prompt = f"{BARK_SYSTEM_PROMPT}\n\n{prompt}"
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_prompt,
    )
    return _strip_markdown_fences(response.text)
```

**Real-world gotcha:** Gemini often wraps JSON output in ` ```json ... ``` ` fences despite explicit instructions not to. Fixed with a small stripper run on every response:
```python
def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()
```

**Key format note (as of mid-2026):** Google is migrating Gemini API keys from the old `AIza...` "Standard" format to a new `AQ.Ab...` "Auth key" format — all new keys created in AI Studio now come out as Auth keys by default. Both work with the `google-genai` SDK; only some third-party integrations expecting the old format have trouble.

### Dependency issues hit along the way (and fixes)
| Problem | Cause | Fix |
|---|---|---|
| `arq`/`redis` version conflict | `redis ^8.0.1` incompatible with `arq 0.28.0`'s internal constraint | `poetry add "redis>=4.2,<6" arq` |
| Poetry venv "broke" after moving repo folder | Poetry ties venv identity to folder path hash | `poetry install` in the new location |
| `ImportError: cannot import name 'ExecutionContext'` | `graphql-core 3.3.0rc0` (pre-release) incompatible with `ariadne 1.1.0` | Pin `graphql-core>=3.2.0,<3.3.0` |
| That pin failed with Python version errors | `pyproject.toml` used `python = ...` instead of `requires-python = ...` under `[project]` (PEP 621 format) | Rename key to `requires-python = ">=3.14,<4"` |

---

## Frontend, Step by Step

### 1. Scaffold
```bash
npm create vite@latest genai-app-frontend -- --template react
cd genai-app-frontend && npm install && npm run dev
```
Confirmed the blank Vite + React starter renders before touching any real code.

### 2. CORS (backend side, required before any frontend fetch works)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
Without this, the browser blocks any request from `localhost:5173` → `localhost:8000` as a cross-origin request.

### 3. First query wired (`hello`)
Plain `fetch()`, no GraphQL client library — kept simple deliberately:
```jsx
useEffect(() => {
  fetch('http://localhost:8000/graphql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: `{ hello }` }),
  })
    .then(res => res.json())
    .then(data => setMessage(data.data.hello));
}, []);
```

### 4. Real mutation: the Bark Generator form
```jsx
const handleGenerate = async () => {
  const res = await fetch('http://localhost:8000/graphql', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: `
        mutation GenerateBark($enemyType: String!) {
          generateBark(enemyType: $enemyType) {
            id enemyType lines createdAt
          }
        }`,
      variables: { enemyType },
    }),
  });
  const data = await res.json();
  setLines(data.data.generateBark.lines);
};
```
Basic `useState` for `enemyType`, `lines`, `loading`, `error` — no external state library needed at this scale.

---

## What This Project Actually Demonstrates

1. **Prompt engineering as a real artifact** — `prompts.py` is a first-class file in the codebase, iterated on using real output, not guessed at once and left alone.
2. **LLM calls treated like any other unreliable external service** — validated (Pydantic), retried on failure, cached (Redis), logged (Postgres) — same discipline as calling a third-party REST API.
3. **Provider-agnostic architecture** — swapping Anthropic → Gemini only ever touched `llm_client.py`. Every other layer (validation, retry, caching, storage, GraphQL, frontend) was provider-blind by design.
4. **Build order that de-risks cost** — the entire pipeline was proven correct on fake data before a single paid/real API call was made, so the only unknown left at the end was "is the generated content actually good," which is the one thing that can't be tested any other way.

---

## Natural Next Steps
- Enemy-type dropdown instead of free-text input (constrain to known types)
- A history view using the existing `generations` query
- Per-enemy-type prompt variants (regular vs. boss tone, more explicitly separated)
- Turn off `echo=True` SQL logging for a cleaner console
- Environment-based config (dev vs. prod settings)
- Basic test suite (pytest) covering validation, retry, and caching logic