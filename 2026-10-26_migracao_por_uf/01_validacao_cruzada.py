"""Validação cruzada de kappa (peso da região) para a migração de votos por estado.

Lê a base, valida as âncoras (PARA se alguma divergir), roda a validação
cruzada de 5 dobras na grade de kappa da especificação e grava:

    curva_validacao_cruzada.csv          (lida por 02_estimar_uf.py para obter kappa*)
    curva_validacao_cruzada_por_uf.csv   (erro por UF e kappa; lida por 02_estimar_uf.py)
    validacao_cruzada.md

Uso: python3 -I 01_validacao_cruzada.py
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np

# `-I` remove a pasta do script do sys.path; ela é reinserida para achar os módulos locais.
PASTA_TRABALHO = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_TRABALHO))

import nucleo_uf as nucleo  # noqa: E402
import saidas_uf as saidas  # noqa: E402

LOGGER = logging.getLogger("01_validacao_cruzada")

DATA_CRIACAO = "26/10/2026"
CAMINHO_CURVA_CSV = PASTA_TRABALHO / saidas.NOME_CURVA_CSV
CAMINHO_CURVA_POR_UF_CSV = PASTA_TRABALHO / saidas.NOME_CURVA_POR_UF_CSV
CAMINHO_VALIDACAO_MD = PASTA_TRABALHO / "validacao_cruzada.md"


def configurar_logging() -> None:
    """Configura o log no formato `hora nível mensagem`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    """Executa a validação cruzada e grava a curva e o relatório."""
    configurar_logging()
    instante_inicial = time.perf_counter()

    municipios = nucleo.carregar_municipios_brasileiros(nucleo.CAMINHO_BASE_PARQUET)
    base = nucleo.montar_base_uf(municipios)
    nucleo.exigir_ancoras_por_uf(base)

    resultado_cv = nucleo.executar_validacao_cruzada(
        base,
        nucleo.KAPPAS_GRADE,
        nucleo.NUMERO_DOBRAS,
    )

    multiplicidade_cheia = np.ones(base.dados.aptos_1t.shape[0])
    estatisticas = nucleo.calcular_estatisticas_por_uf(base, multiplicidade_cheia)
    n_efetivo_por_uf = nucleo.calcular_n_efetivo_kish(
        estatisticas.soma_pesos,
        estatisticas.soma_quadrados_dos_pesos,
    )

    tabela_curva = saidas.montar_tabela_curva_cv(resultado_cv)
    saidas.gravar_tabela_csv(CAMINHO_CURVA_CSV, tabela_curva)

    tabela_curva_por_uf = saidas.montar_tabela_cv_por_uf(base, resultado_cv)
    saidas.gravar_tabela_csv(CAMINHO_CURVA_POR_UF_CSV, tabela_curva_por_uf)

    texto = saidas.montar_texto_validacao_cruzada(
        base,
        resultado_cv,
        n_efetivo_por_uf,
        DATA_CRIACAO,
    )
    saidas.gravar_texto(CAMINHO_VALIDACAO_MD, texto)

    LOGGER.info(
        "kappa* = %s (borda da grade: %s); erro em kappa*: %.1f; em 0,25: %.1f; em infinito: %.1f.",
        resultado_cv.kappa_otimo,
        resultado_cv.na_borda_da_grade,
        float(resultado_cv.erro_por_kappa[resultado_cv.posicao_kappa_otimo]),
        float(resultado_cv.erro_por_kappa[0]),
        resultado_cv.erro_regiao,
    )
    LOGGER.info("Tempo total: %.1f s.", time.perf_counter() - instante_inicial)


if __name__ == "__main__":
    main()
