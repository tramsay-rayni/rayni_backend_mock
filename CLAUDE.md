# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Rayni is a full-stack application consisting of two separate codebases:

1. **Backend** (`rayni-backend-complete/`): Django REST API with PostgreSQL, Redis, MinIO
2. **Frontend** (`rayni-frontend-complete/`): Next.js application with TypeScript

The application provides a **scientific laboratory instrument** knowledge management system with chat capabilities, document storage, access control, and support features. Users can search for information about lab equipment (flow cytometers, mass spectrometers, microscopes, etc.), access equipment documentation, and chat with an AI assistant to get answers about specific instruments and their operation.

## Backend (Django)

### Authentication

**Demo Users** for testing role-based access:
- `admin@rayni.com` - Admin with full access to all instruments
- `user@rayni.com` - Regular user with limited access (must request access)

**Endpoints**:
- `POST /api/auth/login` - Login with email (demo: no password required)
- `POST /api/auth/logout` - Clear session
- `GET /api/auth/me` - Get current user info with allowed instrument IDs

See `TESTING-AUTH.md` for complete testing guide.

### Development Commands

```bash
# Initial setup
cd rayni-backend-complete
cp .env.example .env
docker compose build
docker compose up -d

# Database migrations
docker compose exec api python manage.py migrate
docker compose exec api python manage.py createsuperuser

# Seed demo data (recommended)
docker compose exec api python manage.py seed_instruments --clear
docker compose exec api python manage.py seed_folders
docker compose exec api python manage.py seed_sources

# View API docs
open http://localhost:8000/api/docs
```

**Seed Commands**:
- `seed_instruments` - Creates 10 realistic lab instruments (flow cytometers, mass specs, microscopes, etc.)
- `seed_folders` - Creates default folder structure (Manuals, Protocols, SOPs, Troubleshooting, Training, Maintenance) for all instruments
- `seed_sources` - Adds 5-10 sample documents per instrument with realistic titles, categories, and metadata


### Architecture

**Core Models** (`core/models.py`):
- **Instrument**: Laboratory instruments with models_arr (equipment variants), vendor info, visibility settings
- **Folder**: Hierarchical organization with self-referential parent for nested structures (Manuals, Protocols, SOPs, etc.)
- **Source**: Documents with:
  - `category` - Classification: manual, protocol, sop, troubleshooting, training, maintenance
  - `description` - Optional text for AI context and retrieval
  - `version` - Document revision tracking (e.g., "v8.2", "Rev 2024")
  - `model_tags` - ArrayField linking to specific equipment variants
  - `folder` - FK to Folder for organization
  - `archived` - Boolean for soft delete (preserves citations)
  - `archived_at` - Timestamp when archived
- **Fragment types**: `PDFFragment`, `VideoFragment`, `ImageFragment` for document highlights
- **Access system**: `AccessGrant` and `AccessRequest` for role-based permissions (instrument_manager, trained_user)
- **Chat system**: `ChatSession`, `ChatTurn`, `Citation`, `Attachment` for conversational AI
- **Support**: `Feedback` model for user submissions with admin responses
- **Connectors**: Scaffold for external integrations (Google Drive, SharePoint)

**API Structure** (`core/views.py` + `rayni/urls.py`):
- RESTful ViewSets for CRUD operations on instruments, sources, folders
- Chat endpoints: `/api/chat/ask` (POST), `/stream/chat` (GET with SSE - outside `/api/` to avoid DRF 406 errors), `/api/chat/turns/<id>/regenerate`, `/api/chat/turns/<id>/feedback`, `/api/chat/turns/<id>/citations`
- Access control: `/api/instruments/<id>/request-access`, `/api/instruments/<id>/access/grants`
- Folder management: `/api/folders/?instrument=<id>` (GET), `/api/folders/` (POST), `/api/folders/<id>/` (DELETE)
- Archive: `/api/sources/<id>/archive` (PATCH) - Admin-only soft delete
- Support: `/api/support/faq`, `/api/support/feedback`
- Viewer metadata: `/api/viewer/pdf/<id>`, `/api/viewer/video/<id>`, `/api/viewer/image/<id>`
- Upload flow: `/api/uploads/initiate`, `/api/uploads/<id>/complete` (now accepts category, description, version, model_tags, folder_id)

**Chat API Contracts** (Authoritative):

