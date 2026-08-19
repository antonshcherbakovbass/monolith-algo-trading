FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY hedge_fund/requirements.txt /app/hedge_fund/requirements.txt
RUN pip install --no-cache-dir -r hedge_fund/requirements.txt

COPY . /app

ENV PYTHONUNBUFFERED=1
ENV MONOLITH_MODE=paper
ENV DATABASE_URL=sqlite+aiosqlite:///hedge_fund/data/monolith.db

# Bootstrap models if missing
RUN python -m hedge_fund.scripts.bootstrap_models || true

EXPOSE 8080

CMD ["python", "-m", "hedge_fund.main", "--no-gui", "--no-dashboard"]
