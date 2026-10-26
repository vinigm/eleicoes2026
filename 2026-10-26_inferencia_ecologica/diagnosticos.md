# Diagnósticos — inferência ecológica da migração de votos (presidente 2026)

Gerado em 26/10/2026 por `01_estimar_transferencias.py` · 5571 municípios · B = 1000 · semente 20261025 · tempo 23s.

> **Leitura do IC.** O IC 95% (bootstrap) mede apenas a variabilidade amostral entre municípios. Ele NÃO captura o viés da hipótese de constância (dentro de cada região, a fração de cada grupo que vai para cada destino é igual em todos os municípios).

## Alertas

- **E1**
  - células na fronteira (0 ou 1) na estimativa pontual: **77**
  - maior cond(G) pontual: **1.545e+06**
  - maior cond(G) entre as 1000 réplicas: **2.635e+06**
  - maior lacuna de dualidade pontual: 1.27e-09
- **E2**
  - células na fronteira (0 ou 1) na estimativa pontual: **20**
  - maior cond(G) pontual: **9.360e+04**
  - maior cond(G) entre as 1000 réplicas: **1.711e+05**
  - maior lacuna de dualidade pontual: 2.03e-09
- **E3**
  - células na fronteira (0 ou 1) na estimativa pontual: **70**
  - maior cond(G) pontual: **1.656e+06**
  - maior cond(G) entre as 1000 réplicas: **2.028e+06**
  - maior lacuna de dualidade pontual: 9.37e-10

- **E1, concentração extrema regional** (β ≥ 0.8 em cury/renan/caiado; heurística de alerta, indica grupo pouco identificado):
  - Nordeste renan→lula = 0.928 [0.763; 1.000]
  - Norte cury→lula = 0.885 [0.323; 1.000]
  - Norte caiado→branco_nulo = 0.872 [0.538; 1.000]

- Convergência: nenhuma falha. Qualquer falha de convergência, solução inviável ou lacuna de dualidade acima de 1e-07 interromperia a execução com erro.

## 1. Âncoras

Todas as 20 âncoras da especificação (somas por categoria nos dois turnos, aptos, municípios total e por região) foram conferidas por igualdade exata de inteiros, e as linhas de X e Y somam 1 (desvio máximo ~2e-16).

- `1t_lula`: 53,722,151 (esperado 53,722,151) — **PASS**
- `1t_flavio`: 55,960,603 (esperado 55,960,603) — **PASS**
- `1t_cury`: 3,438,835 (esperado 3,438,835) — **PASS**
- `1t_renan`: 2,667,307 (esperado 2,667,307) — **PASS**
- `1t_caiado`: 2,600,440 (esperado 2,600,440) — **PASS**
- `1t_demais`: 580,570 (esperado 580,570) — **PASS**
- `1t_branco_nulo`: 5,964,163 (esperado 5,964,163) — **PASS**
- `1t_abstencao`: 32,894,899 (esperado 32,894,899) — **PASS**
- `1t_aptos`: 157,828,968 (esperado 157,828,968) — **PASS**
- `2t_lula`: 64,056,078 (esperado 64,056,078) — **PASS**
- `2t_flavio`: 59,654,544 (esperado 59,654,544) — **PASS**
- `2t_branco_nulo`: 4,144,009 (esperado 4,144,009) — **PASS**
- `2t_abstencao`: 29,974,188 (esperado 29,974,188) — **PASS**
- `2t_aptos`: 157,828,819 (esperado 157,828,819) — **PASS**
- `municipios_total`: 5,571 (esperado 5,571) — **PASS**
- `municipios_Centro-Oeste`: 468 (esperado 468) — **PASS**
- `municipios_Nordeste`: 1,794 (esperado 1,794) — **PASS**
- `municipios_Norte`: 450 (esperado 450) — **PASS**
- `municipios_Sudeste`: 1,668 (esperado 1,668) — **PASS**
- `municipios_Sul`: 1,191 (esperado 1,191) — **PASS**

