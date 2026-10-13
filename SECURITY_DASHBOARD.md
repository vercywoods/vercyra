# Local Security Dashboard

## Cloudflare Pages frontend

Cloudflare Pages can host the React dashboard. It does not host the Python API, SQLite database, or continuous file watcher; those need a separate backend host.

1. Push this repository to GitHub and create a Pages project using **Connect to Git**.
2. Select the repository's `frontend` directory as the root directory.
3. Set the framework preset to **Vite**, build command to `npm run build`, and build output directory to `dist`.
4. Set the Pages build variable `VITE_BASE_PATH` to `/`. Leave `VITE_API_BASE_URL` unset so the app requests `/api/...` from its own Pages domain.
5. In Pages settings, add the runtime variable `VERCYRA_API_ORIGIN` as the HTTPS origin of the deployed backend, without a path. For example, use `https://vercyra.com` if its `/api/` routes already reach the Python app.
6. Set the backend's `VERCYRA_PUBLIC_URL` to the Pages site's exact origin (for example, `https://vercyra.pages.dev`) so dashboard login accepts requests from that site. After adding a custom domain, update it to that exact HTTPS origin and restart the backend.
7. Deploy, then verify the Pages dashboard loads and `https://<your-pages-domain>/api/health` returns `{"status":"ok"}`. Test dashboard login and PayPal sandbox before considering the deployment ready.

The Pages Function under `frontend/functions/api/` forwards `/api/*` requests to `VERCYRA_API_ORIGIN`, keeping API calls and session cookies same-origin in the browser. Never put backend credentials in `VITE_*` variables or frontend code. Keep the backend HTTPS-only. Packet capture remains unavailable in the WSGI deployment described below.

## Start the services

Open two terminals at the repository root:

```powershell
py -m pip install -r requirements.txt
py .\vercyra_security_api.py
```

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

Open <http://localhost:4173>. The Vite development server proxies `/api` to the Python API on `127.0.0.1:8765`. Packet capture is stopped by default. Start it from the dashboard only on systems and networks you are authorized to monitor. Windows packet capture may require Npcap and elevated privileges.

## cPanel domain path

The production Vite build is based at `/security/`. To publish the frontend without replacing the current homepage, build with `npm --prefix frontend run build` and upload the **contents** of `frontend/dist/` into `public_html/security/` in cPanel. The intended dashboard URL is `https://vercyra.com/security/`.

The frontend upload alone is not a working deployment. The public `https://vercyra.com/api/health` route was checked and currently returns 404. The cPanel Python application needs to be created at URL `/api`, with its application root outside `public_html`. Upload `passenger_wsgi.py`, `vercyra_passenger.py`, `vercyra_config.py`, `vercyra_network_security.py`, `vercyra_security_api.py`, and `requirements.txt` into that application root, then install requirements in the cPanel-created virtual environment and restart the Python app. Do not upload either `.env` file.

Set these environment variables in cPanel's Python Application settings, not in frontend files: `PAYPAL_ENVIRONMENT`, PayPal client credentials, webhook ID and plan IDs, `VERCYRA_PUBLIC_URL=https://vercyra.com/security`, `PAYPAL_WEBHOOK_URL=https://vercyra.com/api/paypal/webhook`, `VERCYRA_SESSION_SECRET`, and `VERCYRA_DASHBOARD_PASSWORD_HASH`. Generate a session secret locally with `py -c "import secrets; print(secrets.token_urlsafe(48))"`. Generate a password hash locally by running `py passenger_wsgi.py` and entering the dashboard password at its hidden prompt; copy only the resulting hash into cPanel. Never paste either value into chat or commit them.

After the app is mounted, verify `https://vercyra.com/api/health` returns `{"status":"ok"}`, and that unauthenticated dashboard endpoints return 401 while PayPal's signed webhook can reach `/api/paypal/webhook`. Shared cPanel hosting generally cannot capture raw network packets; this WSGI deployment returns an explicit unavailable response for packet capture. Use a VPS or a separate authorized sensor for live capture. Keep PayPal live checkout disabled until the public webhook route is deployed and verified.

