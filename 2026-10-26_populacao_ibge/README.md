# População por município — IBGE, estimativa 2026

Criado em 26/10/2026, a pedido do Vinicius: coluna "Habitantes" na seção "Cidades" do HTML.

## O que é

- Fonte: IBGE, API de agregados, tabela **6579** ("População residente estimada"), variável **9324**, período **2026**.
  - A estimativa de 2026 foi publicada em 28/08/2026. É a mais recente disponível em 26/10/2026.
- `populacao_ibge.py` baixa o total do Brasil e o de cada município para `dados/ibge/`.
  - São dados brutos, fora do git e regeneráveis.
  - Depois de conferir, o script grava `dados/processados/populacao_municipios_ibge.csv` (`cd_municipio_ibge;populacao`).
- O gerador do HTML (`2026-10-26_html_publico/gerar_dados_html.py`) cruza o CSV com a base eleitoral pelo código IBGE e grava a população em `docs/municipios.js`.

## Números-âncora (26/10/2026)

- **5.571 municípios**, com soma **214.211.951**, exatamente o total do Brasil publicado pelo IBGE.
- O cruzamento com a base do TSE pegou os 5.571 municípios brasileiros, sem nenhum código sem par. O gerador volta a conferir a soma.
- As 186 cidades do exterior não têm população (aparecem com "—").

## Observações

- **Fato:** algumas cidades pequenas têm mais eleitores aptos que habitantes estimados. Exemplos: Davinópolis (GO), com 4.144 eleitores e 1.877 habitantes; Anhanguera (GO), com 1.738 e 906.
  - **Hipótese, não verificada:** eleitores que moram em outra cidade e cadastro eleitoral desatualizado. Não é erro de cruzamento.
- O download é feito pelo `curl`, porque o Python desta máquina não confia na cadeia de certificados da rede (proxy corporativo). A verificação de certificado continua ligada.

## Como regenerar

1. `python3 -I 2026-10-26_populacao_ibge/populacao_ibge.py`. Ele só baixa o que ainda não estiver em `dados/ibge/`.
2. `python3 -I 2026-10-26_html_publico/gerar_dados_html.py`.
