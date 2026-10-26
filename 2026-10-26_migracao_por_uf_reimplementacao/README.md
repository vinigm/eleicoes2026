# Migração de votos por UF — reimplementação independente (B)

Criado em 26/10/2026. Segue `2026-10-26_migracao_por_uf/ESPECIFICACAO.md` (que por sua vez remete ao método regional). Pergunta: para onde foram, no 2º turno, os eleitores de Caiado, Cury e Renan (e os demais grupos), estado a estado, com cada estado puxado para o padrão dos demais estados da sua região.

## Como rodar (a partir desta pasta)

```
python3 -I executar.py            # CV de kappa, 3 versões, bootstrap B=500 (~12 min)
python3 -I teste_sintetico.py     # teste sintético (seção 7), 6 sementes + cobertura do bootstrap (~14 min)
python3 -I analise_criticas_spec.py   # kappa* sob outras partições de dobras (~3 min)
python3 -I testes_montagem.py     # objetivo direto vs. G,H montados; E1 vs. regional B
```

## Diferença em relação à implementação A

- Sem `scipy`. Solver = FISTA com reinício + projeção exata no simplex (Duchi et al.), importado de `../2026-10-26_inferencia_ecologica_reimplementacao/ecologia_b.py` sem alterá-lo.
- X/Y, estatísticas suficientes por UF e por "região sem a UF", CV e bootstrap escritos aqui (`migracao_uf_b.py`).
- Não foi lido nada de `2026-10-26_migracao_por_uf/` além da especificação, nem de `2026-10-26_inferencia_ecologica/` além da especificação. O E1 regional do diagnóstico de coerência foi refeito aqui com o mesmo solver.

## Arquivos

- `transferencias_uf.csv`: 2.592 linhas (27 UFs x 3 versões x 32 células), `;`, UTF-8. `kappa = inf` em `UF_REGIAO`; IC só em `UF`.
- `validacao_cruzada.md`, `diagnosticos.md`, `teste_sintetico.md`, `criticas_especificacao.md`.

## Números principais

- Âncoras: 74 conferências exatas (totais nacionais 1º/2º turno, 5.571 municípios, municípios por região e por UF, n efetivo da tabela da seção 1) todas OK.
- kappa* = **4** (interior da grade). Erro de validação: 52.167 em kappa*, 53.086 em 0,25, 101.276 em kappa = inf.
- Maior violação KKT: 1,4e-13 (pontuais 8,7e-14; CV 1,2e-13; bootstrap 1,4e-13). Nenhum ajuste deixou de convergir.
- Decisões onde a especificação é omissa: n_u fixo no valor observado nas réplicas do bootstrap; N_u (votos) fixo, não reamostrado; `UF_REGIAO` do DF = GO+MT+MS.
- O IC mede só variabilidade amostral dentro de cada UF; não captura o encolhimento para a região nem a falha da hipótese de constância.
