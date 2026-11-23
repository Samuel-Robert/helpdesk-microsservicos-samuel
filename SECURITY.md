# Segurança

Este projeto é didático, mas segue práticas de segurança reais. A versão em microsserviços mantém
tudo o que o monólito protegia e cuida do que a rede trouxe de novo. Esta página explica o que já
está protegido e o que fica para quem for colocar o sistema em produção.

## O que está protegido

| Risco | Proteção |
|---|---|
| Acesso sem login | **Cada serviço confere o token sozinho** (assinatura, validade, emissor e algoritmo fixos) antes de responder. Só `/auth/login`, `/saude` e a tela não exigem login. |
| Token falsificado | Assinado (HS256) com um segredo único para todos os serviços, vindo do `.env` ou gerado na primeira subida num volume que só os serviços leem. Nunca no código. Tokens `alg: none` são recusados. |
| Senhas vazadas do banco | Só o serviço de Usuários conhece senhas, guardadas como hash **scrypt** com sal aleatório. A senha nunca é salva nem devolvida. |
| Adivinhar senhas | Bloqueio temporário depois de 5 tentativas erradas (por e-mail e endereço), guardado no **Redis**: vale para todas as cópias do serviço de Usuários. Mensagem igual para e-mail inexistente e senha errada. |
| Ver ou mexer no que não é seu | Permissões por perfil em cada serviço: o solicitante só vê os próprios chamados e notificações; só técnicos e administradores atribuem e resolvem; só administradores criam usuários. |
| Agir em nome de outra pessoa | O solicitante e o autor do comentário vêm do token, não do corpo da requisição. Quando Chamados consulta Usuários ou Inventário, **repassa o token do usuário**, que é conferido de novo do outro lado. |
| Usuário desativado | O serviço de Usuários confere no banco a cada pedido: perde o acesso na hora. Nos outros serviços, vale o token até ele vencer (veja abaixo). |
| Descobrir o que existe | Chamado de outra pessoa responde "não encontrado" (404). A lista de usuários não mostra e-mails. |
| Serviços expostos | **Só o gateway publica porta**, e só em `127.0.0.1`. Os serviços, os bancos e o Redis ficam na rede interna do Docker. |
| Cabeçalhos forjados | O gateway só repassa o token, o tipo do conteúdo e o ID de rastreio. O `X-Forwarded-For` é o endereço que ele viu, não o que veio do navegador. Cookies não passam, nem na ida nem na volta. |
| Linhas falsas no log | O ID de rastreio que vem de fora só é aceito com letras, números e hífen; qualquer outro é trocado por um novo. |
| XSS na tela | Todo texto vindo da API é escapado antes de entrar no HTML; não há scripts embutidos na página; a política CSP só permite arquivos do próprio servidor. |
| Clickjacking e outros | `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` em todas as respostas, do gateway e de cada serviço. |
| Dados enormes | Corpo da requisição limitado a 64 KB, barrado já no gateway (e de novo em cada serviço); limites de tamanho em todos os campos. |
| Serviço fora do ar | Tempo limite em toda chamada entre serviços e disjuntor em Chamados: a resposta é um 503 claro, sem travar e sem acumular espera. |
| SQL injection | Acesso ao banco só pelo SQLAlchemy, com parâmetros. |
| Erros que vazam detalhes | Erros de banco respondem com mensagem genérica. |
| Dependências vulneráveis | Versões fixas por serviço, `pip-audit` de cada `requirements.txt` no GitHub Actions a cada envio e Dependabot semanal. |
| Contêiner | Todos rodam sem root, com o sistema de arquivos somente leitura, sem capacidades extras e sem novos privilégios. O contêiner que gera o segredo não tem rede e só recebe a capacidade de entregar o arquivo ao usuário dos serviços. |
| Segredos no código | Só por variável de ambiente (`.env`, fora do Git) ou pelo volume gerado na primeira subida. |

## Antes de usar em produção

- Defina `JWT_SEGREDO` com pelo menos 32 caracteres aleatórios, guardado num cofre de segredos.
- Rode com `DADOS_EXEMPLO=0` (os usuários de exemplo têm senha conhecida) e `DOCS=0`.
- Coloque o gateway atrás de HTTPS (por exemplo, um proxy reverso com certificado).
- Troque o SQLite por um banco gerenciado por serviço (PostgreSQL), com backup.
- Proteja o Redis com senha e mantenha a persistência ligada.
- O perfil dentro do token vale até ele vencer: com `TOKEN_MINUTOS` menor, um usuário desativado ou
  rebaixado perde o acesso mais cedo nos outros serviços.
- Os avisos publicados com o Redis fora do ar se perdem; se isso importar, grave os eventos numa
  tabela de saída (*outbox*) antes de publicar.

## Como relatar um problema

Encontrou uma falha? Não abra uma issue pública: fale diretamente com o autor do repositório.
