# RAG Evaluation Test Folder

This folder contains quick helpers to test retrieval relevance and RAGAS scoring through the new Swagger endpoint:

- `POST /test/evaluate`

## Endpoint purpose

The endpoint runs one full RAG query and returns:

- retrieval scores from your pipeline (`semantic_distance`, `rerank_score`, match counts, latency)
- RAGAS scores (`faithfulness`, `answer_relevancy`, `context_precision`, and `context_recall` when `ground_truth` is provided)
- a `metric_guide` object explaining what each score means

## Run setup

From `backend/`:

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open Swagger:

- `http://127.0.0.1:8000/docs`
- Find tag: `test`
- Use endpoint: `POST /test/evaluate`

## Example request body

```json
{
  "question": "What is the retention policy?",
  "ground_truth": "Logs are retained for 90 days.",
  "limit": 5
}
```

## Notes

- Authentication is required (same bearer token you use for other protected endpoints).
- If RAGAS dependencies or evaluator config are missing, the endpoint still returns retrieval scoring and sets `ragas.status` to `failed` with a helpful message.
