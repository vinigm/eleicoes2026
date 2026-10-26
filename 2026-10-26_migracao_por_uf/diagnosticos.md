# Diagnósticos — migração de votos por estado (presidente 2026, 1º → 2º turno)

Criado em 26/10/2026. Gerado por `02_estimar_uf.py`. Método: `ESPECIFICACAO.md` desta pasta.

- O IC 95% (bootstrap) mede apenas a variabilidade amostral entre municípios, com kappa fixo em kappa*. Ele NÃO captura o viés da hipótese de constância (dentro do estado, a fração de cada grupo que vai para cada destino é igual em todos os municípios) nem o viés de empurrar o estado para o padrão dos demais.
- κ\* = **4** (ver `validacao_cruzada.md`).

## Alertas

- UF × E1: |Δβ| 0,206 para cury (Nordeste, cury→lula) (limite editorial de alerta: 0,10).
- UF × E1: |Δβ| 0,223 para renan (Sul, renan→lula) (limite editorial de alerta: 0,10).
- UF × E1: |Δβ| 0,320 para caiado (Norte, caiado→branco_nulo) (limite editorial de alerta: 0,10).
- UF_SOZINHO × E1: |Δβ| 0,291 para cury (Nordeste, cury→lula) (limite editorial de alerta: 0,10).
- UF_SOZINHO × E1: |Δβ| 0,331 para renan (Sudeste, renan→lula) (limite editorial de alerta: 0,10).
- UF_SOZINHO × E1: |Δβ| 0,762 para caiado (Norte, caiado→branco_nulo) (limite editorial de alerta: 0,10).
- UF_REGIAO × E1: |Δβ| 0,376 para renan (Centro-Oeste, renan→flavio) (limite editorial de alerta: 0,10).
- UF_REGIAO × E1: |Δβ| 0,374 para caiado (Norte, caiado→branco_nulo) (limite editorial de alerta: 0,10).
- Versão UF com 6 ou mais das 12 células de cury/renan/caiado na fronteira: AC (8/12), AM (6/12), AP (8/12), BA (9/12), ES (7/12), MA (7/12), PI (7/12), RO (7/12), RR (8/12), TO (8/12).
- Erro de validação em κ\* maior que o do padrão da região (razão > 1) em: AM (2,23), CE (1,09), RR (1,10), SE (1,05) (ver `validacao_cruzada.md`).
- DF tem 1 município: o IC do DF reflete só a região (GO + MT + MS); o ponto do DF é 80,0% região.

## Âncoras

- **Status: PASS** (56 verificações inteiras; n efetivo de 27 UFs na tolerância de arredondamento da tabela).
- Totais nacionais dos dois turnos, aptos e municípios por região: idênticos aos da especificação regional.
- 27 UFs com as contagens de municípios da tabela da especificação.

| origem | Σ_u N_u[r] | âncora | situação |
|---|---|---|---|
| lula | 53.722.151 | 53.722.151 | ok |
| flavio | 55.960.603 | 55.960.603 | ok |
| cury | 3.438.835 | 3.438.835 | ok |
| renan | 2.667.307 | 2.667.307 | ok |
| caiado | 2.600.440 | 2.600.440 | ok |
| demais | 580.570 | 580.570 | ok |
| branco_nulo | 5.964.163 | 5.964.163 | ok |
| abstencao | 32.894.899 | 32.894.899 | ok |