## 2. Resultado principal — E1, Brasil, β com IC 95%

> O IC 95% (bootstrap) mede apenas a variabilidade amostral entre municípios. Ele NÃO captura o viés da hipótese de constância (dentro de cada região, a fração de cada grupo que vai para cada destino é igual em todos os municípios).

| origem 1º turno | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| **lula** | 0.992 [0.989; 0.995] | 0.000 [0.000; 0.000] | 0.003 [0.001; 0.004] | 0.004 [0.003; 0.010] |
| **flavio** | 0.000 [0.000; 0.000] | 0.997 [0.993; 0.999] | 0.001 [0.000; 0.002] | 0.002 [0.000; 0.006] |
| **cury** | 0.477 [0.368; 0.642] | 0.333 [0.222; 0.404] | 0.189 [0.115; 0.235] | 0.000 [0.000; 0.058] |
| **renan** | 0.466 [0.340; 0.578] | 0.406 [0.317; 0.509] | 0.114 [0.060; 0.182] | 0.013 [0.000; 0.030] |
| **caiado** | 0.444 [0.327; 0.519] | 0.416 [0.346; 0.511] | 0.121 [0.080; 0.191] | 0.019 [0.006; 0.036] |
| **demais** | 0.521 [0.307; 0.698] | 0.428 [0.255; 0.645] | 0.051 [0.000; 0.102] | 0.000 [0.000; 0.014] |
| **branco_nulo** | 0.702 [0.647; 0.735] | 0.000 [0.000; 0.030] | 0.298 [0.262; 0.341] | 0.000 [0.000; 0.010] |
| **abstencao** | 0.068 [0.057; 0.078] | 0.010 [0.004; 0.017] | 0.024 [0.019; 0.033] | 0.898 [0.884; 0.906] |

### Fluxos em votos (E1, Brasil, milhares de votos)

| origem 1º turno | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| **lula** | 53,316 [53,124; 53,454] | 0 [0; 0] | 177 [46; 234] | 229 [137; 513] |
| **flavio** | 0 [0; 11] | 55,773 [55,557; 55,914] | 57 [0; 138] | 130 [0; 344] |
| **cury** | 1,641 [1,267; 2,209] | 1,147 [764; 1,389] | 651 [395; 808] | 0 [0; 198] |
| **renan** | 1,244 [906; 1,541] | 1,084 [845; 1,358] | 305 [160; 485] | 35 [0; 80] |
| **caiado** | 1,154 [851; 1,350] | 1,082 [900; 1,330] | 315 [209; 496] | 50 [15; 94] |
| **demais** | 302 [178; 405] | 249 [148; 375] | 29 [0; 59] | 0 [0; 8] |
| **branco_nulo** | 4,185 [3,861; 4,381] | 0 [0; 180] | 1,779 [1,564; 2,036] | 0 [0; 61] |
| **abstencao** | 2,227 [1,886; 2,577] | 327 [118; 574] | 801 [618; 1,077] | 29,539 [29,084; 29,790] |

### E1 por região (β pontual, origens principais e lealdade)

