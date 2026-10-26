# Especificação — migração de votos por estado, puxada para a região

Criado em 26/10/2026. Duas implementações independentes seguem este documento e precisam concordar:

- `2026-10-26_migracao_por_uf/` (implementação A)
- `2026-10-26_migracao_por_uf_reimplementacao/` (implementação B)

Base: o método regional de `2026-10-26_inferencia_ecologica/ESPECIFICACAO.md`. Categorias, denominadores, restrições e âncoras são **idênticos** aos de lá (seções 3 a 5). Ler aquele documento primeiro.

---

## 1. Problema

- O Vinicius quer filtrar a migração de votos por estado.
- Estimar cada estado sozinho é inviável: são 32 frações e o tamanho efetivo (Kish, `(Σw)²/Σw²` com `w = aptos_1t`) é muito pequeno na maioria dos estados.

| UF | municípios | n efetivo | UF | municípios | n efetivo |
|---|---|---|---|---|---|
| DF | 1 | 1,0 | PI | 224 | 18,3 |
| RR | 15 | 2,7 | TO | 139 | 18,3 |
| AP | 16 | 2,9 | ES | 78 | 18,3 |
| AM | 62 | 3,5 | GO | 246 | 18,4 |
| AC | 22 | 4,6 | MT | 142 | 20,5 |
| RJ | 92 | 6,2 | PB | 223 | 21,1 |
| MS | 79 | 8,6 | PE | 185 | 23,3 |
| RO | 52 | 9,3 | PA | 144 | 24,9 |
| AL | 102 | 12,3 | PR | 399 | 27,3 |
| SP | 645 | 13,0 | BA | 417 | 28,5 |
| SE | 75 | 13,1 | MA | 217 | 34,4 |
| CE | 184 | 13,8 | RS | 497 | 40,7 |
| RN | 167 | 16,7 | SC | 295 | 44,4 |
|  |  |  | MG | 853 | 50,0 |

## 2. Modelo — cada estado com os próprios municípios + a região como pseudo-dados

Para o estado `u` da região `g`, com `β` 8×4 nas mesmas restrições do modelo regional (cada linha no simplex):

```
J_u(β) = (1 / W_u) · Σ_{i ∈ u} w_i ‖Y_i − X_i β‖²   +   (κ / n_u) · (1 / W_{g∖u}) · Σ_{i ∈ g∖u} w_i ‖Y_i − X_i β‖²
```

- `w_i = aptos_1t_i`; `W_u = Σ_{i∈u} w_i`; `n_u` = n efetivo de Kish do estado (calculado sobre os municípios usados no ajuste).
- **`g∖u` = os demais estados da região, sem o próprio estado.**
  - Evita que os dados do estado contem duas vezes.
  - Para o DF, o "padrão da região" é GO + MT + MS.
- **Leitura:** a região entra como se fosse **κ municípios a mais**, contra `n_u` municípios efetivos do próprio estado.
  - **Peso da região no resultado** = `κ / (n_u + κ)`. Reportar em % por estado.
- **Forma computacional:** com `G = G_u / W_u + (κ/n_u) · G_{g∖u} / W_{g∖u}` e `H` análogo, é o mesmo QP de 32 parâmetros do modelo regional.
  - `G` é definida positiva porque `G_{g∖u}` é.
  - O ótimo é único, inclusive no DF (1 município).
- **Limites:**
  - `κ → 0`: estado sozinho (instável);
  - `κ → ∞`: padrão dos demais estados da região.

## 3. Escolha de κ — validação cruzada (um κ único para todos os estados)

- **Grade:** κ ∈ {0,25; 0,5; 1; 2; 4; 8; 16; 32; 64; 128; 256}.
- **Partição determinística**, para A e B usarem os mesmos grupos: `dobra_i = int(cd_municipio_tse_i) mod 5` (5 dobras).
- **Para cada κ e cada dobra `k`:**
  - em cada estado, ajustar `β_u` com os municípios do estado fora da dobra `k`;
  - o termo da região usa todos os municípios de `g∖u`, sem relação com as dobras;
  - `n_u` é recalculado sobre os municípios de treino;
  - prever os municípios da dobra `k` com `Ŷ_i = X_i β_u`.
