# One shared image for all of this project's agents (content_agent,
# poster_agent, telegram_bot). They're small, share the same
# dependencies, and docker-compose.yml just points each service at a
# different `command` (e.g. `python -m poster_agent.main`).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Overridden per-service in docker-compose.yml.
CMD ["python", "-m", "poster_agent.main"]
