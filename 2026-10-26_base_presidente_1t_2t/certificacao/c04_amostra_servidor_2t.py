"""Medicao 3 (parte 2): cache local do 2T x o que o servidor serve hoje.

Sorteia 50 municipios aleatorios do 6258, baixa de novo e compara com o
arquivo local: igualdade de bytes e, se diferir, igualdade dos campos
numericos relevantes (e.te, e.c, e.a, e.esni, v.vv, v.vb, v.tvn, votos).

Uso: python3 -I c04_amostra_servidor_2t.py
"""

from __future__ import annotations

import json
import logging
import random
import socket
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

# Raiz do projeto, dois níveis acima de `certificacao/`: roda de qualquer clone.
PASTA_PROJETO = Path(__file__).resolve().parents[2]
PASTA_6258 = PASTA_PROJETO / "dados" / "json_tse" / "6258"
CONFIG_2T = PASTA_6258 / "config" / "mun-e006258-cm.json"
MODELO_URL = (
    "https://resultados.tse.jus.br/oficial/ele2026/6258/dados/{uf}/{uf}{cd}-c0001-e006258-u.json"
)
TAMANHO_AMOSTRA = 50
MAXIMO_TENTATIVAS = 5
TIMEOUT_SEGUNDOS = 30
CODIGOS_HTTP_COM_RETRY = {429, 500, 502, 503, 504}
CONTEXTO_TLS = ssl.create_default_context(cafile="/etc/ssl/cert.pem")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
registro = logging.getLogger("c04")


def baixar(url: str) -> bytes:
    """Baixa com retry somente em timeout, 429 e 5xx."""
    for tentativa in range(1, MAXIMO_TENTATIVAS + 1):
        requisicao = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (certificacao)"})
        try:
            with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SEGUNDOS, context=CONTEXTO_TLS) as resposta:
                return resposta.read()
        except urllib.error.HTTPError as erro:
            if erro.code not in CODIGOS_HTTP_COM_RETRY:
                raise
        except (socket.timeout, TimeoutError):
            pass
        time.sleep(2.0 * tentativa)
    raise RuntimeError(f"Tentativas esgotadas em {url}")


def extrair_numeros(documento: dict) -> dict[str, int]:
    """Campos numericos relevantes de um JSON de municipio."""
    numeros: dict[str, int] = {
        "te": int(documento["e"]["te"]),
        "c": int(documento["e"]["c"]),
        "a": int(documento["e"]["a"]),
        "esni": int(documento["e"]["esni"]),
        "vv": int(documento["v"]["vv"]),
        "vb": int(documento["v"]["vb"]),
        "tvn": int(documento["v"]["tvn"]),
    }
    for agremiacao in documento["carg"][0]["agr"]:
        for partido in agremiacao["par"]:
            for candidato in partido["cand"]:
                numeros["cand_" + candidato["n"]] = int(candidato["vap"])
    return numeros


def main() -> None:
    """Sorteia, rebaixa e compara."""
    semente = int(time.time())
    registro.info("Semente do sorteio: %d", semente)
    gerador = random.Random(semente)
    config = json.loads(CONFIG_2T.read_text(encoding="utf-8"))
    todos: list[tuple[str, str]] = []
    for bloco_uf in config["abr"]:
        for municipio in bloco_uf["mu"]:
            todos.append((bloco_uf["cd"], municipio["cd"]))
    amostra = gerador.sample(todos, TAMANHO_AMOSTRA)

    iguais_em_bytes = 0
    iguais_em_numeros = 0
    divergentes: list[str] = []
    for uf, codigo_tse in amostra:
        caminho_local = PASTA_6258 / "dados" / uf / f"{uf}{codigo_tse}-c0001-e006258-u.json"
        bytes_local = caminho_local.read_bytes()
        bytes_servidor = baixar(MODELO_URL.format(uf=uf, cd=codigo_tse))
        if bytes_local == bytes_servidor:
            iguais_em_bytes += 1
            iguais_em_numeros += 1
            continue
        numeros_local = extrair_numeros(json.loads(bytes_local))
        numeros_servidor = extrair_numeros(json.loads(bytes_servidor))
        if numeros_local == numeros_servidor:
            iguais_em_numeros += 1
        else:
            divergentes.append(f"{uf} {codigo_tse}")
    print(f"amostra={len(amostra)} iguais_em_bytes={iguais_em_bytes} "
          f"iguais_em_numeros={iguais_em_numeros} divergentes_numericos={divergentes}")


if __name__ == "__main__":
    main()
