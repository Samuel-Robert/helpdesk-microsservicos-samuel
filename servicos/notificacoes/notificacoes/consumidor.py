"""Consumidor dos eventos de Chamados, lidos do fluxo do Redis em grupo de consumo.

O Redis guarda, para o grupo "notificacoes", até onde cada evento foi confirmado (XACK). Um evento
só é confirmado depois de o aviso estar gravado no banco. Por isso:

- se este serviço cair, os eventos publicados enquanto ele estava fora ficam no fluxo e são lidos
  quando ele volta;
- se cair no meio de um evento (lido e não confirmado), ele é lido de novo ao voltar, e o
  evento_id único no banco impede o aviso duplicado.

Cada evento traz o ID de rastreio do pedido que o gerou: o log daqui continua a mesma história.
"""
import os
import threading

import redis

from comum.rastreio import id_atual, log
from notificacoes import servico
from notificacoes.banco import Sessao

FLUXO = "helpdesk:eventos"
GRUPO = "notificacoes"
CONSUMIDOR = os.getenv("CONSUMIDOR", "notificacoes-1")


def processar(evento_id: str, campos: dict) -> None:
    marca = id_atual.set(campos.get("rastreio", "-"))
    try:
        with Sessao() as db:
            novo = servico.registrar(db, evento_id, campos["tipo"], int(campos["destinatario_id"]), campos["mensagem"])
        log.info("evento %s %s para o usuário %s", campos["tipo"], "gravado" if novo else "repetido, ignorado",
                 campos["destinatario_id"])
    finally:
        id_atual.reset(marca)


def consumir(r: redis.Redis, parar: threading.Event) -> None:
    """Lê e confirma eventos até `parar` ser acionado. Se o Redis cair, espera e tenta de novo."""
    pendentes = True  # ao começar, primeiro o que foi lido e não confirmado antes de uma queda
    while not parar.is_set():
        try:
            try:
                r.xgroup_create(FLUXO, GRUPO, id="0", mkstream=True)
            except redis.ResponseError as erro:
                if "BUSYGROUP" not in str(erro):  # o grupo já existe: tudo certo
                    raise
            resposta = r.xreadgroup(GRUPO, CONSUMIDOR, {FLUXO: "0" if pendentes else ">"}, count=50, block=2000)
            mensagens = resposta[0][1] if resposta else []
            if pendentes and not mensagens:
                pendentes = False
            for evento_id, campos in mensagens:
                processar(evento_id, campos)
                r.xack(FLUXO, GRUPO, evento_id)
        except redis.RedisError as erro:
            log.warning("Redis fora do ar (%s); nova tentativa em 2 s", type(erro).__name__)
            pendentes = True
            parar.wait(2)


_parar = threading.Event()


def iniciar() -> None:
    url = os.getenv("REDIS_URL")
    if not url:
        log.warning("sem REDIS_URL: nenhum evento será lido")
        return
    r = redis.Redis.from_url(url, decode_responses=True, socket_timeout=5, socket_connect_timeout=2)
    _parar.clear()
    threading.Thread(target=consumir, args=(r, _parar), name="consumidor", daemon=True).start()
    log.info("lendo o fluxo %s como %s, no grupo %s", FLUXO, CONSUMIDOR, GRUPO)


def parar() -> None:
    _parar.set()
