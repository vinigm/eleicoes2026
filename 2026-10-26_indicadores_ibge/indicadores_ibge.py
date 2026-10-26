"""Baixa e confere indicadores socioeconômicos por município (IBGE).

Contexto:
    A seção "Cidades" do HTML ganha uma dispersão "índice × voto" por região,
    a pedido do Vinicius. Os índices são de condições socioeconômicas (acesso a
    estudo e renda), não de "inteligência", e a relação por cidade não descreve
    o voto de cada eleitor (falácia ecológica). Isso fica dito no HTML.

Indicadores (API de agregados do IBGE):
    * Taxa de alfabetização das pessoas de 15 anos ou mais, Censo 2022
      (tabela 9543, variável 2513), total de sexo, cor ou raça e idade.
    * PIB a preços correntes de 2023, em mil reais (tabela 5938, variável 37).
    * População estimada de 2024 (tabela 6579, variável 9324), denominador do
      PIB per capita. A tabela não tem estimativa de 2023.

Saída:
    dados/processados/indicadores_municipios_ibge.csv
    (cd_municipio_ibge; alfabetizacao_15mais_2022; pib_2023_mil_reais;
     populacao_2024; pib_per_capita_2023)

Execução (dados baixados são não confiáveis; modo isolado):
    python3 -I 2026-10-26_indicadores_ibge/indicadores_ibge.py
"""

import json
import logging
import pathlib
import subprocess

import pandas as pd

LOGGER = logging.getLogger(__name__)

RAIZ_PROJETO = pathlib.Path(__file__).resolve().parent.parent
PASTA_BRUTOS = RAIZ_PROJETO / "dados" / "ibge"
CAMINHO_SAIDA = RAIZ_PROJETO / "dados" / "processados" / "indicadores_municipios_ibge.csv"

URL_BASE = "https://servicodados.ibge.gov.br/api/v3/agregados"
TEMPO_LIMITE_SEGUNDOS = 300
MINIMO_MUNICIPIOS = 5570
# Totais das classificações da tabela 9543: sexo, cor ou raça e idade (15 anos ou mais).
CLASSIFICACAO_ALFABETIZACAO_TOTAL = "2%5B6794%5D%7C86%5B95251%5D%7C287%5B100362%5D"

# Municípios que existem na lista do IBGE, mas não no Censo 2022, no PIB 2023 nem na
# estimativa de 2024 (esta traz "..."). Ficam vazios, sem imputação. Qualquer outro ausente é erro.
MUNICIPIOS_SEM_INDICADORES = {"5101837": "Boa Esperança do Norte (MT), criado depois do Censo 2022"}

CONSULTAS = {
    "alfabetizacao": {"agregado": "9543", "variavel": "2513", "periodo": "2022", "classificacao": CLASSIFICACAO_ALFABETIZACAO_TOTAL},
    "pib": {"agregado": "5938", "variavel": "37", "periodo": "2023", "classificacao": None},
    "populacao": {"agregado": "6579", "variavel": "9324", "periodo": "2024", "classificacao": None},
}


def montar_url(consulta: dict[str, str | None], nivel: str) -> str:
    """Monta a URL da API de agregados para um nível geográfico (N1 Brasil, N6 municípios)."""
    url = (
        f"{URL_BASE}/{consulta['agregado']}/periodos/{consulta['periodo']}"
        f"/variaveis/{consulta['variavel']}?localidades={nivel}%5Ball%5D"
    )
    if consulta["classificacao"]:
        url += f"&classificacao={consulta['classificacao']}"
    return url


def baixar_json(url: str, caminho_destino: pathlib.Path) -> object:
    """Baixa um JSON da API do IBGE (se ainda não existir) e o devolve.

    O download usa `curl`, que confia nos certificados do sistema; o Python desta
    máquina não confia na cadeia (proxy corporativo). A verificação continua ligada.
    """
    if not caminho_destino.exists():
        LOGGER.info("Baixando %s", url)
        comando = ["curl", "-sS", "--fail", "--max-time", str(TEMPO_LIMITE_SEGUNDOS), "-o", str(caminho_destino), url]
        subprocess.run(comando, check=True)
    with caminho_destino.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def extrair_valores(resposta_api: object, periodo: str) -> dict[str, str]:
    """Extrai {código da localidade: valor} da resposta da API de agregados.

    Raises:
        ValueError: Se a resposta não tiver exatamente uma série por localidade.
    """
    if not isinstance(resposta_api, list) or len(resposta_api) != 1:
        raise ValueError("Resposta da API do IBGE em formato inesperado.")
    resultados = resposta_api[0]["resultados"]
    if len(resultados) != 1:
        raise ValueError(f"Esperado 1 resultado (totais), vieram {len(resultados)}.")
    valores: dict[str, str] = {}
    for serie in resultados[0]["series"]:
        valores[serie["localidade"]["id"]] = serie["serie"][periodo]
    return valores


