# Conciliação: base de Presidente 2026 (1º e 2º turno) por município

Gerado em 26/10/2026 11:02 por `03_conciliar.py`. **Status geral: OK** (0 checagens reprovadas).

## Resumo

| Checagem | Descrição | Status | Números |
|---|---|---|---|
| a | Somas nacionais vs âncoras oficiais | PASS | 29/29 âncoras batem; divergências: 0 |
| b | Soma dos municípios por UF (2T) vs JSON de cada UF | PASS | 28 UFs x 9 campos = 252 comparações; divergências: 0 |
| c | Soma das UFs vs JSON nacional (e soma da base vs JSON nacional) | PASS | 28 UFs; 9 campos; divergências: 0 |
| d | Identidades contábeis por município | PASS | 7 identidades testadas em 5757 municípios cada; violações totais: 0 |
| e | Todo JSON com tf == "s" e s.pst == "100,00" | PASS | 5757/5757 municípios lidos + 28 UFs + nacional; exceções: 0; erros de leitura: 0 |
| f | Contagem de municípios por UF vs lista oficial | PASS | 28 UFs; divergências por UF: 0; total=5757, Brasil=5571, exterior=186 |
| g1 | Extra: chave única, nulos, tipos e códigos | PASS | 5757 linhas, 34 colunas; 28 colunas numéricas em int64 sem nulos nem negativos; problemas: 0 |
| g2 | Extra: código IBGE (formato, unicidade, prefixo da UF, nulo no exterior) | PASS | IBGE distintos no Brasil: 5571; nulos no exterior: 186/186; problemas: 0 |
| g3 | Extra: 1T da base vs soma por UF dos CSVs brutos | PASS | 532 comparações UF x coluna; divergências: 0 |
| g4 | Extra: longo vs largo (linhas, nulos, chaves, células) | PASS | longo: 80598 linhas (1T=69084, 2T=11514); células diferentes: 0; problemas: 0 |
| g5 | Extra: CSV gravado == parquet | PASS | CSV com 5757 linhas e 34 colunas; 28 colunas numéricas comparadas; problemas: 0 |
| g6 | Informativo: aptos por município mudam entre turnos (total nacional igual) | INFO | 3779 de 5757 municípios com aptos diferentes entre os turnos; soma das altas 9.524, soma das quedas -9.524, saldo líquido 0 |
| g7 | Informativo: nome do município no config (2T) vs CSV (1T) | INFO | 45 nomes diferentes de 5757; 45 só por apóstrofo (config "D'ÁGUA" vs CSV 1T "D ÁGUA"); outras diferenças: 0 |

## (a) Somas nacionais vs âncoras oficiais: PASS

29/29 âncoras batem; divergências: 0

