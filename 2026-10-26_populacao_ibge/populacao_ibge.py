"""Baixa e confere a população estimada de cada município (IBGE, 2026).

Contexto:
    A seção "Cidades" do HTML mostra os habitantes de cada cidade ao lado
    dos eleitores. A base eleitoral (TSE) não tem população; ela vem da
    estimativa oficial do IBGE (tabela 6579, variável 9324, "População
    residente estimada"), pela API pública de agregados.

O que faz:
    1. Baixa o total do Brasil e o de cada município para `PERIODO` em
       `dados/ibge/` (dados brutos, fora do git; regeneráveis).
    2. Confere: um valor por município, sem vazio, e a soma dos municípios
       igual ao total do Brasil publicado pelo IBGE.
    3. Grava `dados/processados/populacao_municipios_ibge.csv`
       (`cd_municipio_ibge;populacao`), lido pelo gerador do HTML.

Execução (dados baixados são não confiáveis; modo isolado):
    python3 -I 2026-10-26_populacao_ibge/populacao_ibge.py
"""

import json
import logging
import pathlib
import subprocess

import pandas as pd

LOGGER = logging.getLogger(__name__)

RAIZ_PROJETO = pathlib.Path(__file__).resolve().parent.parent
PASTA_BRUTOS = RAIZ_PROJETO / "dados" / "ibge"
CAMINHO_SAIDA = RAIZ_PROJETO / "dados" / "processados" / "populacao_municipios_ibge.csv"

AGREGADO = "6579"
VARIAVEL = "9324"
PERIODO = "2026"
URL_BASE = "https://servicodados.ibge.gov.br/api/v3/agregados"
TEMPO_LIMITE_SEGUNDOS = 180
# O IBGE tem 5.570 municípios (DF conta como um); abaixo disso a resposta veio incompleta.
MINIMO_MUNICIPIOS = 5570


def montar_url(nivel: str) -> str:
    """Monta a URL da API de agregados para um nível geográfico (N1 Brasil, N6 municípios)."""
    return (
        f"{URL_BASE}/{AGREGADO}/periodos/{PERIODO}/variaveis/{VARIAVEL}"
        f"?localidades={nivel}%5Ball%5D"
    )


def baixar_json(url: str, caminho_destino: pathlib.Path) -> object:
    """Baixa um JSON da API do IBGE para o disco (se ainda não existir) e o devolve.

    Args:
        url: Endereço da API.
        caminho_destino: Arquivo bruto em `dados/ibge/`.

    Returns:
        O JSON lido do arquivo.
    """
    if not caminho_destino.exists():
        # curl usa os certificados do sistema; o Python desta máquina não confia na cadeia
        # (proxy corporativo). A verificação de certificado continua ligada.
        LOGGER.info("Baixando %s", url)
        comando = ["curl", "-sS", "--fail", "--max-time", str(TEMPO_LIMITE_SEGUNDOS), "-o", str(caminho_destino), url]
        subprocess.run(comando, check=True)
    with caminho_destino.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def extrair_series(resposta_api: object) -> dict[str, str]:
    """Extrai {código da localidade: valor} da resposta da API de agregados.

    Raises:
        ValueError: Se a resposta não tiver o formato esperado.
    """
    if not isinstance(resposta_api, list) or len(resposta_api) != 1:
        raise ValueError("Resposta da API do IBGE em formato inesperado.")
    resultados = resposta_api[0]["resultados"]
    if len(resultados) != 1:
        raise ValueError("Esperado 1 resultado (sem classificações) na resposta do IBGE.")
    valores: dict[str, str] = {}
    for serie in resultados[0]["series"]:
        codigo_localidade = serie["localidade"]["id"]
        valores[codigo_localidade] = serie["serie"][PERIODO]
    return valores


def processar_populacao() -> pd.DataFrame:
    """Baixa, confere e grava a população estimada por município.

    Returns:
        Tabela com `cd_municipio_ibge` (texto, 7 dígitos) e `populacao` (inteiro).

    Raises:
        ValueError: Se faltar município, houver valor vazio ou a soma não fechar com o Brasil.
    """
    PASTA_BRUTOS.mkdir(parents=True, exist_ok=True)
    brasil = extrair_series(
        baixar_json(montar_url("N1"), PASTA_BRUTOS / f"estimativa_{PERIODO}_brasil.json")
    )
    municipios = extrair_series(
        baixar_json(montar_url("N6"), PASTA_BRUTOS / f"estimativa_{PERIODO}_municipios.json")
    )

    if len(municipios) < MINIMO_MUNICIPIOS:
        raise ValueError(f"IBGE devolveu {len(municipios)} municípios; esperado ≥ {MINIMO_MUNICIPIOS}.")

    registros: list[dict[str, object]] = []
    for codigo_municipio, valor in municipios.items():
        if not str(valor).isdigit():
            raise ValueError(f"População vazia ou inválida no município {codigo_municipio}: {valor!r}.")
        registros.append({"cd_municipio_ibge": codigo_municipio, "populacao": int(valor)})
    populacao = pd.DataFrame(registros).sort_values("cd_municipio_ibge")

    total_brasil = int(brasil["1"])
    soma_municipios = int(populacao["populacao"].sum())
    if soma_municipios != total_brasil:
        raise ValueError(f"Soma dos municípios {soma_municipios} ≠ total do Brasil {total_brasil}.")

    populacao.to_csv(CAMINHO_SAIDA, sep=";", index=False)
    LOGGER.info(
        "População %s: %d municípios, soma %d = total do Brasil. Gravado %s.",
        PERIODO,
        len(populacao),
        soma_municipios,
        CAMINHO_SAIDA,
    )
    return populacao


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    processar_populacao()
