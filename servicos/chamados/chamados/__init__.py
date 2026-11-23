"""Serviço de Chamados: abrir, atribuir, acompanhar e resolver chamados.

Depende de Usuários e Inventário, mas só pela rede (clientes.py), e avisa as outras partes
publicando eventos (eventos.py). Se um deles cair, responde um erro claro em vez de travar.
"""
