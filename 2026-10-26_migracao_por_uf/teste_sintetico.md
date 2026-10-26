# Teste de recuperação sintética — migração de votos por estado

Criado em 26/10/2026. Gerado por `03_teste_sintetico.py`. Método: seção 7 de `ESPECIFICACAO.md`.

## Desenho

- X real (5.571 municípios); `Y_i ~ Multinomial(aptos_1t_i, X_i · β_verdadeiro_u)`; semente 20261025.
- β da região = matriz T1 da especificação regional (lula/flavio ~0,95 de lealdade; cury 0,40/0,35/0,10/0,15; renan 0,15/0,65/0,10/0,10; caiado 0,35/0,45/0,10/0,10; ...).
- β do estado = β da região + deslocamento δ_u de `flavio` para `lula` (δ_u > 0 = mais lula) nas linhas caiado, cury e renan; δ_u ~ Uniforme[−0,15; +0,15] por estado (mesmo δ_u nas 3 linhas), sorteado ANTES de Y com a mesma semente; deslocamento recortado em [−β_lula, +β_flavio] para manter o simplex.
- Y em fração dos aptos do 1º turno (cada linha soma 1); o 2º turno real não é usado.
- Comparação: (a) UF com κ escolhido por validação cruzada (mesma grade e dobras) NOS DADOS SINTÉTICOS; (b) UF_SOZINHO; (c) UF_REGIAO.
- **Esperado:** (a) ≤ min((b), (c)). Se não for, reporta-se; o método não é ajustado.

## Sorteio principal (semente 20261025)

- **CONFIRMADO SÓ POR EMPATE: (a) = (b)**, porque o κ\* sintético caiu na borda inferior da grade (κ = 0,25) e a versão UF coincide com UF_SOZINHO. O teste não mostra ganho do encolhimento sobre o estado sozinho.
- (a) = **0,04700** · (b) = **0,04700** · (c) = **0,09064**.
- **ALERTA: κ\* sintético está na borda da grade** (grade não estendida).
- Erro = média, sobre as 4 destinações, de |β̂ − β verdadeiro|, nas linhas caiado/cury/renan, ponderada por `N_u[r]` (contagem do grupo no estado).

| versão | erro médio absoluto de β (caiado, cury, renan; ponderado por N_u[r]) |
|---|---|
| (a) UF, κ por validação cruzada nos dados sintéticos (κ\* = 0,25) | 0,04700 |
| (b) UF_SOZINHO (κ = 0,25) | 0,04700 |
| (c) UF_REGIAO (κ = ∞) | 0,09064 |

### Erro por origem

| origem | (a) UF | (b) UF_SOZINHO | (c) UF_REGIAO |
|---|---|---|---|
| caiado | 0,03460 | 0,03460 | 0,12630 |
| cury | 0,03795 | 0,03795 | 0,06804 |
| renan | 0,07074 | 0,07074 | 0,08502 |

### Validação cruzada nos dados sintéticos

| κ | erro de validação (dados sintéticos) | ÷ menor erro |
|---|---|---|
| 0,25 | 3.879,1 | 1,0000 |
| 0,5 | 3.895,1 | 1,0041 |
| 1 | 3.951,2 | 1,0186 |
| 2 | 4.076,5 | 1,0509 |
| 4 | 4.314,9 | 1,1123 |
| 8 | 4.745,3 | 1,2233 |
| 16 | 5.496,9 | 1,4171 |
| 32 | 6.661,0 | 1,7172 |
| 64 | 8.253,0 | 2,1276 |
| 128 | 10.133,4 | 2,6123 |
| 256 | 12.097,8 | 3,1187 |
| ∞ | 21.311,6 | 5,4940 |

### Diagnóstico: erro de β por κ com o β verdadeiro (oráculo; não existe em dados reais)

- Melhor κ pelo erro de β verdadeiro: **0,25**; κ\* escolhido pela validação cruzada (que só enxerga Y): **0,25**.

| κ | erro de β verdadeiro (a versão UF nesse κ) |
|---|---|
| 0,25 | 0,04700 |
| 0,5 | 0,04873 |
| 1 | 0,05370 |
| 2 | 0,06114 |
| 4 | 0,07011 |
| 8 | 0,07649 |
| 16 | 0,08032 |
| 32 | 0,08056 |
| 64 | 0,07928 |
| 128 | 0,08076 |
| 256 | 0,08334 |
| ∞ | 0,09064 |

### Por estado (erro ponderado por N_u[r] nas 3 linhas)

