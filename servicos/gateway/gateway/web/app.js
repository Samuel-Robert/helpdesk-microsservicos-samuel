// Tela do HelpDesk, servida pelo gateway. Todo texto vindo da API passa por esc() antes de ir
// para o HTML, para impedir que um título como <script> seja executado (XSS).
"use strict";
const API = "";  // o gateway serve a tela e a API no mesmo endereço
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (s) => new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const ROTULO = { aberto: "aberto", em_atendimento: "em atendimento", resolvido: "resolvido", fechado: "fechado" };
const PRIORIDADE = { baixa: "baixa", media: "média", alta: "alta", critica: "crítica" };
const PERFIL = { admin: "administrador", tecnico: "técnico", solicitante: "solicitante" };
const SERVICOS = { usuarios: "Usuários", inventario: "Inventário", chamados: "Chamados", notificacoes: "Notificações" };

let token = null, eu = null, usuarios = [], ativos = [], vigia = null;
try { token = sessionStorage.getItem("token"); } catch (e) { token = null; }

async function req(metodo, caminho, corpo) {
  const cab = { "Content-Type": "application/json" };
  if (token) cab.Authorization = "Bearer " + token;
  const r = await fetch(API + caminho, { method: metodo, headers: cab, body: corpo ? JSON.stringify(corpo) : undefined });
  const dados = await r.json().catch(() => ({}));
  if (r.status === 401 && caminho !== "/auth/login") { sair(); throw new Error("Sessão expirada. Entre novamente."); }
  if (!r.ok) {
    const erro = new Error(typeof dados.detail === "string" ? dados.detail : "Dados inválidos (" + r.status + ").");
    erro.rastreio = r.headers.get("X-Request-ID");  // para achar o pedido nos logs: docker compose logs | grep <id>
    throw erro;
  }
  return dados;
}

function avisar(erros) {
  const lista = [].concat(erros).filter(Boolean);
  $("alerta").hidden = lista.length === 0;
  $("erro").textContent = [...new Set(lista.map((e) => e.message))].join(" ");
  const ids = lista.map((e) => e.rastreio).filter(Boolean);
  $("erro-id").textContent = ids.length ? "ID de rastreio: " + ids.join(", ") : "";
}

function guardarToken(t) { token = t; try { t ? sessionStorage.setItem("token", t) : sessionStorage.removeItem("token"); } catch (e) {} }
function sair() { guardarToken(null); eu = null; mostrar(false); }
function mostrar(logado) {
  $("tela-login").hidden = logado; $("tela-sistema").hidden = !logado;
  clearInterval(vigia);
  if (logado) { verServicos(); vigia = setInterval(verServicos, 5000); }
}
const nome = (id) => (usuarios.find((u) => u.id === id) || {}).nome || "—";
const equipe = () => eu && (eu.perfil === "tecnico" || eu.perfil === "admin");

// O painel de serviços: o gateway pergunta a cada um se está no ar (/saude)
async function verServicos() {
  let saude = null;
  try { saude = await (await fetch(API + "/saude")).json(); } catch (e) { saude = null; }
  $("servicos").innerHTML = Object.entries(SERVICOS).map(([chave, rotulo]) => {
    const estado = saude ? (saude.servicos[chave] || "fora do ar") : "gateway sem resposta";
    const classe = estado === "no ar" ? "ok" : estado === "com problemas" ? "atencao" : "fora";
    return `<li class="${classe}"><span class="ponto" aria-hidden="true"></span>${esc(rotulo)}<small>${esc(estado)}</small></li>`;
  }).join("");
}