| UF | municípios | tabela da especificação | n efetivo (Kish) calculado | tabela da especificação |
|---|---|---|---|---|
| AC | 22 | 22 | 4,59 | 4,6 |
| AL | 102 | 102 | 12,31 | 12,3 |
| AM | 62 | 62 | 3,52 | 3,5 |
| AP | 16 | 16 | 2,93 | 2,9 |
| BA | 417 | 417 | 28,48 | 28,5 |
| CE | 184 | 184 | 13,78 | 13,8 |
| DF | 1 | 1 | 1,00 | 1,0 |
| ES | 78 | 78 | 18,32 | 18,3 |
| GO | 246 | 246 | 18,38 | 18,4 |
| MA | 217 | 217 | 34,44 | 34,4 |
| MG | 853 | 853 | 50,00 | 50,0 |
| MS | 79 | 79 | 8,62 | 8,6 |
| MT | 142 | 142 | 20,50 | 20,5 |
| PA | 144 | 144 | 24,90 | 24,9 |
| PB | 223 | 223 | 21,11 | 21,1 |
| PE | 185 | 185 | 23,27 | 23,3 |
| PI | 224 | 224 | 18,28 | 18,3 |
| PR | 399 | 399 | 27,35 | 27,3 |
| RJ | 92 | 92 | 6,17 | 6,2 |
| RN | 167 | 167 | 16,70 | 16,7 |
| RO | 52 | 52 | 9,33 | 9,3 |
| RR | 15 | 15 | 2,67 | 2,7 |
| RS | 497 | 497 | 40,69 | 40,7 |
| SC | 295 | 295 | 44,38 | 44,4 |
| SE | 75 | 75 | 13,14 | 13,1 |
| SP | 645 | 645 | 12,97 | 13,0 |
| TO | 139 | 139 | 18,26 | 18,3 |

## Peso da região por estado

- Peso da região = `κ / (n_u + κ)`: a região entra como κ municípios a mais contra `n_u` municípios efetivos do estado.
- Menor peso (versão UF): **MG 7,4%**; maior: **DF 80,0%**.

| UF | região | municípios | n efetivo | peso da região UF (κ=4), % | peso UF_SOZINHO (κ=0,25), % | peso UF_REGIAO (κ=∞), % |
|---|---|---|---|---|---|---|
| AC | Norte | 22 | 4,6 | 46,6 | 5,2 | 100,0 |
| AL | Nordeste | 102 | 12,3 | 24,5 | 2,0 | 100,0 |
| AM | Norte | 62 | 3,5 | 53,2 | 6,6 | 100,0 |
| AP | Norte | 16 | 2,9 | 57,7 | 7,9 | 100,0 |
| BA | Nordeste | 417 | 28,5 | 12,3 | 0,9 | 100,0 |
| CE | Nordeste | 184 | 13,8 | 22,5 | 1,8 | 100,0 |
| DF | Centro-Oeste | 1 | 1,0 | 80,0 | 20,0 | 100,0 |
| ES | Sudeste | 78 | 18,3 | 17,9 | 1,3 | 100,0 |
| GO | Centro-Oeste | 246 | 18,4 | 17,9 | 1,3 | 100,0 |
| MA | Nordeste | 217 | 34,4 | 10,4 | 0,7 | 100,0 |
| MG | Sudeste | 853 | 50,0 | 7,4 | 0,5 | 100,0 |
| MS | Centro-Oeste | 79 | 8,6 | 31,7 | 2,8 | 100,0 |
| MT | Centro-Oeste | 142 | 20,5 | 16,3 | 1,2 | 100,0 |
| PA | Norte | 144 | 24,9 | 13,8 | 1,0 | 100,0 |
| PB | Nordeste | 223 | 21,1 | 15,9 | 1,2 | 100,0 |
| PE | Nordeste | 185 | 23,3 | 14,7 | 1,1 | 100,0 |
| PI | Nordeste | 224 | 18,3 | 18,0 | 1,3 | 100,0 |
| PR | Sul | 399 | 27,3 | 12,8 | 0,9 | 100,0 |
| RJ | Sudeste | 92 | 6,2 | 39,3 | 3,9 | 100,0 |
| RN | Nordeste | 167 | 16,7 | 19,3 | 1,5 | 100,0 |
| RO | Norte | 52 | 9,3 | 30,0 | 2,6 | 100,0 |
| RR | Norte | 15 | 2,7 | 60,0 | 8,6 | 100,0 |
| RS | Sul | 497 | 40,7 | 9,0 | 0,6 | 100,0 |
| SC | Sul | 295 | 44,4 | 8,3 | 0,6 | 100,0 |
| SE | Nordeste | 75 | 13,1 | 23,3 | 1,9 | 100,0 |
| SP | Sudeste | 645 | 13,0 | 23,6 | 1,9 | 100,0 |
| TO | Norte | 139 | 18,3 | 18,0 | 1,4 | 100,0 |