| região | origem | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|---|
| Centro-Oeste | cury | 0.553 | 0.292 | 0.155 | 0.000 |
| Centro-Oeste | renan | 0.491 | 0.244 | 0.265 | 0.000 |
| Centro-Oeste | caiado | 0.378 | 0.484 | 0.093 | 0.045 |
| Centro-Oeste | lula | 1.000 | 0.000 | 0.000 | 0.000 |
| Centro-Oeste | flavio | 0.000 | 1.000 | 0.000 | 0.000 |
| Centro-Oeste | abstencao | 0.043 | 0.031 | 0.013 | 0.913 |
| Nordeste | cury | 0.446 | 0.219 | 0.335 | 0.000 |
| Nordeste | renan | 0.928 | 0.072 | 0.000 | 0.000 |
| Nordeste | caiado | 0.713 | 0.274 | 0.013 | 0.000 |
| Nordeste | lula | 0.992 | 0.000 | 0.006 | 0.002 |
| Nordeste | flavio | 0.000 | 1.000 | 0.000 | 0.000 |
| Nordeste | abstencao | 0.058 | 0.000 | 0.048 | 0.894 |
| Norte | cury | 0.885 | 0.000 | 0.115 | 0.000 |
| Norte | renan | 0.541 | 0.459 | 0.000 | 0.000 |
| Norte | caiado | 0.000 | 0.128 | 0.872 | 0.000 |
| Norte | lula | 0.947 | 0.000 | 0.011 | 0.042 |
| Norte | flavio | 0.000 | 0.980 | 0.011 | 0.008 |
| Norte | abstencao | 0.000 | 0.000 | 0.000 | 1.000 |
| Sudeste | cury | 0.468 | 0.401 | 0.130 | 0.000 |
| Sudeste | renan | 0.402 | 0.482 | 0.115 | 0.000 |
| Sudeste | caiado | 0.580 | 0.349 | 0.071 | 0.000 |
| Sudeste | lula | 1.000 | 0.000 | 0.000 | 0.000 |
| Sudeste | flavio | 0.000 | 0.996 | 0.000 | 0.004 |
| Sudeste | abstencao | 0.072 | 0.016 | 0.025 | 0.887 |
| Sul | cury | 0.304 | 0.499 | 0.197 | 0.000 |
| Sul | renan | 0.095 | 0.604 | 0.228 | 0.073 |
| Sul | caiado | 0.087 | 0.719 | 0.141 | 0.053 |
| Sul | lula | 1.000 | 0.000 | 0.000 | 0.000 |
| Sul | flavio | 0.000 | 1.000 | 0.000 | 0.000 |
| Sul | abstencao | 0.122 | 0.000 | 0.001 | 0.877 |

## 3. Sensibilidade — E1 × E2 × E3 (β do Brasil)

| origem | especificação | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|---|
| **cury** | E1 | 0.477 | 0.333 | 0.189 | 0.000 |
| **cury** | E2 | 0.542 | 0.000 | 0.458 | 0.000 |
| **cury** | E3 | 0.538 | 0.218 | 0.148 | 0.096 |
| **renan** | E1 | 0.466 | 0.406 | 0.114 | 0.013 |
| **renan** | E2 | 0.330 | 0.670 | 0.000 | 0.000 |
| **renan** | E3 | 0.459 | 0.386 | 0.139 | 0.016 |
| **caiado** | E1 | 0.444 | 0.416 | 0.121 | 0.019 |
| **caiado** | E2 | 0.383 | 0.551 | 0.066 | 0.000 |
| **caiado** | E3 | 0.327 | 0.485 | 0.153 | 0.035 |
| **lula** | E1 | 0.992 | 0.000 | 0.003 | 0.004 |
| **lula** | E2 | 1.000 | 0.000 | 0.000 | 0.000 |
| **lula** | E3 | 0.990 | 0.000 | 0.004 | 0.006 |
| **flavio** | E1 | 0.000 | 0.997 | 0.001 | 0.002 |
| **flavio** | E2 | 0.000 | 1.000 | 0.000 | 0.000 |
| **flavio** | E3 | 0.000 | 0.996 | 0.002 | 0.002 |
| **abstencao** | E1 | 0.068 | 0.010 | 0.024 | 0.898 |
| **abstencao** | E2 | 0.042 | 0.000 | 0.048 | 0.910 |
| **abstencao** | E3 | 0.065 | 0.010 | 0.016 | 0.909 |

- Diferença máxima **E1 × E2** nas linhas cury/renan/caiado e nas 4 células de lealdade: **0.3335** (na matriz inteira: 0.5716).
- Diferença máxima **E1 × E3** nas mesmas células: **0.1165** (na matriz inteira: 0.1165).
- Diferença grande entre E1 e E2 sinaliza viés de agregação (β que varia por região ajustado por um β único). É reportada, não corrigida.

## 4. Ajuste

