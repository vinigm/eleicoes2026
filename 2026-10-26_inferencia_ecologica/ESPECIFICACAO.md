# Especificação — inferência ecológica da migração de votos (1º → 2º turno, presidente 2026)

Criado em 26/10/2026. Documento de método: define o QUE estimar e COMO. Duas implementações independentes seguem esta especificação e precisam concordar:

- `2026-10-26_inferencia_ecologica/` (implementação A)
- `2026-10-26_inferencia_ecologica_reimplementacao/` (implementação B)

---

## 1. Pergunta

- **Principal:** no 2º turno, para onde foram os eleitores que no 1º turno votaram em **Cury (70)**, **Renan Santos (14)** e **Caiado (55)**?
- **Secundárias:**
  - lealdade dos eleitores de Lula e Flávio;
  - em quem votaram, no 2º turno, os que se abstiveram ou votaram branco/nulo no 1º (o comparecimento subiu 2,96 milhões).

## 2. Por que é estimativa e não observação

- O voto é secreto: só existem totais por município.
- A inferência ecológica estima o comportamento dos grupos a partir de como os totais variam entre municípios.
- **Hipótese central (constância):** dentro de cada região, a fração de um grupo que vai para cada destino é a mesma em todos os municípios.
  - Se ela falha (ex.: eleitor de Caiado em GO se comporta diferente do de SP), a estimativa tem viés que o intervalo de confiança **não** captura.

## 3. Universo e fonte

- **5.571 municípios brasileiros.** Exterior (`ZZ`, 186 cidades) excluído: comparecimento ~40%, unidades minúsculas, comportamento distinto.
- Fonte única: `dados/processados/presidente_municipio_turnos.parquet` (base certificada em 26/10/2026).

## 4. Categorias

Todas como **fração dos aptos do turno no município**. Cada linha de X e de Y soma 1 (identidade — validar).

**Origem — 1º turno (R = 8 linhas de β), denominador `aptos_1t`:**

| # | código | composição |
|---|---|---|
| 1 | `lula` | `votos_1t_13` |
| 2 | `flavio` | `votos_1t_22` |
| 3 | `cury` | `votos_1t_70` |
| 4 | `renan` | `votos_1t_14` |
| 5 | `caiado` | `votos_1t_55` |
| 6 | `demais` | `votos_1t_30 + 80 + 16 + 27 + 21 + 35 + 29` |
| 7 | `branco_nulo` | `brancos_1t + nulos_1t` |
| 8 | `abstencao` | `abstencao_1t + nao_instaladas_1t` |

**Destino — 2º turno (C = 4 colunas de β), denominador `aptos_2t`:** `lula` (`votos_2t_13`), `flavio` (`votos_2t_22`), `branco_nulo` (`brancos_2t + nulos_2t`), `abstencao` (`abstencao_2t + nao_instaladas_2t`).

**Âncoras (Brasil, 5.571 municípios):**

- 1º turno: lula **53.722.151** · flavio **55.960.603** · cury **3.438.835** · renan **2.667.307** · caiado **2.600.440** · demais **580.570** · branco_nulo **5.964.163** · abstencao **32.894.899** · soma = aptos **157.828.968**.
- 2º turno: lula **64.056.078** · flavio **59.654.544** · branco_nulo **4.144.009** · abstencao **29.974.188** · soma = aptos **157.828.819**.
- Municípios por região: Centro-Oeste 468 · Nordeste 1.794 · Norte 450 · Sudeste 1.668 · Sul 1.191.

## 5. Modelo — regressão de Goodman com restrições, ponderada

- Para cada município `i`: `Y_i (1×4) ≈ X_i (1×8) · β (8×4)`.
- `β[r, c]` = fração do eleitorado do grupo `r` no 1º turno que foi para o destino `c` no 2º turno.
- **Restrições:** `0 ≤ β[r, c] ≤ 1` e `Σ_c β[r, c] = 1` para cada linha `r`.
- **Estimador:** minimizar `Σ_i w_i · ‖Y_i − X_i β‖²`, com `w_i = aptos_1t_i`.
- **Forma computacional:** com `G = Xᵀ W X` (8×8) e `H = Xᵀ W Y` (8×4), o objetivo é `Σ_c (β_cᵀ G β_c − 2 β_cᵀ H_c) + constante`. Problema convexo de 32 parâmetros.
- **Unicidade:** se `G` for definida positiva, o ótimo é único. Reportar o número de condição de `G` em cada ajuste.

