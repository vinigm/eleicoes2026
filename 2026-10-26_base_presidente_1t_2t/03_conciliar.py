"""Concilia a base de Presidente 2026 (1º e 2º turno) com as fontes oficiais.

Pergunta de negócio:
    Os números da base por município batem com os totais oficiais do TSE?

O script relê as fontes de forma independente do script 02 (outra leitura
dos JSONs e dos CSVs) e compara com as saídas gravadas por ele:

    (a) somas nacionais da base vs âncoras oficiais;
    (b) soma dos municípios por UF no 2º turno vs JSON de cada UF;
    (c) soma das UFs vs JSON nacional;
    (d) identidades contábeis por município, em cada turno;
    (e) todo JSON com totalização final ("tf" == "s") e "s.pst" == "100,00";
    (f) contagem de municípios por UF vs lista oficial;
    (g) extras: schema, chaves, IBGE, 1º turno vs CSV bruto por UF, longo vs
        largo, CSV vs parquet. Itens informativos (INFO) não reprovam.

Saída: <PASTA DESTE SCRIPT>/conciliacao.md. Código de saída 1 se houver FAIL.

Execução (os dados baixados são não confiáveis; usar o modo isolado):
    python3 -I 03_conciliar.py
"""

import dataclasses
import datetime
import json
import logging
import zipfile
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger("conciliar")

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------

PASTA_SCRIPT = Path(__file__).resolve().parent
RAIZ_PROJETO = PASTA_SCRIPT.parent

CODIGO_ELEICAO_2T = "6258"
PASTA_JSON_2T = RAIZ_PROJETO / "dados" / "json_tse" / CODIGO_ELEICAO_2T
CAMINHO_CONFIG_2T = PASTA_JSON_2T / "config" / "mun-e006258-cm.json"
SUFIXO_ARQUIVO_JSON_2T = "c0001-e006258-u.json"

PASTA_PROCESSADOS = RAIZ_PROJETO / "dados" / "processados"
CAMINHO_BASE_PARQUET = PASTA_PROCESSADOS / "presidente_municipio_turnos.parquet"
CAMINHO_BASE_CSV = PASTA_PROCESSADOS / "presidente_municipio_turnos.csv"
CAMINHO_LONGO_PARQUET = PASTA_PROCESSADOS / "presidente_municipio_candidato_long.parquet"
CAMINHO_RELATORIO = PASTA_SCRIPT / "conciliacao.md"

ZIP_CANDIDATO_1T = RAIZ_PROJETO / "votacao_candidato_munzona_2026.zip"
MEMBRO_CANDIDATO_1T = "votacao_candidato_munzona_2026_BR.csv"
ZIP_DETALHE_1T = RAIZ_PROJETO / "detalhe_votacao_munzona_2026.zip"
MEMBRO_DETALHE_1T = "detalhe_votacao_munzona_2026_BR.csv"
ENCODING_CSV_TSE = "latin-1"
SEPARADOR_CSV = ";"
ENCODING_CSV_SAIDA = "utf-8"

# --------------------------------------------------------------------------
# Âncoras oficiais (fornecidas pelo solicitante)
# --------------------------------------------------------------------------

ANCORAS_1T_VOTOS_POR_CANDIDATO = {
    22: 56104503,
    13: 53879538,
    70: 3448569,
    14: 2675887,
    55: 2605148,
    30: 326488,
    80: 122911,
    16: 43103,
    27: 40043,
    21: 22693,
    35: 16881,
    29: 15024,
}
ANCORAS_1T_METRICAS = {
    "validos": 119300788,
    "brancos": 2300798,
    "nulos": 3674249,
    "comparecimento": 125275835,
    "abstencao": 33469244,
    "aptos": 158745502,
    "nao_instaladas": 423,
}
ANCORAS_1T_EXTERIOR = {
    "aptos": 916534,
    "comparecimento": 341766,
}
ANCORAS_2T_VOTOS_POR_CANDIDATO = {
    13: 64256232,
    22: 59826041,
}
ANCORAS_2T_METRICAS = {
    "validos": 124082273,
    "brancos": 1430496,
    "nulos": 2723305,
    "comparecimento": 128236074,
    "abstencao": 30509005,
    "aptos": 158745502,
}

TOTAL_MUNICIPIOS_ESPERADO = 5757
TOTAL_MUNICIPIOS_BRASIL_ESPERADO = 5571
TOTAL_MUNICIPIOS_EXTERIOR_ESPERADO = 186
SIGLA_EXTERIOR = "ZZ"

MUNICIPIOS_ESPERADOS_POR_UF = {
    "AC": 22,
    "AL": 102,
    "AP": 16,
    "AM": 62,
    "BA": 417,
    "CE": 184,
    "DF": 1,
    "ES": 78,
    "GO": 246,
    "MA": 217,
    "MT": 142,
    "MS": 79,
    "MG": 853,
    "PR": 399,
    "PB": 223,
    "PA": 144,
    "PE": 185,
    "PI": 224,
    "RJ": 92,
    "RN": 167,
    "RS": 497,
    "RO": 52,
    "RR": 15,
    "SC": 295,
    "SE": 75,
    "SP": 645,
    "TO": 139,
    "ZZ": 186,
}

# Código IBGE da UF (2 primeiros dígitos do código de município IBGE).
CODIGO_IBGE_POR_UF = {
    "AC": "12",
    "AL": "27",
    "AP": "16",
    "AM": "13",
    "BA": "29",
    "CE": "23",
    "DF": "53",
    "ES": "32",
    "GO": "52",
    "MA": "21",
    "MT": "51",
    "MS": "50",
    "MG": "31",
    "PA": "15",
    "PB": "25",
    "PR": "41",
    "PE": "26",
    "PI": "22",
    "RJ": "33",
    "RN": "24",
    "RS": "43",
    "RO": "11",
    "RR": "14",
    "SC": "42",
    "SP": "35",
    "SE": "28",
    "TO": "17",
}

NUMEROS_CANDIDATOS_1T = (13, 14, 16, 21, 22, 27, 29, 30, 35, 55, 70, 80)
NUMEROS_CANDIDATOS_2T = (13, 22)
METRICAS = (
    "aptos",
    "comparecimento",
    "abstencao",
    "nao_instaladas",
    "validos",
    "brancos",
    "nulos",
)
COLUNAS_CHAVE = ["sg_uf", "cd_municipio_tse"]
COLUNAS_IDENTIFICACAO = [
    "sg_uf",
    "nm_regiao",
    "cd_municipio_tse",
    "cd_municipio_ibge",
    "nm_municipio",
    "fl_exterior",
]

# Campos lidos dos JSONs do 2º turno -> coluna correspondente na base.
COLUNA_BASE_POR_CAMPO_JSON = {
    "aptos": "aptos_2t",
    "comparecimento": "comparecimento_2t",
    "abstencao": "abstencao_2t",
    "nao_instaladas": "nao_instaladas_2t",
    "validos": "validos_2t",
    "brancos": "brancos_2t",
    "nulos": "nulos_2t",
    "votos_13": "votos_2t_13",
    "votos_22": "votos_2t_22",
}

# Colunas do CSV bruto do 1º turno -> métrica.
METRICA_POR_COLUNA_DETALHE_1T = {
    "QT_APTOS": "aptos",
    "QT_COMPARECIMENTO": "comparecimento",
    "QT_ABSTENCOES": "abstencao",
    "QT_ELEITORES_SECOES_NAO_INSTALADAS": "nao_instaladas",
    "QT_TOTAL_VOTOS_VALIDOS": "validos",
    "QT_VOTOS_BRANCOS": "brancos",
    "QT_TOTAL_VOTOS_NULOS": "nulos",
}

TOTALIZACAO_FINAL = "s"
PERCENTUAL_SECOES_APURADAS_FINAL = "100,00"
LIMITE_LINHAS_EXEMPLO = 20

STATUS_APROVADO = "PASS"
STATUS_REPROVADO = "FAIL"
STATUS_INFORMATIVO = "INFO"


