FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY passenger_wsgi.py vercyra_config.py vercyra_network_security.py vercyra_security_api.py ./

CMD ["sh", "-c", "exec gunicorn passenger_wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 120"]
