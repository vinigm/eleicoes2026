"""Núcleo da inferência ecológica da migração de votos (1º para 2º turno).

Implementa a especificação de `ESPECIFICACAO.md`: regressão de Goodman com
restrições (cada linha de beta soma 1 e todas as células ficam em [0, 1]),
ponderada por aptos do 1º turno, resolvida por SLSQP sobre as equações
normais G = X'WX e H = X'WY.

Este módulo contém apenas funções puras e o carregamento da base. Quem grava
arquivos e orquestra as execuções são os scripts `01_estimar_transferencias.py`
e `02_teste_sintetico.py`.

Convenções de shape usadas em todo o módulo:
    n          número de municípios
    X          (n, 8)  fração dos aptos do 1º turno em cada grupo de origem
    Y          (n, 4)  fração dos aptos do 2º turno em cada destino
    beta       (8, 4)  fração de cada origem que vai para cada destino
    G, H       (8, 8) e (8, 4)  equações normais, já divididas pelo peso total
"""

import dataclasses
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes do domínio (ESPECIFICACAO.md, seções 3, 4 e 6)
# ---------------------------------------------------------------------------

SEMENTE_PADRAO = 20261025
NUMERO_REPLICAS_BOOTSTRAP = 1000
PERCENTIL_IC_INFERIOR = 2.5
PERCENTIL_IC_SUPERIOR = 97.5

ORIGENS_1T: tuple[str, ...] = (
    "lula",
    "flavio",
    "cury",
    "renan",
    "caiado",
    "demais",
    "branco_nulo",
    "abstencao",
)
DESTINOS_2T: tuple[str, ...] = (
    "lula",
    "flavio",
    "branco_nulo",
    "abstencao",
)
NUMERO_ORIGENS = len(ORIGENS_1T)
NUMERO_DESTINOS = len(DESTINOS_2T)
NUMERO_PARAMETROS = NUMERO_ORIGENS * NUMERO_DESTINOS

REGIOES: tuple[str, ...] = (
    "Centro-Oeste",
    "Nordeste",
    "Norte",
    "Sudeste",
    "Sul",
)
ROTULO_BRASIL = "Brasil"

# Partidos/candidatos agrupados na categoria "demais" (ESPECIFICACAO.md, seção 4).
NUMEROS_CANDIDATOS_DEMAIS: tuple[int, ...] = (30, 80, 16, 27, 21, 35, 29)

COLUNA_REGIAO = "nm_regiao"
COLUNA_EXTERIOR = "fl_exterior"
COLUNA_APTOS_1T = "aptos_1t"
COLUNA_APTOS_2T = "aptos_2t"
COLUNAS_OBRIGATORIAS: tuple[str, ...] = (
    "cd_municipio_tse",
    COLUNA_REGIAO,
    COLUNA_EXTERIOR,
    COLUNA_APTOS_1T,
    COLUNA_APTOS_2T,
    "abstencao_1t",
    "nao_instaladas_1t",
    "brancos_1t",
    "nulos_1t",
    "votos_1t_13",
    "votos_1t_22",
    "votos_1t_70",
    "votos_1t_14",
    "votos_1t_55",
    "votos_1t_30",
    "votos_1t_80",
    "votos_1t_16",
    "votos_1t_27",
    "votos_1t_21",
    "votos_1t_35",
    "votos_1t_29",
    "abstencao_2t",
    "nao_instaladas_2t",
    "brancos_2t",
    "nulos_2t",
    "votos_2t_13",
    "votos_2t_22",
)

