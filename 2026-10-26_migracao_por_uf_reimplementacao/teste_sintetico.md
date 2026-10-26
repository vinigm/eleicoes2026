# Teste sintético do método por UF (implementação B)

X real; `Y_i ~ Multinomial(aptos_1t_i, X_i beta_u)` e `Y_i = contagens/aptos_1t_i`. `beta_regiao` = T1 da especificação regional (igual em todas as regiões). `beta_u` = T1 com `lula += delta_u`, `flavio -= delta_u` nas linhas caiado, cury e renan, `delta_u ~ U[-0,15; +0,15]` (um por UF, UFs em ordem alfabética). Erro = média dos |beta_estimado - beta_verdadeiro| nas 4 colunas, ponderada por `N_u[r]` sobre as 27 UFs e as 3 linhas.

## Semente principal 20261025

| versão | erro médio absoluto ponderado |
|---|---|
| (a) UF, kappa* = 0.25 (CV nos dados sintéticos) | **0.04700** |
| (b) UF_SOZINHO (kappa = 0,25) | **0.04700** |
| (c) UF_REGIAO (kappa = inf) | **0.09064** |
| referência: usar a T1 exata da região em todas as UFs | 0.03327 |

**Esperado (a) <= min((b), (c)): SIM.** KKT máximo (CV + ajustes): 1.11e-13.

Erro por linha (a / b / c):

| linha | (a) | (b) | (c) |
|---|---|---|---|
| caiado | 0.03460 | 0.03460 | 0.12630 |
| cury | 0.03795 | 0.03795 | 0.06804 |
| renan | 0.07074 | 0.07074 | 0.08502 |

## Robustez (outras sementes, mesmo procedimento)

| semente | kappa* | (a) | (b) | (c) | (a) <= min(b, c)? |
|---|---|---|---|---|---|
| 20261025 | 0.25 | 0.04700 | 0.04700 | 0.09064 | sim |
| 20261026 | 0.5 | 0.04207 | 0.03883 | 0.10551 | NÃO |
| 20261027 | 0.25 | 0.04855 | 0.04855 | 0.11170 | sim |
| 20261028 | 0.25 | 0.04440 | 0.04440 | 0.09929 | sim |
| 20261029 | 0.5 | 0.03977 | 0.03802 | 0.07233 | NÃO |
| 20261030 | 0.25 | 0.04441 | 0.04441 | 0.11706 | sim |

(a) <= min((b), (c)) em 4 de 6 sementes.

## Cobertura do IC do bootstrap (semente 20261025, B = 300, kappa fixo)

- beta verdadeiro dentro do IC 95%: **87.7%** das células das linhas caiado/cury/renan; 85.8% nas colunas lula/flavio dessas linhas; 89.0% em todas as 32 células.
- O IC mede só variabilidade amostral; o viés de encolhimento para a região não entra.