| Âncora | Esperado | Obtido | Diferença | Status |
|---|---|---|---|---|
| 1T votos candidato 22 | 56.104.503 | 56.104.503 | 0 | PASS |
| 1T votos candidato 13 | 53.879.538 | 53.879.538 | 0 | PASS |
| 1T votos candidato 70 | 3.448.569 | 3.448.569 | 0 | PASS |
| 1T votos candidato 14 | 2.675.887 | 2.675.887 | 0 | PASS |
| 1T votos candidato 55 | 2.605.148 | 2.605.148 | 0 | PASS |
| 1T votos candidato 30 | 326.488 | 326.488 | 0 | PASS |
| 1T votos candidato 80 | 122.911 | 122.911 | 0 | PASS |
| 1T votos candidato 16 | 43.103 | 43.103 | 0 | PASS |
| 1T votos candidato 27 | 40.043 | 40.043 | 0 | PASS |
| 1T votos candidato 21 | 22.693 | 22.693 | 0 | PASS |
| 1T votos candidato 35 | 16.881 | 16.881 | 0 | PASS |
| 1T votos candidato 29 | 15.024 | 15.024 | 0 | PASS |
| 1T validos | 119.300.788 | 119.300.788 | 0 | PASS |
| 1T brancos | 2.300.798 | 2.300.798 | 0 | PASS |
| 1T nulos | 3.674.249 | 3.674.249 | 0 | PASS |
| 1T comparecimento | 125.275.835 | 125.275.835 | 0 | PASS |
| 1T abstencao | 33.469.244 | 33.469.244 | 0 | PASS |
| 1T aptos | 158.745.502 | 158.745.502 | 0 | PASS |
| 1T nao_instaladas | 423 | 423 | 0 | PASS |
| 1T ZZ aptos | 916.534 | 916.534 | 0 | PASS |
| 1T ZZ comparecimento | 341.766 | 341.766 | 0 | PASS |
| 2T votos candidato 13 | 64.256.232 | 64.256.232 | 0 | PASS |
| 2T votos candidato 22 | 59.826.041 | 59.826.041 | 0 | PASS |
| 2T validos | 124.082.273 | 124.082.273 | 0 | PASS |
| 2T brancos | 1.430.496 | 1.430.496 | 0 | PASS |
| 2T nulos | 2.723.305 | 2.723.305 | 0 | PASS |
| 2T comparecimento | 128.236.074 | 128.236.074 | 0 | PASS |
| 2T abstencao | 30.509.005 | 30.509.005 | 0 | PASS |
| 2T aptos | 158.745.502 | 158.745.502 | 0 | PASS |

## (b) Soma dos municípios por UF (2T) vs JSON de cada UF: PASS

28 UFs x 9 campos = 252 comparações; divergências: 0

## (c) Soma das UFs vs JSON nacional (e soma da base vs JSON nacional): PASS

28 UFs; 9 campos; divergências: 0

| Campo | JSON nacional | Soma dos JSONs de UF | Soma da base | Status |
|---|---|---|---|---|
| aptos | 158.745.502 | 158.745.502 | 158.745.502 | PASS |
| comparecimento | 128.236.074 | 128.236.074 | 128.236.074 | PASS |
| abstencao | 30.509.005 | 30.509.005 | 30.509.005 | PASS |
| nao_instaladas | 423 | 423 | 423 | PASS |
| validos | 124.082.273 | 124.082.273 | 124.082.273 | PASS |
| brancos | 1.430.496 | 1.430.496 | 1.430.496 | PASS |
| nulos | 2.723.305 | 2.723.305 | 2.723.305 | PASS |
| votos_13 | 64.256.232 | 64.256.232 | 64.256.232 | PASS |
| votos_22 | 59.826.041 | 59.826.041 | 59.826.041 | PASS |

## (d) Identidades contábeis por município: PASS

7 identidades testadas em 5757 municípios cada; violações totais: 0

| Turno | Identidade | Municípios testados | Violações | Status |
|---|---|---|---|---|
| 1T | comparecimento == validos + brancos + nulos | 5.757 | 0 | PASS |
| 1T | aptos == comparecimento + abstencao + nao_instaladas | 5.757 | 0 | PASS |
| 1T | validos == soma dos votos dos candidatos | 5.757 | 0 | PASS |
| 2T | comparecimento == validos + brancos + nulos | 5.757 | 0 | PASS |
| 2T | aptos == comparecimento + abstencao + nao_instaladas | 5.757 | 0 | PASS |
| 2T | validos == soma dos votos dos candidatos | 5.757 | 0 | PASS |
| 2T (JSON) | v.tv == e.c | 5.757 | 0 | PASS |

## (e) Todo JSON com tf == "s" e s.pst == "100,00": PASS

5757/5757 municípios lidos + 28 UFs + nacional; exceções: 0; erros de leitura: 0

## (f) Contagem de municípios por UF vs lista oficial: PASS

28 UFs; divergências por UF: 0; total=5757, Brasil=5571, exterior=186

