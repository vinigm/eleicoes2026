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
import json
import logging
import pathlib

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
CAMINHO_BASE_MUNICIPIOS = (
    RAIZ_PROJETO / "dados" / "processados" / "presidente_municipio_turnos.parquet"
)
CAMINHO_SAIDA = RAIZ_PROJETO / "docs" / "dados.js"

COLUNA_VOTOS_CAIADO_1T = "votos_1t_55"

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


def montar_migracao(transferencias: pd.DataFrame) -> list[dict[str, object]]:
    """Converte a tabela longa de transferências em lista de registros.

    Mantém todas as especificações (E1 principal, E2 e E3 de sensibilidade)
    para que o HTML mostre a principal e cite as outras na metodologia.

    Args:
        transferencias: Tabela longa no formato da especificação.

    Returns:
        Lista de registros com β, IC 95% e votos estimados.
    """
    registros: list[dict[str, object]] = []

    for _, linha_transferencia in transferencias.iterrows():
        registro = {
            "especificacao": linha_transferencia["especificacao"],
            "regiao": linha_transferencia["regiao"],
            "origem": linha_transferencia["origem_1t"],
            "destino": linha_transferencia["destino_2t"],
            "beta": round(float(linha_transferencia["beta"]), CASAS_DECIMAIS_PERCENTUAL),
            "beta_ic_inf": round(
                float(linha_transferencia["beta_ic_inf"]), CASAS_DECIMAIS_PERCENTUAL
            ),
            "beta_ic_sup": round(
                float(linha_transferencia["beta_ic_sup"]), CASAS_DECIMAIS_PERCENTUAL
            ),
            "votos": int(round(float(linha_transferencia["votos"]))),
            "votos_ic_inf": int(round(float(linha_transferencia["votos_ic_inf"]))),
            "votos_ic_sup": int(round(float(linha_transferencia["votos_ic_sup"]))),
        }
        registros.append(registro)

    return registros


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


def gerar_dados_html() -> None:
    """Orquestra leitura, validação, montagem e gravação dos dados do HTML."""
    indicadores_brasil = ler_csv_obrigatorio(CAMINHO_INDICADORES_BRASIL)
    indicadores_regiao = ler_csv_obrigatorio(CAMINHO_INDICADORES_REGIAO)
    indicadores_uf = ler_csv_obrigatorio(CAMINHO_INDICADORES_UF)
    transferencias = ler_csv_obrigatorio(CAMINHO_TRANSFERENCIAS)
    pct_caiado_por_uf = calcular_pct_caiado_por_uf(CAMINHO_BASE_MUNICIPIOS)

    validar_colunas(indicadores_brasil, COLUNAS_INDICADORES, "indicadores_brasil")
    validar_colunas(indicadores_regiao, COLUNAS_INDICADORES, "indicadores_regiao")
    validar_colunas(indicadores_uf, COLUNAS_INDICADORES, "indicadores_uf")
    validar_colunas(transferencias, COLUNAS_TRANSFERENCIAS, "transferencias")

    data_geracao = datetime.date.today().strftime("%d/%m/%Y")

    dados_html = {
        "meta": {
            "data_geracao": data_geracao,
            "eleicao": "Presidente 2026",
            "data_1t": "04/10/2026",
            "data_2t": "25/10/2026",
        },
        "brasil": montar_bloco_brasil(indicadores_brasil),
        "regioes": montar_lista_regioes(indicadores_regiao),
        "ufs": montar_lista_ufs(indicadores_uf, pct_caiado_por_uf),
        "migracao": montar_migracao(transferencias),
        "diagnosticos_regiao": calcular_diagnosticos_regiao(CAMINHO_BASE_MUNICIPIOS),
    }

    gravar_dados_js(dados_html, CAMINHO_SAIDA)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    gerar_dados_html()
