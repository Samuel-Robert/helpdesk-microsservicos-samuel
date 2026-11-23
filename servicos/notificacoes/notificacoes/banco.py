"""Banco do serviço de Notificações (só este serviço o acessa)."""
import os

from sqlalchemy.orm import DeclarativeBase

from comum.banco import conectar

engine, Sessao, get_db = conectar(os.getenv("DATABASE_URL", "sqlite:///./notificacoes.db"))


class Base(DeclarativeBase):
    pass
