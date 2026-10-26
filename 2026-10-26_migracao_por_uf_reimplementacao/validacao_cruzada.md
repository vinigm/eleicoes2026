# Validação cruzada de kappa (implementação B)

5 dobras por `int(cd_municipio_tse) mod 5`. Erro = soma de `w_i * ||Y_i - X_i beta_u||^2` nos municípios de teste, somado em UFs e dobras, `w_i = aptos_1t`. Total de ajustes: 1572; não convergidos: 0; maior violação KKT: 1.17e-13 (relativa 3.49e-13).

## kappa* = 4

- Erro em kappa*: **52167.26**; em kappa = 0,25: **53086.37**; em kappa = inf (padrão da região): **101275.86**.
- kappa* na borda da grade: **não**.

## Curva de erro

| kappa | erro total | erro / erro(kappa*) | (erro - erro*) / EP |
|---|---|---|---|
| 0.25 | 53086.37 | 1.0176 | 0.40 |
| 0.5 | 52867.28 | 1.0134 | 0.34 |
| 1 | 52386.27 | 1.0042 | 0.14 |
| 2 | 52174.01 | 1.0001 | 0.01 |
| 4 **(kappa*)** | 52167.26 | 1.0000 | — |
| 8 | 53353.92 | 1.0227 | 1.22 |
| 16 | 56132.08 | 1.0760 | 1.92 |
| 32 | 60416.95 | 1.1581 | 2.67 |
| 64 | 65914.12 | 1.2635 | 3.55 |
| 128 | 72032.95 | 1.3808 | 4.48 |
| 256 | 77874.58 | 1.4928 | 5.23 |
| inf | 101275.86 | 1.9414 | 5.58 |

EP = erro padrão aproximado da diferença, tratando cada par (UF, dobra) como unidade independente (régua grosseira; as 135 unidades têm pesos muito desiguais).

## Heterogeneidade entre UFs (crítica ao kappa único)

kappa ótimo por UF (argmin do erro da própria UF na grade finita) e erro em kappa* relativo ao erro da própria UF em kappa = inf.

| UF | n_u | % do erro total em kappa* | kappa ótimo da UF | erro(kappa*) / erro(inf) |
|---|---|---|---|---|
| AC | 4.6 | 4.9 | 1 | 0.592 |
| AL | 12.3 | 4.2 | 0.25 | 0.715 |
| AM | 3.5 | 9.4 | 256 | 2.226 |
| AP | 2.9 | 5.0 | 0.25 | 0.535 |
| BA | 28.5 | 8.1 | 2 | 0.506 |
| CE | 13.8 | 3.5 | 256 | 1.089 |
| DF | 1.0 | 0.7 | indiferente (UF sem município de treino na dobra de teste) | 1.000 |
| ES | 18.3 | 0.5 | 0.25 | 0.197 |
| GO | 18.4 | 2.6 | 4 | 0.099 |
| MA | 34.4 | 7.1 | 1 | 0.357 |
| MG | 50.0 | 6.1 | 16 | 0.802 |
| MS | 8.6 | 1.7 | 1 | 0.704 |
| MT | 20.5 | 1.3 | 0.25 | 0.545 |
| PA | 24.9 | 7.0 | 0.25 | 0.354 |
| PB | 21.1 | 1.5 | 0.25 | 0.965 |
| PE | 23.3 | 2.6 | 0.25 | 0.380 |
| PI | 18.3 | 2.3 | 2 | 0.437 |
| PR | 27.3 | 2.3 | 1 | 0.813 |
| RJ | 6.2 | 7.3 | 2 | 0.555 |
| RN | 16.7 | 2.3 | 4 | 0.921 |
| RO | 9.3 | 0.6 | 2 | 0.243 |
| RR | 2.7 | 5.6 | 64 | 1.102 |
| RS | 40.7 | 2.6 | 0.25 | 0.667 |
| SC | 44.4 | 1.5 | 4 | 0.698 |
| SE | 13.1 | 0.6 | 64 | 1.047 |
| SP | 13.0 | 7.8 | 0.25 | 0.449 |
| TO | 18.3 | 0.8 | 1 | 0.472 |

## Sensibilidade de kappa* ao critério de agregação

- Critério da especificação (soma bruta): kappa* = **4**.
- Média dos erros relativos por UF (cada UF dividida pelo próprio erro em kappa = inf): kappa = **4**.
- Sem as 3 UFs de maior erro (AM, BA, SP; 25.3% do erro): kappa = **1**.

## Equilíbrio das dobras (`cd_municipio_tse mod 5`)

| dobra | municípios | % dos aptos_1t |
|---|---|---|
| 0 | 1524 | 27.9 |
| 1 | 1011 | 16.8 |
| 2 | 1012 | 22.6 |
| 3 | 1013 | 19.7 |
| 4 | 1011 | 13.0 |
