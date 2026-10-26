# ESTADO — o que o projeto É hoje

Atualizado em: 26/10/2026 · Par deste doc: [PENDENCIAS.md](PENDENCIAS.md) · Índice: [CLAUDE.md](CLAUDE.md)

---

## O que FAZ

- **Base por município, presidente, 1º e 2º turno** — `dados/processados/presidente_municipio_turnos.parquet` (+ `.csv`).
  - **5.757 linhas** = 5.571 municípios + 186 cidades do exterior (`ZZ`), 34 colunas, com região e **código IBGE**.
  - 1º turno vem dos **dados abertos** (CSV); 2º turno vem do **JSON de divulgação** do TSE (eleição `6258`).
  - Gerada por `2026-10-26_base_presidente_1t_2t/`.
  - **Certificação adversarial APROVADA**, com tolerância zero. CSV do 1º turno = JSON do 1º turno em 109.383 células, então misturar as fontes é seguro.

- **Primeira leitura por região e UF** — `2026-10-26_primeira_leitura_regiao_uf/`.

- **Migração de votos (inferência ecológica)** — `2026-10-26_inferencia_ecologica/`, com método em `ESPECIFICACAO.md`.
  - Regressão de Goodman com restrições, um modelo por região somado no Brasil, bootstrap de 1.000 reamostragens, testes sintéticos.
  - **Duas implementações independentes (A e B) com estimativas idênticas** nas 576 células; veredito em `COMPARACAO_A_B.md`.
  - **Robusto nos 3 modelos:**
    - Flávio cresceu quase só com eleitores dos eliminados (3,3–3,8 mi);
    - Lula recebeu 3,7–4,3 mi dos eliminados e 5,9–6,6 mi de quem anulou ou não votou no 1º turno;
    - o bloco Caiado + Cury + Renan se dividiu 43–46% Lula, 35–38% Flávio e 15–20% branco/nulo.

- **Migração por estado** — `2026-10-26_migracao_por_uf/` (método em `ESPECIFICACAO.md`, veredito em `COMPARACAO_A_B.md`).
  - Cada estado é estimado com os próprios municípios mais os demais estados da região, que entram como se fossem κ = 4 municípios (κ escolhido por validação cruzada).
  - Duas implementações (A e B) com estimativas idênticas nas 2.592 linhas.
  - **Frágil:** 54% das células caem na fronteira 0 ou 1; os IC 95% cobrem só ~88% em teste; o DF é 80% região.

- **HTML público (no ar)** — `docs/index.html` + `docs/dados.js`, gerado por `2026-10-26_html_publico/`.
  - Verificado no Chrome headless: desktop, celular e modo escuro, sem erro no console.
  - Layout (26/10/2026): cartões "1º × 2º turno" lado a lado com variação ▲▼, botão votos válidos ↔ todo o eleitorado, Sankey com filtro Brasil/região/estado. A página não tem mais seção de metodologia (fica no repositório).
  - Perfil das cidades: mapa de calor "região/estado × faixa de habitantes" e dispersão "alfabetização ou PIB per capita × voto" por região (`2026-10-26_indicadores_ibge/`). Estatística conferida de forma independente.
  - Seção "Cidades" no fim: filtro por estado, busca sem acento e lista ordenável das 5.757 cidades, com 1º e 2º turno em % e votos e os habitantes (IBGE 2026). Fonte: `docs/municipios.js`; somas conferidas com o Brasil e com o IBGE.
  - Resumo executivo no topo: 5 big numbers do Brasil (1º turno, 2º turno e variação) e 5 cartões por região.
  - Regiões e estados num cartão só (Regiões é o padrão): só o mapa do 2º turno com ▲▼; os dois turnos e os números absolutos ficam na dica.
  - Conclusão no fim: cascata "de onde vieram os votos a mais" (Lula × Flávio) e a virada.
    - Fato: o ganho de cada finalista e a virada, de −2,22 mi a +4,43 mi.
    - Estimativa: a divisão por origem. 6,09 mi da virada vieram de quem anulou ou não votou; os eliminados deram +0,78 mi líquido a Lula (−0,06 a +0,87 entre os modelos).
    - Estimativa por região: quem anulou ou não votou e foi para Lula veio 42% do Sudeste e 31% do Nordeste. O Sudeste lidera nos 3 modelos; a taxa é maior no Nordeste (84% × 57%).
  - Sem rolagem lateral em 1.440 a 390 px (medido).
  - **No ar em https://vinigm.github.io/eleicoes2026/** (GitHub Pages, branch `main`, pasta `/docs`, desde 26/10/2026).
  - Atualizar a página = regenerar `docs/`, fazer commit e push; o Pages republica sozinho.

## O que NÃO faz (limitações)

- **2º turno não desce abaixo de município.** Zona e seção só quando o TSE publicar o 2º turno nos dados abertos.
- **A divisão por candidato eliminado NÃO é robusta.**
  - Exemplo: Renan → Lula sai 47% no modelo principal e 33% no nacional.
  - No HTML, a fragilidade aparece na dica de cada eliminado na conclusão e na faixa entre os modelos.
- **A migração por região é exibida, mas é instável** (77 de 160 células na fronteira 0 ou 1; n efetivo de 20 a 145 municípios).
  - O HTML mostra, em cada região, um aviso com esses números.
  - O Brasil continua sendo o recorte padrão e o único sem aviso.
- **Branco/nulo do 1º turno → Lula (64–87%)** pode ter viés de agregação (pobreza), comum aos 3 modelos. Hipótese, não verificada.
- **Perfil de comparecimento** (gênero, idade, escolaridade) só existe para o 1º turno.
- **Índices × voto é correlação entre cidades**, não comportamento de eleitor (falácia ecológica). O IDH municipal ficou de fora: o último é de 2010.
- **Aptos por município mudam entre turnos** em 3.779 municípios (saldo zero). Fato do TSE; causa não identificada; impacto por UF ≤ 0,03%.

## PRONTO para fazer

- Cruzamentos com dados do IBGE pelo `cd_municipio_ibge`.

## Maquiagem de visualização

- **Mapa de estados é um mosaico**, não um mapa geográfico: a posição de cada UF é aproximada; no nível Regiões, os blocos são os quadrados das UFs colados (formato aproximado).
- **No HTML, o Sankey e as barras de migração mostram só o modelo principal.** A faixa entre os modelos aparece na dica do mouse e nas faixas da conclusão.