### E1 — erro relativo do total previsto do 2º turno

| região | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| Centro-Oeste | +0.011% | +0.001% | -0.534% | +0.037% |
| Nordeste | -0.006% | -0.005% | -0.954% | +0.171% |
| Norte | +0.006% | +0.220% | -2.335% | -0.182% |
| Sudeste | +0.030% | +0.011% | -0.458% | -0.007% |
| Sul | +0.100% | -0.050% | -0.402% | +0.022% |
| Brasil | +0.021% | +0.013% | -0.708% | +0.027% |

### E1 — R² ponderado por destino (peso aptos_1t)

| região | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| Centro-Oeste | 0.9811 | 0.9811 | 0.7561 | 0.8465 |
| Nordeste | 0.9711 | 0.9890 | 0.3918 | 0.7154 |
| Norte | 0.9836 | 0.9778 | 0.3236 | 0.5772 |
| Sudeste | 0.9867 | 0.9869 | 0.5656 | 0.8816 |
| Sul | 0.9893 | 0.9938 | 0.7317 | 0.9441 |
| Brasil | 0.9935 | 0.9940 | 0.6521 | 0.8274 |

### E2 — erro relativo do total previsto do 2º turno

| região | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| Centro-Oeste | -0.063% | +0.146% | +11.892% | -1.514% |
| Nordeste | -1.145% | +2.261% | -6.376% | +1.465% |
| Norte | +4.353% | +4.088% | +16.066% | -16.787% |
| Sudeste | -0.062% | -0.456% | -5.825% | +1.894% |
| Sul | +0.934% | -2.019% | +13.456% | +2.329% |
| Brasil | -0.023% | +0.176% | -1.047% | -0.157% |

### E2 — R² ponderado por destino (peso aptos_1t)

| região | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| Centro-Oeste | 0.9804 | 0.9781 | 0.1316 | 0.8314 |
| Nordeste | 0.9598 | 0.9846 | 0.3341 | 0.7117 |
| Norte | 0.9597 | 0.9616 | -0.0488 | -0.0837 |
| Sudeste | 0.9846 | 0.9860 | 0.2022 | 0.8559 |
| Sul | 0.9846 | 0.9810 | -0.1375 | 0.9209 |
| Brasil | 0.9902 | 0.9909 | 0.4263 | 0.7321 |

### E3 — erro relativo do total previsto do 2º turno

| região | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| Centro-Oeste | -1.141% | -0.564% | -16.382% | +4.837% |
| Nordeste | -0.885% | -1.499% | -2.956% | +5.718% |
| Norte | -2.694% | -2.489% | +11.480% | +8.245% |
| Sudeste | -0.997% | +0.653% | -0.835% | +0.604% |
| Sul | -1.252% | +0.724% | +1.178% | -0.079% |
| Brasil | -1.123% | -0.102% | -1.308% | +2.783% |

### E3 — R² ponderado por destino (peso aptos_1t)

| região | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| Centro-Oeste | 0.9754 | 0.9790 | -0.0101 | 0.7388 |
| Nordeste | 0.9660 | 0.9856 | 0.3963 | 0.6474 |
| Norte | 0.9733 | 0.9672 | 0.2872 | 0.3481 |
| Sudeste | 0.9827 | 0.9855 | 0.5827 | 0.8774 |
| Sul | 0.9854 | 0.9917 | 0.7201 | 0.9427 |
| Brasil | 0.9915 | 0.9923 | 0.6145 | 0.7720 |

### E1 — total previsto × real, Brasil

| destino | previsto | real | diferença |
|---|---|---|---|
| lula | 64,069,601 | 64,056,078 | +13,523 |
| flavio | 59,662,323 | 59,654,544 | +7,779 |
| branco_nulo | 4,114,678 | 4,144,009 | -29,331 |
| abstencao | 29,982,218 | 29,974,188 | +8,030 |

## 5. Células de β na fronteira (0 ou 1)

