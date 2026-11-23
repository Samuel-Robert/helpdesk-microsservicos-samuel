"""Regras do serviço de Notificações."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from notificacoes.modelos import Notificacao


def registrar(db: Session, evento_id: str, tipo: str, destinatario_id: int, mensagem: str) -> bool:
    """Grava o aviso de um evento. Devolve False se o evento já tinha sido gravado (reentrega)."""
    if db.scalar(select(Notificacao.id).where(Notificacao.evento_id == evento_id)):
        return False
    db.add(Notificacao(evento_id=evento_id, tipo=tipo, destinatario_id=destinatario_id,
                       mensagem=mensagem[:300], criada_em=datetime.now()))
    db.commit()
    return True


def listar(db: Session, destinatario_id: int) -> list[Notificacao]:
    consulta = select(Notificacao).where(Notificacao.destinatario_id == destinatario_id).order_by(Notificacao.id)
    return list(db.scalars(consulta))
