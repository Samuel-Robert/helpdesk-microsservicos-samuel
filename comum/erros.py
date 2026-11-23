"""Erros de negócio comuns aos serviços e a resposta HTTP de cada um."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class NaoEncontrado(Exception):
    """O recurso pedido não existe (ou o usuário não pode vê-lo)."""


class RegraDeNegocio(Exception):
    """A operação viola uma regra do sistema."""


class SemPermissao(Exception):
    """O usuário está logado, mas não pode fazer esta operação."""


class ServicoIndisponivel(Exception):
    """Outro serviço não respondeu a tempo ou está fora do ar."""


STATUS = {NaoEncontrado: 404, RegraDeNegocio: 422, SemPermissao: 403, ServicoIndisponivel: 503}


def registrar_tratadores(app: FastAPI) -> None:
    for erro, codigo in STATUS.items():
        def tratar(request: Request, e: Exception, codigo: int = codigo):
            return JSONResponse(status_code=codigo, content={"detail": str(e)})
        app.add_exception_handler(erro, tratar)

    def conflito(request: Request, e: IntegrityError):
        # Não expõe detalhes do banco na resposta
        return JSONResponse(status_code=409, content={"detail": "O registro conflita com outro já existente."})
    app.add_exception_handler(IntegrityError, conflito)
