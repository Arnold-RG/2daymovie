FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV PORT=5000
ENV FLASK_DEBUG=0

CMD gunicorn app:app --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120
