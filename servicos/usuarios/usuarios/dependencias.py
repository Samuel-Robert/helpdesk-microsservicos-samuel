"""Login com os dados do próprio banco.

Os outros serviços confiam no perfil que vem dentro do token. Este serviço é o dono dos usuários,
então confere no banco: um usuário desativado ou rebaixado perde o acesso aqui na hora.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from comum.auth import NAO_AUTENTICADO, identidade
from comum.tokens import Identidade
from usuarios.banco import get_db
from usuarios.modelos import Usuario


def usuario_atual(quem: Identidade = Depends(identidade), db: Session = Depends(get_db)) -> Usuario:
    usuario = db.get(Usuario, quem.id)
    if usuario is None or not usuario.ativo:
        raise NAO_AUTENTICADO
    return usuario


def exigir_admin(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    if usuario.perfil != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem permissão para esta ação.")
    return usuario