## Células de β na fronteira (= 0 ou = 1)

- Tolerância de 1e-6. Fronteira ativa indica tensão do modelo (a restrição `0 ≤ β ≤ 1` está pesando).
- Cada estado tem 32 células. Contagem por versão:

| UF | UF (κ\*) | UF_SOZINHO | UF_REGIAO |
|---|---|---|---|
| AC | 20 | 22 | 20 |
| AL | 17 | 22 | 16 |
| AM | 20 | 17 | 15 |
| AP | 21 | 21 | 17 |
| BA | 21 | 23 | 15 |
| CE | 16 | 18 | 16 |
| DF | 16 | 17 | 15 |
| ES | 17 | 16 | 13 |
| GO | 16 | 17 | 19 |
| MA | 18 | 17 | 16 |
| MG | 14 | 14 | 17 |
| MS | 12 | 13 | 16 |
| MT | 16 | 16 | 17 |
| PA | 16 | 18 | 18 |
| PB | 17 | 20 | 17 |
| PE | 19 | 19 | 16 |
| PI | 19 | 14 | 17 |
| PR | 15 | 16 | 17 |
| RJ | 14 | 17 | 15 |
| RN | 15 | 15 | 17 |
| RO | 20 | 17 | 18 |
| RR | 21 | 25 | 19 |
| RS | 19 | 19 | 13 |
| SC | 15 | 15 | 15 |
| SE | 17 | 15 | 16 |
| SP | 15 | 15 | 13 |
| TO | 20 | 17 | 20 |

- Células na fronteira da versão **UF** (κ\*):

