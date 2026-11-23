"""Chamados de exemplo, criados quando o banco está vazio (só para aula).

Usam os ids dos dados de exemplo dos outros serviços: Ana 2, Bruno 3, Carla 4 (Usuários) e
o desktop 1 e a impressora 2 (Inventário). Não passam pela rede nem publicam eventos: são
gravados direto, porque na primeira subida os outros serviços podem ainda não estar no ar.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from chamados import repositorio
from chamados.modelos import Chamado
from chamados.servico import calcular_prazo

ANA, BRUNO, CARLA = 2, 3, 4
DESKTOP, IMPRESSORA = 1, 2


def carregar(db: Session) -> None:
    if repositorio.listar(db):
        return
    agora = datetime.now()
    for titulo, descricao, prioridade, solicitante, ativo, tecnico in [
        ("Computador não liga", "Apertei o botão e nada acontece.", "alta", ANA, DESKTOP, CARLA),
        ("Impressora atolando papel", "Atola a cada 3 folhas.", "media", BRUNO, IMPRESSORA, None),
        ("Acesso ao sistema de RH", "Preciso de acesso para a nova estagiária.", "baixa", BRUNO, None, None),
    ]:
        repositorio.salvar(db, Chamado(
            titulo=titulo, descricao=descricao, prioridade=prioridade, solicitante_id=solicitante, ativo_id=ativo,
            tecnico_id=tecnico, status="em_atendimento" if tecnico else "aberto",
            criado_em=agora, prazo_sla=calcular_prazo(prioridade, agora),
        ))
