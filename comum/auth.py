"""Dependências do FastAPI para exigir login e perfil.

Cada serviço confere o token sozinho, sem perguntar a ninguém: a assinatura, a validade e o
emissor. O id e o perfil de quem chamou vêm de dentro do token.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from comum import tokens
from comum.tokens import Identidade

esquema = HTTPBearer(auto_error=False)

NAO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Faça login para continuar.",
    headers={"WWW-Authenticate": "Bearer"},
)


def identidade(credenciais: HTTPAuthorizationCredentials | None = Depends(esquema)) -> Identidade:
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise NAO_AUTENTICADO
    try:
        return tokens.ler(credenciais.credentials)
    except tokens.TokenInvalido:
        raise NAO_AUTENTICADO


def token_do_pedido(credenciais: HTTPAuthorizationCredentials | None = Depends(esquema),
                    quem: Identidade = Depends(identidade)) -> str:
    """O token de quem chamou, já conferido, para repassar quando este serviço chama outro."""
    return credenciais.credentials


def exigir_perfil(*perfis: str):
    """Libera a rota só para os perfis informados."""
    def verificar(quem: Identidade = Depends(identidade)) -> Identidade:
        if quem.perfil not in perfis:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem permissão para esta ação.")
        return quem
    return verificar
