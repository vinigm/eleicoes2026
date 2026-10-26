# Indicadores socioeconômicos por município — IBGE

Criado em 26/10/2026, a pedido do Vinicius, para a dispersão "índices sociais × voto" da seção "Cidades".

## O que é

- `indicadores_ibge.py` baixa da API de agregados do IBGE para `dados/ibge/` (fora do git), confere os dados e grava `dados/processados/indicadores_municipios_ibge.csv`.
  - **Alfabetização**, Censo 2022: tabela 9543, variável 2513. Total de sexo, cor ou raça e idade (15 anos ou mais).
  - **PIB 2023**, em mil reais: tabela 5938, variável 37.
  - **População 2024**: tabela 6579, que não tem estimativa de 2023. É o denominador do **PIB per capita 2023**.
- O gerador do HTML cruza o CSV com as cidades pelo código IBGE e grava `alfabetizacao` (2 casas) e `pib_per_capita` em `docs/municipios.js`.

## Números-âncora (26/10/2026)

- **Alfabetização:** Brasil 93,00%. Entre os municípios, vai de 63,2% a 99,1%; a mediana é 90,6%.
- **PIB per capita 2023:** de R$ 6.841 a R$ 679.627 por município; a mediana é R$ 29.088.
- **Soma do PIB dos municípios:** fica 19 mil reais abaixo do Brasil, num total de R$ 10,9 trilhões. É arredondamento: cada município é publicado em mil reais. O limite aceito é meio milhar por município.
- **Soma da população 2024:** igual à do Brasil.
- **Boa Esperança do Norte (MT, 5101837)** foi criado depois do Censo 2022 e fica sem os três campos, sem imputação. Qualquer outro município ausente faz o script parar.

## Como ler (vai também no HTML)

- Alfabetização e PIB medem **acesso a estudo e renda**, não inteligência.
- A relação entre cidades **não diz como votou cada eleitor** (falácia ecológica). Exemplo: cidade com alfabetização baixa e voto alto em Lula não significa que quem não sabe ler votou em Lula.
- A região é o fator que mais confunde: o Nordeste tem índices mais baixos e votou em Lula. Por isso a dispersão é mostrada **dentro de cada região**.

## Como regenerar

1. `python3 -I 2026-10-26_indicadores_ibge/indicadores_ibge.py`. Ele só baixa o que ainda não estiver em `dados/ibge/`.
2. `python3 -I 2026-10-26_html_publico/gerar_dados_html.py`.
