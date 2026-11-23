"""Usuários de exemplo, criados quando o banco está vazio (só para aula).

Os ids saem nesta ordem (1 a 5) e o serviço de Chamados usa os mesmos nos chamados de exemplo.
Em produção, rode com DADOS_EXEMPLO=0.
"""
import os

from sqlalchemy.orm import Session

from usuarios import servico
from usuarios.esquemas import UsuarioCriar

PESSOAS = [
    ("Admin TI", "admin@empresa.com", "admin"),        # 1
    ("Ana Souza", "ana@empresa.com", "solicitante"),   # 2
    ("Bruno Lima", "bruno@empresa.com", "solicitante"),  # 3
    ("Carla Dias", "carla@empresa.com", "tecnico"),    # 4
    ("Diego Rocha", "diego@empresa.com", "tecnico"),   # 5
]


def carregar(db: Session) -> None:
    if servico.listar(db):
        return
    senha = os.getenv("SENHA_EXEMPLO", "Helpdesk2026")
    for nome, email, perfil in PESSOAS:
        servico.criar(db, UsuarioCriar(nome=nome, email=email, perfil=perfil, senha=senha))
