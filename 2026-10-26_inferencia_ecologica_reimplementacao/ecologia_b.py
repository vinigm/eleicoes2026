"""Reimplementação independente (B) da inferência ecológica de migração de votos.

Pergunta de negócio: para onde foram, no 2º turno, os eleitores que no 1º turno
votaram em cada candidato (ou se abstiveram)? O voto é secreto; só existem
totais por município. O modelo é uma regressão de Goodman com restrições:

    Y_i (1x4)  ~  X_i (1x8) @ beta (8x4),   linhas de beta no simplex de
    probabilidade,  minimizando  sum_i w_i * ||Y_i - X_i beta||^2.

Diferença deliberada de método computacional em relação à implementação A:
nenhum otimizador pronto é usado. O solver é um gradiente projetado acelerado
(FISTA, com reinício adaptativo) sobre os 32 parâmetros, passo 1/L com
L = 2 * lambda_max(G), e projeção euclidiana exata de cada linha de beta no
simplex (algoritmo de ordenação de Duchi et al., 2008), tudo escrito aqui.
O solver trabalha em LOTES (primeira dimensão = ajuste), o que permite resolver
as 1.000 réplicas do bootstrap de uma vez.
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

import numpy as np
import pandas as pd

LOGGER = logging.getLogger("ecologia_b")

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

# Raiz do projeto = pasta acima desta: roda de qualquer clone.
CAMINHO_BASE = (
    Path(__file__).resolve().parent.parent
    / "dados"
    / "processados"
    / "presidente_municipio_turnos.parquet"
)
SEMENTE_PADRAO = 20261025
NUMERO_REPLICAS_BOOTSTRAP = 1000

REGIOES: list[str] = ["Centro-Oeste", "Nordeste", "Norte", "Sudeste", "Sul"]
NOME_BRASIL = "Brasil"

ORIGENS: list[str] = [
    "lula",
    "flavio",
    "cury",
    "renan",
    "caiado",
    "demais",
    "branco_nulo",
    "abstencao",
]
DESTINOS: list[str] = ["lula", "flavio", "branco_nulo", "abstencao"]
NUMERO_ORIGENS = len(ORIGENS)
NUMERO_DESTINOS = len(DESTINOS)

COLUNAS_ORIGEM: dict[str, list[str]] = {
    "lula": ["votos_1t_13"],
    "flavio": ["votos_1t_22"],
    "cury": ["votos_1t_70"],
    "renan": ["votos_1t_14"],
    "caiado": ["votos_1t_55"],
    "demais": [
        "votos_1t_30",
        "votos_1t_80",
        "votos_1t_16",
        "votos_1t_27",
        "votos_1t_21",
        "votos_1t_35",
        "votos_1t_29",
    ],
    "branco_nulo": ["brancos_1t", "nulos_1t"],
    "abstencao": ["abstencao_1t", "nao_instaladas_1t"],
}
COLUNAS_DESTINO: dict[str, list[str]] = {
    "lula": ["votos_2t_13"],
    "flavio": ["votos_2t_22"],
    "branco_nulo": ["brancos_2t", "nulos_2t"],
    "abstencao": ["abstencao_2t", "nao_instaladas_2t"],
}

# Âncoras da seção 4 da especificação (Brasil, 5.571 municípios).
ANCORAS_ORIGEM: dict[str, int] = {
    "lula": 53_722_151,
    "flavio": 55_960_603,
    "cury": 3_438_835,
    "renan": 2_667_307,
    "caiado": 2_600_440,
    "demais": 580_570,
    "branco_nulo": 5_964_163,
    "abstencao": 32_894_899,
}
ANCORA_APTOS_1T = 157_828_968
ANCORAS_DESTINO: dict[str, int] = {
    "lula": 64_056_078,
    "flavio": 59_654_544,
    "branco_nulo": 4_144_009,
    "abstencao": 29_974_188,
}
ANCORA_APTOS_2T = 157_828_819
ANCORA_MUNICIPIOS = 5_571
ANCORAS_MUNICIPIOS_REGIAO: dict[str, int] = {
    "Centro-Oeste": 468,
    "Nordeste": 1_794,
    "Norte": 450,
    "Sudeste": 1_668,
    "Sul": 1_191,
}

# Parâmetros numéricos do solver e dos diagnósticos.
TOLERANCIA_RELATIVA = 1e-12
MAXIMO_ITERACOES = 400_000
PISO_ESCALA = 1e-300
LIMIAR_SUPORTE_KKT = 1e-10
LIMIAR_FRONTEIRA = 1e-9
TOLERANCIA_SOMA_LINHA = 1e-12


# ---------------------------------------------------------------------------
# Estruturas
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DadosEleitorais:
    """Matrizes eleitorais dos municípios (sem exterior), prontas para o modelo.

    Attributes:
        contagens_origem: Votos por grupo de origem, shape (n, 8).
        contagens_destino: Votos por destino, shape (n, 4).
        aptos_1t: Aptos do 1º turno por município, shape (n,).
        aptos_2t: Aptos do 2º turno por município, shape (n,).
        x: Frações de origem (contagens / aptos_1t), shape (n, 8).
        y: Frações de destino (contagens / aptos_2t), shape (n, 4).
        indice_regiao: Posição da região do município em REGIOES, shape (n,).
    """

    contagens_origem: np.ndarray
    contagens_destino: np.ndarray
    aptos_1t: np.ndarray
    aptos_2t: np.ndarray
    x: np.ndarray
    y: np.ndarray
    indice_regiao: np.ndarray


@dataclasses.dataclass(frozen=True)
class ConfiguracaoSolver:
    """Parâmetros de parada do FISTA."""

    tolerancia_relativa: float = TOLERANCIA_RELATIVA
    maximo_iteracoes: int = MAXIMO_ITERACOES


@dataclasses.dataclass(frozen=True)
class ResultadoSolver:
    """Resultado de um lote de ajustes.

    Attributes:
        beta: Soluções, shape (B, 8, 4).
        objetivo: Valor do objetivo (soma ponderada dos erros quadráticos com
            pesos normalizados para somar 1), shape (B,).
        iteracoes: Iterações usadas por ajuste, shape (B,).
        convergiu: Se o critério de parada foi atingido antes do limite.
        lipschitz: Constante L = 2 * lambda_max(G), shape (B,).
    """

    beta: np.ndarray
    objetivo: np.ndarray
    iteracoes: np.ndarray
    convergiu: np.ndarray
    lipschitz: np.ndarray


@dataclasses.dataclass(frozen=True)
class EstatisticasSuficientes:
    """Produtos por município que permitem montar G, H e a constante.

    Attributes:
        produtos_xx: X_i^T X_i achatado, shape (n, 64).
        produtos_xy: X_i^T Y_i achatado, shape (n, 32).
        produtos_yy: soma dos quadrados de Y_i, shape (n,).
    """

    produtos_xx: np.ndarray
    produtos_xy: np.ndarray
    produtos_yy: np.ndarray


@dataclasses.dataclass(frozen=True)
class ViolacaoKkt:
    """Violações das condições KKT por ajuste (shape (B,))."""

    estacionariedade: np.ndarray
    complementaridade: np.ndarray
    maxima_absoluta: np.ndarray
    maxima_relativa: np.ndarray
    residuo_gradiente_projetado: np.ndarray


# ---------------------------------------------------------------------------
# Carga, montagem e validação dos dados
# ---------------------------------------------------------------------------


def carregar_base_municipal(caminho: Path = CAMINHO_BASE) -> pd.DataFrame:
    """Lê a base certificada e mantém só os municípios brasileiros.

    Args:
        caminho: Parquet com um registro por município e turno.

    Returns:
        DataFrame sem o exterior (``fl_exterior == False``), na ordem original.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"Base não encontrada: {caminho}")
    base_completa = pd.read_parquet(caminho)
    mascara_brasil = base_completa["fl_exterior"] == False  # noqa: E712
    base_brasil = base_completa[mascara_brasil].reset_index(drop=True)
    LOGGER.info(
        "Base lida de %s: %d registros totais, %d municípios sem exterior.",
        caminho,
        len(base_completa),
        len(base_brasil),
    )
    return base_brasil