def baixar_indicador(nome: str) -> tuple[dict[str, str], str]:
    """Baixa o indicador para os municípios e para o Brasil.

    Returns:
        (valores por município, valor do Brasil).
    """
    consulta = CONSULTAS[nome]
    periodo = consulta["periodo"]
    municipios = extrair_valores(
        baixar_json(montar_url(consulta, "N6"), PASTA_BRUTOS / f"{nome}_{periodo}_municipios.json"), periodo
    )
    brasil = extrair_valores(
        baixar_json(montar_url(consulta, "N1"), PASTA_BRUTOS / f"{nome}_{periodo}_brasil.json"), periodo
    )
    if len(municipios) < MINIMO_MUNICIPIOS:
        raise ValueError(f"{nome}: IBGE devolveu {len(municipios)} municípios; esperado ≥ {MINIMO_MUNICIPIOS}.")
    return municipios, brasil["1"]


def converter_numero(valor: str, nome: str, codigo: str) -> float:
    """Converte o valor da API em número; símbolos do IBGE ("-", "...", "X") são erro aqui."""
    try:
        return float(valor)
    except ValueError as erro:
        raise ValueError(f"{nome}: valor não numérico no município {codigo}: {valor!r}.") from erro


def processar_indicadores() -> pd.DataFrame:
    """Baixa, confere e grava os indicadores por município.

    Conferências:
        * alfabetização entre 0 e 100 em todos os municípios;
        * soma do PIB dos municípios = PIB do Brasil na mesma tabela, a menos do arredondamento;
        * soma da população 2024 dos municípios = total do Brasil.

    Raises:
        ValueError: Se alguma conferência falhar.
    """
    PASTA_BRUTOS.mkdir(parents=True, exist_ok=True)
    alfabetizacao, alfabetizacao_brasil = baixar_indicador("alfabetizacao")
    pib, pib_brasil = baixar_indicador("pib")
    populacao, populacao_brasil = baixar_indicador("populacao")

    ausentes = sorted(set(populacao) - set(alfabetizacao) | set(populacao) - set(pib))
    if set(ausentes) != set(MUNICIPIOS_SEM_INDICADORES):
        raise ValueError(f"Municípios sem indicador diferentes do esperado: {ausentes}.")
    for codigo_ausente in ausentes:
        LOGGER.info("Sem alfabetização e PIB: %s (%s).", codigo_ausente, MUNICIPIOS_SEM_INDICADORES[codigo_ausente])

    registros: list[dict[str, object]] = []
    for codigo_municipio in sorted(populacao):
        registro: dict[str, object] = {
            "cd_municipio_ibge": codigo_municipio,
            "alfabetizacao_15mais_2022": None,
            "pib_2023_mil_reais": None,
            "populacao_2024": None,
            "pib_per_capita_2023": None,
        }
        if codigo_municipio not in MUNICIPIOS_SEM_INDICADORES:
            habitantes = converter_numero(populacao[codigo_municipio], "população", codigo_municipio)
            registro["populacao_2024"] = int(habitantes)
            taxa = converter_numero(alfabetizacao[codigo_municipio], "alfabetização", codigo_municipio)
            valor_pib = converter_numero(pib[codigo_municipio], "PIB", codigo_municipio)
            if not 0 <= taxa <= 100:
                raise ValueError(f"Alfabetização fora de 0–100 no município {codigo_municipio}: {taxa}.")
            registro["alfabetizacao_15mais_2022"] = round(taxa, 2)
            registro["pib_2023_mil_reais"] = int(valor_pib)
            registro["pib_per_capita_2023"] = int(round(1000 * valor_pib / habitantes))
        registros.append(registro)
    indicadores = pd.DataFrame(registros)
    indicadores["pib_2023_mil_reais"] = indicadores["pib_2023_mil_reais"].astype("Int64")
    indicadores["populacao_2024"] = indicadores["populacao_2024"].astype("Int64")
    indicadores["pib_per_capita_2023"] = indicadores["pib_per_capita_2023"].astype("Int64")

    soma_pib = int(indicadores["pib_2023_mil_reais"].sum())
    soma_populacao = int(indicadores["populacao_2024"].sum())
    if soma_populacao != int(float(populacao_brasil)):
        raise ValueError(f"População 2024: soma {soma_populacao} ≠ Brasil {populacao_brasil}.")
    # O IBGE publica cada município arredondado em mil reais: a soma pode diferir do Brasil em até
    # meio milhar por município. Em 2023 a diferença foi de 19 mil reais em R$ 10,9 trilhões.
    diferenca_pib = abs(soma_pib - int(float(pib_brasil)))
    tolerancia_pib = 0.5 * int(indicadores["pib_2023_mil_reais"].notna().sum())
    if diferenca_pib > tolerancia_pib:
        raise ValueError(f"PIB 2023: soma dos municípios {soma_pib} ≠ Brasil {pib_brasil} (mil R$), além do arredondamento.")
    LOGGER.info("PIB 2023: soma dos municípios difere do Brasil em %d mil R$ (arredondamento; limite %.0f).", diferenca_pib, tolerancia_pib)

    indicadores.to_csv(CAMINHO_SAIDA, sep=";", index=False)
    LOGGER.info(
        "Indicadores: %d municípios; alfabetização Brasil %s%%; PIB 2023 soma %d; população 2024 soma %d = Brasil. Gravado %s.",
        len(indicadores),
        alfabetizacao_brasil,
        soma_pib,
        soma_populacao,
        CAMINHO_SAIDA,
    )
    return indicadores


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    processar_indicadores()
