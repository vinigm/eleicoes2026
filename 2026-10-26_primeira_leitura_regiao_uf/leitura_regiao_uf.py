"""Primeira leitura comparativa do 1º × 2º turno de presidente, por região e UF.

Lê a base por município gerada em `2026-10-26_base_presidente_1t_2t/` e
produz, para cada região e cada UF, a participação de Lula e Flávio nos
votos válidos de cada turno, a variação entre turnos e a origem do
crescimento de votos de cada candidato.

Rodar a partir da raiz do projeto com `python3 -I`.
"""

import logging
import pathlib

import pandas as pd

LOGGER = logging.getLogger(__name__)

RAIZ_PROJETO = pathlib.Path(__file__).resolve().parent.parent
CAMINHO_BASE_MUNICIPIOS = (
    RAIZ_PROJETO / "dados" / "processados" / "presidente_municipio_turnos.parquet"
)
PASTA_SAIDA = pathlib.Path(__file__).resolve().parent

COLUNAS_SOMAVEIS = [
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
]

ORDEM_REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul", "Exterior"]

PONTOS_PERCENTUAIS = 100.0


def carregar_base_municipios(caminho_base: pathlib.Path) -> pd.DataFrame:
    """Carrega a base por município e garante as colunas usadas na leitura.

    Args:
        caminho_base: Caminho do parquet com uma linha por município.

    Returns:
        DataFrame com uma linha por município.

    Raises:
        FileNotFoundError: Se o parquet não existir.
        KeyError: Se faltar alguma coluna necessária para as somas.
    """
    if not caminho_base.exists():
        raise FileNotFoundError(f"Base por município não encontrada: {caminho_base}")

    base_municipios = pd.read_parquet(caminho_base)

    colunas_necessarias = set(COLUNAS_SOMAVEIS) | {"sg_uf", "nm_regiao"}
    colunas_ausentes = colunas_necessarias.difference(base_municipios.columns)
    if colunas_ausentes:
        raise KeyError(f"Colunas ausentes na base: {sorted(colunas_ausentes)}")

    LOGGER.info(
        "Base carregada: %d municípios de %s.",
        len(base_municipios),
        caminho_base,
    )
    return base_municipios


def somar_por_grupo(
    base_municipios: pd.DataFrame,
    colunas_grupo: list[str],
) -> pd.DataFrame:
    """Soma as contagens de votos e eleitores por grupo geográfico.

    Somar contagens antes de calcular percentuais evita a média de
    percentuais, que daria o mesmo peso a municípios pequenos e grandes.

    Args:
        base_municipios: Base com uma linha por município.
        colunas_grupo: Colunas que definem o grupo (ex.: região, UF).

    Returns:
        DataFrame com uma linha por grupo e as contagens somadas.
    """
    contagens_por_grupo = base_municipios.groupby(colunas_grupo, as_index=False)[
        COLUNAS_SOMAVEIS
    ].sum()
    return contagens_por_grupo