# --------------------------------------------------------------------------
# Tipos
# --------------------------------------------------------------------------


class ErroJsonConciliacaoError(ValueError):
    """Um JSON da fonte oficial não tem a estrutura esperada."""


@dataclasses.dataclass(frozen=True)
class ValoresJson:
    """Valores de Presidente lidos de um JSON do 2º turno (município, UF ou BR).

    Attributes:
        totalizacao_final: Valor bruto de "tf".
        percentual_secoes_apuradas: Valor bruto de "s.pst".
        total_votos: Total de votos (v.tv).
        valores: Mapa campo -> inteiro, com as chaves de
            COLUNA_BASE_POR_CAMPO_JSON.
    """

    totalizacao_final: str
    percentual_secoes_apuradas: str
    total_votos: int
    valores: dict[str, int]


@dataclasses.dataclass
class ResultadoChecagem:
    """Resultado de uma checagem de conciliação.

    Attributes:
        codigo: Letra da checagem (a, b, ..., g1, g2, ...).
        titulo: Descrição curta.
        status: PASS, FAIL ou INFO.
        resumo: Linha com os números principais.
        detalhes: Linhas em Markdown (tabelas, exceções).
    """

    codigo: str
    titulo: str
    status: str
    resumo: str
    detalhes: list[str]


# --------------------------------------------------------------------------
# Funções puras: formatação e leitura de JSON
# --------------------------------------------------------------------------


def formatar_inteiro(valor: int) -> str:
    """Formata inteiro com ponto como separador de milhar (padrão pt-BR).

    Args:
        valor: Número inteiro.

    Returns:
        Texto, por exemplo "56.104.503".
    """
    texto_americano = f"{valor:,}"
    return texto_americano.replace(",", ".")


def classificar_status(aprovado: bool) -> str:
    """Converte um booleano em PASS ou FAIL.

    Args:
        aprovado: Resultado da comparação.

    Returns:
        "PASS" se aprovado, "FAIL" caso contrário.
    """
    if aprovado:
        return STATUS_APROVADO
    return STATUS_REPROVADO


def montar_tabela_markdown(cabecalho: list[str], linhas: list[list[str]]) -> list[str]:
    """Monta uma tabela Markdown.

    Args:
        cabecalho: Títulos das colunas.
        linhas: Linhas de dados, já formatadas como texto.

    Returns:
        Linhas de texto da tabela (cabeçalho, separador e dados).
    """
    linha_cabecalho = "| " + " | ".join(cabecalho) + " |"
    linha_separador = "|" + "|".join(["---"] * len(cabecalho)) + "|"
    tabela = [linha_cabecalho, linha_separador]

    for linha in linhas:
        tabela.append("| " + " | ".join(linha) + " |")
    return tabela


def converter_texto_em_inteiro(texto: object, nome_campo: str) -> int:
    """Converte número em texto do JSON em inteiro, rejeitando qualquer outro formato.

    Args:
        texto: Valor lido do JSON.
        nome_campo: Nome do campo para a mensagem de erro.

    Returns:
        Valor inteiro.

    Raises:
        ErroJsonConciliacaoError: Se não for texto com apenas dígitos.
    """
    if not isinstance(texto, str) or not texto.isdigit():
        raise ErroJsonConciliacaoError(f"Campo {nome_campo} não é inteiro: {texto!r}")
    return int(texto)


def extrair_votos_dos_candidatos(conteudo: dict) -> dict[int, int]:
    """Lê os votos por número de candidato do bloco de Presidente.

    Args:
        conteudo: JSON desserializado.

    Returns:
        Mapa número do candidato -> votos ("vap").

    Raises:
        ErroJsonConciliacaoError: Se a estrutura for inesperada ou houver
            candidato repetido.
    """
    cargos = conteudo.get("carg")
    if not isinstance(cargos, list) or len(cargos) != 1:
        raise ErroJsonConciliacaoError("JSON sem exatamente um cargo")

    votos_por_numero: dict[int, int] = {}
    agrupamentos = cargos[0].get("agr", [])

    for agrupamento in agrupamentos:
        for partido in agrupamento.get("par", []):
            for candidato in partido.get("cand", []):
                numero = converter_texto_em_inteiro(candidato.get("n"), "cand.n")
                votos = converter_texto_em_inteiro(candidato.get("vap"), "cand.vap")
                if numero in votos_por_numero:
                    raise ErroJsonConciliacaoError(f"Candidato repetido: {numero}")
                votos_por_numero[numero] = votos

    return votos_por_numero


def extrair_valores_json(conteudo: dict) -> ValoresJson:
    """Extrai métricas e votos dos candidatos 13 e 22 de um JSON do 2º turno.

    Candidato ausente no JSON conta como zero voto, regra idêntica à da base.

    Args:
        conteudo: JSON desserializado.

    Returns:
        Valores lidos, marcas de totalização e total de votos.

    Raises:
        ErroJsonConciliacaoError: Se faltar bloco ou campo ou houver valor
            não inteiro.
    """
    try:
        bloco_eleitorado = conteudo["e"]
        bloco_votos = conteudo["v"]
        bloco_secoes = conteudo["s"]
        marca_totalizacao = conteudo["tf"]

        votos_por_numero = extrair_votos_dos_candidatos(conteudo)

        valores = {
            "aptos": converter_texto_em_inteiro(bloco_eleitorado["te"], "e.te"),
            "comparecimento": converter_texto_em_inteiro(bloco_eleitorado["c"], "e.c"),
            "abstencao": converter_texto_em_inteiro(bloco_eleitorado["a"], "e.a"),
            "nao_instaladas": converter_texto_em_inteiro(bloco_eleitorado["esni"], "e.esni"),
            "validos": converter_texto_em_inteiro(bloco_votos["vv"], "v.vv"),
            "brancos": converter_texto_em_inteiro(bloco_votos["vb"], "v.vb"),
            "nulos": converter_texto_em_inteiro(bloco_votos["tvn"], "v.tvn"),
            "votos_13": votos_por_numero.get(13, 0),
            "votos_22": votos_por_numero.get(22, 0),
        }
        total_votos = converter_texto_em_inteiro(bloco_votos["tv"], "v.tv")
        percentual = bloco_secoes["pst"]
    except KeyError as erro:
        raise ErroJsonConciliacaoError(f"Campo ausente: {erro}") from erro

    valores_json = ValoresJson(
        totalizacao_final=marca_totalizacao,
        percentual_secoes_apuradas=percentual,
        total_votos=total_votos,
        valores=valores,
    )
    return valores_json


def contar_violacoes(mascara_violacao: pd.Series) -> int:
    """Conta quantas linhas violam uma identidade.

    Args:
        mascara_violacao: Série booleana, True onde a identidade falha.

    Returns:
        Quantidade de violações.
    """
    return int(mascara_violacao.sum())


# --------------------------------------------------------------------------
# Funções com I/O
# --------------------------------------------------------------------------


def ler_json(caminho: Path) -> dict:
    """Lê um JSON em UTF-8.

    Args:
        caminho: Arquivo a ler.

    Returns:
        Objeto JSON.

    Raises:
        ErroJsonConciliacaoError: Se o arquivo não existir, não for JSON
            válido ou não for um objeto.
    """
    if not caminho.is_file():
        raise ErroJsonConciliacaoError(f"Arquivo ausente: {caminho}")

    try:
        texto = caminho.read_text(encoding="utf-8")
        conteudo = json.loads(texto)
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroJsonConciliacaoError(f"JSON ilegível em {caminho}: {erro}") from erro

    if not isinstance(conteudo, dict):
        raise ErroJsonConciliacaoError(f"JSON de {caminho} não é um objeto")
    return conteudo


