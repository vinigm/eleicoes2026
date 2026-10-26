# Migração de votos por estado, puxada para a região (presidente 2026, 1º → 2º turno)

Criado em 26/10/2026. Implementação **A** de `ESPECIFICACAO.md` desta pasta (a fonte de verdade do método; esta pasta não a altera). Base de categorias, denominadores, restrições e âncoras: `../2026-10-26_inferencia_ecologica/ESPECIFICACAO.md`.

## O que responde

- Para onde foram, no 2º turno, os eleitores de **Cury**, **Renan** e **Caiado**, **estado por estado**.
- Cada estado é estimado com os próprios municípios **mais** o padrão dos demais estados da região (sem o próprio estado), como `κ` municípios a mais contra `n_u` municípios efetivos (Kish) do estado.
- `κ*` é escolhido por validação cruzada (5 dobras, `int(cd_municipio_tse) mod 5`), um único para os 27 estados.
- Três versões: `UF` (κ = κ\*, com IC), `UF_SOZINHO` (κ = 0,25) e `UF_REGIAO` (κ = ∞, só os demais estados da região).

## Como rodar

```
python3 -I 01_validacao_cruzada.py   # curva de κ e κ*  -> curva_validacao_cruzada*.csv, validacao_cruzada.md   (~3 s)
python3 -I 02_estimar_uf.py          # 3 versões + bootstrap B=500 -> transferencias_uf.csv, diagnosticos.md  (~30 s)
python3 -I 03_teste_sintetico.py     # teste sintético (+ complementos) -> teste_sintetico.md                 (~80 s)
python3 -I testes_unitarios.py       # 65 testes (inclui integração com a base real)                         (~25 s)
```

- Ordem: 01 antes de 02 (02 lê `κ*` de `curva_validacao_cruzada.csv`).
- Python 3.14, numpy 2.4, pandas 3.0, scipy 1.17. Nada a instalar. Tudo serial; sem paralelismo.
- Entrada: `../dados/processados/presidente_municipio_turnos.parquet` (5.571 municípios, `fl_exterior == False`).
- **Dependência da pasta regional (somente leitura):** o solver é importado de `../2026-10-26_inferencia_ecologica/nucleo_inferencia.py` (SLSQP com reescala por √G_rr) e o E1 vem de `../2026-10-26_inferencia_ecologica/transferencias.csv`. Os caminhos são resolvidos a partir de `Path(__file__)`.
- Saídas são regeneráveis; nova execução sobrescreve. CSV: `;`, UTF-8, ponto decimal, β com 6 casas, votos com 1.

## Arquivos

- `nucleo_uf.py`: base por UF, G/H pré-calculados por estado e por "região sem o estado", QP combinado, validação cruzada, bootstrap, coerência com E1.
- `saidas_uf.py`: `transferencias_uf.csv` e textos Markdown. `sintetico_uf.py`: funções do teste sintético.
- `01_validacao_cruzada.py`, `02_estimar_uf.py`, `03_teste_sintetico.py`, `testes_unitarios.py`.
- `transferencias_uf.csv` (**2.592 linhas** = 27 UFs × 3 versões × 32 células), `validacao_cruzada.md`, `diagnosticos.md`, `teste_sintetico.md`, `curva_validacao_cruzada.csv`, `curva_validacao_cruzada_por_uf.csv`.

## Números principais

**Âncoras: PASS.** Σ_u N_u[r] = âncoras nacionais (Caiado 2.600.440, Cury 3.438.835, Renan 2.667.307, ...), 27 UFs com as contagens de municípios da especificação e n efetivo de Kish igual à tabela (1 casa decimal).

**Validação cruzada (`validacao_cruzada.md`)**

