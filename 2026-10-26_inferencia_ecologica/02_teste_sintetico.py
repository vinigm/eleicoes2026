"""Teste de recuperação sintética (T1 e T2) da implementação de E1 e E2.

Com o X real, sorteia Y_i ~ Multinomial(aptos_1t_i, X_i · beta_verdadeiro),
semente 20261025, e verifica se E1 e E2 recuperam o beta verdadeiro.

    T1: beta constante no país (E1 e E2 devem recuperar).
    T2: beta de Caiado difere no Centro-Oeste (E1 deve recuperar; E2 enviesa).

Em dados sintéticos, Y é a contagem sorteada dividida por aptos_1t (o mesmo
denominador de X), de modo que a identidade 'linha soma 1' vale exatamente.

Uso:
    python3 -I 02_teste_sintetico.py
"""

import dataclasses
import logging
import sys
import time
from pathlib import Path

import numpy as np

PASTA_TRABALHO = Path(__file__).resolve().parent
# `python3 -I` remove a pasta do script do sys.path; este insert é explícito
# e restrito à pasta onde estão os módulos deste projeto.
sys.path.insert(0, str(PASTA_TRABALHO))

import nucleo_inferencia as nucleo  # noqa: E402
import saidas_inferencia as saidas  # noqa: E402

LOGGER = logging.getLogger("teste_sintetico")

CAMINHO_BASE = (
    PASTA_TRABALHO.parent / "dados" / "processados" / "presidente_municipio_turnos.parquet"
)
CAMINHO_RELATORIO = PASTA_TRABALHO / "teste_sintetico.md"
CODIFICACAO_SAIDA = "utf-8"

NUMERO_SORTEIOS_COMPLEMENTARES = 20
SEMENTE_PRIMEIRO_SORTEIO_COMPLEMENTAR = nucleo.SEMENTE_PADRAO + 1

# beta verdadeiro do T1 (ESPECIFICACAO.md, seção 9). Linhas = ORIGENS_1T,
# colunas = DESTINOS_2T (lula, flavio, branco_nulo, abstencao).
BETA_VERDADEIRO_T1 = np.array(
    [
        [0.95, 0.02, 0.01, 0.02],  # lula
        [0.02, 0.95, 0.01, 0.02],  # flavio
        [0.40, 0.35, 0.10, 0.15],  # cury
        [0.15, 0.65, 0.10, 0.10],  # renan
        [0.35, 0.45, 0.10, 0.10],  # caiado
        [0.30, 0.40, 0.15, 0.15],  # demais
        [0.20, 0.15, 0.45, 0.20],  # branco_nulo
        [0.08, 0.05, 0.02, 0.85],  # abstencao
    ]
)
REGIAO_CAIADO_DIFERENTE_T2 = "Centro-Oeste"
LINHA_CAIADO_CENTRO_OESTE_T2 = np.array([0.55, 0.30, 0.08, 0.07])
LINHA_CAIADO_DEMAIS_REGIOES_T2 = np.array([0.25, 0.55, 0.10, 0.10])
POSICAO_CAIADO = nucleo.ORIGENS_1T.index("caiado")


@dataclasses.dataclass(frozen=True)
class RecuperacaoSintetica:
    """Estimativas de E1 e E2 sobre um conjunto sintético.

    Attributes:
        estimativa_e1: E1 (beta por região) ajustada ao Y sintético.
        estimativa_e2: E2 (beta único) ajustada ao Y sintético.
    """

    estimativa_e1: nucleo.EstimativaEspecificacao
    estimativa_e2: nucleo.EstimativaEspecificacao


