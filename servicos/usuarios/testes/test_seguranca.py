"""Testes de segurança do serviço de Usuários: login, token, senhas, permissões e entrada."""
from datetime import datetime, timedelta, timezone

import jwt

from comum import tokens
from comum.config import JWT_EMISSOR
from usuarios import limite
from usuarios.modelos import Usuario


def forjar(segredo, algoritmo="HS256", **dados):
    agora = datetime.now(timezone.utc)
    corpo = {"sub": "1", "perfil": "admin", "iss": JWT_EMISSOR, "iat": agora, "exp": agora + timedelta(hours=1), **dados}
    return {"Authorization": f"Bearer {jwt.encode(corpo, segredo, algorithm=algoritmo)}"}


# ---------- autenticação ----------

def test_rotas_exigem_login(cliente, contas):
    for metodo, rota in [("get", "/usuarios"), ("get", "/usuarios/1"), ("post", "/usuarios"), ("get", "/auth/eu")]:
        assert getattr(cliente, metodo)(rota).status_code == 401, rota


def test_login_com_senha_errada(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ana@x.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["detail"] == "E-mail ou senha inválidos."


def test_login_com_email_inexistente_tem_a_mesma_mensagem(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ninguem@x.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["detail"] == "E-mail ou senha inválidos."


def test_bloqueio_apos_varias_senhas_erradas(cliente, contas, senha):
    for _ in range(limite.MAX_FALHAS):
        cliente.post("/auth/login", json={"email": "ana@x.com", "senha": "errada123"})
    # mesmo com a senha certa, fica bloqueado por um tempo
    assert cliente.post("/auth/login", json={"email": "ana@x.com", "senha": senha}).status_code == 429


def test_token_adulterado(cliente, contas):
    token = contas["ana"]["headers"]["Authorization"] + "x"
    assert cliente.get("/auth/eu", headers={"Authorization": token}).status_code == 401


def test_token_assinado_com_outro_segredo(cliente, contas):
    h = forjar("segredo-de-outra-pessoa-com-mais-de-32-caracteres", sub=str(contas["admin"]["id"]))
    assert cliente.get("/auth/eu", headers=h).status_code == 401


def test_token_sem_assinatura_alg_none(cliente, contas):
    h = forjar(None, algoritmo="none", sub=str(contas["admin"]["id"]))
    assert cliente.get("/auth/eu", headers=h).status_code == 401


def test_token_expirado(cliente, contas):
    antigo = datetime.now(timezone.utc) - timedelta(hours=2)
    h = forjar(tokens.segredo(), sub=str(contas["ana"]["id"]), iat=antigo, exp=antigo + timedelta(minutes=5))
    assert cliente.get("/auth/eu", headers=h).status_code == 401


def test_usuario_desativado_perde_o_acesso_na_hora(sessao, cliente, contas):
    with sessao() as db:
        db.get(Usuario, contas["ana"]["id"]).ativo = False
        db.commit()
    # o token ainda não venceu, mas este serviço confere no banco
    assert cliente.get("/auth/eu", headers=contas["ana"]["headers"]).status_code == 401


def test_senha_guardada_com_hash(sessao, contas, senha):
    with sessao() as db:
        u = db.query(Usuario).filter_by(email="ana@x.com").one()
        assert senha not in u.senha_hash and u.senha_hash.startswith("scrypt$")


def test_senha_fraca_e_recusada(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "solicitante", "senha": "abcdefgh"})
    assert r.status_code == 422


# ---------- permissões ----------

def test_solicitante_nao_cria_usuario(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["ana"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "admin", "senha": "Forte1234"})
    assert r.status_code == 403


def test_tecnico_nao_cria_usuario(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["carla"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "admin", "senha": "Forte1234"})
    assert r.status_code == 403


# ---------- entrada e respostas ----------

def test_campo_extra_e_recusado(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "solicitante", "senha": "Forte1234", "ativo": False})
    assert r.status_code == 422


def test_requisicao_grande_demais(cliente, contas):
    corpo = '{"nome": "' + "x" * 70000 + '"}'
    r = cliente.post("/usuarios", headers={**contas["admin"]["headers"], "Content-Type": "application/json"}, content=corpo)
    assert r.status_code == 413


def test_cabecalhos_de_seguranca(cliente):
    r = cliente.get("/saude")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_id_de_rastreio_volta_na_resposta(cliente):
    assert cliente.get("/saude", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"
    # um ID com caracteres estranhos é trocado por um novo, para não sujar os logs
    novo = cliente.get("/saude", headers={"X-Request-ID": "<script>"}).headers["x-request-id"]
    assert novo != "<script>" and novo.isalnum()