- **Erro de validação:** `Σ_i w_i ‖Y_i − Ŷ_i‖²`, somado sobre todos os municípios e dobras. **κ\* = argmin.**
- **Estado sem municípios de treino em uma dobra** (o DF, quando o único município cai na dobra): `β_u` = o ótimo só do termo da região.
- **Reportar a curva inteira**, com o erro para cada κ, mais as referências κ = 0,25 e κ = ∞ (padrão da região).
- Se κ\* cair na borda da grade, reportar. Não estender a grade por conta própria.

## 4. Três versões a entregar (para mostrar a sensibilidade na página)

| código | o que é |
|---|---|
| `UF` | **principal**: κ = κ\* |
| `UF_SOZINHO` | κ = 0,25, quase só o próprio estado |
| `UF_REGIAO` | κ = ∞: o ótimo só do termo `g∖u` (padrão dos demais estados da região) |

## 5. Incerteza — bootstrap

- **B = 500** réplicas, semente **20261025**.
- **Em cada réplica:** reamostrar municípios com reposição **dentro de cada estado**.
  - O termo da região usa os municípios reamostrados dos outros estados da mesma réplica.
  - κ fica fixo em κ\*; não é reescolhido por réplica (declarar isso).
- **Saídas:** IC 95% por percentis para `β` e para os votos.
- **Só para `UF`.** `UF_SOZINHO` e `UF_REGIAO` saem sem intervalo (colunas de IC vazias).
- **DF:** a reamostragem do próprio estado é degenerada (1 município); o intervalo reflete só a região. Declarar.

## 6. Fluxos em votos

- `votos[r, c] = β_u[r, c] · N_u[r]`, com `N_u[r] = Σ_{i∈u} aptos_1t_i · X_i[r]` (contagem do grupo `r` no estado no 1º turno).
- **Âncora:** `Σ_u N_u[r]` = âncoras da seção 4 da especificação regional. Exemplo: Caiado **2.600.440**, Cury **3.438.835**, Renan **2.667.307**.
- **Diagnóstico de coerência:** somar os fluxos dos estados por região e comparar com os fluxos regionais do modelo E1 (`2026-10-26_inferencia_ecologica/transferencias.csv`).
  - Não precisam bater: são modelos diferentes.
  - Reportar a diferença máxima em β agregado para Caiado, Cury e Renan.

## 7. Teste sintético obrigatório (vale o método, não só o código)

Com o `X` real e contagens `Y_i ~ Multinomial(aptos_1t_i, X_i · β_verdadeiro_u)`, semente 20261025:

- **Região:** `β_regiao` = matriz do teste T1 da especificação regional.
- **Estado:** `β_verdadeiro_u = β_regiao + perturbação` só nas linhas `caiado`, `cury` e `renan`.
  - Perturbação: desloca `δ_u` entre as colunas `lula` e `flavio`, com `δ_u` sorteado uniforme em [−0,15; +0,15] por estado e mesma semente.
  - Recortar para manter a linha no simplex.
- **Comparar o erro médio absoluto de β nessas 3 linhas**, ponderado por `N_u[r]`, entre:
  - (a) `UF` com o κ escolhido por validação cruzada nos dados sintéticos;
  - (b) `UF_SOZINHO`;
  - (c) `UF_REGIAO`.
- **Esperado:** (a) ≤ min((b), (c)). Se não for, reportar; não ajustar o método.

## 8. Saídas (cada implementação na sua pasta)

- **`transferencias_uf.csv`** (`;`, UTF-8), formato longo, colunas:
  - `especificacao` (`UF`, `UF_SOZINHO` ou `UF_REGIAO`), `uf`, `nm_regiao`, `origem_1t`, `destino_2t`;
  - `beta`, `beta_ic_inf`, `beta_ic_sup`, `votos`, `votos_ic_inf`, `votos_ic_sup`;
  - `n_efetivo`, `kappa`, `peso_regiao_pct`.
  - São 27 estados × 3 versões × 32 células = **2.592 linhas**.
- **`validacao_cruzada.md`:** a curva de erro por κ e o κ\*.
- **`diagnosticos.md`:** peso da região por estado, células na fronteira por estado, número de condição de G, coerência com o E1.
- **`teste_sintetico.md`** e **`README.md`**.
