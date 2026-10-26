"""Monta a base de Presidente 2026 (1º e 2º turno) agregada por município.

Pergunta de negócio:
    Como cada município votou no 1º e no 2º turno para Presidente, de forma
    a comparar os turnos por UF, região e partido?

Entradas (somente leitura):
    <PROJ>/votacao_candidato_munzona_2026.zip   (1º turno, votos por candidato)
    <PROJ>/detalhe_votacao_munzona_2026.zip     (1º turno, aptos/comparecimento/...)
    <PROJ>/dados/json_tse/6258/...              (2º turno, JSONs do script 01)

Saídas (em <PROJ>/dados/processados/):
    presidente_municipio_turnos.parquet  e  .csv   (uma linha por município)
    presidente_municipio_candidato_long.parquet    (formato longo)

Regras de negócio da montagem:
    * Chave do município: (sg_uf, cd_municipio_tse), com código TSE sempre
      em texto de 5 dígitos (o CSV do TSE traz "01007" num arquivo e 1007
      em outro).
    * 1º turno: soma das zonas eleitorais de cada município, somando as linhas
      com voto em trânsito "S" e "N".
    * 2º turno: valores do JSON oficial de cada município. "nulos" é o total
      de nulos (v.tvn), que já inclui os nulos técnicos, igual ao
      QT_TOTAL_VOTOS_NULOS do 1º turno.
    * Município sem voto para um candidato recebe 0 de forma explícita
      (função completar_grade_de_votos), nunca por efeito colateral de merge.
    * Anti-join nos dois sentidos entre as chaves do 1º e do 2º turno; se
      houver órfão, o script lista e aborta sem gravar a base.

Execução (os dados baixados são não confiáveis; usar o modo isolado):
    python3 -I 02_montar_base.py
"""

import dataclasses
import json
import logging
import re
import zipfile
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger("montar_base")

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------

PASTA_SCRIPT = Path(__file__).resolve().parent
RAIZ_PROJETO = PASTA_SCRIPT.parent

ZIP_CANDIDATO_1T = RAIZ_PROJETO / "votacao_candidato_munzona_2026.zip"
MEMBRO_CANDIDATO_1T = "votacao_candidato_munzona_2026_BR.csv"
ZIP_DETALHE_1T = RAIZ_PROJETO / "detalhe_votacao_munzona_2026.zip"
MEMBRO_DETALHE_1T = "detalhe_votacao_munzona_2026_BR.csv"

CODIGO_ELEICAO_2T = "6258"
PASTA_JSON_2T = RAIZ_PROJETO / "dados" / "json_tse" / CODIGO_ELEICAO_2T
CAMINHO_CONFIG_2T = PASTA_JSON_2T / "config" / "mun-e006258-cm.json"
SUFIXO_ARQUIVO_JSON_2T = "c0001-e006258-u.json"

PASTA_PROCESSADOS = RAIZ_PROJETO / "dados" / "processados"
CAMINHO_BASE_PARQUET = PASTA_PROCESSADOS / "presidente_municipio_turnos.parquet"
CAMINHO_BASE_CSV = PASTA_PROCESSADOS / "presidente_municipio_turnos.csv"
CAMINHO_LONGO_PARQUET = PASTA_PROCESSADOS / "presidente_municipio_candidato_long.parquet"
CAMINHO_ORFAOS = PASTA_SCRIPT / "orfaos_chaves_1t_2t.csv"
SUFIXO_ARQUIVO_PARCIAL = ".parcial"

# --------------------------------------------------------------------------
# Constantes de formato e de domínio
# --------------------------------------------------------------------------

ENCODING_CSV_TSE = "latin-1"
SEPARADOR_CSV_TSE = ";"
ENCODING_CSV_SAIDA = "utf-8"
SEPARADOR_CSV_SAIDA = ";"

TAMANHO_CODIGO_MUNICIPIO_TSE = 5
TAMANHO_CODIGO_MUNICIPIO_IBGE = 7
SIGLA_EXTERIOR = "ZZ"
REGIAO_EXTERIOR = "Exterior"
CODIGO_CARGO_PRESIDENTE_JSON = "1"
DESCRICAO_CARGO_PRESIDENTE_CSV = "Presidente"
TOTALIZACAO_FINAL = "s"
PERCENTUAL_SECOES_APURADAS_FINAL = "100,00"
VOTO_EM_TRANSITO_PERMITIDOS = frozenset({"S", "N"})

# Candidatos do 1º turno (ordem crescente do número na urna).
NUMEROS_CANDIDATOS_1T = (13, 14, 16, 21, 22, 27, 29, 30, 35, 55, 70, 80)
# Candidatos do 2º turno.
NUMEROS_CANDIDATOS_2T = (13, 22)

# Quando um candidato não aparece em um município (ou aparece sem votos),
# a regra de negócio é: zero voto. O valor é nomeado para ficar explícito.
VOTOS_CANDIDATO_AUSENTE = 0

ROTULO_TURNO_1T = "1t"
ROTULO_TURNO_2T = "2t"
NUMERO_TURNO_1T = 1
NUMERO_TURNO_2T = 2

# Métricas de comparecimento, na ordem em que aparecem nas colunas finais.
METRICAS_DO_TURNO = (
    "aptos",
    "comparecimento",
    "abstencao",
    "nao_instaladas",
    "validos",
    "brancos",
    "nulos",
)

# Colunas do CSV de detalhe do 1º turno (por zona) -> nome da métrica.
METRICA_POR_COLUNA_DETALHE_1T = {
    "QT_APTOS": "aptos",
    "QT_COMPARECIMENTO": "comparecimento",
    "QT_ABSTENCOES": "abstencao",
    "QT_ELEITORES_SECOES_NAO_INSTALADAS": "nao_instaladas",
    "QT_TOTAL_VOTOS_VALIDOS": "validos",
    "QT_VOTOS_BRANCOS": "brancos",
    "QT_TOTAL_VOTOS_NULOS": "nulos",
}

COLUNAS_CHAVE_ZONA_DETALHE_1T = ["SG_UF", "CD_MUNICIPIO", "NR_ZONA", "ST_VOTO_EM_TRANSITO"]
COLUNAS_LIDAS_DETALHE_1T = (
    COLUNAS_CHAVE_ZONA_DETALHE_1T
    + ["NR_TURNO", "DS_CARGO"]
    + list(METRICA_POR_COLUNA_DETALHE_1T.keys())
)

COLUNAS_CHAVE_ZONA_CANDIDATO_1T = [
    "SG_UF",
    "CD_MUNICIPIO",
    "NR_ZONA",
    "NR_CANDIDATO",
    "ST_VOTO_EM_TRANSITO",
]
COLUNA_VOTOS_CANDIDATO_1T = "QT_VOTOS_NOMINAIS_VALIDOS"
COLUNAS_LIDAS_CANDIDATO_1T = COLUNAS_CHAVE_ZONA_CANDIDATO_1T + [
    "NR_TURNO",
    "DS_CARGO",
    "NM_URNA_CANDIDATO",
    "SG_PARTIDO",
    COLUNA_VOTOS_CANDIDATO_1T,
]

COLUNAS_CHAVE_MUNICIPIO = ["sg_uf", "cd_municipio_tse"]
COLUNAS_IDENTIFICACAO = [
    "sg_uf",
    "nm_regiao",
    "cd_municipio_tse",
    "cd_municipio_ibge",
    "nm_municipio",
    "fl_exterior",
]
COLUNAS_LONGO = [
    "nr_turno",
    "sg_uf",
    "cd_municipio_tse",
    "nr_candidato",
    "nm_urna_candidato",
    "sg_partido",
    "votos",
]

