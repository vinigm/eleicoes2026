# CLAUDE.md — Eleições 2026 · Presidente 1º × 2º turno

Criado em: 26/10/2026 · Atualizado em: 26/10/2026

Índice e invariantes do projeto. Muda pouco. O retrato do sistema está em [ESTADO.md](ESTADO.md); o que está em aberto, em [PENDENCIAS.md](PENDENCIAS.md), importado abaixo.

---

## Objetivo

- Comparar o **1º turno (04/10/2026)** com o **2º turno (25/10/2026)** da eleição para **presidente**.
- Eixos: **UF**, **região**, **partido/candidato** e **município**.
- **Fora do escopo:** governador, senador, deputados.

## Fonte de verdade (por pergunta)

- **"Quais são os números oficiais?"**
  - 1º turno → dados abertos do TSE (CSV, zips na raiz).
  - 2º turno → JSON de divulgação do TSE (`resultados.tse.jus.br`, eleição `6258`) **enquanto o CSV do 2º turno não sair nos dados abertos**. Quando sair, o CSV vence e a base é reconciliada.
- **"O que a base FAZ hoje?"** → o código em `2026-10-26_base_presidente_1t_2t/` vence.
- **"O que a análise DEVERIA fazer?"** → a decisão mais recente do Vinicius, registrada em PENDENCIAS.
- A diferença entre os dois últimos é ⏳ pendência, não contradição.

## Invariantes

- **Só presidente:** arquivos com sufixo `_BR` nos zips. Os `_BRASIL` têm todos os cargos (3 GB+) — não ler.
- **Unidade comum entre turnos = município.** O JSON do 2º turno não desce a zona/seção.
- **Chave do município:** (`sg_uf`, `cd_municipio_tse`), código TSE como **string de 5 dígitos** com zero à esquerda.
- **`ZZ` = exterior** (186 cidades estrangeiras tratadas como municípios).
- **Âncoras nacionais** — toda base nova tem que bater exatamente:
  - 1º turno: Flávio (22) **56.104.503** · Lula (13) **53.879.538** · válidos **119.300.788** · comparecimento **125.275.835** · aptos **158.745.502**.
  - 2º turno: Lula (13) **64.256.232** · Flávio (22) **59.826.041** · válidos **124.082.273** · comparecimento **128.236.074** · aptos **158.745.502**.
- **Dados baixados são não confiáveis:** scripts nunca ficam na pasta de dados e rodam com `python3 -I`.
- **Código Python** segue `~/.claude/PADRAO-CODIGO-PYTHON.md`.

## Mapa de pastas

- `*.zip` (raiz) → dados abertos do TSE baixados em 26/10/2026. **Não mover nem descompactar em disco.**
- `dados/json_tse/` → JSON de divulgação do TSE (cache bruto da coleta).
- `dados/processados/` → bases geradas (parquet/csv). Regeneráveis.
- `AAAA-MM-DD_descricao/` → scripts de cada etapa, com `README.md` de contexto.
- `docs/` → HTML público (`index.html` + `dados.js`, gerado por `2026-10-26_html_publico/`). Pasta pensada para o GitHub Pages.

## Repositório e publicação

- **Remoto:** https://github.com/vinigm/eleicoes2026 — **público**, criado vazio pelo Vinicius em 26/10/2026. Todo push vai para ele, e só quando o Vinicius pedir.
- **Repositório git local** com remote `origin` = `vinigm/eleicoes2026`, branch `main`. Autor dos commits: nome do Vinicius com o e-mail noreply do GitHub (configurado só neste repo), para não expor o e-mail corporativo.
- **Nunca versionar:** `*.zip` (1,1 GB; arquivo de 452 MB passa do limite de 100 MB do GitHub) e `dados/json_tse/` (milhares de JSONs, regeneráveis pelo script de coleta). Vão para o `.gitignore`.
- **Pode versionar:** scripts, READMEs, docs vivos e `dados/processados/` (~1,7 MB).
- **Repo é público:** nada de caminho local, e-mail ou credencial em arquivo versionado.
- **Página pública:** https://vinigm.github.io/eleicoes2026/ (GitHub Pages servindo `docs/` da branch `main`). Todo push em `docs/` republica a página: confira o HTML localmente antes de enviar.

---

@PENDENCIAS.md