async function carregar() {
  eu = await req("GET", "/auth/eu");
  $("quem-nome").textContent = eu.nome;
  $("quem-perfil").textContent = PERFIL[eu.perfil] || eu.perfil;
  // Cada parte da tela carrega separada: se um serviço cair, o resto continua aparecendo
  const falhas = [];
  const tentar = (caminho, padrao) => req("GET", caminho).catch((e) => { falhas.push(e); return padrao; });
  const [lista, equipamentos, chamados, painel, avisos] = await Promise.all([
    tentar("/usuarios", null), tentar("/ativos", null), tentar("/chamados", []),
    tentar("/chamados/painel", { total: 0, por_status: {}, atrasados: 0 }), tentar("/notificacoes", []),
  ]);
  // Sem resposta de Usuários ou Inventário, fica a última lista que chegou
  if (lista) usuarios = lista;
  if (equipamentos) ativos = equipamentos;
  const ps = painel.por_status;
  $("kpis").innerHTML = [["Total", painel.total, ""], ["Abertos", ps.aberto || 0, "aberto"], ["Em atendimento", ps.em_atendimento || 0, "andamento"],
    ["Resolvidos", (ps.resolvido || 0) + (ps.fechado || 0), "resolvido"], ["Atrasados", painel.atrasados, "atrasado"]]
    .map(([t, v, c]) => `<div class="kpi ${c}"><small>${esc(t)}</small><b>${esc(v)}</b></div>`).join("");
  const tecnicos = usuarios.filter((u) => u.perfil === "tecnico");
  $("lista").innerHTML = chamados.map((c) => `<tr>
    <td>${esc(c.id)}</td><td><b>${esc(c.titulo)}</b><small>${esc(nome(c.solicitante_id))}</small></td>
    <td class="p-${esc(c.prioridade)}">${esc(PRIORIDADE[c.prioridade])}</td>
    <td><span class="selo s-${esc(c.status)}">${esc(ROTULO[c.status])}</span></td>
    <td>${c.tecnico_id ? esc(nome(c.tecnico_id)) : "—"}</td><td>${esc(fmt(c.prazo_sla))}</td>
    <td><div class="acoes">${acoes(c, tecnicos)}</div></td></tr>`).join("") || `<tr><td colspan="7"><small>Nenhum chamado.</small></td></tr>`;
  $("avisos").innerHTML = avisos.slice().reverse().slice(0, 6).map((a) =>
    `<div class="aviso"><b>${esc(a.tipo)}</b>${esc(a.mensagem)}<small>${esc(fmt(a.criada_em))}</small></div>`).join("") || "<small>Nenhuma notificação.</small>";
  const escolhido = $("ativo").value;
  $("ativo").innerHTML = `<option value="">Nenhum</option>` + ativos.map((a) => `<option value="${esc(a.id)}">${esc(a.patrimonio)} · ${esc(a.descricao)}</option>`).join("");
  $("ativo").value = escolhido;
  avisar(falhas);
}

function acoes(c, tecnicos) {
  const botao = (acao, texto, extra = "") => `<button type="button" data-acao="${acao}" data-id="${esc(c.id)}" ${extra}>${esc(texto)}</button>`;
  if (equipe() && c.status === "aberto")
    return `<select id="t${esc(c.id)}" aria-label="Técnico do chamado ${esc(c.id)}">${tecnicos.map((t) => `<option value="${esc(t.id)}">${esc(t.nome)}</option>`).join("")}</select>` + botao("atribuir", "Atribuir");
  if (equipe() && c.status === "em_atendimento") return botao("resolvido", "Resolver");
  if (c.status === "resolvido" && (equipe() || c.solicitante_id === eu.id))
    return botao("fechado", "Fechar") + botao("em_atendimento", "Reabrir", 'class="sec"');
  return "";
}

async function acao(f) {
  try { await f(); await carregar(); } catch (e) { avisar(e); verServicos(); }
}

$("lista").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-acao]");
  if (!b) return;
  const id = Number(b.dataset.id);
  if (b.dataset.acao === "atribuir") acao(() => req("PATCH", `/chamados/${id}/atribuir`, { tecnico_id: Number($("t" + id).value) }));
  else acao(() => req("PATCH", `/chamados/${id}/status`, { status: b.dataset.acao }));
});

$("novo").addEventListener("submit", (e) => {
  e.preventDefault();
  acao(() => req("POST", "/chamados", {
    titulo: $("titulo").value, descricao: $("descricao").value, prioridade: $("prioridade").value,
    ativo_id: $("ativo").value ? Number($("ativo").value) : null,
  }));
});

$("tela-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("erro-login").textContent = "";
  try {
    const r = await req("POST", "/auth/login", { email: $("email").value, senha: $("senha").value });
    guardarToken(r.access_token); $("senha").value = "";
    mostrar(true); await carregar();
  } catch (err) { $("erro-login").textContent = err.message; }
});

$("sair").addEventListener("click", sair);

if (token) { mostrar(true); carregar().catch(avisar); } else { mostrar(false); }
