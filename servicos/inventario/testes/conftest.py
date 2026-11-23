"""Testes do serviço de Inventário: banco em memória e tokens feitos aqui mesmo.

O serviço não depende de Usuários para funcionar: basta um token válido, que os testes geram.
"""
import os

os.environ.setdefault("JWT_SEGREDO", "segredo-so-para-os-testes-com-mais-de-32-caracteres")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["DADOS_EXEMPLO"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from comum import tokens  # noqa: E402
from inventario.banco import Base, get_db  # noqa: E402
from inventario.main import app  # noqa: E402


@pytest.fixture
def cliente():
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
    """Cabeçalho de login de um admin, uma solicitante e uma técnica (ids como os de Usuários)."""
    def cabecalho(usuario_id, perfil):
        return {"Authorization": f"Bearer {tokens.criar(usuario_id, perfil)[0]}"}
    return {"admin": cabecalho(1, "admin"), "ana": cabecalho(2, "solicitante"), "carla": cabecalho(4, "tecnico")}
