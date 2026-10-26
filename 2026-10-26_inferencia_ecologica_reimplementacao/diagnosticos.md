# Diagnósticos — reimplementação B

> O IC (bootstrap) mede apenas a variabilidade amostral; NAO captura o viés da hipótese de constância de comportamento dentro da região.

## 0. Âncoras da seção 4

| âncora | esperado | calculado | status |
|---|---|---|---|
| municipios | 5.571 | 5.571 | PASS |
| municipios_Centro-Oeste | 468 | 468 | PASS |
| municipios_Nordeste | 1.794 | 1.794 | PASS |
| municipios_Norte | 450 | 450 | PASS |
| municipios_Sudeste | 1.668 | 1.668 | PASS |
| municipios_Sul | 1.191 | 1.191 | PASS |
| 1t_lula | 53.722.151 | 53.722.151 | PASS |
| 1t_flavio | 55.960.603 | 55.960.603 | PASS |
| 1t_cury | 3.438.835 | 3.438.835 | PASS |
| 1t_renan | 2.667.307 | 2.667.307 | PASS |
| 1t_caiado | 2.600.440 | 2.600.440 | PASS |
| 1t_demais | 580.570 | 580.570 | PASS |
| 1t_branco_nulo | 5.964.163 | 5.964.163 | PASS |
| 1t_abstencao | 32.894.899 | 32.894.899 | PASS |
| 1t_aptos | 157.828.968 | 157.828.968 | PASS |
| 2t_lula | 64.056.078 | 64.056.078 | PASS |
| 2t_flavio | 59.654.544 | 59.654.544 | PASS |
| 2t_branco_nulo | 4.144.009 | 4.144.009 | PASS |
| 2t_abstencao | 29.974.188 | 29.974.188 | PASS |
| 2t_aptos | 157.828.819 | 157.828.819 | PASS |

Identidade por município (soma das categorias de origem = aptos_1t; soma das de destino = aptos_2t): 0 violações em 5.571.

## 1. Solver, condicionamento, KKT e identificabilidade

Solver: FISTA com reinício adaptativo, passo 1/L (L = 2 lambda_max(G)), projeção exata de cada linha de beta no simplex (Duchi et al., 2008). Parada: variação relativa do objetivo E da solução <= 1e-12 entre iterações consecutivas. G é montada com pesos normalizados (soma 1); o número de condição é invariante à escala. KKT: suporte = beta > 1e-10; violação relativa = violação absoluta / (2 max|H|). `max abs dbeta (8 inícios)` = maior diferença de beta entre a solução principal (início uniforme) e soluções partindo de 8 pontos iniciais (uniforme, 4 vértices, 3 Dirichlet), com tolerância 1e-12 e com 1e-14. `cota` = sqrt(dobj/lambda_min): como G é definida positiva, f(b) - f(b*) >= lambda_min ||b - b*||^2, então a diferença de objetivo entre duas soluções limita a distância entre elas (dobj é limitado por baixo pelo ruído de ponto flutuante, eps*objetivo).

### E1

| ajuste | lambda_min(G) | lambda_max(G) | cond(G) | iter. | objetivo | KKT abs. | KKT rel. | res. grad. proj. | max abs dbeta (8 inícios, tol 1e-12) | max abs dobj (8 inícios) | cota sqrt(dobj/lambda_min) | max abs dbeta (8 inícios, tol 1e-14) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Centro-Oeste | 3.170e-07 | 2.956e-01 | 9.328e+05 | 7096 | 2.7270466859e-04 | 8.36e-13 | 2.06e-12 | 1.41e-12 | 5.35e-08 | 4.44e-16 | 3.74e-05 | 2.89e-10 |
| Nordeste | 2.192e-07 | 3.387e-01 | 1.545e+06 | 7106 | 6.1885703855e-04 | 2.54e-13 | 4.49e-13 | 3.75e-13 | 2.77e-08 | 6.11e-16 | 5.28e-05 | 2.31e-10 |
| Norte | 2.192e-07 | 3.063e-01 | 1.397e+06 | 4746 | 1.4176690098e-03 | 2.35e-13 | 7.36e-13 | 3.83e-13 | 1.33e-08 | 3.33e-16 | 3.90e-05 | 1.87e-11 |
| Sudeste | 4.323e-06 | 2.798e-01 | 6.474e+04 | 5195 | 2.0782949939e-04 | 2.71e-13 | 8.65e-13 | 4.85e-13 | 3.79e-08 | 5.55e-16 | 1.13e-05 | 3.09e-10 |
| Sul | 1.155e-06 | 3.144e-01 | 2.722e+05 | 8924 | 1.5451986891e-04 | 3.98e-14 | 8.40e-14 | 6.32e-14 | 4.19e-08 | 2.22e-16 | 1.39e-05 | 1.95e-09 |

