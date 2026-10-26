"""Coleta os JSONs oficiais de divulgação do TSE para o 2º turno de 2026.

Contexto:
    O 2º turno da eleição para Presidente de 2026 ainda não saiu nos dados
    abertos do TSE (CSV). A fonte equivalente é o JSON de divulgação de
    resultados, que traz os mesmos números oficiais em outro formato.

O que este script baixa (espelhando a estrutura de pastas da URL):
    config/mun-e006258-cm.json                -> lista de UFs e municípios
    dados/br/br-c0001-e006258-u.json          -> total nacional
    dados/{uf}/{uf}-c0001-e006258-u.json      -> total de cada UF (27 + zz)
    dados/{uf}/{uf}{cd}-c0001-e006258-u.json  -> total de cada município

Destino:
    <PROJ>/dados/json_tse/6258/...

Regras operacionais:
    * Idempotente: arquivo local já baixado, íntegro e com totalização final
      ("tf" == "s") é pulado.
    * Concorrência limitada a MAXIMO_REQUISICOES_SIMULTANEAS conexões.
    * Retentativa com backoff exponencial apenas para erro transitório
      (timeout, falha de rede, HTTP 5xx e HTTP 429). HTTP 404 e demais
      respostas são falha definitiva.
    * Falha nunca é silenciosa: o resumo final lista cada arquivo que falhou
      e o código de saída é 1.

Execução (os dados baixados são não confiáveis; usar o modo isolado):
    nohup python3 -I 01_coletar_json_2t.py > coleta.log 2>&1 &
"""

import dataclasses
import enum
import json
import logging
import random
import re
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

LOGGER = logging.getLogger("coleta_json_2t")

# --------------------------------------------------------------------------
# Constantes de origem e destino
# --------------------------------------------------------------------------

PASTA_SCRIPT = Path(__file__).resolve().parent
RAIZ_PROJETO = PASTA_SCRIPT.parent

CODIGO_ELEICAO = "6258"
URL_BASE_ELEICAO = f"https://resultados.tse.jus.br/oficial/ele2026/{CODIGO_ELEICAO}"
CAMINHO_RELATIVO_CONFIG = f"config/mun-e{CODIGO_ELEICAO:0>6}-cm.json"
SUFIXO_ARQUIVO_DADOS = f"c0001-e{CODIGO_ELEICAO:0>6}-u.json"
PASTA_DESTINO = RAIZ_PROJETO / "dados" / "json_tse" / CODIGO_ELEICAO
SUFIXO_ARQUIVO_PARCIAL = ".parcial"

NUMERO_TURNO_ESPERADO = "2"
SIGLA_BRASIL = "br"
SIGLA_EXTERIOR = "zz"
TIPO_ABRANGENCIA_BRASIL = "br"
TIPO_ABRANGENCIA_UF = "uf"
TIPO_ABRANGENCIA_MUNICIPIO = "mu"
TIPO_ABRANGENCIA_CONFIG = "config"
TOTALIZACAO_FINAL = "s"

# Números oficiais usados apenas para sanidade do config (a conciliação
# completa fica no script 03).
TOTAL_UFS_CONFIG_ESPERADO = 28
TOTAL_MUNICIPIOS_CONFIG_ESPERADO = 5757

# --------------------------------------------------------------------------
# Constantes de rede
# --------------------------------------------------------------------------

MAXIMO_REQUISICOES_SIMULTANEAS = 8
TIMEOUT_CONEXAO_SEGUNDOS = 10.0
TIMEOUT_LEITURA_SEGUNDOS = 30.0
MAXIMO_TENTATIVAS = 5
ESPERA_BASE_SEGUNDOS = 1.0
FATOR_BACKOFF = 2.0
JITTER_MAXIMO_SEGUNDOS = 0.5
CODIGO_HTTP_SUCESSO = 200
CODIGO_HTTP_LIMITE_DE_TAXA = 429
CODIGO_HTTP_INICIO_ERRO_SERVIDOR = 500
CABECALHO_USER_AGENT = "eleicoes2026-coleta-json/1.0 (pesquisa academica)"
INTERVALO_LOG_PROGRESSO = 500