def somar_colunas_inteiras(base: pd.DataFrame, colunas: list[str]) -> np.ndarray:
    """Soma, linha a linha, as colunas informadas, em inteiros de 64 bits."""
    bloco = base[colunas].to_numpy(dtype=np.int64)
    return bloco.sum(axis=1)


def montar_dados(base: pd.DataFrame) -> DadosEleitorais:
    """Refaz as categorias da seção 4 a partir das colunas brutas.

    Origem: frações dos aptos do 1º turno. Destino: frações dos aptos do 2º
    turno. Cada linha de X e de Y deve somar 1 (identidade validada aqui).

    Raises:
        ValueError: Se alguma linha de X ou de Y não somar exatamente os aptos.
    """
    numero_municipios = len(base)
    contagens_origem = np.zeros((numero_municipios, NUMERO_ORIGENS), dtype=np.int64)
    for posicao, nome_origem in enumerate(ORIGENS):
        colunas = COLUNAS_ORIGEM[nome_origem]
        contagens_origem[:, posicao] = somar_colunas_inteiras(base, colunas)

    contagens_destino = np.zeros((numero_municipios, NUMERO_DESTINOS), dtype=np.int64)
    for posicao, nome_destino in enumerate(DESTINOS):
        colunas = COLUNAS_DESTINO[nome_destino]
        contagens_destino[:, posicao] = somar_colunas_inteiras(base, colunas)

    aptos_1t = base["aptos_1t"].to_numpy(dtype=np.int64)
    aptos_2t = base["aptos_2t"].to_numpy(dtype=np.int64)

    soma_origem = contagens_origem.sum(axis=1)
    soma_destino = contagens_destino.sum(axis=1)
    linhas_origem_invalidas = int((soma_origem != aptos_1t).sum())
    linhas_destino_invalidas = int((soma_destino != aptos_2t).sum())
    if linhas_origem_invalidas > 0 or linhas_destino_invalidas > 0:
        raise ValueError(
            "Identidade violada: municípios com soma de origem != aptos_1t = "
            f"{linhas_origem_invalidas}; soma de destino != aptos_2t = "
            f"{linhas_destino_invalidas}."
        )

    x = contagens_origem / aptos_1t[:, None]
    y = contagens_destino / aptos_2t[:, None]

    mapa_regiao = {nome: posicao for posicao, nome in enumerate(REGIOES)}
    indice_regiao = base["nm_regiao"].map(mapa_regiao).to_numpy()
    if np.isnan(indice_regiao.astype(float)).any():
        raise ValueError("Há municípios com região fora das 5 regiões esperadas.")
    indice_regiao = indice_regiao.astype(np.int64)

    return DadosEleitorais(
        contagens_origem=contagens_origem,
        contagens_destino=contagens_destino,
        aptos_1t=aptos_1t,
        aptos_2t=aptos_2t,
        x=x,
        y=y,
        indice_regiao=indice_regiao,
    )


