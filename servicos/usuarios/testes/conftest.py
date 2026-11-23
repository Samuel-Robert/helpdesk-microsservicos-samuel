"""Testes do serviço de Usuários: banco em memória, novo a cada teste, e sem Redis."""
import os

os.environ.setdefault("JWT_SEGREDO", "segredo-so-para-os-testes-com-mais-de-32-caracteres")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["DADOS_EXEMPLO"] = "0"
os.environ.pop("REDIS_URL", None)  # sem Redis, o limite de login usa a memória

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from usuarios import limite, servico  # noqa: E402
from usuarios.banco import Base, get_db  # noqa: E402
from usuarios.esquemas import UsuarioCriar  # noqa: E402
from usuarios.main import app  # noqa: E402

SENHA = "Senha123"


@pytest.fixture
def senha():
    return SENHA


@pytest.fixture
def sessao():
    limite.limpar_tudo()
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
    yield Sessao
    app.dependency_overrides.clear()


@pytest.fixture
def cliente(sessao):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def contas(sessao, cliente):
    """Cria um admin, dois solicitantes e um técnico, e devolve o cabeçalho de login de cada um."""
    with sessao() as db:
        for nome, email, perfil in [("Admin", "admin@x.com", "admin"), ("Ana", "ana@x.com", "solicitante"),
                                    ("Bia", "bia@x.com", "solicitante"), ("Carla", "carla@x.com", "tecnico")]:
            servico.criar(db, UsuarioCriar(nome=nome, email=email, perfil=perfil, senha=SENHA))
    resultado = {}
    for apelido in ("admin", "ana", "bia", "carla"):
        r = cliente.post("/auth/login", json={"email": f"{apelido}@x.com", "senha": SENHA}).json()
        resultado[apelido] = {"headers": {"Authorization": f"Bearer {r['access_token']}"}, "id": r["usuario"]["id"]}
    return resultado