PADRAO_SIGLA_UF = re.compile(r"^[a-z]{2}$")
PADRAO_CODIGO_MUNICIPIO = re.compile(r"^[0-9]{5}$")

# Falhas de rede que justificam nova tentativa.
EXCECOES_TRANSITORIAS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


# --------------------------------------------------------------------------
# Tipos
# --------------------------------------------------------------------------


class SituacaoDownload(enum.Enum):
    """Resultado possível do processamento de um arquivo."""

    BAIXADO = "baixado"
    PULADO = "pulado"
    FALHOU = "falhou"


class ConteudoInvalidoError(ValueError):
    """O JSON recebido ou lido do disco não tem a estrutura esperada."""


class FalhaDownloadError(RuntimeError):
    """O download não foi concluído (erro definitivo ou tentativas esgotadas).

    Attributes:
        tentativas: Quantas requisições foram feitas antes de desistir.
    """

    def __init__(self, mensagem: str, tentativas: int = 0) -> None:
        super().__init__(mensagem)
        self.tentativas = tentativas


@dataclasses.dataclass(frozen=True)
class TarefaDownload:
    """Um arquivo a ser garantido em disco.

    Attributes:
        tipo_abrangencia: "config", "br", "uf" ou "mu".
        codigo_abrangencia: "config", "br", sigla da UF em minúsculas ou
            código TSE do município (5 dígitos).
        url: Endereço completo do arquivo na divulgação do TSE.
        caminho_destino: Caminho local, espelhando a estrutura da URL.
    """

    tipo_abrangencia: str
    codigo_abrangencia: str
    url: str
    caminho_destino: Path


@dataclasses.dataclass(frozen=True)
class ResultadoDownload:
    """Desfecho do processamento de uma tarefa."""

    tarefa: TarefaDownload
    situacao: SituacaoDownload
    tentativas: int
    mensagem_erro: str


@dataclasses.dataclass(frozen=True)
class MunicipioConfig:
    """Município listado no arquivo de configuração do TSE."""

    sigla_uf: str
    codigo_tse: str


# --------------------------------------------------------------------------
# Funções puras: caminhos, URLs e validação de conteúdo
# --------------------------------------------------------------------------


def validar_sigla_uf(sigla_uf: str) -> None:
    """Garante que a sigla seja segura para compor URL e caminho de arquivo.

    Os dados vêm de uma fonte externa; a validação impede que um valor
    inesperado (por exemplo com "../") escape da pasta de destino.

    Args:
        sigla_uf: Sigla da UF em minúsculas (ex.: "sp", "zz").

    Raises:
        ConteudoInvalidoError: Se não forem exatamente duas letras minúsculas.
    """
    if not PADRAO_SIGLA_UF.match(sigla_uf):
        raise ConteudoInvalidoError(f"Sigla de UF inválida: {sigla_uf!r}")


def validar_codigo_municipio(codigo_municipio: str) -> None:
    """Garante que o código TSE do município tenha exatamente 5 dígitos.

    Args:
        codigo_municipio: Código TSE (ex.: "71072", "01120").

    Raises:
        ConteudoInvalidoError: Se não forem exatamente cinco dígitos.
    """
    if not PADRAO_CODIGO_MUNICIPIO.match(codigo_municipio):
        raise ConteudoInvalidoError(
            f"Código de município inválido: {codigo_municipio!r}"
        )


