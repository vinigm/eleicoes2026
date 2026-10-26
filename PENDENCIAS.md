# PENDENCIAS — fila viva

Atualizado em: 26/10/2026 · Par deste doc: [ESTADO.md](ESTADO.md) · Status: ✅ resolvido · ⏳ em aberto · 🚫 descartado

---

## Vinicius (decide)

- ✅ Migração por região no HTML: incluída com aviso forte de instabilidade (26/10/2026, Vinicius).

- ✅ Redesenho das visualizações (26/10/2026): resultado, saldo, regiões, estados, Sankey, sensibilidade, variação ▲▼, base eleitorado, poda de texto.

- ✅ Abstenção e branco/nulo: botão "votos válidos ↔ todo o eleitorado" nos cartões de resultado, regiões e estados (26/10/2026).

- ✅ Poda de texto e metodologia fora da página; página mais larga, sem rolagem lateral (26/10/2026). Metodologia segue no repositório.

- ✅ Redesenho + migração por estado enviados ao GitHub e publicados (26/10/2026).

- ✅ GitHub Pages ativo (branch `main`, pasta `/docs`): página no ar em https://vinigm.github.io/eleicoes2026/ (26/10/2026).

- ✅ Escopo do HTML: UF + região + migração dos eliminados (26/10/2026).

- ✅ Exterior: entra como 6ª região nos gráficos descritivos e fica fora da migração (26/10/2026, decisão do agente com o Vinicius ausente; revisar).

- 🚫 Cartão "Regiões" separado: removido por redundância com o seletor Regiões | Estados (26/10/2026, Vinicius).

- 🚫 Cartões "De onde veio o crescimento" e "Quanto a estimativa muda conforme o modelo" (sensibilidade): removidos; repetiam a conclusão (26/10/2026, Vinicius).

## Agente (executa)

- ✅ Primeiro push para `vinigm/eleicoes2026` (26/10/2026): README na raiz, autor com e-mail noreply do GitHub, caminhos absolutos trocados por relativos.

- ⏳ Quando o TSE publicar o 2º turno nos dados abertos: trocar a fonte e reconciliar (checar `NR_TURNO=2` no `detalhe_votacao_munzona_2026.zip`).

- ⏳ Robustez da migração: EI hierárquica (King/Rosen) como segunda opinião, ou dados por seção quando o 2º turno sair nos dados abertos.

## TSE (externo)

- ⏳ Publicar o 2º turno nos dados abertos (sem prazo; em 26/10/2026 10:42 ainda não havia).

- ⏳ Publicar o perfil de comparecimento do 2º turno (mostraria quem são os +2,96 mi eleitores a mais).

## Hipóteses a confirmar

- ⏳ Queda de comparecimento nas 9 UFs do Norte e do Nordeste ligada à ausência de 2º turno para governador — requer resultado de governador `6260`.

- ⏳ Branco/nulo do 1º turno → Lula (64–87%): efeito real ou viés de agregação (pobreza)?

- ⏳ Renan Santos → Lula 47% no modelo principal (33% no nacional): provável viés urbano. Conferir com pesquisa que cruze voto 1T × 2T, se alguma for publicada.

- ⏳ Causa da diferença de aptos por município entre turnos (hipótese: voto em trânsito por turno).

---

## Registro cronológico

- **26/10/2026**
  - ✅ Verificação dos zips: só 1º turno; 1º turno bate com o oficial.
  - ✅ 2º turno obtido pelo JSON de divulgação do TSE; base por município 1T+2T certificada (APROVADA).
  - ✅ Primeira leitura por região/UF: única virada em MG; maior avanço de Lula em GO (+9,28 pp).
  - ✅ Repo público `github.com/vinigm/eleicoes2026` registrado (vazio, nada enviado).
  - ✅ Inferência ecológica: A e B idênticas; robusto = bloco e origem do crescimento; candidato individual frágil.
  - ✅ HTML público montado e verificado (desktop, celular, escuro); não publicado.
  - ✅ HTML: seletor de região na migração, com aviso de instabilidade por região e link `#regiao=`.
  - ✅ Primeiro push para o GitHub (52 arquivos + README).
  - ✅ GitHub Pages ativado; página publicada idêntica à local e renderizando sem erro.
  - ✅ Migração por estado (κ = 4, A e B idênticas) + Sankey com filtro Brasil/região/estado.
  - ✅ Página redesenhada (lado a lado, ▲▼, base eleitorado, sem metodologia) enviada ao GitHub.
  - ✅ Página quebrava para quem tinha a versão anterior em cache: `dados.js` passou a ser versionado pelo conteúdo.
  - ✅ Mapas de estados com seletor "Mostrar por: Estados | Regiões".
  - ✅ Conclusão "de onde vieram os votos a mais de Lula" (cascata + virada); certificação independente achou e corrigiu a troca direta Flávio → Lula (E3).
  - ✅ Regiões e estados fundidos (Regiões padrão), ▲▼ nos mapas, dicas na ordem 1º/2º/diferença, legenda dos mapas sem texto.
  - ✅ Virada com rótulos "à frente por" / "puxou"; Sankey por região de quem anulou ou não votou → Lula (Sudeste 42%, Nordeste 31%).
  - ✅ Poda da migração: saíram os cartões de sensibilidade e de crescimento.
  - ✅ Dicas dos mapas, tabelas e resultado em formato de tabela (1º × 2º × diferença).
  - ✅ Dica dos mapas com números absolutos (votos, válidos, compareceram, aptos).
