# Vercyra.com deployment plan

This repository contains the React frontend. The authenticated app and SQLite data live in a separate Node service under `C:/Users/hp/OneDrive/Documents/Vercyra`.

## Recommended production architecture

Use a single domain, `vercyra.com`, with:

- DNS: `A` record for `@` and `CNAME` for `www`
- Nginx: reverse proxy for HTTPS traffic
- Node backend: `Vercyra/server.mjs` on port `8765`
- Frontend: built `dist/` output served by Nginx or by the same Node service
- TLS: managed by Certbot or a managed host

This is a good production shape for your app because the backend sets cookies and the frontend calls `/api/*` from the same origin.

## 1) DNS

Create these records at your domain provider:

- `A @ -> <your VPS/public IP>`
- `CNAME www -> vercyra.com`

Before the site is live, verify the server is reachable on the public IP.

## 2) Host setup

On Ubuntu 22.04 or a similar VPS:

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx nodejs npm
sudo npm install -g npm@latest
```

## 3) Backend deployment

Place the backend folder on the server:

```bash
sudo mkdir -p /var/www/vercyra
sudo cp -r /path/to/Vercyra /var/www/vercyra/app
```

Run it with a service manager such as systemd:

```bash
sudo nano /etc/systemd/system/vercyra.service
```

Example:

```ini
[Unit]
Description=Vercyra backend
After=network.target

[Service]
WorkingDirectory=/var/www/vercyra/app
Environment=NODE_ENV=production
Environment=TRUST_PROXY=true
ExecStart=/usr/bin/node server.mjs
Restart=always
RestartSec=5
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vercyra.service
sudo systemctl status vercyra.service
```

## 4) Frontend deployment

Build the frontend in this repo:

```bash
cd /path/to/vercywoods/frontend
npm install
npm run build
```

If you want the frontend served by the same domain on HTTPS, copy the output to a web directory and let Nginx serve it:

```bash
sudo mkdir -p /var/www/vercyra/frontend
sudo cp -r dist/* /var/www/vercyra/frontend/
```

Set the production API base in the frontend env file:

```bash
VITE_API_BASE_URL=https://vercyra.com
```

The file already has a sample in `frontend/.env.example`.

## 5) Nginx reverse proxy

Create a config file like this:

```nginx
server {
    listen 80;
    server_name vercyra.com www.vercyra.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name vercyra.com www.vercyra.com;

    ssl_certificate /etc/letsencrypt/live/vercyra.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/vercyra.com/privkey.pem;

    root /var/www/vercyra/frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable it:

```bash
sudo ln -s /etc/nginx/sites-available/vercyra.conf /etc/nginx/sites-enabled/vercyra.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 6) TLS

```bash
sudo certbot --nginx -d vercyra.com -d www.vercyra.com
```

## 7) Cookie and domain requirements

The backend uses a cookie named `vercyra_session` and sets it with:

- `HttpOnly`
- `SameSite=Lax`
- `Secure` when `NODE_ENV=production`

For production, make sure the browser sees the cookie on `vercyra.com` and that the app is served from the same root domain or a trusted subdomain. A same-origin setup is the simplest and safest option.

## 8) Final production checklist

- DNS records are live
- Nginx listens on 80/443
- TLS certificate is valid
- backend runs on port 8765
- `/api/health` returns `{"status":"ok"}`
- frontend build succeeds
- `/api/login` and `/api/dashboard` work with the live domain
- cookies are sent and retained on the production domain

## Important note

This environment does not have the live domain credentials, DNS control, or hosting account needed to push the site to `vercyra.com` directly. The steps above are the exact production setup to run once those credentials are available.
