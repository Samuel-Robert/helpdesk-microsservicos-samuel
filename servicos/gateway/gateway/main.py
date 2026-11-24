"""API Gateway: o único ponto de entrada do HelpDesk (porta 8000).

Serve a tela e encaminha cada rota ao serviço certo, pelo primeiro trecho do caminho. Não confere
o token: quem confere é cada serviço (requisito 8). O gateway cuida do que é de borda:

- cabeçalhos de segurança e limite de tamanho, antes de qualquer serviço ser incomodado;
- o ID de rastreio, criado aqui e repassado adiante;
- o endereço de quem chamou (X-Forwarded-For), para o limite de login de Usuários;
- um tempo limite por serviço: serviço fora do ar vira 503 com uma mensagem clara;
- /saude: quais serviços estão no ar (a tela mostra).
"""
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from comum.rastreio import CABECALHO, Rastreio, configurar_logs, id_atual, log
from comum.seguranca_http import CabecalhosDeSeguranca

WEB = Path(__file__).parent / "web"
TEMPO_LIMITE = float(os.getenv("TEMPO_LIMITE_SEGUNDOS", "5"))

SERVICOS = {
    "usuarios": os.getenv("USUARIOS_URL", "http://usuarios:8000"),
    "inventario": os.getenv("INVENTARIO_URL", "http://inventario:8000"),
    "chamados": os.getenv("CHAMADOS_URL", "http://chamados:8000"),
    "notificacoes": os.getenv("NOTIFICACOES_URL", "http://notificacoes:8000"),
}
NOMES = {"usuarios": "usuários", "inventario": "inventário", "chamados": "chamados", "notificacoes": "notificações"}

# Qual serviço atende cada rota, pelo primeiro trecho do caminho
ROTAS = {"auth": "usuarios", "usuarios": "usuarios", "ativos": "inventario",
         "chamados": "chamados", "notificacoes": "notificacoes"}

# Só estes cabeçalhos passam adiante; o resto (cookies, por exemplo) fica no gateway
REPASSA_PEDIDO = ("authorization", "content-type", "accept")
REPASSA_RESPOSTA = ("content-type", "www-authenticate", "retry-after")

configurar_logs("gateway")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    # Conexão parada é descartada em 2 s: o uvicorn dos serviços fecha a dele em 5 s, e reaproveitar
    # uma conexão no instante em que ela fecha derruba o pedido (a tela mostrava "fora do ar" à toa)
    app.state.http = httpx.AsyncClient(timeout=TEMPO_LIMITE, limits=httpx.Limits(keepalive_expiry=2))
    log.info("gateway no ar, encaminhando para %s", ", ".join(SERVICOS))
    yield
    await app.state.http.aclose()


app = FastAPI(title="HelpDesk TI · gateway", lifespan=ciclo_de_vida, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CabecalhosDeSeguranca)
app.add_middleware(Rastreio)


@app.get("/", include_in_schema=False)
def tela_inicial():
    return FileResponse(WEB / "index.html")


@app.get("/app.js", include_in_schema=False)
def script():
    return FileResponse(WEB / "app.js", media_type="text/javascript")


@app.get("/estilo.css", include_in_schema=False)
def estilo():
    return FileResponse(WEB / "estilo.css", media_type="text/css")


@app.get("/saude")
async def saude(request: Request):
    """O gateway e cada serviço: no ar, com problemas ou fora do ar (bônus: rota de saúde)."""
    async def ver(nome: str, url: str) -> tuple[str, str]:
        try:
            r = await request.app.state.http.get(f"{url}/saude", timeout=1)
            return nome, "no ar" if r.status_code == 200 else "com problemas"
        except httpx.HTTPError:
            return nome, "fora do ar"

    servicos = dict(await asyncio.gather(*(ver(n, u) for n, u in SERVICOS.items())))
    return {"gateway": "no ar", "servicos": servicos,
            "status": "ok" if all(s == "no ar" for s in servicos.values()) else "parcial"}


@app.api_route("/{caminho:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def encaminhar(caminho: str, request: Request):
    servico = ROTAS.get(caminho.split("/", 1)[0])
    if servico is None:
        return JSONResponse(status_code=404, content={"detail": "Rota não encontrada."})

    cabecalhos = {k: v for k, v in request.headers.items() if k in REPASSA_PEDIDO}
    cabecalhos[CABECALHO] = id_atual.get()
    # Sempre o endereço que o gateway viu: o que vier do navegador nesse cabeçalho é descartado
    cabecalhos["X-Forwarded-For"] = request.client.host if request.client else ""
    try:
        resposta = await request.app.state.http.request(
            request.method, f"{SERVICOS[servico]}/{caminho}", params=request.query_params,
            content=await request.body(), headers=cabecalhos,
        )
    except httpx.HTTPError as erro:
        log.warning("%s não respondeu (%s)", servico, type(erro).__name__)
        return JSONResponse(status_code=503, content={
            "detail": f"O serviço de {NOMES[servico]} está fora do ar. Tente de novo em instantes."})
    return Response(content=resposta.content, status_code=resposta.status_code,
                    headers={k: v for k, v in resposta.headers.items() if k in REPASSA_RESPOSTA})
