# Teste de recuperação sintética (reimplementação B)

Gerado por `executar.py`. `X` real (5.571 municípios); `Y_i ~ Multinomial(aptos_1t_i, X_i beta_verdadeiro)`, semente 20261025 (um `default_rng` novo por teste); pesos aptos_1t. Erro = |estimado - verdadeiro|. E1 Brasil = fluxos das 5 regiões somados.

## T1 — beta constante no país

Erro absoluto máximo por linha de origem (máximo sobre os 4 destinos).

| origem | E2 (nacional) | E1 Brasil (agregado) | E1 pior região |
|---|---|---|---|
| lula | 0.0002 | 0.0012 | 0.0097 |
| flavio | 0.0006 | 0.0008 | 0.0070 |
| cury | 0.0145 | 0.0114 | 0.0468 |
| renan | 0.0144 | 0.0084 | 0.0497 |
| caiado | 0.0060 | 0.0088 | 0.0412 |
| demais | 0.0224 | 0.0064 | 0.2161 |
| branco_nulo | 0.0038 | 0.0049 | 0.0871 |
| abstencao | 0.0007 | 0.0017 | 0.0091 |

Máximo geral: E2 = **0.0224**, E1 Brasil = **0.0114**, E1 pior região = **0.2161**.

Betas estimados x verdadeiros:

| origem | modelo | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|---|
| lula | verdadeiro | 0.9500 | 0.0200 | 0.0100 | 0.0200 |
| lula | E2 | 0.9501 | 0.0198 | 0.0098 | 0.0202 |
| lula | E1 Brasil | 0.9509 | 0.0188 | 0.0097 | 0.0206 |
| flavio | verdadeiro | 0.0200 | 0.9500 | 0.0100 | 0.0200 |
| flavio | E2 | 0.0201 | 0.9494 | 0.0100 | 0.0205 |
| flavio | E1 Brasil | 0.0203 | 0.9492 | 0.0099 | 0.0207 |
| cury | verdadeiro | 0.4000 | 0.3500 | 0.1000 | 0.1500 |
| cury | E2 | 0.3855 | 0.3571 | 0.1067 | 0.1508 |
| cury | E1 Brasil | 0.3886 | 0.3539 | 0.1062 | 0.1514 |
| renan | verdadeiro | 0.1500 | 0.6500 | 0.1000 | 0.1000 |
| renan | E2 | 0.1644 | 0.6414 | 0.0976 | 0.0966 |
| renan | E1 Brasil | 0.1554 | 0.6543 | 0.0987 | 0.0916 |
| caiado | verdadeiro | 0.3500 | 0.4500 | 0.1000 | 0.1000 |
| caiado | E2 | 0.3461 | 0.4560 | 0.0996 | 0.0983 |
| caiado | E1 Brasil | 0.3588 | 0.4541 | 0.0952 | 0.0918 |
| demais | verdadeiro | 0.3000 | 0.4000 | 0.1500 | 0.1500 |
| demais | E2 | 0.3224 | 0.3841 | 0.1380 | 0.1555 |
| demais | E1 Brasil | 0.3012 | 0.3936 | 0.1494 | 0.1558 |
| branco_nulo | verdadeiro | 0.2000 | 0.1500 | 0.4500 | 0.2000 |
| branco_nulo | E2 | 0.2008 | 0.1515 | 0.4515 | 0.1962 |
| branco_nulo | E1 Brasil | 0.1951 | 0.1531 | 0.4537 | 0.1981 |
| abstencao | verdadeiro | 0.0800 | 0.0500 | 0.0200 | 0.8500 |
| abstencao | E2 | 0.0802 | 0.0507 | 0.0197 | 0.8494 |
| abstencao | E1 Brasil | 0.0795 | 0.0517 | 0.0197 | 0.8491 |

## T2 — beta de Caiado varia por região

Caiado verdadeiro: Centro-Oeste `[0,55; 0,30; 0,08; 0,07]`; demais regiões `[0,25; 0,55; 0,10; 0,10]`. Demais linhas iguais a T1. Fluxo verdadeiro = soma por região de `beta_verdadeiro * N_reg` (esperança, sem ruído multinomial).

Total de eleitores de Caiado (1º turno, 5.571 municípios): **2.600.440**; beta nacional verdadeiro de Caiado (média ponderada pelos fluxos): `0.3208, 0.4910, 0.0953, 0.0929`.

**Fluxo nacional de Caiado (votos).**

| destino | verdadeiro | E1 | erro E1 | erro E1 % | E2 | erro E2 | erro E2 % |
|---|---|---|---|---|---|---|---|
| lula | 834.156 | 782.565 | -51.591 | -6.18% | 1.467.926 | +633.770 | +75.98% |
| flavio | 1.276.870 | 1.287.730 | +10.860 | +0.85% | 748.895 | -527.976 | -41.35% |
| branco_nulo | 247.774 | 258.424 | +10.649 | +4.30% | 202.115 | -45.659 | -18.43% |
| abstencao | 241.639 | 271.722 | +30.082 | +12.45% | 181.505 | -60.135 | -24.89% |

Erro máximo do fluxo de Caiado (por destino): E1 = **51.591 votos (12.45% do total de Caiado)**; E2 = **633.770 votos (75.98%)**.

Beta de Caiado no Centro-Oeste (verdadeiro `[0,55; 0,30; 0,08; 0,07]`):

| modelo | lula | flavio | branco_nulo | abstencao | erro máx. |
|---|---|---|---|---|---|
| E1 (região CO) | 0.5452 | 0.3021 | 0.0782 | 0.0744 | 0.0048 |
| E2 (nacional) | 0.5645 | 0.2880 | 0.0777 | 0.0698 | 0.0145 |

**Leitura.** E2 erra mais que E1 no fluxo nacional (esperado). No Centro-Oeste, E2 enviesa o beta de Caiado e E1 recupera.