REGIAO_POR_UF = {
    "AC": "Norte",
    "AP": "Norte",
    "AM": "Norte",
    "PA": "Norte",
    "RO": "Norte",
    "RR": "Norte",
    "TO": "Norte",
    "AL": "Nordeste",
    "BA": "Nordeste",
    "CE": "Nordeste",
    "MA": "Nordeste",
    "PB": "Nordeste",
    "PE": "Nordeste",
    "PI": "Nordeste",
    "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste",
    "GO": "Centro-Oeste",
    "MT": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "ES": "Sudeste",
    "MG": "Sudeste",
    "RJ": "Sudeste",
    "SP": "Sudeste",
    "PR": "Sul",
    "RS": "Sul",
    "SC": "Sul",
    SIGLA_EXTERIOR: REGIAO_EXTERIOR,
}

PADRAO_SOMENTE_DIGITOS = re.compile(r"^[0-9]+$")
PADRAO_SIGLA_UF_MINUSCULA = re.compile(r"^[a-z]{2}$")


# --------------------------------------------------------------------------
# Tipos
# --------------------------------------------------------------------------


class ChavesOrfasError(RuntimeError):
    """Há municípios presentes em apenas um dos turnos."""


class ArquivosAusentesError(FileNotFoundError):
    """Há JSONs de município esperados que não existem em disco."""


class ErroLeituraJsonError(ValueError):
    """Um JSON de município não tem a estrutura ou os valores esperados."""


@dataclasses.dataclass(frozen=True)
class MunicipioConfig:
    """Município do arquivo de configuração do TSE (espinha da base)."""

    sg_uf: str
    cd_municipio_tse: str
    cd_municipio_ibge: str | None
    nm_municipio: str


@dataclasses.dataclass(frozen=True)
class VotosCandidatoJson:
    """Votos de um candidato em um município, lidos do JSON do 2º turno."""

    numero_candidato: int
    nome_urna: str
    sigla_partido: str
    votos: int


@dataclasses.dataclass(frozen=True)
class ApuracaoMunicipio:
    """Resultado de Presidente em um município, lido do JSON do 2º turno.

    Attributes:
        totalizacao_final: Valor bruto de "tf" ("s" = totalização final).
        percentual_secoes_apuradas: Valor bruto de "s.pst" (ex.: "100,00").
        aptos: Eleitores aptos (e.te).
        comparecimento: Eleitores que compareceram (e.c).
        abstencao: Abstenções (e.a).
        nao_instaladas: Eleitores de seções não instaladas (e.esni).
        validos: Votos válidos (v.vv).
        brancos: Votos em branco (v.vb).
        nulos: Total de votos nulos, incluindo técnicos (v.tvn).
        candidatos: Votos de cada candidato listado no JSON.
    """

    totalizacao_final: str
    percentual_secoes_apuradas: str
    aptos: int
    comparecimento: int
    abstencao: int
    nao_instaladas: int
    validos: int
    brancos: int
    nulos: int
    candidatos: tuple[VotosCandidatoJson, ...]


# --------------------------------------------------------------------------
# Funções puras: códigos, regiões e conversões
# --------------------------------------------------------------------------


def normalizar_codigo_municipio(valor: str) -> str:
    """Padroniza o código TSE do município para texto de 5 dígitos.

    O TSE publica o mesmo código como "01007" (quando o campo vem entre
    aspas) e como 1007 (quando vem sem aspas). Sem esta padronização o
    join entre arquivos perde os municípios com código iniciado em zero.

    Args:
        valor: Código lido como texto (nunca como número).

    Returns:
        Texto com exatamente 5 dígitos, completado com zeros à esquerda.

    Raises:
        ValueError: Se o valor estiver vazio, tiver caractere não numérico
            ou tiver mais de 5 dígitos.
    """
    texto_limpo = valor.strip()

    if not PADRAO_SOMENTE_DIGITOS.match(texto_limpo):
        raise ValueError(f"Código de município não numérico: {valor!r}")

    if len(texto_limpo) > TAMANHO_CODIGO_MUNICIPIO_TSE:
        raise ValueError(f"Código de município com mais de 5 dígitos: {valor!r}")

    return texto_limpo.zfill(TAMANHO_CODIGO_MUNICIPIO_TSE)


def obter_regiao_da_uf(sigla_uf: str) -> str:
    """Devolve a região geográfica de uma UF (ou "Exterior" para "ZZ").

    Args:
        sigla_uf: Sigla em maiúsculas (ex.: "SP", "ZZ").

    Returns:
        Nome da região: Norte, Nordeste, Centro-Oeste, Sudeste, Sul ou
        Exterior.

    Raises:
        ValueError: Se a sigla não for uma das 28 conhecidas.
    """
    if sigla_uf not in REGIAO_POR_UF:
        raise ValueError(f"UF desconhecida: {sigla_uf!r}")
    return REGIAO_POR_UF[sigla_uf]


def converter_para_inteiro(texto: str, nome_campo: str) -> int:
    """Converte número em texto (como vem no JSON do TSE) para inteiro.

    Aceita somente dígitos; vazio, sinal, decimal ou separador de milhar
    são rejeitados para que um dado estranho nunca vire número em silêncio.

    Args:
        texto: Valor do JSON (ex.: "7284071").
        nome_campo: Nome do campo, usado na mensagem de erro.

    Returns:
        O valor como int.

    Raises:
        ValueError: Se o texto não contiver apenas dígitos.
    """
    if not isinstance(texto, str):
        raise ValueError(f"Campo {nome_campo!r} não é texto: {texto!r}")

    texto_limpo = texto.strip()
    if not PADRAO_SOMENTE_DIGITOS.match(texto_limpo):
        raise ValueError(f"Campo {nome_campo!r} não é inteiro: {texto!r}")

    return int(texto_limpo)


def nomes_colunas_metricas(rotulo_turno: str) -> list[str]:
    """Lista os nomes das colunas de métricas de um turno (ex.: aptos_1t).

    Args:
        rotulo_turno: "1t" ou "2t".

    Returns:
        Nomes na ordem de METRICAS_DO_TURNO.
    """
    nomes: list[str] = []
    for metrica in METRICAS_DO_TURNO:
        nomes.append(f"{metrica}_{rotulo_turno}")
    return nomes


def nomes_colunas_votos(rotulo_turno: str, numeros_candidatos: tuple[int, ...]) -> list[str]:
    """Lista os nomes das colunas de votos por candidato (ex.: votos_1t_13).

    Args:
        rotulo_turno: "1t" ou "2t".
        numeros_candidatos: Números dos candidatos, na ordem desejada.

    Returns:
        Um nome por candidato.
    """
    nomes: list[str] = []
    for numero in numeros_candidatos:
        nomes.append(f"votos_{rotulo_turno}_{numero}")
    return nomes


# --------------------------------------------------------------------------
# Funções puras: leitura do JSON do 2º turno
# --------------------------------------------------------------------------


def extrair_candidatos_presidente(conteudo: dict) -> list[VotosCandidatoJson]:
    """Extrai os candidatos de Presidente do JSON de um município.

    Percorre carg[0] -> agr[] -> par[] -> cand[]. O número e o nome de urna
    estão no candidato; a sigla do partido está no nível "par".

    Args:
        conteudo: JSON do município já desserializado.

    Returns:
        Lista de candidatos com seus votos (campo "vap").

    Raises:
        ValueError: Se o JSON não tiver exatamente o cargo Presidente ou se
            algum número não for inteiro.
        KeyError: Se faltar um campo obrigatório da estrutura.
    """
    cargos = conteudo["carg"]
    if len(cargos) != 1:
        raise ValueError(f"Esperado 1 cargo, encontrado {len(cargos)}")

    cargo = cargos[0]
    if cargo["cd"] != CODIGO_CARGO_PRESIDENTE_JSON:
        raise ValueError(f"Cargo inesperado: {cargo['cd']!r}")

    candidatos: list[VotosCandidatoJson] = []

    for agrupamento in cargo["agr"]:
        for partido in agrupamento["par"]:
            sigla_partido = partido["sg"]
            lista_candidatos_do_partido = partido.get("cand", [])

            for candidato in lista_candidatos_do_partido:
                numero = converter_para_inteiro(candidato["n"], "cand.n")
                votos = converter_para_inteiro(candidato["vap"], "cand.vap")
                votos_candidato = VotosCandidatoJson(
                    numero_candidato=numero,
                    nome_urna=candidato["nmu"],
                    sigla_partido=sigla_partido,
                    votos=votos,
                )
                candidatos.append(votos_candidato)

    return candidatos


