"""Testes do serviço de Chamados com uma rede falsa.

Usuários e Inventário são simulados por um transporte do httpx: respondem como os serviços de
verdade, guardam o que receberam e podem ser "derrubados" (`rede.fora_do_ar`) ou ficar lentos
(`rede.lentos`). Os eventos publicados ficam numa lista, em vez de ir para o Redis.
"""
import os

os.environ.setdefault("JWT_SEGREDO", "segredo-so-para-os-testes-com-mais-de-32-caracteres")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["DADOS_EXEMPLO"] = "0"
os.environ["USUARIOS_URL"] = "http://usuarios"
os.environ["INVENTARIO_URL"] = "http://inventario"

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from chamados import clientes, eventos  # noqa: E402
from chamados.banco import Base, get_db  # noqa: E402
from chamados.main import app  # noqa: E402
from comum import tokens  # noqa: E402

USUARIOS = {1: ("Admin", "admin"), 2: ("Ana", "solicitante"), 3: ("Bia", "solicitante"), 4: ("Carla", "tecnico")}
ATIVOS = {1: {"id": 1, "patrimonio": "PAT-1", "tipo": "computador", "descricao": "Desktop", "setor": "TI"}}


class RedeFalsa:
    def __init__(self):
        self.fora_do_ar: set[str] = set()
        self.lentos: set[str] = set()
        self.pedidos: list[httpx.Request] = []

    def responder(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        servico = pedido.url.host
        if servico in self.fora_do_ar:
            raise httpx.ConnectError("conexão recusada", request=pedido)
        if servico in self.lentos:
            raise httpx.ReadTimeout("passou do tempo limite", request=pedido)
        recurso, ident = pedido.url.path.strip("/").split("/")
        if servico == "usuarios" and int(ident) in USUARIOS:
            nome, perfil = USUARIOS[int(ident)]
            return httpx.Response(200, json={"id": int(ident), "nome": nome, "perfil": perfil})
        if servico == "inventario" and int(ident) in ATIVOS:
            return httpx.Response(200, json=ATIVOS[int(ident)])
        return httpx.Response(404, json={"detail": f"{recurso} {ident} não encontrado."})

    def chamadas_a(self, servico: str) -> int:
        return sum(1 for p in self.pedidos if p.url.host == servico)


@pytest.fixture
def rede(monkeypatch):
    falsa = RedeFalsa()
    monkeypatch.setattr(clientes, "http", httpx.Client(transport=httpx.MockTransport(falsa.responder)))
    for _, disjuntor in clientes.SERVICOS.values():
        disjuntor.sucesso()  # cada teste começa com os disjuntores fechados
    return falsa


@pytest.fixture
def publicados(monkeypatch):
    lista = []
    monkeypatch.setattr(eventos, "publicar", lambda tipo, destinatario_id, mensagem: lista.append((tipo, destinatario_id)))
    return lista


@pytest.fixture
def cliente(rede, publicados):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def db_de_teste():
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_de_teste
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def contas():
    """Cabeçalho de login de cada pessoa, com os mesmos ids da rede falsa."""
    def cabecalho(usuario_id, perfil):
        return {"Authorization": f"Bearer {tokens.criar(usuario_id, perfil)[0]}"}
    return {"admin": cabecalho(1, "admin"), "ana": cabecalho(2, "solicitante"), "bia": cabecalho(3, "solicitante"),
            "carla": cabecalho(4, "tecnico")}


@pytest.fixture
def abrir(cliente, contas):
    def abrir(quem="ana", prioridade="alta", **extra):
        dados = {"titulo": "PC não liga", "descricao": "Nada acontece", "prioridade": prioridade, "ativo_id": 1, **extra}
        return cliente.post("/chamados", headers=contas[quem], json=dados)
    return abrir