def montar_caminho_relativo_dados(
    sigla_uf: str,
    codigo_municipio: str | None,
) -> str:
    """Monta o caminho relativo do arquivo de resultado, igual na URL e no disco.

    Exemplos:
        ("br", None)    -> "dados/br/br-c0001-e006258-u.json"
        ("sp", None)    -> "dados/sp/sp-c0001-e006258-u.json"
        ("sp", "71072") -> "dados/sp/sp71072-c0001-e006258-u.json"

    Args:
        sigla_uf: "br" para o total nacional ou sigla da UF em minúsculas.
        codigo_municipio: Código TSE de 5 dígitos, ou None para totais de
            UF e do Brasil.

    Returns:
        Caminho relativo à raiz da eleição, com separador "/".

    Raises:
        ConteudoInvalidoError: Se a sigla ou o código não forem válidos.
    """
    validar_sigla_uf(sigla_uf)

    if codigo_municipio is None:
        nome_arquivo = f"{sigla_uf}-{SUFIXO_ARQUIVO_DADOS}"
    else:
        validar_codigo_municipio(codigo_municipio)
        nome_arquivo = f"{sigla_uf}{codigo_municipio}-{SUFIXO_ARQUIVO_DADOS}"

    return f"dados/{sigla_uf}/{nome_arquivo}"


def criar_tarefa(
    tipo_abrangencia: str,
    codigo_abrangencia: str,
    caminho_relativo: str,
) -> TarefaDownload:
    """Cria a tarefa de download a partir do caminho relativo.

    Args:
        tipo_abrangencia: "config", "br", "uf" ou "mu".
        codigo_abrangencia: Identificador do recorte (ver TarefaDownload).
        caminho_relativo: Caminho relativo à raiz da eleição.

    Returns:
        Tarefa com URL completa e destino local espelhando a URL.
    """
    url_completa = f"{URL_BASE_ELEICAO}/{caminho_relativo}"
    caminho_local = PASTA_DESTINO / caminho_relativo

    tarefa = TarefaDownload(
        tipo_abrangencia=tipo_abrangencia,
        codigo_abrangencia=codigo_abrangencia,
        url=url_completa,
        caminho_destino=caminho_local,
    )
    return tarefa


def validar_conteudo_config(conteudo: object) -> None:
    """Valida a estrutura mínima do arquivo de configuração de municípios.

    Args:
        conteudo: Objeto resultante de json.loads.

    Raises:
        ConteudoInvalidoError: Se faltar a lista "abr" ou se algum item não
            tiver "cd" e a lista "mu".
    """
    if not isinstance(conteudo, dict):
        raise ConteudoInvalidoError("Config não é um objeto JSON.")

    lista_abrangencias = conteudo.get("abr")
    if not isinstance(lista_abrangencias, list) or not lista_abrangencias:
        raise ConteudoInvalidoError("Config sem lista 'abr' preenchida.")

    for abrangencia in lista_abrangencias:
        if not isinstance(abrangencia, dict):
            raise ConteudoInvalidoError("Item de 'abr' não é um objeto.")
        if "cd" not in abrangencia:
            raise ConteudoInvalidoError("Item de 'abr' sem campo 'cd'.")
        if not isinstance(abrangencia.get("mu"), list):
            raise ConteudoInvalidoError("Item de 'abr' sem lista 'mu'.")


def validar_conteudo_apuracao(
    conteudo: object,
    tipo_abrangencia: str,
    codigo_abrangencia: str,
) -> None:
    """Valida que o JSON de resultado corresponde ao recorte solicitado.

    A checagem de "cdabr" evita aceitar, por exemplo, o arquivo de um
    município gravado no caminho de outro.

    Args:
        conteudo: Objeto resultante de json.loads.
        tipo_abrangencia: "br", "uf" ou "mu".
        codigo_abrangencia: "br", sigla da UF ou código TSE do município.

    Raises:
        ConteudoInvalidoError: Se faltar bloco obrigatório, se o turno ou a
            eleição forem diferentes do esperado ou se o recorte não bater.
    """
    if not isinstance(conteudo, dict):
        raise ConteudoInvalidoError("Resultado não é um objeto JSON.")

    campos_obrigatorios = ("ele", "t", "tpabr", "cdabr", "tf", "carg", "s", "e", "v")
    for campo in campos_obrigatorios:
        if campo not in conteudo:
            raise ConteudoInvalidoError(f"Campo obrigatório ausente: {campo!r}")

    if conteudo["ele"] != CODIGO_ELEICAO:
        raise ConteudoInvalidoError(f"Eleição inesperada: {conteudo['ele']!r}")

    if conteudo["t"] != NUMERO_TURNO_ESPERADO:
        raise ConteudoInvalidoError(f"Turno inesperado: {conteudo['t']!r}")

    if conteudo["tpabr"] != tipo_abrangencia:
        raise ConteudoInvalidoError(
            f"Tipo de abrangência {conteudo['tpabr']!r} != {tipo_abrangencia!r}"
        )

    if conteudo["cdabr"] != codigo_abrangencia:
        raise ConteudoInvalidoError(
            f"Código de abrangência {conteudo['cdabr']!r} != {codigo_abrangencia!r}"
        )


