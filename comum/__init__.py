"""Biblioteca comum aos serviços do HelpDesk: token, erros, segurança HTTP, rastreio e banco.

Cada serviço copia esta pasta para a própria imagem (veja os Dockerfiles em `servicos/`).
O que se compartilha aqui é só código, nunca dados: nenhum serviço lê o banco de outro.
"""