`POST /api/chat/ask` (Non-streaming):
- Request: `{"instrument_id": "uuid", "question": "string"}`
- Response 200: `{"turn_id": "uuid", "answer": "string", "citations": [{"source_id": "uuid", "fragment_id": "uuid", "score": 0.8}]}`
- Errors: 400 if `instrument_id` missing; 200 with `"[LLM error: ...]"` if OpenAI fails

`GET /stream/chat?instrument_id=<uuid>&q=<string>` (SSE streaming):
- Response: `Content-Type: text/event-stream`
- **Critical**: Endpoint is at `/stream/chat` (NOT `/api/chat/stream`) to avoid DRF content negotiation
- SSE Event Sequence:
  1. `start` → `{"turn_id":"<user_turn_uuid>"}` (user turn ID)
  2. `token` (repeated) → `{"t":"<chunk>"}` (incremental text)
  3. `done` → `{"turn_id":"<assistant_turn_uuid>","citations":[...]}` (assistant turn ID)
- **Critical**: `start.turn_id` is the user turn, `done.turn_id` is the assistant turn
- **Implementation Note**: Uses plain Django `StreamingHttpResponse` registered in `urls.py` before `/api/` routes
- Query params required because EventSource cannot send custom headers

**Stack**:
- PostgreSQL for database with ArrayField support
- Redis for Celery task queue
- MinIO for object storage (S3-compatible)
- Celery worker service for background processing
- OpenAI integration for chat functionality

**Attachment Ingest Workflow**:

The `Attachment` model has an `ingest` boolean field that controls document processing:

- `ingest=False` (default): Attachment is "turn-scoped" - used only for immediate chat context, not added to Knowledge Store
- `ingest=True`: Triggers background processing pipeline via Celery:
  1. **Parse**: Extract text/metadata (e.g., pdfminer.six for PDFs)
  2. **Chunk**: Split into semantically meaningful segments
  3. **Embed**: Generate vector embeddings using sentence-transformer
  4. **Index**: Store chunks + embeddings in vector database (PGvector/Pinecone)
  5. **Cite**: Vector search retrieves relevant chunks; citations reference source document + location

This creates a `Source` record in the instrument's Knowledge Store for long-term retrieval.

**Services** (docker-compose.yml):
- `db`: PostgreSQL on port 5432
- `redis`: Redis on port 6379
- `minio`: MinIO on ports 9000 (API) and 9001 (console)
- `api`: Django API on port 8000
- `worker`: Celery worker

## Frontend (Next.js)

### Development Commands

```bash
cd rayni-frontend-complete

# Install dependencies
pnpm install

# Run development server (port 3001)
pnpm run dev

# Build for production
pnpm run build

# Start production server
pnpm start
```

### Architecture

**App Structure** (Next.js App Router):
- `/app/page.tsx`: Home page with instrument list
- `/app/instruments/[id]/chat/page.tsx`: Chat interface with SSE streaming
- `/app/instruments/[id]/store/page.tsx`: Knowledge store with:
  - **Enhanced table**: Category badges, folder paths, model tag chips, version, upload date, archive action
  - **5 filters**: Search, category, folder, type, status
  - **Folder modal** (admin): Create/delete nested folders
- `/app/instruments/[id]/store/upload/page.tsx`: **4-step wizard** with:
  - Step 1: File selection (drag-and-drop)
  - Step 2: Category (auto-detected from filename)
  - Step 3: Metadata (folder auto-selected, model tags auto-checked)
  - Step 4: Preview & submit
- `/app/instruments/[id]/access/page.tsx`: Access request management
- `/app/settings/users/page.tsx`: User management and roster
- `/app/support/page.tsx`: FAQ and feedback submission
- `/app/viewer/page.tsx`: Universal viewer for PDF/video/image with highlighting

**API Client** (`lib/api.ts`):
- All backend communication centralized in typed functions
- EventSource for SSE streaming chat
- Environment variable: `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000/api`)

**Frontend SSE Pattern** (avoiding empty bubbles):
1. Push user message to state immediately
2. Push assistant placeholder: `{role: "assistant", text: ""}`
3. On each `token` event: Update text of last message in-place
4. On `done` event: Attach citations to same message
- This ensures the UI never shows an empty assistant bubble

**Technologies**:
- Next.js 14 with App Router and TypeScript
- TailwindCSS for styling
- pdfjs-dist for PDF rendering
- MSW (Mock Service Worker) for API mocking during development

## Cross-Repository Context

