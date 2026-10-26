"""Reimplementação independente (B) da migração de votos por estado.

Pergunta de negócio: para onde foram, no 2º turno, os eleitores que no 1º turno
votaram em cada candidato, ESTADO a ESTADO, quando cada estado sozinho tem
poucos municípios efetivos? A solução (ver ESPECIFICACAO.md da pasta de A) é
ajustar cada estado com os próprios municípios mais a região (sem o próprio
estado) como pseudo-dados:

    J_u(beta) = (1/W_u) sum_{i em u} w_i ||Y_i - X_i beta||^2
              + (kappa/n_u) (1/W_{g\\u}) sum_{i em g\\u} w_i ||Y_i - X_i beta||^2

Método computacional deliberadamente diferente de A: nenhum scipy. O solver
(FISTA em lote + projeção exata no simplex de Duchi et al.) é o da
reimplementação regional B, importado de ``ecologia_b.py`` sem alterá-lo. A
montagem de X e Y, as estatísticas suficientes por estado, o termo "região sem
o estado", a validação cruzada e o bootstrap são escritos aqui.
"""

from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PASTA_ATUAL = Path(__file__).resolve().parent
RAIZ_PROJETO = PASTA_ATUAL.parent
PASTA_SOLVER_REGIONAL = RAIZ_PROJETO / "2026-10-26_inferencia_ecologica_reimplementacao"

# Importar sem gravar __pycache__ na pasta do solver (ela não pode ser alterada).
sys.dont_write_bytecode = True
sys.path.insert(0, str(PASTA_SOLVER_REGIONAL))
import ecologia_b as solver_b  # noqa: E402

LOGGER = logging.getLogger("migracao_uf_b")

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

CAMINHO_BASE = RAIZ_PROJETO / "dados" / "processados" / "presidente_municipio_turnos.parquet"
SEMENTE_PADRAO = 20261025
NUMERO_DOBRAS = 5
GRADE_KAPPA: list[float] = [0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0]
KAPPA_SOZINHO = 0.25
KAPPA_REGIAO = float("inf")

ORIGENS = solver_b.ORIGENS
DESTINOS = solver_b.DESTINOS
NUMERO_ORIGENS = len(ORIGENS)
NUMERO_DESTINOS = len(DESTINOS)
REGIOES = solver_b.REGIOES

# Layout do vetor de momentos ponderados por município (98 colunas).
FATIA_XX = slice(0, 64)
FATIA_XY = slice(64, 96)
COLUNA_YY = 96
COLUNA_PESO = 97
NUMERO_COLUNAS_MOMENTOS = 98

# Contagem de municípios por UF da tabela da seção 1 da especificação.
MUNICIPIOS_POR_UF: dict[str, int] = {
    "DF": 1, "RR": 15, "AP": 16, "AM": 62, "AC": 22, "RJ": 92, "MS": 79,
    "RO": 52, "AL": 102, "SP": 645, "SE": 75, "CE": 184, "RN": 167,
    "PI": 224, "TO": 139, "ES": 78, "GO": 246, "MT": 142, "PB": 223,
    "PE": 185, "PA": 144, "PR": 399, "BA": 417, "MA": 217, "RS": 497,
    "SC": 295, "MG": 853,
}
# n efetivo de Kish da tabela da seção 1 (1 casa decimal).
N_EFETIVO_TABELA: dict[str, float] = {
    "DF": 1.0, "RR": 2.7, "AP": 2.9, "AM": 3.5, "AC": 4.6, "RJ": 6.2,
    "MS": 8.6, "RO": 9.3, "AL": 12.3, "SP": 13.0, "SE": 13.1, "CE": 13.8,
    "RN": 16.7, "PI": 18.3, "TO": 18.3, "ES": 18.3, "GO": 18.4, "MT": 20.5,
    "PB": 21.1, "PE": 23.3, "PA": 24.9, "PR": 27.3, "BA": 28.5, "MA": 34.4,
    "RS": 40.7, "SC": 44.4, "MG": 50.0,
}

LIMIAR_FRONTEIRA = 1e-9
TOLERANCIA_SOLVER = 1e-13
MAXIMO_ITERACOES_SOLVER = 400_000

CONFIGURACAO_SOLVER = solver_b.ConfiguracaoSolver(
    tolerancia_relativa=TOLERANCIA_SOLVER,
    maximo_iteracoes=MAXIMO_ITERACOES_SOLVER,
)


