"""Serviço de Chamados: o fluxo de um chamado, do aberto ao fechado."""
import os

from chamados import clientes, dados_exemplo
from chamados.banco import Base, Sessao, engine
from chamados.rotas import router
from comum.app import criar_app


def iniciar() -> None:
    Base.metadata.create_all(engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        with Sessao() as db:
            dados_exemplo.carregar(db)


app = criar_app("chamados", [router], ao_iniciar=iniciar, ao_parar=clientes.http.close)
