"""Quando Usuários ou Inventário caem: erro claro, sem travar, e o disjuntor."""
import redis

from chamados import clientes, eventos

PUBLICAR_DE_VERDADE = eventos.publicar  # guardada antes de os testes trocarem por uma lista


def test_inventario_fora_do_ar_responde_503_claro(abrir, rede):
    rede.fora_do_ar.add("inventario")
    r = abrir()
    assert r.status_code == 503
    assert r.json()["detail"] == "O serviço de inventário não respondeu. Tente de novo em instantes."


def test_inventario_fora_do_ar_nao_impede_o_resto(cliente, contas, abrir, rede):
    rede.fora_do_ar.add("inventario")
    assert abrir(ativo_id=None).status_code == 201  # chamado sem equipamento não depende do Inventário
    assert cliente.get("/chamados", headers=contas["carla"]).status_code == 200
    assert cliente.get("/chamados/painel", headers=contas["carla"]).status_code == 200


def test_servico_lento_estoura_o_tempo_limite(abrir, rede):
    rede.lentos.add("inventario")
    assert abrir().status_code == 503


def test_usuarios_fora_do_ar_na_atribuicao(cliente, contas, abrir, rede):
    cid = abrir().json()["id"]
    rede.fora_do_ar.add("usuarios")
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"], json={"tecnico_id": 4})
    assert r.status_code == 503 and "usuários" in r.json()["detail"]


def test_disjuntor_abre_depois_de_falhas_seguidas(abrir, rede):
    rede.fora_do_ar.add("inventario")
    for _ in range(clientes.DISJUNTOR_FALHAS):
        abrir()
    tentativas = rede.chamadas_a("inventario")
    r = abrir()
    # aberto: responde na hora, sem nem tentar a rede
    assert r.status_code == 503 and "Nova tentativa em" in r.json()["detail"]
    assert rede.chamadas_a("inventario") == tentativas


def test_disjuntor_fecha_quando_o_servico_volta(abrir, rede):
    rede.fora_do_ar.add("inventario")
    for _ in range(clientes.DISJUNTOR_FALHAS):
        abrir()
    rede.fora_do_ar.clear()
    _, disjuntor = clientes.SERVICOS["inventario"]
    disjuntor.aberto_ate = 0.0  # simula o fim do intervalo
    assert abrir().status_code == 201
    assert disjuntor.falhas == 0


def test_repassa_o_token_e_o_id_de_rastreio(cliente, contas, rede):
    dados = {"titulo": "PC não liga", "descricao": "Nada acontece", "prioridade": "alta", "ativo_id": 1}
    cliente.post("/chamados", headers={**contas["ana"], "X-Request-ID": "pedido-42"}, json=dados)
    pedido = rede.pedidos[-1]
    assert pedido.headers["authorization"] == contas["ana"]["Authorization"]
    assert pedido.headers["x-request-id"] == "pedido-42"


def test_redis_fora_do_ar_nao_impede_abrir_chamado(abrir, monkeypatch):
    class RedisFora:
        def xadd(self, *a, **k):
            raise redis.ConnectionError("Redis fora do ar")
    monkeypatch.setattr(eventos, "publicar", PUBLICAR_DE_VERDADE)  # não a da lista dos outros testes
    monkeypatch.setattr(eventos, "_redis", RedisFora())
    assert abrir().status_code == 201  # o aviso se perde (fica no log), o chamado não