def montar_caminho_json(sigla_uf_minuscula: str, codigo_municipio: str | None) -> Path:
    """Monta o caminho local de um JSON do 2º turno (nacional, UF ou município).

    Args:
        sigla_uf_minuscula: "br" ou sigla da UF.
        codigo_municipio: Código TSE de 5 dígitos, ou None para UF/Brasil.

    Returns:
        Caminho em <PROJ>/dados/json_tse/6258/dados/....
    """
    if codigo_municipio is None:
        nome_arquivo = f"{sigla_uf_minuscula}-{SUFIXO_ARQUIVO_JSON_2T}"
    else:
        nome_arquivo = f"{sigla_uf_minuscula}{codigo_municipio}-{SUFIXO_ARQUIVO_JSON_2T}"
    return PASTA_JSON_2T / "dados" / sigla_uf_minuscula / nome_arquivo


def ler_csv_do_zip(caminho_zip: Path, nome_membro: str, colunas: list[str]) -> pd.DataFrame:
    """Lê um CSV do TSE de dentro do zip, tudo como texto.

    Args:
        caminho_zip: Arquivo zip.
        nome_membro: CSV dentro do zip.
        colunas: Colunas a ler.

    Returns:
        Tabela em texto.
    """
    with zipfile.ZipFile(caminho_zip) as arquivo_zip:
        with arquivo_zip.open(nome_membro) as arquivo_csv:
            tabela = pd.read_csv(
                arquivo_csv,
                sep=SEPARADOR_CSV,
                encoding=ENCODING_CSV_TSE,
                dtype=str,
                usecols=colunas,
                keep_default_na=False,
            )
    return tabela


# --------------------------------------------------------------------------
# Checagens
# --------------------------------------------------------------------------


def coletar_comparacoes_de_ancoras(base: pd.DataFrame) -> list[tuple[str, int, int]]:
    """Calcula, para cada âncora oficial, o valor obtido na base.

    Args:
        base: Base por município (parquet).

    Returns:
        Lista de tuplas (descrição, valor esperado, valor obtido).
    """
    comparacoes: list[tuple[str, int, int]] = []

    for numero, esperado in ANCORAS_1T_VOTOS_POR_CANDIDATO.items():
        obtido = int(base[f"votos_1t_{numero}"].sum())
        comparacoes.append((f"1T votos candidato {numero}", esperado, obtido))

    for metrica, esperado in ANCORAS_1T_METRICAS.items():
        obtido = int(base[f"{metrica}_1t"].sum())
        comparacoes.append((f"1T {metrica}", esperado, obtido))

    base_exterior = base[base["sg_uf"] == SIGLA_EXTERIOR]
    for metrica, esperado in ANCORAS_1T_EXTERIOR.items():
        obtido = int(base_exterior[f"{metrica}_1t"].sum())
        comparacoes.append((f"1T ZZ {metrica}", esperado, obtido))

    for numero, esperado in ANCORAS_2T_VOTOS_POR_CANDIDATO.items():
        obtido = int(base[f"votos_2t_{numero}"].sum())
        comparacoes.append((f"2T votos candidato {numero}", esperado, obtido))

    for metrica, esperado in ANCORAS_2T_METRICAS.items():
        obtido = int(base[f"{metrica}_2t"].sum())
        comparacoes.append((f"2T {metrica}", esperado, obtido))

    return comparacoes


def checar_ancoras(base: pd.DataFrame) -> ResultadoChecagem:
    """Checagem (a): somas nacionais da base contra as âncoras oficiais.

    Args:
        base: Base por município (parquet).

    Returns:
        Resultado com uma linha por âncora.
    """
    comparacoes = coletar_comparacoes_de_ancoras(base)

    linhas: list[list[str]] = []
    divergencias = 0

    for descricao, esperado, obtido in comparacoes:
        bateu = esperado == obtido
        if not bateu:
            divergencias += 1
        linhas.append(
            [
                descricao,
                formatar_inteiro(esperado),
                formatar_inteiro(obtido),
                formatar_inteiro(obtido - esperado),
                classificar_status(bateu),
            ]
        )

    detalhes = montar_tabela_markdown(
        ["Âncora", "Esperado", "Obtido", "Diferença", "Status"],
        linhas,
    )
    total_ancoras = len(comparacoes)
    resumo = f"{total_ancoras - divergencias}/{total_ancoras} âncoras batem; divergências: {divergencias}"
    resultado = ResultadoChecagem(
        codigo="a",
        titulo="Somas nacionais vs âncoras oficiais",
        status=classificar_status(divergencias == 0),
        resumo=resumo,
        detalhes=detalhes,
    )
    return resultado


def carregar_json_das_ufs(siglas_uf: list[str]) -> tuple[dict[str, ValoresJson], list[str]]:
    """Lê o JSON de cada UF (inclusive "ZZ") do 2º turno.

    Args:
        siglas_uf: Siglas em maiúsculas.

    Returns:
        Tupla (valores por UF, mensagens de erro).
    """
    valores_por_uf: dict[str, ValoresJson] = {}
    erros: list[str] = []

    for sigla in siglas_uf:
        caminho = montar_caminho_json(sigla.lower(), None)
        try:
            conteudo = ler_json(caminho)
            valores_por_uf[sigla] = extrair_valores_json(conteudo)
        except ErroJsonConciliacaoError as erro:
            erros.append(f"{sigla}: {erro}")

    return valores_por_uf, erros


def checar_soma_municipios_vs_uf(
    base: pd.DataFrame,
    valores_por_uf: dict[str, ValoresJson],
    erros_leitura: list[str],
) -> ResultadoChecagem:
    """Checagem (b): soma dos municípios por UF (2º turno) vs JSON de cada UF.

    Args:
        base: Base por município.
        valores_por_uf: Valores lidos dos JSONs de UF.
        erros_leitura: Erros ao ler os JSONs de UF.

    Returns:
        Resultado com contagem de comparações e lista de divergências.
    """
    colunas_2t = list(COLUNA_BASE_POR_CAMPO_JSON.values())
    soma_por_uf = base.groupby("sg_uf")[colunas_2t].sum()

    divergencias: list[list[str]] = []
    total_comparacoes = 0

    for sigla, valores_json in valores_por_uf.items():
        for campo, coluna in COLUNA_BASE_POR_CAMPO_JSON.items():
            total_comparacoes += 1
            valor_base = int(soma_por_uf.loc[sigla, coluna])
            valor_json = valores_json.valores[campo]
            if valor_base != valor_json:
                divergencias.append(
                    [
                        sigla,
                        coluna,
                        formatar_inteiro(valor_json),
                        formatar_inteiro(valor_base),
                        formatar_inteiro(valor_base - valor_json),
                    ]
                )

    ufs_na_base = set(soma_por_uf.index)
    ufs_sem_json = sorted(ufs_na_base.difference(valores_por_uf.keys()))

    aprovado = not divergencias and not erros_leitura and not ufs_sem_json
    detalhes: list[str] = []
    if divergencias:
        detalhes.extend(
            montar_tabela_markdown(
                ["UF", "Coluna", "JSON da UF", "Soma dos municípios", "Diferença"],
                divergencias[:LIMITE_LINHAS_EXEMPLO],
            )
        )
    for mensagem in erros_leitura:
        detalhes.append(f"- Erro de leitura: {mensagem}")
    if ufs_sem_json:
        detalhes.append(f"- UFs da base sem JSON de UF: {ufs_sem_json}")

    resumo = (
        f"{len(valores_por_uf)} UFs x {len(COLUNA_BASE_POR_CAMPO_JSON)} campos = "
        f"{total_comparacoes} comparações; divergências: {len(divergencias)}"
    )
    resultado = ResultadoChecagem(
        codigo="b",
        titulo="Soma dos municípios por UF (2T) vs JSON de cada UF",
        status=classificar_status(aprovado),
        resumo=resumo,
        detalhes=detalhes,
    )
    return resultado


