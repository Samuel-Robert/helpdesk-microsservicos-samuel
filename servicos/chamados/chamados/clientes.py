"""Chamadas aos serviços de Usuários e Inventário, pela rede.

No monólito, conferir o técnico e o equipamento era uma chamada de função. Agora é uma
requisição HTTP, que pode demorar ou falhar. Três cuidados:

1. tempo limite: ninguém espera mais que TEMPO_LIMITE segundos por uma resposta;
2. repasse do token e do ID de rastreio: o outro serviço confere o login, e o log liga as pontas;
3. disjuntor (circuit breaker): depois de DISJUNTOR_FALHAS falhas seguidas, para de chamar o
   serviço por DISJUNTOR_SEGUNDOS e responde 503 na hora. Quem usa o sistema não espera o tempo
   limite a cada tentativa, e o serviço que caiu não recebe carga enquanto se recupera.
"""
import os
import threading
import time

import httpx

from comum.erros import NaoEncontrado, RegraDeNegocio, ServicoIndisponivel
from comum.rastreio import CABECALHO, id_atual, log

TEMPO_LIMITE = float(os.getenv("TEMPO_LIMITE_SEGUNDOS", "2"))
DISJUNTOR_FALHAS = int(os.getenv("DISJUNTOR_FALHAS", "3"))
DISJUNTOR_SEGUNDOS = float(os.getenv("DISJUNTOR_SEGUNDOS", "15"))

http = httpx.Client(timeout=TEMPO_LIMITE)  # os testes trocam por um cliente de rede falsa


class Disjuntor:
    """Fechado, as chamadas passam. Aberto, recusa na hora. Vencido o intervalo, deixa passar de novo:
    se der certo, fecha; se falhar, abre outra vez."""
    # ponytail: estado na memória de cada cópia do serviço; com várias cópias, cada uma abre o seu

    def __init__(self, nome: str):
        self.nome = nome
        self.falhas = 0
        self.aberto_ate = 0.0
        self._trava = threading.Lock()

    def conferir(self) -> None:
        with self._trava:
            restante = self.aberto_ate - time.monotonic()
        if restante > 0:
            raise ServicoIndisponivel(
                f"O serviço de {self.nome} está fora do ar. Nova tentativa em {restante:.0f} s."
            )

    def sucesso(self) -> None:
        with self._trava:
            self.falhas, self.aberto_ate = 0, 0.0

    def falha(self) -> None:
        with self._trava:
            self.falhas += 1
            if self.falhas >= DISJUNTOR_FALHAS:
                self.aberto_ate = time.monotonic() + DISJUNTOR_SEGUNDOS
                log.warning("disjuntor de %s aberto por %.0f s, depois de %d falhas", self.nome, DISJUNTOR_SEGUNDOS, self.falhas)


SERVICOS = {
    "usuarios": (os.getenv("USUARIOS_URL", "http://usuarios:8000"), Disjuntor("usuários")),
    "inventario": (os.getenv("INVENTARIO_URL", "http://inventario:8000"), Disjuntor("inventário")),
}


def _consultar(servico: str, caminho: str, token: str) -> dict:
    url, disjuntor = SERVICOS[servico]
    disjuntor.conferir()
    try:
        resposta = http.get(url + caminho, headers={"Authorization": f"Bearer {token}", CABECALHO: id_atual.get()})
    except httpx.TransportError as erro:  # fora do ar, conexão recusada ou tempo limite estourado
        disjuntor.falha()
        log.warning("%s não respondeu (%s)", servico, type(erro).__name__)
        raise ServicoIndisponivel(f"O serviço de {disjuntor.nome} não respondeu. Tente de novo em instantes.") from erro
    if resposta.status_code >= 500:
        disjuntor.falha()
        raise ServicoIndisponivel(f"O serviço de {disjuntor.nome} está com problemas. Tente de novo em instantes.")
    disjuntor.sucesso()
    if resposta.status_code == 404:
        raise NaoEncontrado(resposta.json().get("detail", "Não encontrado."))
    if resposta.status_code != 200:
        raise RegraDeNegocio(f"O serviço de {disjuntor.nome} recusou a consulta ({resposta.status_code}).")
    return resposta.json()


def obter_ativo(ativo_id: int, token: str) -> dict:
    """Era inventario.servico.obter(): agora é GET /ativos/{id} no serviço de Inventário."""
    return _consultar("inventario", f"/ativos/{ativo_id}", token)


def obter_tecnico(usuario_id: int, token: str) -> dict:
    """Era usuarios.servico.obter_tecnico(): agora é GET /usuarios/{id} no serviço de Usuários."""
    usuario = _consultar("usuarios", f"/usuarios/{usuario_id}", token)
    if usuario["perfil"] != "tecnico":
        raise RegraDeNegocio(f"Usuário {usuario_id} não é técnico.")
    return usuario
