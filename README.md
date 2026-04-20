# RAG Model Project

## File purpose

- Documents how to run the backend and frontend for this upload + ingestion baseline.

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Command-line Groq Bot

Add this to `backend/.env`:

```bash
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

Run the bot from your terminal:

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