Fronteira ativa indica tensão do modelo (o ótimo sem restrição sairia de [0, 1]) ou grupo pouco identificado.

### E1

- **Centro-Oeste**: 16 célula(s) na fronteira: lula→lula=1.0000; lula→flavio=0.0000; lula→branco_nulo=0.0000; lula→abstencao=0.0000; flavio→lula=0.0000; flavio→flavio=1.0000; flavio→branco_nulo=0.0000; flavio→abstencao=0.0000; cury→abstencao=0.0000; renan→abstencao=0.0000; demais→lula=0.0000; demais→flavio=0.0000; demais→branco_nulo=1.0000; demais→abstencao=0.0000; branco_nulo→flavio=0.0000; branco_nulo→abstencao=0.0000
- **Nordeste**: 16 célula(s) na fronteira: lula→flavio=0.0000; flavio→lula=0.0000; flavio→flavio=1.0000; flavio→branco_nulo=0.0000; flavio→abstencao=0.0000; cury→abstencao=0.0000; renan→branco_nulo=0.0000; renan→abstencao=0.0000; caiado→abstencao=0.0000; demais→lula=0.0000; demais→flavio=1.0000; demais→branco_nulo=0.0000; demais→abstencao=0.0000; branco_nulo→flavio=0.0000; branco_nulo→abstencao=0.0000; abstencao→flavio=0.0000
- **Norte**: 18 célula(s) na fronteira: lula→flavio=0.0000; flavio→lula=0.0000; cury→flavio=0.0000; cury→abstencao=0.0000; renan→branco_nulo=0.0000; renan→abstencao=0.0000; caiado→lula=0.0000; caiado→abstencao=0.0000; demais→lula=0.0000; demais→flavio=1.0000; demais→branco_nulo=0.0000; demais→abstencao=0.0000; branco_nulo→flavio=0.0000; branco_nulo→abstencao=0.0000; abstencao→lula=0.0000; abstencao→flavio=0.0000; abstencao→branco_nulo=0.0000; abstencao→abstencao=1.0000
- **Sudeste**: 13 célula(s) na fronteira: lula→lula=1.0000; lula→flavio=0.0000; lula→branco_nulo=0.0000; lula→abstencao=0.0000; flavio→lula=0.0000; flavio→branco_nulo=0.0000; cury→abstencao=0.0000; renan→abstencao=0.0000; caiado→abstencao=0.0000; demais→branco_nulo=0.0000; demais→abstencao=0.0000; branco_nulo→flavio=0.0000; branco_nulo→abstencao=0.0000
- **Sul**: 14 célula(s) na fronteira: lula→lula=1.0000; lula→flavio=0.0000; lula→branco_nulo=0.0000; lula→abstencao=0.0000; flavio→lula=0.0000; flavio→flavio=1.0000; flavio→branco_nulo=0.0000; flavio→abstencao=0.0000; cury→abstencao=0.0000; demais→branco_nulo=0.0000; demais→abstencao=0.0000; branco_nulo→flavio=0.0000; branco_nulo→abstencao=0.0000; abstencao→flavio=0.0000

### E2

- **Brasil**: 20 célula(s) na fronteira: lula→lula=1.0000; lula→flavio=0.0000; lula→branco_nulo=0.0000; lula→abstencao=0.0000; flavio→lula=0.0000; flavio→flavio=1.0000; flavio→branco_nulo=0.0000; flavio→abstencao=0.0000; cury→flavio=0.0000; cury→abstencao=0.0000; renan→branco_nulo=0.0000; renan→abstencao=0.0000; caiado→abstencao=0.0000; demais→lula=0.0000; demais→flavio=1.0000; demais→branco_nulo=0.0000; demais→abstencao=0.0000; branco_nulo→flavio=0.0000; branco_nulo→abstencao=0.0000; abstencao→flavio=0.0000

### E3