### E2

| ajuste | lambda_min(G) | lambda_max(G) | cond(G) | iter. | objetivo | KKT abs. | KKT rel. | res. grad. proj. | max abs dbeta (8 inícios, tol 1e-12) | max abs dobj (8 inícios) | cota sqrt(dobj/lambda_min) | max abs dbeta (8 inícios, tol 1e-14) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Brasil (nacional) | 3.074e-06 | 2.878e-01 | 9.360e+04 | 3372 | 6.4533615083e-04 | 1.88e-13 | 6.16e-13 | 3.27e-13 | 3.03e-09 | 6.11e-16 | 1.41e-05 | 1.02e-11 |

### E3

| ajuste | lambda_min(G) | lambda_max(G) | cond(G) | iter. | objetivo | KKT abs. | KKT rel. | res. grad. proj. | max abs dbeta (8 inícios, tol 1e-12) | max abs dobj (8 inícios) | cota sqrt(dobj/lambda_min) | max abs dbeta (8 inícios, tol 1e-14) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Centro-Oeste | 4.002e-07 | 2.961e-01 | 7.401e+05 | 7902 | 6.1382730050e-04 | 1.56e-13 | 3.99e-13 | 2.63e-13 | 6.19e-08 | 3.89e-16 | 3.12e-05 | 2.11e-10 |
| Nordeste | 2.229e-07 | 3.690e-01 | 1.656e+06 | 24769 | 9.2715488018e-04 | 1.71e-13 | 2.64e-13 | 2.32e-13 | 2.53e-06 | 5.00e-16 | 4.73e-05 | 1.67e-08 |
| Norte | 2.689e-07 | 3.110e-01 | 1.156e+06 | 9625 | 2.2890647363e-03 | 2.00e-15 | 6.30e-15 | 3.22e-15 | 8.02e-09 | 5.55e-16 | 4.54e-05 | 1.48e-09 |
| Sudeste | 5.091e-06 | 2.888e-01 | 5.674e+04 | 5180 | 3.7095691304e-04 | 5.42e-13 | 1.68e-12 | 9.37e-13 | 6.49e-08 | 3.89e-16 | 8.74e-06 | 7.51e-11 |
| Sul | 1.045e-06 | 3.311e-01 | 3.168e+05 | 5017 | 2.6347347324e-04 | 9.26e-14 | 1.80e-13 | 1.40e-13 | 1.35e-08 | 7.77e-16 | 2.73e-05 | 4.13e-10 |

**Resumo.** Maior cond(G) entre os ajustes pontuais: **1.656e+06**. Maior violação KKT: **8.36e-13** (absoluta), **2.06e-12** (relativa). Todos convergiram pelo critério de parada: **True**. Maior |dbeta| entre inícios distintos: **2.53e-06** (tol 1e-12) e **1.67e-08** (tol 1e-14); maior |dobjetivo|: **7.77e-16** (ruído de ponto flutuante). Todas as diferenças de beta dentro da cota sqrt(dobj/lambda_min): **True**.

**Identificabilidade.** G é definida positiva em todos os ajustes (lambda_min > 0), logo o ótimo é único. cond(G) elevada (~1e5 a 1e6) significa que direções do espaço de beta quase não são informadas pelos dados: o ponto é único, mas a precisão estatística em grupos pequenos (cury, renan, caiado, demais) é baixa — ver os IC. Os 8 inícios chegam ao mesmo objetivo (diferença no nível do ruído de ponto flutuante) e a betas que diferem só no resíduo de convergência: a diferença de beta cai quando a tolerância passa de 1e-12 para 1e-14 e fica dentro da cota teórica. NÃO há não identificabilidade: ótimo único.