def validar_ancoras(dados: DadosEleitorais) -> dict[str, tuple[int, int, bool]]:
    """Compara totais calculados com as âncoras da seção 4.

    Returns:
        Dicionário nome -> (esperado, calculado, passou).

    Raises:
        ValueError: Se qualquer âncora divergir (nunca se força o resultado).
    """
    resultados: dict[str, tuple[int, int, bool]] = {}

    resultados["municipios"] = _comparar(
        ANCORA_MUNICIPIOS, int(len(dados.aptos_1t))
    )
    for posicao_regiao, nome_regiao in enumerate(REGIOES):
        calculado = int((dados.indice_regiao == posicao_regiao).sum())
        esperado = ANCORAS_MUNICIPIOS_REGIAO[nome_regiao]
        resultados[f"municipios_{nome_regiao}"] = _comparar(esperado, calculado)

    totais_origem = dados.contagens_origem.sum(axis=0)
    for posicao, nome_origem in enumerate(ORIGENS):
        esperado = ANCORAS_ORIGEM[nome_origem]
        resultados[f"1t_{nome_origem}"] = _comparar(
            esperado, int(totais_origem[posicao])
        )
    resultados["1t_aptos"] = _comparar(ANCORA_APTOS_1T, int(dados.aptos_1t.sum()))

    totais_destino = dados.contagens_destino.sum(axis=0)
    for posicao, nome_destino in enumerate(DESTINOS):
        esperado = ANCORAS_DESTINO[nome_destino]
        resultados[f"2t_{nome_destino}"] = _comparar(
            esperado, int(totais_destino[posicao])
        )
    resultados["2t_aptos"] = _comparar(ANCORA_APTOS_2T, int(dados.aptos_2t.sum()))

    reprovadas = [nome for nome, (_, _, passou) in resultados.items() if not passou]
    if reprovadas:
        raise ValueError(f"Âncoras divergentes (investigar, não forçar): {reprovadas}")
    LOGGER.info("Todas as %d âncoras da seção 4 conferem.", len(resultados))
    return resultados


