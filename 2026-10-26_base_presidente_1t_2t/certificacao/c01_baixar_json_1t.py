"""Coleta independente dos JSONs de municipio do 1o turno (eleicao 6257).

Contexto: o certificador precisa comparar, municipio a municipio, o 1T vindo
do CSV de dados abertos com o 1T vindo do JSON de divulgacao (mesmo formato do
2T). Este script baixa os 5.757 JSONs para dados/json_tse/6257/ espelhando a
URL oficial.

Regras:
    * no maximo 8 requisicoes simultaneas;
    * retry somente em timeout, HTTP 429 e HTTP 5xx (com espera crescente);
    * idempotente: arquivo ja existente e valido (JSON parseavel) e pulado;
    * escrita atomica (arquivo temporario + rename).

Uso:
    nohup python3 -I c01_baixar_json_1t.py > c01.log 2>&1 &
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import socket
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

# Raiz do projeto, dois níveis acima de `certificacao/`: roda de qualquer clone.
PASTA_PROJETO = Path(__file__).resolve().parents[2]
PASTA_DESTINO = PASTA_PROJETO / "dados" / "json_tse" / "6257"
CONFIG_2T = PASTA_PROJETO / "dados" / "json_tse" / "6258" / "config" / "mun-e006258-cm.json"

URL_BASE = "https://resultados.tse.jus.br/oficial/ele2026/6257"
URL_CONFIG_1T = URL_BASE + "/config/mun-e006257-cm.json"
MODELO_URL_MUNICIPIO = URL_BASE + "/dados/{uf}/{uf}{cd}-c0001-e006257-u.json"

MAXIMO_REQUISICOES_SIMULTANEAS = 8
MAXIMO_TENTATIVAS = 6
TIMEOUT_SEGUNDOS = 30
ESPERA_BASE_SEGUNDOS = 2.0
CODIGOS_HTTP_COM_RETRY = {429, 500, 502, 503, 504}
CAMINHO_CERTIFICADOS_SISTEMA = "/etc/ssl/cert.pem"
USER_AGENT = "Mozilla/5.0 (certificacao-base-eleicoes2026)"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
registro = logging.getLogger("c01")

# O Python instalado nao traz CAs; usa o bundle do macOS (verificacao TLS mantida).
CONTEXTO_TLS = ssl.create_default_context(cafile=CAMINHO_CERTIFICADOS_SISTEMA)


class FalhaDefinitiva(Exception):
    """Erro sem possibilidade de retry (ex.: HTTP 404)."""


def baixar_bytes(url: str) -> bytes:
    """Baixa uma URL com retry apenas para falhas transitorias.

    Args:
        url: Endereco completo.

    Returns:
        Corpo da resposta.

    Raises:
        FalhaDefinitiva: Erro HTTP nao transitorio ou tentativas esgotadas.
    """
    ultimo_erro = ""
    for tentativa in range(1, MAXIMO_TENTATIVAS + 1):
        requisicao = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(
                requisicao, timeout=TIMEOUT_SEGUNDOS, context=CONTEXTO_TLS
            ) as resposta:
                return resposta.read()
        except urllib.error.HTTPError as erro:
            if erro.code not in CODIGOS_HTTP_COM_RETRY:
                raise FalhaDefinitiva(f"HTTP {erro.code} em {url}") from erro
            ultimo_erro = f"HTTP {erro.code}"
        except (socket.timeout, TimeoutError) as erro:
            ultimo_erro = f"timeout: {erro}"
        except urllib.error.URLError as erro:
            motivo = erro.reason
            if isinstance(motivo, (socket.timeout, TimeoutError)):
                ultimo_erro = f"timeout: {motivo}"
            else:
                raise FalhaDefinitiva(f"URLError {motivo} em {url}") from erro
        espera = ESPERA_BASE_SEGUNDOS * tentativa
        registro.warning(
            "Tentativa %d/%d falhou (%s) em %s; aguardando %.1fs.",
            tentativa,
            MAXIMO_TENTATIVAS,
            ultimo_erro,
            url,
            espera,
        )
        time.sleep(espera)
    raise FalhaDefinitiva(f"Tentativas esgotadas ({ultimo_erro}) em {url}")


def gravar_atomico(caminho: Path, conteudo: bytes) -> None:
    """Grava bytes em arquivo temporario e renomeia (evita arquivo parcial)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho_temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    caminho_temporario.write_bytes(conteudo)
    caminho_temporario.replace(caminho)


