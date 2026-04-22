FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y stockfish && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STOCKFISH_PATH=/usr/games/stockfish

CMD ["gunicorn", "server:app", "--bind", "0.0.0.0:10000"]
