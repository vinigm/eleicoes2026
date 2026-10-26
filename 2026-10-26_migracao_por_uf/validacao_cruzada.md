# Validação cruzada de κ — migração de votos por estado

Criado em 26/10/2026. Gerado por `01_validacao_cruzada.py`.

## Resultado

- **κ\* = 4**, argmin do erro de validação (um κ único para os 27 estados).
- **κ\* não está na borda da grade.**
- Erro em κ\*: **52.167,3**; em κ = 0,25: **53.086,4**; em κ = ∞ (padrão da região): **101.275,9**.
- Erro em κ\* é 48,5% menor que o do padrão da região e 1,7% menor que o de κ = 0,25.
- O ponto vizinho à esquerda na grade (κ = 2) tem erro 0,013% maior que o de κ\*: a curva é rasa em torno do mínimo.
- **Estados em que o erro em κ\* supera o do padrão da região** (razão erro κ\* ÷ erro ∞ > 1, entre parênteses): AM (2,23), CE (1,09), RR (1,10), SE (1,05). Para eles, um κ único maior seria melhor; a escolha de um κ único (especificação) foi mantida.
- **DF:** com 1 município, ele sempre sai do treino na própria dobra e o ajuste vira só o termo da região; o erro do DF é igual para todo κ e não informa a escolha.

## Método (resumo)

- Partição determinística: `dobra = int(cd_municipio_tse) mod 5`.
- Para cada κ e dobra: cada estado é ajustado com os próprios municípios fora da dobra (n efetivo de Kish recalculado no treino) e com o termo da região usando TODOS os municípios dos demais estados da região.
- DF (1 município): na dobra em que o município sai, β = ótimo só do termo da região (GO + MT + MS).
- Erro de validação: `Σ_i w_i ‖Y_i − X_i β_u‖²` sobre todos os municípios e dobras, com `w_i = aptos_1t_i`.
- Ajustes SLSQP executados: 1468. Todos convergiram e foram certificados (falha seria exceção).
- Ajustes que precisaram do ponto inicial uniforme de reserva (1ª tentativa, a partir da solução do κ anterior, ficou acima do limite de certificação): **0**. O critério de certificação (lacuna de dualidade ≤ 1e-7) não foi relaxado.

## Curva de erro por κ

| κ | erro de validação Σ w‖Y−Ŷ‖² | erro ÷ Σw (×10⁻⁴) | erro ÷ menor erro |
|---|---|---|---|
| 0,25 (UF_SOZINHO) | 53.086,4 | 3,3635 | 1,0176 |
| 0,5 | 52.867,3 | 3,3497 | 1,0134 |
| 1 | 52.386,3 | 3,3192 | 1,0042 |
| 2 | 52.174,0 | 3,3057 | 1,0001 |
| 4 **← κ\*** | 52.167,3 | 3,3053 | 1,0000 |
| 8 | 53.353,9 | 3,3805 | 1,0227 |
| 16 | 56.132,1 | 3,5565 | 1,0760 |
| 32 | 60.417,0 | 3,8280 | 1,1581 |
| 64 | 65.914,1 | 4,1763 | 1,2635 |
| 128 | 72.033,0 | 4,5640 | 1,3808 |
| 256 | 77.874,6 | 4,9341 | 1,4928 |
| ∞ (padrão da região) | 101.275,9 | 6,4168 | 1,9414 |

## Decomposição por estado (informativa)

- Razão < 1: o estado erra menos fora da amostra do que com o padrão da região.
- A última coluna é o melhor κ da grade olhando só aquele estado. **O método usa κ\* único**; a coluna é só um retrato da heterogeneidade e é ruidosa nos estados pequenos.

| UF | região | n efetivo | erro κ\* ÷ erro ∞ | erro κ=0,25 ÷ erro ∞ | melhor κ da grade (só a UF) |
|---|---|---|---|---|---|
| AC | Norte | 4,6 | 0,592 | 0,588 | 1 |
| AL | Nordeste | 12,3 | 0,715 | 0,673 | 0,25 |
| AM | Norte | 3,5 | 2,226 | 2,742 | 256 |
| AP | Norte | 2,9 | 0,535 | 0,408 | 0,25 |
| BA | Nordeste | 28,5 | 0,506 | 0,509 | 2 |
| CE | Nordeste | 13,8 | 1,089 | 1,190 | 256 |
| DF | Centro-Oeste | 1,0 | 1,000 | 1,000 | n/d (1 município) |
| ES | Sudeste | 18,3 | 0,197 | 0,137 | 0,25 |
| GO | Centro-Oeste | 18,4 | 0,099 | 0,100 | 4 |
| MA | Nordeste | 34,4 | 0,357 | 0,352 | 1 |
| MG | Sudeste | 50,0 | 0,802 | 0,809 | 16 |
| MS | Centro-Oeste | 8,6 | 0,704 | 0,704 | 1 |
| MT | Centro-Oeste | 20,5 | 0,545 | 0,529 | 0,25 |
| PA | Norte | 24,9 | 0,354 | 0,345 | 0,25 |
| PB | Nordeste | 21,1 | 0,965 | 0,960 | 0,25 |
| PE | Nordeste | 23,3 | 0,380 | 0,361 | 0,25 |
| PI | Nordeste | 18,3 | 0,437 | 0,433 | 2 |
| PR | Sul | 27,3 | 0,813 | 0,809 | 1 |
| RJ | Sudeste | 6,2 | 0,555 | 0,594 | 2 |
| RN | Nordeste | 16,7 | 0,921 | 0,936 | 4 |
| RO | Norte | 9,3 | 0,243 | 0,256 | 2 |
| RR | Norte | 2,7 | 1,102 | 1,370 | 64 |
| RS | Sul | 40,7 | 0,667 | 0,661 | 0,25 |
| SC | Sul | 44,4 | 0,698 | 0,704 | 4 |
| SE | Nordeste | 13,1 | 1,047 | 1,115 | 64 |
| SP | Sudeste | 13,0 | 0,449 | 0,408 | 0,25 |
| TO | Norte | 18,3 | 0,472 | 0,462 | 1 |
