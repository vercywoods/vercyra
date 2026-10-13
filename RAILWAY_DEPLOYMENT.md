# Railway deployment

This setup serves the React dashboard and authenticated Python API on one public origin. The frontend service proxies `/api/*` to a private backend service, so the browser uses same-origin requests and the API can keep its session cookie policy. The backend uses a Railway volume for SQLite state. The WSGI deployment does not provide packet capture; do not advertise that function as available on Railway.

## Before publishing

Review `git status` and stage only source and deployment files intended for GitHub. Do not publish `.env`, local databases, logs, quarantine contents, virtual environments, or generated build output. `.dockerignore` and `.gitignore` exclude common local artifacts, but review the staged file list before every commit and push.

## Create the Railway services

Connect the GitHub repository to a Railway project and create two services from the same repository:

### Backend service

- Root directory: repository root (`/`).
- Builder: Dockerfile.
- Dockerfile path: `/Dockerfile`.
- Add a Railway volume mounted at `/data`.
- Keep this service at one replica while it uses SQLite on a mounted volume.
- Set `VERCYRA_DATABASE_PATH=/data/vercyra_security.db`.
- Set `VERCYRA_PUBLIC_URL` to the frontend's public HTTPS origin. Use the Railway frontend domain during setup, then update it to `https://vercyra.co.ke` after adding the custom domain.
- Set `VERCYRA_SESSION_SECRET` to a unique random value and `VERCYRA_DASHBOARD_PASSWORD_HASH` to a locally generated PBKDF2 hash. Never put either value in Git or chat.
- Keep the backend's public domain disabled. The frontend connects over Railway private networking.
- Health check path: `/api/health`.

### Frontend service

- Root directory: `/frontend`.
- Builder: Dockerfile.
- Dockerfile path: `/Dockerfile` relative to the frontend root.
- Add the variable `API_UPSTREAM=http://${{Backend.RAILWAY_PRIVATE_DOMAIN}}:${{Backend.PORT}}`, changing `Backend` to the exact Railway backend service name if necessary.
- Add the custom domain `vercyra.co.ke` to this frontend service. Use the exact DNS records Railway displays; do not change the DNS configuration for `vercyra.com`.
- Health check path: `/api/health`.

The frontend image builds with `VITE_BASE_PATH=/`, serves the compiled SPA, and proxies API routes to the backend. The backend image runs the existing WSGI application with Gunicorn bound to Railway's `$PORT`. The database file is stored under the mounted `/data` volume so it survives normal redeployments. Deploy and health-check the backend first, then deploy the frontend so its proxy can reach the backend.

## Backend configuration

Set all secrets as Railway backend service variables. For initial launch, keep `PAYPAL_ENVIRONMENT=sandbox` and simulator flags disabled unless you explicitly need local-style simulator controls. Configure the PayPal sandbox credentials, plan IDs, webhook ID, and exact public webhook URL only in Railway variables after the service is deployed. Do not enable live payments until signed webhook delivery and subscription lifecycle updates have been verified end to end.

## Verify before announcing launch

1. Wait for both Railway deployments to report healthy.
2. Open the Railway frontend domain and check `/api/health` returns `{"status":"ok"}`.
3. Verify login, dashboard refresh, logout, and CSV export behavior.
4. Add `vercyra.co.ke` to the frontend service and publish only the DNS records Railway specifies.
5. Repeat the health and login checks on `https://vercyra.co.ke`.
6. Confirm `vercyra.com` still resolves to its existing host.

Railway domains, DNS records, service variables, and health-check settings must be completed in the Railway and domain-provider accounts. This file does not publish code or change DNS.