def _comparar(esperado: int, calculado: int) -> tuple[int, int, bool]:
    """Empacota a comparação exata entre âncora e valor calculado."""
    return (esperado, calculado, esperado == calculado)


# ---------------------------------------------------------------------------
# Projeção no simplex (Duchi et al., 2008)
# ---------------------------------------------------------------------------


def projetar_linhas_no_simplex(matriz: np.ndarray) -> np.ndarray:
    """Projeção euclidiana exata de cada vetor da última dimensão no simplex.

    Algoritmo de ordenação (Duchi et al., 2008): ordena em ordem decrescente
    u_1 >= ... >= u_K, acha rho = max{j : u_j - (sum_{r<=j} u_r - 1)/j > 0},
    define theta = (sum_{r<=rho} u_r - 1)/rho e devolve max(v - theta, 0).

    Args:
        matriz: Array (..., K). Cada vetor da última dimensão é projetado.

    Returns:
        Array do mesmo shape; cada vetor soma 1 e tem entradas >= 0.
    """
    tamanho = matriz.shape[-1]
    ordenados = -np.sort(-matriz, axis=-1)
    somas_acumuladas = np.cumsum(ordenados, axis=-1)
    posicoes = np.arange(1, tamanho + 1, dtype=np.float64)
    limiares_candidatos = (somas_acumuladas - 1.0) / posicoes
    mascara_ativa = (ordenados - limiares_candidatos) > 0.0
    posicao_rho = (mascara_ativa * posicoes).max(axis=-1)
    indice_rho = posicao_rho.astype(np.int64) - 1
    indice_rho_expandido = indice_rho[..., None]
    theta = np.take_along_axis(limiares_candidatos, indice_rho_expandido, axis=-1)
    projetada = np.maximum(matriz - theta, 0.0)
    return projetada


# ---------------------------------------------------------------------------
# Equações normais e objetivo
# ---------------------------------------------------------------------------


def montar_estatisticas_suficientes(
    x: np.ndarray, y: np.ndarray
) -> EstatisticasSuficientes:
    """Pré-computa X_i^T X_i, X_i^T Y_i e ||Y_i||^2 de cada município."""
    numero_municipios = x.shape[0]
    produtos_xx = x[:, :, None] * x[:, None, :]
    produtos_xy = x[:, :, None] * y[:, None, :]
    produtos_yy = (y * y).sum(axis=1)
    return EstatisticasSuficientes(
        produtos_xx=produtos_xx.reshape(numero_municipios, -1),
        produtos_xy=produtos_xy.reshape(numero_municipios, -1),
        produtos_yy=produtos_yy,
    )


