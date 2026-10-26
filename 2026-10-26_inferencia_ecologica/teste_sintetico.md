# Teste de recuperação sintética

Gerado por `02_teste_sintetico.py` · semente 20261025 · 5571 municípios (X real).

Y sintético: `contagens ~ Multinomial(aptos_1t, X · β_verdadeiro)`, sorteado região a região (ordem Centro-Oeste, Nordeste, Norte, Sudeste, Sul) com um único gerador; Y = contagens / aptos_1t. Ajuste ponderado por `aptos_1t`, sem bootstrap (só estimativa pontual).

## T1 — β constante no país

Sorteio oficial (semente 20261025). Erro absoluto máximo por linha (maior |estimado − verdadeiro| entre os 4 destinos).

| origem | E2 (β nacional) | E1 (Brasil agregado) | E1 (pior região) |
|---|---|---|---|
| **lula** | 0.0001 | 0.0004 | 0.0046 |
| **flavio** | 0.0003 | 0.0003 | 0.0031 |
| **cury** | 0.0138 | 0.0195 | 0.0457 |
| **renan** | 0.0118 | 0.0131 | 0.0641 |
| **caiado** | 0.0021 | 0.0126 | 0.0333 |
| **demais** | 0.0119 | 0.0375 | 0.2085 |
| **branco_nulo** | 0.0048 | 0.0031 | 0.0176 |
| **abstencao** | 0.0005 | 0.0010 | 0.0086 |

- Máximo geral: **E2 = 0.0138** · **E1 Brasil = 0.0375** · **E1 pior região = 0.2085**.

### Erro com sinal (estimado − verdadeiro), sorteio oficial

**E2**

| origem | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| **lula** | -0.0000 | -0.0001 | -0.0000 | +0.0001 |
| **flavio** | -0.0003 | +0.0001 | +0.0001 | +0.0000 |
| **cury** | -0.0045 | -0.0060 | -0.0032 | +0.0138 |
| **renan** | +0.0118 | -0.0051 | +0.0018 | -0.0084 |
| **caiado** | -0.0020 | +0.0021 | +0.0009 | -0.0009 |
| **demais** | -0.0031 | -0.0119 | +0.0061 | +0.0090 |
| **branco_nulo** | -0.0006 | +0.0040 | +0.0015 | -0.0048 |
| **abstencao** | +0.0004 | +0.0001 | -0.0005 | +0.0000 |

**E1 (Brasil agregado)**

| origem | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| **lula** | +0.0001 | -0.0003 | -0.0001 | +0.0004 |
| **flavio** | -0.0003 | -0.0001 | +0.0001 | +0.0003 |
| **cury** | -0.0039 | -0.0123 | -0.0033 | +0.0195 |
| **renan** | +0.0091 | +0.0048 | -0.0008 | -0.0131 |
| **caiado** | +0.0126 | -0.0027 | -0.0030 | -0.0069 |
| **demais** | -0.0375 | +0.0080 | +0.0289 | +0.0007 |
| **branco_nulo** | -0.0013 | +0.0022 | +0.0022 | -0.0031 |
| **abstencao** | +0.0000 | +0.0010 | -0.0003 | -0.0008 |

### Sorteios complementares (20 sementes, 20261026 em diante)

Não faz parte da especificação. Serve para separar viés sistemático de ruído amostral: erro máximo por linha, mediana e máximo entre sorteios.

| origem | E2 mediana | E2 máximo | E1 Brasil mediana | E1 Brasil máximo |
|---|---|---|---|---|
| **lula** | 0.0004 | 0.0009 | 0.0006 | 0.0015 |
| **flavio** | 0.0004 | 0.0008 | 0.0004 | 0.0014 |
| **cury** | 0.0107 | 0.0201 | 0.0136 | 0.0262 |
| **renan** | 0.0105 | 0.0316 | 0.0134 | 0.0279 |
| **caiado** | 0.0026 | 0.0058 | 0.0152 | 0.0326 |
| **demais** | 0.0286 | 0.0650 | 0.0462 | 0.1022 |
| **branco_nulo** | 0.0056 | 0.0123 | 0.0084 | 0.0165 |
| **abstencao** | 0.0012 | 0.0028 | 0.0015 | 0.0031 |