## 2. Bootstrap

| espec. | réplicas | ajustes não convergidos (somando unidades) | iterações máx. | KKT rel. máx. nas réplicas |
|---|---|---|---|---|
| E1 | 1000 | 0 | 21263 | 4.02e-12 |
| E2 | 1000 | 0 | 5493 | 3.16e-12 |
| E3 | 1000 | 0 | 23597 | 3.74e-12 |

Reamostragem estratificada por região, B = 1000, `numpy.random.default_rng(20261025)`; as mesmas réplicas são usadas em E1, E2 e E3. Partida a quente a partir do ponto estimado (teto de 60000 iterações). IC por percentis 2,5 e 97,5. Fluxo em votos: usa N_reg observado (fixo) — ver crítica C3.

## 3. E1 — ajuste, R2, fronteira e plausibilidade

**Total previsto x real do 2º turno (votos).** `previsto = soma_i aptos_*_i * (X_i beta)_c`.

| regiao | destino | previsto (aptos_2t) | previsto (aptos_1t) | real | dif. % (aptos_2t) | dif. % (aptos_1t) |
|---|---|---|---|---|---|---|
| Centro-Oeste | lula | 3.734.347 | 3.734.149 | 3.733.919 | +0.0115 | +0.0062 |
| Centro-Oeste | flavio | 5.603.935 | 5.603.691 | 5.603.867 | +0.0012 | -0.0031 |
| Centro-Oeste | branco_nulo | 256.192 | 256.179 | 257.568 | -0.5343 | -0.5391 |
| Centro-Oeste | abstencao | 2.407.222 | 2.407.122 | 2.406.342 | +0.0366 | +0.0324 |
| Nordeste | lula | 24.449.076 | 24.449.221 | 24.450.432 | -0.0055 | -0.0050 |
| Nordeste | flavio | 10.796.184 | 10.796.369 | 10.796.736 | -0.0051 | -0.0034 |
| Nordeste | branco_nulo | 1.078.081 | 1.078.092 | 1.088.464 | -0.9539 | -0.9529 |
| Nordeste | abstencao | 7.187.517 | 7.187.555 | 7.175.226 | +0.1713 | +0.1718 |
| Norte | lula | 5.024.916 | 5.025.031 | 5.024.626 | +0.0058 | +0.0081 |
| Norte | flavio | 5.034.596 | 5.034.752 | 5.023.547 | +0.2199 | +0.2230 |
| Norte | branco_nulo | 262.658 | 262.669 | 268.937 | -2.3346 | -2.3306 |
| Norte | abstencao | 2.778.686 | 2.778.724 | 2.783.746 | -0.1818 | -0.1804 |
| Sudeste | lula | 24.045.055 | 24.044.916 | 24.037.731 | +0.0305 | +0.0299 |
| Sudeste | flavio | 26.847.385 | 26.847.367 | 26.844.501 | +0.0107 | +0.0107 |
| Sudeste | branco_nulo | 2.003.803 | 2.003.792 | 2.013.023 | -0.4580 | -0.4586 |
| Sudeste | abstencao | 13.448.533 | 13.448.487 | 13.449.521 | -0.0073 | -0.0077 |
| Sul | lula | 6.816.206 | 6.816.321 | 6.809.370 | +0.1004 | +0.1021 |
| Sul | flavio | 11.380.223 | 11.380.276 | 11.385.893 | -0.0498 | -0.0493 |
| Sul | branco_nulo | 513.943 | 513.949 | 516.017 | -0.4019 | -0.4008 |
| Sul | abstencao | 4.160.261 | 4.160.307 | 4.159.353 | +0.0218 | +0.0229 |
| Brasil | lula | 64.069.601 | 64.069.637 | 64.056.078 | +0.0211 | +0.0212 |
| Brasil | flavio | 59.662.323 | 59.662.455 | 59.654.544 | +0.0130 | +0.0133 |
| Brasil | branco_nulo | 4.114.678 | 4.114.681 | 4.144.009 | -0.7078 | -0.7077 |
| Brasil | abstencao | 29.982.218 | 29.982.194 | 29.974.188 | +0.0268 | +0.0267 |

