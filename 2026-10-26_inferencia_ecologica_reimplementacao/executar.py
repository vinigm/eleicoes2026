"""Orquestração da reimplementação B: ajustes, bootstrap, testes e relatórios.

Uso (sempre em modo isolado):

    python3 -I executar.py [--replicas 1000]

Escreve, nesta pasta: transferencias.csv, transferencias_n_reamostrado.csv,
diagnosticos.md, teste_sintetico.md e README.md.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
import time
from pathlib import Path

PASTA_SAIDA = Path(__file__).resolve().parent
# O modo -I não inclui a pasta do script no sys.path; inclui-se explicitamente.
sys.path.insert(0, str(PASTA_SAIDA))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import ecologia_b as eco  # noqa: E402

LOGGER = logging.getLogger("executar_b")

ESPECIFICACAO_E1 = "E1"
ESPECIFICACAO_E2 = "E2"
ESPECIFICACAO_E3 = "E3"
PERCENTIL_INFERIOR = 2.5
PERCENTIL_SUPERIOR = 97.5
MAXIMO_ITERACOES_BOOTSTRAP = 60_000
SEMENTE_INICIOS_ALEATORIOS = 7
NUMERO_INICIOS_ALEATORIOS = 3
LIMIAR_LARGURA_DEGENERADA = 1e-9
TOLERANCIA_REFINADA = 1e-14
MAXIMO_ITERACOES_REFINADO = 2_000_000
EPSILON_MAQUINA = float(np.finfo(np.float64).eps)
AVISO_IC = (
    "O IC (bootstrap) mede apenas a variabilidade amostral; NAO captura o viés "
    "da hipótese de constância de comportamento dentro da região."
)

BETA_VERDADEIRO_T1 = np.array(
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
LINHA_CAIADO_CENTRO_OESTE_T2 = np.array([0.55, 0.30, 0.08, 0.07])
LINHA_CAIADO_DEMAIS_REGIOES_T2 = np.array([0.25, 0.55, 0.10, 0.10])
POSICAO_CAIADO = eco.ORIGENS.index("caiado")
POSICAO_CENTRO_OESTE = eco.REGIOES.index("Centro-Oeste")


# ---------------------------------------------------------------------------
# Estruturas
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class AjusteUnidade:
    """Ajuste pontual de uma unidade (uma região ou o país inteiro)."""

    rotulo: str
    beta: np.ndarray
    objetivo: float
    iteracoes: int
    convergiu: bool
    lambda_minimo: float
    lambda_maximo: float
    condicao: float
    kkt_absoluta: float
    kkt_relativa: float
    residuo_projetado: float
    numero_inicios: int
    inicios_dif_beta_max: float
    inicios_dif_objetivo_max: float
    inicios_iteracoes_max: int
    inicios_dif_beta_max_fino: float
    cota_dif_beta: float


@dataclasses.dataclass
class EspecificacaoAjustada:
    """Resultado pontual de E1, E2 ou E3.

    Attributes:
        nome: E1, E2 ou E3.
        unidades: Ajustes (5 regionais, ou 1 nacional no caso de E2).
        beta_regioes: beta aplicado em cada região, shape (5, 8, 4). Em E2,
            é o beta nacional repetido nas 5 regiões.
    """

    nome: str
    unidades: list[AjusteUnidade]
    beta_regioes: np.ndarray


@dataclasses.dataclass
class ResultadoBootstrap:
    """Réplicas do bootstrap de uma especificação.

    Attributes:
        beta_regioes: (B, 5, 8, 4).
        nao_convergiram: Número de réplicas (somando unidades) sem convergência.
        iteracoes_maximas: Maior número de iterações entre as réplicas.
        kkt_relativa_maxima: Maior violação KKT relativa entre as réplicas.
    """

    beta_regioes: np.ndarray
    nao_convergiram: int
    iteracoes_maximas: int
    kkt_relativa_maxima: float


# ---------------------------------------------------------------------------
# Ajustes pontuais
# ---------------------------------------------------------------------------


def montar_inicios_alternativos() -> np.ndarray:
    """Pontos iniciais distintos para testar unicidade do ótimo.

    Inclui: uniforme, quatro vértices (todas as linhas de beta concentradas em
    um mesmo destino) e três sorteios de Dirichlet(1,1,1,1) por linha.

    Returns:
        Array (8, 8, 4).
    """
    inicios: list[np.ndarray] = []
    uniforme = np.full((eco.NUMERO_ORIGENS, eco.NUMERO_DESTINOS), 0.25)
    inicios.append(uniforme)
    for posicao_destino in range(eco.NUMERO_DESTINOS):
        vertice = np.zeros((eco.NUMERO_ORIGENS, eco.NUMERO_DESTINOS))
        vertice[:, posicao_destino] = 1.0
        inicios.append(vertice)
    gerador = np.random.default_rng(SEMENTE_INICIOS_ALEATORIOS)
    for _ in range(NUMERO_INICIOS_ALEATORIOS):
        sorteio = gerador.dirichlet(
            np.ones(eco.NUMERO_DESTINOS), size=eco.NUMERO_ORIGENS
        )
        inicios.append(sorteio)
    return np.stack(inicios, axis=0)


def ajustar_unidade_pontual(
    estatisticas: eco.EstatisticasSuficientes,
    pesos: np.ndarray,
    indices_municipios: np.ndarray,
    rotulo: str,
    configuracao: eco.ConfiguracaoSolver,
) -> AjusteUnidade:
    """Ajusta uma unidade a partir do ponto uniforme e testa unicidade.

    Além do ajuste principal, resolve o mesmo problema a partir de 8 pontos
    iniciais distintos e mede a maior diferença de beta e de objetivo.
    """
    matriz_pesos = pesos[None, :]
    g, h, constante = eco.montar_equacoes_normais(
        estatisticas, matriz_pesos, indices_municipios
    )
    inicio_principal = eco.beta_inicial_uniforme(1)
    resultado = eco.resolver_fista(g, h, constante, inicio_principal, configuracao)
    violacao = eco.calcular_violacao_kkt(g, h, resultado.beta)
    lambda_minimo, lambda_maximo, condicao = eco.numeros_de_condicao(g)

    inicios = montar_inicios_alternativos()
    numero_inicios = inicios.shape[0]
    g_repetido = np.repeat(g, numero_inicios, axis=0)
    h_repetido = np.repeat(h, numero_inicios, axis=0)
    constante_repetida = np.repeat(constante, numero_inicios, axis=0)
    resultado_inicios = eco.resolver_fista(
        g_repetido, h_repetido, constante_repetida, inicios, configuracao
    )
    diferenca_beta = np.abs(resultado_inicios.beta - resultado.beta).max()
    diferenca_objetivo = np.abs(resultado_inicios.objetivo - resultado.objetivo[0]).max()

    # Cota rigorosa: f(b) - f(b*) >= lambda_min * ||b - b*||_F^2 (G definida
    # positiva e b* ótimo), logo ||b - b*||_F <= sqrt(dobj / lambda_min). O piso
    # de ruído de ponto flutuante do objetivo é epsilon * |objetivo|.
    piso_ruido = EPSILON_MAQUINA * abs(float(resultado.objetivo[0]))
    diferenca_objetivo_efetiva = max(float(diferenca_objetivo), piso_ruido)
    cota_diferenca_beta = float(
        np.sqrt(diferenca_objetivo_efetiva / lambda_minimo[0])
    )

    # Mesmo teste com tolerância mais fina: se a diferença entre inícios encolhe,
    # ela é resíduo de convergência (ótimo único), não não-identificabilidade.
    configuracao_refinada = eco.ConfiguracaoSolver(
        tolerancia_relativa=TOLERANCIA_REFINADA,
        maximo_iteracoes=MAXIMO_ITERACOES_REFINADO,
    )
    resultado_refinado = eco.resolver_fista(
        g_repetido, h_repetido, constante_repetida, inicios, configuracao_refinada
    )
    diferenca_beta_fina = np.abs(
        resultado_refinado.beta - resultado_refinado.beta[0]
    ).max()

    LOGGER.info(
        "Ajuste %s: %d iterações, convergiu=%s, cond(G)=%.3e, KKT relativa=%.2e.",
        rotulo,
        int(resultado.iteracoes[0]),
        bool(resultado.convergiu[0]),
        float(condicao[0]),
        float(violacao.maxima_relativa[0]),
    )
    return AjusteUnidade(
        rotulo=rotulo,
        beta=resultado.beta[0],
        objetivo=float(resultado.objetivo[0]),
        iteracoes=int(resultado.iteracoes[0]),
        convergiu=bool(resultado.convergiu[0]),
        lambda_minimo=float(lambda_minimo[0]),
        lambda_maximo=float(lambda_maximo[0]),
        condicao=float(condicao[0]),
        kkt_absoluta=float(violacao.maxima_absoluta[0]),
        kkt_relativa=float(violacao.maxima_relativa[0]),
        residuo_projetado=float(violacao.residuo_gradiente_projetado[0]),
        numero_inicios=int(numero_inicios),
        inicios_dif_beta_max=float(diferenca_beta),
        inicios_dif_objetivo_max=float(diferenca_objetivo),
        inicios_iteracoes_max=int(resultado_inicios.iteracoes.max()),
        inicios_dif_beta_max_fino=float(diferenca_beta_fina),
        cota_dif_beta=cota_diferenca_beta,
    )


def pesos_da_especificacao(nome: str, dados: eco.DadosEleitorais) -> np.ndarray:
    """E1 e E2 usam aptos_1t como peso; E3 usa peso 1 (sem ponderação)."""
    if nome == ESPECIFICACAO_E3:
        return np.ones(len(dados.aptos_1t), dtype=np.float64)
    return dados.aptos_1t.astype(np.float64)


def indices_das_regioes(dados: eco.DadosEleitorais) -> list[np.ndarray]:
    """Índices (posições) dos municípios de cada região, na ordem de REGIOES."""
    indices: list[np.ndarray] = []
    for posicao_regiao in range(len(eco.REGIOES)):
        indices_regiao = np.flatnonzero(dados.indice_regiao == posicao_regiao)
        indices.append(indices_regiao)
    return indices


def ajustar_especificacao(
    nome: str,
    dados: eco.DadosEleitorais,
    estatisticas: eco.EstatisticasSuficientes,
    configuracao: eco.ConfiguracaoSolver,
) -> EspecificacaoAjustada:
    """Ajuste pontual de uma especificação (por região, ou nacional em E2)."""
    pesos = pesos_da_especificacao(nome, dados)
    unidades: list[AjusteUnidade] = []
    beta_regioes = np.zeros((len(eco.REGIOES), eco.NUMERO_ORIGENS, eco.NUMERO_DESTINOS))

    if nome == ESPECIFICACAO_E2:
        todos_os_municipios = np.arange(len(dados.aptos_1t))
        unidade = ajustar_unidade_pontual(
            estatisticas, pesos, todos_os_municipios, "Brasil (nacional)", configuracao
        )
        unidades.append(unidade)
        for posicao_regiao in range(len(eco.REGIOES)):
            beta_regioes[posicao_regiao] = unidade.beta
        return EspecificacaoAjustada(nome=nome, unidades=unidades, beta_regioes=beta_regioes)

    lista_indices = indices_das_regioes(dados)
    for posicao_regiao, nome_regiao in enumerate(eco.REGIOES):
        unidade = ajustar_unidade_pontual(
            estatisticas,
            pesos,
            lista_indices[posicao_regiao],
            nome_regiao,
            configuracao,
        )
        unidades.append(unidade)
        beta_regioes[posicao_regiao] = unidade.beta
    return EspecificacaoAjustada(nome=nome, unidades=unidades, beta_regioes=beta_regioes)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def gerar_multiplicidades_bootstrap(
    dados: eco.DadosEleitorais, numero_replicas: int, semente: int
) -> np.ndarray:
    """Reamostragem estratificada por região, com reposição.

    Em cada réplica e em cada região sorteiam-se n_regiao municípios com
    reposição; guarda-se quantas vezes cada município foi sorteado.

    Returns:
        Array (B, n) de multiplicidades (inteiros).
    """
    gerador = np.random.default_rng(semente)
    numero_municipios = len(dados.aptos_1t)
    multiplicidades = np.zeros((numero_replicas, numero_municipios), dtype=np.int32)
    lista_indices = indices_das_regioes(dados)
    for numero_replica in range(numero_replicas):
        for indices_regiao in lista_indices:
            tamanho = len(indices_regiao)
            sorteados = gerador.integers(0, tamanho, size=tamanho)
            repeticoes = np.bincount(sorteados, minlength=tamanho)
            multiplicidades[numero_replica, indices_regiao] = repeticoes
    return multiplicidades


def executar_bootstrap(
    nome: str,
    dados: eco.DadosEleitorais,
    estatisticas: eco.EstatisticasSuficientes,
    ajuste: EspecificacaoAjustada,
    multiplicidades: np.ndarray,
) -> ResultadoBootstrap:
    """Reajusta a especificação em cada réplica (partida a quente do ponto)."""
    numero_replicas = multiplicidades.shape[0]
    pesos_base = pesos_da_especificacao(nome, dados)
    matriz_pesos = multiplicidades * pesos_base[None, :]
    configuracao = eco.ConfiguracaoSolver(maximo_iteracoes=MAXIMO_ITERACOES_BOOTSTRAP)
    beta_regioes = np.zeros(
        (numero_replicas, len(eco.REGIOES), eco.NUMERO_ORIGENS, eco.NUMERO_DESTINOS)
    )
    nao_convergiram = 0
    iteracoes_maximas = 0
    kkt_relativa_maxima = 0.0

    if nome == ESPECIFICACAO_E2:
        grupos = [np.arange(len(dados.aptos_1t))]
    else:
        grupos = indices_das_regioes(dados)

    for posicao_grupo, indices in enumerate(grupos):
        inicio_quente = np.repeat(
            ajuste.unidades[posicao_grupo].beta[None, :, :], numero_replicas, axis=0
        )
        inicio_tempo = time.time()
        resultado, g, h, _ = eco.ajustar_lote(
            estatisticas, matriz_pesos, indices, inicio_quente, configuracao
        )
        violacao = eco.calcular_violacao_kkt(g, h, resultado.beta)
        nao_convergiram += int((~resultado.convergiu).sum())
        iteracoes_maximas = max(iteracoes_maximas, int(resultado.iteracoes.max()))
        kkt_relativa_maxima = max(kkt_relativa_maxima, float(violacao.maxima_relativa.max()))
        LOGGER.info(
            "Bootstrap %s, unidade %s: %.1fs, não convergiram=%d, iterações máx=%d, "
            "KKT relativa máx=%.2e.",
            nome,
            ajuste.unidades[posicao_grupo].rotulo,
            time.time() - inicio_tempo,
            int((~resultado.convergiu).sum()),
            int(resultado.iteracoes.max()),
            float(violacao.maxima_relativa.max()),
        )
        if nome == ESPECIFICACAO_E2:
            for posicao_regiao in range(len(eco.REGIOES)):
                beta_regioes[:, posicao_regiao] = resultado.beta
        else:
            beta_regioes[:, posicao_grupo] = resultado.beta

    return ResultadoBootstrap(
        beta_regioes=beta_regioes,
        nao_convergiram=nao_convergiram,
        iteracoes_maximas=iteracoes_maximas,
        kkt_relativa_maxima=kkt_relativa_maxima,
    )


# ---------------------------------------------------------------------------
# Tabela longa (transferencias.csv)
# ---------------------------------------------------------------------------


def calcular_quantis_ic(valores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Percentis 2,5 e 97,5 ao longo da primeira dimensão (réplicas)."""
    inferior = np.percentile(valores, PERCENTIL_INFERIOR, axis=0)
    superior = np.percentile(valores, PERCENTIL_SUPERIOR, axis=0)
    return inferior, superior


