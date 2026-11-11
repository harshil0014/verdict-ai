# VERDICT

VERDICT is a private workspace for investigating payment disputes. It preserves original evidence, compares competing accounts and identifies what additional evidence could clarify a case. [Open the live demo](https://verdict-ai-harshil0014.onrender.com/)

## Features

- **Case workspaces** with registration, recovery keys, source citations, evidence graphs and an audit timeline.
- **Document reading** for images, scanned and searchable PDFs, text and JSON. Tesseract OCR preserves uncertainty alongside the original file.
- **Automatic investigation and reassessment** using Gemini 3.1 Flash-Lite, with Gemini 3.5 Flash-Lite as the backup. Both stages validate structured responses and tie claims to preserved passages.
- **Witness requests** with scoped, expiring response links. New evidence and replies trigger reassessment.
- **Public evidence research** that preserves accessible source snapshots and retrieval provenance.
- **Delivery location comparison** using source-backed address descriptions, optional Photon lookups and Leaflet maps with OpenStreetMap tiles. [Location controls](docs/DELIVERY_LOCATION.md)
- **PayPal Sandbox import** for an authorized test merchant, with dispute, capture and order records linked to the private case. Sandbox financial actions require a separate, bounded merchant policy. [Integration guide](docs/PAYPAL.md)

## Architecture

React, TypeScript and Vite provide the frontend. FastAPI serves the API and built frontend from one origin. Supabase PostgreSQL stores accounts, files, investigations and durable jobs, with server-side ownership checks and row-level security. A Docker image runs the application on Render. [Architecture](docs/ARCHITECTURE.md) · [Security](docs/SECURITY.md)

## Local setup

Install Python 3.13, Node.js 22, and Tesseract with English language data. Use a dedicated Supabase project and apply the timestamped SQL migrations in filename order before starting the app. The optional legacy snapshot migration is documented in the deployment guide. [Migrations and deployment](docs/DEPLOYMENT.md)

```powershell
git clone https://github.com/harshil0014/verdict-ai.git
cd verdict-ai
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
Copy-Item backend/.env.example backend/.env
```

Run the copy command on a fresh checkout. Fill in the server credentials in `backend/.env` before starting the account app. Keep this file private.

| Setting | Purpose |
| --- | --- |
| `SUPABASE_URL`, `SUPABASE_SECRET_KEY` | Dedicated Supabase project and server-only key |
| `VERDICT_AUTH_PEPPER` | Stable random secret of at least 24 characters |
| `GEMINI_API_KEY` | Server-only Gemini key |
| `GEMINI_MODEL` | Primary model, defaults to `gemini-3.1-flash-lite` |
| `VERDICT_PUBLIC_HOST`, `VERDICT_SECURE_COOKIES` | Allowed host and HTTPS cookie settings |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `VERDICT_PAYPAL_DEMO_OWNER_ID`, `VERDICT_PAYPAL_DEMO_MERCHANT_ID` | Optional authorized Sandbox connection |
| `TESSERACT_CMD` | Optional path to Tesseract when it is outside PATH |

```powershell
cd backend
.venv/Scripts/python.exe -m uvicorn saas_app:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open `http://127.0.0.1:8000/`, register, and save the recovery key. On macOS or Linux, use `backend/.venv/bin/python` from the repository root, `.venv/bin/python` inside `backend/`, and `npm` in place of `npm.cmd`.

## Testing

Run from the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pytest
cd frontend
npm.cmd test
npm.cmd run build
```

GitHub Actions also builds and checks the Docker container. The live acceptance tools require an isolated test environment and may create test records. [Testing guide](docs/SAAS_ACCEPTANCE.md) · [Evaluation methodology and results](docs/EVALUATION.md)

## Deployment

Build the included Dockerfile and set `VERDICT_APP_MODULE=saas_app:app` for the account application. Configure the server environment and use `/api/health` to verify database connectivity. [Deployment and recovery](docs/DEPLOYMENT.md)

## License

VERDICT is released under the [MIT License](LICENSE). [Third-party notices](THIRD_PARTY_NOTICES.md) cover bundled dependencies, map attribution and provider terms.