def checar_soma_ufs_vs_nacional(
    base: pd.DataFrame,
    valores_por_uf: dict[str, ValoresJson],
    valores_nacional: ValoresJson | None,
    erro_nacional: str,
) -> ResultadoChecagem:
    """Checagem (c): soma das UFs vs JSON nacional (e base vs JSON nacional).

    Args:
        base: Base por município.
        valores_por_uf: Valores lidos dos JSONs de UF.
        valores_nacional: Valores do JSON nacional, ou None se ilegível.
        erro_nacional: Mensagem de erro ao ler o JSON nacional.

    Returns:
        Resultado com as divergências, se houver.
    """
    if valores_nacional is None:
        return ResultadoChecagem(
            codigo="c",
            titulo="Soma das UFs vs JSON nacional",
            status=STATUS_REPROVADO,
            resumo=f"JSON nacional ilegível: {erro_nacional}",
            detalhes=[],
        )

    linhas: list[list[str]] = []
    divergencias = 0

    for campo, coluna in COLUNA_BASE_POR_CAMPO_JSON.items():
        soma_ufs = 0
        for valores_json in valores_por_uf.values():
            soma_ufs += valores_json.valores[campo]

        valor_nacional = valores_nacional.valores[campo]
        soma_base = int(base[coluna].sum())

        ufs_batem = soma_ufs == valor_nacional
        base_bate = soma_base == valor_nacional
        if not (ufs_batem and base_bate):
            divergencias += 1

        linhas.append(
            [
                campo,
                formatar_inteiro(valor_nacional),
                formatar_inteiro(soma_ufs),
                formatar_inteiro(soma_base),
                classificar_status(ufs_batem and base_bate),
            ]
        )

    detalhes = montar_tabela_markdown(
        ["Campo", "JSON nacional", "Soma dos JSONs de UF", "Soma da base", "Status"],
        linhas,
    )
    resumo = (
        f"{len(valores_por_uf)} UFs; {len(COLUNA_BASE_POR_CAMPO_JSON)} campos; "
        f"divergências: {divergencias}"
    )
    resultado = ResultadoChecagem(
        codigo="c",
        titulo="Soma das UFs vs JSON nacional (e soma da base vs JSON nacional)",
        status=classificar_status(divergencias == 0),
        resumo=resumo,
        detalhes=detalhes,
    )
    return resultado


def listar_municipios_violadores(base: pd.DataFrame, mascara: pd.Series) -> list[str]:
    """Lista até LIMITE_LINHAS_EXEMPLO municípios (UF/código/nome) que violam uma regra.

    Args:
        base: Base por município.
        mascara: Série booleana, True onde há violação.

    Returns:
        Linhas de texto para o relatório.
    """
    exemplos: list[str] = []
    violadores = base.loc[mascara, ["sg_uf", "cd_municipio_tse", "nm_municipio"]]

    for _, linha in violadores.head(LIMITE_LINHAS_EXEMPLO).iterrows():
        exemplos.append(f"  - {linha['sg_uf']}/{linha['cd_municipio_tse']} {linha['nm_municipio']}")
    return exemplos


def checar_identidades(
    base: pd.DataFrame,
    violacoes_total_votos_json: tuple[int, list[str]],
) -> ResultadoChecagem:
    """Checagem (d): identidades contábeis por município, em cada turno.

    Identidades:
        1. comparecimento == validos + brancos + nulos
        2. aptos == comparecimento + abstencao + nao_instaladas
        3. validos == soma dos votos dos candidatos
        4. (2T, JSON) v.tv == e.c em cada município

    Args:
        base: Base por município.
        violacoes_total_votos_json: Tupla (quantidade de municípios em que v.tv != e.c
            no JSON, exemplos), calculada na leitura dos JSONs.

    Returns:
        Resultado com violações por identidade e turno.
    """
    linhas: list[list[str]] = []
    detalhes_exemplos: list[str] = []
    total_violacoes = 0

    for rotulo, numeros in (("1t", NUMEROS_CANDIDATOS_1T), ("2t", NUMEROS_CANDIDATOS_2T)):
        comparecimento = base[f"comparecimento_{rotulo}"]
        aptos = base[f"aptos_{rotulo}"]
        validos = base[f"validos_{rotulo}"]
        brancos = base[f"brancos_{rotulo}"]
        nulos = base[f"nulos_{rotulo}"]
        abstencao = base[f"abstencao_{rotulo}"]
        nao_instaladas = base[f"nao_instaladas_{rotulo}"]

        soma_candidatos = pd.Series(0, index=base.index, dtype="int64")
        for numero in numeros:
            soma_candidatos = soma_candidatos + base[f"votos_{rotulo}_{numero}"]

        regras = [
            ("comparecimento == validos + brancos + nulos", comparecimento != validos + brancos + nulos),
            ("aptos == comparecimento + abstencao + nao_instaladas", aptos != comparecimento + abstencao + nao_instaladas),
            ("validos == soma dos votos dos candidatos", validos != soma_candidatos),
        ]

        for descricao, mascara_violacao in regras:
            quantidade = contar_violacoes(mascara_violacao)
            total_violacoes += quantidade
            linhas.append(
                [
                    rotulo.upper(),
                    descricao,
                    formatar_inteiro(len(base)),
                    formatar_inteiro(quantidade),
                    classificar_status(quantidade == 0),
                ]
            )
            if quantidade > 0:
                detalhes_exemplos.append(f"- {rotulo.upper()} {descricao}: exemplos")
                detalhes_exemplos.extend(listar_municipios_violadores(base, mascara_violacao))

    quantidade_tv, exemplos_tv = violacoes_total_votos_json
    total_violacoes += quantidade_tv
    linhas.append(
        [
            "2T (JSON)",
            "v.tv == e.c",
            formatar_inteiro(len(base)),
            formatar_inteiro(quantidade_tv),
            classificar_status(quantidade_tv == 0),
        ]
    )
    if quantidade_tv > 0:
        detalhes_exemplos.append("- 2T JSON v.tv != e.c: exemplos")
        detalhes_exemplos.extend(exemplos_tv)

    detalhes = montar_tabela_markdown(
        ["Turno", "Identidade", "Municípios testados", "Violações", "Status"],
        linhas,
    )
    detalhes.extend(detalhes_exemplos)

    resumo = (
        f"{len(linhas)} identidades testadas em {len(base)} municípios cada; "
        f"violações totais: {total_violacoes}"
    )
    resultado = ResultadoChecagem(
        codigo="d",
        titulo="Identidades contábeis por município",
        status=classificar_status(total_violacoes == 0),
        resumo=resumo,
        detalhes=detalhes,
    )
    return resultado


def ler_todos_os_jsons_de_municipio(
    base: pd.DataFrame,
) -> tuple[dict[tuple[str, str], ValoresJson], list[str]]:
    """Lê o JSON de cada município da base (2º turno).

    Args:
        base: Base por município (define quais arquivos ler).

    Returns:
        Tupla (valores por município, mensagens de erro de leitura).
    """
    valores_por_municipio: dict[tuple[str, str], ValoresJson] = {}
    erros: list[str] = []

    pares = base[COLUNAS_CHAVE].itertuples(index=False, name=None)
    for sigla, codigo in pares:
        caminho = montar_caminho_json(sigla.lower(), codigo)
        try:
            conteudo = ler_json(caminho)
            valores_por_municipio[(sigla, codigo)] = extrair_valores_json(conteudo)
        except ErroJsonConciliacaoError as erro:
            erros.append(f"{sigla}/{codigo}: {erro}")

    return valores_por_municipio, erros


def contar_total_votos_diferente_do_comparecimento(
    valores_por_municipio: dict[tuple[str, str], ValoresJson],
) -> tuple[int, list[str]]:
    """Conta municípios em que v.tv (JSON) difere de e.c (JSON).

    Args:
        valores_por_municipio: Valores lidos dos JSONs de município.

    Returns:
        Tupla (quantidade, exemplos de até LIMITE_LINHAS_EXEMPLO municípios).
    """
    quantidade = 0
    exemplos: list[str] = []

    for chave, valores_json in valores_por_municipio.items():
        comparecimento = valores_json.valores["comparecimento"]
        if valores_json.total_votos != comparecimento:
            quantidade += 1
            if len(exemplos) < LIMITE_LINHAS_EXEMPLO:
                exemplos.append(
                    f"  - {chave[0]}/{chave[1]}: tv={valores_json.total_votos} c={comparecimento}"
                )

    return quantidade, exemplos


