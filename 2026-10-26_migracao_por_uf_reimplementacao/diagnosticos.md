# Diagnósticos (implementação B)

O IC (bootstrap) mede só a variabilidade amostral dentro de cada UF, com kappa e n_u fixos; NÃO captura o viés de a UF ser puxada para o padrão da região (nem o viés de a hipótese de constância falhar).

## Convergência e KKT dos ajustes pontuais

Violação KKT medida em G, H normalizados (pesos somando 1). Estacionariedade: `|g_rc - mu_r|` no suporte; complementaridade: `max(mu_r - g_rc, 0)` fora do suporte; relativa = absoluta / (2 max|H|).

| versão | kappa | KKT abs. máx | KKT rel. máx | resíduo grad. proj. máx | iterações máx | todos convergiram |
|---|---|---|---|---|---|---|
| UF | 4 | 8.68e-14 | 1.82e-13 | 1.31e-13 | 15761 | True |
| UF_SOZINHO | 0.25 | 5.36e-14 | 1.17e-13 | 8.06e-14 | 15471 | True |
| UF_REGIAO | inf | 6.99e-14 | 2.23e-13 | 1.26e-13 | 14625 | True |
| E1 regional refeito (5 regiões) | — | 1.58e-14 | — | — | — | — |

Bootstrap UF (B=500 x 27 UFs): KKT abs. máx **1.37e-13**, não convergidos 0.

## Peso da região, fronteira e condicionamento por UF

`peso região = kappa/(n_u+kappa)` em %. Fronteira = células de beta (de 32) a menos de 1e-9 de 0 ou 1. Cond(G) = lambda_max/lambda_min da matriz normalizada do ajuste `UF`.