def calcular_indicadores_turnos(contagens: pd.DataFrame) -> pd.DataFrame:
    """Calcula participação, variação entre turnos e origem dos ganhos.

    Regras:
        - Percentuais de candidato são sobre votos válidos do turno.
        - "Outros" no 1º turno = válidos menos Lula e Flávio, ou seja, os
          votos dos dez candidatos eliminados.
        - O ganho de cada candidato é a diferença líquida de votos entre os
          turnos. Não é transferência individual: o voto é secreto e o
          mesmo saldo pode vir de eleitores que trocaram de lado.
        - `fatia_ganho_lula_pct` = ganho de Lula sobre o ganho somado dos
          dois. Só é definida quando o ganho somado é positivo.

    Args:
        contagens: Contagens somadas por grupo, saída de `somar_por_grupo`.

    Returns:
        Cópia de `contagens` com as colunas de indicadores acrescentadas.
    """
    indicadores = contagens.copy()

    indicadores["pct_lula_1t"] = (
        PONTOS_PERCENTUAIS * indicadores["votos_1t_13"] / indicadores["validos_1t"]
    )
    indicadores["pct_flavio_1t"] = (
        PONTOS_PERCENTUAIS * indicadores["votos_1t_22"] / indicadores["validos_1t"]
    )
    indicadores["pct_outros_1t"] = (
        PONTOS_PERCENTUAIS - indicadores["pct_lula_1t"] - indicadores["pct_flavio_1t"]
    )
    indicadores["pct_lula_2t"] = (
        PONTOS_PERCENTUAIS * indicadores["votos_2t_13"] / indicadores["validos_2t"]
    )
    indicadores["variacao_lula_pp"] = (
        indicadores["pct_lula_2t"] - indicadores["pct_lula_1t"]
    )

    indicadores["comparecimento_pct_1t"] = (
        PONTOS_PERCENTUAIS
        * indicadores["comparecimento_1t"]
        / indicadores["aptos_1t"]
    )
    indicadores["comparecimento_pct_2t"] = (
        PONTOS_PERCENTUAIS
        * indicadores["comparecimento_2t"]
        / indicadores["aptos_2t"]
    )
    indicadores["variacao_comparecimento_pp"] = (
        indicadores["comparecimento_pct_2t"] - indicadores["comparecimento_pct_1t"]
    )

    indicadores["ganho_lula"] = indicadores["votos_2t_13"] - indicadores["votos_1t_13"]
    indicadores["ganho_flavio"] = (
        indicadores["votos_2t_22"] - indicadores["votos_1t_22"]
    )
    ganho_somado = indicadores["ganho_lula"] + indicadores["ganho_flavio"]
    mascara_ganho_positivo = ganho_somado > 0
    fatia_ganho_lula = PONTOS_PERCENTUAIS * indicadores["ganho_lula"] / ganho_somado
    indicadores["fatia_ganho_lula_pct"] = fatia_ganho_lula.where(
        mascara_ganho_positivo
    )

    indicadores["vencedor_1t"] = "Flávio"
    mascara_lula_1t = indicadores["votos_1t_13"] > indicadores["votos_1t_22"]
    indicadores.loc[mascara_lula_1t, "vencedor_1t"] = "Lula"

    indicadores["vencedor_2t"] = "Flávio"
    mascara_lula_2t = indicadores["votos_2t_13"] > indicadores["votos_2t_22"]
    indicadores.loc[mascara_lula_2t, "vencedor_2t"] = "Lula"

    return indicadores


def gravar_tabela(tabela: pd.DataFrame, nome_arquivo: str) -> None:
    """Grava a tabela em CSV (`;`, UTF-8) na pasta desta análise.

    Args:
        tabela: Tabela a gravar.
        nome_arquivo: Nome do arquivo CSV de saída.
    """
    caminho_saida = PASTA_SAIDA / nome_arquivo
    tabela.to_csv(caminho_saida, sep=";", index=False, encoding="utf-8")
    LOGGER.info("Gravado %s (%d linhas).", caminho_saida, len(tabela))


def executar_leitura() -> None:
    """Orquestra a leitura por região e por UF e grava as tabelas."""
    base_municipios = carregar_base_municipios(CAMINHO_BASE_MUNICIPIOS)

    contagens_regiao = somar_por_grupo(base_municipios, ["nm_regiao"])
    indicadores_regiao = calcular_indicadores_turnos(contagens_regiao)
    indicadores_regiao["nm_regiao"] = pd.Categorical(
        indicadores_regiao["nm_regiao"],
        categories=ORDEM_REGIOES,
        ordered=True,
    )
    indicadores_regiao = indicadores_regiao.sort_values("nm_regiao")

    contagens_uf = somar_por_grupo(base_municipios, ["nm_regiao", "sg_uf"])
    indicadores_uf = calcular_indicadores_turnos(contagens_uf)
    indicadores_uf = indicadores_uf.sort_values("variacao_lula_pp", ascending=False)

    contagens_brasil = base_municipios[COLUNAS_SOMAVEIS].sum().to_frame().T
    contagens_brasil.insert(0, "nm_regiao", "Brasil + exterior")
    indicadores_brasil = calcular_indicadores_turnos(contagens_brasil)

    gravar_tabela(indicadores_regiao, "indicadores_regiao.csv")
    gravar_tabela(indicadores_uf, "indicadores_uf.csv")
    gravar_tabela(indicadores_brasil, "indicadores_brasil.csv")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    executar_leitura()