def extrair_apuracao_municipio(conteudo: dict) -> ApuracaoMunicipio:
    """Converte o JSON de um município em um registro tipado.

    Mapeamento de campos (todos vêm como texto no JSON):
        aptos e.te | comparecimento e.c | abstencao e.a |
        nao_instaladas e.esni | validos v.vv | brancos v.vb |
        nulos v.tvn (total de nulos, já inclui os técnicos v.vnt).

    Args:
        conteudo: JSON do município já desserializado.

    Returns:
        Registro com métricas, candidatos e marcas de totalização.

    Raises:
        KeyError: Se faltar bloco ou campo obrigatório.
        ValueError: Se algum número não for inteiro ou se houver candidato
            repetido no mesmo município.
    """
    bloco_secoes = conteudo["s"]
    bloco_eleitorado = conteudo["e"]
    bloco_votos = conteudo["v"]

    candidatos = extrair_candidatos_presidente(conteudo)

    numeros_vistos: set[int] = set()
    for candidato in candidatos:
        if candidato.numero_candidato in numeros_vistos:
            raise ValueError(f"Candidato repetido: {candidato.numero_candidato}")
        numeros_vistos.add(candidato.numero_candidato)

    apuracao = ApuracaoMunicipio(
        totalizacao_final=conteudo["tf"],
        percentual_secoes_apuradas=bloco_secoes["pst"],
        aptos=converter_para_inteiro(bloco_eleitorado["te"], "e.te"),
        comparecimento=converter_para_inteiro(bloco_eleitorado["c"], "e.c"),
        abstencao=converter_para_inteiro(bloco_eleitorado["a"], "e.a"),
        nao_instaladas=converter_para_inteiro(bloco_eleitorado["esni"], "e.esni"),
        validos=converter_para_inteiro(bloco_votos["vv"], "v.vv"),
        brancos=converter_para_inteiro(bloco_votos["vb"], "v.vb"),
        nulos=converter_para_inteiro(bloco_votos["tvn"], "v.tvn"),
        candidatos=tuple(candidatos),
    )
    return apuracao


def validar_identificacao_json(conteudo: dict, sg_uf: str, cd_municipio_tse: str) -> None:
    """Confere que o JSON lido é do município e do turno esperados.

    Evita que um arquivo trocado de lugar contamine a base.

    Args:
        conteudo: JSON do município já desserializado.
        sg_uf: Sigla da UF em maiúsculas.
        cd_municipio_tse: Código TSE de 5 dígitos.

    Raises:
        ValueError: Se eleição, turno, tipo ou código do recorte divergirem.
    """
    if conteudo.get("ele") != CODIGO_ELEICAO_2T:
        raise ValueError(f"Eleição inesperada: {conteudo.get('ele')!r}")

    if conteudo.get("t") != "2":
        raise ValueError(f"Turno inesperado: {conteudo.get('t')!r}")

    if conteudo.get("tpabr") != "mu":
        raise ValueError(f"Tipo de abrangência inesperado: {conteudo.get('tpabr')!r}")

    codigo_no_json = normalizar_codigo_municipio(conteudo.get("cdabr", ""))
    if codigo_no_json != cd_municipio_tse:
        raise ValueError(
            f"cdabr {codigo_no_json!r} diferente do município esperado "
            f"{sg_uf}/{cd_municipio_tse}"
        )


def converter_config_em_municipios(conteudo_config: dict) -> list[MunicipioConfig]:
    """Converte o JSON de configuração do TSE na lista de municípios.

    O código IBGE (campo "cdi") é vazio no exterior; nesse caso vira None.

    Args:
        conteudo_config: Config já desserializado.

    Returns:
        Um registro por município, na ordem do arquivo.

    Raises:
        ValueError: Se sigla, código TSE ou código IBGE tiverem formato
            inválido, ou se houver município repetido.
    """
    municipios: list[MunicipioConfig] = []
    chaves_vistas: set[tuple[str, str]] = set()

    for abrangencia in conteudo_config["abr"]:
        sigla_minuscula = abrangencia["cd"]
        if not PADRAO_SIGLA_UF_MINUSCULA.match(sigla_minuscula):
            raise ValueError(f"Sigla de UF inválida no config: {sigla_minuscula!r}")
        sg_uf = sigla_minuscula.upper()

        for municipio in abrangencia["mu"]:
            cd_tse = normalizar_codigo_municipio(municipio["cd"])

            texto_ibge = municipio.get("cdi", "")
            if texto_ibge == "":
                cd_ibge = None
            else:
                so_tem_digitos = PADRAO_SOMENTE_DIGITOS.match(texto_ibge) is not None
                tem_sete_digitos = len(texto_ibge) == TAMANHO_CODIGO_MUNICIPIO_IBGE
                if not (so_tem_digitos and tem_sete_digitos):
                    raise ValueError(f"Código IBGE inválido: {texto_ibge!r} ({sg_uf}/{cd_tse})")
                cd_ibge = texto_ibge

            chave = (sg_uf, cd_tse)
            if chave in chaves_vistas:
                raise ValueError(f"Município repetido no config: {chave}")
            chaves_vistas.add(chave)

            municipios.append(
                MunicipioConfig(
                    sg_uf=sg_uf,
                    cd_municipio_tse=cd_tse,
                    cd_municipio_ibge=cd_ibge,
                    nm_municipio=municipio["nm"],
                )
            )

    return municipios


# --------------------------------------------------------------------------
# Funções puras: transformações em DataFrame
# --------------------------------------------------------------------------


def validar_colunas_presentes(tabela: pd.DataFrame, colunas: list[str], nome_tabela: str) -> None:
    """Garante que a tabela tenha todas as colunas exigidas.

    Args:
        tabela: Tabela a validar.
        colunas: Colunas obrigatórias.
        nome_tabela: Nome usado na mensagem de erro.

    Raises:
        KeyError: Se alguma coluna estiver ausente.
    """
    ausentes = set(colunas).difference(tabela.columns)
    if ausentes:
        raise KeyError(f"Colunas ausentes em {nome_tabela}: {sorted(ausentes)}")