| UF | δ_u | erro (a) UF | erro (b) UF_SOZINHO | erro (c) UF_REGIAO |
|---|---|---|---|---|
| AC | -0,102 | 0,1485 | 0,1485 | 0,0799 |
| AL | -0,107 | 0,1214 | 0,1214 | 0,0578 |
| AM | -0,056 | 0,0408 | 0,0408 | 0,0626 |
| AP | 0,051 | 0,0896 | 0,0896 | 0,0747 |
| BA | -0,125 | 0,0431 | 0,0431 | 0,1290 |
| CE | 0,014 | 0,0518 | 0,0518 | 0,0262 |
| DF | -0,054 | 0,1225 | 0,1225 | 0,1073 |
| ES | 0,014 | 0,1034 | 0,1034 | 0,0918 |
| GO | 0,087 | 0,0155 | 0,0155 | 0,1302 |
| MA | 0,042 | 0,0999 | 0,0999 | 0,0313 |
| MG | 0,112 | 0,0141 | 0,0141 | 0,1287 |
| MS | -0,139 | 0,1427 | 0,1427 | 0,1128 |
| MT | 0,124 | 0,0477 | 0,0477 | 0,1428 |
| PA | -0,116 | 0,0331 | 0,0331 | 0,0988 |
| PB | -0,023 | 0,0646 | 0,0646 | 0,0431 |
| PE | 0,133 | 0,0447 | 0,0447 | 0,0703 |
| PI | -0,053 | 0,0556 | 0,0556 | 0,0514 |
| PR | 0,118 | 0,0312 | 0,0312 | 0,1262 |
| RJ | 0,104 | 0,0823 | 0,0823 | 0,1125 |
| RN | 0,049 | 0,0500 | 0,0500 | 0,0172 |
| RO | -0,088 | 0,0863 | 0,0863 | 0,0650 |
| RR | 0,142 | 0,1548 | 0,1548 | 0,1078 |
| RS | -0,114 | 0,0306 | 0,0306 | 0,1590 |
| SC | 0,002 | 0,0536 | 0,0536 | 0,0917 |
| SE | 0,047 | 0,1260 | 0,1260 | 0,0403 |
| SP | -0,004 | 0,0367 | 0,0367 | 0,0528 |
| TO | 0,047 | 0,0570 | 0,0570 | 0,0547 |

## Evidência complementar (fora da especificação): outras sementes

- 20 sorteios independentes (sementes 20261026 a 20261045), mesmo procedimento.
- **(a) ≤ min((b), (c)) em 15 de 20 sorteios.**
- κ\* sintético = 0,25 (borda inferior da grade) em **13 de 20**; nesses casos (a) é idêntico a (b) (13 empates exatos).
- Erro médio: (a) **0,04647** · (b) **0,04583** · (c) **0,09705**.
- Serve só para saber se o sorteio principal é típico; o veredito da especificação é o do sorteio principal.

| semente | κ\* sintético | (a) UF | (b) UF_SOZINHO | (c) UF_REGIAO | (a) ≤ min((b), (c)) | melhor κ (oráculo) | erro no melhor κ (oráculo) |
|---|---|---|---|---|---|---|---|
| 20261026 | 0,5 | 0,04207 | 0,03883 | 0,10551 | NÃO | 0,25 | 0,03883 |
| 20261027 | 0,25 | 0,04855 | 0,04855 | 0,11170 | sim | 0,25 | 0,04855 |
| 20261028 | 0,25 | 0,04440 | 0,04440 | 0,09929 | sim | 0,25 | 0,04440 |
| 20261029 | 0,5 | 0,03977 | 0,03802 | 0,07233 | NÃO | 0,25 | 0,03802 |
| 20261030 | 0,25 | 0,04441 | 0,04441 | 0,11706 | sim | 0,25 | 0,04441 |
| 20261031 | 0,25 | 0,04837 | 0,04837 | 0,14416 | sim | 0,25 | 0,04837 |
| 20261032 | 0,25 | 0,05318 | 0,05318 | 0,10706 | sim | 0,25 | 0,05318 |
| 20261033 | 0,25 | 0,05636 | 0,05636 | 0,14172 | sim | 0,25 | 0,05636 |
| 20261034 | 0,25 | 0,05414 | 0,05414 | 0,09562 | sim | 0,25 | 0,05414 |
| 20261035 | 0,25 | 0,04366 | 0,04366 | 0,08149 | sim | 0,25 | 0,04366 |
| 20261036 | 0,25 | 0,05638 | 0,05638 | 0,10822 | sim | 0,25 | 0,05638 |
| 20261037 | 0,25 | 0,04572 | 0,04572 | 0,07417 | sim | 0,25 | 0,04572 |
| 20261038 | 0,5 | 0,03981 | 0,03689 | 0,06450 | NÃO | 0,25 | 0,03689 |
| 20261039 | 0,25 | 0,04898 | 0,04898 | 0,10421 | sim | 0,25 | 0,04898 |
| 20261040 | 0,25 | 0,05225 | 0,05225 | 0,11630 | sim | 0,25 | 0,05225 |
| 20261041 | 0,25 | 0,04366 | 0,04366 | 0,08277 | sim | 0,25 | 0,04366 |
| 20261042 | 0,5 | 0,04647 | 0,04216 | 0,08506 | NÃO | 0,25 | 0,04216 |
| 20261043 | 0,5 | 0,04497 | 0,04360 | 0,08346 | NÃO | 0,25 | 0,04360 |
| 20261044 | 0,5 | 0,03688 | 0,03742 | 0,06012 | sim | 1 | 0,03646 |
| 20261045 | 0,5 | 0,03933 | 0,03969 | 0,08615 | sim | 0,5 | 0,03933 |

## Controle (fora da especificação): mundo sem heterogeneidade, δ_u = 0

- Mesmo procedimento e semente, mas todos os estados com o β da região (β constante). É o regime em que encolher para a região DEVE ajudar; confere se a validação cruzada e o solver enxergam isso.
- κ\* sintético = **128** (borda da grade: não); melhor κ pelo β verdadeiro (oráculo) = **64**.
- Erro de β nas 3 linhas: (a) UF = **0,01687** · (b) UF_SOZINHO = **0,03836** · (c) UF_REGIAO = **0,02240**; (a) ≤ min((b), (c)): sim.

## Solver

- Todos os ajustes (validações cruzadas e estimativas dos sorteios) foram certificados (sucesso do SLSQP, viabilidade e lacuna de dualidade ≤ 1e-7); falha seria exceção.
- Ajustes das validações cruzadas que precisaram do ponto inicial uniforme de reserva: **3** (sorteio principal: 0; inclui complementares e controle).
