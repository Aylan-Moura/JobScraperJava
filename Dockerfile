FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    curl \
    --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ .

CMD ["python", "main.py"]