def converter_colunas_para_inteiro(tabela: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Converte colunas de texto em int64, rejeitando nulos e negativos.

    Args:
        tabela: Tabela com as colunas em texto.
        colunas: Colunas a converter.

    Returns:
        Cópia da tabela com as colunas em int64.

    Raises:
        ValueError: Se houver valor não inteiro, vazio ou negativo.
    """
    tabela_convertida = tabela.copy()

    for coluna in colunas:
        valores_numericos = pd.to_numeric(tabela_convertida[coluna], errors="raise")
        if not pd.api.types.is_integer_dtype(valores_numericos):
            raise ValueError(f"Coluna {coluna} com valor não inteiro")
        if valores_numericos.isna().any():
            raise ValueError(f"Coluna {coluna} com valor nulo")
        if (valores_numericos < 0).any():
            raise ValueError(f"Coluna {coluna} com valor negativo")
        tabela_convertida[coluna] = valores_numericos.astype("int64")

    return tabela_convertida


def validar_valores_permitidos(
    tabela: pd.DataFrame,
    coluna: str,
    valores_permitidos: frozenset[str],
    nome_tabela: str,
) -> None:
    """Garante que a coluna só contenha valores de um conjunto permitido.

    Args:
        tabela: Tabela a validar.
        coluna: Coluna a checar.
        valores_permitidos: Conjunto aceito.
        nome_tabela: Nome usado na mensagem de erro.

    Raises:
        ValueError: Se houver valor fora do conjunto.
    """
    valores_encontrados = set(tabela[coluna].unique())
    valores_invalidos = valores_encontrados.difference(valores_permitidos)
    if valores_invalidos:
        raise ValueError(f"{nome_tabela}.{coluna} com valores inesperados: {sorted(valores_invalidos)}")


def validar_chave_unica(tabela: pd.DataFrame, colunas_chave: list[str], nome_tabela: str) -> None:
    """Garante que não haja linhas duplicadas para a chave informada.

    Args:
        tabela: Tabela a validar.
        colunas_chave: Colunas que formam a chave.
        nome_tabela: Nome usado na mensagem de erro.

    Raises:
        ValueError: Se houver chave duplicada.
    """
    mascara_duplicadas = tabela.duplicated(subset=colunas_chave, keep=False)
    quantidade_duplicadas = int(mascara_duplicadas.sum())
    if quantidade_duplicadas > 0:
        exemplos = tabela.loc[mascara_duplicadas, colunas_chave].head(5).to_dict("records")
        raise ValueError(
            f"{nome_tabela} com {quantidade_duplicadas} linhas de chave duplicada "
            f"{colunas_chave}; exemplos: {exemplos}"
        )


def preparar_tabela_1t(
    tabela_bruta: pd.DataFrame,
    colunas_numericas: list[str],
    colunas_chave: list[str],
    nome_tabela: str,
) -> pd.DataFrame:
    """Valida e padroniza uma tabela bruta do 1º turno (por zona).

    Passos: confere colunas, turno 1, cargo Presidente e voto em trânsito
    permitido; garante chave única; normaliza o código do município e a
    sigla da UF; converte números para int64.

    Args:
        tabela_bruta: Tabela lida do CSV (tudo em texto).
        colunas_numericas: Colunas que devem virar int64.
        colunas_chave: Colunas que identificam uma linha (no CSV bruto).
        nome_tabela: Nome usado nas mensagens de erro.

    Returns:
        Tabela com colunas "sg_uf" e "cd_municipio_tse" padronizadas
        (acrescentadas às originais).

    Raises:
        KeyError: Se faltar coluna obrigatória.
        ValueError: Se houver turno, cargo ou voto em trânsito inesperado,
            chave duplicada ou número inválido.
    """
    colunas_exigidas = colunas_chave + colunas_numericas + ["NR_TURNO", "DS_CARGO"]
    validar_colunas_presentes(tabela_bruta, colunas_exigidas, nome_tabela)

    validar_valores_permitidos(tabela_bruta, "NR_TURNO", frozenset({"1"}), nome_tabela)
    validar_valores_permitidos(
        tabela_bruta,
        "DS_CARGO",
        frozenset({DESCRICAO_CARGO_PRESIDENTE_CSV}),
        nome_tabela,
    )
    validar_valores_permitidos(
        tabela_bruta,
        "ST_VOTO_EM_TRANSITO",
        VOTO_EM_TRANSITO_PERMITIDOS,
        nome_tabela,
    )
    validar_chave_unica(tabela_bruta, colunas_chave, nome_tabela)

    tabela_numerica = converter_colunas_para_inteiro(tabela_bruta, colunas_numericas)

    codigos_normalizados = tabela_numerica["CD_MUNICIPIO"].map(normalizar_codigo_municipio)
    tabela_numerica["cd_municipio_tse"] = codigos_normalizados
    tabela_numerica["sg_uf"] = tabela_numerica["SG_UF"].str.strip().str.upper()

    return tabela_numerica


def agregar_metricas_1t(detalhe_por_zona: pd.DataFrame) -> pd.DataFrame:
    """Soma aptos, comparecimento etc. das zonas de cada município (1º turno).

    As linhas com voto em trânsito "S" e "N" são somadas juntas.

    Args:
        detalhe_por_zona: Saída de preparar_tabela_1t para o CSV de detalhe.

    Returns:
        Uma linha por município, com colunas de chave e "{metrica}_1t".
    """
    colunas_origem = list(METRICA_POR_COLUNA_DETALHE_1T.keys())
    colunas_para_somar = COLUNAS_CHAVE_MUNICIPIO + colunas_origem

    soma_por_municipio = detalhe_por_zona[colunas_para_somar].groupby(
        COLUNAS_CHAVE_MUNICIPIO,
        as_index=False,
    ).sum()

    renomear: dict[str, str] = {}
    for coluna_origem, metrica in METRICA_POR_COLUNA_DETALHE_1T.items():
        renomear[coluna_origem] = f"{metrica}_{ROTULO_TURNO_1T}"

    metricas_1t = soma_por_municipio.rename(columns=renomear)
    return metricas_1t


def agregar_votos_candidato_1t(votos_por_zona: pd.DataFrame) -> pd.DataFrame:
    """Soma os votos nominais válidos de cada candidato por município (1º turno).

    Args:
        votos_por_zona: Saída de preparar_tabela_1t para o CSV de candidatos.

    Returns:
        Formato longo com "sg_uf", "cd_municipio_tse", "nr_candidato" e
        "votos"; só existem linhas para combinações presentes no CSV (a
        grade completa com zeros é feita em completar_grade_de_votos).
    """
    tabela_reduzida = votos_por_zona[
        COLUNAS_CHAVE_MUNICIPIO + ["NR_CANDIDATO", COLUNA_VOTOS_CANDIDATO_1T]
    ]
    soma_por_candidato = tabela_reduzida.groupby(
        COLUNAS_CHAVE_MUNICIPIO + ["NR_CANDIDATO"],
        as_index=False,
    ).sum()

    votos_longo = soma_por_candidato.rename(
        columns={
            "NR_CANDIDATO": "nr_candidato",
            COLUNA_VOTOS_CANDIDATO_1T: "votos",
        }
    )
    votos_longo["nr_candidato"] = votos_longo["nr_candidato"].astype("int64")
    return votos_longo


def catalogar_candidatos_1t(votos_por_zona: pd.DataFrame) -> pd.DataFrame:
    """Monta o catálogo número -> nome de urna e partido a partir do 1º turno.

    Args:
        votos_por_zona: Saída de preparar_tabela_1t para o CSV de candidatos.

    Returns:
        Tabela com "nr_candidato", "nm_urna_candidato" e "sg_partido", uma
        linha por candidato.

    Raises:
        ValueError: Se um mesmo número tiver mais de um nome ou partido.
    """
    colunas_catalogo = ["NR_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO"]
    catalogo = votos_por_zona[colunas_catalogo].drop_duplicates()
    catalogo = catalogo.rename(
        columns={
            "NR_CANDIDATO": "nr_candidato",
            "NM_URNA_CANDIDATO": "nm_urna_candidato",
            "SG_PARTIDO": "sg_partido",
        }
    )
    catalogo["nr_candidato"] = catalogo["nr_candidato"].astype("int64")

    validar_chave_unica(catalogo, ["nr_candidato"], "catálogo de candidatos do 1º turno")
    return catalogo.reset_index(drop=True)


def montar_tabelas_2t(
    apuracoes: dict[tuple[str, str], ApuracaoMunicipio],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Transforma as apurações do 2º turno em métricas, votos e catálogo.

    Args:
        apuracoes: Mapa (sg_uf, cd_municipio_tse) -> apuração do JSON.

    Returns:
        Tupla (métricas por município com "{metrica}_2t", votos em formato
        longo com "nr_candidato" e "votos", catálogo de candidatos).

    Raises:
        ValueError: Se algum candidato fora de NUMEROS_CANDIDATOS_2T aparecer
            ou se o mesmo número tiver nome/partido diferentes entre
            municípios.
    """
    linhas_metricas: list[dict] = []
    linhas_votos: list[dict] = []
    catalogo_por_numero: dict[int, tuple[str, str]] = {}

    for chave, apuracao in apuracoes.items():
        sg_uf, cd_municipio_tse = chave

        linhas_metricas.append(
            {
                "sg_uf": sg_uf,
                "cd_municipio_tse": cd_municipio_tse,
                f"aptos_{ROTULO_TURNO_2T}": apuracao.aptos,
                f"comparecimento_{ROTULO_TURNO_2T}": apuracao.comparecimento,
                f"abstencao_{ROTULO_TURNO_2T}": apuracao.abstencao,
                f"nao_instaladas_{ROTULO_TURNO_2T}": apuracao.nao_instaladas,
                f"validos_{ROTULO_TURNO_2T}": apuracao.validos,
                f"brancos_{ROTULO_TURNO_2T}": apuracao.brancos,
                f"nulos_{ROTULO_TURNO_2T}": apuracao.nulos,
            }
        )

        for candidato in apuracao.candidatos:
            numero = candidato.numero_candidato
            if numero not in NUMEROS_CANDIDATOS_2T:
                raise ValueError(
                    f"Candidato inesperado no 2º turno em {chave}: {numero}"
                )

            identificacao = (candidato.nome_urna, candidato.sigla_partido)
            if numero in catalogo_por_numero:
                if catalogo_por_numero[numero] != identificacao:
                    raise ValueError(
                        f"Candidato {numero} com nome/partido diferentes entre "
                        f"municípios: {catalogo_por_numero[numero]} vs {identificacao}"
                    )
            else:
                catalogo_por_numero[numero] = identificacao

            linhas_votos.append(
                {
                    "sg_uf": sg_uf,
                    "cd_municipio_tse": cd_municipio_tse,
                    "nr_candidato": numero,
                    "votos": candidato.votos,
                }
            )

    metricas_2t = pd.DataFrame(linhas_metricas)
    votos_2t = pd.DataFrame(linhas_votos)

    linhas_catalogo: list[dict] = []
    for numero, identificacao in catalogo_por_numero.items():
        linhas_catalogo.append(
            {
                "nr_candidato": numero,
                "nm_urna_candidato": identificacao[0],
                "sg_partido": identificacao[1],
            }
        )
    catalogo_2t = pd.DataFrame(linhas_catalogo)

    return metricas_2t, votos_2t, catalogo_2t


def comparar_chaves_entre_turnos(
    chaves_1t: pd.DataFrame,
    chaves_2t: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Anti-join nos dois sentidos entre as chaves do 1º e do 2º turno.

    Args:
        chaves_1t: Tabela com as colunas de COLUNAS_CHAVE_MUNICIPIO (1º turno).
        chaves_2t: Tabela com as mesmas colunas (2º turno).

    Returns:
        Tupla (municípios só no 1º turno, municípios só no 2º turno).
    """
    chaves_1t_unicas = chaves_1t[COLUNAS_CHAVE_MUNICIPIO].drop_duplicates()
    chaves_2t_unicas = chaves_2t[COLUNAS_CHAVE_MUNICIPIO].drop_duplicates()

    juncao = chaves_1t_unicas.merge(
        chaves_2t_unicas,
        on=COLUNAS_CHAVE_MUNICIPIO,
        how="outer",
        indicator=True,
    )

    mascara_so_1t = juncao["_merge"] == "left_only"
    mascara_so_2t = juncao["_merge"] == "right_only"

    somente_1t = juncao.loc[mascara_so_1t, COLUNAS_CHAVE_MUNICIPIO].reset_index(drop=True)
    somente_2t = juncao.loc[mascara_so_2t, COLUNAS_CHAVE_MUNICIPIO].reset_index(drop=True)
    return somente_1t, somente_2t


def completar_grade_de_votos(
    votos_observados: pd.DataFrame,
    chaves_municipios: pd.DataFrame,
    numeros_candidatos: tuple[int, ...],
) -> tuple[pd.DataFrame, int]:
    """Garante uma linha por município x candidato, com zero onde não houve voto.

    Regra de negócio: município sem registro de votos para um candidato
    significa zero voto. A grade completa é construída de forma explícita
    (produto cartesiano município x candidato) e o preenchimento com
    VOTOS_CANDIDATO_AUSENTE é feito e contado aqui, nunca como efeito de um
    merge posterior.

    Args:
        votos_observados: Longo com sg_uf, cd_municipio_tse, nr_candidato e
            votos, somente das combinações existentes na fonte.
        chaves_municipios: Municípios que devem ter linha (chaves únicas).
        numeros_candidatos: Candidatos que devem ter linha em cada município.

    Returns:
        Tupla (longo completo com votos em int64, quantidade de células
        preenchidas com zero).

    Raises:
        ValueError: Se houver candidato fora de numeros_candidatos ou
            município fora de chaves_municipios nos votos observados.
    """
    tabela_candidatos = pd.DataFrame({"nr_candidato": list(numeros_candidatos)})
    tabela_candidatos["nr_candidato"] = tabela_candidatos["nr_candidato"].astype("int64")

    grade = chaves_municipios[COLUNAS_CHAVE_MUNICIPIO].merge(tabela_candidatos, how="cross")

    candidatos_fora = set(votos_observados["nr_candidato"]).difference(numeros_candidatos)
    if candidatos_fora:
        raise ValueError(f"Candidatos fora do esperado: {sorted(candidatos_fora)}")

    chaves_colunas = COLUNAS_CHAVE_MUNICIPIO + ["nr_candidato"]
    validar_chave_unica(votos_observados, chaves_colunas, "votos observados")

    grade_com_votos = grade.merge(
        votos_observados[chaves_colunas + ["votos"]],
        on=chaves_colunas,
        how="left",
        validate="one_to_one",
    )

    linhas_observadas_usadas = int(grade_com_votos["votos"].notna().sum())
    if linhas_observadas_usadas != len(votos_observados):
        raise ValueError(
            f"{len(votos_observados) - linhas_observadas_usadas} linhas de votos "
            "pertencem a municípios fora da lista de chaves"
        )

    mascara_sem_registro = grade_com_votos["votos"].isna()
    quantidade_preenchida = int(mascara_sem_registro.sum())
    grade_com_votos.loc[mascara_sem_registro, "votos"] = VOTOS_CANDIDATO_AUSENTE
    grade_com_votos["votos"] = grade_com_votos["votos"].astype("int64")

    return grade_com_votos, quantidade_preenchida


def anexar_catalogo_de_candidatos(
    votos_completos: pd.DataFrame,
    catalogo: pd.DataFrame,
    numero_turno: int,
) -> pd.DataFrame:
    """Acrescenta turno, nome de urna e partido ao longo de votos.

    Args:
        votos_completos: Saída de completar_grade_de_votos.
        catalogo: Catálogo com nr_candidato, nm_urna_candidato e sg_partido.
        numero_turno: 1 ou 2.

    Returns:
        Tabela com as colunas de COLUNAS_LONGO.

    Raises:
        ValueError: Se algum candidato ficar sem nome/partido no catálogo.
    """
    com_catalogo = votos_completos.merge(
        catalogo,
        on="nr_candidato",
        how="left",
        validate="many_to_one",
    )

    if com_catalogo["nm_urna_candidato"].isna().any():
        raise ValueError("Candidato sem nome de urna no catálogo")

    com_catalogo["nr_turno"] = numero_turno
    com_catalogo["nr_turno"] = com_catalogo["nr_turno"].astype("int64")

    tabela_longa = com_catalogo[COLUNAS_LONGO]
    return tabela_longa


def pivotar_votos_para_colunas(
    votos_completos: pd.DataFrame,
    rotulo_turno: str,
    numeros_candidatos: tuple[int, ...],
) -> pd.DataFrame:
    """Transforma o longo de votos em colunas votos_{turno}_{numero}.

    Args:
        votos_completos: Saída de completar_grade_de_votos (sem lacunas).
        rotulo_turno: "1t" ou "2t".
        numeros_candidatos: Candidatos, na ordem das colunas finais.

    Returns:
        Uma linha por município, colunas de chave + uma coluna por
        candidato, todas int64.

    Raises:
        ValueError: Se a pivotagem produzir valor nulo.
    """
    pivotada = votos_completos.pivot(
        index=COLUNAS_CHAVE_MUNICIPIO,
        columns="nr_candidato",
        values="votos",
    )

    if pivotada.isna().any().any():
        raise ValueError("Pivotagem de votos com lacunas: grade incompleta")

    pivotada = pivotada[list(numeros_candidatos)]
    pivotada.columns = nomes_colunas_votos(rotulo_turno, numeros_candidatos)
    pivotada = pivotada.astype("int64")
    pivotada = pivotada.reset_index()
    return pivotada


def montar_tabela_municipios_config(municipios: list[MunicipioConfig]) -> pd.DataFrame:
    """Cria a espinha da base: identificação, região e flag de exterior.

    Args:
        municipios: Municípios do config.

    Returns:
        Tabela com COLUNAS_IDENTIFICACAO, ordenada por UF e código TSE.
    """
    linhas: list[dict] = []
    for municipio in municipios:
        regiao = obter_regiao_da_uf(municipio.sg_uf)
        linhas.append(
            {
                "sg_uf": municipio.sg_uf,
                "nm_regiao": regiao,
                "cd_municipio_tse": municipio.cd_municipio_tse,
                "cd_municipio_ibge": municipio.cd_municipio_ibge,
                "nm_municipio": municipio.nm_municipio,
                "fl_exterior": municipio.sg_uf == SIGLA_EXTERIOR,
            }
        )

    espinha = pd.DataFrame(linhas, columns=COLUNAS_IDENTIFICACAO)
    espinha = espinha.sort_values(COLUNAS_CHAVE_MUNICIPIO).reset_index(drop=True)
    return espinha


def montar_ordem_colunas_base() -> list[str]:
    """Define a ordem final das colunas da base por município.

    Returns:
        Identificação, depois 1º turno (métricas e votos por candidato),
        depois 2º turno (métricas e votos por candidato).
    """
    ordem: list[str] = list(COLUNAS_IDENTIFICACAO)
    ordem.extend(nomes_colunas_metricas(ROTULO_TURNO_1T))
    ordem.extend(nomes_colunas_votos(ROTULO_TURNO_1T, NUMEROS_CANDIDATOS_1T))
    ordem.extend(nomes_colunas_metricas(ROTULO_TURNO_2T))
    ordem.extend(nomes_colunas_votos(ROTULO_TURNO_2T, NUMEROS_CANDIDATOS_2T))
    return ordem


def montar_base_por_municipio(
    espinha: pd.DataFrame,
    metricas_1t: pd.DataFrame,
    votos_1t_colunas: pd.DataFrame,
    metricas_2t: pd.DataFrame,
    votos_2t_colunas: pd.DataFrame,
) -> pd.DataFrame:
    """Junta identificação, 1º turno e 2º turno em uma linha por município.

    Todos os joins são um-para-um e exigem que o anti-join entre os turnos
    já tenha dado zero órfãos; qualquer nulo após a junção é erro.

    Args:
        espinha: Identificação dos municípios.
        metricas_1t: Métricas do 1º turno por município.
        votos_1t_colunas: Votos por candidato do 1º turno em colunas.
        metricas_2t: Métricas do 2º turno por município.
        votos_2t_colunas: Votos por candidato do 2º turno em colunas.

    Returns:
        Base final com colunas na ordem de montar_ordem_colunas_base.

    Raises:
        ValueError: Se a junção perder linhas ou gerar nulos.
    """
    base = espinha.copy()
    tabelas_a_juntar = [metricas_1t, votos_1t_colunas, metricas_2t, votos_2t_colunas]

    for tabela in tabelas_a_juntar:
        base = base.merge(
            tabela,
            on=COLUNAS_CHAVE_MUNICIPIO,
            how="left",
            validate="one_to_one",
        )

    if len(base) != len(espinha):
        raise ValueError(f"Junção alterou o número de municípios: {len(espinha)} -> {len(base)}")

    colunas_numericas = [coluna for coluna in base.columns if coluna not in COLUNAS_IDENTIFICACAO]
    if base[colunas_numericas].isna().any().any():
        raise ValueError("Base com nulos nas colunas numéricas após a junção")

    for coluna in colunas_numericas:
        base[coluna] = base[coluna].astype("int64")

    ordem_colunas = montar_ordem_colunas_base()
    base = base[ordem_colunas]
    base = base.sort_values(COLUNAS_CHAVE_MUNICIPIO).reset_index(drop=True)
    return base


def listar_divergencias_de_nome(
    espinha: pd.DataFrame,
    nomes_1t: pd.DataFrame,
) -> pd.DataFrame:
    """Lista municípios cujo nome difere entre o config (2º turno) e o CSV do 1º.

    Informativo: a base usa o nome do config. A chave do join é o código.

    Args:
        espinha: Tabela com sg_uf, cd_municipio_tse e nm_municipio (config).
        nomes_1t: Tabela do 1º turno com sg_uf, cd_municipio_tse e NM_MUNICIPIO.

    Returns:
        Linhas em que os nomes diferem, com ambos os nomes.
    """
    nomes_1t_unicos = nomes_1t[COLUNAS_CHAVE_MUNICIPIO + ["NM_MUNICIPIO"]].drop_duplicates()
    comparacao = espinha[COLUNAS_CHAVE_MUNICIPIO + ["nm_municipio"]].merge(
        nomes_1t_unicos,
        on=COLUNAS_CHAVE_MUNICIPIO,
        how="inner",
        validate="one_to_one",
    )
    mascara_diferente = comparacao["nm_municipio"] != comparacao["NM_MUNICIPIO"]
    return comparacao.loc[mascara_diferente].reset_index(drop=True)


# --------------------------------------------------------------------------
# Funções com I/O
# --------------------------------------------------------------------------


def ler_csv_do_zip(caminho_zip: Path, nome_membro: str, colunas: list[str]) -> pd.DataFrame:
    """Lê um CSV do TSE direto de dentro do zip, tudo como texto.

    Todo campo é lido como str para preservar zeros à esquerda; a conversão
    numérica é feita depois, de forma explícita e validada.

    Args:
        caminho_zip: Arquivo zip (não é descompactado em disco).
        nome_membro: Nome do CSV dentro do zip.
        colunas: Colunas a ler.

    Returns:
        Tabela com as colunas pedidas, em texto.

    Raises:
        FileNotFoundError: Se o zip não existir.
        KeyError: Se o CSV não estiver no zip.
    """
    if not caminho_zip.is_file():
        raise FileNotFoundError(f"Zip não encontrado: {caminho_zip}")

    with zipfile.ZipFile(caminho_zip) as arquivo_zip:
        if nome_membro not in arquivo_zip.namelist():
            raise KeyError(f"{nome_membro} não está em {caminho_zip.name}")

        with arquivo_zip.open(nome_membro) as arquivo_csv:
            tabela = pd.read_csv(
                arquivo_csv,
                sep=SEPARADOR_CSV_TSE,
                encoding=ENCODING_CSV_TSE,
                dtype=str,
                usecols=colunas,
                keep_default_na=False,
            )

    LOGGER.info("Lido %s::%s com %d linhas.", caminho_zip.name, nome_membro, len(tabela))
    return tabela


def ler_json_do_disco(caminho: Path) -> dict:
    """Lê um arquivo JSON em UTF-8.

    Args:
        caminho: Arquivo a ler.

    Returns:
        Conteúdo desserializado (objeto JSON).

    Raises:
        ErroLeituraJsonError: Se o conteúdo não for JSON válido ou não for
            um objeto.
    """
    try:
        texto = caminho.read_text(encoding="utf-8")
        conteudo = json.loads(texto)
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroLeituraJsonError(f"{caminho}: JSON ilegível ({erro})") from erro

    if not isinstance(conteudo, dict):
        raise ErroLeituraJsonError(f"{caminho}: o JSON não é um objeto")
    return conteudo


def montar_caminho_json_municipio(sg_uf: str, cd_municipio_tse: str) -> Path:
    """Monta o caminho local do JSON de um município (espelha a URL do TSE).

    Args:
        sg_uf: Sigla da UF em maiúsculas.
        cd_municipio_tse: Código TSE de 5 dígitos.

    Returns:
        Caminho em <PROJ>/dados/json_tse/6258/dados/{uf}/{uf}{cd}-c0001-e006258-u.json.
    """
    uf_minuscula = sg_uf.lower()
    nome_arquivo = f"{uf_minuscula}{cd_municipio_tse}-{SUFIXO_ARQUIVO_JSON_2T}"
    return PASTA_JSON_2T / "dados" / uf_minuscula / nome_arquivo


def carregar_municipios_do_config() -> list[MunicipioConfig]:
    """Lê o config do TSE e devolve a lista de municípios.

    Returns:
        Municípios (5.757 no cenário esperado).

    Raises:
        FileNotFoundError: Se o config não tiver sido coletado (script 01).
    """
    if not CAMINHO_CONFIG_2T.is_file():
        raise FileNotFoundError(f"Config não encontrado (rode o script 01): {CAMINHO_CONFIG_2T}")

    conteudo_config = ler_json_do_disco(CAMINHO_CONFIG_2T)
    municipios = converter_config_em_municipios(conteudo_config)
    LOGGER.info("Config: %d municípios.", len(municipios))
    return municipios


def carregar_apuracoes_2t(
    municipios: list[MunicipioConfig],
) -> dict[tuple[str, str], ApuracaoMunicipio]:
    """Lê e converte o JSON de cada município do 2º turno.

    Todos os problemas de arquivo ausente são reunidos antes de abortar,
    para que a lista completa apareça no erro.

    Args:
        municipios: Municípios do config.

    Returns:
        Mapa (sg_uf, cd_municipio_tse) -> apuração.

    Raises:
        ArquivosAusentesError: Se algum JSON de município não existir.
        ErroLeituraJsonError: Se algum JSON for inválido ou de outro município.
    """
    apuracoes: dict[tuple[str, str], ApuracaoMunicipio] = {}
    caminhos_ausentes: list[Path] = []

    for municipio in municipios:
        caminho = montar_caminho_json_municipio(municipio.sg_uf, municipio.cd_municipio_tse)
        if not caminho.is_file():
            caminhos_ausentes.append(caminho)
            continue

        conteudo = ler_json_do_disco(caminho)
        try:
            validar_identificacao_json(conteudo, municipio.sg_uf, municipio.cd_municipio_tse)
            apuracao = extrair_apuracao_municipio(conteudo)
        except (KeyError, ValueError, TypeError) as erro:
            raise ErroLeituraJsonError(f"{caminho}: {type(erro).__name__}: {erro}") from erro

        chave = (municipio.sg_uf, municipio.cd_municipio_tse)
        apuracoes[chave] = apuracao

    if caminhos_ausentes:
        exemplos = [str(caminho) for caminho in caminhos_ausentes[:10]]
        raise ArquivosAusentesError(
            f"{len(caminhos_ausentes)} JSONs de município ausentes (rode o script 01). "
            f"Exemplos: {exemplos}"
        )

    LOGGER.info("Lidos %d JSONs de município do 2º turno.", len(apuracoes))
    return apuracoes


def registrar_totalizacoes_nao_finais(
    apuracoes: dict[tuple[str, str], ApuracaoMunicipio],
) -> None:
    """Registra aviso para município sem totalização final no 2º turno.

    Não interrompe: a conciliação (script 03, checagem e) reporta o detalhe.

    Args:
        apuracoes: Apurações por município.
    """
    chaves_nao_finais: list[tuple[str, str]] = []

    for chave, apuracao in apuracoes.items():
        totalizacao_ok = apuracao.totalizacao_final == TOTALIZACAO_FINAL
        percentual_ok = apuracao.percentual_secoes_apuradas == PERCENTUAL_SECOES_APURADAS_FINAL
        if not (totalizacao_ok and percentual_ok):
            chaves_nao_finais.append(chave)

    if chaves_nao_finais:
        LOGGER.warning(
            "%d municípios sem totalização final no 2º turno; exemplos: %s",
            len(chaves_nao_finais),
            chaves_nao_finais[:10],
        )
    else:
        LOGGER.info("Todos os municípios do 2º turno com totalização final (100,00%).")


def gravar_tabela_parquet(tabela: pd.DataFrame, caminho: Path) -> None:
    """Grava a tabela em parquet de forma atômica (arquivo parcial + renomeação).

    Args:
        tabela: Tabela a gravar (índice não é gravado).
        caminho: Destino final.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho_parcial = caminho.with_name(caminho.name + SUFIXO_ARQUIVO_PARCIAL)
    tabela.to_parquet(caminho_parcial, engine="pyarrow", index=False)
    caminho_parcial.replace(caminho)
    LOGGER.info("Gravado %s (%d linhas, %d colunas).", caminho, len(tabela), len(tabela.columns))


def gravar_tabela_csv(tabela: pd.DataFrame, caminho: Path) -> None:
    """Grava a tabela em CSV (separador ";", UTF-8) de forma atômica.

    Os códigos de município são gravados como texto com zeros à esquerda;
    ao ler este CSV, use dtype=str para as colunas de código.

    Args:
        tabela: Tabela a gravar (índice não é gravado).
        caminho: Destino final.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho_parcial = caminho.with_name(caminho.name + SUFIXO_ARQUIVO_PARCIAL)
    tabela.to_csv(
        caminho_parcial,
        sep=SEPARADOR_CSV_SAIDA,
        encoding=ENCODING_CSV_SAIDA,
        index=False,
    )
    caminho_parcial.replace(caminho)
    LOGGER.info("Gravado %s (%d linhas).", caminho, len(tabela))


def abortar_se_houver_orfaos(
    somente_1t: pd.DataFrame,
    somente_2t: pd.DataFrame,
) -> None:
    """Interrompe a montagem se houver município em apenas um dos turnos.

    Quando há órfãos, grava a lista em CAMINHO_ORFAOS e levanta erro, sem
    tentar forçar o join.

    Args:
        somente_1t: Municípios presentes só no 1º turno.
        somente_2t: Municípios presentes só no 2º turno.

    Raises:
        ChavesOrfasError: Se qualquer um dos dois conjuntos não for vazio.
    """
    LOGGER.info(
        "Anti-join 1T x 2T: só no 1T = %d; só no 2T = %d.",
        len(somente_1t),
        len(somente_2t),
    )

    if somente_1t.empty and somente_2t.empty:
        return

    somente_1t_marcado = somente_1t.copy()
    somente_1t_marcado["presente_apenas_em"] = "1T"
    somente_2t_marcado = somente_2t.copy()
    somente_2t_marcado["presente_apenas_em"] = "2T"
    orfaos = pd.concat([somente_1t_marcado, somente_2t_marcado], ignore_index=True)

    orfaos.to_csv(
        CAMINHO_ORFAOS,
        sep=SEPARADOR_CSV_SAIDA,
        encoding=ENCODING_CSV_SAIDA,
        index=False,
    )
    raise ChavesOrfasError(
        f"{len(somente_1t)} municípios só no 1T e {len(somente_2t)} só no 2T; "
        f"lista em {CAMINHO_ORFAOS}"
    )


def registrar_diferencas_entre_turnos_nos_candidatos(
    catalogo_1t: pd.DataFrame,
    catalogo_2t: pd.DataFrame,
) -> None:
    """Avisa se os candidatos do 2º turno têm nome/partido diferentes do 1º.

    Informativo; nenhum valor é alterado.

    Args:
        catalogo_1t: Catálogo do 1º turno.
        catalogo_2t: Catálogo do 2º turno.
    """
    comparacao = catalogo_2t.merge(
        catalogo_1t,
        on="nr_candidato",
        how="left",
        suffixes=("_2t", "_1t"),
    )

    for _, linha in comparacao.iterrows():
        nome_igual = linha["nm_urna_candidato_2t"] == linha["nm_urna_candidato_1t"]
        partido_igual = linha["sg_partido_2t"] == linha["sg_partido_1t"]
        if nome_igual and partido_igual:
            continue
        LOGGER.warning(
            "Candidato %s difere entre turnos: 1T=(%s, %s) 2T=(%s, %s)",
            linha["nr_candidato"],
            linha["nm_urna_candidato_1t"],
            linha["sg_partido_1t"],
            linha["nm_urna_candidato_2t"],
            linha["sg_partido_2t"],
        )


def validar_candidatos_do_1t(catalogo_1t: pd.DataFrame) -> None:
    """Confere que o CSV do 1º turno traz exatamente os 12 candidatos esperados.

    Args:
        catalogo_1t: Catálogo do 1º turno.

    Raises:
        ValueError: Se faltar ou sobrar candidato.
    """
    encontrados = set(catalogo_1t["nr_candidato"])
    esperados = set(NUMEROS_CANDIDATOS_1T)
    if encontrados != esperados:
        raise ValueError(
            f"Candidatos do 1T diferentes do esperado: faltam {sorted(esperados - encontrados)}, "
            f"sobram {sorted(encontrados - esperados)}"
        )


def montar_e_gravar() -> None:
    """Orquestra a montagem completa e grava as saídas.

    Ordem: 2º turno (config + JSONs) -> 1º turno (CSVs) -> anti-join ->
    grade com zeros -> base por município e longo -> gravação.

    Raises:
        ChavesOrfasError: Se houver município em apenas um dos turnos.
        ArquivosAusentesError: Se faltarem JSONs do 2º turno.
    """
    # ---- 2º turno ----
    municipios_config = carregar_municipios_do_config()
    espinha = montar_tabela_municipios_config(municipios_config)

    apuracoes_2t = carregar_apuracoes_2t(municipios_config)
    registrar_totalizacoes_nao_finais(apuracoes_2t)
    metricas_2t, votos_observados_2t, catalogo_2t = montar_tabelas_2t(apuracoes_2t)

    # ---- 1º turno ----
    colunas_numericas_detalhe = list(METRICA_POR_COLUNA_DETALHE_1T.keys())
    detalhe_bruto = ler_csv_do_zip(
        ZIP_DETALHE_1T,
        MEMBRO_DETALHE_1T,
        COLUNAS_LIDAS_DETALHE_1T + ["NM_MUNICIPIO"],
    )
    detalhe_por_zona = preparar_tabela_1t(
        detalhe_bruto,
        colunas_numericas_detalhe,
        COLUNAS_CHAVE_ZONA_DETALHE_1T,
        "detalhe 1T",
    )
    metricas_1t = agregar_metricas_1t(detalhe_por_zona)

    candidato_bruto = ler_csv_do_zip(
        ZIP_CANDIDATO_1T,
        MEMBRO_CANDIDATO_1T,
        COLUNAS_LIDAS_CANDIDATO_1T,
    )
    votos_por_zona = preparar_tabela_1t(
        candidato_bruto,
        [COLUNA_VOTOS_CANDIDATO_1T],
        COLUNAS_CHAVE_ZONA_CANDIDATO_1T,
        "candidato 1T",
    )
    catalogo_1t = catalogar_candidatos_1t(votos_por_zona)
    validar_candidatos_do_1t(catalogo_1t)
    votos_observados_1t = agregar_votos_candidato_1t(votos_por_zona)

    # ---- Anti-join nos dois sentidos (detalhe 1T, candidato 1T e 2T) ----
    LOGGER.info("Anti-join: chaves do detalhe 1T vs chaves do 2T (config/JSON).")
    somente_detalhe_1t, somente_2t = comparar_chaves_entre_turnos(metricas_1t, metricas_2t)
    abortar_se_houver_orfaos(somente_detalhe_1t, somente_2t)

    LOGGER.info("Anti-join: chaves dos votos por candidato 1T vs chaves do 2T.")
    somente_candidato_1t, somente_2t_candidato = comparar_chaves_entre_turnos(
        votos_observados_1t,
        metricas_2t,
    )
    abortar_se_houver_orfaos(somente_candidato_1t, somente_2t_candidato)

    divergencias_nome = listar_divergencias_de_nome(espinha, detalhe_por_zona)
    LOGGER.info(
        "Nomes de município diferentes entre config (2T) e CSV (1T): %d (a base usa o nome do config).",
        len(divergencias_nome),
    )

    # ---- Grade completa com zeros explícitos ----
    chaves_municipios = espinha[COLUNAS_CHAVE_MUNICIPIO]

    votos_completos_1t, zeros_1t = completar_grade_de_votos(
        votos_observados_1t,
        chaves_municipios,
        NUMEROS_CANDIDATOS_1T,
    )
    votos_completos_2t, zeros_2t = completar_grade_de_votos(
        votos_observados_2t,
        chaves_municipios,
        NUMEROS_CANDIDATOS_2T,
    )
    LOGGER.info(
        "Células município x candidato preenchidas com zero: 1T=%d, 2T=%d.",
        zeros_1t,
        zeros_2t,
    )

    registrar_diferencas_entre_turnos_nos_candidatos(catalogo_1t, catalogo_2t)

    # ---- Base larga (uma linha por município) ----
    votos_1t_colunas = pivotar_votos_para_colunas(
        votos_completos_1t,
        ROTULO_TURNO_1T,
        NUMEROS_CANDIDATOS_1T,
    )
    votos_2t_colunas = pivotar_votos_para_colunas(
        votos_completos_2t,
        ROTULO_TURNO_2T,
        NUMEROS_CANDIDATOS_2T,
    )
    base = montar_base_por_municipio(
        espinha,
        metricas_1t,
        votos_1t_colunas,
        metricas_2t,
        votos_2t_colunas,
    )

    # ---- Base longa ----
    longo_1t = anexar_catalogo_de_candidatos(votos_completos_1t, catalogo_1t, NUMERO_TURNO_1T)
    longo_2t = anexar_catalogo_de_candidatos(votos_completos_2t, catalogo_2t, NUMERO_TURNO_2T)
    longo = pd.concat([longo_1t, longo_2t], ignore_index=True)
    colunas_ordenacao_longo = ["nr_turno", "sg_uf", "cd_municipio_tse", "nr_candidato"]
    longo = longo.sort_values(colunas_ordenacao_longo).reset_index(drop=True)

    # ---- Gravação ----
    gravar_tabela_parquet(base, CAMINHO_BASE_PARQUET)
    gravar_tabela_csv(base, CAMINHO_BASE_CSV)
    gravar_tabela_parquet(longo, CAMINHO_LONGO_PARQUET)

    LOGGER.info(
        "Montagem concluída: base=%d linhas x %d colunas; longo=%d linhas.",
        len(base),
        len(base.columns),
        len(longo),
    )


def main() -> int:
    """Executa a montagem e devolve o código de saída do processo.

    Returns:
        0 em sucesso; 1 se ocorrer erro esperado (órfãos, arquivo ausente,
        JSON inválido ou dado inconsistente).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        montar_e_gravar()
    except (
        ChavesOrfasError,
        ArquivosAusentesError,
        ErroLeituraJsonError,
        FileNotFoundError,
        KeyError,
        ValueError,
    ) as erro:
        LOGGER.error("Montagem interrompida: %s: %s", type(erro).__name__, erro)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
