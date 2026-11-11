# Deployment and recovery

The Dockerfile builds the React assets with Node.js 22 and serves them through FastAPI on Python 3.13. The container installs Tesseract and runs as a non-root user. The account app uses Supabase PostgreSQL for durable state.

1. Apply the timestamped files in [Supabase migrations](../supabase/migrations) in filename order to your intended project. Include the first snapshot migration if using the optional legacy mirror. Keep all applied migration files when upgrading an existing project.
2. Set `VERDICT_APP_MODULE=saas_app:app`, `VERDICT_SECURE_COOKIES=true`, and `VERDICT_PUBLIC_HOST` to the exact public hostname. Configure a stable `VERDICT_AUTH_PEPPER`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, and `GEMINI_API_KEY` as server secrets. Use the [environment template](../backend/.env.example) for additional options.
3. Build the Dockerfile or configure the existing Render service with the repository's [Blueprint](../render.yaml). The container listens on Render's `PORT` or port 8000 locally.
4. Check `GET /api/health` for database readiness, verify the homepage and assets, and confirm unauthenticated case requests return 401. Run provider and persistence checks on a dedicated test environment when validating integration changes.

The durable workflow runner shares the web process. `VERDICT_AUTOMATIC_WORKER=false` pauses the runner on that instance. Free hosting can sleep and delay processing until an instance wakes.

For rollback, redeploy the previous working application commit with its corresponding environment. Keep the cloud schema and stored data in place. Maintain separate database backups and verify their restore procedure. [Render deployment lifecycle](https://render.com/docs/deploys)