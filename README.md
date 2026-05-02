# RAG Workspace (FastAPI + React)

Full-stack RAG application with:
- multi-format document ingestion
- chunking + vector indexing (Chroma)
- grounded chat with citations
- JWT auth + OTP verification
- RBAC and document-level permissions
- chat history and telemetry dashboards

## Tech Stack

- Backend: FastAPI, SQLAlchemy, MySQL, ChromaDB, FastEmbed, LangChain
- Frontend: React (Vite), React Router
- Auth: JWT access/refresh tokens + OTP verification
- Observability: request telemetry persisted in MySQL (`metrics_usage`)

## Repository Layout

- `backend/`: API, ingestion, retrieval, chat, auth, telemetry
- `frontend/`: React app for auth, documents, chat, admin, telemetry
- `pipeline.txt`: implementation roadmap/phases
- `architecture.txt`: detailed file-by-file architecture map

## Backend Setup

1. Create env file:
```bash
copy backend\.env.example backend\.env
```

2. Fill `backend/.env` with your local values (minimum):
- MySQL connection (`DATABASE_URL` or `MYSQL_*`)
- `JWT_SECRET_KEY`
- `GROQ_API_KEY`

3. Install and run backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

4. Open API docs:
- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Default local frontend URL:
- `http://127.0.0.1:5173` (or shown by Vite)

If needed, set `VITE_API_BASE_URL` to point frontend to backend.

## Core Runtime Flow

1. Signup -> verify OTP -> login
2. Upload document(s)
3. Backend loads/cleans/chunks and stores metadata/chunks in MySQL
4. Chunks are embedded and indexed in Chroma
5. Ask questions in chat (`/chat/query`)
6. Retrieval + reranking + prompting -> grounded answer with sources
7. Chat sessions/messages + telemetry are persisted

## Main API Groups

- Auth: `/auth/*`
- Documents: `/documents/*`
- Ingestion (stepwise/debug + batch): `/ingestion/*`
- Retrieval: `/retrieval/*`
- Chat: `/chat/*`
- Admin/RBAC: `/admin/*`
- Metrics/Telemetry: `/metrics`, `/telemetry`
- Quality eval (admin): `/test/evaluate`

## Health Checks

- `GET /health`
- `GET /health?include_vector_store=true`

## CLI Chat (Optional)

For quick local model interaction without frontend:
```bash
cd backend
python chat_cli.py
```

## Notes

- Uploaded files are stored under `backend/uploads/`.
- Vector data is stored under `backend/chroma_db/`.
- Stepwise ingestion endpoints are useful for debugging pipeline stages.
