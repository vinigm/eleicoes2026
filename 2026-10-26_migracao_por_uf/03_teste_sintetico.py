"""Teste de recuperação sintética da migração por estado (seção 7 da especificação).

Com o X real e Y sorteado de uma multinomial cujo β verdadeiro varia por estado
(β da região + deslocamento delta_u nas linhas caiado, cury e renan), compara o
erro de β de (a) UF com kappa escolhido por validação cruzada NOS DADOS SINTÉTICOS,
(b) UF_SOZINHO (kappa = 0,25) e (c) UF_REGIAO (kappa = infinito).

Sorteio principal: semente 20261025 (delta_u primeiro, depois Y, estados em ordem
alfabética). Como evidência complementar (NÃO faz parte da especificação), repete o
experimento com sementes 20261026 a 20261045.

Grava `teste_sintetico.md`. Uso: python3 -I 03_teste_sintetico.py
"""

import dataclasses
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
import sintetico_uf as sintetico  # noqa: E402

LOGGER = logging.getLogger("03_teste_sintetico")
regional = nucleo.regional

DATA_CRIACAO = "26/10/2026"
CAMINHO_TESTE_SINTETICO_MD = PASTA_TRABALHO / "teste_sintetico.md"
NUMERO_SORTEIOS_COMPLEMENTARES = 20
TOLERANCIA_COMPARACAO_ERROS = 1e-12


@dataclasses.dataclass(frozen=True)
class ResultadoSorteio:
    """Resultado de um sorteio sintético completo.

    Attributes:
        semente: Semente do sorteio.
        deslocamentos: delta_u por estado, (U,).
        betas_verdadeiros: (U, 8, 4).
        cv: Validação cruzada nos dados sintéticos.
        estimativas: Versão -> estimativa pontual nos dados sintéticos.
        erro: Versão -> erro médio absoluto ponderado nas 3 linhas.
        erro_por_origem: Versão -> {origem: erro}.
        erro_por_uf: Versão -> erro por estado, (U,).
        erro_oraculo_por_kappa: Erro de β para cada kappa da grade seguido de kappa = infinito,
            (K + 1,). Usa o β verdadeiro (inexistente em dados reais): só diagnóstico.
    """

    semente: int
    deslocamentos: np.ndarray
    betas_verdadeiros: np.ndarray
    cv: nucleo.ResultadoValidacaoCruzada
    estimativas: dict[str, nucleo.EstimativaVersao]
    erro: dict[str, float]
    erro_por_origem: dict[str, dict[str, float]]
    erro_por_uf: dict[str, np.ndarray]
    erro_oraculo_por_kappa: np.ndarray

    @property
    def kappa_oraculo(self) -> float:
        """Kappa (da grade ou infinito) com o menor erro de β verdadeiro."""
        kappas_com_infinito = list(nucleo.KAPPAS_GRADE) + [nucleo.KAPPA_REGIAO]
        return float(kappas_com_infinito[int(np.argmin(self.erro_oraculo_por_kappa))])


