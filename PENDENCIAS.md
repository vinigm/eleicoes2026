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

- ⏳ Quando o TSE publicar os votos por candidato do 2º turno (`votacao_candidato_munzona` / `votacao_secao`): trocar a fonte e reconciliar.

- ⏳ Robustez da migração: EI hierárquica (King/Rosen) como segunda opinião, ou dados por seção quando o 2º turno sair nos dados abertos.

## TSE (externo)

- ⏳ Publicar votos por candidato, boletim de urna e logs do 2º turno. O detalhe por seção do 2º turno saiu em 26/10/2026 (~12h35) e bate com as âncoras (em `dados/tse_atualizado_2026-10-26/`).

- ⏳ Votos após as 17h (prorrogação do STF): 34.330 (CNN/setup.news) × 35.521 (levantamento nos logs); conferir quando sair o log das urnas do 2º turno.

- ⏳ Publicar o perfil de comparecimento do 2º turno (mostraria quem são os +2,96 mi eleitores a mais).

## Hipóteses a confirmar

- ⏳ Queda de comparecimento nas 9 UFs do Norte e do Nordeste ligada à ausência de 2º turno para governador — requer resultado de governador `6260`.

- ⏳ Branco/nulo do 1º turno → Lula (64–87%): efeito real ou viés de agregação (pobreza)?

- ⏳ Renan Santos → Lula 47% no modelo principal (33% no nacional): provável viés urbano. Conferir com pesquisa que cruze voto 1T × 2T, se alguma for publicada.

- ⏳ Causa da diferença de aptos por município entre turnos (hipótese: voto em trânsito por turno).

- ✅ "Flávio mais forte nas cidades pequenas do interior" (Vinicius): não se confirma no agregado (43,9% até 50 mil, seu pior tamanho, por peso do Nordeste); só no Sul há sinal leve (26/10/2026).

- ⏳ Religião por município (Censo 2022) como próximo índice da dispersão: confirmar se as tabelas de religião descem a município.

- ⏳ Bairros (levantado pelo Vinicius, não decidido): zona não serve (POA: 10 zonas, 346 locais); caminho = seção → local de votação → bairro/coordenadas (`eleitorado_local_votacao_2026.zip`, 167 MB). Depende do boletim de urna do 2º turno.

- ⏳ Voto por escolaridade (levantado pelo Vinicius, não decidido): só pesquisa mede; estimativa possível = inferência ecológica por seção com `perfil_eleitor_secao_2026` (cadastro: 11,2% com superior, subestimado). Depende do 2º turno por seção.

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
  - ✅ Dicas dos mapas, tabelas e resultado em formato de tabela (1º × 2º × diferença), com números absolutos (votos, válidos, compareceram, aptos).
  - ✅ Regiões e estados enxutos: só o mapa do 2º turno; saíram mapa do 1º, tabelas e base eleitorado do cartão.
  - ✅ Resumo executivo no topo: big numbers do Brasil e cartões por região, com 1º turno, 2º turno e variação.
  - ✅ Mapa com filtros na coluna lateral e aviso de uso; seções na ordem da história; seção Cidades (busca + filtro por estado).
  - ✅ Cidades com 1º/2º turno/variação em % e votos e habitantes (IBGE 2026, soma = Brasil); "virou" em selo vermelho.
  - ✅ Card Lula × Flávio (2º turno) ao lado da busca de cidades e filtro "Lula ganhou / Flávio ganhou" com contagens.
  - ✅ Cidades: botões "mais petista" / "mais bolsonarista" (Brasil: Carnaubeira da Penha 92,3%; Nova Pádua 90,6%).
  - ✅ Cidades: filtro por faixa de habitantes (até 50 mil … mais de 300 mil) aplicado a todo o recorte.
  - ✅ Mapa de calor tamanho × voto e dispersão alfabetização/PIB × voto por região (IBGE; conferência independente aprovada).
  - ✅ Dispersão com pontos neutros, faixas "Flávio venceu / Lula venceu", sem reta de tendência e eixo simétrico; filtros de cidades em painel destacado.
  - ✅ Dispersão: cards Lula × Flávio por painel (depois reduzidos e discretos); legenda e texto do cartão retirados.
  - ✅ Dispersão: filtro de faixa do índice, com seleção múltipla (resto em cinza; cards = votos das cidades das faixas). Cidades: filtro "Virou" (225). Recálculo independente APROVADO.
  - ⏳ Bairros e voto por escolaridade avaliados: viáveis só por seção, após o 2º turno sair nos dados abertos.
  - ✅ Celular (320–768 px): rótulos cortados corrigidos e layout próprio (sem dica flutuante, abas, cidades em ficha curta); 30 → 16 telas.
  - ✅ TSE publicou o detalhe por seção com o 2º turno: comparecimento, aptos e nominais batem com as âncoras; 1º turno inalterado.
  - ✅ Card do recorte das cidades com os votos abreviados embaixo do % (SP 200–300 mil: 1,02 × 1,26 mi; Brasil = âncoras).
