"""Gera `docs/dados.js`, o arquivo de dados consumido pelo HTML público.

Junta, num único objeto JavaScript (`window.DADOS_ELEICAO`), três fontes já
produzidas e conferidas em etapas anteriores do projeto:

- indicadores por Brasil, região e UF (`2026-10-26_primeira_leitura_regiao_uf/`);
- migração de votos estimada por inferência ecológica
  (`2026-10-26_inferencia_ecologica/transferencias.csv`);
- a decomposição nacional do ganho de votos entre turnos.

O HTML não recalcula nada: só lê este arquivo. Assim cada número exibido
tem uma origem rastreável no projeto.

Rodar a partir da raiz do projeto com `python3 -I`.
"""

import datetime
import hashlib
import json
import logging
import pathlib
import re

import pandas as pd

LOGGER = logging.getLogger(__name__)

RAIZ_PROJETO = pathlib.Path(__file__).resolve().parent.parent
PASTA_LEITURA = RAIZ_PROJETO / "2026-10-26_primeira_leitura_regiao_uf"
CAMINHO_INDICADORES_BRASIL = PASTA_LEITURA / "indicadores_brasil.csv"
CAMINHO_INDICADORES_REGIAO = PASTA_LEITURA / "indicadores_regiao.csv"
CAMINHO_INDICADORES_UF = PASTA_LEITURA / "indicadores_uf.csv"
CAMINHO_TRANSFERENCIAS = (
    RAIZ_PROJETO / "2026-10-26_inferencia_ecologica" / "transferencias.csv"
)
CAMINHO_TRANSFERENCIAS_UF = (
    RAIZ_PROJETO / "2026-10-26_migracao_por_uf" / "transferencias_uf.csv"
)
CAMINHO_CURVA_VALIDACAO_UF = (
    RAIZ_PROJETO / "2026-10-26_migracao_por_uf" / "curva_validacao_cruzada.csv"
)
# Cobertura empírica dos IC 95% por estado no teste sintético da implementação B
# (`2026-10-26_migracao_por_uf_reimplementacao/teste_sintetico.md`). Não há CSV com
# esse número; fica aqui, com a fonte, para não ser digitado no HTML.
COBERTURA_IC_UF_TESTE_PCT = 87.7
CAMINHO_BASE_MUNICIPIOS = (
    RAIZ_PROJETO / "dados" / "processados" / "presidente_municipio_turnos.parquet"
)
CAMINHO_SAIDA = RAIZ_PROJETO / "docs" / "dados.js"
CAMINHO_SAIDA_MUNICIPIOS = RAIZ_PROJETO / "docs" / "municipios.js"
# População estimada 2026 do IBGE por município (gerada e conferida em 2026-10-26_populacao_ibge/).
CAMINHO_POPULACAO = RAIZ_PROJETO / "dados" / "processados" / "populacao_municipios_ibge.csv"
# Alfabetização (Censo 2022) e PIB per capita 2023 por município (2026-10-26_indicadores_ibge/).
CAMINHO_INDICADORES_IBGE = RAIZ_PROJETO / "dados" / "processados" / "indicadores_municipios_ibge.csv"
# Únicos municípios brasileiros sem esses índices (criados depois do Censo 2022).
MUNICIPIOS_SEM_INDICADORES_IBGE = {"5101837"}
CAMINHO_HTML = RAIZ_PROJETO / "docs" / "index.html"

# Tamanho da versão gravada nas tags de script (`dados.js?v=<hash>`).
TAMANHO_VERSAO = 12

# Cidades: arquivo à parte (`window.DADOS_MUNICIPIOS`), em formato de colunas + linhas
# para ficar enxuto (~5,8 mil linhas). Os campos numéricos têm de somar as âncoras nacionais.
NOME_VARIAVEL_MUNICIPIOS = "DADOS_MUNICIPIOS"
CAMPOS_NUMERICOS_MUNICIPIO = [
    "aptos_1t",
    "aptos_2t",
    "comparecimento_1t",
    "comparecimento_2t",
    "validos_1t",
    "validos_2t",
    "votos_1t_13",
    "votos_1t_22",
    "votos_2t_13",
    "votos_2t_22",
]
# Palavras que ficam em minúscula no nome da cidade (exceto no começo): "Colônia do Gurguéia".
CONECTIVOS_NOME = {"de", "da", "do", "das", "dos", "e", "del", "di", "du"}

COLUNA_VOTOS_CAIADO_1T = "votos_1t_55"
PREFIXO_VOTOS_1T = "votos_1t_"

NOME_VARIAVEL_JS = "DADOS_ELEICAO"

NOMES_UF = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
    "ZZ": "Exterior",
}

COLUNAS_INDICADORES = [
    "aptos_1t",
    "comparecimento_1t",
    "validos_1t",
    "brancos_1t",
    "nulos_1t",
    "votos_1t_13",
    "votos_1t_22",
    "aptos_2t",
    "comparecimento_2t",
    "validos_2t",
    "brancos_2t",
    "nulos_2t",
    "votos_2t_13",
    "votos_2t_22",
    "pct_lula_1t",
    "pct_flavio_1t",
    "pct_outros_1t",
    "pct_lula_2t",
    "variacao_lula_pp",
    "comparecimento_pct_1t",
    "comparecimento_pct_2t",
    "variacao_comparecimento_pp",
    "ganho_lula",
    "ganho_flavio",
    "vencedor_1t",
    "vencedor_2t",
]

COLUNAS_TRANSFERENCIAS = [
    "especificacao",
    "regiao",
    "origem_1t",
    "destino_2t",
    "beta",
    "beta_ic_inf",
    "beta_ic_sup",
    "votos",
    "votos_ic_inf",
    "votos_ic_sup",
]

CASAS_DECIMAIS_PERCENTUAL = 4