def montar_equacoes_normais(
    estatisticas: EstatisticasSuficientes,
    matriz_pesos: np.ndarray,
    indices_municipios: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Monta G = X^T W X, H = X^T W Y e a constante Y^T W Y para um lote.

    Os pesos de cada ajuste são normalizados para somar 1 (o argmin é invariante
    à escala; o número de condição de G também).

    Args:
        estatisticas: Produtos por município (todos os municípios).
        matriz_pesos: Pesos (B, n_total); zero para quem não entra no ajuste.
        indices_municipios: Colunas (municípios) do subconjunto do ajuste.

    Returns:
        (G (B,8,8), H (B,8,4), constante (B,)).
    """
    pesos_subconjunto = matriz_pesos[:, indices_municipios]
    soma_pesos = pesos_subconjunto.sum(axis=1, keepdims=True)
    pesos_normalizados = pesos_subconjunto / soma_pesos
    produtos_xx = estatisticas.produtos_xx[indices_municipios]
    produtos_xy = estatisticas.produtos_xy[indices_municipios]
    produtos_yy = estatisticas.produtos_yy[indices_municipios]
    numero_ajustes = matriz_pesos.shape[0]
    g = (pesos_normalizados @ produtos_xx).reshape(
        numero_ajustes, NUMERO_ORIGENS, NUMERO_ORIGENS
    )
    h = (pesos_normalizados @ produtos_xy).reshape(
        numero_ajustes, NUMERO_ORIGENS, NUMERO_DESTINOS
    )
    constante = pesos_normalizados @ produtos_yy
    return g, h, constante


def calcular_objetivo(
    g: np.ndarray, h: np.ndarray, constante: np.ndarray, beta: np.ndarray
) -> np.ndarray:
    """Objetivo sum_c (b_c^T G b_c - 2 b_c^T H_c) + constante, por ajuste."""
    termo_quadratico = np.einsum("bkc,bkj,bjc->b", beta, g, beta)
    termo_linear = np.einsum("bkc,bkc->b", beta, h)
    return termo_quadratico - 2.0 * termo_linear + constante


def numeros_de_condicao(g: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Autovalores extremos e número de condição (lambda_max/lambda_min) de G."""
    autovalores = np.linalg.eigvalsh(g)
    lambda_minimo = autovalores[:, 0]
    lambda_maximo = autovalores[:, -1]
    condicao = lambda_maximo / lambda_minimo
    return lambda_minimo, lambda_maximo, condicao


# ---------------------------------------------------------------------------
# Solver FISTA em lote
# ---------------------------------------------------------------------------


def resolver_fista(
    g: np.ndarray,
    h: np.ndarray,
    constante: np.ndarray,
    beta_inicial: np.ndarray,
    configuracao: ConfiguracaoSolver,
) -> ResultadoSolver:
    """Minimiza o objetivo de Goodman com linhas de beta no simplex (FISTA).

    Gradiente do objetivo: 2 (G beta - H). Passo 1/L, L = 2 lambda_max(G).
    Usa reinício adaptativo de momento (O'Donoghue e Candès, 2015): quando o
    passo de momento aponta contra a direção de descida, o momento é zerado.
    Cada ajuste do lote é congelado assim que o seu critério de parada é
    atingido: variação do objetivo E variação da solução, ambas <= tolerância
    relativa entre duas iterações consecutivas.

    Args:
        g: (B, 8, 8). h: (B, 8, 4). constante: (B,).
        beta_inicial: (B, 8, 4), será projetado no simplex.
        configuracao: Tolerância e limite de iterações.

    Returns:
        ResultadoSolver com beta (B, 8, 4) e metadados de convergência.
    """
    numero_ajustes = g.shape[0]
    _, lambda_maximo, _ = numeros_de_condicao(g)
    lipschitz = 2.0 * lambda_maximo
    passo = (1.0 / lipschitz)[:, None, None]

    beta = projetar_linhas_no_simplex(beta_inicial.astype(np.float64))
    ponto_extrapolado = beta.copy()
    parametro_t = np.ones(numero_ajustes)
    objetivo = calcular_objetivo(g, h, constante, beta)
    ativa = np.ones(numero_ajustes, dtype=bool)
    iteracoes = np.zeros(numero_ajustes, dtype=np.int64)
    tolerancia = configuracao.tolerancia_relativa

    for numero_iteracao in range(1, configuracao.maximo_iteracoes + 1):
        gradiente = 2.0 * (g @ ponto_extrapolado - h)
        candidato = ponto_extrapolado - passo * gradiente
        beta_novo = projetar_linhas_no_simplex(candidato)

        # Reinício adaptativo: produto escalar entre (y - x_novo) e (x_novo - x).
        produto_reinicio = np.sum(
            (ponto_extrapolado - beta_novo) * (beta_novo - beta), axis=(1, 2)
        )
        deve_reiniciar = produto_reinicio > 0.0

        parametro_t_novo = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * parametro_t**2))
        coeficiente_momento = (parametro_t - 1.0) / parametro_t_novo
        coeficiente_momento = np.where(deve_reiniciar, 0.0, coeficiente_momento)
        parametro_t_novo = np.where(deve_reiniciar, 1.0, parametro_t_novo)

        ponto_novo = beta_novo + coeficiente_momento[:, None, None] * (
            beta_novo - beta
        )
        objetivo_novo = calcular_objetivo(g, h, constante, beta_novo)

        variacao_objetivo = np.abs(objetivo_novo - objetivo)
        escala_objetivo = np.maximum(np.abs(objetivo_novo), PISO_ESCALA)
        variacao_solucao = np.linalg.norm(beta_novo - beta, axis=(1, 2))
        escala_solucao = np.maximum(np.linalg.norm(beta_novo, axis=(1, 2)), PISO_ESCALA)
        atingiu_objetivo = variacao_objetivo <= tolerancia * escala_objetivo
        atingiu_solucao = variacao_solucao <= tolerancia * escala_solucao
        atingiu_criterio = atingiu_objetivo & atingiu_solucao

        # Só os ajustes ainda ativos são atualizados (os demais ficam congelados).
        mascara_3d = ativa[:, None, None]
        beta = np.where(mascara_3d, beta_novo, beta)
        ponto_extrapolado = np.where(mascara_3d, ponto_novo, ponto_extrapolado)
        parametro_t = np.where(ativa, parametro_t_novo, parametro_t)
        objetivo = np.where(ativa, objetivo_novo, objetivo)
        iteracoes = np.where(ativa, numero_iteracao, iteracoes)
        ativa = ativa & ~atingiu_criterio
        if not ativa.any():
            break

    convergiu = ~ativa
    return ResultadoSolver(
        beta=beta,
        objetivo=objetivo,
        iteracoes=iteracoes,
        convergiu=convergiu,
        lipschitz=lipschitz,
    )


