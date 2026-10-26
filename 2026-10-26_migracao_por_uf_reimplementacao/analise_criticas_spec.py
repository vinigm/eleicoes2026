"""Evidência numérica das críticas à especificação (partição das dobras e kappa*).

Uso:

    python3 -I analise_criticas_spec.py

Escreve criticas_especificacao.md. Pergunta respondida: o kappa* da validação
cruzada com `int(cd_municipio_tse) mod 5` é robusto a outra partição das
dobras? E quão desequilibrada é essa partição?
"""

from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path

PASTA_SAIDA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_SAIDA))

import numpy as np  # noqa: E402

import migracao_uf_b as mig  # noqa: E402

LOGGER = logging.getLogger("criticas_uf_b")

SEMENTES_PARTICAO_ALEATORIA = [20261025, 1, 2]


def resumir_validacao(validacao: mig.ResultadoValidacao) -> tuple[float, float, float]:
    """(kappa*, erro(kappa*), erro(inf)/erro(kappa*))."""
    kappa_otimo = mig.escolher_kappa_otimo(validacao)
    posicao = validacao.grade.index(kappa_otimo)
    erro_total = validacao.erro_total()
    return kappa_otimo, float(erro_total[posicao]), float(erro_total[-1] / erro_total[posicao])


def principal() -> None:
    """Roda a CV com partições alternativas e escreve o relatório."""
    base = mig.carregar_base_brasil()
    dados, contagens_destino, aptos_2t = mig.montar_dados_uf(base)
    mig.validar_ancoras_uf(dados, contagens_destino, aptos_2t)
    momentos = mig.montar_momentos(dados)

    linhas: list[str] = []
    linhas.append("# Evidências para as críticas à especificação (implementação B)\n")

    linhas.append("## Fração de municípios da dobra 0 por UF (`cd_municipio_tse mod 5 == 0`)\n")
    linhas.append("| UF | municípios | % na dobra 0 | % dos aptos_1t na dobra 0 |")
    linhas.append("|---|---|---|---|")
    for posicao_uf, sigla in enumerate(dados.ufs):
        mascara_uf = dados.indice_uf == posicao_uf
        mascara_dobra_zero = mascara_uf & (dados.dobra == 0)
        percentual_municipios = 100.0 * mascara_dobra_zero.sum() / mascara_uf.sum()
        percentual_peso = 100.0 * dados.peso[mascara_dobra_zero].sum() / dados.peso[mascara_uf].sum()
        linhas.append(
            f"| {sigla} | {int(mascara_uf.sum())} | {percentual_municipios:.1f} | {percentual_peso:.1f} |"
        )

    linhas.append("\n## kappa* sob partições alternativas das dobras\n")
    linhas.append("| partição | kappa* | erro(kappa*) | erro(inf)/erro(kappa*) |")
    linhas.append("|---|---|---|---|")

    validacao_original = mig.validar_cruzado(dados, momentos)
    kappa_otimo, erro_otimo, razao = resumir_validacao(validacao_original)
    linhas.append(f"| `mod 5` (especificação) | {kappa_otimo:g} | {erro_otimo:.2f} | {razao:.3f} |")

    dobra_por_divisao = (dados.codigo_tse // 5) % mig.NUMERO_DOBRAS
    dados_divisao = dataclasses.replace(dados, dobra=dobra_por_divisao)
    validacao_divisao = mig.validar_cruzado(dados_divisao, momentos)
    kappa_divisao, erro_divisao, razao_divisao = resumir_validacao(validacao_divisao)
    linhas.append(
        f"| `(cd // 5) mod 5` | {kappa_divisao:g} | {erro_divisao:.2f} | {razao_divisao:.3f} |"
    )

    for semente in SEMENTES_PARTICAO_ALEATORIA:
        gerador = np.random.default_rng(semente)
        dobra_aleatoria = gerador.integers(0, mig.NUMERO_DOBRAS, size=len(dados.peso))
        dados_aleatorios = dataclasses.replace(dados, dobra=dobra_aleatoria)
        validacao_aleatoria = mig.validar_cruzado(dados_aleatorios, momentos)
        kappa_a, erro_a, razao_a = resumir_validacao(validacao_aleatoria)
        erros = validacao_aleatoria.erro_total()
        LOGGER.info("Semente %d: curva %s", semente, np.round(erros, 1))
        linhas.append(
            f"| aleatória, semente {semente} | {kappa_a:g} | {erro_a:.2f} | {razao_a:.3f} |"
        )

    caminho = PASTA_SAIDA / "criticas_especificacao.md"
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    LOGGER.info("Gravado %s.", caminho.name)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    principal()
