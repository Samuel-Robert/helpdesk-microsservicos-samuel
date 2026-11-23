"""Eventos do serviço de Chamados, publicados num fluxo do Redis (Redis Streams).

No monólito, avisar era chamar notificacoes.notificar(). Agora Chamados só publica o fato
(ChamadoAberto, ChamadoAtribuido, ChamadoResolvido) e segue: não sabe quem vai ler nem espera
resposta. Se o serviço de Notificações cair, os eventos esperam no fluxo até ele voltar.
Se o próprio Redis cair, o chamado é aberto do mesmo jeito e o aviso fica só no log.
"""
import os

import redis

from comum.rastreio import id_atual, log

FLUXO = "helpdesk:eventos"

_url = os.getenv("REDIS_URL")
_redis = redis.Redis.from_url(_url, socket_timeout=1, socket_connect_timeout=1) if _url else None


def publicar(tipo: str, destinatario_id: int, mensagem: str) -> None:
    # ponytail: sem tabela de saída (outbox); se o Redis estiver fora, o aviso se perde. Criar a tabela se isso importar.
    if _redis is None:
        log.warning("sem REDIS_URL: evento %s não publicado", tipo)
        return
    try:
        _redis.xadd(FLUXO, {"tipo": tipo, "destinatario_id": destinatario_id, "mensagem": mensagem,
                            "rastreio": id_atual.get()}, maxlen=10_000, approximate=True)
        log.info("evento %s publicado para o usuário %s", tipo, destinatario_id)
    except redis.RedisError as erro:
        log.warning("Redis fora do ar: evento %s não publicado (%s)", tipo, type(erro).__name__)