# Conclusão da página: decomposição do ganho oficial de cada finalista por origem.
ESPECIFICACOES_CONCLUSAO = ["E1", "E2", "E3"]
RECORTE_BRASIL = "Brasil"
NOME_REGIAO_EXTERIOR = "Exterior"
ORIGENS_GANHO = ["cury", "renan", "caiado", "demais", "branco_nulo", "abstencao"]
DESTINOS_SEGUNDO_TURNO = ["lula", "flavio", "branco_nulo", "abstencao"]
NUMERO_POR_FINALISTA = {"lula": "13", "flavio": "22"}
RIVAL_POR_FINALISTA = {"lula": "flavio", "flavio": "lula"}
# A linha de origem do finalista soma os votos dele no 1º turno (β soma 1);
# acima de 1 voto de diferença, a migração não corresponde à base.
TOLERANCIA_VOTOS_ORIGEM = 1.0
# O ajuste do modelo é recalculado como real − previsto; a diferença para o valor
# em inteiros só pode vir do arredondamento das 7 entradas e 3 perdas.
TOLERANCIA_AJUSTE_MODELO = 6.0


def ler_csv_obrigatorio(caminho: pathlib.Path) -> pd.DataFrame:
    """Lê um CSV do projeto (`;`, UTF-8) e falha cedo se ele não existir.

    Args:
        caminho: Caminho do CSV.

    Returns:
        Conteúdo do CSV.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de entrada ausente: {caminho}")

    tabela = pd.read_csv(caminho, sep=";", encoding="utf-8")
    LOGGER.info("Lido %s (%d linhas).", caminho, len(tabela))
    return tabela


def validar_colunas(
    tabela: pd.DataFrame,
    colunas_obrigatorias: list[str],
    nome_tabela: str,
) -> None:
    """Garante que a tabela tem todas as colunas que o HTML consome.

    Args:
        tabela: Tabela a validar.
        colunas_obrigatorias: Colunas exigidas.
        nome_tabela: Nome usado na mensagem de erro.

    Raises:
        KeyError: Se faltar alguma coluna.
    """
    colunas_ausentes = set(colunas_obrigatorias).difference(tabela.columns)
    if colunas_ausentes:
        raise KeyError(
            f"Colunas ausentes em {nome_tabela}: {sorted(colunas_ausentes)}"
        )


def converter_linha_indicadores(linha: pd.Series) -> dict[str, object]:
    """Converte uma linha de indicadores em dicionário serializável.

    Contagens viram `int`; percentuais são arredondados para reduzir o
    tamanho do arquivo sem perder precisão visível (4 casas decimais).

    Args:
        linha: Linha de uma tabela de indicadores.

    Returns:
        Dicionário com os indicadores da linha.
    """
    indicadores: dict[str, object] = {}

    for nome_coluna in COLUNAS_INDICADORES:
        valor = linha[nome_coluna]
        nome_e_percentual = nome_coluna.startswith("pct_") or nome_coluna.endswith(
            ("_pp", "_pct_1t", "_pct_2t")
        )

        if isinstance(valor, str):
            indicadores[nome_coluna] = valor
        elif nome_e_percentual:
            indicadores[nome_coluna] = round(float(valor), CASAS_DECIMAIS_PERCENTUAL)
        else:
            indicadores[nome_coluna] = int(valor)

    return indicadores


def montar_bloco_brasil(indicadores_brasil: pd.DataFrame) -> dict[str, object]:
    """Monta os indicadores nacionais e a decomposição do ganho de votos.

    A decomposição explica de onde vieram os votos a mais do 2º turno:
    o ganho somado de Lula e Flávio é exatamente igual à soma de três
    fontes — votos dos eliminados, comparecimento extra e queda de brancos
    e nulos. A identidade é verificada aqui para que o gráfico nunca mostre
    uma ponte que não fecha.

    Args:
        indicadores_brasil: Tabela com uma única linha (Brasil + exterior).

    Returns:
        Dicionário com os indicadores nacionais e a ponte de votos.

    Raises:
        ValueError: Se a tabela não tiver uma linha ou a ponte não fechar.
    """
    if len(indicadores_brasil) != 1:
        raise ValueError(
            f"Indicadores nacionais deveriam ter 1 linha, têm {len(indicadores_brasil)}."
        )

    linha_brasil = indicadores_brasil.iloc[0]
    bloco_brasil = converter_linha_indicadores(linha_brasil)

    votos_eliminados = int(
        linha_brasil["validos_1t"] - linha_brasil["votos_1t_13"] - linha_brasil["votos_1t_22"]
    )
    comparecimento_extra = int(
        linha_brasil["comparecimento_2t"] - linha_brasil["comparecimento_1t"]
    )
    brancos_nulos_1t = linha_brasil["brancos_1t"] + linha_brasil["nulos_1t"]
    brancos_nulos_2t = linha_brasil["brancos_2t"] + linha_brasil["nulos_2t"]
    queda_brancos_nulos = int(brancos_nulos_1t - brancos_nulos_2t)

    total_fontes = votos_eliminados + comparecimento_extra + queda_brancos_nulos
    total_ganhos = int(linha_brasil["ganho_lula"] + linha_brasil["ganho_flavio"])
    if total_fontes != total_ganhos:
        raise ValueError(
            "A ponte de votos não fecha: fontes "
            f"{total_fontes} ≠ ganhos {total_ganhos}."
        )

    bloco_brasil["ponte"] = {
        "votos_eliminados": votos_eliminados,
        "comparecimento_extra": comparecimento_extra,
        "queda_brancos_nulos": queda_brancos_nulos,
        "ganho_lula": int(linha_brasil["ganho_lula"]),
        "ganho_flavio": int(linha_brasil["ganho_flavio"]),
        "total": total_ganhos,
    }
    return bloco_brasil


def montar_lista_regioes(indicadores_regiao: pd.DataFrame) -> list[dict[str, object]]:
    """Converte os indicadores por região, preservando a ordem da tabela.

    Args:
        indicadores_regiao: Uma linha por região (inclui Exterior).

    Returns:
        Lista de dicionários, um por região.
    """
    regioes: list[dict[str, object]] = []

    for _, linha_regiao in indicadores_regiao.iterrows():
        bloco_regiao = converter_linha_indicadores(linha_regiao)
        bloco_regiao["nm_regiao"] = linha_regiao["nm_regiao"]
        regioes.append(bloco_regiao)

    return regioes


def calcular_pct_caiado_por_uf(caminho_base: pathlib.Path) -> dict[str, float]:
    """Calcula o percentual de Caiado nos votos válidos do 1º turno, por UF.

    Usado no destaque do estado com maior avanço de Lula (Goiás), para que a
    frase que atribui os votos dos eliminados a Caiado venha do dado e não de
    um número digitado no HTML.

    Args:
        caminho_base: Parquet da base por município.

    Returns:
        Dicionário sigla da UF → percentual de Caiado (0 a 100).

    Raises:
        FileNotFoundError: Se o parquet não existir.
    """
    if not caminho_base.exists():
        raise FileNotFoundError(f"Base por município não encontrada: {caminho_base}")

    base_municipios = pd.read_parquet(
        caminho_base,
        columns=["sg_uf", COLUNA_VOTOS_CAIADO_1T, "validos_1t"],
    )
    contagens_uf = base_municipios.groupby("sg_uf")[
        [COLUNA_VOTOS_CAIADO_1T, "validos_1t"]
    ].sum()
    pct_caiado = (
        100.0 * contagens_uf[COLUNA_VOTOS_CAIADO_1T] / contagens_uf["validos_1t"]
    )

    pct_caiado_por_uf: dict[str, float] = {}
    for sigla_uf, percentual in pct_caiado.items():
        pct_caiado_por_uf[str(sigla_uf)] = round(float(percentual), CASAS_DECIMAIS_PERCENTUAL)
    return pct_caiado_por_uf


def calcular_votos_1t_por_candidato(
    caminho_base: pathlib.Path,
    validos_1t_oficial: int,
) -> dict[str, int]:
    """Soma os votos de cada candidato do 1º turno no Brasil e no exterior.

    Alimenta o resultado nacional do 1º turno na página, que mostra os 12
    candidatos (os menores agrupados no HTML). Inclui o exterior para bater
    com o total oficial divulgado pelo TSE.

    Args:
        caminho_base: Parquet da base por município.
        validos_1t_oficial: Votos válidos do 1º turno já usados na página,
            para garantir que a soma dos candidatos feche com eles.

    Returns:
        Dicionário número do candidato (texto) → votos no 1º turno.

    Raises:
        FileNotFoundError: Se o parquet não existir.
        ValueError: Se a soma dos candidatos não fechar com os válidos.
    """
    if not caminho_base.exists():
        raise FileNotFoundError(f"Base por município não encontrada: {caminho_base}")

    base_municipios = pd.read_parquet(caminho_base)
    colunas_candidatos: list[str] = []
    for nome_coluna in base_municipios.columns:
        if nome_coluna.startswith(PREFIXO_VOTOS_1T):
            colunas_candidatos.append(nome_coluna)

    votos_por_candidato: dict[str, int] = {}
    for nome_coluna in colunas_candidatos:
        numero_candidato = nome_coluna.removeprefix(PREFIXO_VOTOS_1T)
        votos_por_candidato[numero_candidato] = int(base_municipios[nome_coluna].sum())

    soma_candidatos = sum(votos_por_candidato.values())
    if soma_candidatos != validos_1t_oficial:
        raise ValueError(
            "Votos dos candidatos do 1º turno não fecham com os válidos: "
            f"{soma_candidatos} ≠ {validos_1t_oficial}."
        )

    LOGGER.info(
        "Votos do 1º turno somados para %d candidatos (%d válidos).",
        len(votos_por_candidato),
        soma_candidatos,
    )
    return votos_por_candidato


def contar_municipios(caminho_base: pathlib.Path) -> dict[str, int]:
    """Conta municípios brasileiros e cidades do exterior na base.

    Args:
        caminho_base: Parquet da base por município.

    Returns:
        Dicionário com `municipios_brasil` e `cidades_exterior`.

    Raises:
        FileNotFoundError: Se o parquet não existir.
    """
    if not caminho_base.exists():
        raise FileNotFoundError(f"Base por município não encontrada: {caminho_base}")

    base_municipios = pd.read_parquet(caminho_base, columns=["fl_exterior"])
    cidades_exterior = int(base_municipios["fl_exterior"].sum())
    municipios_brasil = int(len(base_municipios) - cidades_exterior)
    return {"municipios_brasil": municipios_brasil, "cidades_exterior": cidades_exterior}


def calcular_diagnosticos_regiao(caminho_base: pathlib.Path) -> list[dict[str, object]]:
    """Calcula, por região, o quanto a estimativa regional de migração é frágil.

    A inferência ecológica pondera municípios pelo eleitorado do 1º turno.
    Quando poucos municípios grandes concentram o peso, a região se comporta
    como uma amostra muito menor do que o número de municípios sugere. O
    tamanho efetivo de Kish, `(Σw)² / Σw²`, mede isso: é o número de
    municípios de mesmo tamanho que daria a mesma precisão.

    O exterior fica de fora, como na própria inferência ecológica.

    Args:
        caminho_base: Parquet da base por município.

    Returns:
        Lista com, por região: nº de municípios, tamanho efetivo, nome e UF
        do maior município e a fração do peso que ele carrega (0 a 100).

    Raises:
        FileNotFoundError: Se o parquet não existir.
    """
    if not caminho_base.exists():
        raise FileNotFoundError(f"Base por município não encontrada: {caminho_base}")

    base_municipios = pd.read_parquet(
        caminho_base,
        columns=["sg_uf", "nm_regiao", "nm_municipio", "fl_exterior", "aptos_1t"],
    )
    mascara_brasil = ~base_municipios["fl_exterior"]
    municipios_brasil = base_municipios[mascara_brasil]

    diagnosticos: list[dict[str, object]] = []
    for nome_regiao, municipios_regiao in municipios_brasil.groupby("nm_regiao"):
        pesos = municipios_regiao["aptos_1t"].astype(float)
        soma_pesos = pesos.sum()
        soma_quadrados = (pesos**2).sum()
        tamanho_efetivo = soma_pesos**2 / soma_quadrados

        posicao_maior = pesos.idxmax()
        maior_municipio = municipios_regiao.loc[posicao_maior]
        peso_maior_pct = 100.0 * pesos.loc[posicao_maior] / soma_pesos

        diagnosticos.append(
            {
                "regiao": str(nome_regiao),
                "municipios": int(len(municipios_regiao)),
                "n_efetivo": round(float(tamanho_efetivo), 1),
                "maior_municipio": str(maior_municipio["nm_municipio"]),
                "maior_municipio_uf": str(maior_municipio["sg_uf"]),
                "maior_peso_pct": round(float(peso_maior_pct), 1),
            }
        )

    LOGGER.info("Diagnósticos regionais calculados para %d regiões.", len(diagnosticos))
    return diagnosticos


def montar_lista_ufs(
    indicadores_uf: pd.DataFrame,
    pct_caiado_por_uf: dict[str, float],
) -> list[dict[str, object]]:
    """Converte os indicadores por UF e acrescenta nome por extenso e Caiado.

    Args:
        indicadores_uf: Uma linha por UF (27 UFs + ZZ).
        pct_caiado_por_uf: Percentual de Caiado no 1º turno por UF.

    Returns:
        Lista de dicionários, um por UF, ordenada pela sigla.

    Raises:
        KeyError: Se aparecer uma sigla sem nome cadastrado ou sem percentual
            de Caiado.
    """
    siglas_sem_nome = set(indicadores_uf["sg_uf"]).difference(NOMES_UF)
    if siglas_sem_nome:
        raise KeyError(f"Siglas de UF sem nome cadastrado: {sorted(siglas_sem_nome)}")

    siglas_sem_caiado = set(indicadores_uf["sg_uf"]).difference(pct_caiado_por_uf)
    if siglas_sem_caiado:
        raise KeyError(f"Siglas de UF sem percentual de Caiado: {sorted(siglas_sem_caiado)}")

    indicadores_ordenados = indicadores_uf.sort_values("sg_uf")
    ufs: list[dict[str, object]] = []

    for _, linha_uf in indicadores_ordenados.iterrows():
        bloco_uf = converter_linha_indicadores(linha_uf)
        sigla_uf = linha_uf["sg_uf"]
        bloco_uf["sg_uf"] = sigla_uf
        bloco_uf["nm_uf"] = NOMES_UF[sigla_uf]
        bloco_uf["nm_regiao"] = linha_uf["nm_regiao"]
        bloco_uf["pct_caiado_1t"] = pct_caiado_por_uf[sigla_uf]
        ufs.append(bloco_uf)

    return ufs


def arredondar_ou_nulo(valor: object, casas: int) -> float | None:
    """Arredonda um número; célula vazia (NaN) vira `None` (→ `null` no JS).

    As versões de sensibilidade por estado não têm intervalo de confiança.
    Sem esta conversão, o NaN viraria o literal `NaN` no JavaScript e
    apareceria como "NaN%" na página.

    Args:
        valor: Valor lido do CSV.
        casas: Casas decimais.

    Returns:
        Valor arredondado, ou `None` se a célula estiver vazia.
    """
    if pd.isna(valor):
        return None
    return round(float(valor), casas)


def inteiro_ou_nulo(valor: object) -> int | None:
    """Converte um número em inteiro arredondado; célula vazia vira `None`.

    Args:
        valor: Valor lido do CSV.

    Returns:
        Inteiro arredondado, ou `None` se a célula estiver vazia.
    """
    if pd.isna(valor):
        return None
    return int(round(float(valor)))


def montar_migracao(
    transferencias: pd.DataFrame,
    coluna_recorte: str,
) -> list[dict[str, object]]:
    """Converte uma tabela longa de transferências em lista de registros.

    Serve às duas fontes: a regional (E1 principal, E2 e E3 de sensibilidade,
    recorte na coluna `regiao`) e a por estado (UF, UF_SOZINHO e UF_REGIAO,
    recorte na coluna `uf`). Na página, as duas ficam na mesma lista, com o
    recorte (região ou sigla da UF) no campo `regiao`.

    Args:
        transferencias: Tabela longa no formato das especificações.
        coluna_recorte: Coluna que identifica o recorte (`regiao` ou `uf`).

    Returns:
        Lista de registros com β, IC 95% (ou `None`) e votos estimados.
    """
    registros: list[dict[str, object]] = []

    for _, linha_transferencia in transferencias.iterrows():
        registro = {
            "especificacao": linha_transferencia["especificacao"],
            "regiao": linha_transferencia[coluna_recorte],
            "origem": linha_transferencia["origem_1t"],
            "destino": linha_transferencia["destino_2t"],
            "beta": round(float(linha_transferencia["beta"]), CASAS_DECIMAIS_PERCENTUAL),
            "beta_ic_inf": arredondar_ou_nulo(
                linha_transferencia["beta_ic_inf"], CASAS_DECIMAIS_PERCENTUAL
            ),
            "beta_ic_sup": arredondar_ou_nulo(
                linha_transferencia["beta_ic_sup"], CASAS_DECIMAIS_PERCENTUAL
            ),
            "votos": int(round(float(linha_transferencia["votos"]))),
            "votos_ic_inf": inteiro_ou_nulo(linha_transferencia["votos_ic_inf"]),
            "votos_ic_sup": inteiro_ou_nulo(linha_transferencia["votos_ic_sup"]),
        }
        registros.append(registro)

    return registros


def montar_fluxos_brasil(transferencias: pd.DataFrame, especificacao: str) -> pd.DataFrame:
    """Monta a matriz origem (1º turno) × destino (2º turno) do Brasil, em votos.

    Args:
        transferencias: Tabela longa de `transferencias.csv`.
        especificacao: Modelo (E1, E2 ou E3).

    Returns:
        Matriz com as 8 origens nas linhas e os 4 destinos nas colunas.

    Raises:
        ValueError: Se a matriz estiver incompleta.
    """
    mascara_modelo = transferencias["especificacao"] == especificacao
    mascara_brasil = transferencias["regiao"] == RECORTE_BRASIL
    transferencias_brasil = transferencias[mascara_modelo & mascara_brasil]
    fluxos_brasil = transferencias_brasil.pivot(
        index="origem_1t", columns="destino_2t", values="votos"
    )

    origens_esperadas = set(ORIGENS_GANHO) | set(NUMERO_POR_FINALISTA)
    origens_ausentes = origens_esperadas - set(fluxos_brasil.index)
    destinos_ausentes = set(DESTINOS_SEGUNDO_TURNO) - set(fluxos_brasil.columns)
    if origens_ausentes or destinos_ausentes or fluxos_brasil.isna().any().any():
        raise ValueError(
            f"Matriz de migração incompleta em {especificacao}: origens ausentes "
            f"{sorted(origens_ausentes)}, destinos ausentes {sorted(destinos_ausentes)}."
        )
    return fluxos_brasil


def decompor_ganho_finalista(
    fluxos_brasil: pd.DataFrame,
    codigo_finalista: str,
    votos_1t_brasil: int,
    votos_2t_brasil: int,
) -> dict[str, object]:
    """Decompõe o saldo de um finalista no Brasil (sem exterior) por origem.

    Identidade, em votos inteiros:
        votos do 2º − votos do 1º = Σ entradas − Σ perdas + ajuste do modelo

    - entradas: eleitores de cada origem do 1º turno (eliminados, branco/nulo,
      não votou e o outro finalista) que o modelo estima terem votado no
      finalista no 2º turno;
    - perdas: eleitores do finalista no 1º turno que, pelo modelo, foram para
      outro destino no 2º (por destino);
    - ajuste do modelo: real − previsto pelo modelo para o total do finalista.
      É o erro de ajuste nacional, não um grupo de eleitores.

    Args:
        fluxos_brasil: Matriz origem × destino de um modelo.
        codigo_finalista: `lula` ou `flavio`.
        votos_1t_brasil: Votos do finalista no 1º turno, sem exterior.
        votos_2t_brasil: Votos do finalista no 2º turno, sem exterior.

    Returns:
        Dicionário com `entradas`, `perdas` e `ajuste_modelo`.

    Raises:
        ValueError: Se a linha de origem do finalista não somar seus votos do
            1º turno, ou se o ajuste em inteiros divergir de real − previsto.
    """
    soma_origem_finalista = float(fluxos_brasil.loc[codigo_finalista].sum())
    if abs(soma_origem_finalista - votos_1t_brasil) > TOLERANCIA_VOTOS_ORIGEM:
        raise ValueError(
            f"Migração de {codigo_finalista} soma {soma_origem_finalista:.1f} votos, "
            f"mas a base tem {votos_1t_brasil} no 1º turno."
        )

    origens_entrada = ORIGENS_GANHO + [RIVAL_POR_FINALISTA[codigo_finalista]]
    entradas: dict[str, int] = {}
    for origem in origens_entrada:
        entradas[origem] = int(round(float(fluxos_brasil.loc[origem, codigo_finalista])))

    perdas: dict[str, int] = {}
    for destino in DESTINOS_SEGUNDO_TURNO:
        if destino != codigo_finalista:
            perdas[destino] = int(round(float(fluxos_brasil.loc[codigo_finalista, destino])))

    saldo_brasil = votos_2t_brasil - votos_1t_brasil
    saldo_estimado = sum(entradas.values()) - sum(perdas.values())
    ajuste_modelo = saldo_brasil - saldo_estimado

    # Conferência independente do ajuste: real − previsto, com o previsto somando
    # a coluna do finalista inteira (retidos + todas as entradas), sem arredondar.
    previsto_brasil = float(fluxos_brasil[codigo_finalista].sum())
    ajuste_medido = votos_2t_brasil - previsto_brasil
    if abs(ajuste_modelo - ajuste_medido) > TOLERANCIA_AJUSTE_MODELO:
        raise ValueError(
            f"Ajuste do modelo de {codigo_finalista} não confere: {ajuste_modelo} em "
            f"inteiros ≠ {ajuste_medido:.1f} (real − previsto). Falta alguma origem?"
        )

    return {"entradas": entradas, "perdas": perdas, "ajuste_modelo": ajuste_modelo}


def montar_conclusao(
    transferencias: pd.DataFrame,
    indicadores_brasil: pd.DataFrame,
    indicadores_regiao: pd.DataFrame,
) -> dict[str, object]:
    """Monta a conclusão: de onde veio o ganho oficial de Lula e de Flávio.

    Para cada finalista e cada modelo (E1 principal, E2 e E3), o ganho oficial
    do 1º para o 2º turno (com exterior) fecha exatamente em:
        Σ entradas − Σ perdas + ajuste do modelo + saldo do exterior

    O ganho oficial e o saldo do exterior são fatos do TSE; entradas e perdas
    são estimativas da inferência ecológica (o exterior ficou fora dela).

    Args:
        transferencias: Tabela longa de `transferencias.csv`.
        indicadores_brasil: Uma linha, Brasil com exterior.
        indicadores_regiao: Uma linha por região, inclusive o Exterior.

    Returns:
        Dicionário por finalista com ganho oficial, saldo do exterior e a
        decomposição de cada modelo.

    Raises:
        ValueError: Se as regiões não fecharem com o Brasil ou a decomposição
            não fechar com o ganho oficial.
    """
    linha_brasil = indicadores_brasil.iloc[0]
    mascara_exterior = indicadores_regiao["nm_regiao"] == NOME_REGIAO_EXTERIOR
    if int(mascara_exterior.sum()) != 1:
        raise ValueError("Indicadores por região deveriam ter exatamente 1 linha de Exterior.")
    linha_exterior = indicadores_regiao[mascara_exterior].iloc[0]
    regioes_sem_exterior = indicadores_regiao[~mascara_exterior]

    fluxos_por_modelo: dict[str, pd.DataFrame] = {}
    for especificacao in ESPECIFICACOES_CONCLUSAO:
        fluxos_por_modelo[especificacao] = montar_fluxos_brasil(transferencias, especificacao)

    conclusao: dict[str, object] = {}
    for codigo_finalista, numero_finalista in NUMERO_POR_FINALISTA.items():
        coluna_1t = f"votos_1t_{numero_finalista}"
        coluna_2t = f"votos_2t_{numero_finalista}"
        votos_1t_brasil = int(regioes_sem_exterior[coluna_1t].sum())
        votos_2t_brasil = int(regioes_sem_exterior[coluna_2t].sum())
        saldo_exterior = int(linha_exterior[coluna_2t] - linha_exterior[coluna_1t])
        ganho_oficial = int(linha_brasil[f"ganho_{codigo_finalista}"])

        saldo_por_regioes = votos_2t_brasil - votos_1t_brasil + saldo_exterior
        if saldo_por_regioes != ganho_oficial:
            raise ValueError(
                f"Regiões não fecham com o Brasil para {codigo_finalista}: "
                f"{saldo_por_regioes} ≠ {ganho_oficial}."
            )

        modelos: dict[str, object] = {}
        for especificacao, fluxos_brasil in fluxos_por_modelo.items():
            decomposicao = decompor_ganho_finalista(
                fluxos_brasil, codigo_finalista, votos_1t_brasil, votos_2t_brasil
            )
            soma_entradas = sum(decomposicao["entradas"].values())
            soma_perdas = sum(decomposicao["perdas"].values())
            total_decomposto = (
                soma_entradas - soma_perdas + decomposicao["ajuste_modelo"] + saldo_exterior
            )
            if total_decomposto != ganho_oficial:
                raise ValueError(
                    f"Decomposição de {codigo_finalista} em {especificacao} não fecha: "
                    f"{total_decomposto} ≠ {ganho_oficial}."
                )
            modelos[especificacao] = decomposicao

        conclusao[codigo_finalista] = {
            "ganho_oficial": ganho_oficial,
            "saldo_exterior": saldo_exterior,
            "modelos": modelos,
        }
        LOGGER.info(
            "Conclusão de %s fecha em %d votos nos %d modelos (ajuste do principal: %d).",
            codigo_finalista,
            ganho_oficial,
            len(modelos),
            modelos[ESPECIFICACOES_CONCLUSAO[0]]["ajuste_modelo"],
        )

    return conclusao


def resumir_validacao_uf(caminho_curva: pathlib.Path) -> dict[str, float]:
    """Resume a validação cruzada do modelo por estado para a metodologia.

    Args:
        caminho_curva: CSV da curva de erro por κ (implementação A).

    Returns:
        κ escolhido, razão entre o erro de "só a região" e o do κ escolhido,
        e a cobertura dos intervalos no teste sintético.

    Raises:
        FileNotFoundError: Se a curva não existir.
        ValueError: Se a curva não tiver a linha de κ infinito.
    """
    curva = ler_csv_obrigatorio(caminho_curva)
    curva["kappa_texto"] = curva["kappa"].astype(str)
    mascara_infinito = curva["kappa_texto"] == "inf"
    if mascara_infinito.sum() != 1:
        raise ValueError("A curva de validação precisa ter uma linha com κ = inf.")

    curva_finita = curva[~mascara_infinito]
    posicao_minimo = curva_finita["erro_validacao"].astype(float).idxmin()
    erro_minimo = float(curva_finita.loc[posicao_minimo, "erro_validacao"])
    kappa_escolhido = float(curva_finita.loc[posicao_minimo, "kappa"])
    erro_so_regiao = float(curva.loc[mascara_infinito, "erro_validacao"].iloc[0])

    return {
        "kappa_escolhido": kappa_escolhido,
        "razao_erro_so_regiao": round(erro_so_regiao / erro_minimo, 2),
        "cobertura_ic_teste_pct": COBERTURA_IC_UF_TESTE_PCT,
    }


def montar_diagnosticos_uf(
    transferencias_uf: pd.DataFrame,
    caminho_base: pathlib.Path,
) -> dict[str, dict[str, object]]:
    """Reúne, por estado, os números do aviso de instabilidade da página.

    Tamanho efetivo, κ e peso da região vêm da versão principal (`UF`) da
    estimativa por estado; o número de municípios vem da base.

    Args:
        transferencias_uf: Tabela longa da estimativa por estado.
        caminho_base: Parquet da base por município.

    Returns:
        Dicionário sigla → {municipios, n_efetivo, kappa, peso_regiao_pct}.

    Raises:
        ValueError: Se um estado tiver valores de diagnóstico divergentes
            entre as próprias linhas.
    """
    base_municipios = pd.read_parquet(caminho_base, columns=["sg_uf", "fl_exterior"])
    mascara_brasil = ~base_municipios["fl_exterior"]
    municipios_por_uf = base_municipios[mascara_brasil].groupby("sg_uf").size()

    mascara_principal = transferencias_uf["especificacao"] == "UF"
    linhas_principais = transferencias_uf[mascara_principal]
    colunas_diagnostico = ["n_efetivo", "kappa", "peso_regiao_pct"]

    diagnosticos: dict[str, dict[str, object]] = {}
    for sigla_uf, linhas_uf in linhas_principais.groupby("uf"):
        valores_unicos = linhas_uf[colunas_diagnostico].drop_duplicates()
        if len(valores_unicos) != 1:
            raise ValueError(f"Diagnóstico inconsistente entre linhas do estado {sigla_uf}.")
        primeira_linha = valores_unicos.iloc[0]
        diagnosticos[str(sigla_uf)] = {
            "municipios": int(municipios_por_uf[sigla_uf]),
            "n_efetivo": round(float(primeira_linha["n_efetivo"]), 1),
            "kappa": round(float(primeira_linha["kappa"]), 2),
            "peso_regiao_pct": round(float(primeira_linha["peso_regiao_pct"]), 1),
        }

    LOGGER.info("Diagnósticos por estado montados para %d estados.", len(diagnosticos))
    return diagnosticos


def gravar_dados_js(dados_html: dict[str, object], caminho_saida: pathlib.Path) -> None:
    """Grava os dados como atribuição a uma variável global JavaScript.

    Um `.js` (e não um `.json` buscado por `fetch`) permite abrir o HTML
    direto do disco, sem servidor, além de funcionar no GitHub Pages.

    Args:
        dados_html: Objeto completo a serializar.
        caminho_saida: Caminho do arquivo `.js` gerado.
    """
    conteudo_json = json.dumps(dados_html, ensure_ascii=False, separators=(",", ":"))
    conteudo_js = f"window.{NOME_VARIAVEL_JS} = {conteudo_json};\n"
    caminho_saida.write_text(conteudo_js, encoding="utf-8")
    LOGGER.info("Gravado %s (%d bytes).", caminho_saida, len(conteudo_js.encode("utf-8")))


def versionar_script_no_html(
    caminho_script: pathlib.Path,
    caminho_html: pathlib.Path,
) -> str:
    """Grava no HTML a versão de um script de dados, derivada do conteúdo do arquivo.

    O GitHub Pages manda o navegador guardar os arquivos por 10 minutos.
    Sem versão, quem já tinha visitado a página recebia o HTML novo com o
    `dados.js` antigo, e a página quebrava no meio (aconteceu em 26/10/2026).
    Com `<arquivo>.js?v=<hash do conteúdo>`, qualquer mudança nos dados muda o
    endereço e força o download da versão nova; sem mudança, o cache segue
    valendo. Vale para `dados.js` e `municipios.js`.

    Args:
        caminho_script: O `.js` recém-gravado.
        caminho_html: O `index.html` que carrega o script.

    Returns:
        A versão gravada (primeiros caracteres do SHA-256 do conteúdo).

    Raises:
        FileNotFoundError: Se o HTML não existir.
        ValueError: Se o HTML não tiver exatamente uma tag do script.
    """
    if not caminho_html.exists():
        raise FileNotFoundError(f"HTML não encontrado: {caminho_html}")

    nome_script = caminho_script.name
    padrao_tag = re.compile(
        r'<script src="' + re.escape(nome_script) + r'(?:\?v=[0-9a-f]+)?"></script>'
    )
    conteudo_script = caminho_script.read_bytes()
    versao = hashlib.sha256(conteudo_script).hexdigest()[:TAMANHO_VERSAO]

    html = caminho_html.read_text(encoding="utf-8")
    quantidade_tags = len(padrao_tag.findall(html))
    if quantidade_tags != 1:
        raise ValueError(
            f"Esperada 1 tag de {nome_script} em {caminho_html}, achadas {quantidade_tags}."
        )

    tag_versionada = f'<script src="{nome_script}?v={versao}"></script>'
    html_versionado = padrao_tag.sub(tag_versionada, html)
    caminho_html.write_text(html_versionado, encoding="utf-8")
    LOGGER.info("Versão do %s gravada no HTML: %s.", nome_script, versao)
    return versao


def formatar_nome_municipio(nome_maiusculo: str) -> str:
    """Passa o nome da cidade do TSE (maiúsculas) para a grafia usual.

    Exemplos: "COLÔNIA DO GURGUÉIA" → "Colônia do Gurguéia";
    "SANTA BÁRBARA D'OESTE" → "Santa Bárbara d'Oeste"; "EMBU-GUAÇU" → "Embu-Guaçu".

    Args:
        nome_maiusculo: Nome como vem na base (maiúsculas, com acento).

    Returns:
        Nome com iniciais maiúsculas e conectivos em minúscula.
    """
    palavras_formatadas: list[str] = []
    for indice_palavra, palavra in enumerate(nome_maiusculo.split()):
        partes_hifen: list[str] = []
        for parte in palavra.split("-"):
            parte_minuscula = parte.lower()
            if parte_minuscula.startswith("d'") and len(parte_minuscula) > 2:
                parte_formatada = "d'" + parte_minuscula[2:].capitalize()
            elif parte_minuscula in CONECTIVOS_NOME and indice_palavra > 0:
                parte_formatada = parte_minuscula
            else:
                parte_formatada = parte_minuscula.capitalize()
            partes_hifen.append(parte_formatada)
        palavras_formatadas.append("-".join(partes_hifen))
    return " ".join(palavras_formatadas)


def montar_municipios(
    caminho_base: pathlib.Path,
    indicadores_brasil: pd.DataFrame,
    caminho_populacao: pathlib.Path,
    caminho_indicadores_ibge: pathlib.Path,
) -> dict[str, object]:
    """Monta a tabela de cidades (1º e 2º turno) para a seção "Cidades" do HTML.

    Cada linha: UF, nome, os campos de `CAMPOS_NUMERICOS_MUNICIPIO` e a população
    estimada do IBGE (`None` nas cidades do exterior). A soma de cada campo
    eleitoral nas 5.757 linhas (5.571 municípios + 186 cidades do exterior) tem
    de bater exatamente com o total nacional; todo município brasileiro tem de
    ter população, e a soma delas tem de bater com a do arquivo do IBGE.

    Args:
        caminho_base: Parquet da base por município.
        indicadores_brasil: Uma linha, Brasil com exterior.
        caminho_populacao: CSV `cd_municipio_ibge;populacao` já conferido.
        caminho_indicadores_ibge: CSV com alfabetização 2022 e PIB per capita 2023 já conferidos.

    Returns:
        Dicionário com `campos` (nomes das colunas) e `linhas` (listas de valores).

    Raises:
        FileNotFoundError: Se o parquet ou o CSV de população não existirem.
        ValueError: Se algum total não bater ou faltar população em algum município.
    """
    if not caminho_base.exists():
        raise FileNotFoundError(f"Base por município não encontrada: {caminho_base}")
    populacao = ler_csv_obrigatorio(caminho_populacao)
    populacao["cd_municipio_ibge"] = populacao["cd_municipio_ibge"].astype(str)

    colunas_lidas = ["sg_uf", "nm_municipio", "cd_municipio_ibge", "fl_exterior"] + CAMPOS_NUMERICOS_MUNICIPIO
    base_municipios = pd.read_parquet(caminho_base, columns=colunas_lidas)
    base_municipios = base_municipios.merge(populacao, on="cd_municipio_ibge", how="left")
    indicadores_ibge = ler_csv_obrigatorio(caminho_indicadores_ibge)
    indicadores_ibge["cd_municipio_ibge"] = indicadores_ibge["cd_municipio_ibge"].astype(str)
    base_municipios = base_municipios.merge(
        indicadores_ibge[["cd_municipio_ibge", "alfabetizacao_15mais_2022", "pib_per_capita_2023"]],
        on="cd_municipio_ibge",
        how="left",
    )
    linha_brasil = indicadores_brasil.iloc[0]

    # Todo município brasileiro tem os índices, exceto os criados depois do Censo 2022.
    mascara_sem_indice = (~base_municipios["fl_exterior"]) & base_municipios["alfabetizacao_15mais_2022"].isna()
    codigos_sem_indice = set(base_municipios.loc[mascara_sem_indice, "cd_municipio_ibge"])
    if codigos_sem_indice != MUNICIPIOS_SEM_INDICADORES_IBGE:
        raise ValueError(f"Municípios sem alfabetização/PIB diferentes do esperado: {sorted(codigos_sem_indice)}.")

    mascara_brasil = ~base_municipios["fl_exterior"]
    sem_populacao = int(base_municipios.loc[mascara_brasil, "populacao"].isna().sum())
    soma_populacao = int(base_municipios.loc[mascara_brasil, "populacao"].sum())
    total_populacao = int(populacao["populacao"].sum())
    if sem_populacao or soma_populacao != total_populacao:
        raise ValueError(
            f"População não fecha: {sem_populacao} municípios sem valor; "
            f"soma {soma_populacao} ≠ total do IBGE {total_populacao}."
        )

    for campo in CAMPOS_NUMERICOS_MUNICIPIO:
        soma_municipios = int(base_municipios[campo].sum())
        total_nacional = int(linha_brasil[campo])
        if soma_municipios != total_nacional:
            raise ValueError(
                f"Cidades não fecham com o Brasil em {campo}: {soma_municipios} ≠ {total_nacional}."
            )

    linhas: list[list[object]] = []
    for _, linha_municipio in base_municipios.iterrows():
        registro: list[object] = [
            linha_municipio["sg_uf"],
            formatar_nome_municipio(linha_municipio["nm_municipio"]),
        ]
        for campo in CAMPOS_NUMERICOS_MUNICIPIO:
            registro.append(int(linha_municipio[campo]))
        registro.append(inteiro_ou_nulo(linha_municipio["populacao"]))
        # Duas casas, como o IBGE publica: arredondar a uma casa mudava a inclinação da
        # dispersão na 3ª casa decimal (achado da conferência independente de 26/10/2026).
        registro.append(arredondar_ou_nulo(linha_municipio["alfabetizacao_15mais_2022"], 2))
        registro.append(inteiro_ou_nulo(linha_municipio["pib_per_capita_2023"]))
        linhas.append(registro)

    LOGGER.info(
        "Cidades montadas: %d linhas, totais conferidos com o Brasil; população %d (IBGE).",
        len(linhas),
        soma_populacao,
    )
    campos = ["uf", "nome"] + CAMPOS_NUMERICOS_MUNICIPIO + ["populacao", "alfabetizacao", "pib_per_capita"]
    return {"campos": campos, "linhas": linhas}


def gravar_municipios_js(municipios: dict[str, object], caminho_saida: pathlib.Path) -> None:
    """Grava a tabela de cidades como variável global JavaScript (arquivo à parte).

    Args:
        municipios: Saída de `montar_municipios`.
        caminho_saida: Caminho do `municipios.js`.
    """
    conteudo_json = json.dumps(municipios, ensure_ascii=False, separators=(",", ":"))
    conteudo_js = f"window.{NOME_VARIAVEL_MUNICIPIOS} = {conteudo_json};\n"
    caminho_saida.write_text(conteudo_js, encoding="utf-8")
    LOGGER.info("Gravado %s (%d bytes).", caminho_saida, len(conteudo_js.encode("utf-8")))


def gerar_dados_html() -> None:
    """Orquestra leitura, validação, montagem e gravação dos dados do HTML."""
    indicadores_brasil = ler_csv_obrigatorio(CAMINHO_INDICADORES_BRASIL)
    indicadores_regiao = ler_csv_obrigatorio(CAMINHO_INDICADORES_REGIAO)
    indicadores_uf = ler_csv_obrigatorio(CAMINHO_INDICADORES_UF)
    transferencias = ler_csv_obrigatorio(CAMINHO_TRANSFERENCIAS)
    transferencias_uf = ler_csv_obrigatorio(CAMINHO_TRANSFERENCIAS_UF)
    validar_colunas(transferencias_uf, ["uf", "n_efetivo", "kappa", "peso_regiao_pct"], "transferencias_uf")
    pct_caiado_por_uf = calcular_pct_caiado_por_uf(CAMINHO_BASE_MUNICIPIOS)

    validar_colunas(indicadores_brasil, COLUNAS_INDICADORES, "indicadores_brasil")
    validar_colunas(indicadores_regiao, COLUNAS_INDICADORES, "indicadores_regiao")
    validar_colunas(indicadores_uf, COLUNAS_INDICADORES, "indicadores_uf")
    validar_colunas(transferencias, COLUNAS_TRANSFERENCIAS, "transferencias")

    data_geracao = datetime.date.today().strftime("%d/%m/%Y")

    bloco_brasil = montar_bloco_brasil(indicadores_brasil)
    bloco_brasil["votos_1t_por_candidato"] = calcular_votos_1t_por_candidato(
        CAMINHO_BASE_MUNICIPIOS,
        int(bloco_brasil["validos_1t"]),
    )

    contagem_municipios = contar_municipios(CAMINHO_BASE_MUNICIPIOS)

    dados_html = {
        "meta": {
            "data_geracao": data_geracao,
            "eleicao": "Presidente 2026",
            "data_1t": "04/10/2026",
            "data_2t": "25/10/2026",
            "municipios_brasil": contagem_municipios["municipios_brasil"],
            "cidades_exterior": contagem_municipios["cidades_exterior"],
        },
        "brasil": bloco_brasil,
        "regioes": montar_lista_regioes(indicadores_regiao),
        "ufs": montar_lista_ufs(indicadores_uf, pct_caiado_por_uf),
        "migracao": montar_migracao(transferencias, "regiao")
        + montar_migracao(transferencias_uf, "uf"),
        "diagnosticos_uf": montar_diagnosticos_uf(transferencias_uf, CAMINHO_BASE_MUNICIPIOS),
        "validacao_uf": resumir_validacao_uf(CAMINHO_CURVA_VALIDACAO_UF),
        "diagnosticos_regiao": calcular_diagnosticos_regiao(CAMINHO_BASE_MUNICIPIOS),
        "conclusao": montar_conclusao(transferencias, indicadores_brasil, indicadores_regiao),
    }

    gravar_dados_js(dados_html, CAMINHO_SAIDA)
    versionar_script_no_html(CAMINHO_SAIDA, CAMINHO_HTML)

    municipios = montar_municipios(
        CAMINHO_BASE_MUNICIPIOS, indicadores_brasil, CAMINHO_POPULACAO, CAMINHO_INDICADORES_IBGE
    )
    gravar_municipios_js(municipios, CAMINHO_SAIDA_MUNICIPIOS)
    versionar_script_no_html(CAMINHO_SAIDA_MUNICIPIOS, CAMINHO_HTML)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    gerar_dados_html()