- **κ\* = 4** (interior da grade). Erro de validação `Σ w‖Y−Ŷ‖²`: **52.167** em κ\*; **53.086** em κ = 0,25; **101.276** em κ = ∞ (padrão da região).
- A curva é rasa em torno do mínimo: κ = 2 tem erro apenas 0,013% maior que κ = 4.
- Estados em que o erro em κ\* supera o do padrão da região: **AM (2,23×), RR (1,10×), CE (1,09×), SE (1,05×)**. DF não informa κ (1 município: o erro é igual para todo κ).

**Peso da região (`κ / (n_u + κ)`)**: DF **80,0%** (n = 1) · SP **23,6%** (n = 13,0) · GO **17,9%** (n = 18,4) · MG **7,4%** (n = 50,0).

**β de `UF` para Caiado (IC 95% bootstrap = só variabilidade amostral)**

| UF | caiado→lula | caiado→flavio |
|---|---|---|
| GO | 0,345 [0,317; 0,414] | 0,523 [0,480; 0,544] |
| SP | 0,336 [0,000; 0,572] | 0,548 [0,339; 0,921] |
| MG | 0,558 [0,356; 0,717] | 0,413 [0,270; 0,575] |

- Em SP o IC é largo (n efetivo 13): o ponto depende muito do modelo.

**Teste sintético (`teste_sintetico.md`, semente 20261025)**

- (a) `UF` com κ da validação cruzada: **0,04700** · (b) `UF_SOZINHO`: **0,04700** · (c) `UF_REGIAO`: **0,09064** (erro médio absoluto de β em caiado/cury/renan, ponderado por N_u[r]).
- Formalmente (a) ≤ min((b), (c)), **mas por empate**: o κ\* sintético caiu em 0,25, **na borda da grade**, então (a) ≡ (b). O teste não demonstra ganho do encolhimento sobre o estado sozinho.
- Complemento (fora da especificação): em 20 outras sementes, κ\* sintético = 0,25 em 13; (a) ≤ min((b), (c)) em 15 de 20; o erro médio de (a) é 0,0465 contra 0,0458 de (b). O melhor κ pelo β verdadeiro (oráculo) é 0,25 no sorteio principal e em 18 dos 20 complementares: no desenho da especificação (heterogeneidade ±0,15 entre estados) nenhum κ da grade bate o estado sozinho na maioria dos sorteios. Hipótese a confirmar: a validação cruzada mede o erro de Y (dominado por lula, flavio e abstenção) e não o de β das três linhas pequenas.
- Controle (fora da especificação, δ_u = 0, β constante): κ\* = 128, erros (a) 0,0169 < (c) 0,0224 < (b) 0,0384. A validação cruzada e o solver encolhem quando devem.

**Coerência com o E1 (`diagnosticos.md`)**: não precisam bater. Maior |Δβ| (β agregado por região e Brasil, 4 destinos), versão `UF`: Cury **0,206** (Nordeste, →lula), Renan **0,223** (Sul, →lula), Caiado **0,320** (Norte, →branco_nulo). No nível Brasil: Cury 0,045, Renan 0,100, Caiado 0,084.

- O E1 do Norte para Caiado está numa solução de fronteira (0 / 0,128 / 0,872 / 0 para lula/flavio/branco_nulo/abstenção): grupo pequeno, mal identificado. Sem o PA (o maior, 51.991 eleitores de Caiado), o padrão dos demais seria 0,95 para lula; com o PA, o E1 dá 0,87 para branco/nulo. Por isso `UF_REGIAO` também difere do E1 em até 0,374 nesse caso.

## Solver e verificação