# ---------------------------------------------------------------------------
# Estruturas
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DadosUf:
    """Matrizes eleitorais por município (sem exterior), com a geografia.

    Attributes:
        codigo_tse: cd_municipio_tse como inteiro, shape (n,).
        peso: aptos_1t (w_i), shape (n,).
        contagens_origem: Contagens por grupo de origem, shape (n, 8).
        x: Frações de origem (contagens / aptos_1t), shape (n, 8).
        y: Frações de destino (contagens / aptos_2t), shape (n, 4).
        ufs: UFs na ordem fixa de execução (ordem alfabética), lista de 27.
        indice_uf: Posição da UF do município em ``ufs``, shape (n,).
        regiao_da_uf: Região de cada UF, na mesma ordem de ``ufs``.
        dobra: int(codigo_tse) mod 5, shape (n,).
    """

    codigo_tse: np.ndarray
    peso: np.ndarray
    contagens_origem: np.ndarray
    x: np.ndarray
    y: np.ndarray
    ufs: list[str]
    indice_uf: np.ndarray
    regiao_da_uf: list[str]
    dobra: np.ndarray


@dataclasses.dataclass(frozen=True)
class AjustesUf:
    """Ajuste pontual de todas as UFs para um kappa.

    Attributes:
        beta: (27, 8, 4).
        kappa: Kappa usado (inf = só região).
        n_efetivo: (27,) Kish dos municípios usados.
        peso_regiao: (27,) kappa / (n + kappa), em fração.
        violacao_kkt: Violação KKT máxima absoluta por UF, (27,).
        violacao_kkt_relativa: Idem, relativa a 2 max|H|.
        residuo_projetado: Resíduo do gradiente projetado por UF.
        numero_condicao: Número de condição de G por UF.
        iteracoes: Iterações do FISTA por UF.
        convergiu: Critério de parada atingido por UF.
    """

    beta: np.ndarray
    kappa: float
    n_efetivo: np.ndarray
    peso_regiao: np.ndarray
    violacao_kkt: np.ndarray
    violacao_kkt_relativa: np.ndarray
    residuo_projetado: np.ndarray
    numero_condicao: np.ndarray
    iteracoes: np.ndarray
    convergiu: np.ndarray


# ---------------------------------------------------------------------------
# Carga e montagem de X/Y
# ---------------------------------------------------------------------------


def carregar_base_brasil(caminho: Path = CAMINHO_BASE) -> pd.DataFrame:
    """Lê o parquet e mantém só os 5.571 municípios (fl_exterior == False)."""
    if not caminho.exists():
        raise FileNotFoundError(f"Base não encontrada: {caminho}")
    base_completa = pd.read_parquet(caminho)
    mascara_brasil = ~base_completa["fl_exterior"].astype(bool)
    base_brasil = base_completa.loc[mascara_brasil].reset_index(drop=True)
    LOGGER.info(
        "Base lida: %d registros totais, %d municípios sem exterior.",
        len(base_completa),
        len(base_brasil),
    )
    return base_brasil


def somar_colunas(base: pd.DataFrame, colunas: list[str]) -> np.ndarray:
    """Soma colunas inteiras linha a linha (int64)."""
    bloco = base[colunas].to_numpy(dtype=np.int64)
    return bloco.sum(axis=1)


