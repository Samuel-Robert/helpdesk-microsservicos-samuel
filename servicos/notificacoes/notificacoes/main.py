"""Serviço de Notificações: consome os eventos de Chamados e mostra os avisos de cada usuário."""
from comum.app import criar_app
from notificacoes import consumidor
from notificacoes.banco import Base, engine
from notificacoes.rotas import router


def iniciar() -> None:
    Base.metadata.create_all(engine)
    consumidor.iniciar()


app = criar_app("notificacoes", [router], ao_iniciar=iniciar, ao_parar=consumidor.parar)