- Frontend expects backend at `http://localhost:8000/api` (configurable via `NEXT_PUBLIC_API_BASE_URL`)
- Backend runs on port 8000, frontend on port 3001
- Chat uses two modes: single request (`/chat/ask`) and streaming (`/chat/stream` with SSE)
- Fragment IDs reference `PDFFragment`, `VideoFragment`, or `ImageFragment` for citation highlighting
- Access control is enforced by checking `AccessGrant` records with roles
- All IDs are UUID v4

## Known Gotchas

- **SSE 406 Not Acceptable**: Fixed by moving stream endpoint to `/stream/chat` (outside `/api/` path) to avoid DRF content negotiation. The route must be registered in `urls.py` BEFORE the `path("api/", include(router.urls))` line.
- **CORS with Credentials**: Backend uses `CORS_ALLOWED_ORIGINS` (NOT `CORS_ALLOW_ALL_ORIGINS=True`) with `CORS_ALLOW_CREDENTIALS=True` to support session-based auth. Frontend must use `credentials: 'include'` in all auth-related fetch calls.
- **Parameter Naming**: Frontend must send `instrument_id` (not `instrument`) to `/api/chat/ask`
- **Two Turn IDs**: The `start` event returns the user turn ID, the `done` event returns the assistant turn ID - don't confuse them
- **EventSource Limitations**: Cannot send custom headers, which is why `instrument_id` and `q` are query parameters in `/stream/chat`
- **OpenAI Client**: Use custom httpx.Client() to avoid "unexpected keyword argument 'proxies'" errors with OpenAI SDK v1.42+
- **Session Auth**: Login stores user in Django session. All authenticated requests must include `credentials: 'include'` to send session cookies.

## Common Workflows

**Adding a new API endpoint**:
1. Create/update model in `core/models.py`
2. Add serializer in `core/serializers.py`
3. Implement view function in `core/views.py`
4. Register route in `rayni/urls.py`
5. Run migration: `docker compose exec api python manage.py makemigrations && docker compose exec api python manage.py migrate`

**Adding a new frontend page**:
1. Create page component in `app/[route]/page.tsx`
2. Add API call to `lib/api.ts` if needed
3. Use existing types from `lib/api.ts` for type safety

**Testing chat streaming**:
1. Backend must have `OPENAI_API_KEY` in `.env`
2. Seed at least one Instrument via Django admin or management command
3. Test with curl: `curl -N "http://localhost:8000/stream/chat?instrument_id=<uuid>&q=hello"`
4. Expected SSE events:
   - `event: start\ndata: {"turn_id":"<user_uuid>"}`
   - Multiple `event: token\ndata: {"t":"chunk"}`
   - `event: done\ndata: {"turn_id":"<assistant_uuid>","citations":[...]}`
5. Frontend uses EventSource to consume these events and update UI in real-time
6. **Important**: The endpoint is `/stream/chat` not `/api/chat/stream` - this prevents DRF 406 errors

## Gotchas & Troubleshooting

**URL Pattern Ordering in `rayni/urls.py`**:
- Django processes URL patterns in order from top to bottom
- The DRF router `path("api/", include(router.urls))` will capture ALL paths starting with `api/`
- Therefore, specific routes like `api/auth/login`, `api/chat/ask`, etc. MUST be defined BEFORE the router include
- Current correct order:
  1. `/stream/chat` (before API to avoid DRF content negotiation)
  2. Specific API routes (`api/auth/*`, `api/chat/*`, etc.)
  3. Router include `path("api/", include(router.urls))`
- **Symptom if wrong**: 404 errors on specific routes even though they're defined in urls.py

**CORS with Credentials**:
- Session-based auth requires `credentials: "include"` in all frontend fetch calls
- Backend must set `CORS_ALLOWED_ORIGINS` to specific origins (not `"*"`) and `CORS_ALLOW_CREDENTIALS=True`
- Do NOT manually set `Access-Control-Allow-Origin` headers in views - let the corsheaders middleware handle it
- **Symptom if wrong**: CORS errors about wildcard with credentials mode

**Login Endpoint 404 After Rebuild**:
- If you rebuild the Docker container and login still returns 404, check that urls.py inside the container matches your local file
- Run: `docker compose exec api cat rayni/urls.py | grep -A 5 "# auth"`
- If different, rebuild with: `docker compose up -d --build --force-recreate api`

**Session Not Persisting**:
- Ensure all auth API calls include `credentials: "include"`
- Check that the backend sets session cookies with proper flags (HttpOnly, SameSite)
- Verify CORS origins match the frontend origin exactly