def montar_dados_uf(base: pd.DataFrame) -> tuple[DadosUf, np.ndarray, np.ndarray]:
    """Refaz as 8 origens e os 4 destinos a partir das colunas brutas.

    Returns:
        (dados, contagens_destino (n, 4), aptos_2t (n,)); as duas últimas só
        servem para validar as âncoras do 2º turno.

    Raises:
        ValueError: Se a identidade soma_origem == aptos_1t ou
            soma_destino == aptos_2t falhar em algum município.
    """
    aptos_1t = base["aptos_1t"].to_numpy(dtype=np.int64)
    aptos_2t = base["aptos_2t"].to_numpy(dtype=np.int64)

    colunas_demais = [
        "votos_1t_30",
        "votos_1t_80",
        "votos_1t_16",
        "votos_1t_27",
        "votos_1t_21",
        "votos_1t_35",
        "votos_1t_29",
    ]
    contagens_origem = np.column_stack(
        [
            somar_colunas(base, ["votos_1t_13"]),
            somar_colunas(base, ["votos_1t_22"]),
            somar_colunas(base, ["votos_1t_70"]),
            somar_colunas(base, ["votos_1t_14"]),
            somar_colunas(base, ["votos_1t_55"]),
            somar_colunas(base, colunas_demais),
            somar_colunas(base, ["brancos_1t", "nulos_1t"]),
            somar_colunas(base, ["abstencao_1t", "nao_instaladas_1t"]),
        ]
    )
    contagens_destino = np.column_stack(
        [
            somar_colunas(base, ["votos_2t_13"]),
            somar_colunas(base, ["votos_2t_22"]),
            somar_colunas(base, ["brancos_2t", "nulos_2t"]),
            somar_colunas(base, ["abstencao_2t", "nao_instaladas_2t"]),
        ]
    )

    linhas_origem_invalidas = int((contagens_origem.sum(axis=1) != aptos_1t).sum())
    linhas_destino_invalidas = int((contagens_destino.sum(axis=1) != aptos_2t).sum())
    if linhas_origem_invalidas or linhas_destino_invalidas:
        raise ValueError(
            "Identidade violada: origem != aptos_1t em "
            f"{linhas_origem_invalidas} municípios; destino != aptos_2t em "
            f"{linhas_destino_invalidas}."
        )

    x = contagens_origem / aptos_1t[:, None]
    y = contagens_destino / aptos_2t[:, None]

    ufs = sorted(base["sg_uf"].unique().tolist())
    mapa_uf = {sigla: posicao for posicao, sigla in enumerate(ufs)}
    indice_uf = base["sg_uf"].map(mapa_uf).to_numpy(dtype=np.int64)

    regiao_por_uf = base.groupby("sg_uf")["nm_regiao"].nunique()
    if int(regiao_por_uf.max()) != 1:
        raise ValueError("Há UF associada a mais de uma região.")
    regiao_da_uf: list[str] = []
    for sigla in ufs:
        nome_regiao = str(base.loc[base["sg_uf"] == sigla, "nm_regiao"].iloc[0])
        regiao_da_uf.append(nome_regiao)

    codigo_tse = base["cd_municipio_tse"].astype(int).to_numpy(dtype=np.int64)
    dobra = codigo_tse % NUMERO_DOBRAS

    return DadosUf(
        codigo_tse=codigo_tse,
        peso=aptos_1t.astype(np.float64),
        contagens_origem=contagens_origem,
        x=x,
        y=y,
        ufs=ufs,
        indice_uf=indice_uf,
        regiao_da_uf=regiao_da_uf,
        dobra=dobra,
    ), contagens_destino, aptos_2t


def validar_ancoras_uf(
    dados: DadosUf,
    contagens_destino: np.ndarray,
    aptos_2t: np.ndarray,
) -> dict[str, tuple[float, float, bool]]:
    """Confere âncoras nacionais, municípios por região/UF e n efetivo da tabela.

    Returns:
        nome -> (esperado, calculado, passou).

    Raises:
        ValueError: Se qualquer âncora exata divergir (nunca se força).
    """
    resultados: dict[str, tuple[float, float, bool]] = {}

    totais_origem = dados.contagens_origem.sum(axis=0)
    for posicao, nome in enumerate(ORIGENS):
        esperado = float(solver_b.ANCORAS_ORIGEM[nome])
        calculado = float(totais_origem[posicao])
        resultados[f"soma_u N_u[{nome}]"] = (esperado, calculado, esperado == calculado)
    esperado_aptos = float(solver_b.ANCORA_APTOS_1T)
    calculado_aptos = float(dados.peso.sum())
    resultados["aptos_1t"] = (esperado_aptos, calculado_aptos, esperado_aptos == calculado_aptos)

    totais_destino = contagens_destino.sum(axis=0)
    for posicao, nome in enumerate(DESTINOS):
        esperado = float(solver_b.ANCORAS_DESTINO[nome])
        calculado = float(totais_destino[posicao])
        resultados[f"2t_{nome}"] = (esperado, calculado, esperado == calculado)
    esperado_aptos_2t = float(solver_b.ANCORA_APTOS_2T)
    calculado_aptos_2t = float(aptos_2t.sum())
    resultados["aptos_2t"] = (
        esperado_aptos_2t,
        calculado_aptos_2t,
        esperado_aptos_2t == calculado_aptos_2t,
    )

    esperado_municipios = float(solver_b.ANCORA_MUNICIPIOS)
    calculado_municipios = float(len(dados.peso))
    resultados["municipios"] = (
        esperado_municipios,
        calculado_municipios,
        esperado_municipios == calculado_municipios,
    )

    for nome_regiao in REGIOES:
        esperado = float(solver_b.ANCORAS_MUNICIPIOS_REGIAO[nome_regiao])
        posicoes_uf = [
            posicao for posicao, regiao in enumerate(dados.regiao_da_uf) if regiao == nome_regiao
        ]
        mascara = np.isin(dados.indice_uf, posicoes_uf)
        calculado = float(mascara.sum())
        resultados[f"municipios_{nome_regiao}"] = (esperado, calculado, esperado == calculado)

    contagem_por_uf = np.bincount(dados.indice_uf, minlength=len(dados.ufs))
    for posicao, sigla in enumerate(dados.ufs):
        esperado = float(MUNICIPIOS_POR_UF[sigla])
        calculado = float(contagem_por_uf[posicao])
        resultados[f"municipios_{sigla}"] = (esperado, calculado, esperado == calculado)

    n_efetivo = calcular_kish_por_uf(dados)
    for posicao, sigla in enumerate(dados.ufs):
        esperado = N_EFETIVO_TABELA[sigla]
        calculado = float(round(n_efetivo[posicao], 1))
        resultados[f"n_efetivo_{sigla}"] = (esperado, calculado, abs(esperado - calculado) < 1e-9)

    reprovadas = [nome for nome, (_, _, passou) in resultados.items() if not passou]
    if reprovadas:
        raise ValueError(f"Âncoras divergentes (investigar, não forçar): {reprovadas}")
    LOGGER.info("Todas as %d âncoras conferem.", len(resultados))
    return resultados


