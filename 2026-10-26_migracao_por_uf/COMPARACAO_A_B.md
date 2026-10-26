# Comparação A × B e veredito — migração por estado

Criado em 26/10/2026 pelo orquestrador. Lê junto com [ESPECIFICACAO.md](ESPECIFICACAO.md).

- Implementação A: esta pasta, SLSQP.
- Implementação B: `../2026-10-26_migracao_por_uf_reimplementacao/`, FISTA + projeção no simplex, sem scipy.

## Concordância (fato)

- **Estimativas pontuais idênticas:** nas 2.592 linhas (3 versões × 27 estados × 32 células), a maior diferença em β é **1e-6**.
- **Diagnósticos idênticos:** n efetivo, κ e peso da região.
- **Validação cruzada idêntica.** κ\* = **4**, no interior da grade.

| κ | erro de validação | em relação ao mínimo |
|---|---|---|
| 0,25 (estado quase sozinho) | 53.086 | +1,8% |
| 1 | 52.386 | +0,4% |
| 2 | 52.174 | +0,01% |
| **4** | **52.167** | — |
| 8 | 53.354 | +2,3% |
| 64 | 65.914 | +26% |
| ∞ (só a região) | 101.276 | **+94%** |

- **Leitura:**
  - os estados se afastam bastante do padrão da região: usar só a região quase dobra o erro;
  - puxar um pouco para a região ajuda só marginalmente em relação ao estado sozinho.
- **Intervalos bootstrap:**
  - na mediana, A e B diferem **0,003** na soma das bordas;
  - em ~10% das células diferem mais de 0,09, e há células com divergência total. São células na fronteira 0 ou 1, onde a distribuição bootstrap é bimodal.

## Fragilidades (reportadas por A e B; exibidas na página)

- **466 de 864 células (54%) na fronteira 0 ou 1** na versão principal.
- **A curva de validação é plana entre κ = 1 e κ = 4.** κ\* muda (2, 4 ou 8) conforme a partição dos municípios (B).
  - A sensibilidade (estado com peso mínimo da região × só a região) cobre essa faixa.
- **Teste sintético:**
  - o κ escolhido nos dados simulados caiu na borda (0,25), e o modelo principal só empatou com o estado sozinho;
  - em várias sementes, puxar para a região não ajudou;
  - nos dados reais, a validação escolhe κ = 4.
- **Os intervalos de 95% por estado são estreitos demais:** no teste sintético, cobriram **87,7%** (B).
- **"Estado sozinho" (κ = 0,25) não é sozinho nos estados minúsculos:** a região ainda pesa 20% no DF e 8% em RR e AP.
- **DF:** 80% do resultado vem de GO + MT + MS (1 município).
- **A soma dos estados não reproduz a região do modelo E1:** maior diferença em β agregado de 0,32, no Norte (A). São modelos diferentes.

## Decisão de apresentação (orquestrador, 26/10/2026)

- A página usa a versão principal (`UF`, κ = 4) no filtro por estado, sempre com o aviso de instabilidade.
- O aviso traz: peso da região, municípios, n efetivo, células na fronteira e a cobertura baixa dos intervalos.
- Sensibilidade por estado: "estado com peso mínimo da região" (κ = 0,25) e "só os demais estados da região" (κ = ∞).
- Fonte dos dados da página: implementação A (idêntica à B nas estimativas pontuais).