- **AC** (20): lula→flavio=0, lula→branco_nulo=0, flavio→lula=0, cury→branco_nulo=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→lula=0, caiado→flavio=1, caiado→branco_nulo=0, caiado→abstencao=0, demais→lula=1, demais→flavio=0, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, abstencao→lula=0, abstencao→flavio=0, abstencao→branco_nulo=0, abstencao→abstencao=1
- **AL** (17): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→abstencao=0, cury→flavio=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, abstencao→flavio=0
- **AM** (20): lula→flavio=0, flavio→lula=0, cury→flavio=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→flavio=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→lula=1, branco_nulo→flavio=0, branco_nulo→branco_nulo=0, branco_nulo→abstencao=0, abstencao→lula=0, abstencao→flavio=0, abstencao→branco_nulo=0, abstencao→abstencao=1
- **AP** (21): lula→flavio=0, lula→branco_nulo=0, flavio→abstencao=0, cury→flavio=0, cury→branco_nulo=0, renan→lula=1, renan→flavio=0, renan→branco_nulo=0, renan→abstencao=0, caiado→flavio=0, caiado→abstencao=0, demais→lula=1, demais→flavio=0, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→lula=1, branco_nulo→flavio=0, branco_nulo→branco_nulo=0, branco_nulo→abstencao=0, abstencao→lula=0, abstencao→flavio=0
- **BA** (21): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, renan→lula=1, renan→flavio=0, renan→branco_nulo=0, renan→abstencao=0, caiado→lula=1, caiado→flavio=0, caiado→branco_nulo=0, caiado→abstencao=0, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0
- **CE** (16): lula→flavio=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→flavio=0
- **DF** (16): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, renan→abstencao=0, demais→lula=0, demais→flavio=0, demais→branco_nulo=1, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0
- **ES** (17): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→lula=0, caiado→flavio=1, caiado→branco_nulo=0, caiado→abstencao=0, demais→lula=1, demais→flavio=0, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→abstencao=0
- **GO** (16): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, renan→abstencao=0, demais→lula=0, demais→flavio=0, demais→branco_nulo=1, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0
- **MA** (18): lula→flavio=0, flavio→abstencao=0, cury→flavio=0, cury→abstencao=0, renan→lula=1, renan→flavio=0, renan→branco_nulo=0, renan→abstencao=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→lula=1, branco_nulo→flavio=0, branco_nulo→branco_nulo=0, branco_nulo→abstencao=0, abstencao→flavio=0
- **MG** (14): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, renan→abstencao=0, caiado→abstencao=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0
- **MS** (12): lula→flavio=0, lula→branco_nulo=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, renan→abstencao=0, demais→flavio=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0
- **MT** (16): lula→flavio=0, lula→branco_nulo=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→flavio=0, cury→abstencao=0, renan→abstencao=0, caiado→abstencao=0, demais→lula=1, demais→flavio=0, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0
- **PA** (16): lula→flavio=0, flavio→lula=0, flavio→abstencao=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→lula=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→lula=0, abstencao→flavio=0
- **PB** (17): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→abstencao=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→flavio=0
- **PE** (19): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→flavio=0
- **PI** (19): lula→flavio=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→flavio=0, cury→abstencao=0, renan→lula=1, renan→flavio=0, renan→branco_nulo=0, renan→abstencao=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→flavio=0
- **PR** (15): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, caiado→lula=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0
- **RJ** (14): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→branco_nulo=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→abstencao=0, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0
- **RN** (15): lula→flavio=0, flavio→lula=0, flavio→abstencao=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→branco_nulo=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→flavio=0
- **RO** (20): lula→flavio=0, lula→branco_nulo=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→flavio=0, renan→lula=1, renan→flavio=0, renan→branco_nulo=0, renan→abstencao=0, caiado→lula=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→lula=0
- **RR** (21): lula→flavio=0, lula→branco_nulo=0, flavio→lula=0, flavio→branco_nulo=0, cury→branco_nulo=0, cury→abstencao=0, renan→lula=0, renan→flavio=1, renan→branco_nulo=0, renan→abstencao=0, caiado→lula=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→lula=1, branco_nulo→flavio=0, branco_nulo→branco_nulo=0, branco_nulo→abstencao=0, abstencao→lula=0
- **RS** (19): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→lula=0, renan→abstencao=0, caiado→lula=0, demais→lula=1, demais→flavio=0, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→flavio=0, abstencao→branco_nulo=0
- **SC** (15): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, renan→lula=0, renan→abstencao=0, caiado→abstencao=0, demais→flavio=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0
- **SE** (17): lula→flavio=0, lula→branco_nulo=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→flavio=0
- **SP** (15): lula→lula=1, lula→flavio=0, lula→branco_nulo=0, lula→abstencao=0, flavio→lula=0, flavio→flavio=1, flavio→branco_nulo=0, flavio→abstencao=0, cury→abstencao=0, renan→abstencao=0, caiado→abstencao=0, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0
- **TO** (20): lula→flavio=0, flavio→abstencao=0, cury→lula=1, cury→flavio=0, cury→branco_nulo=0, cury→abstencao=0, renan→branco_nulo=0, renan→abstencao=0, caiado→flavio=0, caiado→abstencao=0, demais→lula=0, demais→flavio=1, demais→branco_nulo=0, demais→abstencao=0, branco_nulo→flavio=0, branco_nulo→abstencao=0, abstencao→lula=0, abstencao→flavio=0, abstencao→branco_nulo=0, abstencao→abstencao=1

## Número de condição de G

- Limite de alerta: 1,00e+08.
- Maior cond(G) nos ajustes pontuais (3 versões x 27 estados): **6,91e+06**.
- Maior cond(G) nos 13500 ajustes do bootstrap: **6,19e+06** (após a reescala por √G_rr do solver: 2,38e+03).
- A condição alta de G vem dos grupos minúsculos (ex.: `demais`, ~0,4% dos aptos); o solver reescala as variáveis por √G_rr (mesmo ótimo em β).
- G é definida positiva em todos os estados (inclusive DF) porque `G_{g\u}` é.

