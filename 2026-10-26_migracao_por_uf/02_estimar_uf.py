"""Estimativa da migração de votos por estado (UF, UF_SOZINHO, UF_REGIAO) + bootstrap.

Pré-requisito: `01_validacao_cruzada.py` (gera `curva_validacao_cruzada.csv`, de onde
sai kappa*). Valida as âncoras (PARA se alguma divergir), estima as três versões,
roda o bootstrap (B = 500, semente 20261025) da versão UF e grava:

    transferencias_uf.csv   (2.592 linhas)
    diagnosticos.md

Uso: python3 -I 02_estimar_uf.py
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# `-I` remove a pasta do script do sys.path; ela é reinserida para achar os módulos locais.
PASTA_TRABALHO = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_TRABALHO))

import nucleo_uf as nucleo  # noqa: E402
import saidas_uf as saidas  # noqa: E402

LOGGER = logging.getLogger("02_estimar_uf")

DATA_CRIACAO = "26/10/2026"
CAMINHO_CURVA_CSV = PASTA_TRABALHO / saidas.NOME_CURVA_CSV
CAMINHO_CURVA_POR_UF_CSV = PASTA_TRABALHO / saidas.NOME_CURVA_POR_UF_CSV
CAMINHO_TRANSFERENCIAS_CSV = PASTA_TRABALHO / "transferencias_uf.csv"
CAMINHO_DIAGNOSTICOS_MD = PASTA_TRABALHO / "diagnosticos.md"


def configurar_logging() -> None:
    """Configura o log no formato `hora nível mensagem`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def ler_tabela_gerada_pelo_script_01(caminho: Path) -> pd.DataFrame:
    """Lê um CSV produzido por `01_validacao_cruzada.py`.

    Raises:
        FileNotFoundError: Se o script 01 ainda não foi executado.
    """
    if not caminho.is_file():
        raise FileNotFoundError(f"{caminho.name} não encontrado: rode 01_validacao_cruzada.py antes.")

    return pd.read_csv(caminho, sep=";", encoding="utf-8")


def calcular_diferencas_de_ponto_inicial(
    base: nucleo.BaseUF,
    estimativas: dict[str, nucleo.EstimativaVersao],
) -> dict[str, float]:
    """Reajusta cada versão a partir de outro ponto inicial e mede o maior |delta beta|.

    UF e UF_SOZINHO foram estimadas a partir do beta de UF_REGIAO; são reajustadas
    do ponto uniforme. UF_REGIAO foi estimada do ponto uniforme; é reajustada a
    partir do beta de UF.
    """
    estimativa_regiao = estimativas[nucleo.CODIGO_UF_REGIAO]
    estimativa_uf = estimativas[nucleo.CODIGO_UF]

    diferencas: dict[str, float] = {}
    diferencas[nucleo.CODIGO_UF] = nucleo.medir_diferenca_por_ponto_inicial(
        base,
        estimativa_uf,
        None,
    )
    diferencas[nucleo.CODIGO_UF_SOZINHO] = nucleo.medir_diferenca_por_ponto_inicial(
        base,
        estimativas[nucleo.CODIGO_UF_SOZINHO],
        None,
    )
    diferencas[nucleo.CODIGO_UF_REGIAO] = nucleo.medir_diferenca_por_ponto_inicial(
        base,
        estimativa_regiao,
        estimativa_uf.betas,
    )
    return diferencas