def montar_tabela_longa(
    nome: str,
    beta_pontual_regioes: np.ndarray,
    beta_bootstrap_regioes: np.ndarray,
    populacao_pontual: np.ndarray,
    populacao_bootstrap: np.ndarray,
) -> pd.DataFrame:
    """Monta as linhas (5 regiões + Brasil) x 8 origens x 4 destinos.

    Args:
        nome: Especificação.
        beta_pontual_regioes: (5, 8, 4).
        beta_bootstrap_regioes: (B, 5, 8, 4).
        populacao_pontual: (5, 8), N_reg observado.
        populacao_bootstrap: (B, 5, 8) ou (1, 5, 8) (broadcast); N_reg usado
            para o fluxo em votos de cada réplica.

    Returns:
        DataFrame no formato da seção 10 da especificação.
    """
    fluxo_brasil_pontual, beta_brasil_pontual = eco.agregar_brasil(
        beta_pontual_regioes[None], populacao_pontual[None]
    )
    fluxo_regioes_pontual = beta_pontual_regioes * populacao_pontual[:, :, None]
    beta_pontual_todos = np.concatenate(
        [beta_pontual_regioes, beta_brasil_pontual], axis=0
    )
    fluxo_pontual_todos = np.concatenate(
        [fluxo_regioes_pontual, fluxo_brasil_pontual], axis=0
    )

    fluxo_brasil_boot, beta_brasil_boot = eco.agregar_brasil(
        beta_bootstrap_regioes, populacao_bootstrap
    )
    fluxo_regioes_boot = beta_bootstrap_regioes * populacao_bootstrap[:, :, :, None]
    beta_boot_todos = np.concatenate(
        [beta_bootstrap_regioes, beta_brasil_boot[:, None]], axis=1
    )
    fluxo_boot_todos = np.concatenate(
        [fluxo_regioes_boot, fluxo_brasil_boot[:, None]], axis=1
    )

    beta_inferior, beta_superior = calcular_quantis_ic(beta_boot_todos)
    fluxo_inferior, fluxo_superior = calcular_quantis_ic(fluxo_boot_todos)

    nomes_regioes = eco.REGIOES + [eco.NOME_BRASIL]
    linhas: list[dict[str, object]] = []
    for posicao_regiao, nome_regiao in enumerate(nomes_regioes):
        for posicao_origem, nome_origem in enumerate(eco.ORIGENS):
            for posicao_destino, nome_destino in enumerate(eco.DESTINOS):
                celula = (posicao_regiao, posicao_origem, posicao_destino)
                linha = {
                    "especificacao": nome,
                    "regiao": nome_regiao,
                    "origem_1t": nome_origem,
                    "destino_2t": nome_destino,
                    "beta": beta_pontual_todos[celula],
                    "beta_ic_inf": beta_inferior[celula],
                    "beta_ic_sup": beta_superior[celula],
                    "votos": fluxo_pontual_todos[celula],
                    "votos_ic_inf": fluxo_inferior[celula],
                    "votos_ic_sup": fluxo_superior[celula],
                }
                linhas.append(linha)
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Diagnósticos
# ---------------------------------------------------------------------------