| UF | cond(G) UF | cond(G) UF após reescala | cond(G) UF_SOZINHO | cond(G) UF_REGIAO |
|---|---|---|---|---|
| AC | 9,81e+05 | 6,53e+02 | 1,34e+06 | 1,52e+06 |
| AL | 1,97e+06 | 7,39e+02 | 2,67e+06 | 1,56e+06 |
| AM | 1,72e+06 | 5,16e+02 | 3,82e+06 | 1,36e+06 |
| AP | 1,22e+06 | 5,65e+02 | 2,55e+06 | 1,57e+06 |
| BA | 2,46e+06 | 5,36e+02 | 3,04e+06 | 1,42e+06 |
| CE | 2,44e+06 | 6,93e+02 | 3,58e+06 | 1,46e+06 |
| DF | 9,46e+05 | 8,95e+02 | 3,69e+06 | 7,79e+05 |
| ES | 1,79e+05 | 9,46e+02 | 5,25e+05 | 6,30e+04 |
| GO | 1,18e+06 | 1,01e+03 | 2,01e+06 | 8,94e+05 |
| MA | 1,29e+06 | 6,30e+02 | 1,42e+06 | 1,75e+06 |
| MG | 3,66e+04 | 4,88e+02 | 4,97e+04 | 6,42e+05 |
| MS | 1,02e+06 | 8,08e+02 | 1,54e+06 | 1,06e+06 |
| MT | 6,84e+05 | 1,02e+03 | 7,10e+05 | 1,43e+06 |
| PA | 1,98e+06 | 6,08e+02 | 2,85e+06 | 1,38e+06 |
| PB | 1,74e+06 | 7,13e+02 | 2,20e+06 | 1,57e+06 |
| PE | 1,59e+06 | 6,77e+02 | 1,71e+06 | 1,61e+06 |
| PI | 1,84e+06 | 4,34e+02 | 1,94e+06 | 1,53e+06 |
| PR | 3,90e+05 | 7,41e+02 | 4,91e+05 | 2,56e+05 |
| RJ | 1,17e+05 | 7,32e+02 | 7,40e+05 | 5,57e+04 |
| RN | 1,89e+06 | 7,14e+02 | 2,46e+06 | 1,56e+06 |
| RO | 1,75e+06 | 9,61e+02 | 2,28e+06 | 1,44e+06 |
| RR | 2,03e+06 | 4,76e+02 | 6,91e+06 | 1,37e+06 |
| RS | 3,17e+05 | 6,44e+02 | 3,31e+05 | 2,72e+05 |
| SC | 2,35e+05 | 7,99e+02 | 2,37e+05 | 3,42e+05 |
| SE | 1,93e+06 | 8,54e+02 | 2,61e+06 | 1,57e+06 |
| SP | 1,01e+05 | 9,07e+02 | 3,59e+05 | 4,64e+04 |
| TO | 1,51e+06 | 6,44e+02 | 1,84e+06 | 1,70e+06 |

## Convergência e estabilidade do solver

- Todo ajuste exige `success` do SLSQP, viabilidade (soma e limites a 1e-8) e lacuna de dualidade de Frank-Wolfe ≤ 1e-7. Falha = exceção.
- Ajustes pontuais: 81 (3 versões x 27 UFs); **zero falhas**; maior lacuna de dualidade **5,86e-09**.
- Bootstrap: 13500 ajustes; **zero falhas**; maior lacuna **1,59e-08**.
- Ajustes que precisaram do ponto inicial uniforme de reserva (a 1ª tentativa, de ponto "quente", ficou acima do limite de certificação; critério não relaxado): pontuais **0**, bootstrap **0**.
- Unicidade (G definida positiva): o ótimo não depende do ponto inicial. Verificação empírica, reajustando os 27 estados a partir de outro ponto inicial (UF e UF_SOZINHO: uniforme em vez da solução da região; UF_REGIAO: solução de UF em vez do uniforme):

| versão | maior diferença absoluta em β entre dois pontos iniciais |
|---|---|
| UF | 1,01e-06 |
| UF_SOZINHO | 1,93e-06 |
| UF_REGIAO | 1,41e-06 |

## Ajuste (dentro da amostra, Brasil)

