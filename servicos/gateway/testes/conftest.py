"""Testes do gateway com os serviços simulados: cada pedido encaminhado fica guardado."""
import httpx
import pytest
from fastapi.testclient import TestClient

from gateway.main import app


class ServicosFalsos:
    def __init__(self):
        self.fora_do_ar: set[str] = set()
        self.pedidos: list[httpx.Request] = []

    def responder(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        if pedido.url.host in self.fora_do_ar:
            raise httpx.ConnectError("conexão recusada", request=pedido)
        if pedido.url.path == "/saude":
            return httpx.Response(200, json={"status": "ok"})
        if "authorization" not in pedido.headers:
            return httpx.Response(401, json={"detail": "Faça login para continuar."}, headers={"WWW-Authenticate": "Bearer"})
        return httpx.Response(200, json={"servico": pedido.url.host, "caminho": pedido.url.path},
                              headers={"Set-Cookie": "rastro=1", "X-Interno": "nao-vaza"})


@pytest.fixture
def servicos():
    return ServicosFalsos()


@pytest.fixture
def cliente(servicos):
    with TestClient(app) as c:
        app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(servicos.responder))
        yield c