def validar_conteudo_da_tarefa(conteudo: object, tarefa: TarefaDownload) -> None:
    """Aplica a validação adequada ao tipo da tarefa (config ou resultado).

    Args:
        conteudo: Objeto resultante de json.loads.
        tarefa: Tarefa à qual o conteúdo pertence.

    Raises:
        ConteudoInvalidoError: Se o conteúdo não for válido para a tarefa.
    """
    if tarefa.tipo_abrangencia == TIPO_ABRANGENCIA_CONFIG:
        validar_conteudo_config(conteudo)
        return

    validar_conteudo_apuracao(
        conteudo,
        tarefa.tipo_abrangencia,
        tarefa.codigo_abrangencia,
    )


def totalizacao_esta_final(conteudo: dict) -> bool:
    """Indica se o JSON de resultado traz totalização final ("tf" == "s").

    Args:
        conteudo: Resultado já validado.

    Returns:
        True quando o TSE marca a totalização como final.
    """
    marca_totalizacao = conteudo.get("tf")
    return marca_totalizacao == TOTALIZACAO_FINAL


def calcular_espera_backoff(numero_tentativa: int, jitter: float) -> float:
    """Calcula a espera antes da próxima tentativa (backoff exponencial).

    Args:
        numero_tentativa: Tentativa que acabou de falhar (1, 2, 3, ...).
        jitter: Acréscimo aleatório em segundos, para dessincronizar threads.

    Returns:
        Segundos de espera: ESPERA_BASE * FATOR_BACKOFF ** (tentativa - 1) + jitter.
    """
    expoente = numero_tentativa - 1
    espera_exponencial = ESPERA_BASE_SEGUNDOS * (FATOR_BACKOFF**expoente)
    return espera_exponencial + jitter


def codigo_http_e_transitorio(codigo_http: int) -> bool:
    """Informa se um status HTTP justifica nova tentativa.

    Args:
        codigo_http: Status da resposta.

    Returns:
        True para 5xx e 429 (limite de taxa); False para os demais
        (inclusive 404, que é falha definitiva).
    """
    if codigo_http >= CODIGO_HTTP_INICIO_ERRO_SERVIDOR:
        return True
    return codigo_http == CODIGO_HTTP_LIMITE_DE_TAXA


def extrair_municipios_do_config(conteudo: dict) -> list[MunicipioConfig]:
    """Lista todos os municípios do config, na ordem em que aparecem.

    Args:
        conteudo: Config já validado por validar_conteudo_config.

    Returns:
        Lista de municípios com sigla da UF (minúscula) e código TSE.

    Raises:
        ConteudoInvalidoError: Se alguma sigla ou código for inválido ou se
            houver município repetido na mesma UF.
    """
    municipios: list[MunicipioConfig] = []
    chaves_vistas: set[tuple[str, str]] = set()

    for abrangencia in conteudo["abr"]:
        sigla_uf = abrangencia["cd"]
        validar_sigla_uf(sigla_uf)

        for municipio in abrangencia["mu"]:
            codigo_tse = municipio.get("cd", "")
            validar_codigo_municipio(codigo_tse)

            chave = (sigla_uf, codigo_tse)
            if chave in chaves_vistas:
                raise ConteudoInvalidoError(
                    f"Município repetido no config: {chave}"
                )
            chaves_vistas.add(chave)

            municipios.append(MunicipioConfig(sigla_uf, codigo_tse))

    return municipios


