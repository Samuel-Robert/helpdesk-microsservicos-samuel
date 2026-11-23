"""Monta o app FastAPI de um serviço com as peças comuns: segurança, rastreio, erros e /saude."""
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from comum import tokens
from comum.config import DOCS_ATIVA
from comum.erros import registrar_tratadores
from comum.rastreio import Rastreio, configurar_logs, log
from comum.seguranca_http import CabecalhosDeSeguranca


def criar_app(nome: str, routers: list[APIRouter], ao_iniciar: Callable[[], None] | None = None,
              ao_parar: Callable[[], None] | None = None) -> FastAPI:
    configurar_logs(nome)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        tokens.segredo()  # sem segredo o serviço não sobe: falha aqui, com a mensagem, e não no primeiro login
        if ao_iniciar:
            ao_iniciar()
        log.info("serviço de %s no ar", nome)
        yield
        if ao_parar:
            ao_parar()

    app = FastAPI(
        title=f"HelpDesk TI · {nome}", lifespan=ciclo_de_vida,
        docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None,
        openapi_url="/openapi.json" if DOCS_ATIVA else None,
    )
    app.add_middleware(CabecalhosDeSeguranca)
    app.add_middleware(Rastreio)  # por fora: registra até as respostas recusadas pela segurança
    registrar_tratadores(app)
    for router in routers:
        app.include_router(router)

    @app.get("/saude", tags=["Saúde"])
    def saude():
        return {"servico": nome, "status": "ok"}

    return app
