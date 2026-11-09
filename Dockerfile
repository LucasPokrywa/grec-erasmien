FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends espeak-ng ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.js index.html styles.css phonology.py natural_voice.py server.py ./
EXPOSE 10000
CMD ["python", "server.py", "--host", "0.0.0.0", "--no-browser"]
