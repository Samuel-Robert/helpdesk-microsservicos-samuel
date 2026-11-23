# API Gateway. Construído a partir da raiz do repositório (docker compose), para levar a pasta comum/.
FROM python:3.12-slim

# Não roda como root dentro do contêiner
RUN useradd --create-home --uid 10001 helpdesk

WORKDIR /srv
COPY servicos/gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY comum ./comum
COPY servicos/gateway/gateway ./gateway

USER helpdesk
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