**R2 ponderado por destino (peso = aptos_1t).**

| regiao | R2 lula | R2 flavio | R2 branco_nulo | R2 abstencao |
|---|---|---|---|---|
| Centro-Oeste | 0.9811 | 0.9811 | 0.7561 | 0.8465 |
| Nordeste | 0.9711 | 0.9890 | 0.3918 | 0.7154 |
| Norte | 0.9836 | 0.9778 | 0.3236 | 0.5772 |
| Sudeste | 0.9867 | 0.9869 | 0.5656 | 0.8816 |
| Sul | 0.9893 | 0.9938 | 0.7317 | 0.9441 |

**Células de beta na fronteira (0 ou 1), ajuste pontual.**

| unidade | # em 0 | células em 0 | # em 1 | células em 1 |
|---|---|---|---|---|
| Centro-Oeste | 13 | lula->flavio, lula->branco_nulo, lula->abstencao, flavio->lula, flavio->branco_nulo, flavio->abstencao, cury->abstencao, renan->abstencao, demais->lula, demais->flavio, demais->abstencao, branco_nulo->flavio, branco_nulo->abstencao | 3 | lula->lula, flavio->flavio, demais->branco_nulo |
| Nordeste | 14 | lula->flavio, flavio->lula, flavio->branco_nulo, flavio->abstencao, cury->abstencao, renan->branco_nulo, renan->abstencao, caiado->abstencao, demais->lula, demais->branco_nulo, demais->abstencao, branco_nulo->flavio, branco_nulo->abstencao, abstencao->flavio | 2 | flavio->flavio, demais->flavio |
| Norte | 16 | lula->flavio, flavio->lula, cury->flavio, cury->abstencao, renan->branco_nulo, renan->abstencao, caiado->lula, caiado->abstencao, demais->lula, demais->branco_nulo, demais->abstencao, branco_nulo->flavio, branco_nulo->abstencao, abstencao->lula, abstencao->flavio, abstencao->branco_nulo | 2 | demais->flavio, abstencao->abstencao |
| Sudeste | 12 | lula->flavio, lula->branco_nulo, lula->abstencao, flavio->lula, flavio->branco_nulo, cury->abstencao, renan->abstencao, caiado->abstencao, demais->branco_nulo, demais->abstencao, branco_nulo->flavio, branco_nulo->abstencao | 1 | lula->lula |
| Sul | 12 | lula->flavio, lula->branco_nulo, lula->abstencao, flavio->lula, flavio->branco_nulo, flavio->abstencao, cury->abstencao, demais->branco_nulo, demais->abstencao, branco_nulo->flavio, branco_nulo->abstencao, abstencao->flavio | 2 | lula->lula, flavio->flavio |

**Plausibilidade** (só reportada; nada é forçado).

| regiao | lula->lula | flavio->flavio | abstencao->abstencao |
|---|---|---|---|
| Centro-Oeste | 1.0000 | 1.0000 | 0.9135 |
| Nordeste | 0.9923 | 1.0000 | 0.8935 |
| Norte | 0.9470 | 0.9803 | 1.0000 |
| Sudeste | 1.0000 | 0.9964 | 0.8869 |
| Sul | 1.0000 | 1.0000 | 0.8772 |
| Brasil | 0.9924 | 0.9967 | 0.8980 |

## 4. E2 — ajuste, R2, fronteira e plausibilidade

**Total previsto x real do 2º turno (votos).** `previsto = soma_i aptos_*_i * (X_i beta)_c`.