## T2 — β de Caiado varia por região

Caiado: Centro-Oeste `[0,55; 0,30; 0,08; 0,07]`, demais regiões `[0,25; 0,55; 0,10; 0,10]`. As demais linhas são iguais às do T1. O fluxo 'verdadeiro' é o valor esperado `Σ_regiões N_reg[caiado] · β_verdadeiro_reg` (o sorteio multinomial adiciona ruído de ordem √N aos votos realizados).

Total do grupo Caiado no Brasil: **2,600,440** eleitores.

### Fluxo nacional de Caiado

| destino | verdadeiro (votos) | E1 (votos) | erro E1 | erro E1 (% do verdadeiro) | E2 (votos) | erro E2 | erro E2 (% do verdadeiro) |
|---|---|---|---|---|---|---|---|
| lula | 834,156 | 825,502 | -8,654 | -1.04% | 1,468,244 | +634,087 | +76.02% |
| flavio | 1,276,870 | 1,289,245 | +12,374 | +0.97% | 751,409 | -525,461 | -41.15% |
| branco_nulo | 247,774 | 241,224 | -6,550 | -2.64% | 204,949 | -42,825 | -17.28% |
| abstencao | 241,639 | 244,470 | +2,830 | +1.17% | 175,839 | -65,801 | -27.23% |

- Erro máximo do fluxo de Caiado (maior destino, % do total do grupo): **E1 = 0.48%** · **E2 = 24.38%**.

### Erro máximo por linha do β do Brasil (contra o β agregado verdadeiro do T2)

| origem | E1 (Brasil) | E2 (Brasil) | E1 (pior região, vs β regional verdadeiro) |
|---|---|---|---|
| **lula** | 0.0006 | 0.0025 | 0.0026 |
| **flavio** | 0.0003 | 0.0003 | 0.0037 |
| **cury** | 0.0061 | 0.0574 | 0.0825 |
| **renan** | 0.0185 | 0.0788 | 0.0805 |
| **caiado** | 0.0048 | 0.2438 | 0.0637 |
| **demais** | 0.0568 | 0.1105 | 0.3501 |
| **branco_nulo** | 0.0042 | 0.0285 | 0.0583 |
| **abstencao** | 0.0011 | 0.0040 | 0.0079 |

### Linha de Caiado, β por região — E1 × verdadeiro

| região | origem | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|---|
| Centro-Oeste | verdadeiro | 0.550 | 0.300 | 0.080 | 0.070 |
| Centro-Oeste | E1 | 0.557 | 0.293 | 0.079 | 0.070 |
| Centro-Oeste | E2 | 0.565 | 0.289 | 0.079 | 0.068 |
| Nordeste | verdadeiro | 0.250 | 0.550 | 0.100 | 0.100 |
| Nordeste | E1 | 0.259 | 0.539 | 0.091 | 0.111 |
| Nordeste | E2 | 0.565 | 0.289 | 0.079 | 0.068 |
| Norte | verdadeiro | 0.250 | 0.550 | 0.100 | 0.100 |
| Norte | E1 | 0.247 | 0.614 | 0.094 | 0.045 |
| Norte | E2 | 0.565 | 0.289 | 0.079 | 0.068 |
| Sudeste | verdadeiro | 0.250 | 0.550 | 0.100 | 0.100 |
| Sudeste | E1 | 0.233 | 0.559 | 0.102 | 0.106 |
| Sudeste | E2 | 0.565 | 0.289 | 0.079 | 0.068 |
| Sul | verdadeiro | 0.250 | 0.550 | 0.100 | 0.100 |
| Sul | E1 | 0.254 | 0.558 | 0.090 | 0.099 |
| Sul | E2 | 0.565 | 0.289 | 0.079 | 0.068 |

- Resultado: E2 erra mais que E1 no fluxo nacional de Caiado (direção esperada).
