from datetime import datetime, timedelta, timezone

import jwt

from comum import tokens
from comum.config import JWT_EMISSOR

PC = {"patrimonio": "PAT-1", "tipo": "computador", "descricao": "Desktop", "setor": "TI"}


# ---------- funcionamento ----------

def test_tecnico_cadastra_ativo_e_filtra_por_setor(cliente, contas):
    h = contas["carla"]
    cliente.post("/ativos", headers=h, json={"patrimonio": "PAT-1", "tipo": "impressora", "descricao": "HP", "setor": "RH"})
    cliente.post("/ativos", headers=h, json={"patrimonio": "PAT-2", "tipo": "computador", "descricao": "Dell", "setor": "TI"})
    assert len(cliente.get("/ativos", params={"setor": "RH"}, headers=h).json()) == 1


def test_chamados_consegue_conferir_o_equipamento(cliente, contas):
    """É a chamada que o serviço de Chamados faz pela rede antes de abrir um chamado."""
    ativo = cliente.post("/ativos", headers=contas["carla"], json=PC).json()
    assert cliente.get(f"/ativos/{ativo['id']}", headers=contas["ana"]).json()["patrimonio"] == "PAT-1"


def test_ativo_inexistente(cliente, contas):
    r = cliente.get("/ativos/99", headers=contas["ana"])
    assert r.status_code == 404 and r.json()["detail"] == "Ativo 99 não encontrado."


def test_patrimonio_repetido(cliente, contas):
    cliente.post("/ativos", headers=contas["carla"], json=PC)
    assert cliente.post("/ativos", headers=contas["carla"], json=PC).status_code == 422


# ---------- segurança ----------

def test_rotas_exigem_login(cliente):
    for metodo, rota in [("get", "/ativos"), ("get", "/ativos/1"), ("post", "/ativos")]:
        assert getattr(cliente, metodo)(rota).status_code == 401, rota


def test_solicitante_nao_cadastra_ativo(cliente, contas):
    assert cliente.post("/ativos", headers=contas["ana"], json=PC).status_code == 403


def test_token_assinado_com_outro_segredo(cliente):
    agora = datetime.now(timezone.utc)
    falso = jwt.encode({"sub": "1", "perfil": "admin", "iss": JWT_EMISSOR, "iat": agora, "exp": agora + timedelta(hours=1)},
                       "segredo-de-outra-pessoa-com-mais-de-32-caracteres", algorithm="HS256")
    assert cliente.post("/ativos", headers={"Authorization": f"Bearer {falso}"}, json=PC).status_code == 401


def test_token_sem_assinatura_alg_none(cliente):
    agora = datetime.now(timezone.utc)
    falso = jwt.encode({"sub": "1", "perfil": "admin", "iss": JWT_EMISSOR, "iat": agora, "exp": agora + timedelta(hours=1)},
                       None, algorithm="none")
    assert cliente.get("/ativos", headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_expirado(cliente):
    antigo = datetime.now(timezone.utc) - timedelta(hours=2)
    vencido = jwt.encode({"sub": "4", "perfil": "tecnico", "iss": JWT_EMISSOR, "iat": antigo,
                          "exp": antigo + timedelta(minutes=5)}, tokens.segredo(), algorithm="HS256")
    assert cliente.get("/ativos", headers={"Authorization": f"Bearer {vencido}"}).status_code == 401


def test_patrimonio_com_caractere_invalido(cliente, contas):
    r = cliente.post("/ativos", headers=contas["carla"], json={**PC, "patrimonio": "PAT 1; DROP"})
    assert r.status_code == 422


def test_campo_extra_e_recusado(cliente, contas):
    assert cliente.post("/ativos", headers=contas["carla"], json={**PC, "id": 50}).status_code == 422


def test_requisicao_grande_demais(cliente, contas):
    corpo = '{"descricao": "' + "x" * 70000 + '"}'
    r = cliente.post("/ativos", headers={**contas["carla"], "Content-Type": "application/json"}, content=corpo)
    assert r.status_code == 413


def test_cabecalhos_de_seguranca(cliente):
    r = cliente.get("/saude")
    assert r.json() == {"servico": "inventario", "status": "ok"}
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