| regiao | destino | previsto (aptos_2t) | previsto (aptos_1t) | real | dif. % (aptos_2t) | dif. % (aptos_1t) |
|---|---|---|---|---|---|---|
| Centro-Oeste | lula | 3.731.555 | 3.731.358 | 3.733.919 | -0.0633 | -0.0686 |
| Centro-Oeste | flavio | 5.612.038 | 5.611.793 | 5.603.867 | +0.1458 | +0.1414 |
| Centro-Oeste | branco_nulo | 288.198 | 288.185 | 257.568 | +11.8919 | +11.8869 |
| Centro-Oeste | abstencao | 2.369.905 | 2.369.806 | 2.406.342 | -1.5142 | -1.5183 |
| Nordeste | lula | 24.170.545 | 24.170.683 | 24.450.432 | -1.1447 | -1.1441 |
| Nordeste | flavio | 11.040.875 | 11.041.067 | 10.796.736 | +2.2612 | +2.2630 |
| Nordeste | branco_nulo | 1.019.065 | 1.019.076 | 1.088.464 | -6.3759 | -6.3748 |
| Nordeste | abstencao | 7.280.372 | 7.280.411 | 7.175.226 | +1.4654 | +1.4659 |
| Norte | lula | 5.243.351 | 5.243.464 | 5.024.626 | +4.3531 | +4.3553 |
| Norte | flavio | 5.228.919 | 5.229.084 | 5.023.547 | +4.0882 | +4.0915 |
| Norte | branco_nulo | 312.145 | 312.156 | 268.937 | +16.0661 | +16.0702 |
| Norte | abstencao | 2.316.441 | 2.316.471 | 2.783.746 | -16.7869 | -16.7858 |
| Sudeste | lula | 24.022.734 | 24.022.592 | 24.037.731 | -0.0624 | -0.0630 |
| Sudeste | flavio | 26.721.996 | 26.721.979 | 26.844.501 | -0.4564 | -0.4564 |
| Sudeste | branco_nulo | 1.895.755 | 1.895.748 | 2.013.023 | -5.8255 | -5.8258 |
| Sudeste | abstencao | 13.704.291 | 13.704.244 | 13.449.521 | +1.8943 | +1.8939 |
| Sul | lula | 6.872.981 | 6.873.095 | 6.809.370 | +0.9342 | +0.9358 |
| Sul | flavio | 11.155.981 | 11.156.034 | 11.385.893 | -2.0193 | -2.0188 |
| Sul | branco_nulo | 585.452 | 585.459 | 516.017 | +13.4560 | +13.4572 |
| Sul | abstencao | 4.256.219 | 4.256.266 | 4.159.353 | +2.3289 | +2.3300 |
| Brasil | lula | 64.041.166 | 64.041.192 | 64.056.078 | -0.0233 | -0.0232 |
| Brasil | flavio | 59.759.810 | 59.759.956 | 59.654.544 | +0.1765 | +0.1767 |
| Brasil | branco_nulo | 4.100.615 | 4.100.623 | 4.144.009 | -1.0471 | -1.0470 |
| Brasil | abstencao | 29.927.228 | 29.927.198 | 29.974.188 | -0.1567 | -0.1568 |

**R2 ponderado por destino (peso = aptos_1t).**

| regiao | R2 lula | R2 flavio | R2 branco_nulo | R2 abstencao |
|---|---|---|---|---|
| Centro-Oeste | 0.9804 | 0.9781 | 0.1316 | 0.8314 |
| Nordeste | 0.9598 | 0.9846 | 0.3341 | 0.7117 |
| Norte | 0.9597 | 0.9616 | -0.0488 | -0.0837 |
| Sudeste | 0.9846 | 0.9860 | 0.2022 | 0.8559 |
| Sul | 0.9846 | 0.9810 | -0.1375 | 0.9209 |

**Células de beta na fronteira (0 ou 1), ajuste pontual.**

| unidade | # em 0 | células em 0 | # em 1 | células em 1 |
|---|---|---|---|---|
| Brasil (nacional) | 17 | lula->flavio, lula->branco_nulo, lula->abstencao, flavio->lula, flavio->branco_nulo, flavio->abstencao, cury->flavio, cury->abstencao, renan->branco_nulo, renan->abstencao, caiado->abstencao, demais->lula, demais->branco_nulo, demais->abstencao, branco_nulo->flavio, branco_nulo->abstencao, abstencao->flavio | 3 | lula->lula, flavio->flavio, demais->flavio |

**Plausibilidade** (só reportada; nada é forçado).

| regiao | lula->lula | flavio->flavio | abstencao->abstencao |
|---|---|---|---|
| Centro-Oeste | 1.0000 | 1.0000 | 0.9098 |
| Nordeste | 1.0000 | 1.0000 | 0.9098 |
| Norte | 1.0000 | 1.0000 | 0.9098 |
| Sudeste | 1.0000 | 1.0000 | 0.9098 |
| Sul | 1.0000 | 1.0000 | 0.9098 |
| Brasil | 1.0000 | 1.0000 | 0.9098 |

