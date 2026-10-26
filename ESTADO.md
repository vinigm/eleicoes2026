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

- **HTML público pronto localmente** — `docs/index.html` + `docs/dados.js`, gerado por `2026-10-26_html_publico/`.
  - Verificado no Chrome headless: desktop, celular e modo escuro, sem erro no console.
  - **No ar em https://vinigm.github.io/eleicoes2026/** (GitHub Pages, branch `main`, pasta `/docs`, desde 26/10/2026).
  - Atualizar a página = regenerar `docs/`, fazer commit e push; o Pages republica sozinho.

## O que NÃO faz (limitações)

- **2º turno não desce abaixo de município.** Zona e seção só quando o TSE publicar o 2º turno nos dados abertos.
- **A divisão por candidato eliminado NÃO é robusta.**
  - Exemplo: Renan → Lula sai 47% no modelo principal e 33% no nacional.
  - No HTML aparece marcada como "estimativa frágil".
- **A migração por região é exibida, mas é instável** (77 de 160 células na fronteira 0 ou 1; n efetivo de 20 a 145 municípios).
  - O HTML mostra, em cada região, um aviso com esses números.
  - O Brasil continua sendo o recorte padrão e o único sem aviso.
- **Branco/nulo do 1º turno → Lula (64–87%)** pode ter viés de agregação (pobreza), comum aos 3 modelos. Hipótese, não verificada.
- **Perfil de comparecimento** (gênero, idade, escolaridade) só existe para o 1º turno.
- **Aptos por município mudam entre turnos** em 3.779 municípios (saldo zero). Fato do TSE; causa não identificada; impacto por UF ≤ 0,03%.

## PRONTO para fazer

- Cruzamentos com dados do IBGE pelo `cd_municipio_ibge`.

## Maquiagem de visualização

- **Mapa de estados é um mosaico**, não um mapa geográfico: a posição de cada UF é aproximada.
- **No HTML, as barras de migração mostram só o modelo principal.** A faixa entre os modelos aparece na dica do mouse, nas tabelas e no gráfico de sensibilidade.
