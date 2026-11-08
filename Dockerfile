FROM python:3.9-alpine

LABEL Maintainer="danielgoepp"
LABEL org.opencontainers.image.source="https://github.com/danielgoepp/iotawatt-sync"

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY ./vm_iotawatt_sync.py .

CMD [ "python", "./vm_iotawatt_sync.py" ]