def configurar_logging() -> None:
    """Configura o log no formato `hora nível mensagem`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def calcular_erro_oraculo_por_kappa(
    base_sintetica: nucleo.BaseUF,
    betas_verdadeiros: np.ndarray,
    betas_da_regiao: np.ndarray,
    populacao_por_uf: np.ndarray,
) -> np.ndarray:
    """Erro de β verdadeiro para cada kappa da grade e para kappa infinito (só diagnóstico).

    Mostra se existe algum kappa que bata UF_SOZINHO no mundo sintético, independente
    de a validação cruzada (que só enxerga Y) conseguir encontrá-lo.
    """
    erros: list[float] = []

    for kappa in nucleo.KAPPAS_GRADE:
        estimativa = nucleo.estimar_versao(
            base_sintetica,
            nucleo.CODIGO_UF,
            kappa,
            betas_da_regiao,
        )
        erro = sintetico.calcular_erro_absoluto_ponderado(
            estimativa.betas,
            betas_verdadeiros,
            populacao_por_uf,
        )
        erros.append(erro)

    erro_regiao = sintetico.calcular_erro_absoluto_ponderado(
        betas_da_regiao,
        betas_verdadeiros,
        populacao_por_uf,
    )
    erros.append(erro_regiao)
    return np.array(erros)


def executar_sorteio(
    base: nucleo.BaseUF,
    semente: int,
    amplitude_deslocamento: float = sintetico.AMPLITUDE_DESLOCAMENTO,
) -> ResultadoSorteio:
    """Sorteia dados sintéticos, escolhe kappa por validação cruzada e mede os erros.

    Args:
        base: Base real (X e aptos_1t reais).
        semente: Semente do gerador.
        amplitude_deslocamento: Meia-largura de delta_u (0,15 na especificação; 0 no controle).

    Returns:
        O resultado completo do sorteio.
    """
    gerador = np.random.default_rng(semente)
    numero_ufs = len(base.lista_ufs)

    deslocamentos = sintetico.sortear_deslocamentos_por_uf(
        numero_ufs,
        gerador,
        amplitude_deslocamento,
    )
    betas_verdadeiros = sintetico.montar_betas_verdadeiros_por_uf(
        sintetico.BETA_REGIAO_T1,
        deslocamentos,
    )
    destino_sintetico = sintetico.sortear_destino_sintetico(base, betas_verdadeiros, gerador)
    base_sintetica = nucleo.substituir_destino(base, destino_sintetico)

    resultado_cv = nucleo.executar_validacao_cruzada(
        base_sintetica,
        nucleo.KAPPAS_GRADE,
        nucleo.NUMERO_DOBRAS,
    )
    kappa_estrela = resultado_cv.kappa_otimo

    estimativa_regiao = nucleo.estimar_versao(
        base_sintetica,
        nucleo.CODIGO_UF_REGIAO,
        nucleo.KAPPA_REGIAO,
        None,
    )
    estimativa_sozinho = nucleo.estimar_versao(
        base_sintetica,
        nucleo.CODIGO_UF_SOZINHO,
        nucleo.KAPPA_SOZINHO,
        estimativa_regiao.betas,
    )
    estimativa_uf = nucleo.estimar_versao(
        base_sintetica,
        nucleo.CODIGO_UF,
        kappa_estrela,
        estimativa_regiao.betas,
    )
    estimativas = {
        nucleo.CODIGO_UF: estimativa_uf,
        nucleo.CODIGO_UF_SOZINHO: estimativa_sozinho,
        nucleo.CODIGO_UF_REGIAO: estimativa_regiao,
    }

    erro: dict[str, float] = {}
    erro_por_origem: dict[str, dict[str, float]] = {}
    erro_por_uf: dict[str, np.ndarray] = {}
    for codigo in nucleo.CODIGOS_VERSOES:
        betas_estimados = estimativas[codigo].betas
        erro[codigo] = sintetico.calcular_erro_absoluto_ponderado(
            betas_estimados,
            betas_verdadeiros,
            base.populacao_por_uf,
        )
        erro_por_origem[codigo] = sintetico.calcular_erro_por_origem(
            betas_estimados,
            betas_verdadeiros,
            base.populacao_por_uf,
        )
        erro_por_uf[codigo] = sintetico.calcular_erro_por_uf(
            betas_estimados,
            betas_verdadeiros,
            base.populacao_por_uf,
        )

    erro_oraculo = calcular_erro_oraculo_por_kappa(
        base_sintetica,
        betas_verdadeiros,
        estimativa_regiao.betas,
        base.populacao_por_uf,
    )

    return ResultadoSorteio(
        semente=semente,
        deslocamentos=deslocamentos,
        betas_verdadeiros=betas_verdadeiros,
        cv=resultado_cv,
        estimativas=estimativas,
        erro=erro,
        erro_por_origem=erro_por_origem,
        erro_por_uf=erro_por_uf,
        erro_oraculo_por_kappa=erro_oraculo,
    )


def a_nao_perde_para_as_referencias(erro: dict[str, float]) -> bool:
    """Verifica (a) <= min((b), (c)) com tolerância numérica desprezível."""
    erro_a = erro[nucleo.CODIGO_UF]
    menor_referencia = min(erro[nucleo.CODIGO_UF_SOZINHO], erro[nucleo.CODIGO_UF_REGIAO])
    return erro_a <= menor_referencia + TOLERANCIA_COMPARACAO_ERROS


def montar_secao_resultado_principal(
    base: nucleo.BaseUF,
    sorteio: ResultadoSorteio,
) -> str:
    """Seção do sorteio principal (semente da especificação)."""
    erro = sorteio.erro
    erro_a = erro[nucleo.CODIGO_UF]
    erro_b = erro[nucleo.CODIGO_UF_SOZINHO]
    erro_c = erro[nucleo.CODIGO_UF_REGIAO]
    cumpriu = a_nao_perde_para_as_referencias(erro)

    veredito = "**CONFIRMADO: (a) ≤ min((b), (c)).**"
    empate_com_b = abs(erro_a - erro_b) <= TOLERANCIA_COMPARACAO_ERROS
    if cumpriu and empate_com_b:
        veredito = (
            "**CONFIRMADO SÓ POR EMPATE: (a) = (b)**, porque o κ\\* sintético caiu na borda inferior da grade "
            "(κ = 0,25) e a versão UF coincide com UF_SOZINHO. O teste não mostra ganho do encolhimento sobre o estado sozinho."
        )
    if not cumpriu:
        veredito = (
            "**CONTRARIA O ESPERADO: (a) > min((b), (c)).** Reportado como está; o método não foi ajustado."
        )

    linhas_resumo: list[list[str]] = [
        [
            "(a) UF, κ por validação cruzada nos dados sintéticos "
            f"(κ\\* = {saidas.formatar_kappa(sorteio.cv.kappa_otimo)})",
            saidas.formatar_numero(erro_a, 5),
        ],
        ["(b) UF_SOZINHO (κ = 0,25)", saidas.formatar_numero(erro_b, 5)],
        ["(c) UF_REGIAO (κ = ∞)", saidas.formatar_numero(erro_c, 5)],
    ]
    tabela_resumo = montar_tabela(["versão", "erro médio absoluto de β (caiado, cury, renan; ponderado por N_u[r])"], linhas_resumo)

    linhas_origem: list[list[str]] = []
    for origem in sintetico.ORIGENS_PERTURBADAS:
        linha = [origem]
        for codigo in nucleo.CODIGOS_VERSOES:
            linha.append(saidas.formatar_numero(sorteio.erro_por_origem[codigo][origem], 5))
        linhas_origem.append(linha)
    tabela_origem = montar_tabela(["origem", "(a) UF", "(b) UF_SOZINHO", "(c) UF_REGIAO"], linhas_origem)

    linhas_cv: list[list[str]] = []
    tabela_curva = saidas.montar_tabela_curva_cv(sorteio.cv)
    for _, linha_curva in tabela_curva.iterrows():
        linhas_cv.append(
            [
                saidas.formatar_kappa(float(linha_curva["kappa"])),
                saidas.formatar_numero(float(linha_curva["erro_validacao"]), 1),
                saidas.formatar_numero(float(linha_curva["razao_ao_minimo"]), 4),
            ]
        )
    tabela_cv = montar_tabela(["κ", "erro de validação (dados sintéticos)", "÷ menor erro"], linhas_cv)

    linhas_uf: list[list[str]] = []
    for posicao_uf, sigla in enumerate(base.lista_ufs):
        linhas_uf.append(
            [
                sigla,
                saidas.formatar_numero(float(sorteio.deslocamentos[posicao_uf]), 3),
                saidas.formatar_numero(float(sorteio.erro_por_uf[nucleo.CODIGO_UF][posicao_uf]), 4),
                saidas.formatar_numero(float(sorteio.erro_por_uf[nucleo.CODIGO_UF_SOZINHO][posicao_uf]), 4),
                saidas.formatar_numero(float(sorteio.erro_por_uf[nucleo.CODIGO_UF_REGIAO][posicao_uf]), 4),
            ]
        )
    tabela_uf = montar_tabela(
        ["UF", "δ_u", "erro (a) UF", "erro (b) UF_SOZINHO", "erro (c) UF_REGIAO"],
        linhas_uf,
    )

    kappas_com_infinito = list(nucleo.KAPPAS_GRADE) + [nucleo.KAPPA_REGIAO]
    linhas_oraculo: list[list[str]] = []
    for posicao_kappa, kappa in enumerate(kappas_com_infinito):
        linhas_oraculo.append(
            [
                saidas.formatar_kappa(kappa),
                saidas.formatar_numero(float(sorteio.erro_oraculo_por_kappa[posicao_kappa]), 5),
            ]
        )
    tabela_oraculo = montar_tabela(["κ", "erro de β verdadeiro (a versão UF nesse κ)"], linhas_oraculo)

    texto_borda = "κ\\* sintético não está na borda da grade."
    if sorteio.cv.na_borda_da_grade:
        texto_borda = "**ALERTA: κ\\* sintético está na borda da grade** (grade não estendida)."

    partes = [
        "## Sorteio principal (semente 20261025)",
        "",
        f"- {veredito}",
        f"- (a) = **{saidas.formatar_numero(erro_a, 5)}** · (b) = **{saidas.formatar_numero(erro_b, 5)}** · (c) = **{saidas.formatar_numero(erro_c, 5)}**.",
        f"- {texto_borda}",
        "- Erro = média, sobre as 4 destinações, de |β̂ − β verdadeiro|, nas linhas caiado/cury/renan, ponderada por `N_u[r]` (contagem do grupo no estado).",
        "",
        tabela_resumo,
        "",
        "### Erro por origem",
        "",
        tabela_origem,
        "",
        "### Validação cruzada nos dados sintéticos",
        "",
        tabela_cv,
        "",
        "### Diagnóstico: erro de β por κ com o β verdadeiro (oráculo; não existe em dados reais)",
        "",
        f"- Melhor κ pelo erro de β verdadeiro: **{saidas.formatar_kappa(sorteio.kappa_oraculo)}**; "
        f"κ\\* escolhido pela validação cruzada (que só enxerga Y): **{saidas.formatar_kappa(sorteio.cv.kappa_otimo)}**.",
        "",
        tabela_oraculo,
        "",
        "### Por estado (erro ponderado por N_u[r] nas 3 linhas)",
        "",
        tabela_uf,
        "",
    ]
    return "\n".join(partes)


def montar_tabela(cabecalhos: list[str], linhas: list[list[str]]) -> str:
    """Tabela Markdown (atalho para `saidas.montar_tabela_markdown`)."""
    return saidas.montar_tabela_markdown(cabecalhos, linhas)


def montar_secao_complementar(sorteios: list[ResultadoSorteio]) -> str:
    """Seção complementar: repetição do experimento com outras sementes."""
    numero_sorteios = len(sorteios)
    vitorias = 0
    soma_erro = {codigo: 0.0 for codigo in nucleo.CODIGOS_VERSOES}
    linhas: list[list[str]] = []

    for sorteio in sorteios:
        cumpriu = a_nao_perde_para_as_referencias(sorteio.erro)
        if cumpriu:
            vitorias += 1
        for codigo in nucleo.CODIGOS_VERSOES:
            soma_erro[codigo] += sorteio.erro[codigo]
        linhas.append(
            [
                str(sorteio.semente),
                saidas.formatar_kappa(sorteio.cv.kappa_otimo),
                saidas.formatar_numero(sorteio.erro[nucleo.CODIGO_UF], 5),
                saidas.formatar_numero(sorteio.erro[nucleo.CODIGO_UF_SOZINHO], 5),
                saidas.formatar_numero(sorteio.erro[nucleo.CODIGO_UF_REGIAO], 5),
                "sim" if cumpriu else "NÃO",
                saidas.formatar_kappa(sorteio.kappa_oraculo),
                saidas.formatar_numero(float(sorteio.erro_oraculo_por_kappa.min()), 5),
            ]
        )

    tabela = montar_tabela(
        [
            "semente",
            "κ\\* sintético",
            "(a) UF",
            "(b) UF_SOZINHO",
            "(c) UF_REGIAO",
            "(a) ≤ min((b), (c))",
            "melhor κ (oráculo)",
            "erro no melhor κ (oráculo)",
        ],
        linhas,
    )
    kappas_estrela_na_borda = 0
    for sorteio in sorteios:
        if sorteio.cv.kappa_otimo == nucleo.KAPPAS_GRADE[0]:
            kappas_estrela_na_borda += 1
    empates_com_b = 0
    for sorteio in sorteios:
        if abs(sorteio.erro[nucleo.CODIGO_UF] - sorteio.erro[nucleo.CODIGO_UF_SOZINHO]) <= TOLERANCIA_COMPARACAO_ERROS:
            empates_com_b += 1
    media_a = soma_erro[nucleo.CODIGO_UF] / numero_sorteios
    media_b = soma_erro[nucleo.CODIGO_UF_SOZINHO] / numero_sorteios
    media_c = soma_erro[nucleo.CODIGO_UF_REGIAO] / numero_sorteios

    partes = [
        "## Evidência complementar (fora da especificação): outras sementes",
        "",
        f"- {numero_sorteios} sorteios independentes (sementes 20261026 a {20261025 + numero_sorteios}), mesmo procedimento.",
        f"- **(a) ≤ min((b), (c)) em {vitorias} de {numero_sorteios} sorteios.**",
        f"- κ\\* sintético = 0,25 (borda inferior da grade) em **{kappas_estrela_na_borda} de {numero_sorteios}**; "
        f"nesses casos (a) é idêntico a (b) ({empates_com_b} empates exatos).",
        f"- Erro médio: (a) **{saidas.formatar_numero(media_a, 5)}** · (b) **{saidas.formatar_numero(media_b, 5)}** · (c) **{saidas.formatar_numero(media_c, 5)}**.",
        "- Serve só para saber se o sorteio principal é típico; o veredito da especificação é o do sorteio principal.",
        "",
        tabela,
        "",
    ]
    return "\n".join(partes)


def montar_secao_controle(sorteio: ResultadoSorteio) -> str:
    """Seção do experimento de controle: mundo sem heterogeneidade entre estados (delta_u = 0)."""
    erro = sorteio.erro
    cumpriu = a_nao_perde_para_as_referencias(erro)
    partes = [
        "## Controle (fora da especificação): mundo sem heterogeneidade, δ_u = 0",
        "",
        "- Mesmo procedimento e semente, mas todos os estados com o β da região (β constante). "
        "É o regime em que encolher para a região DEVE ajudar; confere se a validação cruzada e o solver enxergam isso.",
        f"- κ\\* sintético = **{saidas.formatar_kappa(sorteio.cv.kappa_otimo)}** "
        f"(borda da grade: {'sim' if sorteio.cv.na_borda_da_grade else 'não'}); melhor κ pelo β verdadeiro (oráculo) = "
        f"**{saidas.formatar_kappa(sorteio.kappa_oraculo)}**.",
        f"- Erro de β nas 3 linhas: (a) UF = **{saidas.formatar_numero(erro[nucleo.CODIGO_UF], 5)}** · "
        f"(b) UF_SOZINHO = **{saidas.formatar_numero(erro[nucleo.CODIGO_UF_SOZINHO], 5)}** · "
        f"(c) UF_REGIAO = **{saidas.formatar_numero(erro[nucleo.CODIGO_UF_REGIAO], 5)}**; "
        f"(a) ≤ min((b), (c)): {'sim' if cumpriu else 'NÃO'}.",
        "",
    ]
    return "\n".join(partes)


def main() -> None:
    """Roda o sorteio principal e os complementares e grava `teste_sintetico.md`."""
    configurar_logging()
    instante_inicial = time.perf_counter()

    municipios = nucleo.carregar_municipios_brasileiros(nucleo.CAMINHO_BASE_PARQUET)
    base = nucleo.montar_base_uf(municipios)
    nucleo.exigir_ancoras_por_uf(base)

    sorteio_principal = executar_sorteio(base, nucleo.SEMENTE_UF)
    LOGGER.info(
        "Sorteio principal: kappa*=%s; erro (a)=%.5f (b)=%.5f (c)=%.5f; (a)<=min(b,c): %s.",
        sorteio_principal.cv.kappa_otimo,
        sorteio_principal.erro[nucleo.CODIGO_UF],
        sorteio_principal.erro[nucleo.CODIGO_UF_SOZINHO],
        sorteio_principal.erro[nucleo.CODIGO_UF_REGIAO],
        a_nao_perde_para_as_referencias(sorteio_principal.erro),
    )

    sorteios_complementares: list[ResultadoSorteio] = []
    for deslocamento_semente in range(1, NUMERO_SORTEIOS_COMPLEMENTARES + 1):
        semente = nucleo.SEMENTE_UF + deslocamento_semente
        sorteio = executar_sorteio(base, semente)
        sorteios_complementares.append(sorteio)
        LOGGER.info(
            "Sorteio complementar %d/%d (semente %d): kappa*=%s; (a)=%.5f (b)=%.5f (c)=%.5f.",
            deslocamento_semente,
            NUMERO_SORTEIOS_COMPLEMENTARES,
            semente,
            sorteio.cv.kappa_otimo,
            sorteio.erro[nucleo.CODIGO_UF],
            sorteio.erro[nucleo.CODIGO_UF_SOZINHO],
            sorteio.erro[nucleo.CODIGO_UF_REGIAO],
        )

    partes = [
        "# Teste de recuperação sintética — migração de votos por estado",
        "",
        f"Criado em {DATA_CRIACAO}. Gerado por `03_teste_sintetico.py`. Método: seção 7 de `ESPECIFICACAO.md`.",
        "",
        "## Desenho",
        "",
        "- X real (5.571 municípios); `Y_i ~ Multinomial(aptos_1t_i, X_i · β_verdadeiro_u)`; semente 20261025.",
        "- β da região = matriz T1 da especificação regional (lula/flavio ~0,95 de lealdade; cury 0,40/0,35/0,10/0,15; renan 0,15/0,65/0,10/0,10; caiado 0,35/0,45/0,10/0,10; ...).",
        "- β do estado = β da região + deslocamento δ_u de `flavio` para `lula` (δ_u > 0 = mais lula) nas linhas caiado, cury e renan; "
        "δ_u ~ Uniforme[−0,15; +0,15] por estado (mesmo δ_u nas 3 linhas), sorteado ANTES de Y com a mesma semente; deslocamento recortado em [−β_lula, +β_flavio] para manter o simplex.",
        "- Y em fração dos aptos do 1º turno (cada linha soma 1); o 2º turno real não é usado.",
        "- Comparação: (a) UF com κ escolhido por validação cruzada (mesma grade e dobras) NOS DADOS SINTÉTICOS; (b) UF_SOZINHO; (c) UF_REGIAO.",
        "- **Esperado:** (a) ≤ min((b), (c)). Se não for, reporta-se; o método não é ajustado.",
        "",
        montar_secao_resultado_principal(base, sorteio_principal),
        montar_secao_complementar(sorteios_complementares),
    ]
    sorteio_controle = executar_sorteio(base, nucleo.SEMENTE_UF, 0.0)
    LOGGER.info(
        "Controle (delta_u = 0): kappa*=%s; erro (a)=%.5f (b)=%.5f (c)=%.5f.",
        sorteio_controle.cv.kappa_otimo,
        sorteio_controle.erro[nucleo.CODIGO_UF],
        sorteio_controle.erro[nucleo.CODIGO_UF_SOZINHO],
        sorteio_controle.erro[nucleo.CODIGO_UF_REGIAO],
    )
    partes.append(montar_secao_controle(sorteio_controle))

    retentativas_totais = sorteio_principal.cv.numero_retentativas + sorteio_controle.cv.numero_retentativas
    for sorteio in sorteios_complementares:
        retentativas_totais += sorteio.cv.numero_retentativas
    partes.append(
        "## Solver\n\n"
        "- Todos os ajustes (validações cruzadas e estimativas dos sorteios) foram certificados "
        "(sucesso do SLSQP, viabilidade e lacuna de dualidade ≤ 1e-7); falha seria exceção.\n"
        f"- Ajustes das validações cruzadas que precisaram do ponto inicial uniforme de reserva: **{retentativas_totais}** "
        f"(sorteio principal: {sorteio_principal.cv.numero_retentativas}; inclui complementares e controle).\n"
    )
    saidas.gravar_texto(CAMINHO_TESTE_SINTETICO_MD, "\n".join(partes))
    LOGGER.info("Tempo total: %.1f s.", time.perf_counter() - instante_inicial)


if __name__ == "__main__":
    main()
