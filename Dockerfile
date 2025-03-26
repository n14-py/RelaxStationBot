FROM python:3.9-slim-bullseye

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean && \
    chmod 777 /tmp && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

USER 1001

EXPOSE 10000

CMD ["python", "main.py"]