def configurar_logging() -> None:
    """Configura log no stderr com horário e nível."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def montar_beta_verdadeiro_por_regiao_t1() -> np.ndarray:
    """beta verdadeiro do T1 repetido nas cinco regiões, shape (5, 8, 4)."""
    return np.tile(BETA_VERDADEIRO_T1, (len(nucleo.REGIOES), 1, 1))


def montar_beta_verdadeiro_por_regiao_t2() -> np.ndarray:
    """beta verdadeiro do T2, shape (5, 8, 4).

    Igual ao T1, exceto a linha `caiado`: [0,55; 0,30; 0,08; 0,07] no
    Centro-Oeste e [0,25; 0,55; 0,10; 0,10] nas demais regiões.
    """
    beta_por_regiao = montar_beta_verdadeiro_por_regiao_t1()

    for posicao_regiao, nome_regiao in enumerate(nucleo.REGIOES):
        if nome_regiao == REGIAO_CAIADO_DIFERENTE_T2:
            beta_por_regiao[posicao_regiao, POSICAO_CAIADO] = LINHA_CAIADO_CENTRO_OESTE_T2
        else:
            beta_por_regiao[posicao_regiao, POSICAO_CAIADO] = LINHA_CAIADO_DEMAIS_REGIOES_T2

    return beta_por_regiao


def sortear_dados_sinteticos(
    dados: nucleo.DadosEcologicos,
    beta_por_regiao: np.ndarray,
    gerador: np.random.Generator,
) -> nucleo.DadosEcologicos:
    """Substitui o Y real por contagens ~ Multinomial(aptos_1t, X beta_verdadeiro).

    As regiões são sorteadas na ordem de REGIOES com um único gerador.

    Args:
        dados: Dados reais (o X real é mantido).
        beta_por_regiao: beta verdadeiro por região, (5, 8, 4).
        gerador: Gerador pseudoaleatório com a semente já definida.

    Returns:
        Dados com `contagens_destino`, `matriz_destino` e `aptos_2t` sintéticos
        (aptos_2t = aptos_1t, o denominador de X).
    """
    numero_municipios = dados.regiao.shape[0]
    contagens_sinteticas = np.zeros((numero_municipios, nucleo.NUMERO_DESTINOS), dtype=np.int64)
    aptos_inteiros = dados.aptos_1t.astype(np.int64)

    for posicao_regiao, nome_regiao in enumerate(nucleo.REGIOES):
        posicoes = np.flatnonzero(dados.regiao == nome_regiao)
        beta_da_regiao = beta_por_regiao[posicao_regiao]
        probabilidades = dados.matriz_origem[posicoes] @ beta_da_regiao
        contagens_da_regiao = gerador.multinomial(aptos_inteiros[posicoes], probabilidades)
        contagens_sinteticas[posicoes] = contagens_da_regiao

    matriz_destino_sintetica = contagens_sinteticas / dados.aptos_1t[:, np.newaxis]
    return dataclasses.replace(
        dados,
        aptos_2t=dados.aptos_1t,
        contagens_destino=contagens_sinteticas,
        matriz_destino=matriz_destino_sintetica,
    )


def recuperar_com_e1_e2(
    dados_sinteticos: nucleo.DadosEcologicos,
    indices_regionais: dict[str, np.ndarray],
    populacao_de_grupos: np.ndarray,
) -> RecuperacaoSintetica:
    """Ajusta E1 e E2 (estimativa pontual, sem bootstrap) ao Y sintético."""
    multiplicidade_unitaria = np.ones(dados_sinteticos.regiao.shape[0], dtype=np.int64)

    estimativa_e1 = nucleo.estimar_especificacao(
        dados_sinteticos,
        nucleo.ESPECIFICACAO_E1,
        indices_regionais,
        populacao_de_grupos,
        multiplicidade_unitaria,
    )
    estimativa_e2 = nucleo.estimar_especificacao(
        dados_sinteticos,
        nucleo.ESPECIFICACAO_E2,
        indices_regionais,
        populacao_de_grupos,
        multiplicidade_unitaria,
    )
    return RecuperacaoSintetica(estimativa_e1=estimativa_e1, estimativa_e2=estimativa_e2)


def calcular_erro_maximo_por_linha(
    beta_estimado: np.ndarray,
    beta_verdadeiro: np.ndarray,
) -> np.ndarray:
    """Para cada origem, o maior |beta_estimado - beta_verdadeiro| entre os destinos."""
    erro_absoluto = np.abs(beta_estimado - beta_verdadeiro)
    return erro_absoluto.max(axis=1)


def calcular_erro_maximo_regional_por_linha(
    beta_por_regiao_estimado: np.ndarray,
    beta_por_regiao_verdadeiro: np.ndarray,
) -> np.ndarray:
    """Para cada origem, o maior erro absoluto entre destinos e regiões, (8,)."""
    erro_absoluto = np.abs(beta_por_regiao_estimado - beta_por_regiao_verdadeiro)
    return erro_absoluto.max(axis=(0, 2))


def calcular_fluxos_verdadeiros_brasil(
    beta_por_regiao_verdadeiro: np.ndarray,
    populacao_de_grupos: np.ndarray,
) -> np.ndarray:
    """Fluxo esperado em votos no Brasil: soma_regiões N_reg[r] * beta_verdadeiro_reg[r, c]."""
    fluxos_por_regiao = np.zeros_like(beta_por_regiao_verdadeiro)

    for posicao_regiao in range(len(nucleo.REGIOES)):
        fluxos_por_regiao[posicao_regiao] = nucleo.calcular_fluxos_em_votos(
            beta_por_regiao_verdadeiro[posicao_regiao],
            populacao_de_grupos[posicao_regiao],
        )

    return fluxos_por_regiao.sum(axis=0)


def montar_tabela_erro_por_linha(
    erros_por_coluna: dict[str, np.ndarray],
) -> str:
    """Tabela Markdown: uma linha por origem, uma coluna por conjunto de erros."""
    cabecalho = ["origem"] + list(erros_por_coluna.keys())
    linhas: list[list[str]] = []

    for posicao_origem, nome_origem in enumerate(nucleo.ORIGENS_1T):
        linha = [f"**{nome_origem}**"]
        for erros in erros_por_coluna.values():
            linha.append(f"{erros[posicao_origem]:.4f}")
        linhas.append(linha)

    return saidas.formatar_tabela_markdown(cabecalho, linhas)


def montar_tabela_erro_com_sinal(
    beta_estimado: np.ndarray,
    beta_verdadeiro: np.ndarray,
) -> str:
    """Tabela 8x4 de (estimado - verdadeiro), com sinal."""
    cabecalho = ["origem"] + list(nucleo.DESTINOS_2T)
    linhas: list[list[str]] = []

    for posicao_origem, nome_origem in enumerate(nucleo.ORIGENS_1T):
        linha = [f"**{nome_origem}**"]
        for posicao_destino in range(nucleo.NUMERO_DESTINOS):
            diferenca = (
                beta_estimado[posicao_origem, posicao_destino]
                - beta_verdadeiro[posicao_origem, posicao_destino]
            )
            linha.append(f"{diferenca:+.4f}")
        linhas.append(linha)

    return saidas.formatar_tabela_markdown(cabecalho, linhas)


def rodar_sorteios_complementares_t1(
    dados: nucleo.DadosEcologicos,
    indices_regionais: dict[str, np.ndarray],
    populacao_de_grupos: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Repete o T1 com sementes adicionais para separar viés de ruído amostral.

    Returns:
        (erros E1 Brasil, erros E2), ambos (S, 8): erro máximo por linha em cada sorteio.
    """
    beta_t1_por_regiao = montar_beta_verdadeiro_por_regiao_t1()
    erros_e1 = np.zeros((NUMERO_SORTEIOS_COMPLEMENTARES, nucleo.NUMERO_ORIGENS))
    erros_e2 = np.zeros((NUMERO_SORTEIOS_COMPLEMENTARES, nucleo.NUMERO_ORIGENS))

    for indice_sorteio in range(NUMERO_SORTEIOS_COMPLEMENTARES):
        semente = SEMENTE_PRIMEIRO_SORTEIO_COMPLEMENTAR + indice_sorteio
        gerador = np.random.default_rng(semente)
        dados_sinteticos = sortear_dados_sinteticos(dados, beta_t1_por_regiao, gerador)
        recuperacao = recuperar_com_e1_e2(dados_sinteticos, indices_regionais, populacao_de_grupos)
        erros_e1[indice_sorteio] = calcular_erro_maximo_por_linha(
            recuperacao.estimativa_e1.beta_brasil,
            BETA_VERDADEIRO_T1,
        )
        erros_e2[indice_sorteio] = calcular_erro_maximo_por_linha(
            recuperacao.estimativa_e2.beta_brasil,
            BETA_VERDADEIRO_T1,
        )

    return erros_e1, erros_e2


