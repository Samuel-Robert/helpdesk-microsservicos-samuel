"""Limite de tentativas de login.

No monólito, as falhas ficavam na memória do processo. Com microsserviços, o serviço de Usuários
pode rodar em mais de uma cópia, e quem errasse a senha numa cópia tentaria de novo na outra.
Por isso as falhas ficam no Redis, que todas as cópias enxergam.

Sem Redis (nos testes, ou se ele cair), o controle volta para a memória: o login continua
protegido e funcionando, só que por cópia.
"""
import os
import time
from collections import defaultdict
from threading import Lock

import redis

from comum.rastreio import log

MAX_FALHAS = int(os.getenv("LOGIN_MAX_FALHAS", "5"))
JANELA_SEGUNDOS = int(os.getenv("LOGIN_JANELA_SEGUNDOS", "300"))

_url = os.getenv("REDIS_URL")
_redis = redis.Redis.from_url(_url, socket_timeout=1, socket_connect_timeout=1) if _url else None

_falhas: dict[str, list[float]] = defaultdict(list)
_trava = Lock()


def _chave(chave: str) -> str:
    return f"login:falhas:{chave}"


def _recentes(chave: str, agora: float) -> list[float]:
    _falhas[chave] = [t for t in _falhas[chave] if agora - t < JANELA_SEGUNDOS]
    return _falhas[chave]


def bloqueado(chave: str) -> bool:
    if _redis:
        try:
            return int(_redis.get(_chave(chave)) or 0) >= MAX_FALHAS
        except redis.RedisError:
            log.warning("Redis fora do ar: limite de login na memória")
    with _trava:
        return len(_recentes(chave, time.monotonic())) >= MAX_FALHAS


def registrar_falha(chave: str) -> None:
    if _redis:
        try:
            with _redis.pipeline() as p:
                p.incr(_chave(chave))
                p.expire(_chave(chave), JANELA_SEGUNDOS, nx=True)  # a janela conta da primeira falha
                p.execute()
            return
        except redis.RedisError:
            log.warning("Redis fora do ar: limite de login na memória")
    with _trava:
        agora = time.monotonic()
        _recentes(chave, agora).append(agora)


def limpar(chave: str) -> None:
    if _redis:
        try:
            _redis.delete(_chave(chave))
        except redis.RedisError:
            pass
    with _trava:
        _falhas.pop(chave, None)


def limpar_tudo() -> None:
    """Só para os testes."""
    with _trava:
        _falhas.clear()
