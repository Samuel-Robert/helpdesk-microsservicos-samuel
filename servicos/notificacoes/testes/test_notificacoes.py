from datetime import datetime, timedelta, timezone

import jwt

from comum.config import JWT_EMISSOR
from notificacoes import consumidor


def evento(tipo, destinatario_id, mensagem="aviso", rastreio="pedido-1"):
    """Os campos de um evento como Chamados publica no fluxo do Redis."""
    return {"tipo": tipo, "destinatario_id": str(destinatario_id), "mensagem": mensagem, "rastreio": rastreio}


def test_evento_vira_aviso_so_do_destinatario(cliente, contas, ler_eventos):
    ler_eventos([("1-0", evento("ChamadoAberto", 2, "Seu chamado #1 foi aberto."))])
    avisos = cliente.get("/notificacoes", headers=contas["ana"]).json()
    assert [(a["tipo"], a["mensagem"]) for a in avisos] == [("ChamadoAberto", "Seu chamado #1 foi aberto.")]
    assert cliente.get("/notificacoes", headers=contas["bia"]).json() == []


def test_confirma_so_depois_de_gravar(cliente, contas, ler_eventos):
    falso = ler_eventos([("1-0", evento("ChamadoAberto", 2)), ("2-0", evento("ChamadoAtribuido", 4))])
    assert falso.confirmados == ["1-0", "2-0"]
    assert len(cliente.get("/notificacoes", headers=contas["carla"]).json()) == 1


def test_evento_reentregue_nao_duplica(cliente, contas, ler_eventos):
    ler_eventos([("1-0", evento("ChamadoAberto", 2))])
    ler_eventos([("1-0", evento("ChamadoAberto", 2))])  # o mesmo evento, lido de novo depois de uma queda
    assert len(cliente.get("/notificacoes", headers=contas["ana"]).json()) == 1


def test_consumidor_aguenta_o_redis_fora_do_ar(cliente, contas, ler_eventos):
    falso = ler_eventos([("1-0", evento("ChamadoResolvido", 2))], quedas=2)
    assert falso.confirmados == ["1-0"]  # tentou de novo e leu quando o Redis voltou


def test_o_log_continua_com_o_id_de_rastreio(cliente, ler_eventos, caplog):
    consumidor.log.propagate = True  # deixa o caplog ver o log do serviço
    try:
        with caplog.at_level("INFO", logger="helpdesk"):
            ler_eventos([("1-0", evento("ChamadoAberto", 2, rastreio="pedido-77"))])
    finally:
        consumidor.log.propagate = False
    assert any(getattr(r, "rid", None) == "pedido-77" for r in caplog.records)


# ---------- segurança ----------

def test_rota_exige_login(cliente):
    assert cliente.get("/notificacoes").status_code == 401


def test_token_assinado_com_outro_segredo(cliente):
    agora = datetime.now(timezone.utc)
    falso = jwt.encode({"sub": "2", "perfil": "solicitante", "iss": JWT_EMISSOR, "iat": agora,
                        "exp": agora + timedelta(hours=1)}, "segredo-de-outra-pessoa-com-mais-de-32-caracteres")
    assert cliente.get("/notificacoes", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_cabecalhos_de_seguranca(cliente):
    r = cliente.get("/saude")
    assert r.json() == {"servico": "notificacoes", "status": "ok"}
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