- **Centro-Oeste**: 15 célula(s) na fronteira: lula→flavio=0.0000; lula→branco_nulo=0.0000; flavio→lula=0.0000; flavio→flavio=1.0000; flavio→branco_nulo=0.0000; flavio→abstencao=0.0000; cury→abstencao=0.0000; renan→branco_nulo=0.0000; renan→abstencao=0.0000; demais→lula=1.0000; demais→flavio=0.0000; demais→branco_nulo=0.0000; demais→abstencao=0.0000; branco_nulo→flavio=0.0000; branco_nulo→abstencao=0.0000
- **Nordeste**: 13 célula(s) na fronteira: lula→flavio=0.0000; flavio→lula=0.0000; flavio→abstencao=0.0000; cury→abstencao=0.0000; renan→lula=1.0000; renan→flavio=0.0000; renan→branco_nulo=0.0000; renan→abstencao=0.0000; caiado→abstencao=0.0000; demais→lula=0.0000; branco_nulo→flavio=0.0000; branco_nulo→abstencao=0.0000; abstencao→flavio=0.0000
- **Norte**: 16 célula(s) na fronteira: lula→flavio=0.0000; cury→lula=0.0000; cury→flavio=0.0000; cury→branco_nulo=0.0000; cury→abstencao=1.0000; renan→lula=1.0000; renan→flavio=0.0000; renan→branco_nulo=0.0000; renan→abstencao=0.0000; caiado→flavio=0.0000; caiado→abstencao=0.0000; demais→branco_nulo=0.0000; demais→abstencao=0.0000; branco_nulo→flavio=0.0000; branco_nulo→abstencao=0.0000; abstencao→flavio=0.0000
- **Sudeste**: 13 célula(s) na fronteira: lula→lula=1.0000; lula→flavio=0.0000; lula→branco_nulo=0.0000; lula→abstencao=0.0000; flavio→lula=0.0000; flavio→flavio=1.0000; flavio→branco_nulo=0.0000; flavio→abstencao=0.0000; cury→abstencao=0.0000; renan→abstencao=0.0000; caiado→abstencao=0.0000; demais→branco_nulo=0.0000; branco_nulo→abstencao=0.0000
- **Sul**: 13 célula(s) na fronteira: lula→lula=1.0000; lula→flavio=0.0000; lula→branco_nulo=0.0000; lula→abstencao=0.0000; flavio→lula=0.0000; flavio→flavio=1.0000; flavio→branco_nulo=0.0000; flavio→abstencao=0.0000; demais→lula=0.0000; demais→flavio=1.0000; demais→branco_nulo=0.0000; demais→abstencao=0.0000; abstencao→flavio=0.0000

## 6. Plausibilidade (só reportada, nunca forçada)

| especificação | região | β[lula→lula] | β[flavio→flavio] |
|---|---|---|---|
| E1 | Centro-Oeste | 1.000 | 1.000 |
| E1 | Nordeste | 0.992 | 1.000 |
| E1 | Norte | 0.947 | 0.980 |
| E1 | Sudeste | 1.000 | 0.996 |
| E1 | Sul | 1.000 | 1.000 |
| E1 | Brasil | 0.992 | 0.997 |
| E2 | Centro-Oeste | 1.000 | 1.000 |
| E2 | Nordeste | 1.000 | 1.000 |
| E2 | Norte | 1.000 | 1.000 |
| E2 | Sudeste | 1.000 | 1.000 |
| E2 | Sul | 1.000 | 1.000 |
| E2 | Brasil | 1.000 | 1.000 |
| E3 | Centro-Oeste | 0.978 | 1.000 |
| E3 | Nordeste | 0.987 | 0.989 |
| E3 | Norte | 0.961 | 0.975 |
| E3 | Sudeste | 1.000 | 1.000 |
| E3 | Sul | 1.000 | 1.000 |
| E3 | Brasil | 0.990 | 0.996 |

## 7. Convergência do solver (estimativa pontual)

### E1

