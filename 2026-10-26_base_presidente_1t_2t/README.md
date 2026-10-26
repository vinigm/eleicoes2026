# Base de Presidente 2026, 1º e 2º turno, por município (rascunho)

Criado em 26/10/2026. Só o cargo de **Presidente**. Esta pasta é datada: os scripts são regeneráveis, o contexto abaixo não.

## O que isto responde

- Como cada município votou nos dois turnos, para comparar turnos por **UF**, **região** e **partido**.
- Base com **5.757** municípios = **5.571** no Brasil + **186** cidades do exterior (`sg_uf = ZZ`).

## Como rodar (ordem)

Sempre com `python3 -I` (os dados baixados são não confiáveis). A partir desta pasta:

1. `nohup python3 -I 01_coletar_json_2t.py > coleta.log 2>&1 &` (baixa 1 config + 5.786 JSONs; acompanhar com `tail coleta.log`)
2. `python3 -I 02_montar_base.py`
3. `python3 -I 03_conciliar.py` (grava `conciliacao.md`; código de saída 1 se algum FAIL)
4. `python3 -I testes_base.py` (71 testes, sem rede e sem os dados reais)

Os scripts são autocontidos (não importam um ao outro). Só `testes_base.py` carrega os três pelo caminho do arquivo.

## Entradas

- **1º turno** (dados abertos do TSE, lidos direto do zip, nunca descompactados; os zips não são alterados):
  - `votacao_candidato_munzona_2026.zip` -> `votacao_candidato_munzona_2026_BR.csv` (75.504 linhas)
  - `detalhe_votacao_munzona_2026.zip` -> `detalhe_votacao_munzona_2026_BR.csv` (6.292 linhas)
  - latin-1, separador `;`. `CD_MUNICIPIO` vem como `"01007"` num arquivo e `1007` no outro: normalizado para texto de 5 dígitos.
  - Todas as linhas têm `ST_VOTO_EM_TRANSITO = N` (não há linhas `S` neste lote); o código soma `S` e `N` se aparecerem.
- **2º turno** (JSON oficial de divulgação do TSE, eleição `6258`; ainda não saiu nos dados abertos):
  - config `.../6258/config/mun-e006258-cm.json` (lista de UFs e municípios, com `cdi` = código IBGE)
  - por município `.../dados/{uf}/{uf}{cd}-c0001-e006258-u.json`; por UF `.../dados/{uf}/{uf}-c0001-e006258-u.json`; nacional `.../dados/br/br-c0001-e006258-u.json`
  - copiados para `dados/json_tse/6258/` espelhando a URL (5.787 arquivos).

## Saídas (em `dados/processados/`)

- `presidente_municipio_turnos.parquet` e `.csv` (`;`, UTF-8): **5.757 linhas x 34 colunas**.
- `presidente_municipio_candidato_long.parquet`: **80.598 linhas** (1T: 5.757 x 12 = 69.084; 2T: 5.757 x 2 = 11.514), incluindo linhas com 0 voto.
- Nota sobre o CSV: códigos de município têm zero à esquerda; ao ler, use `dtype=str` em `cd_municipio_tse` e `cd_municipio_ibge`.

## Schema da base larga (ordem das colunas)

| Grupo | Colunas | Tipo |
|---|---|---|
| Identificação | `sg_uf`, `nm_regiao`, `cd_municipio_tse` (5 dígitos), `cd_municipio_ibge` (7 dígitos; nulo no exterior), `nm_municipio` | texto |
| Identificação | `fl_exterior` (True para `ZZ`) | bool |
| 1º turno, métricas | `aptos_1t`, `comparecimento_1t`, `abstencao_1t`, `nao_instaladas_1t`, `validos_1t`, `brancos_1t`, `nulos_1t` | int64 |
| 1º turno, candidatos | `votos_1t_{13,14,16,21,22,27,29,30,35,55,70,80}` | int64 |
| 2º turno, métricas | `aptos_2t`, `comparecimento_2t`, `abstencao_2t`, `nao_instaladas_2t`, `validos_2t`, `brancos_2t`, `nulos_2t` | int64 |
| 2º turno, candidatos | `votos_2t_13`, `votos_2t_22` | int64 |

- Regiões: Norte (AC AP AM PA RO RR TO), Nordeste (AL BA CE MA PB PE PI RN SE), Centro-Oeste (DF GO MT MS), Sudeste (ES MG RJ SP), Sul (PR RS SC), Exterior (ZZ).
- Chave do município: (`sg_uf`, `cd_municipio_tse`).
- Candidatos (número: nome de urna, partido): 13 LULA (PT), 14 RENAN SANTOS (MISSÃO), 16 HERTZ DIAS (PSTU), 21 EDMILSON COSTA (PCB), 22 FLAVIO BOLSONARO (PL), 27 CLARIANA BARAO (DC), 29 RUI COSTA PIMENTA (PCO), 30 ZEMA (NOVO), 35 VETERINÁRIO WILSON GRASSI (DEMOCRATA), 55 RONALDO CAIADO (PSD), 70 ESCRITOR AUGUSTO CURY (AVANTE), 80 SAMARA (UP). Nome e partido de 13 e 22 são idênticos nos dois turnos.