def calcular_kish(pesos: np.ndarray) -> float:
    """n efetivo de Kish: (soma w)^2 / soma w^2. Zero para conjunto vazio."""
    if pesos.size == 0:
        return 0.0
    soma = float(pesos.sum())
    soma_quadrados = float((pesos**2).sum())
    return soma * soma / soma_quadrados


def calcular_kish_por_uf(dados: DadosUf) -> np.ndarray:
    """Kish de cada UF sobre todos os seus municípios."""
    resultado = np.zeros(len(dados.ufs))
    for posicao in range(len(dados.ufs)):
        pesos_uf = dados.peso[dados.indice_uf == posicao]
        resultado[posicao] = calcular_kish(pesos_uf)
    return resultado


def calcular_populacao_origem_uf(dados: DadosUf) -> np.ndarray:
    """N_u[r]: contagem do grupo r de origem em cada UF (27, 8)."""
    resultado = np.zeros((len(dados.ufs), NUMERO_ORIGENS))
    for posicao in range(len(dados.ufs)):
        mascara = dados.indice_uf == posicao
        resultado[posicao] = dados.contagens_origem[mascara].sum(axis=0)
    return resultado


def substituir_destino(dados: DadosUf, y_novo: np.ndarray) -> DadosUf:
    """Cópia de ``dados`` com Y trocado (usada nos testes sintéticos)."""
    return dataclasses.replace(dados, y=y_novo)


# ---------------------------------------------------------------------------
# Estatísticas suficientes (momentos ponderados por município)
# ---------------------------------------------------------------------------


def montar_momentos(dados: DadosUf) -> np.ndarray:
    """Momentos w_i * [vec(x x^T), vec(x y^T), y.y, 1] por município, (n, 98).

    Somando as linhas de um conjunto de municípios (ou com multiplicidades do
    bootstrap) obtém-se, sem tocar nos dados brutos, G, H, a constante e W do
    termo quadrático daquele conjunto.
    """
    numero_municipios = dados.x.shape[0]
    produtos_xx = dados.x[:, :, None] * dados.x[:, None, :]
    produtos_xy = dados.x[:, :, None] * dados.y[:, None, :]
    produtos_yy = (dados.y * dados.y).sum(axis=1)
    peso = dados.peso
    momentos = np.zeros((numero_municipios, NUMERO_COLUNAS_MOMENTOS))
    momentos[:, FATIA_XX] = produtos_xx.reshape(numero_municipios, -1) * peso[:, None]
    momentos[:, FATIA_XY] = produtos_xy.reshape(numero_municipios, -1) * peso[:, None]
    momentos[:, COLUNA_YY] = produtos_yy * peso
    momentos[:, COLUNA_PESO] = peso
    return momentos


def somar_momentos_por_uf(
    dados: DadosUf, momentos: np.ndarray, indicador_incluidos: np.ndarray
) -> np.ndarray:
    """Soma de momentos por UF restrita aos municípios com indicador 1 -> (27, 98)."""
    resultado = np.zeros((len(dados.ufs), NUMERO_COLUNAS_MOMENTOS))
    for posicao in range(len(dados.ufs)):
        mascara = (dados.indice_uf == posicao) & (indicador_incluidos > 0)
        resultado[posicao] = momentos[mascara].sum(axis=0)
    return resultado


