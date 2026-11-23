# Serviço de Usuários. Construído a partir da raiz do repositório (docker compose), para levar a pasta comum/.
FROM python:3.15-slim

# Não roda como root dentro do contêiner
RUN useradd --create-home --uid 10001 helpdesk && mkdir /dados && chown helpdesk /dados

WORKDIR /srv
COPY servicos/usuarios/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY comum ./comum
COPY servicos/usuarios/usuarios ./usuarios

USER helpdesk
ENV DATABASE_URL=sqlite:////dados/usuarios.db \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 8000
# O IP de quem tenta o login chega pelo gateway (X-Forwarded-For). Dá para confiar porque o serviço
# não publica porta: só quem está na rede interna do Docker fala com ele.
CMD ["uvicorn", "usuarios.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
