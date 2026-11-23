from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from comum.auth import identidade
from comum.tokens import Identidade
from notificacoes import servico
from notificacoes.banco import get_db
from notificacoes.esquemas import NotificacaoSaida

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])


@router.get("", response_model=list[NotificacaoSaida])
def minhas_notificacoes(quem: Identidade = Depends(identidade), db: Session = Depends(get_db)):
    """Cada usuário vê só as próprias notificações."""
    return servico.listar(db, quem.id)
