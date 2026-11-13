FROM python:3.13-alpine

LABEL org.opencontainers.image.source="https://github.com/danielgoepp/iotawatt-sync"
LABEL org.opencontainers.image.authors="danielgoepp"

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY vm_iotawatt_sync.py .

USER nobody

CMD ["python", "./vm_iotawatt_sync.py"]
