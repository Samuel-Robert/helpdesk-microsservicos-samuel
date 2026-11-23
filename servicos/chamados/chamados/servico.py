"""Regras do serviço de Chamados.

As regras são as mesmas do monólito (SLA, transições de status, permissões). O que mudou são
as dependências: o técnico e o equipamento são conferidos pela rede (`clientes`), e os avisos
viraram eventos (`eventos`). Quem chamou vem do token (`Identidade`: id e perfil).

Permissões:
- solicitante: abre chamados e só vê, comenta e fecha os próprios;
- técnico e admin: veem todos, atribuem e mudam o status.
"""
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from chamados import clientes, eventos, repositorio
from chamados.esquemas import ChamadoCriar, ComentarioCriar
from chamados.modelos import Chamado, Comentario
from comum.erros import NaoEncontrado, RegraDeNegocio, SemPermissao
from comum.tokens import Identidade

# Prazo para resolver o chamado, conforme a prioridade (SLA)
HORAS_SLA = {"critica": 4, "alta": 8, "media": 24, "baixa": 72}

# De qual status para quais status um chamado pode ir
TRANSICOES = {
    "aberto": {"em_atendimento"},
    "em_atendimento": {"resolvido"},
    "resolvido": {"fechado", "em_atendimento"},  # reabrir se o problema voltar
    "fechado": set(),
}

EQUIPE = ("tecnico", "admin")


def eh_equipe(quem: Identidade) -> bool:
    return quem.perfil in EQUIPE


def calcular_prazo(prioridade: str, inicio: datetime) -> datetime:
    return inicio + timedelta(hours=HORAS_SLA[prioridade])


def abrir(db: Session, dados: ChamadoCriar, quem: Identidade, token: str) -> Chamado:
    if dados.ativo_id is not None:
        clientes.obter_ativo(dados.ativo_id, token)                  # HTTP: GET /ativos/{id}

    agora = datetime.now()
    chamado = repositorio.salvar(db, Chamado(
        **dados.model_dump(), solicitante_id=quem.id, status="aberto", criado_em=agora,
        prazo_sla=calcular_prazo(dados.prioridade, agora),
    ))
    eventos.publicar(                                                # evento ChamadoAberto
        "ChamadoAberto", quem.id, f"Seu chamado #{chamado.id} foi aberto. Prazo: {chamado.prazo_sla:%d/%m %H:%M}.",
    )
    return chamado


def obter(db: Session, chamado_id: int, quem: Identidade) -> Chamado:
    chamado = repositorio.buscar_por_id(db, chamado_id)
    # Para quem não pode ver, responde "não encontrado": não revela que o chamado existe
    if chamado is None or not (eh_equipe(quem) or chamado.solicitante_id == quem.id):
        raise NaoEncontrado(f"Chamado {chamado_id} não encontrado.")
    return chamado


def listar(db: Session, quem: Identidade, status: str | None = None, tecnico_id: int | None = None) -> list[Chamado]:
    solicitante_id = None if eh_equipe(quem) else quem.id
    return repositorio.listar(db, status, tecnico_id, solicitante_id)


def atribuir(db: Session, chamado_id: int, tecnico_id: int, quem: Identidade, token: str) -> Chamado:
    if not eh_equipe(quem):
        raise SemPermissao("Só técnicos e administradores atribuem chamados.")
    chamado = obter(db, chamado_id, quem)
    if chamado.status in ("resolvido", "fechado"):
        raise RegraDeNegocio("Não é possível atribuir um chamado resolvido ou fechado.")
    tecnico = clientes.obter_tecnico(tecnico_id, token)               # HTTP: GET /usuarios/{id}
    chamado.tecnico_id = tecnico["id"]
    if chamado.status == "aberto":
        chamado.status = "em_atendimento"
    repositorio.salvar(db, chamado)
    eventos.publicar(                                                # evento ChamadoAtribuido
        "ChamadoAtribuido", tecnico["id"], f"O chamado #{chamado.id} foi atribuído a você."
    )
    return chamado


def mudar_status(db: Session, chamado_id: int, novo_status: str, quem: Identidade) -> Chamado:
    chamado = obter(db, chamado_id, quem)
    # O solicitante só pode confirmar (fechar) ou reabrir o próprio chamado resolvido
    pode_solicitante = chamado.status == "resolvido" and novo_status in ("fechado", "em_atendimento")
    if not (eh_equipe(quem) or pode_solicitante):
        raise SemPermissao("Você não pode mudar o status deste chamado.")
    if novo_status not in TRANSICOES[chamado.status]:
        raise RegraDeNegocio(f"Não é possível ir de '{chamado.status}' para '{novo_status}'.")
    if novo_status == "em_atendimento" and chamado.tecnico_id is None:
        raise RegraDeNegocio("Atribua um técnico antes de iniciar o atendimento.")
    chamado.status = novo_status
    repositorio.salvar(db, chamado)
    if novo_status == "resolvido":
        eventos.publicar(                                            # evento ChamadoResolvido
            "ChamadoResolvido", chamado.solicitante_id,
            f"Seu chamado #{chamado.id} foi resolvido. Confirme se está tudo certo.",
        )
    return chamado


def comentar(db: Session, chamado_id: int, dados: ComentarioCriar, quem: Identidade) -> Comentario:
    chamado = obter(db, chamado_id, quem)
    if chamado.status == "fechado":
        raise RegraDeNegocio("Chamados fechados não recebem comentários.")
    return repositorio.salvar_comentario(db, Comentario(
        chamado_id=chamado.id, autor_id=quem.id, texto=dados.texto, criado_em=datetime.now()
    ))


def painel(db: Session, quem: Identidade) -> dict:
    chamados = listar(db, quem)
    agora = datetime.now()
    atrasados = sum(1 for c in chamados if c.status in ("aberto", "em_atendimento") and c.prazo_sla < agora)
    return {"total": len(chamados), "por_status": dict(Counter(c.status for c in chamados)), "atrasados": atrasados}
