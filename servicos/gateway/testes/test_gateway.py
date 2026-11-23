from pathlib import Path

import pytest

LOGIN = {"Authorization": "Bearer qualquer"}  # quem confere o token é o serviço, não o gateway


@pytest.mark.parametrize("rota, servico", [
    ("/auth/login", "usuarios"), ("/usuarios", "usuarios"), ("/ativos/1", "inventario"),
    ("/chamados/painel", "chamados"), ("/notificacoes", "notificacoes"),
])
def test_cada_rota_vai_para_o_servico_certo(cliente, rota, servico):
    assert cliente.get(rota, headers=LOGIN).json() == {"servico": servico, "caminho": rota}


def test_repassa_token_rastreio_e_corpo(cliente, servicos):
    cliente.post("/chamados", headers={**LOGIN, "X-Request-ID": "pedido-7"}, json={"titulo": "x"})
    pedido = servicos.pedidos[-1]
    assert pedido.method == "POST" and pedido.content == b'{"titulo":"x"}'
    assert pedido.headers["authorization"] == "Bearer qualquer"
    assert pedido.headers["x-request-id"] == "pedido-7"


def test_repassa_os_filtros_da_rota(cliente, servicos):
    cliente.get("/ativos", headers=LOGIN, params={"setor": "RH"})
    assert servicos.pedidos[-1].url.params["setor"] == "RH"


def test_nao_repassa_cookies_nem_endereco_forjado(cliente, servicos):
    cliente.get("/chamados", headers={**LOGIN, "Cookie": "sessao=1", "X-Forwarded-For": "1.2.3.4"})
    pedido = servicos.pedidos[-1]
    assert "cookie" not in pedido.headers
    assert pedido.headers["x-forwarded-for"] != "1.2.3.4"  # vale o endereço que o gateway viu


def test_nao_devolve_cabecalhos_internos(cliente):
    r = cliente.get("/chamados", headers=LOGIN)
    assert "set-cookie" not in r.headers and "x-interno" not in r.headers


def test_a_resposta_do_servico_passa_como_veio(cliente):
    r = cliente.get("/chamados")  # sem token: o serviço responde 401 e o gateway não muda nada
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


def test_servico_fora_do_ar_vira_503_claro(cliente, servicos):
    servicos.fora_do_ar.add("inventario")
    r = cliente.get("/ativos", headers=LOGIN)
    assert r.status_code == 503
    assert r.json()["detail"] == "O serviço de inventário está fora do ar. Tente de novo em instantes."
    assert cliente.get("/chamados", headers=LOGIN).status_code == 200  # o resto segue


def test_rota_desconhecida(cliente, servicos):
    assert cliente.get("/admin/segredos").status_code == 404
    assert servicos.pedidos == []  # nem chega aos serviços


def test_saude_mostra_cada_servico(cliente, servicos):
    servicos.fora_do_ar.add("inventario")
    r = cliente.get("/saude").json()
    assert r["status"] == "parcial"
    assert r["servicos"] == {"usuarios": "no ar", "inventario": "fora do ar", "chamados": "no ar", "notificacoes": "no ar"}


def test_requisicao_grande_demais_para_no_gateway(cliente, servicos):
    corpo = '{"titulo": "' + "x" * 70000 + '"}'
    r = cliente.post("/chamados", headers={**LOGIN, "Content-Type": "application/json"}, content=corpo)
    assert r.status_code == 413 and servicos.pedidos == []


def test_cabecalhos_de_seguranca_na_tela(cliente):
    r = cliente.get("/")
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_tela_escapa_o_html():
    js = (Path(__file__).parent.parent / "gateway" / "web" / "app.js").read_text(encoding="utf-8")
    assert "const esc =" in js and "onclick" not in js
