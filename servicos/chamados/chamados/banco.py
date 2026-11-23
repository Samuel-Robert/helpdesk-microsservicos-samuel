"""Banco do serviço de Chamados (só este serviço o acessa)."""
import os

from sqlalchemy.orm import DeclarativeBase

from comum.banco import conectar

engine, Sessao, get_db = conectar(os.getenv("DATABASE_URL", "sqlite:///./chamados.db"))


class Base(DeclarativeBase):
    pass
