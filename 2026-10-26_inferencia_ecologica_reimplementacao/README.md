# Reimplementação B — inferência ecológica (1º -> 2º turno, presidente 2026)

Reimplementação independente do método de `2026-10-26_inferencia_ecologica/ESPECIFICACAO.md`, escrita só a partir da especificação. Diferença de método computacional: solver FISTA com projeção exata no simplex (Duchi et al., 2008) escrito do zero, sem `scipy.optimize`; equações normais montadas a partir das colunas brutas.

## Como rodar

```
cd 2026-10-26_inferencia_ecologica_reimplementacao
python3 -I executar.py              # B = 1000, ~minutos
python3 -I executar.py --replicas 50   # execução rápida de conferência
```

Entrada: `dados/processados/presidente_municipio_turnos.parquet` (`fl_exterior == False`, 5.571 municípios). Saídas nesta pasta: `transferencias.csv` (`;`, UTF-8, ponto decimal), `transferencias_n_reamostrado.csv` (variante C3), `diagnosticos.md`, `teste_sintetico.md`. Código: `ecologia_b.py` (biblioteca) e `executar.py` (orquestração).

> O IC (bootstrap) mede apenas a variabilidade amostral; NAO captura o viés da hipótese de constância de comportamento dentro da região.

## E1 Brasil (B = 1000) — beta com IC 95%

- **cury**: lula 0.4772 [0.3717; 0.6565] · flavio 0.3335 [0.2198; 0.4009] · branco_nulo 0.1893 [0.1142; 0.2356] · abstencao 0.0000 [0.0000; 0.0540]
- **renan**: lula 0.4663 [0.3431; 0.5666] · flavio 0.4064 [0.3219; 0.5005] · branco_nulo 0.1142 [0.0581; 0.1857] · abstencao 0.0130 [0.0000; 0.0297]
- **caiado**: lula 0.4436 [0.3230; 0.5222] · flavio 0.4162 [0.3413; 0.5112] · branco_nulo 0.1211 [0.0800; 0.1826] · abstencao 0.0191 [0.0057; 0.0363]

- beta[lula->lula] = 0.9924 [0.9887; 0.9948]
- beta[flavio->flavio] = 0.9967 [0.9923; 0.9991]
- beta[abstencao->lula] = 0.0677 [0.0574; 0.0789]
- beta[abstencao->flavio] = 0.0099 [0.0035; 0.0173]

## Qualidade numérica

- Maior cond(G): 1.656e+06
- Maior violação KKT (absoluta): 8.36e-13
- T1 erro máx. de beta: E2 0.0224, E1 Brasil 0.0114
- T2 erro máx. do fluxo de Caiado: E1 12.45%, E2 75.98% do total de Caiado
- Tempo total da execução: 3.5 min