- Todo ajuste exige `success` do SLSQP, viabilidade (soma e limites a 1e-8) e **lacuna de dualidade de Frank-Wolfe ≤ 1e-7**. Falha = exceção. Maior lacuna: 5,9e-9 (pontual) e 1,6e-8 (bootstrap). Zero falhas em 81 ajustes pontuais, 1.468 de validação cruzada e 13.500 de bootstrap.
- **cond(G)** máximo 6,9e6 (pontual) e 6,2e6 (bootstrap); 5e2 a 9e2 após a reescala do solver (versão UF, pontual; até 2,4e3 no bootstrap). Abaixo do limite de alerta de 1e8.
- **Verificação independente (testes):** SLSQP × gradiente projetado acelerado (FISTA), nos 27 estados × 3 versões: maior |Δβ| = 2,9e-5 (8.000 iterações), maior |Δobjetivo| = 7e-15. Reajustar a partir de outro ponto inicial: maior |Δβ| ≤ 2e-6.
- **Teste diferencial do QP combinado:** G e H pré-calculados × `calcular_equacoes_normais` regional sobre os dados empilhados (estado com peso `w/W_u`, `g\u` com `(κ/n_u) w/W_{g\u}`): iguais a 1e-10.

## Decisões onde a especificação admitia mais de uma leitura

- **Normalização:** G e H do QP são divididos por `(1 + κ/n_u)` (constante positiva, mesmo argmin), mantendo a escala O(1) coerente com as tolerâncias do solver regional. κ = ∞ usa só G e H de `g\u` (não um κ enorme).
- **Ponto inicial de reserva:** se a 1ª tentativa (ponto "quente") ficar com lacuna > 1e-7, repete-se **uma vez** a partir do ponto uniforme, sem relaxar critério algum. Ocorreu em 3 ajustes (validações cruzadas do teste sintético: complementares e controle) e em 0 nos resultados reais.
- **Bootstrap:** multiplicidades `Multinomial(n_u, 1/n_u)` por estado, estados em ordem alfabética, um único gerador `default_rng(20261025)`; κ fixo em κ\*; **`n_u` de Kish recalculado em cada réplica** sobre os municípios reamostrados (cada cópia é uma linha); `N_u[r]` observado e fixo. DF: reamostragem do próprio estado degenerada, o IC reflete só a região.
- **Validação cruzada:** `n_u` recalculado no treino; termo da região com todos os municípios de `g\u`; estado sem treino na dobra (DF) usa só o termo da região. Erro em κ = ∞ calculado com o ajuste único de `g\u`.
- **Teste sintético:** `δ_u` (um por estado, o mesmo nas linhas caiado/cury/renan) soma-se a `lula` e subtrai-se de `flavio` (sinal não definido na especificação); recortado em `[−β_lula, +β_flavio]`; sorteado **antes** de Y com a mesma semente; Y sorteado estado a estado (ordem alfabética) em fração de `aptos_1t`. Erro = média sobre as 4 destinações de |β̂ − β|, ponderada por `N_u[r]`.
- **Diagnósticos de ajuste** (`diagnosticos.md`): total previsto com `aptos_2t`; R² ponderado por `aptos_1t`; em amostra (UF_SOZINHO ajusta melhor aqui por construção).

## Alertas

- **κ\* único não serve a todos:** AM, RR, CE e SE erram mais com κ\* do que com o padrão da região.
- **Fronteira:** na versão `UF`, AC, AP, BA, RR e TO têm 8 ou 9 das 12 células de cury/renan/caiado em 0 ou 1; AM, ES, MA, PI e RO têm 6 ou 7 (lista completa em `diagnosticos.md`). Grupos pequenos mal identificados.
- **IC não captura viés:** o IC mede só a variabilidade amostral entre municípios com κ fixo; não inclui a hipótese de constância dentro do estado nem o viés de encolher para a região.
- **DF:** 1 município, 80% região; o ponto e o IC do DF são, na prática, GO + MT + MS.
- **Teste sintético:** o resultado principal é empate por borda de grade; o complementar mostra (a) pior que (b) em 5 de 20 sorteios (diferenças de 0,001 a 0,004).
- **`UF_REGIAO` × E1:** a versão com κ = ∞ difere do E1 em até 0,376 (Renan, Centro-Oeste, →flavio): retirar o estado altera muito o padrão regional quando o grupo é pequeno.