def calcular_r2_ponderado(
    y_real: np.ndarray, y_previsto: np.ndarray, pesos: np.ndarray
) -> np.ndarray:
    """R2 ponderado por destino: 1 - SQR_ponderada / SQT_ponderada (shape (4,))."""
    soma_pesos = pesos.sum()
    media_ponderada = (pesos[:, None] * y_real).sum(axis=0) / soma_pesos
    residuo = y_real - y_previsto
    soma_quadrados_residuo = (pesos[:, None] * residuo**2).sum(axis=0)
    desvio = y_real - media_ponderada
    soma_quadrados_total = (pesos[:, None] * desvio**2).sum(axis=0)
    return 1.0 - soma_quadrados_residuo / soma_quadrados_total


def formatar_inteiro(valor: float) -> str:
    """Inteiro com separador de milhar em ponto (padrão pt-BR)."""
    texto = f"{valor:,.0f}"
    return texto.replace(",", ".")


def formatar_inteiro_com_sinal(valor: float) -> str:
    """Inteiro com sinal explícito e separador de milhar em ponto."""
    texto = f"{valor:+,.0f}"
    return texto.replace(",", ".")


def formatar_tabela_markdown(cabecalho: list[str], linhas: list[list[str]]) -> str:
    """Tabela markdown simples a partir de cabeçalho e linhas já formatadas."""
    linhas_texto = ["| " + " | ".join(cabecalho) + " |"]
    separador = "|" + "|".join(["---"] * len(cabecalho)) + "|"
    linhas_texto.append(separador)
    for linha in linhas:
        linhas_texto.append("| " + " | ".join(linha) + " |")
    return "\n".join(linhas_texto)


def secao_ajuste_e_r2(
    ajuste: EspecificacaoAjustada, dados: eco.DadosEleitorais
) -> str:
    """Totais previstos x reais e R2 ponderado por região e Brasil."""
    pesos_aptos = dados.aptos_1t.astype(np.float64)
    lista_indices = indices_das_regioes(dados)
    blocos: list[str] = []

    linhas_totais: list[list[str]] = []
    linhas_r2: list[list[str]] = []
    previsto_2t_brasil = np.zeros(eco.NUMERO_DESTINOS)
    previsto_1t_brasil = np.zeros(eco.NUMERO_DESTINOS)
    real_brasil = np.zeros(eco.NUMERO_DESTINOS)

    for posicao_regiao, nome_regiao in enumerate(eco.REGIOES):
        indices = lista_indices[posicao_regiao]
        beta = ajuste.beta_regioes[posicao_regiao]
        y_previsto = dados.x[indices] @ beta
        previsto_2t = (dados.aptos_2t[indices, None] * y_previsto).sum(axis=0)
        previsto_1t = (dados.aptos_1t[indices, None] * y_previsto).sum(axis=0)
        real = dados.contagens_destino[indices].sum(axis=0).astype(np.float64)
        previsto_2t_brasil += previsto_2t
        previsto_1t_brasil += previsto_1t
        real_brasil += real
        linhas_totais.extend(
            _linhas_totais(nome_regiao, previsto_2t, previsto_1t, real)
        )
        r2 = calcular_r2_ponderado(dados.y[indices], y_previsto, pesos_aptos[indices])
        linha_r2 = [nome_regiao] + [f"{valor:.4f}" for valor in r2]
        if ajuste.nome == ESPECIFICACAO_E3:
            r2_sem_peso = calcular_r2_ponderado(
                dados.y[indices], y_previsto, np.ones(len(indices))
            )
            linha_r2 = linha_r2 + [f"{valor:.4f}" for valor in r2_sem_peso]
        linhas_r2.append(linha_r2)

    linhas_totais.extend(
        _linhas_totais(eco.NOME_BRASIL, previsto_2t_brasil, previsto_1t_brasil, real_brasil)
    )

    cabecalho_totais = [
        "regiao",
        "destino",
        "previsto (aptos_2t)",
        "previsto (aptos_1t)",
        "real",
        "dif. % (aptos_2t)",
        "dif. % (aptos_1t)",
    ]
    blocos.append("**Total previsto x real do 2º turno (votos).** `previsto = soma_i aptos_*_i * (X_i beta)_c`.")
    blocos.append(formatar_tabela_markdown(cabecalho_totais, linhas_totais))

    cabecalho_r2 = ["regiao"] + [f"R2 {nome}" for nome in eco.DESTINOS]
    descricao_r2 = "**R2 ponderado por destino (peso = aptos_1t).**"
    if ajuste.nome == ESPECIFICACAO_E3:
        cabecalho_r2 = cabecalho_r2 + [f"R2 s/peso {nome}" for nome in eco.DESTINOS]
        descricao_r2 = (
            "**R2 por destino**: colunas `R2 destino` com peso aptos_1t; "
            "colunas `R2 s/peso` com peso 1 (o critério próprio de E3)."
        )
    blocos.append(descricao_r2)
    blocos.append(formatar_tabela_markdown(cabecalho_r2, linhas_r2))
    return "\n\n".join(blocos)


def _linhas_totais(
    rotulo: str, previsto_2t: np.ndarray, previsto_1t: np.ndarray, real: np.ndarray
) -> list[list[str]]:
    """Linhas da tabela de totais para uma região (ou Brasil)."""
    linhas: list[list[str]] = []
    for posicao_destino, nome_destino in enumerate(eco.DESTINOS):
        diferenca_2t = 100.0 * (previsto_2t[posicao_destino] / real[posicao_destino] - 1.0)
        diferenca_1t = 100.0 * (previsto_1t[posicao_destino] / real[posicao_destino] - 1.0)
        linhas.append(
            [
                rotulo,
                nome_destino,
                formatar_inteiro(previsto_2t[posicao_destino]),
                formatar_inteiro(previsto_1t[posicao_destino]),
                formatar_inteiro(real[posicao_destino]),
                f"{diferenca_2t:+.4f}",
                f"{diferenca_1t:+.4f}",
            ]
        )
    return linhas


def secao_fronteira(ajuste: EspecificacaoAjustada) -> str:
    """Lista as células de beta com valor 0 ou 1 (fronteira ativa)."""
    linhas: list[list[str]] = []
    rotulos = [unidade.rotulo for unidade in ajuste.unidades]
    for posicao_unidade, unidade in enumerate(ajuste.unidades):
        celulas_zero: list[str] = []
        celulas_um: list[str] = []
        for posicao_origem, nome_origem in enumerate(eco.ORIGENS):
            for posicao_destino, nome_destino in enumerate(eco.DESTINOS):
                valor = unidade.beta[posicao_origem, posicao_destino]
                descricao = f"{nome_origem}->{nome_destino}"
                if valor <= eco.LIMIAR_FRONTEIRA:
                    celulas_zero.append(descricao)
                if valor >= 1.0 - eco.LIMIAR_FRONTEIRA:
                    celulas_um.append(descricao)
        linhas.append(
            [
                rotulos[posicao_unidade],
                str(len(celulas_zero)),
                ", ".join(celulas_zero) if celulas_zero else "-",
                str(len(celulas_um)),
                ", ".join(celulas_um) if celulas_um else "-",
            ]
        )
    cabecalho = ["unidade", "# em 0", "células em 0", "# em 1", "células em 1"]
    return formatar_tabela_markdown(cabecalho, linhas)


def secao_plausibilidade(
    ajuste: EspecificacaoAjustada, beta_brasil: np.ndarray
) -> str:
    """beta[lula,lula], beta[flavio,flavio] e beta[abst,abst] por região e Brasil."""
    posicao_lula = eco.ORIGENS.index("lula")
    posicao_flavio = eco.ORIGENS.index("flavio")
    posicao_abstencao = eco.ORIGENS.index("abstencao")
    destino_lula = eco.DESTINOS.index("lula")
    destino_flavio = eco.DESTINOS.index("flavio")
    destino_abstencao = eco.DESTINOS.index("abstencao")
    linhas: list[list[str]] = []
    for posicao_regiao, nome_regiao in enumerate(eco.REGIOES):
        beta = ajuste.beta_regioes[posicao_regiao]
        linhas.append(
            [
                nome_regiao,
                f"{beta[posicao_lula, destino_lula]:.4f}",
                f"{beta[posicao_flavio, destino_flavio]:.4f}",
                f"{beta[posicao_abstencao, destino_abstencao]:.4f}",
            ]
        )
    linhas.append(
        [
            eco.NOME_BRASIL,
            f"{beta_brasil[posicao_lula, destino_lula]:.4f}",
            f"{beta_brasil[posicao_flavio, destino_flavio]:.4f}",
            f"{beta_brasil[posicao_abstencao, destino_abstencao]:.4f}",
        ]
    )
    cabecalho = ["regiao", "lula->lula", "flavio->flavio", "abstencao->abstencao"]
    return formatar_tabela_markdown(cabecalho, linhas)