## 5. E3 — ajuste, R2, fronteira e plausibilidade

**Total previsto x real do 2º turno (votos).** `previsto = soma_i aptos_*_i * (X_i beta)_c`.

| regiao | destino | previsto (aptos_2t) | previsto (aptos_1t) | real | dif. % (aptos_2t) | dif. % (aptos_1t) |
|---|---|---|---|---|---|---|
| Centro-Oeste | lula | 3.691.325 | 3.691.128 | 3.733.919 | -1.1407 | -1.1460 |
| Centro-Oeste | flavio | 5.572.272 | 5.572.028 | 5.603.867 | -0.5638 | -0.5682 |
| Centro-Oeste | branco_nulo | 215.373 | 215.364 | 257.568 | -16.3820 | -16.3854 |
| Centro-Oeste | abstencao | 2.522.726 | 2.522.621 | 2.406.342 | +4.8365 | +4.8322 |
| Nordeste | lula | 24.234.095 | 24.234.239 | 24.450.432 | -0.8848 | -0.8842 |
| Nordeste | flavio | 10.634.934 | 10.635.116 | 10.796.736 | -1.4986 | -1.4969 |
| Nordeste | branco_nulo | 1.056.293 | 1.056.305 | 1.088.464 | -2.9556 | -2.9545 |
| Nordeste | abstencao | 7.585.536 | 7.585.577 | 7.175.226 | +5.7184 | +5.7190 |
| Norte | lula | 4.889.287 | 4.889.392 | 5.024.626 | -2.6935 | -2.6914 |
| Norte | flavio | 4.898.500 | 4.898.649 | 5.023.547 | -2.4892 | -2.4863 |
| Norte | branco_nulo | 299.812 | 299.824 | 268.937 | +11.4802 | +11.4847 |
| Norte | abstencao | 3.013.257 | 3.013.311 | 2.783.746 | +8.2447 | +8.2466 |
| Sudeste | lula | 23.797.983 | 23.797.846 | 24.037.731 | -0.9974 | -0.9980 |
| Sudeste | flavio | 27.019.886 | 27.019.866 | 26.844.501 | +0.6533 | +0.6533 |
| Sudeste | branco_nulo | 1.996.215 | 1.996.204 | 2.013.023 | -0.8350 | -0.8355 |
| Sudeste | abstencao | 13.530.692 | 13.530.646 | 13.449.521 | +0.6035 | +0.6032 |
| Sul | lula | 6.724.136 | 6.724.249 | 6.809.370 | -1.2517 | -1.2501 |
| Sul | flavio | 11.468.345 | 11.468.401 | 11.385.893 | +0.7242 | +0.7246 |
| Sul | branco_nulo | 522.095 | 522.100 | 516.017 | +1.1778 | +1.1788 |
| Sul | abstencao | 4.156.058 | 4.156.104 | 4.159.353 | -0.0792 | -0.0781 |
| Brasil | lula | 63.336.826 | 63.336.854 | 64.056.078 | -1.1228 | -1.1228 |
| Brasil | flavio | 59.593.937 | 59.594.059 | 59.654.544 | -0.1016 | -0.1014 |
| Brasil | branco_nulo | 4.089.788 | 4.089.797 | 4.144.009 | -1.3084 | -1.3082 |
| Brasil | abstencao | 30.808.268 | 30.808.258 | 29.974.188 | +2.7827 | +2.7826 |

**R2 por destino**: colunas `R2 destino` com peso aptos_1t; colunas `R2 s/peso` com peso 1 (o critério próprio de E3).