- Total previsto = `Σ_i aptos_2t_i · (X_i β_estado(i))_c`; R² ponderado por `aptos_1t`.
- É ajuste DENTRO da amostra: UF_SOZINHO tende a ajustar melhor aqui por construção; quem mede desempenho fora da amostra é a validação cruzada.

| destino | real | previsto UF | previsto UF_SOZINHO | previsto UF_REGIAO |
|---|---|---|---|---|
| lula | 64.056.078 | 64.057.112 | 64.049.422 | 64.024.327 |
| flavio | 59.654.544 | 59.666.983 | 59.671.793 | 59.308.933 |
| branco_nulo | 4.144.009 | 4.112.143 | 4.114.883 | 4.361.578 |
| abstencao | 29.974.188 | 29.992.581 | 29.992.721 | 30.133.981 |

| destino | R² UF | R² UF_SOZINHO | R² UF_REGIAO |
|---|---|---|---|
| lula | 0,9954 | 0,9956 | 0,9908 |
| flavio | 0,9962 | 0,9966 | 0,9878 |
| branco_nulo | 0,8616 | 0,8796 | -0,3722 |
| abstencao | 0,8954 | 0,9060 | 0,7897 |

## Coerência com o E1 (modelo regional)

- Soma dos fluxos dos estados por região e no Brasil → β agregado; comparado ao β do E1 (`../2026-10-26_inferencia_ecologica/transferencias.csv`).
- Os modelos são diferentes: **não precisam bater**. A diferença é reportada, não corrigida.
- Maior diferença absoluta em β (entre as 4 destinações e entre as 5 regiões + Brasil), por origem e versão, com o local:

| versão | cury | renan | caiado |
|---|---|---|---|
| UF | 0,206 (Nordeste, cury→lula) | 0,223 (Sul, renan→lula) | 0,320 (Norte, caiado→branco_nulo) |
| UF_SOZINHO | 0,291 (Nordeste, cury→lula) | 0,331 (Sudeste, renan→lula) | 0,762 (Norte, caiado→branco_nulo) |
| UF_REGIAO | 0,085 (Sul, cury→flavio) | 0,376 (Centro-Oeste, renan→flavio) | 0,374 (Norte, caiado→branco_nulo) |

- Detalhe da versão UF: maior |Δβ| por região (sobre as 4 destinações):

| origem (UF) | Centro-Oeste | Nordeste | Norte | Sudeste | Sul | Brasil |
|---|---|---|---|---|---|---|
| cury | 0,135 | 0,206 | 0,086 | 0,018 | 0,047 | 0,045 |
| renan | 0,115 | 0,073 | 0,195 | 0,117 | 0,223 | 0,100 |
| caiado | 0,028 | 0,158 | 0,320 | 0,127 | 0,055 | 0,084 |

## Bootstrap

- B = **500** réplicas, semente **20261025**, só para a versão `UF`.
- Reamostragem de municípios com reposição **dentro de cada estado**; o termo da região usa os municípios reamostrados dos outros estados da mesma réplica.
- **κ fica fixo em κ\* = 4**; não é reescolhido por réplica (o IC ignora a incerteza de κ).
- O n efetivo de Kish `n_u` é recalculado em cada réplica sobre os municípios reamostrados (cada cópia conta como uma linha), então o peso da região varia entre réplicas.
- `N_u[r]` (contagem do grupo no estado) é observado e fixo; os votos de cada réplica são `β · N_u[r]`.
- **DF:** a reamostragem do próprio estado é degenerada (1 município, sempre ele mesmo); o intervalo do DF reflete só a região (GO + MT + MS reamostrados).
- Células (UF x origem x destino) com β pontual FORA do IC percentil: **0 de 864** (0,00%).
- Tempo do bootstrap: 31,0 s (serial).
- O IC 95% (bootstrap) mede apenas a variabilidade amostral entre municípios, com kappa fixo em kappa*. Ele NÃO captura o viés da hipótese de constância (dentro do estado, a fração de cada grupo que vai para cada destino é igual em todos os municípios) nem o viés de empurrar o estado para o padrão dos demais.
- `UF_SOZINHO` e `UF_REGIAO` saem sem intervalo (colunas de IC vazias).
