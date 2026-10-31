# Codriver

Codriver is a small AI assistant: a static page in `frontend/` and a FastAPI service in `backend/` that forwards chat messages to a Hugging Face model.

The page can answer a few things on its own (time, jokes, riddles, quotes, a number game, weather, and news). Anything else is sent to `POST /api/chat`.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port "${PORT:-8000}"
```

On Render, bind to `0.0.0.0` and the platform `PORT`. The filesystem is ephemeral, so the Hugging Face token has to come from the service environment, not a file written at runtime.

## Environment variables

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `HF_TOKEN` | yes | | Hugging Face token sent as the bearer token for chat completions. If it is unset, `/api/chat` returns HTTP 503. |
| `CORS_ORIGINS` | no | `https://hellenicdev.eu` | Comma-separated browser origins allowed to call the API. |
| `RATE_LIMIT` | no | `10/minute` | [slowapi](https://github.com/laurentS/slowapi) limit for `POST /api/chat`. |

`/api/chat` waits at most 30 seconds for the model. A non-200 response from Hugging Face becomes HTTP 502 with a short JSON `detail`, instead of an unhandled 500. A timeout becomes HTTP 504. Over the limit, the API returns HTTP 429.

Rate limits are counted in memory, per process. The key is the `CF-Connecting-IP` header when Cloudflare sends it (Render does), otherwise the socket address. A client-supplied `X-Forwarded-For` is not used as the key.

## Frontend

Open `frontend/index.html` for the page shell. Assistant behaviour lives in `frontend/script.js`. The public page is [https://hellenicdev.eu/codriver/frontend/](https://hellenicdev.eu/codriver/frontend/).

## License

BSD 3-Clause. See [LICENSE](LICENSE).
