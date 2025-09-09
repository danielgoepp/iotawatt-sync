FROM python:3.9-alpine

LABEL Maintainer="danielgoepp"

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY ./vm_iotawatt_sync.py .

CMD [ "python", "./vm_iotawatt_sync.py" ]