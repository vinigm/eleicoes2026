# Certificação adversarial da base presidente 1T/2T

Data: 26/10/2026 · Certificador independente (código próprio, sem ler os scripts do construtor antes das medições).

## Veredito: APROVADA

Nenhuma divergência encontrada em nenhuma das 6 medições. Não houve tolerância relaxada: todas as comparações de contagem são de igualdade inteira exata.

## Escopo e método

- Base: `dados/processados/presidente_municipio_turnos.parquet` (5.757 x 34) e `presidente_municipio_candidato_long.parquet` (80.598 linhas).
- Fontes brutas usadas: CSVs dentro dos zips (1T), JSONs oficiais 6258 (2T, cache local), JSONs oficiais 6257 (1T, **baixados por mim**: 5.757 arquivos, 0 falhas, 8 requisições simultâneas, sem retries necessários).
- Scripts (rodam com `python3 -I`, nesta pasta): `c01` coleta 6257 · `c02` tabela x CSV · `c03` JSON x CSV, tabela 2T x JSON, aptos · `c04` amostra do servidor 6258 · `c05` estrutura e somas · `c06` aprofundamento de aptos · `c07` nomes de candidatos. Logs: `c0N.log`.
- Intermediários gerados: `csv_1t_agregado.parquet`, `json_1t.parquet`, `json_2t.parquet`, `dif_json1t_menos_csv1t.parquet`.
- Observação operacional: o Python instalado não tem CAs; usei o bundle do macOS (`/etc/ssl/cert.pem`) mantendo a verificação TLS ligada.

## Resultados

| # | Medição | Resultado | Número-chave |
|---|---|---|---|
| 1 | 1T da tabela x CSV bruto reagregado | PASS | 0 divergentes em 109.383 células (5.757 x 19 colunas); 0 chaves só de um lado; nenhum candidato fora dos 12 |
| 2 | 1T-JSON (6257) x 1T-CSV | PASS | 0 divergentes em 109.383 células; soma absoluta 0; nenhum município com divergência |
| 3 | 2T tabela x JSON 6258 | PASS | 0 divergentes em 51.813 células (5.757 x 9); amostra aleatória de 50 JSONs rebaixados do servidor: 50/50 idênticos **byte a byte** ao cache |
| 4 | Aptos entre turnos | PASS (sem artefato) | 3.779 municípios com aptos_1t != aptos_2t nos pares tabela, JSON1T x JSON2T e CSV1T x JSON2T (idênticos); CSV1T x JSON1T = 0 diferenças |
| 5 | Estrutura | PASS | chave única; 5.757 linhas; ZZ=186; Brasil=5.571; int64 sem NaN e sem negativos; IBGE 7 dígitos único e não nulo no Brasil, nulo nos 186 do exterior (e igual ao `cdi` do JSON em 5.571/5.571); `nm_regiao` correto nas 28 siglas; longa == larga em 80.598 células |
| 6 | Somas nacionais e por UF | PASS | 16/16 âncoras nacionais exatas (1T e 2T); 28 UFs x 19 colunas (1T) e x 9 (2T): soma absoluta de diferenças 0 contra CSV e contra JSON |

### Detalhes adicionais medidos

- JSON 6257: 5.757 municípios, todos com `ele=6257`, turno 1, totalização 100%, `cdabr` igual ao código da config. JSON 6258: idem com `ele=6258`, turno 2.
- Os 12 candidatos do 1T e os 2 do 2T são os mesmos nas duas fontes; nome de urna e partido da tabela longa conferem com o CSV (1T) e o JSON (2T).
- Identidades internas, ambos os turnos: `validos+brancos+nulos == comparecimento` em 5.757/5.757; soma dos candidatos == `validos` em 5.757/5.757; `aptos == comparecimento + abstencao + nao_instaladas` em 5.757/5.757.
- CSV espelho do construtor (`.csv`, separador `;`) == parquet: 0 células numéricas divergentes.

## Medição 4 em detalhe: aptos entre turnos

### Fatos (medidos)

- A diferença **existe nas fontes oficiais**: JSON1T x JSON2T dá os mesmos 3.779 municípios (1.485 com 1T maior, 2.294 com 2T maior), soma +9.524 / -9.524, saldo 0, maior |dif| = 845. CSV1T x JSON1T não difere em nenhum município. **Não é artefato de misturar CSV (1T) com JSON (2T).**
- Número de seções (`s.ts`) é idêntico nos dois turnos em todos os municípios; portanto a diferença não vem de criação/extinção de seções.
- Saldo por UF != 0 nas 28 UFs (ex.: SP +699, DF +675, ZZ +149, PA -334): há movimentação **entre UFs**, não só dentro delas.
- Deslocamentos pequenos dominam: mediana +1, 1.555 municípios com +-1; quantis 5% a 95% entre -7 e +8.
- Por identidade, delta aptos = delta comparecimento + delta abstenção (+ delta não instaladas, nulo). A correlação de 0,35 com delta comparecimento é consequência dessa identidade, não evidência de causa.
- O arquivo TTE (voto em trânsito, convocados, militares, presos, etc.) do projeto contém **apenas o 1T** (`NR_TURNO=1`, 595.156 aptos em TTE). Saldo TTE 1T por município x delta aptos: correlação +0,048 (todos os tipos) e +0,042 (só "Voto em trânsito"). Se os aptos do 1T contivessem o TTE e os do 2T não, o delta seguiria -saldo; isso **não** aparece.

### Conclusão rotulada

- **Fato**: a diferença é real nas duas fontes oficiais e não decorre da mistura CSV/JSON.
- **Hipótese (não sustentada nem refutada pelos dados disponíveis)**: ajuste de eleitorado por turno, p.ex. voto em trânsito/transferência temporária pedidos separadamente em cada turno. O único dado de TTE disponível é do 1T, portanto o teste decisivo (TTE do 2T) não é possível aqui, e o teste simples contra o saldo de TTE do 1T não corrobora. Não afirmo causa.

## Ressalvas de uso (não reprovam a base)

- 40 municípios (todos com `nao_instaladas` > 0, 423 eleitores no total, nos dois turnos) têm `aptos != comparecimento + abstencao`. A identidade correta inclui `nao_instaladas`. Taxas de comparecimento/abstenção devem escolher explicitamente a base (aptos ou aptos - nao_instaladas).
- Qualquer taxa comparada entre turnos carrega a variação de aptos descrita acima (efeito de 9.524 eleitores sobre 158,7 milhões, concentrado em poucos municípios; relevante para municípios pequenos).