## Schema da base longa

`nr_turno` (1 ou 2), `sg_uf`, `cd_municipio_tse`, `nr_candidato`, `nm_urna_candidato`, `sg_partido`, `votos` (int64).

## Regras de montagem

- **1º turno**: soma das zonas de cada município. Votos do candidato = `QT_VOTOS_NOMINAIS_VALIDOS`. Nulos = `QT_TOTAL_VOTOS_NULOS` (já inclui nulos técnicos).
- **2º turno**: campos do JSON de cada município: aptos `e.te`, comparecimento `e.c`, abstenção `e.a`, não instaladas `e.esni`, válidos `v.vv`, brancos `v.vb`, nulos `v.tvn` (total, inclui técnicos `v.vnt`), votos do candidato `vap`. Valores em texto no JSON são convertidos de forma rígida (só dígitos).
- **Zero explícito**: município sem registro de votos de um candidato recebe 0 em `completar_grade_de_votos` (grade município x candidato). Células preenchidas com zero nesta execução: **0** no 1T e **0** no 2T (todos os municípios têm os 12 e os 2 candidatos).
- **Join 1T x 2T** por (`sg_uf`, `cd_municipio_tse`) com anti-join nos dois sentidos, feito duas vezes (detalhe 1T x 2T e candidato 1T x 2T): **0 órfãos** em todos. Se houver órfão, o script 02 grava `orfaos_chaves_1t_2t.csv` e aborta sem gravar a base.
- `nm_municipio` vem do config do TSE (2º turno).
- Para forçar nova coleta, apague `dados/json_tse/6258/`. O script 01 pula arquivo local íntegro e com `tf = "s"`; arquivo com totalização parcial é baixado de novo.
- Retentativa (backoff exponencial, até 5 tentativas, 8 conexões): timeout, falha de rede, HTTP 5xx e **HTTP 429**. O 429 foi incluído por ser limite de taxa (o pedido citava timeout/5xx). HTTP 404 e demais respostas são falha definitiva.

## Resultado da conciliação (detalhe em `conciliacao.md`)

Status geral: **OK**. Coleta: 5.786 baixados, 0 pulados, 0 falhos em 50 s; segunda execução: 0 baixados, 5.786 pulados.

| Checagem | Resultado |
|---|---|
| (a) somas nacionais vs âncoras | PASS, 29/29 (inclui ZZ 1T: aptos 916.534, comparecimento 341.766) |
| (b) municípios por UF vs JSON de cada UF (2T) | PASS, 28 UFs x 9 campos = 252 comparações, 0 divergências |
| (c) soma das UFs vs JSON nacional | PASS, 9 campos, 0 divergências (a soma da base também bate) |
| (d) identidades por município, nos dois turnos | PASS, 0 violações em 5.757 municípios x 7 identidades |
| (e) todo JSON com `tf = "s"` e `s.pst = "100,00"` | PASS, 5.757 + 28 + nacional, 0 exceções |
| (f) municípios por UF | PASS, 28 UFs; 5.757 = 5.571 + 186 |
| (g) extras | PASS: chave única/tipos, IBGE (5.571 distintos, prefixo coerente com a UF, nulo só no exterior), 1T vs CSV bruto por UF (532 comparações), longo vs largo, CSV vs parquet |

## Desvios e surpresas

- **Fato medido**: `aptos` por município **difere entre os turnos em 3.779 de 5.757 municípios**, embora o total nacional seja idêntico (158.745.502). As altas somam +9.524 e as quedas -9.524 (saldo 0). Maiores diferenças: São Paulo +845, Brasília +675, Belém -412. **Hipótese a confirmar** (não verificada): ajuste de eleitorado entre turnos, como voto em trânsito. Isso importa em qualquer taxa de comparecimento ou abstenção comparada entre turnos.
- **Fato medido**: 45 nomes de município diferem entre o config (2º turno) e o CSV (1º turno), todos só pelo apóstrofo (config `OLHO D'ÁGUA`, CSV `OLHO D ÁGUA`). A base usa o nome do config. A chave do join é o código, então não afeta a junção.
- O 2º turno veio do **JSON de divulgação**, não dos dados abertos. Quando o CSV oficial do 2º turno sair, vale refazer a conciliação contra ele. O config traz data de geração 15/10/2026, anterior à data do 2º turno, mas os 5.757 arquivos de município estão com totalização final.
- `fl_exterior` é booleano (no CSV aparece como `True`/`False`).