def extrair_siglas_uf_do_config(conteudo: dict) -> list[str]:
    """Lista as siglas (minúsculas) das abrangências do config, incluindo "zz".

    Args:
        conteudo: Config já validado.

    Returns:
        Siglas na ordem do arquivo.
    """
    siglas: list[str] = []
    for abrangencia in conteudo["abr"]:
        sigla_uf = abrangencia["cd"]
        validar_sigla_uf(sigla_uf)
        siglas.append(sigla_uf)
    return siglas


def montar_tarefas(conteudo_config: dict) -> list[TarefaDownload]:
    """Monta a lista completa de arquivos de resultado a baixar.

    Ordem: nacional, UFs (incluindo "zz") e municípios.

    Args:
        conteudo_config: Config já validado.

    Returns:
        Uma tarefa por arquivo de resultado (1 + 28 + 5.757 no cenário
        esperado). O próprio config não entra aqui.
    """
    tarefas: list[TarefaDownload] = []

    caminho_nacional = montar_caminho_relativo_dados(SIGLA_BRASIL, None)
    tarefa_nacional = criar_tarefa(
        TIPO_ABRANGENCIA_BRASIL,
        SIGLA_BRASIL,
        caminho_nacional,
    )
    tarefas.append(tarefa_nacional)

    siglas_uf = extrair_siglas_uf_do_config(conteudo_config)
    for sigla_uf in siglas_uf:
        caminho_uf = montar_caminho_relativo_dados(sigla_uf, None)
        tarefa_uf = criar_tarefa(TIPO_ABRANGENCIA_UF, sigla_uf, caminho_uf)
        tarefas.append(tarefa_uf)

    municipios = extrair_municipios_do_config(conteudo_config)
    for municipio in municipios:
        caminho_municipio = montar_caminho_relativo_dados(
            municipio.sigla_uf,
            municipio.codigo_tse,
        )
        tarefa_municipio = criar_tarefa(
            TIPO_ABRANGENCIA_MUNICIPIO,
            municipio.codigo_tse,
            caminho_municipio,
        )
        tarefas.append(tarefa_municipio)

    return tarefas


# --------------------------------------------------------------------------
# Funções com I/O
# --------------------------------------------------------------------------


def ler_json_local(caminho: Path) -> object | None:
    """Lê um JSON do disco; devolve None se não existir ou estiver corrompido.

    Args:
        caminho: Arquivo local.

    Returns:
        Objeto desserializado, ou None quando o arquivo não existe ou não é
        um JSON válido em UTF-8 (nesse caso o arquivo será baixado de novo).
    """
    if not caminho.is_file():
        return None

    try:
        texto = caminho.read_text(encoding="utf-8")
        conteudo = json.loads(texto)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erro:
        LOGGER.warning("Arquivo local ilegível, será baixado de novo: %s (%s)", caminho, erro)
        return None

    return conteudo


def arquivo_local_esta_completo(tarefa: TarefaDownload) -> bool:
    """Decide se o arquivo local dispensa novo download.

    Regra: o arquivo existe, é JSON válido para a tarefa e, quando for
    resultado de apuração, está com totalização final ("tf" == "s").
    Arquivo com totalização parcial é rebaixado a cada execução, pois pode
    ter sido gravado antes do fechamento da apuração.

    Args:
        tarefa: Tarefa a verificar.

    Returns:
        True se puder ser pulado.
    """
    conteudo = ler_json_local(tarefa.caminho_destino)
    if conteudo is None:
        return False

    try:
        validar_conteudo_da_tarefa(conteudo, tarefa)
    except ConteudoInvalidoError as erro:
        LOGGER.warning("Arquivo local inválido, será baixado de novo: %s (%s)", tarefa.caminho_destino, erro)
        return False

    if tarefa.tipo_abrangencia == TIPO_ABRANGENCIA_CONFIG:
        return True

    return totalizacao_esta_final(conteudo)


