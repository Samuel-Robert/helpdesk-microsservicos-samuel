from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from comum import tokens
from usuarios import limite, senhas, servico
from usuarios.banco import get_db
from usuarios.dependencias import usuario_atual
from usuarios.esquemas import Login, TokenSaida, UsuarioSaida
from usuarios.modelos import Usuario

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenSaida)
def login(dados: Login, request: Request, db: Session = Depends(get_db)):
    email = dados.email.lower()
    # O endereço de quem tenta vem do gateway (X-Forwarded-For), não do próprio gateway
    chave = f"{email}|{request.client.host if request.client else '-'}"
    if limite.bloqueado(chave):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas tentativas. Tente de novo em alguns minutos.")

    usuario = servico.buscar_por_email(db, email)
    # Confere a senha mesmo sem usuário, para o tempo de resposta não revelar se o e-mail existe
    senha_ok = senhas.conferir(dados.senha, usuario.senha_hash if usuario else senhas.HASH_FALSO)
    if not usuario or not senha_ok or not usuario.ativo:
        limite.registrar_falha(chave)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos.")

    limite.limpar(chave)
    token, expira = tokens.criar(usuario.id, usuario.perfil)
    return TokenSaida(access_token=token, expira_em=expira, usuario=UsuarioSaida.model_validate(usuario))


@router.get("/eu", response_model=UsuarioSaida)
def quem_sou_eu(usuario: Usuario = Depends(usuario_atual)):
    return usuario
