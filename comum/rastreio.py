"""ID de rastreio: cada requisição ganha um ID que passa por todos os serviços e aparece nos logs.

O gateway cria o ID (ou aceita o que veio no cabeçalho X-Request-ID, se tiver formato seguro) e
cada serviço o repassa nas chamadas que faz. Para seguir um pedido de ponta a ponta:

    docker compose logs | grep <id>
"""
import logging
import re
import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

CABECALHO = "X-Request-ID"
id_atual: ContextVar[str] = ContextVar("id_de_rastreio", default="-")
# Só letras, números e hífen: ninguém forja uma linha falsa no log mandando uma quebra de linha
FORMATO_VALIDO = re.compile(r"^[A-Za-z0-9-]{1,64}$")

log = logging.getLogger("helpdesk")


class Rastreio(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        recebido = request.headers.get(CABECALHO, "")
        rid = recebido if FORMATO_VALIDO.match(recebido) else uuid.uuid4().hex[:12]
        marca = id_atual.set(rid)
        inicio = time.perf_counter()
        try:
            resposta = await call_next(request)
            resposta.headers[CABECALHO] = rid
            log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, resposta.status_code,
                     (time.perf_counter() - inicio) * 1000)
            return resposta
        finally:
            id_atual.reset(marca)


class _ComId(logging.Filter):
    def filter(self, registro: logging.LogRecord) -> bool:
        registro.rid = id_atual.get()
        return True


def configurar_logs(servico: str) -> None:
    """Cada linha de log sai com a hora, o serviço e o ID de rastreio."""
    saida = logging.StreamHandler()
    saida.addFilter(_ComId())
    saida.setFormatter(logging.Formatter(f"%(asctime)s {servico:<12} [%(rid)s] %(message)s", "%H:%M:%S"))
    log.handlers[:] = [saida]
    log.setLevel(logging.INFO)
    log.propagate = False