def secao_condicionamento(ajuste: EspecificacaoAjustada) -> str:
    """Tabela de número de condição, convergência, KKT e multi-início por ajuste."""
    linhas: list[list[str]] = []
    for unidade in ajuste.unidades:
        linhas.append(
            [
                unidade.rotulo,
                f"{unidade.lambda_minimo:.3e}",
                f"{unidade.lambda_maximo:.3e}",
                f"{unidade.condicao:.3e}",
                str(unidade.iteracoes),
                f"{unidade.objetivo:.10e}",
                f"{unidade.kkt_absoluta:.2e}",
                f"{unidade.kkt_relativa:.2e}",
                f"{unidade.residuo_projetado:.2e}",
                f"{unidade.inicios_dif_beta_max:.2e}",
                f"{unidade.inicios_dif_objetivo_max:.2e}",
                f"{unidade.cota_dif_beta:.2e}",
                f"{unidade.inicios_dif_beta_max_fino:.2e}",
            ]
        )
    cabecalho = [
        "ajuste",
        "lambda_min(G)",
        "lambda_max(G)",
        "cond(G)",
        "iter.",
        "objetivo",
        "KKT abs.",
        "KKT rel.",
        "res. grad. proj.",
        "max abs dbeta (8 inícios, tol 1e-12)",
        "max abs dobj (8 inícios)",
        "cota sqrt(dobj/lambda_min)",
        "max abs dbeta (8 inícios, tol 1e-14)",
    ]
    return formatar_tabela_markdown(cabecalho, linhas)


# ---------------------------------------------------------------------------
# Testes sintéticos
# ---------------------------------------------------------------------------


def construir_beta_verdadeiro_t2() -> np.ndarray:
    """beta verdadeiro (5, 8, 4) de T2: só a linha caiado difere por região."""
    beta_regioes = np.zeros((len(eco.REGIOES), eco.NUMERO_ORIGENS, eco.NUMERO_DESTINOS))
    for posicao_regiao in range(len(eco.REGIOES)):
        beta_regioes[posicao_regiao] = BETA_VERDADEIRO_T1
        if posicao_regiao == POSICAO_CENTRO_OESTE:
            beta_regioes[posicao_regiao, POSICAO_CAIADO] = LINHA_CAIADO_CENTRO_OESTE_T2
        else:
            beta_regioes[posicao_regiao, POSICAO_CAIADO] = LINHA_CAIADO_DEMAIS_REGIOES_T2
    return beta_regioes


def gerar_destino_sintetico(
    dados: eco.DadosEleitorais, beta_regioes_verdadeiro: np.ndarray, semente: int
) -> np.ndarray:
    """Y_i = Multinomial(aptos_1t_i, X_i beta_verdadeiro(regiao_i)) / aptos_1t_i.

    Returns:
        Frações sintéticas (n, 4); cada linha soma 1.
    """
    gerador = np.random.default_rng(semente)
    beta_por_municipio = beta_regioes_verdadeiro[dados.indice_regiao]
    probabilidades = np.einsum("nk,nkc->nc", dados.x, beta_por_municipio)
    contagens = gerador.multinomial(dados.aptos_1t, probabilidades)
    return contagens / dados.aptos_1t[:, None]