def montar_secao_t1(
    recuperacao: RecuperacaoSintetica,
    erros_complementares_e1: np.ndarray,
    erros_complementares_e2: np.ndarray,
) -> list[str]:
    """Seção T1 do relatório: erros do sorteio oficial e dos sorteios complementares."""
    beta_t1_por_regiao = montar_beta_verdadeiro_por_regiao_t1()
    erro_e2 = calcular_erro_maximo_por_linha(
        recuperacao.estimativa_e2.beta_brasil,
        BETA_VERDADEIRO_T1,
    )
    erro_e1_brasil = calcular_erro_maximo_por_linha(
        recuperacao.estimativa_e1.beta_brasil,
        BETA_VERDADEIRO_T1,
    )
    erro_e1_regional = calcular_erro_maximo_regional_por_linha(
        recuperacao.estimativa_e1.beta_por_regiao,
        beta_t1_por_regiao,
    )

    linhas: list[str] = [
        "## T1 — β constante no país",
        "",
        f"Sorteio oficial (semente {nucleo.SEMENTE_PADRAO}). Erro absoluto máximo por linha "
        "(maior |estimado − verdadeiro| entre os 4 destinos).",
        "",
        montar_tabela_erro_por_linha(
            {
                "E2 (β nacional)": erro_e2,
                "E1 (Brasil agregado)": erro_e1_brasil,
                "E1 (pior região)": erro_e1_regional,
            }
        ),
        "",
        f"- Máximo geral: **E2 = {erro_e2.max():.4f}** · **E1 Brasil = {erro_e1_brasil.max():.4f}** "
        f"· **E1 pior região = {erro_e1_regional.max():.4f}**.",
        "",
        "### Erro com sinal (estimado − verdadeiro), sorteio oficial",
        "",
        "**E2**",
        "",
        montar_tabela_erro_com_sinal(recuperacao.estimativa_e2.beta_brasil, BETA_VERDADEIRO_T1),
        "",
        "**E1 (Brasil agregado)**",
        "",
        montar_tabela_erro_com_sinal(recuperacao.estimativa_e1.beta_brasil, BETA_VERDADEIRO_T1),
        "",
        f"### Sorteios complementares ({NUMERO_SORTEIOS_COMPLEMENTARES} sementes, "
        f"{SEMENTE_PRIMEIRO_SORTEIO_COMPLEMENTAR} em diante)",
        "",
        "Não faz parte da especificação. Serve para separar viés sistemático de ruído "
        "amostral: erro máximo por linha, mediana e máximo entre sorteios.",
        "",
    ]

    cabecalho = ["origem", "E2 mediana", "E2 máximo", "E1 Brasil mediana", "E1 Brasil máximo"]
    linhas_tabela: list[list[str]] = []
    for posicao_origem, nome_origem in enumerate(nucleo.ORIGENS_1T):
        linhas_tabela.append(
            [
                f"**{nome_origem}**",
                f"{np.median(erros_complementares_e2[:, posicao_origem]):.4f}",
                f"{erros_complementares_e2[:, posicao_origem].max():.4f}",
                f"{np.median(erros_complementares_e1[:, posicao_origem]):.4f}",
                f"{erros_complementares_e1[:, posicao_origem].max():.4f}",
            ]
        )
    linhas.append(saidas.formatar_tabela_markdown(cabecalho, linhas_tabela))
    linhas.append("")
    return linhas


