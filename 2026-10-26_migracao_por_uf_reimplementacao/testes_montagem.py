"""Testes de montagem do QP e consistência com o E1 da reimplementação regional B.

Uso:

    python3 -I testes_montagem.py

1. O objetivo J_u calculado direto dos municípios (laço, fórmula da
   especificação) deve igualar (1 + kappa/n_u) vezes o objetivo montado a partir
   de G, H e da constante normalizados (para UFs, kappas e betas aleatórios).
2. O E1 refeito aqui deve coincidir com o E1 gravado pela reimplementação
   regional B (``transferencias.csv`` daquela pasta, que é do mesmo autor).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PASTA_SAIDA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_SAIDA))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import migracao_uf_b as mig  # noqa: E402

LOGGER = logging.getLogger("testes_montagem")
UFS_TESTADAS = ["DF", "RR", "GO", "SP", "MG"]
KAPPAS_TESTADOS = [0.25, 4.0, 256.0]
SEMENTE_TESTE = 7


def erro_ponderado_direto(dados: mig.DadosUf, indices: np.ndarray, beta: np.ndarray) -> float:
    """sum_i w_i ||Y_i - X_i beta||^2 por laço sobre os municípios dados."""
    soma = 0.0
    for indice in indices:
        residuo = dados.y[indice] - dados.x[indice] @ beta
        soma += dados.peso[indice] * float(residuo @ residuo)
    return soma


def objetivo_direto(dados: mig.DadosUf, posicao_uf: int, kappa: float, n_u: float, beta: np.ndarray) -> float:
    """J_u(beta) exatamente como na seção 2 da especificação, sem estatísticas suficientes."""
    regiao = dados.regiao_da_uf[posicao_uf]
    posicoes_irmas = [
        p for p, r in enumerate(dados.regiao_da_uf) if r == regiao and p != posicao_uf
    ]
    indices_uf = np.flatnonzero(dados.indice_uf == posicao_uf)
    indices_irmas = np.flatnonzero(np.isin(dados.indice_uf, posicoes_irmas))
    termo_estado = erro_ponderado_direto(dados, indices_uf, beta) / dados.peso[indices_uf].sum()
    termo_regiao = erro_ponderado_direto(dados, indices_irmas, beta) / dados.peso[indices_irmas].sum()
    return termo_estado + (kappa / n_u) * termo_regiao


def main() -> None:
    """Executa os dois testes e levanta AssertionError se algum falhar."""
    base = mig.carregar_base_brasil()
    dados, contagens_destino, aptos_2t = mig.montar_dados_uf(base)
    mig.validar_ancoras_uf(dados, contagens_destino, aptos_2t)
    momentos = mig.montar_momentos(dados)
    n_efetivo = mig.calcular_kish_por_uf(dados)
    momentos_por_uf = mig.somar_momentos_por_uf(dados, momentos, np.ones(len(dados.peso)))
    gerador = np.random.default_rng(SEMENTE_TESTE)

    erro_relativo_maximo = 0.0
    for sigla in UFS_TESTADAS:
        posicao = dados.ufs.index(sigla)
        momentos_regiao = mig.soma_regiao_sem_uf(dados, momentos_por_uf, posicao)
        for kappa in KAPPAS_TESTADOS:
            g, h, constante = mig.montar_problema_qp(
                momentos_por_uf[posicao][None, :],
                momentos_regiao[None, :],
                np.array([n_efetivo[posicao]]),
                kappa,
            )
            beta_aleatorio = mig.solver_b.projetar_linhas_no_simplex(
                gerador.random((1, mig.NUMERO_ORIGENS, mig.NUMERO_DESTINOS))
            )
            via_qp = float(mig.solver_b.calcular_objetivo(g, h, constante, beta_aleatorio)[0])
            via_qp_na_escala_original = via_qp * (1.0 + kappa / n_efetivo[posicao])
            direto = objetivo_direto(dados, posicao, kappa, n_efetivo[posicao], beta_aleatorio[0])
            erro_relativo = abs(via_qp_na_escala_original - direto) / abs(direto)
            erro_relativo_maximo = max(erro_relativo_maximo, erro_relativo)
            LOGGER.info(
                "%s kappa=%g: direto=%.10e via QP=%.10e erro rel=%.2e",
                sigla, kappa, direto, via_qp_na_escala_original, erro_relativo,
            )
    assert erro_relativo_maximo < 1e-9, erro_relativo_maximo
    LOGGER.info("Teste 1 (montagem de G, H e constante): OK, erro relativo máx %.2e.", erro_relativo_maximo)

    beta_regioes, kkt, _ = mig.ajustar_regioes_e1(dados, momentos)
    caminho_b = mig.RAIZ_PROJETO / "2026-10-26_inferencia_ecologica_reimplementacao" / "transferencias.csv"
    tabela_b = pd.read_csv(caminho_b, sep=";")
    e1 = tabela_b[tabela_b["especificacao"] == "E1"]
    diferenca_maxima = 0.0
    for posicao_regiao, nome_regiao in enumerate(mig.REGIOES):
        for posicao_origem, origem in enumerate(mig.ORIGENS):
            for posicao_destino, destino in enumerate(mig.DESTINOS):
                mascara = (
                    (e1["regiao"] == nome_regiao)
                    & (e1["origem_1t"] == origem)
                    & (e1["destino_2t"] == destino)
                )
                valor_b = float(e1.loc[mascara, "beta"].iloc[0])
                valor_aqui = float(beta_regioes[posicao_regiao, posicao_origem, posicao_destino])
                diferenca_maxima = max(diferenca_maxima, abs(valor_b - valor_aqui))
    LOGGER.info("Teste 2 (E1 aqui vs E1 da regional B): diferença máx em beta = %.2e.", diferenca_maxima)
    assert diferenca_maxima < 1e-6, diferenca_maxima
    LOGGER.info("TESTES OK.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
