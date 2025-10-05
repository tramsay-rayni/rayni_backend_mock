# Rayni — Backend (Django) README

This service powers Rayni’s instruments, knowledge sources, and LLM chat endpoints. It’s a Django app (DRF for JSON, plain Django for SSE) typically run with Postgres, Redis, and MinIO via `docker compose`.

---

## Table of Contents
- [Overview & Purpose](#overview--purpose)
- [Architecture at a Glance](#architecture-at-a-glance)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [OpenAI Wiring — Sanity Checks](#openai-wiring--sanity-checks)
- [Everyday Dev Commands](#everyday-dev-commands)
- [Core API (Minimal Contract)](#core-api-minimal-contract)
  - [Chat](#chat)
  - [Instruments & Sources](#instruments--sources)
  - [Access Control](#access-control)
  - [Uploads](#uploads)
  - [Connectors](#connectors)
  - [Viewer Meta](#viewer-meta)
  - [Feedback & FAQ](#feedback--faq)
- [Streaming (SSE) Notes](#streaming-sse-notes)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Security & Secrets](#security--secrets)
- [Deployment Notes](#deployment-notes)

---

## Overview & Purpose
Rayni turns unstructured product/instrument knowledge (PDFs, videos, images, URLs) into a grounded chat experience. The backend exposes:

- **CRUD APIs** for instruments, sources, and access control.
- **Chat endpoints** — non‑stream `POST /api/chat/ask` and streaming `GET /stream/chat` using Server‑Sent Events.
- **Citations ("Proofs")** linking answers to source fragments.
- **Viewer meta** to render highlights/regions in the frontend Proof Viewer.

---

## Architecture at a Glance
```
Next.js FE  ───────►  Django API
                  │     ├─ DRF JSON endpoints
                  │     └─ SSE stream (plain Django view)
                  │
Postgres ◄────────┤  (models: Instrument, Source, Chat*, Citation, …)
Redis    ◄────────┤  (optional for background work)
MinIO    ◄────────┤  (object storage for uploads)

OpenAI   ◄────────┤  (Chat Completions for answers / token stream)
```

**Key flow:**
1) FE calls `/stream/chat?instrument_id=…&q=…` to open an `EventSource`.
2) BE creates `ChatSession` + user `ChatTurn`, emits `start` with `turn_id`.
3) BE streams tokens (`token` events) as they arrive from OpenAI.
4) On completion, BE persists assistant `ChatTurn`, stubs citations, emits `done` with `turn_id` + `citations`.

---

## Quick Start

1. **Create `.env`** (repo root):
```ini
SECRET_KEY=dev-secret
DEBUG=1
DATABASE_URL=postgres://rayni:rayni@db:5432/rayni
OPENAI_API_KEY=sk-...your-key...
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

2. **Boot services**
```bash
docker compose up -d --build
# Watch API
docker compose logs -f api
```
You should see: *“System check identified no issues”* and server on `http://0.0.0.0:8000/`.

3. **Smoke tests**
```bash
# Instruments
curl -s http://localhost:8000/api/instruments/ | jq .

# Non-stream chat
INSTR=$(curl -s http://localhost:8000/api/instruments/ | jq -r '.[0].id')
jq -n --arg instrument_id "$INSTR" --arg q "Hello from README" \
  '{instrument_id:$instrument_id, question:$q}' |
curl -s -X POST http://localhost:8000/api/chat/ask \
  -H 'Content-Type: application/json' --data-binary @- | jq .

# Streaming chat (SSE)
curl -N "http://localhost:8000/stream/chat?instrument_id=$INSTR&q=stream this"
```

---

## Authentication & Testing

### Demo Users

The backend includes two demo accounts for testing:

**Admin User:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@rayni.com"}' \
  -c cookies.txt
```
- **Email**: `admin@rayni.com`
- **Role**: Instrument Manager
- **Access**: All instruments automatically
- **Can**: Approve/deny access requests, manage users

**Regular User:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@rayni.com"}' \
  -c cookies.txt
```
- **Email**: `user@rayni.com`
- **Role**: Trained User
- **Access**: Only granted instruments
- **Can**: Request access, use approved instruments

**Check Auth Status:**
```bash
curl http://localhost:8000/api/auth/me -b cookies.txt
```

**Logout:**
```bash
curl -X POST http://localhost:8000/api/auth/logout -b cookies.txt
```

See `TESTING-AUTH.md` in the repo root for complete testing scenarios.

---

## Environment Variables

| Name | Required | Default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | yes | — | Django secret (dev OK) |
| `DEBUG` | no | `1` | Enables dev mode |
| `DATABASE_URL` | yes | `postgres://rayni:rayni@db:5432/rayni` | Postgres DSN |
| `OPENAI_API_KEY` | **yes** | — | Enables real LLM output |
| `OPENAI_MODEL` | no | `gpt-4o-mini` | Model for ask/stream |
| `OPENAI_BASE_URL` | no | `https://api.openai.com/v1` | For proxy/Azure routing |

> The backend reads `OPENAI_*` first from the environment, then from Django settings (if present).

---

## OpenAI Wiring — Sanity Checks
From **inside** the container:
```bash
docker compose exec -T api python - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','rayni.settings'); django.setup()
from django.conf import settings
print('OPENAI_API_KEY?', bool(getattr(settings,'OPENAI_API_KEY', None)))
print('OPENAI_MODEL =', os.environ.get('OPENAI_MODEL') or getattr(settings,'OPENAI_MODEL', None) or 'gpt-4o-mini')
print('OPENAI_BASE_URL =', os.environ.get('OPENAI_BASE_URL') or getattr(settings,'OPENAI_BASE_URL', None) or 'https://api.openai.com/v1')
PY
```
Simple live call using Python stdlib:
```bash
docker compose exec -T api python - <<'PY'
import os, json, urllib.request
url=(os.environ.get('OPENAI_BASE_URL','https://api.openai.com/v1').rstrip('/'))+'/chat/completions'
payload={'model': os.environ.get('OPENAI_MODEL','gpt-4o-mini'), 'messages':[{'role':'user','content':'Say OK'}]}
req=urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Authorization':'Bearer '+os.environ.get('OPENAI_API_KEY',''),'Content-Type':'application/json'})
print(json.loads(urllib.request.urlopen(req, timeout=30).read().decode())['choices'][0]['message']['content'])
PY
```

---

## Everyday Dev Commands
```bash
# Show services
docker compose ps
# Tail logs
docker compose logs -f api
# Rebuild & recreate
docker compose up -d --build --force-recreate
# Django shell with settings
docker compose exec -T api python - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','rayni.settings'); django.setup()
import core.views as v
print('views file:', v.__file__)
PY
```

---

## Core API (Minimal Contract)

### Chat
- `POST /api/chat/ask`
  - **Body** `{ "instrument_id": "uuid", "question": "string" }`  
    (alias `instrument` is accepted server‑side)
  - **200** `{ "turn_id": "uuid", "answer": "string", "citations": [{"source_id":"uuid","fragment_id":"uuid","score":0.8}] }`

- `GET /stream/chat?instrument_id=<uuid>&q=<string>`
  **SSE**: events `start` → `{turn_id}`; `token` → `{t}`; `done` → `{turn_id, citations}`
  **Note**: Endpoint is outside `/api/` path to avoid DRF content negotiation (406 errors)

- `POST /api/chat/regen/<turn_id>` → `{ turn_id, answer }`

- `POST /api/chat/turn/<turn_id>/feedback` → `{ status: "ok" }`

- `GET /api/citations/turn/<turn_id>` → `{ items: [...] }`

### Instruments & Sources
- `GET /api/instruments/`
- `GET /api/sources/?instrument=<uuid>&q=&type=&status=&page=&page_size=`
- `GET /api/sourceversions/` (if routed)

### Access Control
(Exact routing may vary by `urls.py`; function names shown.)
- `POST` **request_access**: `/api/instruments/<instrument_id>/access/request`
- `GET` **access_requests**: `/api/instruments/<instrument_id>/access/requests`
- `POST` **access_request_action**: `/api/instruments/<instrument_id>/access/requests/<req_id>/<approve|deny>`
- `GET` **access_grants**: `/api/instruments/<instrument_id>/access/grants`
- `POST` **access_grant_create**: `/api/instruments/<instrument_id>/access/grants`
- `PATCH` **access_grant_update**: `/api/instruments/<instrument_id>/access/grants/<grant_id>`

### Uploads
- `POST /api/uploads/initiate` → `{ upload_id, signed_url, headers }`
- `PATCH /api/uploads/<upload_id>/complete` → `{ source_id, status }`

### Connectors
- `GET /api/connectors`
- `POST /api/connectors`
- `POST /api/connectors/<conn_id>/sync`

### Viewer Meta
- `GET /api/viewer/pdf/<source_id>` → `{ type:'pdf', page, bbox, filename, version, checksum }`
- `GET /api/viewer/video/<source_id>` → `{ type:'video', t_start, t_end, transcript[] }`
- `GET /api/viewer/image/<source_id>` → `{ type:'image', region, alt_text }`

### Feedback & FAQ
- `POST /api/feedback/` → creates record
- `POST /api/feedback/<id>/respond` → admin response
- `GET /api/faq/` → basic FAQ items  
  *(FE may also call `/api/support/faq` — project includes a fallback in the FE library.)*

---

## Streaming (SSE) Notes
- The streaming route returns a **`StreamingHttpResponse`** with `content_type="text/event-stream"` and should **not** be wrapped by DRF renderers. Otherwise content negotiation can trigger `406 Not Acceptable`.
- Dev CORS is allowed via `Access-Control-Allow-Origin: *` so `http://localhost:3000` can consume the stream from `http://localhost:8000`.
- FE pattern: push a **user message** then an **assistant placeholder**; update the **last** message on each `token` event.

---

## Troubleshooting
**SSE 406**
- Ensure `chat_stream` is a plain Django view (`@require_GET`, `@csrf_exempt` are fine) returning `StreamingHttpResponse`.
- Do **not** force `Accept:` in curl; use `curl -N URL`.

**"Placeholder answer…"**
- Means OpenAI call didn’t run. Verify env vars inside the container:
  - `docker compose exec -T api env | grep OPENAI_`
  - Test call to `https://api.openai.com/v1/chat/completions`.

**Empty assistant bubble while streaming**
- FE must mutate the last assistant message on each `token` event. A common bug is appending a new message per token (results in blank bubble).

**FAQ 404**
- Ensure FE calls `/api/faq/` (backend ships this route). The FE has a fallback to defaults if it gets 404.

---

## Project Structure
```
rayni-backend/
  core/
    models.py         # Instrument, Source, SourceVersion, ChatSession, ChatTurn, Citation, Access*, Feedback, Connector
    serializers.py
    views.py          # All endpoints incl. chat_ask, chat_stream (SSE), sources, access control, uploads, connectors, viewer meta
  rayni/
    settings.py       # Reads env; DEBUG, DB, OPENAI_*
  docker-compose.yml  # api, worker, db, redis, minio
  entrypoint.sh
```

---

## Security & Secrets
- Keep `OPENAI_API_KEY` and DB creds in `.env` (not committed).
- For production, use a secrets manager and disable `DEBUG`.
- Add auth/permissions on endpoints before exposing beyond dev.

---

## Deployment Notes
- Containerized via `docker compose`; production can use the same images.
- Place a reverse proxy (nginx) in front; ensure SSE headers (`Cache-Control: no-cache`, `X-Accel-Buffering: no`) pass through.
- Configure CORS appropriately (don’t use `*` in production).

---

### Extras
If helpful, we can also provide:
- **Operator Quickstart (PDF)** — 1‑page startup & smoke tests.
- **Postman collection** — covering `chat/ask`, `chat/stream` (note: Postman UI doesn’t render SSE), and `citations/turn/:id`.

> Ask and we’ll export these artifacts, or you can adapt from the sections above.