def main() -> None:
    """Estima as três versões, roda o bootstrap e grava os CSV/MD de saída."""
    configurar_logging()
    instante_inicial = time.perf_counter()

    municipios = nucleo.carregar_municipios_brasileiros(nucleo.CAMINHO_BASE_PARQUET)
    base = nucleo.montar_base_uf(municipios)
    nucleo.exigir_ancoras_por_uf(base)

    tabela_curva = ler_tabela_gerada_pelo_script_01(CAMINHO_CURVA_CSV)
    tabela_curva_por_uf = ler_tabela_gerada_pelo_script_01(CAMINHO_CURVA_POR_UF_CSV)
    kappa_estrela, kappa_na_borda = saidas.ler_kappa_estrela_da_curva(tabela_curva)
    ufs_de_um_municipio = saidas.listar_ufs_de_um_municipio(base)
    ufs_piores = saidas.listar_ufs_piores_que_a_regiao(
        tabela_curva_por_uf,
        kappa_estrela,
        ufs_de_um_municipio,
    )
    LOGGER.info("kappa* lido da curva: %s (borda da grade: %s).", kappa_estrela, kappa_na_borda)

    # UF_REGIAO primeiro: seu beta serve de ponto inicial (só velocidade; o ótimo é único).
    estimativa_regiao = nucleo.estimar_versao(
        base,
        nucleo.CODIGO_UF_REGIAO,
        nucleo.KAPPA_REGIAO,
        None,
    )
    estimativa_sozinho = nucleo.estimar_versao(
        base,
        nucleo.CODIGO_UF_SOZINHO,
        nucleo.KAPPA_SOZINHO,
        estimativa_regiao.betas,
    )
    estimativa_uf = nucleo.estimar_versao(
        base,
        nucleo.CODIGO_UF,
        kappa_estrela,
        estimativa_regiao.betas,
    )
    estimativas = {
        nucleo.CODIGO_UF: estimativa_uf,
        nucleo.CODIGO_UF_SOZINHO: estimativa_sozinho,
        nucleo.CODIGO_UF_REGIAO: estimativa_regiao,
    }
    LOGGER.info("Três versões estimadas (81 ajustes, todos convergidos).")

    diferenca_ponto_inicial = calcular_diferencas_de_ponto_inicial(base, estimativas)

    gerador = np.random.default_rng(nucleo.SEMENTE_UF)
    multiplicidades = nucleo.gerar_multiplicidades_por_uf(
        base,
        nucleo.NUMERO_REPLICAS_BOOTSTRAP_UF,
        gerador,
    )
    bootstrap = nucleo.executar_bootstrap_uf(
        base,
        kappa_estrela,
        estimativa_uf.betas,
        multiplicidades,
    )
    LOGGER.info(
        "Bootstrap concluído: %d réplicas em %.1f s; maior cond(G) %.3e.",
        bootstrap.betas.shape[0],
        bootstrap.segundos,
        bootstrap.maior_numero_condicao,
    )

    intervalos = saidas.calcular_intervalos_do_bootstrap(bootstrap.betas, base.populacao_por_uf)
    tabela_transferencias = saidas.montar_tabela_transferencias(base, estimativas, intervalos)
    saidas.gravar_tabela_csv(CAMINHO_TRANSFERENCIAS_CSV, tabela_transferencias)

    betas_e1 = nucleo.carregar_betas_e1(nucleo.CAMINHO_TRANSFERENCIAS_E1)
    diferencas_e1: dict[str, pd.DataFrame] = {}
    for codigo in nucleo.CODIGOS_VERSOES:
        diferencas_e1[codigo] = nucleo.calcular_diferencas_para_e1(
            base,
            estimativas[codigo].votos,
            betas_e1,
        )

    resultados = saidas.ResultadosEstimacao(
        base=base,
        kappa_estrela=kappa_estrela,
        kappa_na_borda=kappa_na_borda,
        estimativas=estimativas,
        bootstrap=bootstrap,
        semente=nucleo.SEMENTE_UF,
        diferencas_e1=diferencas_e1,
        diferenca_ponto_inicial=diferenca_ponto_inicial,
        ufs_piores_que_regiao=ufs_piores,
    )
    texto_diagnosticos = saidas.montar_texto_diagnosticos(resultados, DATA_CRIACAO)
    saidas.gravar_texto(CAMINHO_DIAGNOSTICOS_MD, texto_diagnosticos)

    LOGGER.info("Tempo total: %.1f s.", time.perf_counter() - instante_inicial)


if __name__ == "__main__":
    main()
