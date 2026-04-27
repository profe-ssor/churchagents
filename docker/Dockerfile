FROM python:3.12-slim-bookworm

WORKDIR /app

# System deps for weasyprint / reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Worker must consume the `agents` queue — task_routes in scheduler/celery_app.py send tasks there.
# Include `celery` so ad-hoc calls without a route still work.
CMD ["celery", "-A", "scheduler.celery_app", "worker", "--beat", \
     "--loglevel=info", "--concurrency=4", "-Q", "agents,celery"]
