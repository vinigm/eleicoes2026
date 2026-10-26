"""Teste de recuperação sintética do método por UF (seção 7 da especificação).

Uso:

    python3 -I teste_sintetico.py [--sementes-extras 5] [--replicas 300]

Com o X real e Y_i ~ Multinomial(aptos_1t_i, X_i beta_verdadeiro_u), compara o
erro médio absoluto de beta nas linhas caiado, cury e renan (ponderado por
N_u[r]) entre (a) UF com kappa escolhido por validação cruzada nos dados
sintéticos, (b) UF_SOZINHO e (c) UF_REGIAO. Escreve teste_sintetico.md.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
import time
from pathlib import Path

PASTA_SAIDA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_SAIDA))

import numpy as np  # noqa: E402

import migracao_uf_b as mig  # noqa: E402

LOGGER = logging.getLogger("sintetico_uf_b")

AMPLITUDE_PERTURBACAO = 0.15
LINHAS_PERTURBADAS = ["caiado", "cury", "renan"]
NUMERO_REPLICAS_COBERTURA = 300
NUMERO_SEMENTES_EXTRAS = 5

# Matriz T1 da especificação regional (seção 9): linhas = origens, colunas = destinos.
BETA_REGIAO_T1 = np.array(
    [
        [0.95, 0.02, 0.01, 0.02],
        [0.02, 0.95, 0.01, 0.02],
        [0.40, 0.35, 0.10, 0.15],
        [0.15, 0.65, 0.10, 0.10],
        [0.35, 0.45, 0.10, 0.10],
        [0.30, 0.40, 0.15, 0.15],
        [0.20, 0.15, 0.45, 0.20],
        [0.08, 0.05, 0.02, 0.85],
    ]
)


@dataclasses.dataclass(frozen=True)
class ResultadoSemente:
    """Resultado do teste sintético para uma semente.

    Attributes:
        semente: Semente do sorteio.
        kappa_otimo: kappa escolhido pela validação cruzada nos dados sintéticos.
        erro_a: Erro médio absoluto ponderado de UF (kappa*).
        erro_b: Idem, UF_SOZINHO.
        erro_c: Idem, UF_REGIAO.
        erro_regiao_verdadeira: Erro de usar a própria matriz T1 como beta de
            todos os estados (referência: o "oráculo da região").
        erro_por_linha: Erro (a), (b), (c) por linha-alvo.
        kkt_maximo: Maior violação KKT entre os ajustes pontuais e da CV.
        beta_verdadeiro: (27, 8, 4).
        beta_principal: (27, 8, 4), beta estimado de UF.
    """

    semente: int
    kappa_otimo: float
    erro_a: float
    erro_b: float
    erro_c: float
    erro_regiao_verdadeira: float
    erro_por_linha: dict[str, tuple[float, float, float]]
    kkt_maximo: float
    beta_verdadeiro: np.ndarray
    beta_principal: np.ndarray


def montar_beta_verdadeiro_por_uf(
    numero_ufs: int, gerador: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """beta_u = T1 + perturbação delta_u (lula +delta, flavio -delta) nas linhas-alvo.

    delta_u ~ Uniforme[-0,15; +0,15], um por UF, igual para as três linhas. Os
    valores são recortados em [0, 1]; com T1 e essa amplitude o recorte nunca
    atua (menor valor = 0,15 - 0,15 = 0), de modo que cada linha segue no simplex.
    """
    deltas = gerador.uniform(-AMPLITUDE_PERTURBACAO, AMPLITUDE_PERTURBACAO, size=numero_ufs)
    beta_por_uf = np.tile(BETA_REGIAO_T1, (numero_ufs, 1, 1))
    destino_lula = mig.DESTINOS.index("lula")
    destino_flavio = mig.DESTINOS.index("flavio")
    for nome_linha in LINHAS_PERTURBADAS:
        posicao_linha = mig.ORIGENS.index(nome_linha)
        beta_por_uf[:, posicao_linha, destino_lula] += deltas
        beta_por_uf[:, posicao_linha, destino_flavio] -= deltas
    beta_por_uf = np.clip(beta_por_uf, 0.0, 1.0)
    soma_linhas = beta_por_uf.sum(axis=2)
    if not np.allclose(soma_linhas, 1.0, atol=1e-12):
        raise ValueError("Perturbação tirou alguma linha do simplex.")
    return beta_por_uf, deltas


def sortear_destino_sintetico(
    dados: mig.DadosUf,
    beta_por_uf: np.ndarray,
    gerador: np.random.Generator,
) -> np.ndarray:
    """Y_i = contagens / aptos_1t, com contagens ~ Multinomial(aptos_1t_i, X_i beta_u(i))."""
    probabilidades = np.einsum("nk,nkc->nc", dados.x, beta_por_uf[dados.indice_uf])
    probabilidades = probabilidades / probabilidades.sum(axis=1, keepdims=True)
    tentativas = dados.peso.astype(np.int64)
    contagens = gerador.multinomial(tentativas, probabilidades)
    return contagens / dados.peso[:, None]


def erro_medio_absoluto_ponderado(
    beta_estimado: np.ndarray,
    beta_verdadeiro: np.ndarray,
    populacao_uf: np.ndarray,
    linhas: list[str],
) -> float:
    """Média dos |erro| nas 4 colunas, ponderada por N_u[r], sobre UFs e linhas dadas."""
    posicoes = [mig.ORIGENS.index(nome) for nome in linhas]
    erro_absoluto = np.abs(beta_estimado - beta_verdadeiro)[:, posicoes, :]
    erro_medio_coluna = erro_absoluto.mean(axis=2)
    pesos = populacao_uf[:, posicoes]
    return float((erro_medio_coluna * pesos).sum() / pesos.sum())


def rodar_uma_semente(
    dados: mig.DadosUf,
    populacao_uf: np.ndarray,
    semente: int,
) -> ResultadoSemente:
    """Sorteia Y, escolhe kappa por CV nos dados sintéticos e compara (a), (b), (c)."""
    gerador = np.random.default_rng(semente)
    numero_ufs = len(dados.ufs)
    beta_verdadeiro, _ = montar_beta_verdadeiro_por_uf(numero_ufs, gerador)
    y_sintetico = sortear_destino_sintetico(dados, beta_verdadeiro, gerador)
    dados_sinteticos = mig.substituir_destino(dados, y_sintetico)
    momentos = mig.montar_momentos(dados_sinteticos)

    validacao = mig.validar_cruzado(dados_sinteticos, momentos)
    kappa_otimo = mig.escolher_kappa_otimo(validacao)
    ajuste_a = mig.ajustar_ufs(dados_sinteticos, momentos, kappa_otimo)
    ajuste_b = mig.ajustar_ufs(dados_sinteticos, momentos, mig.KAPPA_SOZINHO)
    ajuste_c = mig.ajustar_ufs(dados_sinteticos, momentos, mig.KAPPA_REGIAO)

    erro_a = erro_medio_absoluto_ponderado(
        ajuste_a.beta, beta_verdadeiro, populacao_uf, LINHAS_PERTURBADAS
    )
    erro_b = erro_medio_absoluto_ponderado(
        ajuste_b.beta, beta_verdadeiro, populacao_uf, LINHAS_PERTURBADAS
    )
    erro_c = erro_medio_absoluto_ponderado(
        ajuste_c.beta, beta_verdadeiro, populacao_uf, LINHAS_PERTURBADAS
    )
    beta_regiao_verdadeira = np.tile(BETA_REGIAO_T1, (numero_ufs, 1, 1))
    erro_oraculo = erro_medio_absoluto_ponderado(
        beta_regiao_verdadeira, beta_verdadeiro, populacao_uf, LINHAS_PERTURBADAS
    )

    erro_por_linha: dict[str, tuple[float, float, float]] = {}
    for nome_linha in LINHAS_PERTURBADAS:
        valor_a = erro_medio_absoluto_ponderado(
            ajuste_a.beta, beta_verdadeiro, populacao_uf, [nome_linha]
        )
        valor_b = erro_medio_absoluto_ponderado(
            ajuste_b.beta, beta_verdadeiro, populacao_uf, [nome_linha]
        )
        valor_c = erro_medio_absoluto_ponderado(
            ajuste_c.beta, beta_verdadeiro, populacao_uf, [nome_linha]
        )
        erro_por_linha[nome_linha] = (valor_a, valor_b, valor_c)

    kkt_maximo = max(
        validacao.violacao_kkt_maxima,
        float(ajuste_a.violacao_kkt.max()),
        float(ajuste_b.violacao_kkt.max()),
        float(ajuste_c.violacao_kkt.max()),
    )
    LOGGER.info(
        "Semente %d: kappa*=%g | erro a=%.5f b=%.5f c=%.5f oraculo-regiao=%.5f | KKT %.2e",
        semente,
        kappa_otimo,
        erro_a,
        erro_b,
        erro_c,
        erro_oraculo,
        kkt_maximo,
    )
    return ResultadoSemente(
        semente=semente,
        kappa_otimo=kappa_otimo,
        erro_a=erro_a,
        erro_b=erro_b,
        erro_c=erro_c,
        erro_regiao_verdadeira=erro_oraculo,
        erro_por_linha=erro_por_linha,
        kkt_maximo=kkt_maximo,
        beta_verdadeiro=beta_verdadeiro,
        beta_principal=ajuste_a.beta,
    )


def medir_cobertura_bootstrap(
    dados: mig.DadosUf,
    resultado: ResultadoSemente,
    numero_replicas: int,
) -> dict[str, float]:
    """Cobertura do IC 95% do bootstrap (kappa fixo) para beta_verdadeiro nas linhas-alvo.

    Refaz o mesmo sorteio da semente, roda o bootstrap em UF e conta em quantas
    células (27 UFs x 3 linhas x 4 colunas) o beta verdadeiro cai dentro do IC.
    """
    gerador = np.random.default_rng(resultado.semente)
    beta_verdadeiro, _ = montar_beta_verdadeiro_por_uf(len(dados.ufs), gerador)
    y_sintetico = sortear_destino_sintetico(dados, beta_verdadeiro, gerador)
    dados_sinteticos = mig.substituir_destino(dados, y_sintetico)
    momentos = mig.montar_momentos(dados_sinteticos)
    n_efetivo = mig.calcular_kish_por_uf(dados_sinteticos)
    bootstrap = mig.executar_bootstrap(
        dados_sinteticos,
        momentos,
        resultado.kappa_otimo,
        resultado.beta_principal,
        n_efetivo,
        numero_replicas,
    )
    inferior = np.percentile(bootstrap.beta, 2.5, axis=1)
    superior = np.percentile(bootstrap.beta, 97.5, axis=1)
    posicoes = [mig.ORIGENS.index(nome) for nome in LINHAS_PERTURBADAS]
    dentro = (beta_verdadeiro >= inferior) & (beta_verdadeiro <= superior)
    cobertura_linhas_alvo = float(dentro[:, posicoes, :].mean())
    cobertura_todas = float(dentro.mean())
    destino_lula = mig.DESTINOS.index("lula")
    destino_flavio = mig.DESTINOS.index("flavio")
    cobertura_lula_flavio = float(dentro[:, posicoes, :][:, :, [destino_lula, destino_flavio]].mean())
    return {
        "cobertura_linhas_alvo": cobertura_linhas_alvo,
        "cobertura_todas_celulas": cobertura_todas,
        "cobertura_colunas_lula_flavio_linhas_alvo": cobertura_lula_flavio,
        "kkt_bootstrap": bootstrap.violacao_kkt_maxima,
    }


def escrever_relatorio(
    caminho: Path,
    resultados: list[ResultadoSemente],
    cobertura: dict[str, float],
    numero_replicas: int,
) -> None:
    """Escreve teste_sintetico.md."""
    principal = resultados[0]
    linhas: list[str] = []
    linhas.append("# Teste sintético do método por UF (implementação B)\n")
    linhas.append(
        "X real; `Y_i ~ Multinomial(aptos_1t_i, X_i beta_u)` e `Y_i = contagens/aptos_1t_i`. "
        "`beta_regiao` = T1 da especificação regional (igual em todas as regiões). "
        "`beta_u` = T1 com `lula += delta_u`, `flavio -= delta_u` nas linhas caiado, cury e renan, "
        "`delta_u ~ U[-0,15; +0,15]` (um por UF, UFs em ordem alfabética). "
        "Erro = média dos |beta_estimado - beta_verdadeiro| nas 4 colunas, ponderada por `N_u[r]` "
        "sobre as 27 UFs e as 3 linhas.\n"
    )
    linhas.append(f"## Semente principal {principal.semente}\n")
    linhas.append("| versão | erro médio absoluto ponderado |")
    linhas.append("|---|---|")
    linhas.append(f"| (a) UF, kappa* = {principal.kappa_otimo:g} (CV nos dados sintéticos) | **{principal.erro_a:.5f}** |")
    linhas.append(f"| (b) UF_SOZINHO (kappa = 0,25) | **{principal.erro_b:.5f}** |")
    linhas.append(f"| (c) UF_REGIAO (kappa = inf) | **{principal.erro_c:.5f}** |")
    linhas.append(f"| referência: usar a T1 exata da região em todas as UFs | {principal.erro_regiao_verdadeira:.5f} |")
    veredito = "SIM" if principal.erro_a <= min(principal.erro_b, principal.erro_c) else "NÃO"
    linhas.append(f"\n**Esperado (a) <= min((b), (c)): {veredito}.** KKT máximo (CV + ajustes): {principal.kkt_maximo:.2e}.\n")
    linhas.append("Erro por linha (a / b / c):\n")
    linhas.append("| linha | (a) | (b) | (c) |")
    linhas.append("|---|---|---|---|")
    for nome_linha, (valor_a, valor_b, valor_c) in principal.erro_por_linha.items():
        linhas.append(f"| {nome_linha} | {valor_a:.5f} | {valor_b:.5f} | {valor_c:.5f} |")

    linhas.append("\n## Robustez (outras sementes, mesmo procedimento)\n")
    linhas.append("| semente | kappa* | (a) | (b) | (c) | (a) <= min(b, c)? |")
    linhas.append("|---|---|---|---|---|---|")
    vitorias = 0
    for resultado in resultados:
        passou = resultado.erro_a <= min(resultado.erro_b, resultado.erro_c)
        vitorias += int(passou)
        linhas.append(
            f"| {resultado.semente} | {resultado.kappa_otimo:g} | {resultado.erro_a:.5f} | "
            f"{resultado.erro_b:.5f} | {resultado.erro_c:.5f} | {'sim' if passou else 'NÃO'} |"
        )
    linhas.append(f"\n(a) <= min((b), (c)) em {vitorias} de {len(resultados)} sementes.\n")

    linhas.append(f"## Cobertura do IC do bootstrap (semente {principal.semente}, B = {numero_replicas}, kappa fixo)\n")
    linhas.append(
        f"- beta verdadeiro dentro do IC 95%: **{100 * cobertura['cobertura_linhas_alvo']:.1f}%** das células "
        f"das linhas caiado/cury/renan; {100 * cobertura['cobertura_colunas_lula_flavio_linhas_alvo']:.1f}% "
        f"nas colunas lula/flavio dessas linhas; {100 * cobertura['cobertura_todas_celulas']:.1f}% em todas as 32 células.\n"
        "- O IC mede só variabilidade amostral; o viés de encolhimento para a região não entra."
    )
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def principal(numero_sementes_extras: int, numero_replicas: int) -> None:
    """Roda a semente principal, as extras e a cobertura do bootstrap."""
    inicio = time.time()
    base = mig.carregar_base_brasil()
    dados, contagens_destino, aptos_2t = mig.montar_dados_uf(base)
    mig.validar_ancoras_uf(dados, contagens_destino, aptos_2t)
    populacao_uf = mig.calcular_populacao_origem_uf(dados)

    resultados: list[ResultadoSemente] = []
    for deslocamento in range(numero_sementes_extras + 1):
        semente = mig.SEMENTE_PADRAO + deslocamento
        resultados.append(rodar_uma_semente(dados, populacao_uf, semente))

    cobertura = medir_cobertura_bootstrap(dados, resultados[0], numero_replicas)
    LOGGER.info("Cobertura: %s", cobertura)
    escrever_relatorio(PASTA_SAIDA / "teste_sintetico.md", resultados, cobertura, numero_replicas)
    LOGGER.info("Tempo total: %.1f s.", time.time() - inicio)


def interpretar_argumentos() -> argparse.Namespace:
    """Lê --sementes-extras e --replicas."""
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--sementes-extras", type=int, default=NUMERO_SEMENTES_EXTRAS)
    analisador.add_argument("--replicas", type=int, default=NUMERO_REPLICAS_COBERTURA)
    return analisador.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    argumentos = interpretar_argumentos()
    principal(argumentos.sementes_extras, argumentos.replicas)
