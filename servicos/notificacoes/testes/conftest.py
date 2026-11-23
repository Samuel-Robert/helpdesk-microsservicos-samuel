"""Testes do serviço de Notificações: banco em memória e um Redis simulado."""
import os

os.environ.setdefault("JWT_SEGREDO", "segredo-so-para-os-testes-com-mais-de-32-caracteres")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.pop("REDIS_URL", None)  # o consumidor de verdade não sobe nos testes

import pytest  # noqa: E402
import redis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from comum import tokens  # noqa: E402
from notificacoes import consumidor  # noqa: E402
from notificacoes.banco import Base, get_db  # noqa: E402
from notificacoes.main import app  # noqa: E402


@pytest.fixture
def cliente(monkeypatch):
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
    monkeypatch.setattr(consumidor, "Sessao", Sessao)  # o consumidor grava no mesmo banco de teste
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def contas():
    def cabecalho(usuario_id, perfil):
        return {"Authorization": f"Bearer {tokens.criar(usuario_id, perfil)[0]}"}
    return {"ana": cabecalho(2, "solicitante"), "bia": cabecalho(3, "solicitante"), "carla": cabecalho(4, "tecnico")}


class ParadaRapida:
    """Como threading.Event, mas a espera depois de uma falha não atrasa o teste."""
    def __init__(self):
        self.acionada = False

    def is_set(self):
        return self.acionada

    def set(self):
        self.acionada = True

    def wait(self, segundos):
        return self.acionada


class RedisFalso:
    """Entrega os eventos uma vez, guarda as confirmações e pode começar fora do ar."""
    def __init__(self, eventos, parar, quedas=0):
        self.fila, self.parar, self.quedas = list(eventos), parar, quedas
        self.confirmados, self.grupo_criado = [], False

    def xgroup_create(self, fluxo, grupo, id, mkstream):
        if self.quedas:
            self.quedas -= 1
            raise redis.ConnectionError("Redis fora do ar")
        if self.grupo_criado:
            raise redis.ResponseError("BUSYGROUP Consumer Group name already exists")
        self.grupo_criado = True

    def xreadgroup(self, grupo, nome, fluxos, count, block):
        if list(fluxos.values())[0] == "0":
            return [["helpdesk:eventos", []]]  # nada pendente de antes
        if not self.fila:
            self.parar.set()
            return []
        lote, self.fila = self.fila, []
        return [["helpdesk:eventos", lote]]

    def xack(self, fluxo, grupo, evento_id):
        self.confirmados.append(evento_id)


@pytest.fixture
def ler_eventos():
    """Roda o consumidor sobre uma lista de (id, campos) e devolve o Redis falso, para conferir."""
    def ler(eventos, quedas=0):
        parar = ParadaRapida()
        falso = RedisFalso(eventos, parar, quedas)
        consumidor.consumir(falso, parar)
        return falso
    return ler