def checar_totalizacao_final(
    valores_por_municipio: dict[tuple[str, str], ValoresJson],
    erros_municipios: list[str],
    valores_por_uf: dict[str, ValoresJson],
    valores_nacional: ValoresJson | None,
    total_esperado_municipios: int,
) -> ResultadoChecagem:
    """Checagem (e): totalização final e 100,00% de seções apuradas em todo JSON.

    Args:
        valores_por_municipio: JSONs de município lidos.
        erros_municipios: Erros de leitura de município (arquivo ausente etc.).
        valores_por_uf: JSONs de UF lidos.
        valores_nacional: JSON nacional lido (ou None).
        total_esperado_municipios: Quantidade de municípios na base.

    Returns:
        Resultado com as exceções listadas.
    """
    excecoes: list[str] = []

    for chave, valores_json in valores_por_municipio.items():
        if valores_json.totalizacao_final != TOTALIZACAO_FINAL:
            excecoes.append(f"- município {chave[0]}/{chave[1]}: tf={valores_json.totalizacao_final!r}")
        if valores_json.percentual_secoes_apuradas != PERCENTUAL_SECOES_APURADAS_FINAL:
            excecoes.append(
                f"- município {chave[0]}/{chave[1]}: s.pst={valores_json.percentual_secoes_apuradas!r}"
            )

    for sigla, valores_json in valores_por_uf.items():
        if valores_json.totalizacao_final != TOTALIZACAO_FINAL:
            excecoes.append(f"- UF {sigla}: tf={valores_json.totalizacao_final!r}")
        if valores_json.percentual_secoes_apuradas != PERCENTUAL_SECOES_APURADAS_FINAL:
            excecoes.append(f"- UF {sigla}: s.pst={valores_json.percentual_secoes_apuradas!r}")

    if valores_nacional is not None:
        if valores_nacional.totalizacao_final != TOTALIZACAO_FINAL:
            excecoes.append(f"- nacional: tf={valores_nacional.totalizacao_final!r}")
        if valores_nacional.percentual_secoes_apuradas != PERCENTUAL_SECOES_APURADAS_FINAL:
            excecoes.append(f"- nacional: s.pst={valores_nacional.percentual_secoes_apuradas!r}")

    detalhes: list[str] = []
    for mensagem in erros_municipios:
        detalhes.append(f"- erro de leitura: {mensagem}")
    detalhes.extend(excecoes[: LIMITE_LINHAS_EXEMPLO * 5])

    aprovado = not excecoes and not erros_municipios and (
        len(valores_por_municipio) == total_esperado_municipios
    )
    resumo = (
        f"{len(valores_por_municipio)}/{total_esperado_municipios} municípios lidos + "
        f"{len(valores_por_uf)} UFs + nacional; exceções: {len(excecoes)}; "
        f"erros de leitura: {len(erros_municipios)}"
    )
    resultado = ResultadoChecagem(
        codigo="e",
        titulo='Todo JSON com tf == "s" e s.pst == "100,00"',
        status=classificar_status(aprovado),
        resumo=resumo,
        detalhes=detalhes,
    )
    return resultado


def checar_contagem_por_uf(
    base: pd.DataFrame,
    contagem_config_por_uf: dict[str, int],
) -> ResultadoChecagem:
    """Checagem (f): municípios por UF vs lista oficial (e vs o config do TSE).

    Args:
        base: Base por município.
        contagem_config_por_uf: Municípios por UF no arquivo de config.

    Returns:
        Resultado com a tabela por UF.
    """
    contagem_base = base.groupby("sg_uf").size()
    linhas: list[list[str]] = []
    divergencias = 0

    for sigla, esperado in MUNICIPIOS_ESPERADOS_POR_UF.items():
        na_base = int(contagem_base.get(sigla, 0))
        no_config = contagem_config_por_uf.get(sigla, 0)
        bateu = na_base == esperado and no_config == esperado
        if not bateu:
            divergencias += 1
        linhas.append(
            [
                sigla,
                str(esperado),
                str(na_base),
                str(no_config),
                classificar_status(bateu),
            ]
        )

    total_base = len(base)
    total_brasil = int((base["sg_uf"] != SIGLA_EXTERIOR).sum())
    total_exterior = int((base["sg_uf"] == SIGLA_EXTERIOR).sum())
    ufs_fora_da_lista = sorted(set(contagem_base.index).difference(MUNICIPIOS_ESPERADOS_POR_UF.keys()))

    totais_ok = (
        total_base == TOTAL_MUNICIPIOS_ESPERADO
        and total_brasil == TOTAL_MUNICIPIOS_BRASIL_ESPERADO
        and total_exterior == TOTAL_MUNICIPIOS_EXTERIOR_ESPERADO
    )

    detalhes = montar_tabela_markdown(
        ["UF", "Esperado", "Base", "Config TSE", "Status"],
        linhas,
    )
    detalhes.append("")
    detalhes.append(
        f"Totais: base={total_base} (esperado {TOTAL_MUNICIPIOS_ESPERADO}); "
        f"Brasil={total_brasil} (esperado {TOTAL_MUNICIPIOS_BRASIL_ESPERADO}); "
        f"exterior={total_exterior} (esperado {TOTAL_MUNICIPIOS_EXTERIOR_ESPERADO})."
    )
    if ufs_fora_da_lista:
        detalhes.append(f"UFs na base fora da lista oficial: {ufs_fora_da_lista}")

    aprovado = divergencias == 0 and totais_ok and not ufs_fora_da_lista
    resumo = (
        f"{len(MUNICIPIOS_ESPERADOS_POR_UF)} UFs; divergências por UF: {divergencias}; "
        f"total={total_base}, Brasil={total_brasil}, exterior={total_exterior}"
    )
    resultado = ResultadoChecagem(
        codigo="f",
        titulo="Contagem de municípios por UF vs lista oficial",
        status=classificar_status(aprovado),
        resumo=resumo,
        detalhes=detalhes,
    )
    return resultado


def checar_schema_e_chaves(base: pd.DataFrame) -> ResultadoChecagem:
    """Checagem extra (g1): chave única, ausência de nulos e tipos inteiros.

    Args:
        base: Base por município.

    Returns:
        Resultado com os problemas encontrados.
    """
    problemas: list[str] = []

    chaves_duplicadas = int(base.duplicated(subset=COLUNAS_CHAVE).sum())
    if chaves_duplicadas > 0:
        problemas.append(f"- {chaves_duplicadas} chaves duplicadas (sg_uf, cd_municipio_tse)")

    colunas_codigo_invalidas = int((base["cd_municipio_tse"].str.len() != 5).sum())
    if colunas_codigo_invalidas > 0:
        problemas.append(f"- {colunas_codigo_invalidas} códigos TSE sem 5 caracteres")

    colunas_numericas = [coluna for coluna in base.columns if coluna not in COLUNAS_IDENTIFICACAO]
    colunas_nao_int64: list[str] = []
    for coluna in colunas_numericas:
        if str(base[coluna].dtype) != "int64":
            colunas_nao_int64.append(coluna)
    if colunas_nao_int64:
        problemas.append(f"- colunas numéricas fora de int64: {colunas_nao_int64}")

    nulos_numericos = int(base[colunas_numericas].isna().sum().sum())
    if nulos_numericos > 0:
        problemas.append(f"- {nulos_numericos} nulos nas colunas numéricas")

    colunas_identificacao_com_nulo = base[["sg_uf", "nm_regiao", "cd_municipio_tse", "nm_municipio", "fl_exterior"]]
    nulos_identificacao = int(colunas_identificacao_com_nulo.isna().sum().sum())
    if nulos_identificacao > 0:
        problemas.append(f"- {nulos_identificacao} nulos nas colunas de identificação")

    negativos = int((base[colunas_numericas] < 0).sum().sum())
    if negativos > 0:
        problemas.append(f"- {negativos} valores negativos")

    resumo = (
        f"{len(base)} linhas, {len(base.columns)} colunas; {len(colunas_numericas)} colunas numéricas "
        f"em int64 sem nulos nem negativos; problemas: {len(problemas)}"
    )
    resultado = ResultadoChecagem(
        codigo="g1",
        titulo="Extra: chave única, nulos, tipos e códigos",
        status=classificar_status(len(problemas) == 0),
        resumo=resumo,
        detalhes=problemas,
    )
    return resultado