def montar_secao_t2(
    recuperacao: RecuperacaoSintetica,
    populacao_de_grupos: np.ndarray,
) -> tuple[list[str], dict[str, float]]:
    """Seção T2 do relatório: fluxo nacional de Caiado em E1 e E2 contra o verdadeiro.

    Returns:
        (linhas do relatório, métricas-chave para o log).
    """
    beta_t2_por_regiao = montar_beta_verdadeiro_por_regiao_t2()
    fluxos_verdadeiros = calcular_fluxos_verdadeiros_brasil(beta_t2_por_regiao, populacao_de_grupos)

    fluxo_verdadeiro_caiado = fluxos_verdadeiros[POSICAO_CAIADO]
    fluxo_e1_caiado = recuperacao.estimativa_e1.fluxos_brasil[POSICAO_CAIADO]
    fluxo_e2_caiado = recuperacao.estimativa_e2.fluxos_brasil[POSICAO_CAIADO]
    total_caiado = fluxo_verdadeiro_caiado.sum()

    erro_e1 = fluxo_e1_caiado - fluxo_verdadeiro_caiado
    erro_e2 = fluxo_e2_caiado - fluxo_verdadeiro_caiado
    erro_e1_percentual_do_total = 100.0 * np.abs(erro_e1).max() / total_caiado
    erro_e2_percentual_do_total = 100.0 * np.abs(erro_e2).max() / total_caiado

    cabecalho = [
        "destino",
        "verdadeiro (votos)",
        "E1 (votos)",
        "erro E1",
        "erro E1 (% do verdadeiro)",
        "E2 (votos)",
        "erro E2",
        "erro E2 (% do verdadeiro)",
    ]
    linhas_tabela: list[list[str]] = []
    for posicao_destino, nome_destino in enumerate(nucleo.DESTINOS_2T):
        verdadeiro = fluxo_verdadeiro_caiado[posicao_destino]
        linhas_tabela.append(
            [
                nome_destino,
                f"{verdadeiro:,.0f}",
                f"{fluxo_e1_caiado[posicao_destino]:,.0f}",
                f"{erro_e1[posicao_destino]:+,.0f}",
                f"{100.0 * erro_e1[posicao_destino] / verdadeiro:+.2f}%",
                f"{fluxo_e2_caiado[posicao_destino]:,.0f}",
                f"{erro_e2[posicao_destino]:+,.0f}",
                f"{100.0 * erro_e2[posicao_destino] / verdadeiro:+.2f}%",
            ]
        )

    beta_brasil_verdadeiro = nucleo.converter_fluxos_em_beta(fluxos_verdadeiros)
    erro_beta_e1 = calcular_erro_maximo_por_linha(
        recuperacao.estimativa_e1.beta_brasil,
        beta_brasil_verdadeiro,
    )
    erro_beta_e2 = calcular_erro_maximo_por_linha(
        recuperacao.estimativa_e2.beta_brasil,
        beta_brasil_verdadeiro,
    )
    erro_beta_regional_e1 = calcular_erro_maximo_regional_por_linha(
        recuperacao.estimativa_e1.beta_por_regiao,
        beta_t2_por_regiao,
    )

    linhas: list[str] = [
        "## T2 — β de Caiado varia por região",
        "",
        "Caiado: Centro-Oeste `[0,55; 0,30; 0,08; 0,07]`, demais regiões `[0,25; 0,55; 0,10; 0,10]`. "
        "As demais linhas são iguais às do T1. O fluxo 'verdadeiro' é o valor esperado "
        "`Σ_regiões N_reg[caiado] · β_verdadeiro_reg` (o sorteio multinomial adiciona ruído "
        "de ordem √N aos votos realizados).",
        "",
        f"Total do grupo Caiado no Brasil: **{total_caiado:,.0f}** eleitores.",
        "",
        "### Fluxo nacional de Caiado",
        "",
        saidas.formatar_tabela_markdown(cabecalho, linhas_tabela),
        "",
        f"- Erro máximo do fluxo de Caiado (maior destino, % do total do grupo): "
        f"**E1 = {erro_e1_percentual_do_total:.2f}%** · **E2 = {erro_e2_percentual_do_total:.2f}%**.",
        "",
        "### Erro máximo por linha do β do Brasil (contra o β agregado verdadeiro do T2)",
        "",
        montar_tabela_erro_por_linha(
            {
                "E1 (Brasil)": erro_beta_e1,
                "E2 (Brasil)": erro_beta_e2,
                "E1 (pior região, vs β regional verdadeiro)": erro_beta_regional_e1,
            }
        ),
        "",
        "### Linha de Caiado, β por região — E1 × verdadeiro",
        "",
    ]

    cabecalho_regional = ["região", "origem"] + list(nucleo.DESTINOS_2T)
    linhas_regionais: list[list[str]] = []
    for posicao_regiao, nome_regiao in enumerate(nucleo.REGIOES):
        beta_verdadeiro_caiado = beta_t2_por_regiao[posicao_regiao, POSICAO_CAIADO]
        beta_e1_caiado = recuperacao.estimativa_e1.beta_por_regiao[posicao_regiao, POSICAO_CAIADO]
        beta_e2_caiado = recuperacao.estimativa_e2.beta_por_regiao[posicao_regiao, POSICAO_CAIADO]
        for rotulo, vetor in (
            ("verdadeiro", beta_verdadeiro_caiado),
            ("E1", beta_e1_caiado),
            ("E2", beta_e2_caiado),
        ):
            linha = [nome_regiao, rotulo]
            for posicao_destino in range(nucleo.NUMERO_DESTINOS):
                linha.append(f"{vetor[posicao_destino]:.3f}")
            linhas_regionais.append(linha)
    linhas.append(saidas.formatar_tabela_markdown(cabecalho_regional, linhas_regionais))
    linhas.append("")

    if erro_e2_percentual_do_total > erro_e1_percentual_do_total:
        linhas.append("- Resultado: E2 erra mais que E1 no fluxo nacional de Caiado (direção esperada).")
    else:
        linhas.append(
            "- ⚠️ Resultado: E2 NÃO erra mais que E1 no fluxo nacional de Caiado "
            "(contraria o esperado)."
        )
    linhas.append("")

    metricas = {
        "erro_fluxo_caiado_e1_pct": float(erro_e1_percentual_do_total),
        "erro_fluxo_caiado_e2_pct": float(erro_e2_percentual_do_total),
        "erro_fluxo_caiado_e1_votos_max": float(np.abs(erro_e1).max()),
        "erro_fluxo_caiado_e2_votos_max": float(np.abs(erro_e2).max()),
    }
    return linhas, metricas