# Âncoras certificadas da base (ESPECIFICACAO.md, seção 4).
ANCORAS_ORIGEM_1T: dict[str, int] = {
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
ANCORAS_DESTINO_2T: dict[str, int] = {
    "lula": 64_056_078,
    "flavio": 59_654_544,
    "branco_nulo": 4_144_009,
    "abstencao": 29_974_188,
}
ANCORA_APTOS_2T = 157_828_819
ANCORA_MUNICIPIOS_POR_REGIAO: dict[str, int] = {
    "Centro-Oeste": 468,
    "Nordeste": 1794,
    "Norte": 450,
    "Sudeste": 1668,
    "Sul": 1191,
}
ANCORA_TOTAL_MUNICIPIOS = 5571

# ---------------------------------------------------------------------------
# Constantes numéricas do solver
# ---------------------------------------------------------------------------

# O objetivo é multiplicado por ESCALA_OBJETIVO_SLSQP antes de ir ao SLSQP, então
# o ftol efetivo, na escala original de G e H, é TOLERANCIA_FUNCAO_SLSQP / ESCALA
# (1e-14 / 100 = 1e-16). Ver README: com ftol = 1e-12 sem reescala o solver parava
# cedo e betas de grupos pouco identificados variavam ~1e-2 conforme o ponto inicial.
TOLERANCIA_FUNCAO_SLSQP = 1e-14
ESCALA_OBJETIVO_SLSQP = 100.0
MAXIMO_ITERACOES_SLSQP = 1000
TOLERANCIA_LACUNA_DUALIDADE = 1e-7
TOLERANCIA_SOMA_UNITARIA = 1e-12
TOLERANCIA_VIABILIDADE_BETA = 1e-8
TOLERANCIA_FRONTEIRA_BETA = 1e-6
LIMITE_NUMERO_CONDICAO_ALTO = 1e8
LIMIAR_VARIANCIA_NULA = 1e-20


# ---------------------------------------------------------------------------
# Exceções específicas
# ---------------------------------------------------------------------------


class ErroAncora(RuntimeError):
    """Alguma âncora numérica da base divergiu do valor certificado."""


class ErroDadosInvalidos(ValueError):
    """A base não satisfaz as identidades exigidas pelo modelo."""


class ErroConvergenciaAjuste(RuntimeError):
    """O solver SLSQP não convergiu ou devolveu solução inviável."""


# ---------------------------------------------------------------------------
# Estruturas de dados
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DadosEcologicos:
    """Base municipal já transformada nas matrizes do modelo.

    Attributes:
        codigo_municipio: Código TSE de cada município (apenas rastreio).
        regiao: Região de cada município.
        aptos_1t: Aptos do 1º turno (denominador de X e peso do ajuste).
        aptos_2t: Aptos do 2º turno (denominador de Y).
        contagens_origem: Contagem de eleitores por grupo de origem, (n, 8).
        contagens_destino: Contagem de eleitores por destino, (n, 4).
        matriz_origem: Frações de origem X, (n, 8).
        matriz_destino: Frações de destino Y, (n, 4).
    """

    codigo_municipio: np.ndarray
    regiao: np.ndarray
    aptos_1t: np.ndarray
    aptos_2t: np.ndarray
    contagens_origem: np.ndarray
    contagens_destino: np.ndarray
    matriz_origem: np.ndarray
    matriz_destino: np.ndarray


@dataclasses.dataclass(frozen=True)
class ResultadoAncora:
    """Comparação entre um valor certificado e o valor medido na base."""

    nome: str
    esperado: int
    obtido: int

    @property
    def aprovada(self) -> bool:
        """Indica se o valor medido é exatamente igual ao certificado."""
        return self.esperado == self.obtido


@dataclasses.dataclass(frozen=True)
class EquacoesNormais:
    """Matrizes G = X'WX e H = X'WY divididas pelo peso total."""

    matriz_g: np.ndarray
    matriz_h: np.ndarray


@dataclasses.dataclass(frozen=True)
class ResultadoAjuste:
    """Resultado de um ajuste restrito de beta (uma unidade de ajuste).

    Attributes:
        beta: Matriz (8, 4) estimada.
        valor_objetivo: Objetivo no ótimo (sem a constante), na escala de G e H.
        numero_iteracoes: Iterações do SLSQP.
        numero_condicao_g: Número de condição de G (norma 2), sem pré-condicionamento.
        numero_condicao_g_escalada: Número de condição de G após o escalonamento
            diagonal usado internamente pelo solver.
        lacuna_dualidade: Limite superior comprovado para (objetivo - ótimo).
    """

    beta: np.ndarray
    valor_objetivo: float
    numero_iteracoes: int
    numero_condicao_g: float
    numero_condicao_g_escalada: float
    lacuna_dualidade: float


@dataclasses.dataclass(frozen=True)
class EspecificacaoModelo:
    """Define uma especificação do estimador (E1, E2 ou E3).

    Attributes:
        nome: Rótulo da especificação (E1, E2, E3).
        por_regiao: True ajusta um beta por região; False ajusta um beta único.
        ponderada: True pesa por aptos do 1º turno; False usa peso 1.
    """

    nome: str
    por_regiao: bool
    ponderada: bool


ESPECIFICACAO_E1 = EspecificacaoModelo(nome="E1", por_regiao=True, ponderada=True)
ESPECIFICACAO_E2 = EspecificacaoModelo(nome="E2", por_regiao=False, ponderada=True)
ESPECIFICACAO_E3 = EspecificacaoModelo(nome="E3", por_regiao=True, ponderada=False)
ESPECIFICACOES: tuple[EspecificacaoModelo, ...] = (
    ESPECIFICACAO_E1,
    ESPECIFICACAO_E2,
    ESPECIFICACAO_E3,
)


@dataclasses.dataclass(frozen=True)
class EstimativaEspecificacao:
    """Estimativa completa de uma especificação para um conjunto de pesos.

    Attributes:
        beta_por_regiao: beta de cada região, (5, 8, 4), na ordem de REGIOES.
            Em E2 todas as regiões recebem o mesmo beta nacional.
        fluxos_por_regiao: Fluxos em votos por região, (5, 8, 4).
        beta_brasil: beta agregado do Brasil, (8, 4).
        fluxos_brasil: Fluxos em votos do Brasil (soma das regiões), (8, 4).
        resultados_ajuste: Resultado do solver por unidade de ajuste.
    """

    beta_por_regiao: np.ndarray
    fluxos_por_regiao: np.ndarray
    beta_brasil: np.ndarray
    fluxos_brasil: np.ndarray
    resultados_ajuste: dict[str, ResultadoAjuste]


@dataclasses.dataclass(frozen=True)
class ResultadoBootstrap:
    """Réplicas bootstrap de uma especificação.

    Attributes:
        beta_por_regiao: (B, 5, 8, 4).
        fluxos_por_regiao: (B, 5, 8, 4).
        beta_brasil: (B, 8, 4).
        fluxos_brasil: (B, 8, 4).
        maior_numero_condicao: Maior número de condição de G entre todas as
            réplicas e unidades de ajuste.
        total_iteracoes_solver: Soma das iterações do SLSQP em todas as réplicas.
    """

    beta_por_regiao: np.ndarray
    fluxos_por_regiao: np.ndarray
    beta_brasil: np.ndarray
    fluxos_brasil: np.ndarray
    maior_numero_condicao: float
    total_iteracoes_solver: int


# ---------------------------------------------------------------------------
# Carregamento e montagem dos dados
# ---------------------------------------------------------------------------


def carregar_base_municipal(caminho_parquet: Path) -> pd.DataFrame:
    """Lê o parquet de resultados por município e turno.

    Args:
        caminho_parquet: Caminho do arquivo `presidente_municipio_turnos.parquet`.

    Returns:
        A base completa (inclusive exterior), sem nenhuma transformação.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
    """
    if not caminho_parquet.is_file():
        raise FileNotFoundError(f"Base não encontrada: {caminho_parquet}")

    base = pd.read_parquet(caminho_parquet)
    LOGGER.info(
        "Base lida de %s: %d linhas, %d colunas.",
        caminho_parquet,
        base.shape[0],
        base.shape[1],
    )
    return base


def validar_colunas_obrigatorias(base: pd.DataFrame) -> None:
    """Garante que a base possua todas as colunas usadas pelo modelo.

    Raises:
        KeyError: Se alguma coluna obrigatória estiver ausente.
    """
    colunas_ausentes = set(COLUNAS_OBRIGATORIAS).difference(base.columns)

    if colunas_ausentes:
        nomes_ausentes = sorted(colunas_ausentes)
        raise KeyError(f"Colunas obrigatórias ausentes: {nomes_ausentes}")


def selecionar_municipios_brasileiros(base: pd.DataFrame) -> pd.DataFrame:
    """Remove as unidades do exterior (`fl_exterior == True`).

    O exterior (ZZ) é excluído porque tem comparecimento ~40%, unidades
    minúsculas e comportamento distinto (ESPECIFICACAO.md, seção 3).

    Args:
        base: Base completa de resultados.

    Returns:
        Apenas os municípios brasileiros, com índice reiniciado.

    Raises:
        ErroDadosInvalidos: Se `fl_exterior` tiver valores nulos.
    """
    validar_colunas_obrigatorias(base)

    marcador_exterior = base[COLUNA_EXTERIOR]
    if marcador_exterior.isna().any():
        raise ErroDadosInvalidos("fl_exterior possui valores nulos.")

    mascara_brasil = ~marcador_exterior.astype(bool)
    municipios = base.loc[mascara_brasil].reset_index(drop=True)
    LOGGER.info("Municípios brasileiros selecionados: %d.", len(municipios))
    return municipios


def construir_contagens_origem(municipios: pd.DataFrame) -> np.ndarray:
    """Monta as contagens de eleitores por grupo de origem (1º turno).

    Ordem das colunas: `ORIGENS_1T`. A categoria `demais` soma os partidos
    de `NUMEROS_CANDIDATOS_DEMAIS`; `abstencao` inclui seções não instaladas.

    Args:
        municipios: Municípios brasileiros.

    Returns:
        Matriz inteira (n, 8).
    """
    colunas_demais = []
    for numero_candidato in NUMEROS_CANDIDATOS_DEMAIS:
        colunas_demais.append(f"votos_1t_{numero_candidato}")

    votos_lula = municipios["votos_1t_13"].to_numpy(dtype=np.int64)
    votos_flavio = municipios["votos_1t_22"].to_numpy(dtype=np.int64)
    votos_cury = municipios["votos_1t_70"].to_numpy(dtype=np.int64)
    votos_renan = municipios["votos_1t_14"].to_numpy(dtype=np.int64)
    votos_caiado = municipios["votos_1t_55"].to_numpy(dtype=np.int64)
    votos_demais = municipios[colunas_demais].to_numpy(dtype=np.int64).sum(axis=1)
    brancos = municipios["brancos_1t"].to_numpy(dtype=np.int64)
    nulos = municipios["nulos_1t"].to_numpy(dtype=np.int64)
    abstencoes = municipios["abstencao_1t"].to_numpy(dtype=np.int64)
    nao_instaladas = municipios["nao_instaladas_1t"].to_numpy(dtype=np.int64)

    contagens = np.column_stack(
        [
            votos_lula,
            votos_flavio,
            votos_cury,
            votos_renan,
            votos_caiado,
            votos_demais,
            brancos + nulos,
            abstencoes + nao_instaladas,
        ]
    )
    return contagens


def construir_contagens_destino(municipios: pd.DataFrame) -> np.ndarray:
    """Monta as contagens de eleitores por destino (2º turno).

    Ordem das colunas: `DESTINOS_2T`; `abstencao` inclui seções não instaladas.

    Args:
        municipios: Municípios brasileiros.

    Returns:
        Matriz inteira (n, 4).
    """
    votos_lula = municipios["votos_2t_13"].to_numpy(dtype=np.int64)
    votos_flavio = municipios["votos_2t_22"].to_numpy(dtype=np.int64)
    brancos = municipios["brancos_2t"].to_numpy(dtype=np.int64)
    nulos = municipios["nulos_2t"].to_numpy(dtype=np.int64)
    abstencoes = municipios["abstencao_2t"].to_numpy(dtype=np.int64)
    nao_instaladas = municipios["nao_instaladas_2t"].to_numpy(dtype=np.int64)

    contagens = np.column_stack(
        [
            votos_lula,
            votos_flavio,
            brancos + nulos,
            abstencoes + nao_instaladas,
        ]
    )
    return contagens


def montar_dados_ecologicos(municipios: pd.DataFrame) -> DadosEcologicos:
    """Transforma a base municipal nas matrizes X e Y do modelo.

    X_ir = contagem do grupo r / aptos_1t_i e Y_ic = contagem do destino c /
    aptos_2t_i. Cada linha de X e de Y deve somar 1 (identidade contábil).

    Args:
        municipios: Municípios brasileiros (já sem exterior).

    Returns:
        Dados prontos para estimação.

    Raises:
        ErroDadosInvalidos: Se aptos não forem positivos ou se alguma linha
            não satisfizer a identidade de soma.
    """
    validar_colunas_obrigatorias(municipios)

    aptos_1t = municipios[COLUNA_APTOS_1T].to_numpy(dtype=np.int64)
    aptos_2t = municipios[COLUNA_APTOS_2T].to_numpy(dtype=np.int64)

    if (aptos_1t <= 0).any() or (aptos_2t <= 0).any():
        raise ErroDadosInvalidos("Há municípios com aptos não positivos.")

    contagens_origem = construir_contagens_origem(municipios)
    contagens_destino = construir_contagens_destino(municipios)

    soma_origem_por_municipio = contagens_origem.sum(axis=1)
    soma_destino_por_municipio = contagens_destino.sum(axis=1)

    municipios_origem_inconsistentes = int((soma_origem_por_municipio != aptos_1t).sum())
    municipios_destino_inconsistentes = int((soma_destino_por_municipio != aptos_2t).sum())
    if municipios_origem_inconsistentes > 0 or municipios_destino_inconsistentes > 0:
        raise ErroDadosInvalidos(
            "Identidade de soma violada: "
            f"{municipios_origem_inconsistentes} municípios no 1º turno e "
            f"{municipios_destino_inconsistentes} no 2º turno."
        )

    matriz_origem = contagens_origem / aptos_1t[:, np.newaxis]
    matriz_destino = contagens_destino / aptos_2t[:, np.newaxis]

    desvio_soma_origem = np.abs(matriz_origem.sum(axis=1) - 1.0).max()
    desvio_soma_destino = np.abs(matriz_destino.sum(axis=1) - 1.0).max()
    LOGGER.info(
        "Identidade 'linha soma 1': desvio máximo X=%.3e, Y=%.3e.",
        desvio_soma_origem,
        desvio_soma_destino,
    )
    if desvio_soma_origem > TOLERANCIA_SOMA_UNITARIA:
        raise ErroDadosInvalidos(f"Linhas de X não somam 1 (desvio {desvio_soma_origem:.3e}).")
    if desvio_soma_destino > TOLERANCIA_SOMA_UNITARIA:
        raise ErroDadosInvalidos(f"Linhas de Y não somam 1 (desvio {desvio_soma_destino:.3e}).")

    return DadosEcologicos(
        codigo_municipio=municipios["cd_municipio_tse"].to_numpy(dtype=str),
        regiao=municipios[COLUNA_REGIAO].to_numpy(dtype=str),
        aptos_1t=aptos_1t.astype(np.float64),
        aptos_2t=aptos_2t.astype(np.float64),
        contagens_origem=contagens_origem,
        contagens_destino=contagens_destino,
        matriz_origem=matriz_origem,
        matriz_destino=matriz_destino,
    )


def validar_ancoras(dados: DadosEcologicos) -> list[ResultadoAncora]:
    """Compara os totais da base com as âncoras certificadas.

    Verifica somas por categoria nos dois turnos, total de aptos e número de
    municípios (total e por região).

    Args:
        dados: Dados montados a partir da base real.

    Returns:
        Lista com uma comparação por âncora (aprovadas ou não).
    """
    resultados: list[ResultadoAncora] = []

    totais_origem = dados.contagens_origem.sum(axis=0)
    for posicao, nome_origem in enumerate(ORIGENS_1T):
        resultados.append(
            ResultadoAncora(
                nome=f"1t_{nome_origem}",
                esperado=ANCORAS_ORIGEM_1T[nome_origem],
                obtido=int(totais_origem[posicao]),
            )
        )
    resultados.append(
        ResultadoAncora("1t_aptos", ANCORA_APTOS_1T, int(dados.aptos_1t.sum()))
    )

    totais_destino = dados.contagens_destino.sum(axis=0)
    for posicao, nome_destino in enumerate(DESTINOS_2T):
        resultados.append(
            ResultadoAncora(
                nome=f"2t_{nome_destino}",
                esperado=ANCORAS_DESTINO_2T[nome_destino],
                obtido=int(totais_destino[posicao]),
            )
        )
    resultados.append(
        ResultadoAncora("2t_aptos", ANCORA_APTOS_2T, int(dados.aptos_2t.sum()))
    )

    resultados.append(
        ResultadoAncora("municipios_total", ANCORA_TOTAL_MUNICIPIOS, len(dados.regiao))
    )
    for nome_regiao in REGIOES:
        municipios_na_regiao = int((dados.regiao == nome_regiao).sum())
        resultados.append(
            ResultadoAncora(
                nome=f"municipios_{nome_regiao}",
                esperado=ANCORA_MUNICIPIOS_POR_REGIAO[nome_regiao],
                obtido=municipios_na_regiao,
            )
        )

    return resultados


def exigir_ancoras_aprovadas(resultados: list[ResultadoAncora]) -> None:
    """Interrompe a execução se qualquer âncora divergir.

    Raises:
        ErroAncora: Listando todas as âncoras divergentes.
    """
    divergentes = []
    for resultado in resultados:
        if not resultado.aprovada:
            divergentes.append(
                f"{resultado.nome}: esperado {resultado.esperado:,} obtido {resultado.obtido:,}"
            )

    if divergentes:
        raise ErroAncora("Âncoras divergentes: " + " | ".join(divergentes))


# ---------------------------------------------------------------------------
# Estimação: equações normais e solver restrito
# ---------------------------------------------------------------------------


def calcular_equacoes_normais(
    matriz_origem: np.ndarray,
    matriz_destino: np.ndarray,
    pesos: np.ndarray,
) -> EquacoesNormais:
    """Calcula G = X'WX e H = X'WY, divididos pela soma dos pesos.

    Dividir por uma constante positiva não altera o argmin do problema, mas
    mantém G e H em escala O(1) e dá sentido uniforme à tolerância do solver.

    Args:
        matriz_origem: X, (m, 8).
        matriz_destino: Y, (m, 4).
        pesos: Pesos não negativos por município, (m,). Em réplicas bootstrap
            são os pesos originais vezes a multiplicidade sorteada.

    Returns:
        As equações normais normalizadas.

    Raises:
        ErroDadosInvalidos: Se as dimensões forem incompatíveis ou o peso
            total não for positivo.
    """
    numero_linhas = matriz_origem.shape[0]
    if matriz_destino.shape[0] != numero_linhas or pesos.shape[0] != numero_linhas:
        raise ErroDadosInvalidos("X, Y e pesos devem ter o mesmo número de linhas.")

    peso_total = pesos.sum()
    if not peso_total > 0:
        raise ErroDadosInvalidos("A soma dos pesos deve ser positiva.")

    origem_ponderada = matriz_origem * pesos[:, np.newaxis]
    matriz_g = matriz_origem.T @ origem_ponderada / peso_total
    matriz_h = origem_ponderada.T @ matriz_destino / peso_total
    return EquacoesNormais(matriz_g=matriz_g, matriz_h=matriz_h)


def calcular_valor_objetivo(
    parametros: np.ndarray,
    matriz_g: np.ndarray,
    matriz_h: np.ndarray,
) -> float:
    """Valor do objetivo sem a constante: soma_c (b_c'G b_c - 2 b_c'H_c).

    Args:
        parametros: beta achatado por linhas, (32,).
        matriz_g: G, (8, 8).
        matriz_h: H, (8, 4).

    Returns:
        O valor escalar do objetivo.
    """
    beta = parametros.reshape(NUMERO_ORIGENS, NUMERO_DESTINOS)
    termo_quadratico = np.sum(beta * (matriz_g @ beta))
    termo_linear = np.sum(beta * matriz_h)
    return float(termo_quadratico - 2.0 * termo_linear)


def calcular_gradiente_objetivo(
    parametros: np.ndarray,
    matriz_g: np.ndarray,
    matriz_h: np.ndarray,
) -> np.ndarray:
    """Gradiente analítico do objetivo: 2 (G beta - H), achatado em (32,)."""
    beta = parametros.reshape(NUMERO_ORIGENS, NUMERO_DESTINOS)
    gradiente = 2.0 * (matriz_g @ beta - matriz_h)
    return gradiente.reshape(NUMERO_PARAMETROS)


def montar_matriz_restricao_soma_linhas() -> np.ndarray:
    """Matriz A (8, 32) tal que A @ beta_achatado = soma de cada linha de beta."""
    matriz_restricao = np.kron(
        np.eye(NUMERO_ORIGENS),
        np.ones((1, NUMERO_DESTINOS)),
    )
    return matriz_restricao


MATRIZ_RESTRICAO_SOMA_LINHAS = montar_matriz_restricao_soma_linhas()


def calcular_numero_condicao(matriz_g: np.ndarray) -> float:
    """Número de condição (norma 2) de G; `inf` se G for singular."""
    return float(np.linalg.cond(matriz_g))


def calcular_fatores_de_escala(matriz_g: np.ndarray) -> np.ndarray:
    """Fatores d_r = sqrt(G_rr) usados para pré-condicionar o solver.

    O SLSQP usa aproximações BFGS e é sensível à escala das variáveis. Os grupos
    pequenos (ex.: `demais`, ~0,4% dos aptos) têm G_rr ~ 1e-5 e levam o número
    de condição de G a ~1e6. Reescalar a variável de cada linha, gamma_r =
    d_r * beta_r, leva G a uma matriz de correlação (condição ~5e2).
    O problema reescalado tem a mesma solução em beta e o mesmo objetivo.

    Raises:
        ErroDadosInvalidos: Se algum grupo tiver G_rr não positivo (grupo
            ausente da amostra), caso em que beta não é identificável.
    """
    diagonal_g = np.diag(matriz_g)
    if (diagonal_g <= 0).any():
        raise ErroDadosInvalidos("Algum grupo de origem tem peso zero na amostra (G_rr <= 0).")

    return np.sqrt(diagonal_g)


def calcular_lacuna_de_dualidade(
    beta: np.ndarray,
    matriz_g: np.ndarray,
    matriz_h: np.ndarray,
) -> float:
    """Lacuna de Frank-Wolfe: limite superior comprovado de (objetivo - ótimo).

    O conjunto viável é o produto de 8 simplex (cada linha de beta). Para um
    objetivo convexo, f(beta) - f* <= soma_r [ g_r . beta_r - min_c g_rc ],
    com g = 2 (G beta - H). Vale para qualquer ponto viável e não depende do
    solver, então certifica a qualidade da solução.
    """
    gradiente = 2.0 * (matriz_g @ beta - matriz_h)
    termo_no_ponto = np.sum(gradiente * beta)
    termo_no_melhor_vertice = np.sum(gradiente.min(axis=1))
    return float(termo_no_ponto - termo_no_melhor_vertice)


def ajustar_beta_restrito(
    equacoes: EquacoesNormais,
    beta_inicial: np.ndarray | None = None,
) -> ResultadoAjuste:
    """Resolve o problema convexo restrito de 32 parâmetros por SLSQP.

    Minimiza soma_c (b_c'G b_c - 2 b_c'H_c) sujeito a beta em [0, 1] e a
    soma de cada linha de beta igual a 1. Internamente reescala as variáveis
    (gamma_r = d_r beta_r, d_r = sqrt(G_rr)); nesse espaço os limites viram
    0 <= gamma_rc <= d_r e a soma da linha r vale d_r. O beta devolvido está
    na escala original.

    Args:
        equacoes: G e H da unidade de ajuste.
        beta_inicial: Ponto de partida viável (8, 4). Se None, usa beta
            uniforme (cada linha com 1/4 em todos os destinos).

    Returns:
        O ajuste, com beta, objetivo, iterações, condições de G e lacuna de dualidade.

    Raises:
        ErroConvergenciaAjuste: Se o SLSQP não declarar sucesso, se a solução
            violar as restrições além da tolerância ou se a lacuna de
            dualidade exceder TOLERANCIA_LACUNA_DUALIDADE. Nunca devolve
            resultado silenciosamente não convergido.
    """
    if beta_inicial is None:
        beta_inicial = np.full((NUMERO_ORIGENS, NUMERO_DESTINOS), 1.0 / NUMERO_DESTINOS)

    fatores_escala = calcular_fatores_de_escala(equacoes.matriz_g)
    produto_externo_escala = np.outer(fatores_escala, fatores_escala)
    matriz_g_escalada = equacoes.matriz_g / produto_externo_escala * ESCALA_OBJETIVO_SLSQP
    matriz_h_escalada = equacoes.matriz_h / fatores_escala[:, np.newaxis] * ESCALA_OBJETIVO_SLSQP

    ponto_inicial = (beta_inicial * fatores_escala[:, np.newaxis]).reshape(NUMERO_PARAMETROS)
    limite_superior = np.repeat(fatores_escala, NUMERO_DESTINOS)
    limites = optimize.Bounds(
        lb=np.zeros(NUMERO_PARAMETROS),
        ub=limite_superior,
    )
    restricao_soma_linhas = optimize.LinearConstraint(
        MATRIZ_RESTRICAO_SOMA_LINHAS,
        lb=fatores_escala,
        ub=fatores_escala,
    )

    resultado_solver = optimize.minimize(
        calcular_valor_objetivo,
        ponto_inicial,
        args=(matriz_g_escalada, matriz_h_escalada),
        jac=calcular_gradiente_objetivo,
        method="SLSQP",
        bounds=limites,
        constraints=[restricao_soma_linhas],
        options={
            "ftol": TOLERANCIA_FUNCAO_SLSQP,
            "maxiter": MAXIMO_ITERACOES_SLSQP,
        },
    )

    if not resultado_solver.success:
        raise ErroConvergenciaAjuste(
            "SLSQP não convergiu: "
            f"status={resultado_solver.status}, mensagem='{resultado_solver.message}', "
            f"iterações={resultado_solver.nit}."
        )

    parametros_escalados = resultado_solver.x.reshape(NUMERO_ORIGENS, NUMERO_DESTINOS)
    beta_bruto = parametros_escalados / fatores_escala[:, np.newaxis]

    desvio_soma_linhas = np.abs(beta_bruto.sum(axis=1) - 1.0).max()
    menor_valor = beta_bruto.min()
    maior_valor = beta_bruto.max()
    violou_soma = desvio_soma_linhas > TOLERANCIA_VIABILIDADE_BETA
    violou_limites = (
        menor_valor < -TOLERANCIA_VIABILIDADE_BETA
        or maior_valor > 1.0 + TOLERANCIA_VIABILIDADE_BETA
    )
    if violou_soma or violou_limites:
        raise ErroConvergenciaAjuste(
            "Solução inviável: "
            f"desvio da soma={desvio_soma_linhas:.3e}, mínimo={menor_valor:.3e}, "
            f"máximo={maior_valor:.6f}."
        )

    # Remove apenas resíduos numéricos (<= TOLERANCIA_VIABILIDADE_BETA) fora de [0, 1].
    beta_ajustado = np.clip(beta_bruto, 0.0, 1.0)

    lacuna_dualidade = calcular_lacuna_de_dualidade(
        beta_ajustado,
        equacoes.matriz_g,
        equacoes.matriz_h,
    )
    if lacuna_dualidade > TOLERANCIA_LACUNA_DUALIDADE:
        raise ErroConvergenciaAjuste(
            f"Lacuna de dualidade {lacuna_dualidade:.3e} acima de "
            f"{TOLERANCIA_LACUNA_DUALIDADE:.1e}: solução não certificada como ótima."
        )

    valor_objetivo = calcular_valor_objetivo(
        beta_ajustado.reshape(NUMERO_PARAMETROS),
        equacoes.matriz_g,
        equacoes.matriz_h,
    )
    return ResultadoAjuste(
        beta=beta_ajustado,
        valor_objetivo=valor_objetivo,
        numero_iteracoes=int(resultado_solver.nit),
        numero_condicao_g=calcular_numero_condicao(equacoes.matriz_g),
        numero_condicao_g_escalada=calcular_numero_condicao(matriz_g_escalada),
        lacuna_dualidade=lacuna_dualidade,
    )


# ---------------------------------------------------------------------------
# Especificações, fluxos e agregação
# ---------------------------------------------------------------------------


def indices_por_regiao(regiao: np.ndarray) -> dict[str, np.ndarray]:
    """Posições (linhas) dos municípios de cada região, na ordem de REGIOES.

    Raises:
        ErroDadosInvalidos: Se alguma região de REGIOES não tiver municípios
            ou se houver município fora de REGIOES.
    """
    indices: dict[str, np.ndarray] = {}
    total_classificado = 0

    for nome_regiao in REGIOES:
        posicoes = np.flatnonzero(regiao == nome_regiao)
        if posicoes.size == 0:
            raise ErroDadosInvalidos(f"Região sem municípios: {nome_regiao}")
        indices[nome_regiao] = posicoes
        total_classificado += posicoes.size

    if total_classificado != regiao.shape[0]:
        raise ErroDadosInvalidos("Há municípios em região fora de REGIOES.")

    return indices


def montar_unidades_de_ajuste(
    especificacao: EspecificacaoModelo,
    indices_regionais: dict[str, np.ndarray],
    numero_municipios: int,
) -> dict[str, np.ndarray]:
    """Define quais municípios entram em cada ajuste da especificação.

    E1 e E3 ajustam cada região separadamente; E2 ajusta um único beta com
    todos os municípios (rótulo `Brasil`).
    """
    if especificacao.por_regiao:
        return dict(indices_regionais)

    return {ROTULO_BRASIL: np.arange(numero_municipios)}


def calcular_populacao_de_grupos_por_regiao(
    contagens_origem: np.ndarray,
    indices_regionais: dict[str, np.ndarray],
) -> np.ndarray:
    """N_reg[r] = soma_i aptos_1t_i * X_i[r] = contagem do grupo r na região.

    Esses totais são observados (não estimados); por isso são fixos também
    nas réplicas bootstrap.

    Returns:
        Matriz (5, 8): regiões na ordem de REGIOES, grupos na ordem de ORIGENS_1T.
    """
    populacao = np.zeros((len(REGIOES), NUMERO_ORIGENS))

    for posicao_regiao, nome_regiao in enumerate(REGIOES):
        posicoes = indices_regionais[nome_regiao]
        populacao[posicao_regiao, :] = contagens_origem[posicoes].sum(axis=0)

    return populacao


def calcular_fluxos_em_votos(
    beta: np.ndarray,
    populacao_de_grupos: np.ndarray,
) -> np.ndarray:
    """F[r, c] = beta[r, c] * N[r]: votos que migram de cada origem a cada destino."""
    return beta * populacao_de_grupos[:, np.newaxis]


def converter_fluxos_em_beta(fluxos: np.ndarray) -> np.ndarray:
    """beta[r, c] = F[r, c] / soma_c F[r, c].

    Raises:
        ErroDadosInvalidos: Se alguma origem tiver fluxo total zero.
    """
    total_por_origem = fluxos.sum(axis=1)
    if (total_por_origem <= 0).any():
        raise ErroDadosInvalidos("Origem com fluxo total nulo; beta indefinido.")

    return fluxos / total_por_origem[:, np.newaxis]


def calcular_pesos_do_ajuste(
    dados: DadosEcologicos,
    especificacao: EspecificacaoModelo,
    multiplicidade: np.ndarray,
) -> np.ndarray:
    """Pesos do ajuste: (aptos_1t ou 1) vezes a multiplicidade bootstrap."""
    if especificacao.ponderada:
        return dados.aptos_1t * multiplicidade

    return multiplicidade.astype(np.float64)


def estimar_especificacao(
    dados: DadosEcologicos,
    especificacao: EspecificacaoModelo,
    indices_regionais: dict[str, np.ndarray],
    populacao_de_grupos: np.ndarray,
    multiplicidade: np.ndarray,
    betas_iniciais: dict[str, np.ndarray] | None = None,
) -> EstimativaEspecificacao:
    """Estima beta e fluxos de uma especificação para um vetor de multiplicidades.

    Com `multiplicidade` = 1 em todos os municípios obtém-se a estimativa
    pontual; com contagens multinomiais, uma réplica bootstrap.

    Args:
        dados: Dados montados.
        especificacao: E1, E2 ou E3.
        indices_regionais: Posições dos municípios por região.
        populacao_de_grupos: N_reg, (5, 8), fixo.
        multiplicidade: Vezes que cada município entra na amostra, (n,).
        betas_iniciais: Ponto de partida por unidade de ajuste (opcional).

    Returns:
        A estimativa por região, o agregado Brasil e os ajustes do solver.
    """
    pesos = calcular_pesos_do_ajuste(dados, especificacao, multiplicidade)
    unidades = montar_unidades_de_ajuste(
        especificacao,
        indices_regionais,
        dados.regiao.shape[0],
    )

    resultados_ajuste: dict[str, ResultadoAjuste] = {}
    for rotulo_unidade, posicoes in unidades.items():
        equacoes = calcular_equacoes_normais(
            dados.matriz_origem[posicoes],
            dados.matriz_destino[posicoes],
            pesos[posicoes],
        )

        beta_inicial = None
        if betas_iniciais is not None:
            beta_inicial = betas_iniciais[rotulo_unidade]

        resultados_ajuste[rotulo_unidade] = ajustar_beta_restrito(equacoes, beta_inicial)

    numero_regioes = len(REGIOES)
    beta_por_regiao = np.zeros((numero_regioes, NUMERO_ORIGENS, NUMERO_DESTINOS))
    fluxos_por_regiao = np.zeros((numero_regioes, NUMERO_ORIGENS, NUMERO_DESTINOS))

    for posicao_regiao, nome_regiao in enumerate(REGIOES):
        if especificacao.por_regiao:
            beta_da_regiao = resultados_ajuste[nome_regiao].beta
        else:
            beta_da_regiao = resultados_ajuste[ROTULO_BRASIL].beta

        beta_por_regiao[posicao_regiao] = beta_da_regiao
        fluxos_por_regiao[posicao_regiao] = calcular_fluxos_em_votos(
            beta_da_regiao,
            populacao_de_grupos[posicao_regiao],
        )

    fluxos_brasil = fluxos_por_regiao.sum(axis=0)
    beta_brasil = converter_fluxos_em_beta(fluxos_brasil)

    return EstimativaEspecificacao(
        beta_por_regiao=beta_por_regiao,
        fluxos_por_regiao=fluxos_por_regiao,
        beta_brasil=beta_brasil,
        fluxos_brasil=fluxos_brasil,
        resultados_ajuste=resultados_ajuste,
    )


def extrair_betas_iniciais(estimativa: EstimativaEspecificacao) -> dict[str, np.ndarray]:
    """Betas de uma estimativa, por unidade de ajuste, para uso como ponto de partida."""
    betas_iniciais: dict[str, np.ndarray] = {}

    for rotulo_unidade, resultado in estimativa.resultados_ajuste.items():
        betas_iniciais[rotulo_unidade] = resultado.beta

    return betas_iniciais


# ---------------------------------------------------------------------------
# Bootstrap estratificado
# ---------------------------------------------------------------------------


def gerar_multiplicidades_bootstrap(
    indices_regionais: dict[str, np.ndarray],
    numero_municipios: int,
    numero_replicas: int,
    gerador: np.random.Generator,
) -> np.ndarray:
    """Sorteia, por região, quantas vezes cada município entra em cada réplica.

    Reamostrar n municípios com reposição dentro da região equivale a sortear
    contagens ~ Multinomial(n, 1/n, ..., 1/n). A soma das contagens de uma
    região é sempre igual ao número de municípios da região (estratificação).
    As regiões são sorteadas na ordem de REGIOES, com um único gerador.

    Args:
        indices_regionais: Posições dos municípios por região.
        numero_municipios: Total de municípios (colunas da saída).
        numero_replicas: B, número de réplicas.
        gerador: Gerador pseudoaleatório (semente definida pelo chamador).

    Returns:
        Matriz inteira (B, n) com as multiplicidades.
    """
    multiplicidades = np.zeros((numero_replicas, numero_municipios), dtype=np.int64)

    for nome_regiao in REGIOES:
        posicoes = indices_regionais[nome_regiao]
        tamanho_regiao = posicoes.shape[0]
        probabilidades = np.full(tamanho_regiao, 1.0 / tamanho_regiao)
        contagens_sorteadas = gerador.multinomial(
            tamanho_regiao,
            probabilidades,
            size=numero_replicas,
        )
        multiplicidades[:, posicoes] = contagens_sorteadas

    return multiplicidades


def executar_bootstrap(
    dados: DadosEcologicos,
    especificacao: EspecificacaoModelo,
    indices_regionais: dict[str, np.ndarray],
    populacao_de_grupos: np.ndarray,
    multiplicidades: np.ndarray,
    estimativa_pontual: EstimativaEspecificacao,
) -> ResultadoBootstrap:
    """Reajusta a especificação em cada réplica bootstrap.

    Cada réplica reajusta todas as unidades (5 regiões, ou o ajuste nacional
    em E2), recalcula os fluxos com N_reg fixo e agrega o Brasil. O ponto de
    partida do solver é o beta pontual (aceleração; o problema é convexo).

    Args:
        dados: Dados montados.
        especificacao: E1, E2 ou E3.
        indices_regionais: Posições dos municípios por região.
        populacao_de_grupos: N_reg, (5, 8).
        multiplicidades: Matriz (B, n) de contagens multinomiais.
        estimativa_pontual: Estimativa com a amostra original.

    Returns:
        Todas as réplicas e estatísticas de diagnóstico do solver.

    Raises:
        ErroConvergenciaAjuste: Se qualquer ajuste de qualquer réplica falhar.
    """
    numero_replicas = multiplicidades.shape[0]
    numero_regioes = len(REGIOES)
    betas_iniciais = extrair_betas_iniciais(estimativa_pontual)

    beta_por_regiao = np.zeros((numero_replicas, numero_regioes, NUMERO_ORIGENS, NUMERO_DESTINOS))
    fluxos_por_regiao = np.zeros_like(beta_por_regiao)
    beta_brasil = np.zeros((numero_replicas, NUMERO_ORIGENS, NUMERO_DESTINOS))
    fluxos_brasil = np.zeros_like(beta_brasil)
    maior_numero_condicao = 0.0
    total_iteracoes = 0

    for indice_replica in range(numero_replicas):
        try:
            estimativa_replica = estimar_especificacao(
                dados,
                especificacao,
                indices_regionais,
                populacao_de_grupos,
                multiplicidades[indice_replica],
                betas_iniciais,
            )
        except ErroConvergenciaAjuste as erro_ajuste:
            raise ErroConvergenciaAjuste(
                f"Réplica bootstrap {indice_replica} da {especificacao.nome}: {erro_ajuste}"
            ) from erro_ajuste

        beta_por_regiao[indice_replica] = estimativa_replica.beta_por_regiao
        fluxos_por_regiao[indice_replica] = estimativa_replica.fluxos_por_regiao
        beta_brasil[indice_replica] = estimativa_replica.beta_brasil
        fluxos_brasil[indice_replica] = estimativa_replica.fluxos_brasil

        for resultado_ajuste in estimativa_replica.resultados_ajuste.values():
            maior_numero_condicao = max(maior_numero_condicao, resultado_ajuste.numero_condicao_g)
            total_iteracoes += resultado_ajuste.numero_iteracoes

    return ResultadoBootstrap(
        beta_por_regiao=beta_por_regiao,
        fluxos_por_regiao=fluxos_por_regiao,
        beta_brasil=beta_brasil,
        fluxos_brasil=fluxos_brasil,
        maior_numero_condicao=maior_numero_condicao,
        total_iteracoes_solver=total_iteracoes,
    )


def calcular_intervalo_percentil(
    amostras_bootstrap: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Limites do IC 95% por percentis 2,5 e 97,5 ao longo do eixo das réplicas.

    Usa a interpolação linear padrão do NumPy (`np.percentile`).

    Args:
        amostras_bootstrap: Array com as réplicas no primeiro eixo.

    Returns:
        (limite inferior, limite superior), cada um sem o eixo das réplicas.
    """
    limite_inferior = np.percentile(amostras_bootstrap, PERCENTIL_IC_INFERIOR, axis=0)
    limite_superior = np.percentile(amostras_bootstrap, PERCENTIL_IC_SUPERIOR, axis=0)
    return limite_inferior, limite_superior


# ---------------------------------------------------------------------------
# Diagnósticos
# ---------------------------------------------------------------------------


def prever_fracoes_destino(
    matriz_origem: np.ndarray,
    regiao: np.ndarray,
    beta_por_regiao: np.ndarray,
) -> np.ndarray:
    """Frações previstas do 2º turno: Yhat_i = X_i beta_(região de i).

    Args:
        matriz_origem: X, (n, 8).
        regiao: Região de cada município, (n,).
        beta_por_regiao: (5, 8, 4), na ordem de REGIOES (em E2, o mesmo beta
            nas cinco regiões).

    Returns:
        Matriz (n, 4) de frações previstas por destino.
    """
    fracoes_previstas = np.zeros((matriz_origem.shape[0], NUMERO_DESTINOS))

    for posicao_regiao, nome_regiao in enumerate(REGIOES):
        posicoes = np.flatnonzero(regiao == nome_regiao)
        beta_da_regiao = beta_por_regiao[posicao_regiao]
        fracoes_previstas[posicoes] = matriz_origem[posicoes] @ beta_da_regiao

    return fracoes_previstas


def calcular_total_previsto_destino(
    fracoes_previstas: np.ndarray,
    aptos_2t: np.ndarray,
) -> np.ndarray:
    """Total previsto por destino: soma_i aptos_2t_i * Yhat_ic, shape (4,)."""
    contagens_previstas = fracoes_previstas * aptos_2t[:, np.newaxis]
    return contagens_previstas.sum(axis=0)


def calcular_r2_ponderado(
    matriz_destino: np.ndarray,
    fracoes_previstas: np.ndarray,
    pesos: np.ndarray,
) -> np.ndarray:
    """R² ponderado por destino: 1 - SQR / SQT, com média ponderada de Y.

    SQR = soma_i w_i (Y_ic - Yhat_ic)^2 e SQT = soma_i w_i (Y_ic - media_c)^2,
    onde media_c é a média de Y_c ponderada por w. Destino com variância
    ponderada menor ou igual a LIMIAR_VARIANCIA_NULA resulta em NaN (R²
    indefinido).

    Returns:
        Vetor (4,) com o R² de cada destino.
    """
    media_ponderada = (pesos[:, np.newaxis] * matriz_destino).sum(axis=0) / pesos.sum()

    residuos = matriz_destino - fracoes_previstas
    desvios_da_media = matriz_destino - media_ponderada

    soma_quadrados_residual = (pesos[:, np.newaxis] * residuos**2).sum(axis=0)
    soma_quadrados_total = (pesos[:, np.newaxis] * desvios_da_media**2).sum(axis=0)

    # Variância ponderada (por unidade de peso) menor que o limiar é ruído de
    # arredondamento de um Y constante: o R² é indefinido, não "muito negativo".
    variancia_ponderada = soma_quadrados_total / pesos.sum()
    variancia_nula = variancia_ponderada <= LIMIAR_VARIANCIA_NULA
    soma_quadrados_total_valida = np.where(variancia_nula, np.nan, soma_quadrados_total)

    r2 = 1.0 - soma_quadrados_residual / soma_quadrados_total_valida
    return r2


def listar_celulas_na_fronteira(
    beta: np.ndarray,
    tolerancia: float = TOLERANCIA_FRONTEIRA_BETA,
) -> list[tuple[str, str, float]]:
    """Células de beta iguais a 0 ou a 1 dentro da tolerância.

    Returns:
        Lista de (origem, destino, valor) em ordem de origem e destino.
    """
    celulas: list[tuple[str, str, float]] = []

    for posicao_origem, nome_origem in enumerate(ORIGENS_1T):
        for posicao_destino, nome_destino in enumerate(DESTINOS_2T):
            valor = float(beta[posicao_origem, posicao_destino])
            na_fronteira_inferior = valor <= tolerancia
            na_fronteira_superior = valor >= 1.0 - tolerancia
            if na_fronteira_inferior or na_fronteira_superior:
                celulas.append((nome_origem, nome_destino, valor))

    return celulas