def checar_codigos_ibge(base: pd.DataFrame) -> ResultadoChecagem:
    """Checagem extra (g2): código IBGE preenchido no Brasil, nulo no exterior.

    Verifica formato de 7 dígitos, unicidade e coerência do prefixo com a UF.

    Args:
        base: Base por município.

    Returns:
        Resultado com os problemas encontrados.
    """
    problemas: list[str] = []
    mascara_exterior = base["fl_exterior"]
    mascara_brasil = ~mascara_exterior

    ibge_brasil = base.loc[mascara_brasil, "cd_municipio_ibge"]
    nulos_no_brasil = int(ibge_brasil.isna().sum())
    if nulos_no_brasil > 0:
        problemas.append(f"- {nulos_no_brasil} municípios do Brasil sem código IBGE")

    ibge_exterior = base.loc[mascara_exterior, "cd_municipio_ibge"]
    preenchidos_no_exterior = int(ibge_exterior.notna().sum())
    if preenchidos_no_exterior > 0:
        problemas.append(f"- {preenchidos_no_exterior} cidades do exterior com código IBGE")

    ibge_preenchido = ibge_brasil.dropna()
    fora_do_formato = int((ibge_preenchido.str.len() != 7).sum())
    if fora_do_formato > 0:
        problemas.append(f"- {fora_do_formato} códigos IBGE fora do formato de 7 dígitos")

    repetidos = int(ibge_preenchido.duplicated().sum())
    if repetidos > 0:
        problemas.append(f"- {repetidos} códigos IBGE repetidos")

    prefixo_incoerente = 0
    brasil = base.loc[mascara_brasil, ["sg_uf", "cd_municipio_ibge"]].dropna()
    for sigla, codigo_ibge in brasil.itertuples(index=False, name=None):
        prefixo_esperado = CODIGO_IBGE_POR_UF.get(sigla, "??")
        if not codigo_ibge.startswith(prefixo_esperado):
            prefixo_incoerente += 1
    if prefixo_incoerente > 0:
        problemas.append(f"- {prefixo_incoerente} códigos IBGE com prefixo incoerente com a UF")

    resumo = (
        f"IBGE distintos no Brasil: {ibge_preenchido.nunique()}; nulos no exterior: "
        f"{len(ibge_exterior) - preenchidos_no_exterior}/{len(ibge_exterior)}; problemas: {len(problemas)}"
    )
    resultado = ResultadoChecagem(
        codigo="g2",
        titulo="Extra: código IBGE (formato, unicidade, prefixo da UF, nulo no exterior)",
        status=classificar_status(len(problemas) == 0),
        resumo=resumo,
        detalhes=problemas,
    )
    return resultado


def checar_primeiro_turno_vs_csv_bruto(base: pd.DataFrame) -> ResultadoChecagem:
    """Checagem extra (g3): 1º turno da base vs soma por UF direto dos CSVs brutos.

    Reagrega os CSVs originais apenas por UF (sem passar pela chave de
    município), de forma independente do script 02.

    Args:
        base: Base por município.

    Returns:
        Resultado com as divergências, se houver.
    """
    colunas_detalhe = ["SG_UF"] + list(METRICA_POR_COLUNA_DETALHE_1T.keys())
    detalhe = ler_csv_do_zip(ZIP_DETALHE_1T, MEMBRO_DETALHE_1T, colunas_detalhe)
    for coluna in METRICA_POR_COLUNA_DETALHE_1T:
        detalhe[coluna] = detalhe[coluna].astype("int64")
    soma_detalhe_por_uf = detalhe.groupby("SG_UF").sum()

    colunas_candidato = ["SG_UF", "NR_CANDIDATO", "QT_VOTOS_NOMINAIS_VALIDOS"]
    candidato = ler_csv_do_zip(ZIP_CANDIDATO_1T, MEMBRO_CANDIDATO_1T, colunas_candidato)
    candidato["QT_VOTOS_NOMINAIS_VALIDOS"] = candidato["QT_VOTOS_NOMINAIS_VALIDOS"].astype("int64")
    soma_candidato_por_uf = candidato.groupby(["SG_UF", "NR_CANDIDATO"])["QT_VOTOS_NOMINAIS_VALIDOS"].sum()

    colunas_1t = [f"{metrica}_1t" for metrica in METRICAS]
    for numero in NUMEROS_CANDIDATOS_1T:
        colunas_1t.append(f"votos_1t_{numero}")
    soma_base_por_uf = base.groupby("sg_uf")[colunas_1t].sum()

    divergencias: list[list[str]] = []
    total_comparacoes = 0

    for sigla in soma_base_por_uf.index:
        for coluna_bruta, metrica in METRICA_POR_COLUNA_DETALHE_1T.items():
            total_comparacoes += 1
            valor_bruto = int(soma_detalhe_por_uf.loc[sigla, coluna_bruta])
            valor_base = int(soma_base_por_uf.loc[sigla, f"{metrica}_1t"])
            if valor_bruto != valor_base:
                divergencias.append([sigla, f"{metrica}_1t", formatar_inteiro(valor_bruto), formatar_inteiro(valor_base)])

        for numero in NUMEROS_CANDIDATOS_1T:
            total_comparacoes += 1
            valor_bruto = int(soma_candidato_por_uf.get((sigla, str(numero)), 0))
            valor_base = int(soma_base_por_uf.loc[sigla, f"votos_1t_{numero}"])
            if valor_bruto != valor_base:
                divergencias.append([sigla, f"votos_1t_{numero}", formatar_inteiro(valor_bruto), formatar_inteiro(valor_base)])

    detalhes: list[str] = []
    if divergencias:
        detalhes.extend(
            montar_tabela_markdown(
                ["UF", "Coluna", "CSV bruto", "Base"],
                divergencias[:LIMITE_LINHAS_EXEMPLO],
            )
        )

    resumo = f"{total_comparacoes} comparações UF x coluna; divergências: {len(divergencias)}"
    resultado = ResultadoChecagem(
        codigo="g3",
        titulo="Extra: 1T da base vs soma por UF dos CSVs brutos",
        status=classificar_status(len(divergencias) == 0),
        resumo=resumo,
        detalhes=detalhes,
    )
    return resultado