def beta_inicial_uniforme(numero_ajustes: int) -> np.ndarray:
    """Ponto inicial padrão: todas as linhas de beta uniformes (1/4 cada)."""
    uniforme = np.full(
        (numero_ajustes, NUMERO_ORIGENS, NUMERO_DESTINOS), 1.0 / NUMERO_DESTINOS
    )
    return uniforme


def calcular_violacao_kkt(
    g: np.ndarray, h: np.ndarray, beta: np.ndarray
) -> ViolacaoKkt:
    """Mede as violações KKT do problema com linhas no simplex.

    Para cada linha r de beta, com gradiente g_rc = 2 (G beta - H)_rc e
    multiplicador mu_r (da soma = 1):
      - estacionariedade: para beta_rc > 0, g_rc = mu_r;
      - complementaridade/dual: para beta_rc = 0, g_rc >= mu_r.
    mu_r é estimado como a média de g_rc sobre o suporte (beta_rc > 1e-10).
    A escala relativa é 2 * max|H| do ajuste. Também reporta o resíduo do
    gradiente projetado, ||beta - P(beta - g/L)||_inf, que não depende do
    limiar de suporte.
    """
    gradiente = 2.0 * (g @ beta - h)
    suporte = beta > LIMIAR_SUPORTE_KKT
    contagem_suporte = suporte.sum(axis=-1)
    soma_gradiente_suporte = (gradiente * suporte).sum(axis=-1)
    mu = soma_gradiente_suporte / np.maximum(contagem_suporte, 1)
    mu_expandido = mu[..., None]

    desvio = np.abs(gradiente - mu_expandido)
    desvio_no_suporte = desvio * suporte
    estacionariedade = desvio_no_suporte.max(axis=(1, 2))

    deficit_fora_do_suporte = np.maximum(mu_expandido - gradiente, 0.0) * (~suporte)
    complementaridade = deficit_fora_do_suporte.max(axis=(1, 2))

    maxima_absoluta = np.maximum(estacionariedade, complementaridade)
    escala = 2.0 * np.abs(h).max(axis=(1, 2))
    maxima_relativa = maxima_absoluta / escala

    _, lambda_maximo, _ = numeros_de_condicao(g)
    passo = (1.0 / (2.0 * lambda_maximo))[:, None, None]
    projetado = projetar_linhas_no_simplex(beta - passo * gradiente)
    residuo = np.abs(beta - projetado).max(axis=(1, 2))

    return ViolacaoKkt(
        estacionariedade=estacionariedade,
        complementaridade=complementaridade,
        maxima_absoluta=maxima_absoluta,
        maxima_relativa=maxima_relativa,
        residuo_gradiente_projetado=residuo,
    )


