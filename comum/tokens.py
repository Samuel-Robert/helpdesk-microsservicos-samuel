"""Criação e conferência dos tokens JWT, iguais em todos os serviços.

O segredo vem da variável JWT_SEGREDO (arquivo .env) ou, se ela não existir, do arquivo que o
contêiner `segredo` gera na primeira subida do docker compose. Nunca do código.
"""
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import cache
from pathlib import Path

import jwt

from comum.config import JWT_ALGORITMO, JWT_EMISSOR, TOKEN_MINUTOS

ARQUIVO_SEGREDO = Path(os.getenv("JWT_SEGREDO_ARQUIVO", "/segredos/jwt"))


class TokenInvalido(Exception):
    pass


@dataclass(frozen=True)
class Identidade:
    """Quem fez a requisição, segundo o token: o id e o perfil."""
    id: int
    perfil: str


@cache
def segredo() -> str:
    valor = os.getenv("JWT_SEGREDO") or (ARQUIVO_SEGREDO.read_text().strip() if ARQUIVO_SEGREDO.is_file() else "")
    if len(valor) < 32:
        raise RuntimeError(
            "JWT_SEGREDO ausente ou curto (mínimo 32 caracteres). "
            "Defina no .env ou suba pelo docker compose, que gera um na primeira vez."
        )
    return valor


def criar(usuario_id: int, perfil: str) -> tuple[str, datetime]:
    agora = datetime.now(timezone.utc)
    expira = agora + timedelta(minutes=TOKEN_MINUTOS)
    dados = {"sub": str(usuario_id), "perfil": perfil, "iat": agora, "exp": expira, "iss": JWT_EMISSOR}
    return jwt.encode(dados, segredo(), algorithm=JWT_ALGORITMO), expira


def ler(token: str) -> Identidade:
    """Devolve quem é o dono do token, ou lança TokenInvalido."""
    try:
        dados = jwt.decode(
            token, segredo(), algorithms=[JWT_ALGORITMO], issuer=JWT_EMISSOR,
            options={"require": ["exp", "iat", "sub", "iss", "perfil"]},
        )
        return Identidade(int(dados["sub"]), str(dados["perfil"]))
    except (jwt.PyJWTError, ValueError) as erro:
        raise TokenInvalido() from erro