def checar_longo_vs_largo(base: pd.DataFrame, longo: pd.DataFrame) -> ResultadoChecagem:
    """Checagem extra (g4): tabela longa consistente com a tabela larga.

    Verifica contagem de linhas (municípios x candidatos), ausência de
    nulos e igualdade célula a célula após pivotar o longo.

    Args:
        base: Base por município (larga).
        longo: Tabela por município x candidato.

    Returns:
        Resultado com os problemas encontrados.
    """
    problemas: list[str] = []
    esperado_1t = len(base) * len(NUMEROS_CANDIDATOS_1T)
    esperado_2t = len(base) * len(NUMEROS_CANDIDATOS_2T)

    linhas_1t = int((longo["nr_turno"] == 1).sum())
    linhas_2t = int((longo["nr_turno"] == 2).sum())
    if linhas_1t != esperado_1t:
        problemas.append(f"- linhas do 1T no longo: {linhas_1t} (esperado {esperado_1t})")
    if linhas_2t != esperado_2t:
        problemas.append(f"- linhas do 2T no longo: {linhas_2t} (esperado {esperado_2t})")

    colunas_esperadas = [
        "nr_turno",
        "sg_uf",
        "cd_municipio_tse",
        "nr_candidato",
        "nm_urna_candidato",
        "sg_partido",
        "votos",
    ]
    if list(longo.columns) != colunas_esperadas:
        problemas.append(f"- colunas do longo: {list(longo.columns)}")

    if longo.isna().any().any():
        problemas.append("- longo com nulos")

    chave_longo = ["nr_turno", "sg_uf", "cd_municipio_tse", "nr_candidato"]
    duplicadas = int(longo.duplicated(subset=chave_longo).sum())
    if duplicadas > 0:
        problemas.append(f"- {duplicadas} chaves duplicadas no longo")

    celulas_diferentes = 0
    for numero_turno, rotulo, numeros in ((1, "1t", NUMEROS_CANDIDATOS_1T), (2, "2t", NUMEROS_CANDIDATOS_2T)):
        longo_do_turno = longo[longo["nr_turno"] == numero_turno]
        pivotado = longo_do_turno.pivot(
            index=COLUNAS_CHAVE,
            columns="nr_candidato",
            values="votos",
        )
        base_indexada = base.set_index(COLUNAS_CHAVE)

        if set(pivotado.index) != set(base_indexada.index):
            problemas.append(f"- chaves do longo ({rotulo}) diferentes das da base")
            continue

        for numero in numeros:
            valores_longo = pivotado.loc[base_indexada.index, numero]
            valores_base = base_indexada[f"votos_{rotulo}_{numero}"]
            celulas_diferentes += int((valores_longo != valores_base).sum())

    if celulas_diferentes > 0:
        problemas.append(f"- {celulas_diferentes} células de votos diferentes entre longo e largo")

    resumo = (
        f"longo: {len(longo)} linhas (1T={linhas_1t}, 2T={linhas_2t}); células diferentes: "
        f"{celulas_diferentes}; problemas: {len(problemas)}"
    )
    resultado = ResultadoChecagem(
        codigo="g4",
        titulo="Extra: longo vs largo (linhas, nulos, chaves, células)",
        status=classificar_status(len(problemas) == 0),
        resumo=resumo,
        detalhes=problemas,
    )
    return resultado


def checar_csv_vs_parquet(base: pd.DataFrame) -> ResultadoChecagem:
    """Checagem extra (g5): o CSV gravado reproduz exatamente o parquet.

    Lê o CSV como texto, converte as colunas numéricas e compara com o
    parquet; códigos são comparados como texto (zeros à esquerda).

    Args:
        base: Base por município lida do parquet.

    Returns:
        Resultado com os problemas encontrados.
    """
    problemas: list[str] = []
    base_csv = pd.read_csv(
        CAMINHO_BASE_CSV,
        sep=SEPARADOR_CSV,
        encoding=ENCODING_CSV_SAIDA,
        dtype=str,
        keep_default_na=False,
    )

    colunas_numericas_csv = [coluna for coluna in base.columns if coluna not in COLUNAS_IDENTIFICACAO]

    if list(base_csv.columns) != list(base.columns):
        problemas.append("- colunas do CSV diferem das do parquet")
    if len(base_csv) != len(base):
        problemas.append(f"- linhas do CSV {len(base_csv)} != parquet {len(base)}")

    if not problemas:
        colunas_texto = ["sg_uf", "nm_regiao", "cd_municipio_tse", "nm_municipio"]
        for coluna in colunas_texto:
            diferentes = int((base_csv[coluna] != base[coluna]).sum())
            if diferentes > 0:
                problemas.append(f"- {diferentes} diferenças na coluna {coluna}")

        ibge_parquet = base["cd_municipio_ibge"].fillna("")
        diferentes_ibge = int((base_csv["cd_municipio_ibge"] != ibge_parquet).sum())
        if diferentes_ibge > 0:
            problemas.append(f"- {diferentes_ibge} diferenças em cd_municipio_ibge")

        exterior_csv = base_csv["fl_exterior"] == "True"
        diferentes_exterior = int((exterior_csv != base["fl_exterior"]).sum())
        if diferentes_exterior > 0:
            problemas.append(f"- {diferentes_exterior} diferenças em fl_exterior")

        for coluna in colunas_numericas_csv:
            valores_csv = base_csv[coluna].astype("int64")
            diferentes = int((valores_csv != base[coluna]).sum())
            if diferentes > 0:
                problemas.append(f"- {diferentes} diferenças na coluna {coluna}")

    resumo = (
        f"CSV com {len(base_csv)} linhas e {len(base_csv.columns)} colunas; "
        f"{len(colunas_numericas_csv)} colunas numéricas comparadas; problemas: {len(problemas)}"
    )
    resultado = ResultadoChecagem(
        codigo="g5",
        titulo="Extra: CSV gravado == parquet",
        status=classificar_status(len(problemas) == 0),
        resumo=resumo,
        detalhes=problemas,
    )
    return resultado


def informar_aptos_diferentes_entre_turnos(base: pd.DataFrame) -> ResultadoChecagem:
    """Informativo (g6): municípios cujo número de aptos mudou entre os turnos.

    O total nacional de aptos é igual nos dois turnos (checagem a), mas o
    número por município pode diferir. Fato medido, sem juízo de valor.

    Args:
        base: Base por município.

    Returns:
        Resultado INFO com contagens e maiores diferenças.
    """
    diferenca = base["aptos_2t"] - base["aptos_1t"]
    mascara_diferente = diferenca != 0
    quantidade = int(mascara_diferente.sum())
    soma_positiva = int(diferenca[diferenca > 0].sum())
    soma_negativa = int(diferenca[diferenca < 0].sum())
    soma_liquida = int(diferenca.sum())

    tabela_maiores = base.loc[mascara_diferente, ["sg_uf", "cd_municipio_tse", "nm_municipio"]].copy()
    tabela_maiores["aptos_1t"] = base.loc[mascara_diferente, "aptos_1t"]
    tabela_maiores["aptos_2t"] = base.loc[mascara_diferente, "aptos_2t"]
    tabela_maiores["dif"] = diferenca[mascara_diferente]
    tabela_maiores["dif_abs"] = tabela_maiores["dif"].abs()
    tabela_maiores = tabela_maiores.sort_values("dif_abs", ascending=False).head(10)

    linhas: list[list[str]] = []
    for _, linha in tabela_maiores.iterrows():
        linhas.append(
            [
                f"{linha['sg_uf']}/{linha['cd_municipio_tse']} {linha['nm_municipio']}",
                formatar_inteiro(int(linha["aptos_1t"])),
                formatar_inteiro(int(linha["aptos_2t"])),
                formatar_inteiro(int(linha["dif"])),
            ]
        )

    detalhes = montar_tabela_markdown(["Município (10 maiores diferenças)", "Aptos 1T", "Aptos 2T", "Dif."], linhas)
    detalhes.append("")
    detalhes.append(
        "Hipótese a confirmar (não verificada): ajustes de eleitorado entre turnos, como voto em trânsito "
        "ou transferências de seção; o dado só mostra a diferença."
    )
    resumo = (
        f"{quantidade} de {len(base)} municípios com aptos diferentes entre os turnos; "
        f"soma das altas {formatar_inteiro(soma_positiva)}, soma das quedas {formatar_inteiro(soma_negativa)}, "
        f"saldo líquido {formatar_inteiro(soma_liquida)}"
    )
    resultado = ResultadoChecagem(
        codigo="g6",
        titulo="Informativo: aptos por município mudam entre turnos (total nacional igual)",
        status=STATUS_INFORMATIVO,
        resumo=resumo,
        detalhes=detalhes,
    )
    return resultado


