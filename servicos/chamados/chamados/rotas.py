from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from chamados import servico
from chamados.banco import get_db
from chamados.esquemas import (
    Atribuicao, ChamadoCriar, ChamadoSaida, ComentarioCriar, ComentarioSaida, MudancaStatus, Painel, Status,
)
from comum.auth import identidade, token_do_pedido
from comum.tokens import Identidade

router = APIRouter(prefix="/chamados", tags=["Chamados"])


@router.post("", response_model=ChamadoSaida, status_code=201)
def abrir_chamado(dados: ChamadoCriar, quem: Identidade = Depends(identidade), token: str = Depends(token_do_pedido),
                  db: Session = Depends(get_db)):
    return servico.abrir(db, dados, quem, token)


@router.get("", response_model=list[ChamadoSaida])
def listar_chamados(status: Status | None = None, tecnico_id: int | None = None,
                    quem: Identidade = Depends(identidade), db: Session = Depends(get_db)):
    return servico.listar(db, quem, status, tecnico_id)


@router.get("/painel", response_model=Painel)
def painel(quem: Identidade = Depends(identidade), db: Session = Depends(get_db)):
    return servico.painel(db, quem)


@router.get("/{chamado_id}", response_model=ChamadoSaida)
def obter_chamado(chamado_id: int, quem: Identidade = Depends(identidade), db: Session = Depends(get_db)):
    return servico.obter(db, chamado_id, quem)


@router.patch("/{chamado_id}/atribuir", response_model=ChamadoSaida)
def atribuir_chamado(chamado_id: int, dados: Atribuicao, quem: Identidade = Depends(identidade),
                     token: str = Depends(token_do_pedido), db: Session = Depends(get_db)):
    return servico.atribuir(db, chamado_id, dados.tecnico_id, quem, token)


@router.patch("/{chamado_id}/status", response_model=ChamadoSaida)
def mudar_status(chamado_id: int, dados: MudancaStatus, quem: Identidade = Depends(identidade),
                 db: Session = Depends(get_db)):
    return servico.mudar_status(db, chamado_id, dados.status, quem)


@router.post("/{chamado_id}/comentarios", response_model=ComentarioSaida, status_code=201)
def comentar(chamado_id: int, dados: ComentarioCriar, quem: Identidade = Depends(identidade),
             db: Session = Depends(get_db)):
    return servico.comentar(db, chamado_id, dados, quem)
