# Primeira leitura — 1º × 2º turno de presidente por região e UF

Criado em 26/10/2026. Pasta datada: as tabelas são regeneráveis; o contexto abaixo não.

## O que esta leitura respondeu

- Como Lula e Flávio variaram entre os turnos em cada **região** e **UF**.
- De onde veio o crescimento de cada um: votos dos eliminados + mudança de comparecimento.
- Onde o vencedor mudou entre turnos.

## Como rodar

- A partir da raiz do projeto: `python3 -I 2026-10-26_primeira_leitura_regiao_uf/leitura_regiao_uf.py`
- Entrada: `dados/processados/presidente_municipio_turnos.parquet` (base de `2026-10-26_base_presidente_1t_2t/`).
- Saídas nesta pasta: `indicadores_brasil.csv`, `indicadores_regiao.csv`, `indicadores_uf.csv` (`;`, UTF-8).

## Decisões de método

- **Percentuais calculados sobre contagens somadas**, nunca média de percentuais municipais.
- **Percentual de candidato = sobre votos válidos** do turno (padrão TSE).
- **`ganho_lula` / `ganho_flavio` = saldo líquido de votos entre turnos.** Não é transferência individual: o voto é secreto e o mesmo saldo pode esconder trocas de lado.
- **`fatia_ganho_lula_pct`** = ganho de Lula ÷ ganho somado dos dois. Fica vazia quando o ganho somado é negativo (AP, AC, RR) e passa de 100% quando Flávio perdeu votos (AM, MA, TO).
- **Comparecimento % = comparecimento ÷ aptos**, mesma convenção do TSE (dá os **80,78%** oficiais do 2º turno). Aptos incluem os 423 eleitores de seções não instaladas.
- **Comparecimento entre turnos é comparável:** os aptos por UF diferem no máximo **0,03%** entre turnos; total nacional idêntico.
  - Fato (certificação): a diferença está nos dois JSON oficiais do TSE; não é artefato de misturar fontes.
  - Causa não identificada. Hipótese: ajuste de eleitorado por turno (ex.: voto em trânsito).

## Números-âncora (fato, base certificada)

- Brasil + exterior: Lula **45,16% → 51,79%** (+6,62 pp); comparecimento **78,92% → 80,78%**.
- Lula ficou com **73,6%** do saldo de votos novos (+10.376.694 contra +3.721.538 de Flávio).
- **Única UF que virou: MG** (Flávio 48,24% no 1º turno → Lula 50,43% no 2º).
- Maior avanço de Lula: **GO, +9,28 pp**, a UF com mais votos em eliminados (15,34%).
- **Norte foi a única região em que o comparecimento caiu** (−1,81 pp); AP −8,06 pp, RR −6,02 pp, AC −5,65 pp.

## Hipóteses a confirmar (não verificadas)

- Queda de comparecimento no Norte ligada à ausência de 2º turno para governador nessas UFs — precisa do resultado de governador do 2º turno (eleição `6260`), fora da base atual.
- Avanço de Lula em GO ligado a eleitores de Caiado (PSD) — só testável por inferência ecológica município a município.