def main() -> None:
    """Roda T1 e T2, grava `teste_sintetico.md` e registra as métricas principais."""
    configurar_logging()
    inicio = time.perf_counter()

    base_completa = nucleo.carregar_base_municipal(CAMINHO_BASE)
    municipios = nucleo.selecionar_municipios_brasileiros(base_completa)
    dados = nucleo.montar_dados_ecologicos(municipios)
    nucleo.exigir_ancoras_aprovadas(nucleo.validar_ancoras(dados))

    indices_regionais = nucleo.indices_por_regiao(dados.regiao)
    populacao_de_grupos = nucleo.calcular_populacao_de_grupos_por_regiao(
        dados.contagens_origem,
        indices_regionais,
    )

    gerador_t1 = np.random.default_rng(nucleo.SEMENTE_PADRAO)
    dados_t1 = sortear_dados_sinteticos(dados, montar_beta_verdadeiro_por_regiao_t1(), gerador_t1)
    recuperacao_t1 = recuperar_com_e1_e2(dados_t1, indices_regionais, populacao_de_grupos)
    LOGGER.info("T1 concluído.")

    erros_complementares_e1, erros_complementares_e2 = rodar_sorteios_complementares_t1(
        dados,
        indices_regionais,
        populacao_de_grupos,
    )
    LOGGER.info("Sorteios complementares do T1 concluídos.")

    gerador_t2 = np.random.default_rng(nucleo.SEMENTE_PADRAO)
    dados_t2 = sortear_dados_sinteticos(dados, montar_beta_verdadeiro_por_regiao_t2(), gerador_t2)
    recuperacao_t2 = recuperar_com_e1_e2(dados_t2, indices_regionais, populacao_de_grupos)
    LOGGER.info("T2 concluído.")

    linhas_t2, metricas_t2 = montar_secao_t2(recuperacao_t2, populacao_de_grupos)
    linhas_relatorio: list[str] = [
        "# Teste de recuperação sintética",
        "",
        f"Gerado por `02_teste_sintetico.py` · semente {nucleo.SEMENTE_PADRAO} · "
        f"{dados.regiao.shape[0]} municípios (X real).",
        "",
        "Y sintético: `contagens ~ Multinomial(aptos_1t, X · β_verdadeiro)`, sorteado região a "
        "região (ordem Centro-Oeste, Nordeste, Norte, Sudeste, Sul) com um único gerador; "
        "Y = contagens / aptos_1t. Ajuste ponderado por `aptos_1t`, sem bootstrap (só estimativa pontual).",
        "",
    ]
    linhas_relatorio.extend(
        montar_secao_t1(recuperacao_t1, erros_complementares_e1, erros_complementares_e2)
    )
    linhas_relatorio.extend(linhas_t2)

    texto_relatorio = "\n".join(linhas_relatorio)
    CAMINHO_RELATORIO.write_text(texto_relatorio, encoding=CODIFICACAO_SAIDA)
    LOGGER.info("Gravado %s.", CAMINHO_RELATORIO)

    erro_t1_e2 = calcular_erro_maximo_por_linha(
        recuperacao_t1.estimativa_e2.beta_brasil,
        BETA_VERDADEIRO_T1,
    )
    erro_t1_e1 = calcular_erro_maximo_por_linha(
        recuperacao_t1.estimativa_e1.beta_brasil,
        BETA_VERDADEIRO_T1,
    )
    LOGGER.info("T1 erro máximo por linha, E2: %s", np.round(erro_t1_e2, 4).tolist())
    LOGGER.info("T1 erro máximo por linha, E1 Brasil: %s", np.round(erro_t1_e1, 4).tolist())
    LOGGER.info("T2 métricas do fluxo de Caiado: %s", metricas_t2)
    LOGGER.info("Concluído em %.1fs.", time.perf_counter() - inicio)


if __name__ == "__main__":
    main()
