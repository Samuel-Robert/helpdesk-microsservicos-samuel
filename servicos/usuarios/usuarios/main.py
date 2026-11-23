"""Serviço de Usuários: cadastro, login e emissão dos tokens."""
import os

from comum.app import criar_app
from usuarios import dados_exemplo
from usuarios.banco import Base, Sessao, engine
from usuarios.rotas import router
from usuarios.rotas_auth import router as router_auth


def iniciar() -> None:
    Base.metadata.create_all(engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        with Sessao() as db:
            dados_exemplo.carregar(db)


app = criar_app("usuarios", [router_auth, router], ao_iniciar=iniciar)
