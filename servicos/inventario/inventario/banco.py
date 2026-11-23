"""Banco do serviço de Inventário (só este serviço o acessa)."""
import os

from sqlalchemy.orm import DeclarativeBase

from comum.banco import conectar

engine, Sessao, get_db = conectar(os.getenv("DATABASE_URL", "sqlite:///./inventario.db"))


class Base(DeclarativeBase):
    pass