| regiao | R2 lula | R2 flavio | R2 branco_nulo | R2 abstencao | R2 s/peso lula | R2 s/peso flavio | R2 s/peso branco_nulo | R2 s/peso abstencao |
|---|---|---|---|---|---|---|---|---|
| Centro-Oeste | 0.9754 | 0.9790 | -0.0101 | 0.7388 | 0.9703 | 0.9796 | 0.6630 | 0.7468 |
| Nordeste | 0.9660 | 0.9856 | 0.3963 | 0.6474 | 0.9473 | 0.9756 | 0.3336 | 0.6474 |
| Norte | 0.9733 | 0.9672 | 0.2872 | 0.3481 | 0.9793 | 0.9664 | 0.4304 | 0.4518 |
| Sudeste | 0.9827 | 0.9855 | 0.5827 | 0.8774 | 0.9860 | 0.9896 | 0.5275 | 0.8902 |
| Sul | 0.9854 | 0.9917 | 0.7201 | 0.9427 | 0.9876 | 0.9913 | 0.6366 | 0.9164 |

**Células de beta na fronteira (0 ou 1), ajuste pontual.**

| unidade | # em 0 | células em 0 | # em 1 | células em 1 |
|---|---|---|---|---|
| Centro-Oeste | 13 | lula->flavio, lula->branco_nulo, flavio->lula, flavio->branco_nulo, flavio->abstencao, cury->abstencao, renan->branco_nulo, renan->abstencao, demais->flavio, demais->branco_nulo, demais->abstencao, branco_nulo->flavio, branco_nulo->abstencao | 2 | flavio->flavio, demais->lula |
| Nordeste | 12 | lula->flavio, flavio->lula, flavio->abstencao, cury->abstencao, renan->flavio, renan->branco_nulo, renan->abstencao, caiado->abstencao, demais->lula, branco_nulo->flavio, branco_nulo->abstencao, abstencao->flavio | 1 | renan->lula |
| Norte | 14 | lula->flavio, cury->lula, cury->flavio, cury->branco_nulo, renan->flavio, renan->branco_nulo, renan->abstencao, caiado->flavio, caiado->abstencao, demais->branco_nulo, demais->abstencao, branco_nulo->flavio, branco_nulo->abstencao, abstencao->flavio | 2 | cury->abstencao, renan->lula |
| Sudeste | 11 | lula->flavio, lula->branco_nulo, lula->abstencao, flavio->lula, flavio->branco_nulo, flavio->abstencao, cury->abstencao, renan->abstencao, caiado->abstencao, demais->branco_nulo, branco_nulo->abstencao | 2 | lula->lula, flavio->flavio |
| Sul | 10 | lula->flavio, lula->branco_nulo, lula->abstencao, flavio->lula, flavio->branco_nulo, flavio->abstencao, demais->lula, demais->branco_nulo, demais->abstencao, abstencao->flavio | 3 | lula->lula, flavio->flavio, demais->flavio |

**Plausibilidade** (só reportada; nada é forçado).

| regiao | lula->lula | flavio->flavio | abstencao->abstencao |
|---|---|---|---|
| Centro-Oeste | 0.9779 | 1.0000 | 0.9251 |
| Nordeste | 0.9875 | 0.9891 | 0.9319 |
| Norte | 0.9609 | 0.9748 | 0.9694 |
| Sudeste | 1.0000 | 1.0000 | 0.8981 |
| Sul | 1.0000 | 1.0000 | 0.8604 |
| Brasil | 0.9905 | 0.9957 | 0.9086 |

## 6. Comparação E1 x E2 x E3 (beta Brasil)

Maior diferença absoluta entre destinos, por origem (beta Brasil). Diferença grande E1 x E2 indica viés de agregação.

| origem | max|beta E1 - beta E2| | max|beta E1 - beta E3| |
|---|---|---|
| lula | 0.0076 | 0.0020 |
| flavio | 0.0033 | 0.0012 |
| cury | 0.3335 | 0.1156 |
| renan | 0.2634 | 0.0245 |
| caiado | 0.1345 | 0.1165 |
| demais | 0.5716 | 0.0984 |
| branco_nulo | 0.1693 | 0.0633 |
| abstencao | 0.0257 | 0.0106 |

## 7. Críticas à especificação (com números)

**C1. Denominadores `aptos_1t` (X) x `aptos_2t` (Y) diferem.** 3725 de 5.571 municípios têm aptos_2t != aptos_1t; soma dos módulos = 18.863 eleitores, saldo líquido = -149, maior diferença relativa = 0.323%. Efeito prático desprezível (< 0,02% do eleitorado), mas o modelo mistura bases diferentes e a identidade `Y(1x4)` somar 1 vale em aptos_2t. As tabelas de totais previstos (seções 3 a 5) trazem as duas versões (aptos_2t e aptos_1t); a diferença entre elas é de dezenas a centenas de votos.