def soma_regiao_sem_uf(
    dados: DadosUf, momentos_por_uf: np.ndarray, posicao_uf: int
) -> np.ndarray:
    """Soma dos momentos das demais UFs da mesma região, g \\ u.

    Funciona para momentos de shape (27, ...) ou (27, B, ...): soma sobre o
    primeiro eixo apenas as UFs irmãs.
    """
    regiao_alvo = dados.regiao_da_uf[posicao_uf]
    posicoes_irmas = [
        posicao
        for posicao, regiao in enumerate(dados.regiao_da_uf)
        if regiao == regiao_alvo and posicao != posicao_uf
    ]
    return momentos_por_uf[posicoes_irmas].sum(axis=0)


def pesos_do_problema(
    peso_estado_bruto: np.ndarray,
    n_efetivo: np.ndarray,
    kappa: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Pesos relativos (estado, região) que somam 1.

    Estado : região = n_u : kappa, ou seja, estado = n/(n+kappa) e região =
    kappa/(n+kappa). Para kappa infinito, ou estado sem peso (sem municípios de
    treino), o problema é só o termo da região.
    """
    tem_estado = peso_estado_bruto > 0.0
    if np.isinf(kappa):
        peso_estado = np.zeros_like(n_efetivo, dtype=np.float64)
    else:
        peso_estado = np.where(tem_estado, n_efetivo / (n_efetivo + kappa), 0.0)
    peso_regiao = 1.0 - peso_estado
    return peso_estado, peso_regiao


def montar_problema_qp(
    momentos_estado: np.ndarray,
    momentos_regiao: np.ndarray,
    n_efetivo: np.ndarray,
    kappa: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Monta (G, H, constante) normalizados de um lote de problemas.

    O objetivo J_u é dividido por (1 + kappa/n_u): os pesos relativos passam a
    n/(n+kappa) e kappa/(n+kappa), somando 1. O argmin e o número de condição
    de G não mudam com essa escala.

    Args:
        momentos_estado: (B, 98), soma de momentos dos municípios de treino.
        momentos_regiao: (B, 98), soma de momentos de g \\ u.
        n_efetivo: (B,), Kish do estado nos municípios de treino.
        kappa: Escalar positivo ou inf.

    Returns:
        (G (B,8,8), H (B,8,4), constante (B,)).
    """
    peso_estado_bruto = momentos_estado[:, COLUNA_PESO]
    peso_regiao_bruto = momentos_regiao[:, COLUNA_PESO]
    if np.any(peso_regiao_bruto <= 0.0):
        raise ValueError("Termo da região sem municípios (peso zero).")

    divisor_estado = np.where(peso_estado_bruto > 0.0, peso_estado_bruto, 1.0)
    media_estado = momentos_estado / divisor_estado[:, None]
    media_regiao = momentos_regiao / peso_regiao_bruto[:, None]

    peso_estado, peso_regiao = pesos_do_problema(peso_estado_bruto, n_efetivo, kappa)
    combinado = peso_estado[:, None] * media_estado + peso_regiao[:, None] * media_regiao

    numero_problemas = combinado.shape[0]
    g = combinado[:, FATIA_XX].reshape(numero_problemas, NUMERO_ORIGENS, NUMERO_ORIGENS)
    h = combinado[:, FATIA_XY].reshape(numero_problemas, NUMERO_ORIGENS, NUMERO_DESTINOS)
    constante = combinado[:, COLUNA_YY]
    return g, h, constante


def beta_inicial_uniforme(numero_problemas: int) -> np.ndarray:
    """Ponto inicial uniforme (1/4) para um lote."""
    return solver_b.beta_inicial_uniforme(numero_problemas)


def resolver_lote(
    g: np.ndarray,
    h: np.ndarray,
    constante: np.ndarray,
    beta_inicial: np.ndarray,
    configuracao: solver_b.ConfiguracaoSolver = CONFIGURACAO_SOLVER,
) -> tuple[solver_b.ResultadoSolver, solver_b.ViolacaoKkt, np.ndarray]:
    """Resolve o lote com o FISTA e mede KKT e número de condição."""
    resultado = solver_b.resolver_fista(g, h, constante, beta_inicial, configuracao)
    violacao = solver_b.calcular_violacao_kkt(g, h, resultado.beta)
    _, _, condicao = solver_b.numeros_de_condicao(g)
    return resultado, violacao, condicao


# ---------------------------------------------------------------------------
# Ajuste pontual de todas as UFs para um kappa
# ---------------------------------------------------------------------------


def ajustar_ufs(
    dados: DadosUf,
    momentos: np.ndarray,
    kappa: float,
    beta_inicial: np.ndarray | None = None,
) -> AjustesUf:
    """Ajusta as 27 UFs com todos os municípios, para um kappa."""
    numero_ufs = len(dados.ufs)
    indicador_todos = np.ones(len(dados.peso))
    momentos_por_uf = somar_momentos_por_uf(dados, momentos, indicador_todos)
    n_efetivo = calcular_kish_por_uf(dados)

    momentos_regiao = np.zeros((numero_ufs, NUMERO_COLUNAS_MOMENTOS))
    for posicao in range(numero_ufs):
        momentos_regiao[posicao] = soma_regiao_sem_uf(dados, momentos_por_uf, posicao)

    g, h, constante = montar_problema_qp(momentos_por_uf, momentos_regiao, n_efetivo, kappa)
    if beta_inicial is None:
        beta_inicial = beta_inicial_uniforme(numero_ufs)
    resultado, violacao, condicao = resolver_lote(g, h, constante, beta_inicial)

    _, peso_regiao = pesos_do_problema(momentos_por_uf[:, COLUNA_PESO], n_efetivo, kappa)
    return AjustesUf(
        beta=resultado.beta,
        kappa=kappa,
        n_efetivo=n_efetivo,
        peso_regiao=peso_regiao,
        violacao_kkt=violacao.maxima_absoluta,
        violacao_kkt_relativa=violacao.maxima_relativa,
        residuo_projetado=violacao.residuo_gradiente_projetado,
        numero_condicao=condicao,
        iteracoes=resultado.iteracoes,
        convergiu=resultado.convergiu,
    )


# ---------------------------------------------------------------------------
# Validação cruzada
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ResultadoValidacao:
    """Erros de validação cruzada.

    Attributes:
        grade: Valores de kappa, com inf na última posição.
        erro_por_uf_dobra: (len(grade), 27, 5) soma de w ||Y - Yhat||^2 no teste.
        violacao_kkt_maxima: Maior violação absoluta entre todos os ajustes.
        violacao_kkt_relativa_maxima: Idem, relativa.
        nao_convergidos: Número de ajustes que bateram o limite de iterações.
        numero_ajustes: Total de ajustes realizados.
    """

    grade: list[float]
    erro_por_uf_dobra: np.ndarray
    violacao_kkt_maxima: float
    violacao_kkt_relativa_maxima: float
    nao_convergidos: int
    numero_ajustes: int

    def erro_total(self) -> np.ndarray:
        """Erro somado em UFs e dobras para cada kappa."""
        return self.erro_por_uf_dobra.sum(axis=(1, 2))

    def erro_por_uf(self) -> np.ndarray:
        """Erro somado nas dobras, (len(grade), 27)."""
        return self.erro_por_uf_dobra.sum(axis=2)


def erro_quadratico_ponderado(
    x: np.ndarray, y: np.ndarray, peso: np.ndarray, beta: np.ndarray
) -> float:
    """sum_i w_i ||Y_i - X_i beta||^2 no conjunto dado."""
    previsao = x @ beta
    residuo = y - previsao
    soma_quadrados = (residuo**2).sum(axis=1)
    return float((peso * soma_quadrados).sum())


def validar_cruzado(
    dados: DadosUf,
    momentos: np.ndarray,
    grade_kappa: list[float] = GRADE_KAPPA,
) -> ResultadoValidacao:
    """Validação cruzada de 5 dobras (cd_municipio_tse mod 5) para a grade de kappa.

    Em cada (UF, dobra) com municípios de teste: o termo do estado usa os
    municípios da UF fora da dobra (n_u recalculado), o termo da região usa
    todos os municípios de g \\ u. A UF sem municípios de treino na dobra usa só
    o termo da região. Kappa infinito é calculado por último como referência.
    """
    numero_ufs = len(dados.ufs)
    grade_completa = list(grade_kappa) + [KAPPA_REGIAO]

    momentos_todos_por_uf = somar_momentos_por_uf(dados, momentos, np.ones(len(dados.peso)))
    momentos_regiao_por_uf = np.zeros((numero_ufs, NUMERO_COLUNAS_MOMENTOS))
    for posicao in range(numero_ufs):
        momentos_regiao_por_uf[posicao] = soma_regiao_sem_uf(
            dados, momentos_todos_por_uf, posicao
        )

    # Lista de tarefas (UF, dobra) com municípios de teste.
    tarefas_uf: list[int] = []
    tarefas_dobra: list[int] = []
    momentos_treino_lista: list[np.ndarray] = []
    n_treino_lista: list[float] = []
    for posicao in range(numero_ufs):
        mascara_uf = dados.indice_uf == posicao
        for numero_dobra in range(NUMERO_DOBRAS):
            mascara_teste = mascara_uf & (dados.dobra == numero_dobra)
            if not mascara_teste.any():
                continue
            mascara_treino = mascara_uf & (dados.dobra != numero_dobra)
            soma_treino = momentos[mascara_treino].sum(axis=0)
            n_treino = calcular_kish(dados.peso[mascara_treino])
            tarefas_uf.append(posicao)
            tarefas_dobra.append(numero_dobra)
            momentos_treino_lista.append(soma_treino)
            n_treino_lista.append(n_treino)

    numero_tarefas = len(tarefas_uf)
    momentos_treino = np.vstack(momentos_treino_lista)
    n_treino_array = np.asarray(n_treino_lista)
    momentos_regiao = momentos_regiao_por_uf[np.asarray(tarefas_uf)]

    erro = np.zeros((len(grade_completa), numero_ufs, NUMERO_DOBRAS))
    violacao_maxima = 0.0
    violacao_relativa_maxima = 0.0
    nao_convergidos = 0
    beta_anterior = beta_inicial_uniforme(numero_tarefas)

    for posicao_kappa, kappa in enumerate(grade_completa):
        g, h, constante = montar_problema_qp(
            momentos_treino, momentos_regiao, n_treino_array, kappa
        )
        resultado, violacao, _ = resolver_lote(g, h, constante, beta_anterior)
        beta_anterior = resultado.beta
        violacao_maxima = max(violacao_maxima, float(violacao.maxima_absoluta.max()))
        violacao_relativa_maxima = max(
            violacao_relativa_maxima, float(violacao.maxima_relativa.max())
        )
        nao_convergidos += int((~resultado.convergiu).sum())

        for numero_tarefa in range(numero_tarefas):
            posicao_uf = tarefas_uf[numero_tarefa]
            numero_dobra = tarefas_dobra[numero_tarefa]
            mascara_teste = (dados.indice_uf == posicao_uf) & (dados.dobra == numero_dobra)
            erro_tarefa = erro_quadratico_ponderado(
                dados.x[mascara_teste],
                dados.y[mascara_teste],
                dados.peso[mascara_teste],
                resultado.beta[numero_tarefa],
            )
            erro[posicao_kappa, posicao_uf, numero_dobra] = erro_tarefa
        LOGGER.info(
            "CV kappa=%s: erro total %.6f, iter max %d, KKT max %.2e.",
            kappa,
            erro[posicao_kappa].sum(),
            int(resultado.iteracoes.max()),
            float(violacao.maxima_absoluta.max()),
        )

    return ResultadoValidacao(
        grade=grade_completa,
        erro_por_uf_dobra=erro,
        violacao_kkt_maxima=violacao_maxima,
        violacao_kkt_relativa_maxima=violacao_relativa_maxima,
        nao_convergidos=nao_convergidos,
        numero_ajustes=numero_tarefas * len(grade_completa),
    )


def escolher_kappa_otimo(validacao: ResultadoValidacao) -> float:
    """kappa* = argmin do erro total sobre a grade finita (inf é só referência)."""
    erro_total = validacao.erro_total()
    numero_finitos = len(validacao.grade) - 1
    posicao_otima = int(np.argmin(erro_total[:numero_finitos]))
    return float(validacao.grade[posicao_otima])


# ---------------------------------------------------------------------------
# Bootstrap (reamostragem dentro de cada UF, kappa fixo)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ResultadoBootstrap:
    """Saída do bootstrap estadual.

    Attributes:
        beta: (27, B, 8, 4).
        populacao_reamostrada: (27, B, 8), N_u recalculado em cada réplica
            (só para sensibilidade; os votos principais usam N_u observado).
        violacao_kkt_maxima: Maior violação KKT absoluta em todos os ajustes.
        nao_convergidos: Ajustes que bateram o limite de iterações.
    """

    beta: np.ndarray
    populacao_reamostrada: np.ndarray
    violacao_kkt_maxima: float
    nao_convergidos: int


def executar_bootstrap(
    dados: DadosUf,
    momentos: np.ndarray,
    kappa: float,
    beta_pontual: np.ndarray,
    n_efetivo_fixo: np.ndarray,
    numero_replicas: int,
    semente: int = SEMENTE_PADRAO,
    recalcular_n_efetivo: bool = False,
) -> ResultadoBootstrap:
    """Bootstrap não paramétrico, estratificado por UF, com kappa fixo.

    Cada réplica reamostra, com reposição, os municípios dentro de cada UF
    (multiplicidades multinomiais). O termo da região de uma UF usa os
    municípios reamostrados das outras UFs da mesma réplica. kappa não é
    reescolhido. Por padrão n_u fica em seu valor observado (o peso da região
    kappa/(n_u+kappa) é o mesmo reportado); ``recalcular_n_efetivo`` recalcula o
    Kish sobre a amostra reamostrada, para sensibilidade.
    """
    gerador = np.random.default_rng(semente)
    numero_ufs = len(dados.ufs)
    peso_quadrado = dados.peso**2

    soma_por_uf = np.zeros((numero_ufs, numero_replicas, NUMERO_COLUNAS_MOMENTOS))
    populacao = np.zeros((numero_ufs, numero_replicas, NUMERO_ORIGENS))
    n_efetivo_replicas = np.zeros((numero_ufs, numero_replicas))
    for posicao in range(numero_ufs):
        indices_uf = np.flatnonzero(dados.indice_uf == posicao)
        tamanho = indices_uf.size
        probabilidades = np.full(tamanho, 1.0 / tamanho)
        multiplicidades = gerador.multinomial(tamanho, probabilidades, size=numero_replicas)
        soma_por_uf[posicao] = multiplicidades @ momentos[indices_uf]
        populacao[posicao] = multiplicidades @ dados.contagens_origem[indices_uf]
        soma_pesos = multiplicidades @ dados.peso[indices_uf]
        soma_pesos_quadrados = multiplicidades @ peso_quadrado[indices_uf]
        n_efetivo_replicas[posicao] = soma_pesos**2 / soma_pesos_quadrados

    beta_replicas = np.zeros((numero_ufs, numero_replicas, NUMERO_ORIGENS, NUMERO_DESTINOS))
    violacao_maxima = 0.0
    nao_convergidos = 0
    for posicao in range(numero_ufs):
        momentos_regiao = soma_regiao_sem_uf(dados, soma_por_uf, posicao)
        if recalcular_n_efetivo:
            n_efetivo = n_efetivo_replicas[posicao]
        else:
            n_efetivo = np.full(numero_replicas, n_efetivo_fixo[posicao])
        g, h, constante = montar_problema_qp(
            soma_por_uf[posicao], momentos_regiao, n_efetivo, kappa
        )
        inicial = np.broadcast_to(
            beta_pontual[posicao], (numero_replicas, NUMERO_ORIGENS, NUMERO_DESTINOS)
        ).copy()
        resultado, violacao, _ = resolver_lote(g, h, constante, inicial)
        beta_replicas[posicao] = resultado.beta
        violacao_maxima = max(violacao_maxima, float(violacao.maxima_absoluta.max()))
        nao_convergidos += int((~resultado.convergiu).sum())
        LOGGER.info(
            "Bootstrap %s: iter max %d, KKT max %.2e.",
            dados.ufs[posicao],
            int(resultado.iteracoes.max()),
            float(violacao.maxima_absoluta.max()),
        )

    return ResultadoBootstrap(
        beta=beta_replicas,
        populacao_reamostrada=populacao,
        violacao_kkt_maxima=violacao_maxima,
        nao_convergidos=nao_convergidos,
    )


# ---------------------------------------------------------------------------
# Região (E1 refeito) para o diagnóstico de coerência
# ---------------------------------------------------------------------------


def ajustar_regioes_e1(
    dados: DadosUf, momentos: np.ndarray
) -> tuple[np.ndarray, float, np.ndarray]:
    """Refaz E1 (β por região, ponderado) com o mesmo solver.

    Returns:
        (beta (5, 8, 4) na ordem de REGIOES, maior KKT absoluta, população de
        origem por região (5, 8)).
    """
    numero_regioes = len(REGIOES)
    medias = np.zeros((numero_regioes, NUMERO_COLUNAS_MOMENTOS))
    populacao = np.zeros((numero_regioes, NUMERO_ORIGENS))
    for posicao_regiao, nome_regiao in enumerate(REGIOES):
        posicoes_uf = [
            posicao for posicao, regiao in enumerate(dados.regiao_da_uf) if regiao == nome_regiao
        ]
        mascara = np.isin(dados.indice_uf, posicoes_uf)
        soma = momentos[mascara].sum(axis=0)
        medias[posicao_regiao] = soma / soma[COLUNA_PESO]
        populacao[posicao_regiao] = dados.contagens_origem[mascara].sum(axis=0)
    g = medias[:, FATIA_XX].reshape(numero_regioes, NUMERO_ORIGENS, NUMERO_ORIGENS)
    h = medias[:, FATIA_XY].reshape(numero_regioes, NUMERO_ORIGENS, NUMERO_DESTINOS)
    constante = medias[:, COLUNA_YY]
    resultado, violacao, _ = resolver_lote(g, h, constante, beta_inicial_uniforme(numero_regioes))
    return resultado.beta, float(violacao.maxima_absoluta.max()), populacao