## 6. Especificações

- **E1 — principal: β separado por região.** Cada uma das 5 regiões é ajustada só com os seus municípios.
  - Fluxo em votos na região: `F[r, c] = β_reg[r, c] · N_reg[r]`, com `N_reg[r] = Σ_i aptos_1t_i · X_i[r]` (contagem do grupo `r` no 1º turno).
  - Brasil = soma dos fluxos das 5 regiões; `β_Brasil[r, c] = F[r, c] / Σ_c F[r, c]`.
- **E2 — sensibilidade: β único nacional** (5.571 municípios juntos, mesmos pesos).
- **E3 — sensibilidade: igual a E1, sem ponderação** (`w_i = 1`).
- Diferença grande entre E1 e E2 é sinal de viés de agregação: reportar, não esconder.

## 7. Incerteza — bootstrap

- Não paramétrico, **B = 1.000** réplicas, **semente 20261025**.
- Reamostrar municípios com reposição **dentro de cada região** (estratificado). Em cada réplica: reajustar as 5 regiões, recalcular os fluxos e o agregado Brasil.
- Para E2: mesma reamostragem estratificada, ajuste nacional único.
- IC 95% por percentis 2,5 e 97,5, para `β` e para os fluxos em votos.
- O bootstrap mede variabilidade amostral, **não** o viés da hipótese de constância. Dizer isso em todo lugar onde o IC aparecer.

## 8. Diagnósticos obrigatórios

- Ajuste: total previsto do 2º turno por destino (`Σ_i aptos_2t_i · (X_i β)_c`, ou equivalente com `aptos_1t`, declarar qual) × total real, por região e Brasil.
- R² ponderado por destino, por região.
- Células de `β` na fronteira (= 0 ou = 1): listar. Fronteira ativa indica tensão do modelo.
- Plausibilidade (só reportar, nunca forçar): `β[lula, lula]` e `β[flavio, flavio]` deveriam ser altos.

## 9. Teste de recuperação sintética (obrigatório, valida a implementação)

Com o `X` real e contagens sintéticas `Y_i ~ Multinomial(aptos_1t_i, X_i · β_verdadeiro)`, semente 20261025.

**T1 — β constante no país** (ajustar E2 e E1; reportar erro absoluto máximo por linha):

| origem | lula | flavio | branco_nulo | abstencao |
|---|---|---|---|---|
| lula | 0,95 | 0,02 | 0,01 | 0,02 |
| flavio | 0,02 | 0,95 | 0,01 | 0,02 |
| cury | 0,40 | 0,35 | 0,10 | 0,15 |
| renan | 0,15 | 0,65 | 0,10 | 0,10 |
| caiado | 0,35 | 0,45 | 0,10 | 0,10 |
| demais | 0,30 | 0,40 | 0,15 | 0,15 |
| branco_nulo | 0,20 | 0,15 | 0,45 | 0,20 |
| abstencao | 0,08 | 0,05 | 0,02 | 0,85 |

**T2 — β varia por região:** igual a T1, exceto a linha `caiado`, que no Centro-Oeste é `[0,55; 0,30; 0,08; 0,07]` e nas demais regiões `[0,25; 0,55; 0,10; 0,10]`. Reportar o erro do fluxo nacional de Caiado em E1 e em E2. Esperado: E1 recupera; E2 enviesa.

## 10. Saídas (cada implementação na sua pasta)

- `transferencias.csv` (formato longo, `;`, UTF-8): `especificacao`, `regiao` (5 regiões + `Brasil`), `origem_1t`, `destino_2t`, `beta`, `beta_ic_inf`, `beta_ic_sup`, `votos`, `votos_ic_inf`, `votos_ic_sup`.
- `diagnosticos.md` e `teste_sintetico.md`.
- `README.md` com como rodar e os números principais.
