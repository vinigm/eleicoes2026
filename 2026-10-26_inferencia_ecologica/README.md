# Inferência ecológica — migração de votos 1º → 2º turno (presidente 2026)

Criado em 26/10/2026. Implementação **A** da `ESPECIFICACAO.md` (a fonte de verdade do método; esta pasta não a altera).

## O que responde

- Para onde foram, no 2º turno, os eleitores de **Cury (70)**, **Renan Santos (14)** e **Caiado (55)**.
- Lealdade de Lula e Flávio, e em quem votou quem se absteve ou anulou no 1º turno.
- Estimador: regressão de Goodman com restrições (cada linha de β soma 1, células em [0, 1]), ponderada por `aptos_1t`, SLSQP sobre as equações normais `G = XᵀWX`, `H = XᵀWY`.

## Como rodar

```
python3 -I 01_estimar_transferencias.py   # E1, E2, E3 + bootstrap -> transferencias.csv, diagnosticos.md  (~25 s)
python3 -I 02_teste_sintetico.py          # T1, T2 -> teste_sintetico.md                                   (~1 s)
python3 -I testes_unitarios.py            # 59 testes (inclui integração com a base real)
```

- Python 3.14, numpy 2.4, pandas 3.0, scipy 1.17. Nada a instalar.
- Os scripts inserem a própria pasta no `sys.path` (o `-I` a remove); os módulos são `nucleo_inferencia.py` (cálculo puro) e `saidas_inferencia.py` (tabelas e textos).
- Entrada: `../dados/processados/presidente_municipio_turnos.parquet` (5.571 municípios com `fl_exterior == False`).
- Saídas são regeneráveis; nova execução sobrescreve. `transferencias.csv`: `;`, UTF-8, ponto decimal, β com 6 casas e votos com 1.

## Arquivos

- `nucleo_inferencia.py`: montagem de X/Y, âncoras, equações normais, solver, especificações, bootstrap, diagnósticos.
- `saidas_inferencia.py`: `transferencias.csv` e tabelas Markdown.
- `01_estimar_transferencias.py`, `02_teste_sintetico.py`, `testes_unitarios.py`.
- `transferencias.csv` (576 linhas = 3 especificações × 6 regiões/Brasil × 8 × 4), `diagnosticos.md`, `teste_sintetico.md`.

## Números principais (E1, Brasil; IC 95% = variabilidade amostral, **não** inclui o viés da hipótese de constância)

| origem | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| cury | 0,477 [0,368; 0,642] | 0,333 [0,222; 0,404] | 0,189 [0,115; 0,235] | 0,000 [0,000; 0,058] |
| renan | 0,466 [0,340; 0,578] | 0,406 [0,317; 0,509] | 0,114 [0,060; 0,182] | 0,013 [0,000; 0,030] |
| caiado | 0,444 [0,327; 0,519] | 0,416 [0,346; 0,511] | 0,121 [0,080; 0,191] | 0,019 [0,006; 0,036] |

- Lealdade: `lula→lula` 0,992 [0,989; 0,995] · `flavio→flavio` 0,997 [0,993; 0,999].
- Abstenção: `abstencao→lula` 0,068 [0,057; 0,078] · `abstencao→flavio` 0,010 [0,004; 0,017] · `abstencao→abstencao` 0,898.
- **E1 × E2:** diferença máxima nas linhas cury/renan/caiado e nas 4 células de lealdade = **0,333** (`cury→flavio`: E1 0,333 × E2 0,000). Na matriz inteira, 0,572. Sinal forte de viés de agregação no β único nacional.
- **E1 × E3:** 0,1165.

## Teste sintético (`teste_sintetico.md`)

- **T1** (β constante), erro absoluto máximo por linha: E2 ≤ 0,0138 (cury); E1 Brasil ≤ 0,0375 (demais); E1 pior região ≤ 0,2085 (demais, grupo de 0,4% do eleitorado).
- **T2** (Caiado difere no Centro-Oeste), erro do fluxo nacional de Caiado: **E1 0,48%** do grupo (12.374 votos) × **E2 24,38%** (634.087 votos). E1 recupera e E2 enviesa, como esperado.

## Decisões onde a especificação admitia mais de uma leitura

- **N_reg fixo no bootstrap:** os totais por grupo e região são observados; só β é reestimado nas réplicas.
- **E3 com bootstrap** (mesmas multiplicidades de E1/E2), para preencher as colunas de IC.
- **E2 por região:** linhas regionais repetem o β nacional; fluxos = β nacional · N_reg.
- **Total previsto** usa `aptos_2t`; fluxos usam contagens do 1º turno (`aptos_1t`). **R² ponderado** por `aptos_1t` nas três especificações.
- **Solver:** SLSQP, gradiente analítico, restrições de soma por linha e limites [0, 1], mas com **variáveis reescaladas** por `d_r = sqrt(G_rr)` (`cond(G)` ~1e6 → ~5e2 no espaço do solver; mesmo ótimo em β) e `ftol=1e-14` com objetivo ×100 (efetivo 1e-16).
  - Motivo, medido na base real: SLSQP direto com `ftol=1e-12` devolvia β que diferiam até **0,44** conforme o ponto inicial; com a reescala a diferença máxima entre 6 pontos iniciais é 8e-6.
  - Todo ajuste exige `success` do SLSQP, viabilidade (soma e limites a 1e-8) e **lacuna de dualidade de Frank-Wolfe ≤ 1e-7** (limite superior comprovado de objetivo − ótimo). Falha = exceção. Lacuna máxima observada: 2e-9 (pontual).
- **Bootstrap:** contagens `Multinomial(n_reg, 1/n_reg)` por região (equivale a reamostrar com reposição dentro da região), semente `20261025`, B = 1.000, ponto inicial = β pontual. Zero falhas de convergência em 11.000 ajustes.

## Alertas

- `cond(G)` (sem reescala): pontual até **1,7e6** (Nordeste, E3; E1 1,5e6), nas réplicas até **2,6e6** (E1); sempre finito, ou seja, `G` é definida positiva e o ótimo é único, mas grupos pequenos (`demais`, cury, renan, caiado) são pouco identificados.
- **Fronteira:** E1 tem 77 células de β em 0 ou 1 (de 160), E2 20 (de 32), E3 70. Quase todas em `demais`, abstenção como destino de cury/renan/caiado e em lula↔flavio.
- **Concentrações regionais extremas em E1** (β ≥ 0,8 em cury/renan/caiado): Nordeste `renan→lula` 0,928 [0,763; 1,000], Norte `cury→lula` 0,885 [0,323; 1,000], Norte `caiado→branco_nulo` 0,872 [0,538; 1,000]. Tratar como instabilidade de grupo pequeno, não como preferência.
- **IC percentil na fronteira:** com o estimador restrito, quando o ponto está em 0 ou 1 o percentil 2,5 ou 97,5 coincide com a fronteira e o IC fica de um lado só.
- **E2 degenerado:** o β nacional tem `lula→lula = flavio→flavio = 1` e `cury→flavio = 0`. O ajuste nacional ignora que o comportamento difere por região (no T2, E2 copia o β de Caiado do Centro-Oeste para o país inteiro).
- **Diagnóstico de ajuste (E1, Brasil):** R² de `lula` 0,9935 e `flavio` 0,9940, mas `branco_nulo` só 0,652 e `abstencao` 0,827. O total previsto de `branco_nulo` fica 0,71% abaixo do real.
