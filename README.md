# Vercyra API

This repository now includes an Express.js backend API for recording and retrieving security assessment metadata and vulnerability findings. It is designed to run alongside the existing Python monitoring tools and frontend, without altering their behavior.

## What remains preserved

- Existing Python monitoring scripts remain in place.
- The frontend app remains in `frontend/` and is not replaced.
- The new API is additive and intended for structured, read-only security assessment records.

## Local setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

3. Start PostgreSQL locally and create a database named `vercyra` or update `DATABASE_URL` to match your local instance.

4. Start the API:
   ```bash
   npm run dev
   ```

5. Verify the service:
   ```bash
   curl http://127.0.0.1:3001/health
   curl http://127.0.0.1:3001/health/db
   ```

## API endpoints

- `GET /health` — checks whether the API is running.
- `GET /health/db` — checks PostgreSQL connectivity.
- `GET /api/assessments` — lists security assessments.
- `POST /api/assessments` — creates a new assessment with optional findings.
- `GET /api/assessments/:id` — fetches an assessment and its findings.

## Example request body

```json
{
  "title": "Quarterly review",
  "description": "Read-only security assessment record for a customer environment.",
  "assessment_type": "web_application",
  "status": "completed",
  "owner": "security-team",
  "findings": [
    {
      "title": "Outdated framework version",
      "severity": "medium",
      "description": "The application is using an older framework version.",
      "location": "package.json",
      "remediation": "Upgrade the framework to the current supported release.",
      "evidence": "Dependency audit output"
    }
  ]
}
```

## Security notes

- The API accepts only read-only, authorized assessment records.
- It does not execute shell commands or perform active system scans.
- Secrets, DB credentials, and stack traces are never returned to API clients.

## Railway deployment

1. Create a new Railway project and add a PostgreSQL service.
2. Railway provides `DATABASE_URL` automatically for the database service.
3. In the Railway project settings, set these variables:
   - `PORT=3001` (optional if Railway injects it automatically)
   - `NODE_ENV=production`
   - `CORS_ORIGINS=https://your-frontend.example.com,http://localhost:3000`
4. Deploy the repo from GitHub.
5. Set the app start command to:
   ```bash
   npm start
   ```
6. Confirm the service starts correctly with:
   ```bash
   curl https://your-app.up.railway.app/health
   ```

Important: do not create billable resources or modify a production deployment until you confirm the changes and the app is ready for deployment.

## Testing

```bash
npm test
```

This project keeps the existing Python monitoring assets intact and uses the new Node service as an API layer for workflow-friendly assessment management.
