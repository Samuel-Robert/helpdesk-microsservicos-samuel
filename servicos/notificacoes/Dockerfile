# Serviço de Notificações. Construído a partir da raiz do repositório (docker compose), para levar a pasta comum/.
FROM python:3.15-slim

# Não roda como root dentro do contêiner
RUN useradd --create-home --uid 10001 helpdesk && mkdir /dados && chown helpdesk /dados

WORKDIR /srv
COPY servicos/notificacoes/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY comum ./comum
COPY servicos/notificacoes/notificacoes ./notificacoes

USER helpdesk
ENV DATABASE_URL=sqlite:////dados/notificacoes.db \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "notificacoes.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
