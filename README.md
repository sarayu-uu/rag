# RAG Model Project

Backend and frontend workspace for a phased RAG system. Phase 1 establishes the FastAPI backend foundation, environment-based configuration, MySQL connectivity, and the core SQLAlchemy schema that later ingestion, retrieval, auth, and telemetry work will build on.

## Backend setup

1. Create `backend/.env` from `backend/.env.example`.
2. Set your MySQL connection values in `backend/.env`.
3. Install backend dependencies and start the API.

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On startup the FastAPI app now attempts to:

- connect to the configured MySQL database
- create the Phase 1 tables if they do not exist
- seed the baseline RBAC roles

Use `GET /health` to confirm whether the API can currently reach MySQL.

## Command-line Groq bot

Add your Groq key to `backend/.env`:

```bash
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

Then run:

```bash
cd backend
python chat_cli.py
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```