def gravar_atomicamente(caminho: Path, conteudo_bytes: bytes) -> None:
    """Grava o arquivo de forma atômica (arquivo parcial + renomeação).

    Evita deixar um JSON truncado no destino caso o processo seja
    interrompido no meio da escrita.

    Args:
        caminho: Destino final.
        conteudo_bytes: Conteúdo exatamente como recebido do servidor.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho_parcial = caminho.with_name(caminho.name + SUFIXO_ARQUIVO_PARCIAL)
    caminho_parcial.write_bytes(conteudo_bytes)
    caminho_parcial.replace(caminho)


def baixar_com_retentativas(
    cliente: httpx.Client,
    url: str,
) -> tuple[bytes, int]:
    """Baixa uma URL, repetindo apenas em caso de erro transitório.

    Erros transitórios: timeout, falha de rede, HTTP 5xx e HTTP 429.
    Qualquer outra resposta diferente de 200 (ex.: 404) é definitiva.

    Args:
        cliente: Cliente HTTP compartilhado entre as threads.
        url: Endereço a baixar.

    Returns:
        Tupla (corpo da resposta, número de tentativas usadas).

    Raises:
        FalhaDownloadError: Em erro definitivo ou ao esgotar as tentativas.
    """
    ultimo_motivo = "nenhuma tentativa realizada"

    for numero_tentativa in range(1, MAXIMO_TENTATIVAS + 1):
        motivo_transitorio = ""

        try:
            resposta = cliente.get(url)
        except EXCECOES_TRANSITORIAS as erro:
            motivo_transitorio = f"{type(erro).__name__}: {erro}"
        except httpx.HTTPError as erro:
            raise FalhaDownloadError(
                f"Erro definitivo de HTTP em {url}: {type(erro).__name__}: {erro}",
                tentativas=numero_tentativa,
            ) from erro
        else:
            codigo_http = resposta.status_code
            if codigo_http == CODIGO_HTTP_SUCESSO:
                return resposta.content, numero_tentativa

            if not codigo_http_e_transitorio(codigo_http):
                raise FalhaDownloadError(
                    f"HTTP {codigo_http} em {url}",
                    tentativas=numero_tentativa,
                )

            motivo_transitorio = f"HTTP {codigo_http}"

        ultimo_motivo = motivo_transitorio
        if numero_tentativa < MAXIMO_TENTATIVAS:
            jitter = random.uniform(0.0, JITTER_MAXIMO_SEGUNDOS)
            espera = calcular_espera_backoff(numero_tentativa, jitter)
            LOGGER.warning(
                "Falha transitória (%s) em %s; tentativa %d/%d; nova tentativa em %.1fs.",
                motivo_transitorio,
                url,
                numero_tentativa,
                MAXIMO_TENTATIVAS,
                espera,
            )
            time.sleep(espera)

    raise FalhaDownloadError(
        f"Tentativas esgotadas ({MAXIMO_TENTATIVAS}) em {url}: {ultimo_motivo}",
        tentativas=MAXIMO_TENTATIVAS,
    )


def processar_tarefa(cliente: httpx.Client, tarefa: TarefaDownload) -> ResultadoDownload:
    """Garante em disco o arquivo da tarefa: pula, ou baixa, valida e grava.

    Nenhuma exceção de download ou de conteúdo escapa desta função: ela é
    convertida em ResultadoDownload com situação FALHOU, para que o resumo
    final liste todos os arquivos com problema.

    Args:
        cliente: Cliente HTTP compartilhado.
        tarefa: Arquivo a garantir.

    Returns:
        Resultado com situação, tentativas e mensagem de erro (vazia se ok).
    """
    if arquivo_local_esta_completo(tarefa):
        return ResultadoDownload(tarefa, SituacaoDownload.PULADO, 0, "")

    try:
        corpo, tentativas = baixar_com_retentativas(cliente, tarefa.url)
    except FalhaDownloadError as erro:
        return ResultadoDownload(tarefa, SituacaoDownload.FALHOU, erro.tentativas, str(erro))

    try:
        texto = corpo.decode("utf-8")
        conteudo = json.loads(texto)
        validar_conteudo_da_tarefa(conteudo, tarefa)
    except (UnicodeDecodeError, json.JSONDecodeError, ConteudoInvalidoError) as erro:
        mensagem = f"Conteúdo inválido em {tarefa.url}: {type(erro).__name__}: {erro}"
        return ResultadoDownload(tarefa, SituacaoDownload.FALHOU, tentativas, mensagem)

    try:
        gravar_atomicamente(tarefa.caminho_destino, corpo)
    except OSError as erro:
        mensagem = f"Falha ao gravar {tarefa.caminho_destino}: {erro}"
        return ResultadoDownload(tarefa, SituacaoDownload.FALHOU, tentativas, mensagem)

    return ResultadoDownload(tarefa, SituacaoDownload.BAIXADO, tentativas, "")


def criar_cliente_http() -> httpx.Client:
    """Cria o cliente HTTP (thread-safe) com timeouts e pool limitado.

    Returns:
        Cliente configurado com no máximo MAXIMO_REQUISICOES_SIMULTANEAS
        conexões, sem seguir redirecionamentos.
    """
    timeout = httpx.Timeout(
        connect=TIMEOUT_CONEXAO_SEGUNDOS,
        read=TIMEOUT_LEITURA_SEGUNDOS,
        write=TIMEOUT_LEITURA_SEGUNDOS,
        pool=TIMEOUT_LEITURA_SEGUNDOS,
    )
    limites = httpx.Limits(
        max_connections=MAXIMO_REQUISICOES_SIMULTANEAS,
        max_keepalive_connections=MAXIMO_REQUISICOES_SIMULTANEAS,
    )
    cabecalhos = {"User-Agent": CABECALHO_USER_AGENT}

    cliente = httpx.Client(
        timeout=timeout,
        limits=limites,
        headers=cabecalhos,
        follow_redirects=False,
    )
    return cliente


def garantir_config(cliente: httpx.Client) -> dict:
    """Garante o config em disco e devolve seu conteúdo validado.

    Args:
        cliente: Cliente HTTP.

    Returns:
        Conteúdo do config (lista de UFs e municípios).

    Raises:
        FalhaDownloadError: Se o config não puder ser obtido.
    """
    tarefa_config = criar_tarefa(
        TIPO_ABRANGENCIA_CONFIG,
        TIPO_ABRANGENCIA_CONFIG,
        CAMINHO_RELATIVO_CONFIG,
    )
    resultado = processar_tarefa(cliente, tarefa_config)

    if resultado.situacao == SituacaoDownload.FALHOU:
        raise FalhaDownloadError(f"Config não obtido: {resultado.mensagem_erro}")

    LOGGER.info(
        "Config %s: %s",
        resultado.situacao.value,
        tarefa_config.caminho_destino,
    )

    conteudo = ler_json_local(tarefa_config.caminho_destino)
    if not isinstance(conteudo, dict):
        raise FalhaDownloadError("Config gravado mas ilegível.")
    return conteudo


def executar_tarefas(
    cliente: httpx.Client,
    tarefas: list[TarefaDownload],
) -> list[ResultadoDownload]:
    """Executa todas as tarefas com concorrência limitada e registra progresso.

    Args:
        cliente: Cliente HTTP compartilhado.
        tarefas: Arquivos a garantir.

    Returns:
        Um resultado por tarefa (a ordem de conclusão pode diferir da ordem
        de entrada).
    """
    resultados: list[ResultadoDownload] = []
    futuros: list[Future[ResultadoDownload]] = []

    with ThreadPoolExecutor(max_workers=MAXIMO_REQUISICOES_SIMULTANEAS) as executor:
        for tarefa in tarefas:
            futuro = executor.submit(processar_tarefa, cliente, tarefa)
            futuros.append(futuro)

        for futuro in as_completed(futuros):
            resultado = futuro.result()
            resultados.append(resultado)

            if resultado.situacao == SituacaoDownload.FALHOU:
                LOGGER.error("FALHA em %s: %s", resultado.tarefa.url, resultado.mensagem_erro)

            total_concluido = len(resultados)
            if total_concluido % INTERVALO_LOG_PROGRESSO == 0:
                LOGGER.info("Progresso: %d/%d arquivos processados.", total_concluido, len(tarefas))

    return resultados


def contar_por_situacao(resultados: list[ResultadoDownload]) -> dict[SituacaoDownload, int]:
    """Conta os resultados por situação.

    Args:
        resultados: Resultados de todas as tarefas.

    Returns:
        Contagem para cada situação (zero quando não ocorreu).
    """
    contagem = {
        SituacaoDownload.BAIXADO: 0,
        SituacaoDownload.PULADO: 0,
        SituacaoDownload.FALHOU: 0,
    }
    for resultado in resultados:
        contagem[resultado.situacao] += 1
    return contagem


def registrar_sanidade_do_config(conteudo_config: dict) -> None:
    """Registra aviso se o config divergir dos totais oficiais esperados.

    Não interrompe a coleta: a conciliação (script 03) é quem reprova.

    Args:
        conteudo_config: Config já validado.
    """
    siglas_uf = extrair_siglas_uf_do_config(conteudo_config)
    municipios = extrair_municipios_do_config(conteudo_config)

    LOGGER.info(
        "Config gerado em %s %s: %d abrangências (UFs + zz) e %d municípios.",
        conteudo_config.get("dg", "?"),
        conteudo_config.get("hg", "?"),
        len(siglas_uf),
        len(municipios),
    )

    if len(siglas_uf) != TOTAL_UFS_CONFIG_ESPERADO:
        LOGGER.warning(
            "Número de abrangências %d difere do esperado (%d).",
            len(siglas_uf),
            TOTAL_UFS_CONFIG_ESPERADO,
        )

    if len(municipios) != TOTAL_MUNICIPIOS_CONFIG_ESPERADO:
        LOGGER.warning(
            "Número de municípios %d difere do esperado (%d).",
            len(municipios),
            TOTAL_MUNICIPIOS_CONFIG_ESPERADO,
        )


def main() -> int:
    """Orquestra a coleta completa e devolve o código de saída do processo.

    Returns:
        0 se todos os arquivos estão em disco, íntegros; 1 se houve qualquer
        falha (listada no log).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    # O httpx registra uma linha INFO por requisição (milhares de linhas).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    LOGGER.info("Destino da coleta: %s", PASTA_DESTINO)

    inicio = time.monotonic()
    cliente = criar_cliente_http()

    try:
        conteudo_config = garantir_config(cliente)
        registrar_sanidade_do_config(conteudo_config)

        tarefas = montar_tarefas(conteudo_config)
        LOGGER.info("Arquivos de resultado a garantir: %d", len(tarefas))

        resultados = executar_tarefas(cliente, tarefas)
    except (FalhaDownloadError, ConteudoInvalidoError) as erro:
        LOGGER.error("Coleta interrompida: %s", erro)
        return 1
    finally:
        cliente.close()

    contagem = contar_por_situacao(resultados)
    duracao = time.monotonic() - inicio
    LOGGER.info(
        "Resumo: baixados=%d pulados=%d falhos=%d total=%d em %.1fs.",
        contagem[SituacaoDownload.BAIXADO],
        contagem[SituacaoDownload.PULADO],
        contagem[SituacaoDownload.FALHOU],
        len(resultados),
        duracao,
    )

    if contagem[SituacaoDownload.FALHOU] > 0:
        LOGGER.error("Arquivos que falharam (rode novamente para retomar):")
        for resultado in resultados:
            if resultado.situacao == SituacaoDownload.FALHOU:
                LOGGER.error("  %s -> %s", resultado.tarefa.url, resultado.mensagem_erro)
        return 1

    LOGGER.info("Coleta concluída sem falhas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