| UF | Esperado | Base | Config TSE | Status |
|---|---|---|---|---|
| AC | 22 | 22 | 22 | PASS |
| AL | 102 | 102 | 102 | PASS |
| AP | 16 | 16 | 16 | PASS |
| AM | 62 | 62 | 62 | PASS |
| BA | 417 | 417 | 417 | PASS |
| CE | 184 | 184 | 184 | PASS |
| DF | 1 | 1 | 1 | PASS |
| ES | 78 | 78 | 78 | PASS |
| GO | 246 | 246 | 246 | PASS |
| MA | 217 | 217 | 217 | PASS |
| MT | 142 | 142 | 142 | PASS |
| MS | 79 | 79 | 79 | PASS |
| MG | 853 | 853 | 853 | PASS |
| PR | 399 | 399 | 399 | PASS |
| PB | 223 | 223 | 223 | PASS |
| PA | 144 | 144 | 144 | PASS |
| PE | 185 | 185 | 185 | PASS |
| PI | 224 | 224 | 224 | PASS |
| RJ | 92 | 92 | 92 | PASS |
| RN | 167 | 167 | 167 | PASS |
| RS | 497 | 497 | 497 | PASS |
| RO | 52 | 52 | 52 | PASS |
| RR | 15 | 15 | 15 | PASS |
| SC | 295 | 295 | 295 | PASS |
| SE | 75 | 75 | 75 | PASS |
| SP | 645 | 645 | 645 | PASS |
| TO | 139 | 139 | 139 | PASS |
| ZZ | 186 | 186 | 186 | PASS |

Totais: base=5757 (esperado 5757); Brasil=5571 (esperado 5571); exterior=186 (esperado 186).

## (g1) Extra: chave única, nulos, tipos e códigos: PASS

5757 linhas, 34 colunas; 28 colunas numéricas em int64 sem nulos nem negativos; problemas: 0

## (g2) Extra: código IBGE (formato, unicidade, prefixo da UF, nulo no exterior): PASS

IBGE distintos no Brasil: 5571; nulos no exterior: 186/186; problemas: 0

## (g3) Extra: 1T da base vs soma por UF dos CSVs brutos: PASS

532 comparações UF x coluna; divergências: 0

## (g4) Extra: longo vs largo (linhas, nulos, chaves, células): PASS

longo: 80598 linhas (1T=69084, 2T=11514); células diferentes: 0; problemas: 0

## (g5) Extra: CSV gravado == parquet: PASS

CSV com 5757 linhas e 34 colunas; 28 colunas numéricas comparadas; problemas: 0

## (g6) Informativo: aptos por município mudam entre turnos (total nacional igual): INFO

3779 de 5757 municípios com aptos diferentes entre os turnos; soma das altas 9.524, soma das quedas -9.524, saldo líquido 0

| Município (10 maiores diferenças) | Aptos 1T | Aptos 2T | Dif. |
|---|---|---|---|
| SP/71072 SÃO PAULO | 9.145.124 | 9.145.969 | 845 |
| DF/97012 BRASÍLIA | 2.258.320 | 2.258.995 | 675 |
| PA/04278 BELÉM | 1.048.781 | 1.048.369 | -412 |
| RS/88013 PORTO ALEGRE | 1.064.200 | 1.063.955 | -245 |
| GO/93734 GOIÂNIA | 1.019.261 | 1.019.037 | -224 |
| MG/41238 BELO HORIZONTE | 1.966.966 | 1.966.758 | -208 |
| AM/02550 MANAUS | 1.477.265 | 1.477.075 | -190 |
| RJ/60011 RIO DE JANEIRO | 4.952.612 | 4.952.423 | -189 |
| MA/09210 SÃO LUÍS | 761.443 | 761.263 | -180 |
| PE/24910 OLINDA | 301.943 | 301.766 | -177 |

Hipótese a confirmar (não verificada): ajustes de eleitorado entre turnos, como voto em trânsito ou transferências de seção; o dado só mostra a diferença.

## (g7) Informativo: nome do município no config (2T) vs CSV (1T): INFO

45 nomes diferentes de 5757; 45 só por apóstrofo (config "D'ÁGUA" vs CSV 1T "D ÁGUA"); outras diferenças: 0