Packet metadata and billing state are stored locally in `vercyra_security.db`. Packet payloads are not stored. Network event records older than 30 days are removed. The API binds to loopback and is intended for local development, not direct Internet exposure.

Store credentials in `%LOCALAPPDATA%\Vercyra\.env` (normally `C:\Users\<you>\AppData\Local\Vercyra\.env`). The app loads this user-only file before the repository `.env`, and explicit process environment variables take precedence over both. Its folder and file have Windows ACL inheritance disabled and access restricted to your Windows account. The repository `.env` is Git-ignored, but this project is under OneDrive; avoid putting credentials there because Git ignore does not prevent cloud synchronization.

## Local billing simulation

Local PayPal and Stripe simulators are available only when `PAYPAL_ENVIRONMENT=sandbox` and all three simulator flags are explicitly set to `true`. The ignored local `.env` is currently set to live mode with all simulators disabled. Simulated dashboard controls write `SIMULATED_ACTIVE` state and local simulator events only; they do not call either provider, create credentials, or take payments. Simulation cannot replace a real active PayPal subscription.

## PayPal sandbox licensing

1. Use `%LOCALAPPDATA%\Vercyra\.env` for credentials. The file is already created locally; `.env.example` is a reference template only.
2. Create sandbox REST app credentials, subscription products/plans, and a webhook in the PayPal developer dashboard.
3. Set `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID`, and the three `PAYPAL_PLAN_*` values in `%LOCALAPPDATA%\Vercyra\.env`. Plan IDs must be the actual IDs created in the same PayPal environment.
4. Subscribe the webhook to subscription activation, update, cancellation, suspension, expiration, and payment denial events. Set its URL to a public HTTPS endpoint forwarding to `http://127.0.0.1:8765/api/paypal/webhook`. PayPal cannot deliver webhooks directly to localhost. Use a trusted HTTPS tunnel for local sandbox testing, and do not expose the development API directly to the public Internet.
5. Keep `PAYPAL_ENVIRONMENT=sandbox` during testing. Set `VERCYRA_PUBLIC_URL` to the frontend URL users should return to after approving a subscription.
6. Restart the Python API after editing the per-user `.env`. Plan buttons stay disabled until PayPal credentials, webhook ID, and plans are configured.

The API obtains PayPal OAuth tokens server-side, creates subscriptions server-side, and asks PayPal to verify each webhook signature before applying license state. Webhook event IDs are stored for duplicate delivery protection. Subscription state is not activated by a browser redirect alone. CSV event export requires an active Pro or Business entitlement.

The tier labels correspond to features, not hard-coded prices: populate PayPal plan IDs with the products and prices configured in your PayPal sandbox account. Test all subscription lifecycle events in sandbox before switching to live credentials. Never place PayPal secrets in frontend source or `VITE_*` variables.

## Live payments are not enabled yet

The per-user `%LOCALAPPDATA%\Vercyra\.env` selects PayPal live mode but contains blank credentials and IDs, not working values. Checkout therefore remains disabled. Obtain live API credentials, plan IDs, and webhook ID from PayPal directly, then enter them in that per-user file; do not send secrets in chat. Configure `VERCYRA_PUBLIC_URL` and `PAYPAL_WEBHOOK_URL` as real HTTPS URLs and register that exact webhook URL in PayPal. The code refuses live checkout while those values are missing or still placeholders.

The dashboard and API are currently a local development setup: Vite on port 4173 and a loopback-only Python API on port 8765. Do not expose the Vite dev server or the unauthenticated local API to the Internet. Before accepting real customers, deploy behind HTTPS with user authentication, authorization, request protections, production process management, and a reverse proxy that exposes only intended routes. Verify the live webhook and subscription lifecycle with PayPal before directing customers to checkout. Real Stripe integration is not included; only an opt-in local Stripe simulator exists, and it is disabled in the current live configuration.