def arquivo_existente_valido(caminho: Path) -> bool:
    """Indica se ja existe um JSON parseavel no caminho (permite retomar)."""
    if not caminho.exists():
        return False
    try:
        json.loads(caminho.read_bytes())
    except json.JSONDecodeError:
        return False
    return True


def baixar_municipio(tarefa: tuple[str, str]) -> tuple[str, str, str]:
    """Baixa um municipio. Retorna (uf, cd, status)."""
    uf, codigo_tse = tarefa
    caminho = PASTA_DESTINO / "dados" / uf / f"{uf}{codigo_tse}-c0001-e006257-u.json"
    if arquivo_existente_valido(caminho):
        return uf, codigo_tse, "ja_existia"
    url = MODELO_URL_MUNICIPIO.format(uf=uf, cd=codigo_tse)
    try:
        conteudo = baixar_bytes(url)
        json.loads(conteudo)
    except FalhaDefinitiva as erro:
        return uf, codigo_tse, f"FALHA: {erro}"
    except json.JSONDecodeError as erro:
        return uf, codigo_tse, f"FALHA: JSON invalido ({erro})"
    gravar_atomico(caminho, conteudo)
    return uf, codigo_tse, "baixado"


def listar_tarefas(config_json: dict) -> list[tuple[str, str]]:
    """Extrai (uf, codigo_tse) de todos os municipios da configuracao."""
    tarefas: list[tuple[str, str]] = []
    for bloco_uf in config_json["abr"]:
        uf = bloco_uf["cd"]
        for municipio in bloco_uf["mu"]:
            tarefas.append((uf, municipio["cd"]))
    return tarefas


def main() -> None:
    """Orquestra: baixa config 1T, confere com a de 2T e baixa os municipios."""
    PASTA_DESTINO.mkdir(parents=True, exist_ok=True)
    conteudo_config = baixar_bytes(URL_CONFIG_1T)
    gravar_atomico(PASTA_DESTINO / "config" / "mun-e006257-cm.json", conteudo_config)
    config_1t = json.loads(conteudo_config)
    config_2t = json.loads(CONFIG_2T.read_bytes())
    tarefas_1t = listar_tarefas(config_1t)
    tarefas_2t = listar_tarefas(config_2t)
    registro.info(
        "Municipios na config 1T: %d; 2T: %d; conjuntos iguais: %s",
        len(tarefas_1t),
        len(tarefas_2t),
        set(tarefas_1t) == set(tarefas_2t),
    )

    contagem_status: dict[str, int] = {}
    falhas: list[tuple[str, str, str]] = []
    concluidos = 0
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAXIMO_REQUISICOES_SIMULTANEAS
    ) as executor:
        for uf, codigo_tse, status in executor.map(baixar_municipio, tarefas_1t):
            concluidos += 1
            chave_status = status.split(":")[0]
            contagem_status[chave_status] = contagem_status.get(chave_status, 0) + 1
            if status.startswith("FALHA"):
                falhas.append((uf, codigo_tse, status))
                registro.error("%s %s %s", uf, codigo_tse, status)
            if concluidos % 250 == 0:
                registro.info("Progresso %d/%d %s", concluidos, len(tarefas_1t), contagem_status)
    registro.info("FIM. Contagem: %s; falhas: %d", contagem_status, len(falhas))


if __name__ == "__main__":
    main()