**C2. Cifra do enunciado: 'comparecimento subiu 2,96 milhões'.** Nos 5.571 municípios o comparecimento foi de 124.934.069 para 127.854.631 (+2.920.562); a queda da abstenção (com não instaladas, que são 0 nos dois turnos) é 2.920.711. O valor 2,96 milhões só aparece quando se inclui o exterior (ZZ); a especificação exclui o exterior, então o número da seção 1 não é consistente com o universo da seção 3 (erro de ~40 mil).

**C3. Ambiguidade do bootstrap dos fluxos em votos.** A especificação manda 'recalcular os fluxos' por réplica, mas não diz se N_reg[r] é o observado ou o da réplica. N_reg é conhecido exatamente (o universo inteiro é observado), então este código usa o N observado (fixo) em `transferencias.csv`; a alternativa (N reamostrado) está em `transferencias_n_reamostrado.csv`. Efeito, E1 Brasil:

| fluxo | votos (ponto) | IC N fixo | IC N reamostrado | razão das larguras |
|---|---|---|---|---|
| cury->lula | 1.641.048 | 1.278.043 a 2.257.489 | 1.298.648 a 2.086.806 | 0.80 |
| cury->flavio | 1.146.779 | 755.765 a 1.378.471 | 673.920 a 1.629.372 | 1.53 |
| renan->lula | 1.243.869 | 915.216 a 1.511.228 | 844.445 a 1.773.883 | 1.56 |
| renan->flavio | 1.084.048 | 858.648 a 1.334.973 | 798.543 a 1.388.802 | 1.24 |
| caiado->lula | 1.153.657 | 840.052 a 1.358.047 | 756.378 a 1.586.469 | 1.60 |
| caiado->flavio | 1.082.370 | 887.543 a 1.329.381 | 836.983 a 1.425.743 | 1.33 |

**C4. IC percentil na fronteira.** Em E1 há 67 de 160 células regionais com beta pontual = 0. Dessas, o IC é degenerado (largura < 1e-9) em 48 células regionais e 1 das 32 células Brasil. Com a restrição beta >= 0 a distribuição bootstrap acumula massa em 0, e o percentil 2,5 também vira 0: o IC subestima a incerteza de células na fronteira. Células regionais cujo ponto cai fora do próprio IC: 0.


**C5. A ponderação por aptos_1t concentra o ajuste em poucos municípios.** Tamanho efetivo amostral (soma w)^2 / soma w^2 e participação do maior município:

| região | municípios | n efetivo | maior peso |
|---|---|---|---|
| Centro-Oeste | 468 | 19.7 | 18.8% |
| Nordeste | 1794 | 144.5 | 4.5% |
| Norte | 450 | 39.9 | 11.3% |
| Sudeste | 1668 | 35.9 | 13.8% |
| Sul | 1191 | 99.8 | 6.2% |

**C6. Totais do 2º turno não reproduzidos (fronteira ativa).** Sem restrições de sinal, o OLS ponderado com X somando 1 reproduz exatamente o total de cada destino; com `beta >= 0` ativo isso deixa de valer. Em E1, o branco/nulo previsto no Brasil erra -29.331 votos (-0.71%); em E2 erra -43.394 (-1.05%); em E3 a abstenção erra +834.080 (+2.78%). Isto é tensão do modelo (a seção 8 da especificação pede para reportar), não erro de código: o solver satisfaz KKT. Leitura de produto: com 67 de 160 células regionais coladas em 0, o modelo está dizendo que a hipótese de constância linear não descreve bem branco/nulo e abstenção, e as estimativas de grupos pequenos (cury, renan, caiado, demais) dependem mais da restrição do que dos dados.


Com 8 parâmetros livres por coluna, um n efetivo de poucas dezenas explica o cond(G) elevado e os IC largos nos grupos pequenos; a reamostragem bootstrap de municípios com pesos tão desiguais é instável (a presença/ausência de uma capital muda o ajuste).