| UF | região | n_u | peso região UF (%) | peso região UF_SOZINHO (%) | fronteira UF | fronteira UF_SOZINHO | fronteira UF_REGIAO | cond(G) UF | cond(G) UF_SOZINHO | cond(G) UF_REGIAO |
|---|---|---|---|---|---|---|---|---|---|---|
| AC | Norte | 4.59 | 46.6 | 5.2 | 20 | 22 | 20 | 9.81e+05 | 1.34e+06 | 1.52e+06 |
| AL | Nordeste | 12.31 | 24.5 | 2.0 | 17 | 22 | 16 | 1.97e+06 | 2.67e+06 | 1.56e+06 |
| AM | Norte | 3.52 | 53.2 | 6.6 | 20 | 17 | 15 | 1.72e+06 | 3.82e+06 | 1.36e+06 |
| AP | Norte | 2.93 | 57.7 | 7.9 | 21 | 21 | 17 | 1.22e+06 | 2.55e+06 | 1.57e+06 |
| BA | Nordeste | 28.48 | 12.3 | 0.9 | 21 | 23 | 15 | 2.46e+06 | 3.04e+06 | 1.42e+06 |
| CE | Nordeste | 13.78 | 22.5 | 1.8 | 16 | 18 | 16 | 2.44e+06 | 3.58e+06 | 1.46e+06 |
| DF | Centro-Oeste | 1.00 | 80.0 | 20.0 | 16 | 17 | 15 | 9.46e+05 | 3.69e+06 | 7.79e+05 |
| ES | Sudeste | 18.32 | 17.9 | 1.3 | 17 | 16 | 13 | 1.79e+05 | 5.25e+05 | 6.3e+04 |
| GO | Centro-Oeste | 18.38 | 17.9 | 1.3 | 16 | 17 | 19 | 1.18e+06 | 2.01e+06 | 8.94e+05 |
| MA | Nordeste | 34.44 | 10.4 | 0.7 | 18 | 17 | 16 | 1.29e+06 | 1.42e+06 | 1.75e+06 |
| MG | Sudeste | 50.00 | 7.4 | 0.5 | 14 | 14 | 17 | 3.66e+04 | 4.97e+04 | 6.42e+05 |
| MS | Centro-Oeste | 8.62 | 31.7 | 2.8 | 12 | 13 | 16 | 1.02e+06 | 1.54e+06 | 1.06e+06 |
| MT | Centro-Oeste | 20.50 | 16.3 | 1.2 | 16 | 16 | 17 | 6.84e+05 | 7.1e+05 | 1.43e+06 |
| PA | Norte | 24.90 | 13.8 | 1.0 | 16 | 18 | 18 | 1.98e+06 | 2.85e+06 | 1.38e+06 |
| PB | Nordeste | 21.11 | 15.9 | 1.2 | 17 | 20 | 17 | 1.74e+06 | 2.2e+06 | 1.57e+06 |
| PE | Nordeste | 23.27 | 14.7 | 1.1 | 19 | 19 | 16 | 1.59e+06 | 1.71e+06 | 1.61e+06 |
| PI | Nordeste | 18.28 | 18.0 | 1.3 | 19 | 14 | 17 | 1.84e+06 | 1.94e+06 | 1.53e+06 |
| PR | Sul | 27.35 | 12.8 | 0.9 | 15 | 16 | 17 | 3.9e+05 | 4.91e+05 | 2.56e+05 |
| RJ | Sudeste | 6.17 | 39.3 | 3.9 | 14 | 17 | 15 | 1.17e+05 | 7.4e+05 | 5.57e+04 |
| RN | Nordeste | 16.70 | 19.3 | 1.5 | 15 | 15 | 17 | 1.89e+06 | 2.46e+06 | 1.56e+06 |
| RO | Norte | 9.33 | 30.0 | 2.6 | 20 | 17 | 18 | 1.75e+06 | 2.28e+06 | 1.44e+06 |
| RR | Norte | 2.67 | 60.0 | 8.6 | 21 | 25 | 19 | 2.03e+06 | 6.91e+06 | 1.37e+06 |
| RS | Sul | 40.69 | 9.0 | 0.6 | 19 | 19 | 13 | 3.17e+05 | 3.31e+05 | 2.72e+05 |
| SC | Sul | 44.38 | 8.3 | 0.6 | 15 | 15 | 15 | 2.35e+05 | 2.37e+05 | 3.42e+05 |
| SE | Nordeste | 13.14 | 23.3 | 1.9 | 17 | 15 | 16 | 1.93e+06 | 2.61e+06 | 1.57e+06 |
| SP | Sudeste | 12.97 | 23.6 | 1.9 | 15 | 15 | 13 | 1.01e+05 | 3.59e+05 | 4.64e+04 |
| TO | Norte | 18.26 | 18.0 | 1.4 | 20 | 17 | 20 | 1.51e+06 | 1.84e+06 | 1.7e+06 |

Total de células na fronteira: UF 466; UF_SOZINHO 475; UF_REGIAO 443 (de 864 cada).

## Plausibilidade (só reportar)

- UF: min beta[lula->lula] = 0.9286 (AP); min beta[flavio->flavio] = 0.8949 (RR).
- UF_SOZINHO: min beta[lula->lula] = 0.7889 (AP); min beta[flavio->flavio] = 0.8655 (RR).
- UF_REGIAO: min beta[lula->lula] = 0.9438 (AC); min beta[flavio->flavio] = 0.9648 (RO).

## Coerência com o E1 regional (refeito aqui com o mesmo solver)

Diferença máxima, em regiões e colunas, entre beta agregado (soma dos fluxos das UFs / soma de N_u) e o beta do E1 da região. Não precisam bater: são modelos diferentes.

| versão | caiado | cury | renan |
|---|---|---|---|
| UF | 0.3196 | 0.2057 | 0.2225 |
| UF_SOZINHO | 0.7619 | 0.2912 | 0.3306 |
| UF_REGIAO | 0.3737 | 0.0850 | 0.3764 |

## Sensibilidades do bootstrap

- Votos com N_u reamostrado (em vez de N_u observado): razão mediana das larguras de IC = **1.245** (nas células das linhas caiado, cury e renan).
- n_u recalculado em cada réplica (em vez de fixo): razão da largura do IC de beta, mediana **1.019**, mínimo 0.000, máximo 39.040.
- DF: a reamostragem do próprio estado é degenerada (1 município); o IC do DF reflete só a região.
- kappa fixo em kappa* = 4; n_u fixo no valor observado.
