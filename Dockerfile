FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
VOLUME ["/app/data"]

# Shell form so ${PORT} expands: Render injects PORT; defaults to 8000 elsewhere.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
