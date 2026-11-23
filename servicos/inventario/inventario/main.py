"""Serviço de Inventário: cadastro e consulta de equipamentos."""
import os

from comum.app import criar_app
from inventario import dados_exemplo
from inventario.banco import Base, Sessao, engine
from inventario.rotas import router


def iniciar() -> None:
    Base.metadata.create_all(engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        with Sessao() as db:
            dados_exemplo.carregar(db)


app = criar_app("inventario", [router], ao_iniciar=iniciar)