# ---------------------------------------------------------------------------
# Ajuste de uma especificação (regiões ou nacional) sobre lotes de pesos
# ---------------------------------------------------------------------------


def ajustar_lote(
    estatisticas: EstatisticasSuficientes,
    matriz_pesos: np.ndarray,
    indices_municipios: np.ndarray,
    beta_inicial: np.ndarray,
    configuracao: ConfiguracaoSolver,
) -> tuple[ResultadoSolver, np.ndarray, np.ndarray, np.ndarray]:
    """Monta as equações normais e resolve o lote.

    Returns:
        (resultado do solver, G, H, constante).
    """
    g, h, constante = montar_equacoes_normais(
        estatisticas, matriz_pesos, indices_municipios
    )
    resultado = resolver_fista(g, h, constante, beta_inicial, configuracao)
    return resultado, g, h, constante


def calcular_populacao_origem(
    dados: DadosEleitorais, matriz_contagens: np.ndarray
) -> np.ndarray:
    """N_reg[r] = sum_i (contagem de reamostragem_i) * aptos_1t_i * X_i[r].

    Args:
        dados: Dados eleitorais.
        matriz_contagens: Multiplicidades (B, n); com uma linha de uns, é a
            população observada.

    Returns:
        Array (B, 5, 8): tamanho de cada grupo de origem em cada região.
    """
    numero_replicas = matriz_contagens.shape[0]
    resultado = np.zeros((numero_replicas, len(REGIOES), NUMERO_ORIGENS))
    for posicao_regiao in range(len(REGIOES)):
        indices = np.flatnonzero(dados.indice_regiao == posicao_regiao)
        contagens_regiao = matriz_contagens[:, indices]
        origem_regiao = dados.contagens_origem[indices].astype(np.float64)
        resultado[:, posicao_regiao, :] = contagens_regiao @ origem_regiao
    return resultado


def agregar_brasil(beta_regioes: np.ndarray, populacao: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Soma os fluxos das 5 regiões e deriva o beta do Brasil.

    F[r, c] = beta_reg[r, c] * N_reg[r]; beta_Brasil = F / sum_c F.

    Args:
        beta_regioes: (B, 5, 8, 4).
        populacao: (B, 5, 8) ou (1, 5, 8) (broadcast).

    Returns:
        (fluxo Brasil (B, 8, 4), beta Brasil (B, 8, 4)).
    """
    fluxo_regioes = beta_regioes * populacao[:, :, :, None]
    fluxo_brasil = fluxo_regioes.sum(axis=1)
    total_origem = fluxo_brasil.sum(axis=-1, keepdims=True)
    beta_brasil = fluxo_brasil / total_origem
    return fluxo_brasil, beta_brasil