def informar_nomes_divergentes(base: pd.DataFrame) -> ResultadoChecagem:
    """Informativo (g7): nomes de município diferentes entre config (2T) e CSV (1T).

    A base usa o nome do config do TSE (2º turno). A chave do join é o código.

    Args:
        base: Base por município.

    Returns:
        Resultado INFO com a contagem e a natureza das diferenças.
    """
    colunas = ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO"]
    detalhe = ler_csv_do_zip(ZIP_DETALHE_1T, MEMBRO_DETALHE_1T, colunas)
    detalhe = detalhe.drop_duplicates()
    detalhe["cd_municipio_tse"] = detalhe["CD_MUNICIPIO"].str.zfill(5)
    detalhe["sg_uf"] = detalhe["SG_UF"]

    comparacao = base[COLUNAS_CHAVE + ["nm_municipio"]].merge(
        detalhe[COLUNAS_CHAVE + ["NM_MUNICIPIO"]],
        on=COLUNAS_CHAVE,
        how="inner",
    )
    mascara_diferente = comparacao["nm_municipio"] != comparacao["NM_MUNICIPIO"]
    divergentes = comparacao.loc[mascara_diferente].copy()

    nome_config_sem_apostrofo = divergentes["nm_municipio"].str.replace("'", " ", regex=False)
    somente_apostrofo = nome_config_sem_apostrofo == divergentes["NM_MUNICIPIO"]
    quantidade_somente_apostrofo = int(somente_apostrofo.sum())
    outras = divergentes.loc[~somente_apostrofo]

    detalhes: list[str] = []
    for _, linha in outras.head(LIMITE_LINHAS_EXEMPLO).iterrows():
        detalhes.append(f"- {linha['sg_uf']}/{linha['cd_municipio_tse']}: config={linha['nm_municipio']!r} 1T={linha['NM_MUNICIPIO']!r}")

    resumo = (
        f"{len(divergentes)} nomes diferentes de {len(comparacao)}; "
        f"{quantidade_somente_apostrofo} só por apóstrofo (config \"D'ÁGUA\" vs CSV 1T \"D ÁGUA\"); "
        f"outras diferenças: {len(outras)}"
    )
    resultado = ResultadoChecagem(
        codigo="g7",
        titulo="Informativo: nome do município no config (2T) vs CSV (1T)",
        status=STATUS_INFORMATIVO,
        resumo=resumo,
        detalhes=detalhes,
    )
    return resultado


# --------------------------------------------------------------------------
# Relatório
# --------------------------------------------------------------------------


def montar_relatorio_markdown(resultados: list[ResultadoChecagem]) -> str:
    """Monta o texto do relatório de conciliação.

    Args:
        resultados: Resultados de todas as checagens.

    Returns:
        Texto Markdown completo.
    """
    total_fail = 0
    for resultado in resultados:
        if resultado.status == STATUS_REPROVADO:
            total_fail += 1

    status_geral = "FALHA" if total_fail > 0 else "OK"
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    linhas: list[str] = []
    linhas.append("# Conciliação: base de Presidente 2026 (1º e 2º turno) por município")
    linhas.append("")
    linhas.append(f"Gerado em {agora} por `03_conciliar.py`. **Status geral: {status_geral}** ({total_fail} checagens reprovadas).")
    linhas.append("")
    linhas.append("## Resumo")
    linhas.append("")

    linhas_resumo: list[list[str]] = []
    for resultado in resultados:
        linhas_resumo.append([resultado.codigo, resultado.titulo, resultado.status, resultado.resumo])
    linhas.extend(montar_tabela_markdown(["Checagem", "Descrição", "Status", "Números"], linhas_resumo))
    linhas.append("")

    for resultado in resultados:
        linhas.append(f"## ({resultado.codigo}) {resultado.titulo}: {resultado.status}")
        linhas.append("")
        linhas.append(resultado.resumo)
        linhas.append("")
        if resultado.detalhes:
            linhas.extend(resultado.detalhes)
            linhas.append("")

    return "\n".join(linhas)


def gravar_relatorio(texto: str) -> None:
    """Grava o relatório em CAMINHO_RELATORIO (sobrescreve a versão anterior).

    Args:
        texto: Conteúdo em Markdown.
    """
    CAMINHO_RELATORIO.write_text(texto, encoding="utf-8")
    LOGGER.info("Relatório gravado em %s", CAMINHO_RELATORIO)


def contar_municipios_do_config_por_uf() -> dict[str, int]:
    """Conta os municípios de cada UF no arquivo de config do TSE.

    Returns:
        Mapa sigla (maiúscula) -> quantidade.

    Raises:
        ErroJsonConciliacaoError: Se o config estiver ausente ou ilegível.
    """
    conteudo_config = ler_json(CAMINHO_CONFIG_2T)
    contagem: dict[str, int] = {}

    for abrangencia in conteudo_config.get("abr", []):
        sigla = abrangencia["cd"].upper()
        contagem[sigla] = len(abrangencia.get("mu", []))
    return contagem


def executar_conciliacao() -> list[ResultadoChecagem]:
    """Executa todas as checagens e devolve os resultados na ordem do relatório.

    Returns:
        Lista de resultados (a, b, c, d, e, f, g1..g7).
    """
    base = pd.read_parquet(CAMINHO_BASE_PARQUET)
    longo = pd.read_parquet(CAMINHO_LONGO_PARQUET)
    LOGGER.info("Base lida: %d linhas x %d colunas; longo: %d linhas.", len(base), len(base.columns), len(longo))

    siglas_uf = sorted(base["sg_uf"].unique())
    valores_por_uf, erros_ufs = carregar_json_das_ufs(siglas_uf)

    valores_nacional: ValoresJson | None = None
    erro_nacional = ""
    try:
        conteudo_nacional = ler_json(montar_caminho_json("br", None))
        valores_nacional = extrair_valores_json(conteudo_nacional)
    except ErroJsonConciliacaoError as erro:
        erro_nacional = str(erro)

    valores_por_municipio, erros_municipios = ler_todos_os_jsons_de_municipio(base)
    LOGGER.info("JSONs de município lidos: %d; erros: %d", len(valores_por_municipio), len(erros_municipios))

    tv_diferente = contar_total_votos_diferente_do_comparecimento(valores_por_municipio)
    contagem_config = contar_municipios_do_config_por_uf()

    resultados: list[ResultadoChecagem] = []
    resultados.append(checar_ancoras(base))
    resultados.append(checar_soma_municipios_vs_uf(base, valores_por_uf, erros_ufs))
    resultados.append(checar_soma_ufs_vs_nacional(base, valores_por_uf, valores_nacional, erro_nacional))
    resultados.append(checar_identidades(base, tv_diferente))
    resultados.append(
        checar_totalizacao_final(
            valores_por_municipio,
            erros_municipios,
            valores_por_uf,
            valores_nacional,
            len(base),
        )
    )
    resultados.append(checar_contagem_por_uf(base, contagem_config))
    resultados.append(checar_schema_e_chaves(base))
    resultados.append(checar_codigos_ibge(base))
    resultados.append(checar_primeiro_turno_vs_csv_bruto(base))
    resultados.append(checar_longo_vs_largo(base, longo))
    resultados.append(checar_csv_vs_parquet(base))
    resultados.append(informar_aptos_diferentes_entre_turnos(base))
    resultados.append(informar_nomes_divergentes(base))
    return resultados


def main() -> int:
    """Executa a conciliação, grava o relatório e devolve o código de saída.

    Returns:
        0 se nenhuma checagem foi reprovada; 1 se houver FAIL ou se alguma
        entrada necessária estiver ausente.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        resultados = executar_conciliacao()
    except (FileNotFoundError, ErroJsonConciliacaoError, KeyError) as erro:
        LOGGER.error("Conciliação não pôde ser executada: %s: %s", type(erro).__name__, erro)
        return 1

    texto_relatorio = montar_relatorio_markdown(resultados)
    gravar_relatorio(texto_relatorio)

    total_fail = 0
    for resultado in resultados:
        LOGGER.info("(%s) %s: %s | %s", resultado.codigo, resultado.titulo, resultado.status, resultado.resumo)
        if resultado.status == STATUS_REPROVADO:
            total_fail += 1

    if total_fail > 0:
        LOGGER.error("Conciliação com %d checagens reprovadas.", total_fail)
        return 1

    LOGGER.info("Conciliação aprovada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
