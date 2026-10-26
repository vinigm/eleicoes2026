# Comparação A × B e veredito da inferência ecológica

Criado em 26/10/2026 pelo orquestrador. Lê junto com [ESPECIFICACAO.md](ESPECIFICACAO.md). Implementação A: esta pasta. Implementação B: `../2026-10-26_inferencia_ecologica_reimplementacao/`.

## Concordância numérica (fato)

- **Estimativas pontuais: idênticas** nas 576 células (3 especificações × 6 recortes × 8 origens × 4 destinos), diferença 0 na 4ª casa.
  - A: SLSQP do scipy com variáveis reescaladas. B: FISTA + projeção no simplex escrita do zero, sem scipy.
  - B confirmou ótimo único (G definida positiva; 8 pontos iniciais com o mesmo resultado).
- **Intervalos bootstrap:** no Brasil, nas linhas de foco, diferem no máximo **0,017** (sorteios diferentes, como esperado).
  - As maiores diferenças (até 0,197) estão em células regionais do grupo `demais` (580 mil eleitores), quase todas na fronteira 0 ou 1.

## O que é robusto (se mantém em E1, E2 e E3)

| Achado | E1 (principal) | E2 | E3 |
|---|---|---|---|
| Lula → Lula | 99,2% | 100% | 99,0% |
| Flávio → Flávio | 99,7% | 100% | 99,6% |
| Bloco Caiado+Cury+Renan → Lula | 46% | 43% | 45% |
| Bloco → Flávio | 38% | 37% | 35% |
| Bloco → branco/nulo | 15% | 20% | 15% |
| Flávio recebeu dos 10 eliminados | 3,56 mi | 3,80 mi | 3,31 mi |
| Flávio recebeu de quem anulou/não votou no 1º turno | 0,33 mi | 0,00 mi | 0,57 mi |
| Lula recebeu dos 10 eliminados | 4,33 mi | 3,74 mi | 4,18 mi |
| Lula recebeu de quem anulou/não votou no 1º turno | 6,42 mi | 6,58 mi | 5,95 mi |

## O que NÃO é robusto (exibido como "frágil")

- **Divisão por candidato eliminado:**
  - Caiado → Flávio: 42% / 55% / 49%;
  - Cury → Flávio: 33% / 0% / 22%;
  - Renan → Lula: 47% / 33% / 46%.
- **Estimativas regionais:** 77 de 160 células de E1 ficam na fronteira; o n efetivo vai de 20 a 145 municípios por região. Por isso o HTML mostra só o Brasil.
- **Grupo `demais`** (7 candidatos, 580 mil eleitores): E1 e E2 divergem em até 0,57.

## Ressalvas que valem para todos os achados (hipótese, não verificada)

- **Os três modelos usam a mesma estratégia de identificação.** Concordar entre eles não elimina viés de agregação comum aos três.
- **Branco/nulo do 1º turno → Lula (64% a 87%)** é o achado mais exposto a esse viés.
  - Municípios com mais brancos e nulos tendem a ser mais pobres, onde Lula cresceu entre todos os grupos.
  - Pela contabilidade, porém, esse número é quase forçado: com a lealdade ≈ 99% e o bloco dividido ~46/38, o restante do ganho de Lula precisa vir de quem não escolheu candidato no 1º turno.
- **Renan Santos → Lula 47%** é politicamente contraintuitivo (eleitorado anti-PT). É provável sinal de viés: o voto de Renan se concentra em áreas urbanas, onde Lula cresceu mais. O modelo nacional (E2) dá 33%.
- **Sem referência externa:** não foi encontrada pesquisa publicada que cruze voto do 1º e do 2º turno (busca de 26/10/2026).

## Decisão de apresentação (orquestrador, 26/10/2026)

- O HTML destaca só o robusto: origem do crescimento de cada candidato e o bloco dos três eliminados, sempre com a faixa entre os três modelos.
- Os candidatos individuais aparecem marcados como "estimativa frágil", com os três modelos lado a lado.
- O Brasil é o recorte padrão.
- As regiões entraram por decisão do Vinicius (26/10/2026), sempre com aviso de instabilidade que traz três números da própria região:
  - quantos municípios ela tem;
  - a quantos municípios de mesmo tamanho ela equivale em precisão (n efetivo de Kish: (Σw)² ÷ Σw²);
  - quantas das 32 frações caíram nos limites de 0% ou 100%.