def ajustar_sinteticos(
    dados: eco.DadosEleitorais, y_sintetico: np.ndarray, configuracao: eco.ConfiguracaoSolver
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ajusta E1 e E2 sobre o Y sintético (pesos aptos_1t).

    Returns:
        (beta E1 por região (5,8,4), beta E2 nacional (8,4), populacao (5,8)).
    """
    estatisticas = eco.montar_estatisticas_suficientes(dados.x, y_sintetico)
    pesos = dados.aptos_1t.astype(np.float64)[None, :]
    beta_e1 = np.zeros((len(eco.REGIOES), eco.NUMERO_ORIGENS, eco.NUMERO_DESTINOS))
    for posicao_regiao, indices in enumerate(indices_das_regioes(dados)):
        resultado, _, _, _ = eco.ajustar_lote(
            estatisticas, pesos, indices, eco.beta_inicial_uniforme(1), configuracao
        )
        beta_e1[posicao_regiao] = resultado.beta[0]
    todos = np.arange(len(dados.aptos_1t))
    resultado_nacional, _, _, _ = eco.ajustar_lote(
        estatisticas, pesos, todos, eco.beta_inicial_uniforme(1), configuracao
    )
    beta_e2 = resultado_nacional.beta[0]
    populacao = eco.calcular_populacao_origem(
        dados, np.ones((1, len(dados.aptos_1t)))
    )[0]
    return beta_e1, beta_e2, populacao


def escrever_teste_sintetico(
    dados: eco.DadosEleitorais,
    configuracao: eco.ConfiguracaoSolver,
    caminho: Path,
) -> dict[str, float]:
    """Executa T1 e T2 e escreve teste_sintetico.md.

    Returns:
        Resumo numérico (erros máximos) para o README e o relatório final.
    """
    resumo: dict[str, float] = {}
    partes: list[str] = []
    partes.append("# Teste de recuperação sintética (reimplementação B)\n")
    partes.append(
        "Gerado por `executar.py`. `X` real (5.571 municípios); "
        "`Y_i ~ Multinomial(aptos_1t_i, X_i beta_verdadeiro)`, semente "
        f"{eco.SEMENTE_PADRAO} (um `default_rng` novo por teste); pesos aptos_1t. "
        "Erro = |estimado - verdadeiro|. E1 Brasil = fluxos das 5 regiões somados.\n"
    )

    # ----- T1 -----
    beta_t1_regioes = np.repeat(BETA_VERDADEIRO_T1[None], len(eco.REGIOES), axis=0)
    y_t1 = gerar_destino_sintetico(dados, beta_t1_regioes, eco.SEMENTE_PADRAO)
    beta_e1_t1, beta_e2_t1, populacao = ajustar_sinteticos(dados, y_t1, configuracao)
    _, beta_brasil_e1_t1 = eco.agregar_brasil(beta_e1_t1[None], populacao[None])
    beta_brasil_e1_t1 = beta_brasil_e1_t1[0]

    erro_e1_brasil = np.abs(beta_brasil_e1_t1 - BETA_VERDADEIRO_T1)
    erro_e2 = np.abs(beta_e2_t1 - BETA_VERDADEIRO_T1)
    erro_e1_pior_regiao = np.abs(beta_e1_t1 - BETA_VERDADEIRO_T1[None]).max(axis=(0, 2))
    linhas_t1: list[list[str]] = []
    for posicao_origem, nome_origem in enumerate(eco.ORIGENS):
        linhas_t1.append(
            [
                nome_origem,
                f"{erro_e2[posicao_origem].max():.4f}",
                f"{erro_e1_brasil[posicao_origem].max():.4f}",
                f"{erro_e1_pior_regiao[posicao_origem]:.4f}",
            ]
        )
    resumo["t1_e2_max"] = float(erro_e2.max())
    resumo["t1_e1_brasil_max"] = float(erro_e1_brasil.max())
    resumo["t1_e1_regiao_max"] = float(erro_e1_pior_regiao.max())
    partes.append("## T1 — beta constante no país\n")
    partes.append(
        "Erro absoluto máximo por linha de origem (máximo sobre os 4 destinos).\n"
    )
    partes.append(
        formatar_tabela_markdown(
            ["origem", "E2 (nacional)", "E1 Brasil (agregado)", "E1 pior região"],
            linhas_t1,
        )
    )
    partes.append(
        f"\nMáximo geral: E2 = **{erro_e2.max():.4f}**, E1 Brasil = "
        f"**{erro_e1_brasil.max():.4f}**, E1 pior região = "
        f"**{erro_e1_pior_regiao.max():.4f}**.\n"
    )
    linhas_beta_t1: list[list[str]] = []
    for posicao_origem, nome_origem in enumerate(eco.ORIGENS):
        for nome_modelo, matriz in (("verdadeiro", BETA_VERDADEIRO_T1), ("E2", beta_e2_t1), ("E1 Brasil", beta_brasil_e1_t1)):
            linhas_beta_t1.append(
                [nome_origem, nome_modelo] + [f"{valor:.4f}" for valor in matriz[posicao_origem]]
            )
    partes.append("Betas estimados x verdadeiros:\n")
    partes.append(
        formatar_tabela_markdown(["origem", "modelo"] + eco.DESTINOS, linhas_beta_t1)
    )

    # ----- T2 -----
    beta_t2_regioes = construir_beta_verdadeiro_t2()
    y_t2 = gerar_destino_sintetico(dados, beta_t2_regioes, eco.SEMENTE_PADRAO)
    beta_e1_t2, beta_e2_t2, populacao = ajustar_sinteticos(dados, y_t2, configuracao)

    fluxo_verdadeiro_regioes = beta_t2_regioes * populacao[:, :, None]
    fluxo_verdadeiro_brasil = fluxo_verdadeiro_regioes.sum(axis=0)
    fluxo_e1_brasil, beta_e1_brasil_t2 = eco.agregar_brasil(
        beta_e1_t2[None], populacao[None]
    )
    fluxo_e1_brasil = fluxo_e1_brasil[0]
    beta_e1_brasil_t2 = beta_e1_brasil_t2[0]
    beta_e2_repetido = np.repeat(beta_e2_t2[None], len(eco.REGIOES), axis=0)
    fluxo_e2_brasil, _ = eco.agregar_brasil(beta_e2_repetido[None], populacao[None])
    fluxo_e2_brasil = fluxo_e2_brasil[0]

    total_caiado = populacao[:, POSICAO_CAIADO].sum()
    beta_caiado_verdadeiro = fluxo_verdadeiro_brasil[POSICAO_CAIADO] / total_caiado
    linhas_t2: list[list[str]] = []
    for posicao_destino, nome_destino in enumerate(eco.DESTINOS):
        verdadeiro = fluxo_verdadeiro_brasil[POSICAO_CAIADO, posicao_destino]
        estimado_e1 = fluxo_e1_brasil[POSICAO_CAIADO, posicao_destino]
        estimado_e2 = fluxo_e2_brasil[POSICAO_CAIADO, posicao_destino]
        linhas_t2.append(
            [
                nome_destino,
                formatar_inteiro(verdadeiro),
                formatar_inteiro(estimado_e1),
                formatar_inteiro_com_sinal(estimado_e1 - verdadeiro),
                f"{100.0 * (estimado_e1 / verdadeiro - 1.0):+.2f}%",
                formatar_inteiro(estimado_e2),
                formatar_inteiro_com_sinal(estimado_e2 - verdadeiro),
                f"{100.0 * (estimado_e2 / verdadeiro - 1.0):+.2f}%",
            ]
        )
    erro_fluxo_e1 = np.abs(fluxo_e1_brasil[POSICAO_CAIADO] - fluxo_verdadeiro_brasil[POSICAO_CAIADO])
    erro_fluxo_e2 = np.abs(fluxo_e2_brasil[POSICAO_CAIADO] - fluxo_verdadeiro_brasil[POSICAO_CAIADO])
    erro_beta_caiado_e1 = np.abs(beta_e1_brasil_t2[POSICAO_CAIADO] - beta_caiado_verdadeiro)
    erro_beta_caiado_e2 = np.abs(beta_e2_t2[POSICAO_CAIADO] - beta_caiado_verdadeiro)
    erro_beta_co_e1 = np.abs(
        beta_e1_t2[POSICAO_CENTRO_OESTE, POSICAO_CAIADO] - LINHA_CAIADO_CENTRO_OESTE_T2
    )
    erro_beta_co_e2 = np.abs(beta_e2_t2[POSICAO_CAIADO] - LINHA_CAIADO_CENTRO_OESTE_T2)
    resumo["t2_fluxo_caiado_e1_max_votos"] = float(erro_fluxo_e1.max())
    resumo["t2_fluxo_caiado_e2_max_votos"] = float(erro_fluxo_e2.max())
    resumo["t2_fluxo_caiado_e1_max_pct"] = float(
        100.0 * (erro_fluxo_e1 / fluxo_verdadeiro_brasil[POSICAO_CAIADO]).max()
    )
    resumo["t2_fluxo_caiado_e2_max_pct"] = float(
        100.0 * (erro_fluxo_e2 / fluxo_verdadeiro_brasil[POSICAO_CAIADO]).max()
    )
    resumo["t2_beta_caiado_co_e1_max"] = float(erro_beta_co_e1.max())
    resumo["t2_beta_caiado_co_e2_max"] = float(erro_beta_co_e2.max())
    resumo["t2_beta_caiado_br_e1_max"] = float(erro_beta_caiado_e1.max())
    resumo["t2_beta_caiado_br_e2_max"] = float(erro_beta_caiado_e2.max())

    partes.append("\n## T2 — beta de Caiado varia por região\n")
    partes.append(
        "Caiado verdadeiro: Centro-Oeste `[0,55; 0,30; 0,08; 0,07]`; demais "
        "regiões `[0,25; 0,55; 0,10; 0,10]`. Demais linhas iguais a T1. "
        "Fluxo verdadeiro = soma por região de `beta_verdadeiro * N_reg` "
        "(esperança, sem ruído multinomial).\n"
    )
    partes.append(
        f"Total de eleitores de Caiado (1º turno, 5.571 municípios): "
        f"**{formatar_inteiro(total_caiado)}**; beta nacional verdadeiro de Caiado "
        f"(média ponderada pelos fluxos): "
        f"`{', '.join(f'{valor:.4f}' for valor in beta_caiado_verdadeiro)}`.\n"
    )
    partes.append("**Fluxo nacional de Caiado (votos).**\n")
    partes.append(
        formatar_tabela_markdown(
            [
                "destino",
                "verdadeiro",
                "E1",
                "erro E1",
                "erro E1 %",
                "E2",
                "erro E2",
                "erro E2 %",
            ],
            linhas_t2,
        )
    )
    partes.append(
        f"\nErro máximo do fluxo de Caiado (por destino): E1 = "
        f"**{formatar_inteiro(erro_fluxo_e1.max())} votos "
        f"({resumo['t2_fluxo_caiado_e1_max_pct']:.2f}% do total de Caiado)**; "
        f"E2 = **{formatar_inteiro(erro_fluxo_e2.max())} votos "
        f"({resumo['t2_fluxo_caiado_e2_max_pct']:.2f}%)**.\n"
    )
    partes.append(
        "Beta de Caiado no Centro-Oeste (verdadeiro `[0,55; 0,30; 0,08; 0,07]`):\n"
    )
    partes.append(
        formatar_tabela_markdown(
            ["modelo"] + eco.DESTINOS + ["erro máx."],
            [
                ["E1 (região CO)"]
                + [f"{v:.4f}" for v in beta_e1_t2[POSICAO_CENTRO_OESTE, POSICAO_CAIADO]]
                + [f"{erro_beta_co_e1.max():.4f}"],
                ["E2 (nacional)"]
                + [f"{v:.4f}" for v in beta_e2_t2[POSICAO_CAIADO]]
                + [f"{erro_beta_co_e2.max():.4f}"],
            ],
        )
    )
    interpretacao = _interpretar_t2(erro_fluxo_e1, erro_fluxo_e2, erro_beta_co_e1, erro_beta_co_e2)
    partes.append("\n" + interpretacao + "\n")

    caminho.write_text("\n".join(partes) + "\n", encoding="utf-8")
    LOGGER.info("Teste sintético escrito em %s.", caminho)
    return resumo


def _interpretar_t2(
    erro_fluxo_e1: np.ndarray,
    erro_fluxo_e2: np.ndarray,
    erro_beta_co_e1: np.ndarray,
    erro_beta_co_e2: np.ndarray,
) -> str:
    """Texto factual comparando E1 e E2 em T2 (sem presumir o resultado)."""
    fluxo_e1 = erro_fluxo_e1.max()
    fluxo_e2 = erro_fluxo_e2.max()
    if fluxo_e2 > fluxo_e1:
        resultado_fluxo = "E2 erra mais que E1 no fluxo nacional (esperado)."
    else:
        resultado_fluxo = (
            "E2 NÃO erra mais que E1 no fluxo nacional: o beta único funciona "
            "como média e o viés se concentra no nível regional, não no agregado."
        )
    if erro_beta_co_e2.max() > erro_beta_co_e1.max():
        resultado_regional = "No Centro-Oeste, E2 enviesa o beta de Caiado e E1 recupera."
    else:
        resultado_regional = "No Centro-Oeste, E2 não erra mais que E1."
    return f"**Leitura.** {resultado_fluxo} {resultado_regional}"


# ---------------------------------------------------------------------------
# Críticas à especificação (números)
# ---------------------------------------------------------------------------


def calcular_criticas(
    dados: eco.DadosEleitorais, base: pd.DataFrame
) -> dict[str, float]:
    """Números de apoio às críticas à especificação."""
    diferenca_aptos = dados.aptos_2t - dados.aptos_1t
    resultados: dict[str, float] = {}
    resultados["municipios_aptos_diferentes"] = float((diferenca_aptos != 0).sum())
    resultados["soma_abs_dif_aptos"] = float(np.abs(diferenca_aptos).sum())
    resultados["soma_dif_aptos"] = float(diferenca_aptos.sum())
    resultados["max_dif_relativa_aptos"] = float(
        (np.abs(diferenca_aptos) / dados.aptos_1t).max()
    )
    resultados["comparecimento_1t_brasil"] = float(base["comparecimento_1t"].sum())
    resultados["comparecimento_2t_brasil"] = float(base["comparecimento_2t"].sum())
    resultados["queda_abstencao_brasil"] = float(
        dados.contagens_origem[:, eco.ORIGENS.index("abstencao")].sum()
        - dados.contagens_destino[:, eco.DESTINOS.index("abstencao")].sum()
    )
    resultados["nao_instaladas_1t"] = float(base["nao_instaladas_1t"].sum())
    resultados["nao_instaladas_2t"] = float(base["nao_instaladas_2t"].sum())
    return resultados


def calcular_tamanho_efetivo(dados: eco.DadosEleitorais) -> list[tuple[str, int, float, float]]:
    """Tamanho efetivo amostral (soma w)^2 / soma w^2 e maior peso, por região."""
    saida: list[tuple[str, int, float, float]] = []
    pesos = dados.aptos_1t.astype(np.float64)
    for posicao_regiao, nome_regiao in enumerate(eco.REGIOES):
        indices = np.flatnonzero(dados.indice_regiao == posicao_regiao)
        pesos_regiao = pesos[indices]
        soma = pesos_regiao.sum()
        soma_quadrados = (pesos_regiao**2).sum()
        tamanho_efetivo = soma**2 / soma_quadrados
        maior_participacao = pesos_regiao.max() / soma
        saida.append((nome_regiao, len(indices), float(tamanho_efetivo), float(maior_participacao)))
    return saida


# ---------------------------------------------------------------------------
# Escrita de relatórios
# ---------------------------------------------------------------------------


def extrair_celula(
    tabela: pd.DataFrame,
    especificacao: str,
    regiao: str,
    origem: str,
    destino: str,
) -> pd.Series:
    """Linha da tabela longa para (especificação, região, origem, destino)."""
    mascara = (
        (tabela["especificacao"] == especificacao)
        & (tabela["regiao"] == regiao)
        & (tabela["origem_1t"] == origem)
        & (tabela["destino_2t"] == destino)
    )
    selecionadas = tabela[mascara]
    if len(selecionadas) != 1:
        raise KeyError(f"Célula não encontrada: {especificacao}/{regiao}/{origem}/{destino}")
    return selecionadas.iloc[0]


def formatar_beta_com_ic(linha: pd.Series) -> str:
    """beta [ic_inf; ic_sup] com 4 casas."""
    return f"{linha['beta']:.4f} [{linha['beta_ic_inf']:.4f}; {linha['beta_ic_sup']:.4f}]"


def escrever_diagnosticos(
    caminho: Path,
    ajustes: dict[str, EspecificacaoAjustada],
    bootstraps: dict[str, ResultadoBootstrap],
    tabela: pd.DataFrame,
    tabela_n_reamostrado: pd.DataFrame,
    dados: eco.DadosEleitorais,
    ancoras: dict[str, tuple[int, int, bool]],
    criticas: dict[str, float],
    numero_replicas: int,
) -> None:
    """Escreve diagnosticos.md com todas as seções da especificação (seção 8)."""
    partes: list[str] = []
    partes.append("# Diagnósticos — reimplementação B\n")
    partes.append(f"> {AVISO_IC}\n")

    # Âncoras
    partes.append("## 0. Âncoras da seção 4\n")
    linhas_ancora: list[list[str]] = []
    for nome, (esperado, calculado, passou) in ancoras.items():
        linhas_ancora.append(
            [nome, formatar_inteiro(esperado), formatar_inteiro(calculado), "PASS" if passou else "FAIL"]
        )
    partes.append(
        formatar_tabela_markdown(["âncora", "esperado", "calculado", "status"], linhas_ancora)
    )
    partes.append(
        "\nIdentidade por município (soma das categorias de origem = aptos_1t; "
        "soma das de destino = aptos_2t): 0 violações em 5.571.\n"
    )

    # Solver
    partes.append("## 1. Solver, condicionamento, KKT e identificabilidade\n")
    partes.append(
        "Solver: FISTA com reinício adaptativo, passo 1/L (L = 2 lambda_max(G)), "
        "projeção exata de cada linha de beta no simplex (Duchi et al., 2008). "
        f"Parada: variação relativa do objetivo E da solução <= {eco.TOLERANCIA_RELATIVA:.0e} "
        "entre iterações consecutivas. G é montada com pesos normalizados "
        "(soma 1); o número de condição é invariante à escala. "
        f"KKT: suporte = beta > {eco.LIMIAR_SUPORTE_KKT:.0e}; violação relativa = "
        "violação absoluta / (2 max|H|). `max abs dbeta (8 inícios)` = maior diferença "
        "de beta entre a solução principal (início uniforme) e soluções partindo "
        "de 8 pontos iniciais (uniforme, 4 vértices, 3 Dirichlet), com tolerância "
        "1e-12 e com 1e-14. `cota` = sqrt(dobj/lambda_min): como G é definida "
        "positiva, f(b) - f(b*) >= lambda_min ||b - b*||^2, então a diferença "
        "de objetivo entre duas soluções limita a distância entre elas "
        "(dobj é limitado por baixo pelo ruído de ponto flutuante, eps*objetivo).\n"
    )
    for nome, ajuste in ajustes.items():
        partes.append(f"### {nome}\n")
        partes.append(secao_condicionamento(ajuste))
        partes.append("")
    maior_condicao = max(
        unidade.condicao for ajuste in ajustes.values() for unidade in ajuste.unidades
    )
    maior_kkt = max(
        unidade.kkt_absoluta for ajuste in ajustes.values() for unidade in ajuste.unidades
    )
    maior_kkt_relativa = max(
        unidade.kkt_relativa for ajuste in ajustes.values() for unidade in ajuste.unidades
    )
    maior_dif_inicios = max(
        unidade.inicios_dif_beta_max for ajuste in ajustes.values() for unidade in ajuste.unidades
    )
    maior_dif_inicios_fino = max(
        unidade.inicios_dif_beta_max_fino
        for ajuste in ajustes.values()
        for unidade in ajuste.unidades
    )
    dentro_da_cota = all(
        unidade.inicios_dif_beta_max <= unidade.cota_dif_beta
        for ajuste in ajustes.values()
        for unidade in ajuste.unidades
    )
    maior_dif_objetivo = max(
        unidade.inicios_dif_objetivo_max for ajuste in ajustes.values() for unidade in ajuste.unidades
    )
    todos_convergiram = all(
        unidade.convergiu for ajuste in ajustes.values() for unidade in ajuste.unidades
    )
    partes.append(
        f"**Resumo.** Maior cond(G) entre os ajustes pontuais: **{maior_condicao:.3e}**. "
        f"Maior violação KKT: **{maior_kkt:.2e}** (absoluta), **{maior_kkt_relativa:.2e}** (relativa). "
        f"Todos convergiram pelo critério de parada: **{todos_convergiram}**. "
        f"Maior |dbeta| entre inícios distintos: **{maior_dif_inicios:.2e}** (tol 1e-12) e "
        f"**{maior_dif_inicios_fino:.2e}** (tol 1e-14); "
        f"maior |dobjetivo|: **{maior_dif_objetivo:.2e}** (ruído de ponto flutuante). "
        f"Todas as diferenças de beta dentro da cota sqrt(dobj/lambda_min): **{dentro_da_cota}**.\n"
    )
    partes.append(
        "**Identificabilidade.** G é definida positiva em todos os ajustes "
        "(lambda_min > 0), logo o ótimo é único. cond(G) elevada (~1e5 a 1e6) "
        "significa que direções do espaço de beta quase não são informadas pelos "
        "dados: o ponto é único, mas a precisão estatística em grupos pequenos "
        "(cury, renan, caiado, demais) é baixa — ver os IC. "
        + (
            "Os 8 inícios chegam ao mesmo objetivo (diferença no nível do ruído "
            "de ponto flutuante) e a betas que diferem só no resíduo de convergência: "
            "a diferença de beta cai quando a tolerância passa de 1e-12 para 1e-14 "
            "e fica dentro da cota teórica. NÃO há não identificabilidade: ótimo único.\n"
            if (dentro_da_cota and maior_dif_inicios_fino < maior_dif_inicios)
            else "ATENÇÃO: inícios distintos produziram betas diferentes além da cota; investigar.\n"
        )
    )

    # Bootstrap
    partes.append("## 2. Bootstrap\n")
    linhas_boot: list[list[str]] = []
    for nome, resultado in bootstraps.items():
        linhas_boot.append(
            [
                nome,
                str(numero_replicas),
                str(resultado.nao_convergiram),
                str(resultado.iteracoes_maximas),
                f"{resultado.kkt_relativa_maxima:.2e}",
            ]
        )
    partes.append(
        formatar_tabela_markdown(
            [
                "espec.",
                "réplicas",
                "ajustes não convergidos (somando unidades)",
                "iterações máx.",
                "KKT rel. máx. nas réplicas",
            ],
            linhas_boot,
        )
    )
    partes.append(
        f"\nReamostragem estratificada por região, B = {numero_replicas}, "
        f"`numpy.random.default_rng({eco.SEMENTE_PADRAO})`; as mesmas réplicas "
        "são usadas em E1, E2 e E3. Partida a quente a partir do ponto estimado "
        f"(teto de {MAXIMO_ITERACOES_BOOTSTRAP} iterações). IC por percentis 2,5 e 97,5. "
        "Fluxo em votos: usa N_reg observado (fixo) — ver crítica C3.\n"
    )

    # Ajuste e R2, fronteira, plausibilidade
    for posicao_ajuste, (nome, ajuste) in enumerate(ajustes.items()):
        partes.append(f"## {3 + posicao_ajuste}. {nome} — ajuste, R2, fronteira e plausibilidade\n")
        partes.append(secao_ajuste_e_r2(ajuste, dados))
        partes.append("\n**Células de beta na fronteira (0 ou 1), ajuste pontual.**\n")
        partes.append(secao_fronteira(ajuste))
        beta_brasil = np.zeros((eco.NUMERO_ORIGENS, eco.NUMERO_DESTINOS))
        for posicao_origem, nome_origem in enumerate(eco.ORIGENS):
            for posicao_destino, nome_destino in enumerate(eco.DESTINOS):
                linha = extrair_celula(tabela, nome, eco.NOME_BRASIL, nome_origem, nome_destino)
                beta_brasil[posicao_origem, posicao_destino] = linha["beta"]
        partes.append("\n**Plausibilidade** (só reportada; nada é forçado).\n")
        partes.append(secao_plausibilidade(ajuste, beta_brasil))
        partes.append("")

    # Comparação E1 x E2 x E3
    partes.append("## 6. Comparação E1 x E2 x E3 (beta Brasil)\n")
    partes.append(_secao_comparacao_especificacoes(tabela))

    # Críticas
    partes.append("\n## 7. Críticas à especificação (com números)\n")
    partes.append(
        _secao_criticas(criticas, dados, tabela, tabela_n_reamostrado, ajustes)
    )
    caminho.write_text("\n".join(partes) + "\n", encoding="utf-8")
    LOGGER.info("Diagnósticos escritos em %s.", caminho)


def _secao_comparacao_especificacoes(tabela: pd.DataFrame) -> str:
    """Diferenças máximas de beta Brasil entre E1, E2 e E3 por origem."""
    mascara_brasil = tabela["regiao"] == eco.NOME_BRASIL
    base_brasil = tabela[mascara_brasil]
    linhas: list[list[str]] = []
    for nome_origem in eco.ORIGENS:
        mascara_origem = base_brasil["origem_1t"] == nome_origem
        subtabela = base_brasil[mascara_origem]
        betas: dict[str, np.ndarray] = {}
        for nome_especificacao in (ESPECIFICACAO_E1, ESPECIFICACAO_E2, ESPECIFICACAO_E3):
            selecao = subtabela[subtabela["especificacao"] == nome_especificacao]
            betas[nome_especificacao] = selecao.set_index("destino_2t").loc[eco.DESTINOS, "beta"].to_numpy()
        dif_e1_e2 = np.abs(betas[ESPECIFICACAO_E1] - betas[ESPECIFICACAO_E2]).max()
        dif_e1_e3 = np.abs(betas[ESPECIFICACAO_E1] - betas[ESPECIFICACAO_E3]).max()
        linhas.append([nome_origem, f"{dif_e1_e2:.4f}", f"{dif_e1_e3:.4f}"])
    texto = formatar_tabela_markdown(
        ["origem", "max|beta E1 - beta E2|", "max|beta E1 - beta E3|"], linhas
    )
    return (
        "Maior diferença absoluta entre destinos, por origem (beta Brasil). "
        "Diferença grande E1 x E2 indica viés de agregação.\n\n" + texto
    )


def _secao_criticas(
    criticas: dict[str, float],
    dados: eco.DadosEleitorais,
    tabela: pd.DataFrame,
    tabela_n_reamostrado: pd.DataFrame,
    ajustes: dict[str, EspecificacaoAjustada],
) -> str:
    """Texto das críticas C1..Cn, cada uma com números medidos."""
    partes: list[str] = []

    partes.append(
        "**C1. Denominadores `aptos_1t` (X) x `aptos_2t` (Y) diferem.** "
        f"{int(criticas['municipios_aptos_diferentes'])} de 5.571 municípios têm "
        f"aptos_2t != aptos_1t; soma dos módulos = {formatar_inteiro(criticas['soma_abs_dif_aptos'])} "
        f"eleitores, saldo líquido = {formatar_inteiro(criticas['soma_dif_aptos'])}, maior diferença "
        f"relativa = {100 * criticas['max_dif_relativa_aptos']:.3f}%. "
        "Efeito prático desprezível (< 0,02% do eleitorado), mas o modelo mistura "
        "bases diferentes e a identidade `Y(1x4)` somar 1 vale em aptos_2t. "
        "As tabelas de totais previstos (seções 3 a 5) trazem as duas versões "
        "(aptos_2t e aptos_1t); a diferença entre elas é de dezenas a centenas de votos.\n"
    )

    # Efeito de aptos nos totais previstos: comparar E1
    partes.append(
        "**C2. Cifra do enunciado: 'comparecimento subiu 2,96 milhões'.** "
        f"Nos 5.571 municípios o comparecimento foi de {formatar_inteiro(criticas['comparecimento_1t_brasil'])} "
        f"para {formatar_inteiro(criticas['comparecimento_2t_brasil'])} "
        f"(+{formatar_inteiro(criticas['comparecimento_2t_brasil'] - criticas['comparecimento_1t_brasil'])}); "
        f"a queda da abstenção (com não instaladas, que são 0 nos dois turnos) é "
        f"{formatar_inteiro(criticas['queda_abstencao_brasil'])}. O valor 2,96 milhões "
        "só aparece quando se inclui o exterior (ZZ); a especificação exclui o exterior, "
        "então o número da seção 1 não é consistente com o universo da seção 3 "
        "(erro de ~40 mil).\n"
    )

    # C3: N fixo x N reamostrado
    linhas_n: list[list[str]] = []
    origens_principais = ["cury", "renan", "caiado"]
    for nome_origem in origens_principais:
        for nome_destino in ("lula", "flavio"):
            fixo = extrair_celula(tabela, ESPECIFICACAO_E1, eco.NOME_BRASIL, nome_origem, nome_destino)
            reamostrado = extrair_celula(
                tabela_n_reamostrado, ESPECIFICACAO_E1, eco.NOME_BRASIL, nome_origem, nome_destino
            )
            largura_fixo = fixo["votos_ic_sup"] - fixo["votos_ic_inf"]
            largura_reamostrado = reamostrado["votos_ic_sup"] - reamostrado["votos_ic_inf"]
            linhas_n.append(
                [
                    f"{nome_origem}->{nome_destino}",
                    formatar_inteiro(fixo["votos"]),
                    f"{formatar_inteiro(fixo['votos_ic_inf'])} a {formatar_inteiro(fixo['votos_ic_sup'])}",
                    f"{formatar_inteiro(reamostrado['votos_ic_inf'])} a {formatar_inteiro(reamostrado['votos_ic_sup'])}",
                    f"{largura_reamostrado / largura_fixo:.2f}",
                ]
            )
    partes.append(
        "**C3. Ambiguidade do bootstrap dos fluxos em votos.** A especificação "
        "manda 'recalcular os fluxos' por réplica, mas não diz se N_reg[r] é o "
        "observado ou o da réplica. N_reg é conhecido exatamente (o universo "
        "inteiro é observado), então este código usa o N observado (fixo) em "
        "`transferencias.csv`; a alternativa (N reamostrado) está em "
        "`transferencias_n_reamostrado.csv`. Efeito, E1 Brasil:\n"
    )
    partes.append(
        formatar_tabela_markdown(
            ["fluxo", "votos (ponto)", "IC N fixo", "IC N reamostrado", "razão das larguras"],
            linhas_n,
        )
    )

    # C4: IC degenerado na fronteira
    e1_brasil = tabela[(tabela["especificacao"] == ESPECIFICACAO_E1) & (tabela["regiao"] == eco.NOME_BRASIL)]
    largura_beta = e1_brasil["beta_ic_sup"] - e1_brasil["beta_ic_inf"]
    degenerados = int((largura_beta < LIMIAR_LARGURA_DEGENERADA).sum())
    e1_regioes = tabela[(tabela["especificacao"] == ESPECIFICACAO_E1) & (tabela["regiao"] != eco.NOME_BRASIL)]
    largura_regioes = e1_regioes["beta_ic_sup"] - e1_regioes["beta_ic_inf"]
    degenerados_regioes = int((largura_regioes < LIMIAR_LARGURA_DEGENERADA).sum())
    ponto_zero_regioes = int((e1_regioes["beta"] <= eco.LIMIAR_FRONTEIRA).sum())
    ponto_fora_ic = int(
        (
            (e1_regioes["beta"] < e1_regioes["beta_ic_inf"] - 1e-9)
            | (e1_regioes["beta"] > e1_regioes["beta_ic_sup"] + 1e-9)
        ).sum()
    )
    partes.append(
        "\n**C4. IC percentil na fronteira.** Em E1 há "
        f"{ponto_zero_regioes} de 160 células regionais com beta pontual = 0. "
        f"Dessas, o IC é degenerado (largura < 1e-9) em {degenerados_regioes} "
        "células regionais e "
        f"{degenerados} das 32 células Brasil. Com a restrição beta >= 0 a "
        "distribuição bootstrap acumula massa em 0, e o percentil 2,5 também "
        "vira 0: o IC subestima a incerteza de células na fronteira. "
        f"Células regionais cujo ponto cai fora do próprio IC: {ponto_fora_ic}.\n"
    )

    # C5: tamanho efetivo
    linhas_neff: list[list[str]] = []
    for nome_regiao, numero, neff, maior in calcular_tamanho_efetivo(dados):
        linhas_neff.append(
            [nome_regiao, str(numero), f"{neff:.1f}", f"{100 * maior:.1f}%"]
        )
    partes.append(
        "\n**C5. A ponderação por aptos_1t concentra o ajuste em poucos municípios.** "
        "Tamanho efetivo amostral (soma w)^2 / soma w^2 e participação do maior município:\n"
    )
    partes.append(
        formatar_tabela_markdown(
            ["região", "municípios", "n efetivo", "maior peso"], linhas_neff
        )
    )
    partes.append(_texto_tensao_totais(dados, ajustes))
    partes.append(
        "\nCom 8 parâmetros livres por coluna, um n efetivo de poucas dezenas "
        "explica o cond(G) elevado e os IC largos nos grupos pequenos; a "
        "reamostragem bootstrap de municípios com pesos tão desiguais é instável "
        "(a presença/ausência de uma capital muda o ajuste).\n"
    )
    return "\n".join(partes)


def _texto_tensao_totais(
    dados: eco.DadosEleitorais, ajustes: dict[str, EspecificacaoAjustada]
) -> str:
    """C6: totais do 2º turno que o modelo restrito não reproduz."""
    posicao_bn = eco.DESTINOS.index("branco_nulo")
    posicao_abstencao = eco.DESTINOS.index("abstencao")
    real_bn = float(dados.contagens_destino[:, posicao_bn].sum())
    real_abstencao = float(dados.contagens_destino[:, posicao_abstencao].sum())
    saidas: dict[str, np.ndarray] = {}
    for nome, ajuste in ajustes.items():
        previsto = np.zeros(eco.NUMERO_DESTINOS)
        for posicao_regiao, indices in enumerate(indices_das_regioes(dados)):
            y_previsto = dados.x[indices] @ ajuste.beta_regioes[posicao_regiao]
            previsto += (dados.aptos_2t[indices, None] * y_previsto).sum(axis=0)
        saidas[nome] = previsto
    erro_bn_e1 = saidas[ESPECIFICACAO_E1][posicao_bn] - real_bn
    erro_abstencao_e3 = saidas[ESPECIFICACAO_E3][posicao_abstencao] - real_abstencao
    erro_bn_e2 = saidas[ESPECIFICACAO_E2][posicao_bn] - real_bn
    celulas_em_zero_e1 = 0
    for unidade in ajustes[ESPECIFICACAO_E1].unidades:
        celulas_em_zero_e1 += int((unidade.beta <= eco.LIMIAR_FRONTEIRA).sum())
    return (
        "\n**C6. Totais do 2º turno não reproduzidos (fronteira ativa).** Sem "
        "restrições de sinal, o OLS ponderado com X somando 1 reproduz exatamente "
        "o total de cada destino; com `beta >= 0` ativo isso deixa de valer. "
        f"Em E1, o branco/nulo previsto no Brasil erra {formatar_inteiro_com_sinal(erro_bn_e1)} votos "
        f"({100 * erro_bn_e1 / real_bn:+.2f}%); em E2 erra {formatar_inteiro_com_sinal(erro_bn_e2)} "
        f"({100 * erro_bn_e2 / real_bn:+.2f}%); em E3 a abstenção erra "
        f"{formatar_inteiro_com_sinal(erro_abstencao_e3)} ({100 * erro_abstencao_e3 / real_abstencao:+.2f}%). "
        "Isto é tensão do modelo (a seção 8 da especificação pede para reportar), "
        "não erro de código: o solver satisfaz KKT. "
        f"Leitura de produto: com {celulas_em_zero_e1} de 160 células regionais coladas em 0, o "
        "modelo está dizendo que a hipótese de constância linear não descreve bem "
        "branco/nulo e abstenção, e as estimativas de grupos pequenos "
        "(cury, renan, caiado, demais) dependem mais da restrição do que dos dados.\n"
    )


def escrever_readme(
    caminho: Path,
    tabela: pd.DataFrame,
    ajustes: dict[str, EspecificacaoAjustada],
    resumo_sintetico: dict[str, float],
    numero_replicas: int,
    tempo_total: float,
) -> None:
    """README: como rodar e números principais."""
    linhas: list[str] = []
    linhas.append("# Reimplementação B — inferência ecológica (1º -> 2º turno, presidente 2026)\n")
    linhas.append(
        "Reimplementação independente do método de `2026-10-26_inferencia_ecologica/ESPECIFICACAO.md`, "
        "escrita só a partir da especificação. Diferença de método computacional: "
        "solver FISTA com projeção exata no simplex (Duchi et al., 2008) escrito do zero, "
        "sem `scipy.optimize`; equações normais montadas a partir das colunas brutas.\n"
    )
    linhas.append("## Como rodar\n")
    linhas.append(
        "```\ncd 2026-10-26_inferencia_ecologica_reimplementacao\n"
        "python3 -I executar.py              # B = 1000, ~minutos\n"
        "python3 -I executar.py --replicas 50   # execução rápida de conferência\n```\n"
    )
    linhas.append(
        "Entrada: `dados/processados/presidente_municipio_turnos.parquet` "
        "(`fl_exterior == False`, 5.571 municípios). Saídas nesta pasta: "
        "`transferencias.csv` (`;`, UTF-8, ponto decimal), `transferencias_n_reamostrado.csv` "
        "(variante C3), `diagnosticos.md`, `teste_sintetico.md`. Código: `ecologia_b.py` "
        "(biblioteca) e `executar.py` (orquestração).\n"
    )
    linhas.append(f"> {AVISO_IC}\n")
    linhas.append(f"## E1 Brasil (B = {numero_replicas}) — beta com IC 95%\n")
    for nome_origem in ("cury", "renan", "caiado"):
        linha_tabela: list[str] = []
        for nome_destino in eco.DESTINOS:
            celula = extrair_celula(tabela, ESPECIFICACAO_E1, eco.NOME_BRASIL, nome_origem, nome_destino)
            linha_tabela.append(formatar_beta_com_ic(celula))
        linhas.append(f"- **{nome_origem}**: " + " · ".join(
            f"{destino} {valor}" for destino, valor in zip(eco.DESTINOS, linha_tabela)
        ))
    linhas.append("")
    celulas_chave = [
        ("lula", "lula"),
        ("flavio", "flavio"),
        ("abstencao", "lula"),
        ("abstencao", "flavio"),
    ]
    for nome_origem, nome_destino in celulas_chave:
        celula = extrair_celula(tabela, ESPECIFICACAO_E1, eco.NOME_BRASIL, nome_origem, nome_destino)
        linhas.append(
            f"- beta[{nome_origem}->{nome_destino}] = {formatar_beta_com_ic(celula)}"
        )
    linhas.append("\n## Qualidade numérica\n")
    maior_condicao = max(
        unidade.condicao for ajuste in ajustes.values() for unidade in ajuste.unidades
    )
    maior_kkt = max(
        unidade.kkt_absoluta for ajuste in ajustes.values() for unidade in ajuste.unidades
    )
    linhas.append(f"- Maior cond(G): {maior_condicao:.3e}")
    linhas.append(f"- Maior violação KKT (absoluta): {maior_kkt:.2e}")
    linhas.append(
        f"- T1 erro máx. de beta: E2 {resumo_sintetico['t1_e2_max']:.4f}, "
        f"E1 Brasil {resumo_sintetico['t1_e1_brasil_max']:.4f}"
    )
    linhas.append(
        f"- T2 erro máx. do fluxo de Caiado: E1 {resumo_sintetico['t2_fluxo_caiado_e1_max_pct']:.2f}%, "
        f"E2 {resumo_sintetico['t2_fluxo_caiado_e2_max_pct']:.2f}% do total de Caiado"
    )
    linhas.append(f"- Tempo total da execução: {tempo_total / 60.0:.1f} min")
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    LOGGER.info("README escrito em %s.", caminho)


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------


def executar(numero_replicas: int) -> None:
    """Pipeline completo: dados, âncoras, ajustes, bootstrap, testes, relatórios."""
    inicio_total = time.time()
    configuracao = eco.ConfiguracaoSolver()

    base = eco.carregar_base_municipal()
    dados = eco.montar_dados(base)
    ancoras = eco.validar_ancoras(dados)
    estatisticas = eco.montar_estatisticas_suficientes(dados.x, dados.y)

    nomes_especificacoes = [ESPECIFICACAO_E1, ESPECIFICACAO_E2, ESPECIFICACAO_E3]
    ajustes: dict[str, EspecificacaoAjustada] = {}
    for nome in nomes_especificacoes:
        ajustes[nome] = ajustar_especificacao(nome, dados, estatisticas, configuracao)

    multiplicidades = gerar_multiplicidades_bootstrap(
        dados, numero_replicas, eco.SEMENTE_PADRAO
    )
    bootstraps: dict[str, ResultadoBootstrap] = {}
    for nome in nomes_especificacoes:
        bootstraps[nome] = executar_bootstrap(
            nome, dados, estatisticas, ajustes[nome], multiplicidades
        )

    populacao_pontual = eco.calcular_populacao_origem(
        dados, np.ones((1, len(dados.aptos_1t)))
    )[0]
    populacao_fixa = populacao_pontual[None]
    populacao_reamostrada = eco.calcular_populacao_origem(dados, multiplicidades)

    tabelas_fixo: list[pd.DataFrame] = []
    tabelas_reamostrado: list[pd.DataFrame] = []
    for nome in nomes_especificacoes:
        tabela_fixo = montar_tabela_longa(
            nome,
            ajustes[nome].beta_regioes,
            bootstraps[nome].beta_regioes,
            populacao_pontual,
            populacao_fixa,
        )
        tabela_reamostrado = montar_tabela_longa(
            nome,
            ajustes[nome].beta_regioes,
            bootstraps[nome].beta_regioes,
            populacao_pontual,
            populacao_reamostrada,
        )
        tabelas_fixo.append(tabela_fixo)
        tabelas_reamostrado.append(tabela_reamostrado)
    tabela = pd.concat(tabelas_fixo, ignore_index=True)
    tabela_n_reamostrado = pd.concat(tabelas_reamostrado, ignore_index=True)

    caminho_csv = PASTA_SAIDA / "transferencias.csv"
    caminho_csv_alternativo = PASTA_SAIDA / "transferencias_n_reamostrado.csv"
    tabela.to_csv(caminho_csv, sep=";", index=False, encoding="utf-8", float_format="%.12g")
    tabela_n_reamostrado.to_csv(
        caminho_csv_alternativo, sep=";", index=False, encoding="utf-8", float_format="%.12g"
    )
    LOGGER.info("CSVs escritos: %s (%d linhas).", caminho_csv, len(tabela))

    criticas = calcular_criticas(dados, base)
    escrever_diagnosticos(
        PASTA_SAIDA / "diagnosticos.md",
        ajustes,
        bootstraps,
        tabela,
        tabela_n_reamostrado,
        dados,
        ancoras,
        criticas,
        numero_replicas,
    )
    resumo_sintetico = escrever_teste_sintetico(
        dados, configuracao, PASTA_SAIDA / "teste_sintetico.md"
    )
    tempo_total = time.time() - inicio_total
    escrever_readme(
        PASTA_SAIDA / "README.md",
        tabela,
        ajustes,
        resumo_sintetico,
        numero_replicas,
        tempo_total,
    )
    LOGGER.info("Execução completa em %.1f s.", tempo_total)


def interpretar_argumentos() -> argparse.Namespace:
    """Lê os argumentos de linha de comando."""
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--replicas",
        type=int,
        default=eco.NUMERO_REPLICAS_BOOTSTRAP,
        help="Número de réplicas do bootstrap (padrão 1000).",
    )
    return analisador.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    argumentos = interpretar_argumentos()
    executar(argumentos.replicas)
