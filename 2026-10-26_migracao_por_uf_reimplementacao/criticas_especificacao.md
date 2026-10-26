# Evidências para as críticas à especificação (implementação B)

## Fração de municípios da dobra 0 por UF (`cd_municipio_tse mod 5 == 0`)

| UF | municípios | % na dobra 0 | % dos aptos_1t na dobra 0 |
|---|---|---|---|
| AC | 22 | 27.3 | 10.6 |
| AL | 102 | 27.5 | 41.3 |
| AM | 62 | 27.4 | 67.9 |
| AP | 16 | 18.8 | 63.3 |
| BA | 417 | 28.1 | 36.4 |
| CE | 184 | 28.8 | 20.9 |
| DF | 1 | 0.0 | 0.0 |
| ES | 78 | 26.9 | 28.1 |
| GO | 246 | 29.3 | 32.2 |
| MA | 217 | 27.6 | 35.3 |
| MG | 853 | 27.2 | 27.9 |
| MS | 79 | 29.1 | 28.3 |
| MT | 142 | 26.1 | 47.6 |
| PA | 144 | 27.8 | 22.7 |
| PB | 223 | 27.4 | 28.9 |
| PE | 185 | 28.1 | 32.1 |
| PI | 224 | 26.8 | 41.5 |
| PR | 399 | 27.3 | 21.0 |
| RJ | 92 | 26.1 | 18.2 |
| RN | 167 | 26.9 | 28.4 |
| RO | 52 | 25.0 | 39.4 |
| RR | 15 | 26.7 | 13.6 |
| RS | 497 | 27.2 | 26.0 |
| SC | 295 | 27.8 | 35.6 |
| SE | 75 | 26.7 | 26.0 |
| SP | 645 | 27.3 | 23.1 |
| TO | 139 | 24.5 | 43.1 |

## kappa* sob partições alternativas das dobras

| partição | kappa* | erro(kappa*) | erro(inf)/erro(kappa*) |
|---|---|---|---|
| `mod 5` (especificação) | 4 | 52167.26 | 1.941 |
| `(cd // 5) mod 5` | 2 | 53123.72 | 1.906 |
| aleatória, semente 20261025 | 8 | 53258.40 | 1.902 |
| aleatória, semente 1 | 4 | 53144.35 | 1.906 |
| aleatória, semente 2 | 4 | 54606.25 | 1.855 |
