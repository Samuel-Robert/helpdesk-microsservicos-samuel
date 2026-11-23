"""Equipamentos de exemplo, criados quando o banco está vazio (só para aula).

Os ids saem nesta ordem (1 a 3) e o serviço de Chamados usa os mesmos nos chamados de exemplo.
"""
from sqlalchemy.orm import Session

from inventario import servico
from inventario.esquemas import AtivoCriar

EQUIPAMENTOS = [
    ("PAT-0001", "computador", "Desktop Dell OptiPlex", "Financeiro"),  # 1
    ("PAT-0002", "impressora", "Impressora HP LaserJet", "RH"),         # 2
    ("PAT-0003", "notebook", "Notebook Lenovo ThinkPad", "TI"),         # 3
]


def carregar(db: Session) -> None:
    if servico.listar(db):
        return
    for patrimonio, tipo, descricao, setor in EQUIPAMENTOS:
        servico.criar(db, AtivoCriar(patrimonio=patrimonio, tipo=tipo, descricao=descricao, setor=setor))
