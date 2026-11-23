"""O fluxo de um chamado: as mesmas regras do monólito, agora com as conferências pela rede."""
from datetime import datetime

from chamados.modelos import Chamado, Comentario


def test_abrir_calcula_sla_e_publica_evento(abrir, publicados):
    r = abrir(prioridade="critica")
    assert r.status_code == 201
    c = r.json()
    assert c["solicitante_id"] == 2
    horas = (datetime.fromisoformat(c["prazo_sla"]) - datetime.fromisoformat(c["criado_em"])).total_seconds() / 3600
    assert round(horas) == 4
    assert publicados == [("ChamadoAberto", 2)]


def test_abrir_confere_o_equipamento_no_inventario(abrir, rede):
    assert abrir().status_code == 201
    assert rede.chamadas_a("inventario") == 1


def test_abrir_com_ativo_inexistente(abrir):
    r = abrir(ativo_id=999)
    assert r.status_code == 404 and "não encontrado" in r.json()["detail"]


def test_abrir_sem_equipamento_nao_chama_o_inventario(abrir, rede):
    assert abrir(ativo_id=None).status_code == 201
    assert rede.chamadas_a("inventario") == 0


def test_atribuir_confere_o_tecnico_e_publica_evento(cliente, contas, abrir, rede, publicados):
    cid = abrir().json()["id"]
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"], json={"tecnico_id": 4})
    assert r.json()["status"] == "em_atendimento" and r.json()["tecnico_id"] == 4
    assert rede.chamadas_a("usuarios") == 1
    assert publicados[-1] == ("ChamadoAtribuido", 4)


def test_so_tecnico_pode_ser_atribuido(cliente, contas, abrir):
    cid = abrir().json()["id"]
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"], json={"tecnico_id": 2})
    assert r.status_code == 422 and r.json()["detail"] == "Usuário 2 não é técnico."


def test_tecnico_inexistente(cliente, contas, abrir):
    cid = abrir().json()["id"]
    assert cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"], json={"tecnico_id": 99}).status_code == 404


def test_fluxo_completo_de_status(cliente, contas, abrir, publicados):
    cid = abrir().json()["id"]
    cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"], json={"tecnico_id": 4})
    assert cliente.patch(f"/chamados/{cid}/status", headers=contas["carla"], json={"status": "resolvido"}).status_code == 200
    assert publicados[-1] == ("ChamadoResolvido", 2)
    # a própria solicitante confirma e fecha
    r = cliente.patch(f"/chamados/{cid}/status", headers=contas["ana"], json={"status": "fechado"})
    assert r.json()["status"] == "fechado"


def test_transicao_invalida(cliente, contas, abrir):
    cid = abrir().json()["id"]
    assert cliente.patch(f"/chamados/{cid}/status", headers=contas["carla"], json={"status": "fechado"}).status_code == 422


def test_iniciar_atendimento_sem_tecnico(cliente, contas, abrir):
    cid = abrir().json()["id"]
    r = cliente.patch(f"/chamados/{cid}/status", headers=contas["carla"], json={"status": "em_atendimento"})
    assert r.status_code == 422


def test_comentar_usa_o_usuario_logado(cliente, contas, abrir):
    cid = abrir().json()["id"]
    r = cliente.post(f"/chamados/{cid}/comentarios", headers=contas["carla"], json={"texto": "Verificando a fonte."})
    assert r.status_code == 201 and r.json()["autor_id"] == 4
    assert len(cliente.get(f"/chamados/{cid}", headers=contas["ana"]).json()["comentarios"]) == 1


def test_painel(cliente, contas, abrir):
    abrir()
    abrir(prioridade="baixa")
    p = cliente.get("/chamados/painel", headers=contas["carla"]).json()
    assert p["total"] == 2 and p["por_status"] == {"aberto": 2}


def test_sem_chave_estrangeira_para_outros_servicos():
    """Requisito 2: nenhuma tabela aponta para tabelas de Usuários ou Inventário."""
    alvos = {fk.column.table.name for tabela in (Chamado.__table__, Comentario.__table__) for fk in tabela.foreign_keys}
    assert alvos == {"chamados"}