| unidade de ajuste | iterações SLSQP | cond(G) | cond(G escalada) | lacuna de dualidade |
|---|---|---|---|---|
| Centro-Oeste | 26 | 9.328e+05 | 8.809e+02 | 5.12e-10 |
| Nordeste | 22 | 1.545e+06 | 4.742e+02 | 1.27e-09 |
| Norte | 21 | 1.397e+06 | 5.019e+02 | 1.67e-10 |
| Sudeste | 25 | 6.474e+04 | 6.946e+02 | 1.79e-11 |
| Sul | 27 | 2.722e+05 | 6.589e+02 | 2.71e-10 |

### E2

| unidade de ajuste | iterações SLSQP | cond(G) | cond(G escalada) | lacuna de dualidade |
|---|---|---|---|---|
| Brasil | 19 | 9.360e+04 | 3.436e+02 | 2.03e-09 |

### E3

| unidade de ajuste | iterações SLSQP | cond(G) | cond(G escalada) | lacuna de dualidade |
|---|---|---|---|---|
| Centro-Oeste | 26 | 7.401e+05 | 3.965e+02 | 4.60e-10 |
| Nordeste | 24 | 1.656e+06 | 3.562e+02 | 2.44e-10 |
| Norte | 23 | 1.156e+06 | 2.948e+02 | 9.37e-10 |
| Sudeste | 26 | 5.674e+04 | 3.405e+02 | 5.68e-10 |
| Sul | 27 | 3.168e+05 | 3.061e+02 | 2.65e-10 |

## Decisões de implementação (ambiguidades da especificação)

- **N_reg fixo no bootstrap:** os totais de cada grupo por região (`N_reg[r] = Σ aptos_1t · X[r]`) são dados observados, não estimados; só o `β` é reestimado em cada réplica. O IC dos fluxos mede, portanto, incerteza de `β`.
- **E3 com bootstrap:** a especificação define IC para E1 e E2; E3 também recebeu bootstrap (mesmas multiplicidades) para preencher as colunas de IC do CSV.
- **E2 por região:** as linhas regionais de E2 repetem o `β` nacional; os fluxos regionais usam `β_nacional · N_reg`.
- **Total previsto** usa `aptos_2t` como denominador (Y é fração dos aptos do 2º turno). Os fluxos em votos usam `aptos_1t` (contagem do grupo no 1º turno): a soma dos fluxos por destino difere do total real do 2º turno só pelo erro do ajuste e pela diferença de aptos entre turnos (−149 aptos no Brasil).
- **R² ponderado** usa peso `aptos_1t` em E1, E2 e E3 (mesma régua).
- **Pesos:** o ajuste pondera por `aptos_1t` mesmo com Y normalizado por `aptos_2t`, como na especificação. `aptos_2t − aptos_1t` soma −149 no Brasil; 3.725 municípios diferem, com diferença relativa máxima de 0,32%.
- **Solver:** SLSQP sobre 32 parâmetros com gradiente analítico, restrições de soma por linha e limites [0, 1]. As variáveis são reescaladas por `d_r = sqrt(G_rr)` (o `cond(G)` cai de ~1e6 para ~5e2 no espaço do solver; o ótimo é o mesmo). `ftol`=1e-14 com objetivo multiplicado por 100 (ftol efetivo 1e-16). Medido na base real: SLSQP direto, sem reescala, com `ftol=1e-12` devolvia betas que diferiam até 0,44 (Centro-Oeste) conforme o ponto inicial; com a reescala, a diferença máxima entre 6 pontos iniciais (E1, E3, regiões e nacional) foi 8e-6.
- **Certificado de ótimo:** a lacuna de Frank-Wolfe (limite superior de objetivo − ótimo) é calculada em todo ajuste e exigida ≤ 1e-07.
- **Ponto inicial:** uniforme (0,25) na estimativa pontual; o `β` pontual em cada réplica bootstrap (só acelera, o problema é convexo).
- **Fronteira:** célula com `β ≤ 1e-6` ou `β ≥ 1 − 1e-6`.
- **Percentis:** `np.percentile` com interpolação linear (2,5 e 97,5).
