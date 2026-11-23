"""Conexão com o banco do serviço. Cada serviço tem o seu: nenhum lê ou grava no banco de outro."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def conectar(url: str):
    """Devolve o engine, a fábrica de sessões e a dependência `get_db` do FastAPI."""
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def get_db():
        """Abre uma sessão por requisição e fecha no final."""
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    return engine, Sessao, get_db
