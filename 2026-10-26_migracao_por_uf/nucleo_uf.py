"""Núcleo da migração de votos por estado, puxada para a região.

Implementa `ESPECIFICACAO.md` desta pasta. Para o estado `u` da região `g`, o
objetivo é

    J_u(beta) = (1 / W_u) soma_{i em u}   w_i ||Y_i - X_i beta||^2
              + (kappa / n_u) (1 / W_{g\\u}) soma_{i em g\\u} w_i ||Y_i - X_i beta||^2

com `w_i = aptos_1t_i`, `n_u` = n efetivo de Kish do estado e `g\\u` = os demais
estados da região (sem o próprio estado). O problema é o mesmo QP de 32
parâmetros do modelo regional; o solver (SLSQP com reescala por sqrt(G_rr)) é
reaproveitado de `../2026-10-26_inferencia_ecologica/nucleo_inferencia.py`.

Estratégia de cálculo: G e H brutos (sem normalizar) são pré-calculados por
estado a partir de um produto por município (X_i X_i', X_i Y_i'); a "região sem
o estado" é a soma exata das estatísticas dos estados irmãos. Nenhum laço sobre
municípios dentro do objetivo.

Convenções de shape:
    n    municípios brasileiros (5.571)
    U    estados (27)
    X    (n, 8)   Y (n, 4)   beta (8, 4)
    produtos_por_municipio  (n, 96) = [vec(X_i X_i') (64), vec(X_i Y_i') (32)]
"""

import dataclasses
import logging
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PASTA_TRABALHO = Path(__file__).resolve().parent
PASTA_REGIONAL = PASTA_TRABALHO.parent / "2026-10-26_inferencia_ecologica"
CAMINHO_BASE_PARQUET = (
    PASTA_TRABALHO.parent / "dados" / "processados" / "presidente_municipio_turnos.parquet"
)
CAMINHO_TRANSFERENCIAS_E1 = PASTA_REGIONAL / "transferencias.csv"

# O solver regional é reaproveitado por importação; a pasta regional entra no
# FIM do sys.path para nunca sombrear módulos desta pasta.
if str(PASTA_REGIONAL) not in sys.path:
    sys.path.append(str(PASTA_REGIONAL))

import nucleo_inferencia as regional  # noqa: E402

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes do domínio (ESPECIFICACAO.md desta pasta)
# ---------------------------------------------------------------------------

COLUNA_UF = "sg_uf"
SEMENTE_UF = 20261025
NUMERO_REPLICAS_BOOTSTRAP_UF = 500
NUMERO_DOBRAS = 5

KAPPAS_GRADE: tuple[float, ...] = (
    0.25,
    0.5,
    1.0,
    2.0,
    4.0,
    8.0,
    16.0,
    32.0,
    64.0,
    128.0,
    256.0,
)
KAPPA_SOZINHO = 0.25
KAPPA_REGIAO = math.inf

CODIGO_UF = "UF"
CODIGO_UF_SOZINHO = "UF_SOZINHO"
CODIGO_UF_REGIAO = "UF_REGIAO"
CODIGOS_VERSOES: tuple[str, ...] = (CODIGO_UF, CODIGO_UF_SOZINHO, CODIGO_UF_REGIAO)

NUMERO_PRODUTOS_G = regional.NUMERO_ORIGENS * regional.NUMERO_ORIGENS
NUMERO_PRODUTOS_H = regional.NUMERO_ORIGENS * regional.NUMERO_DESTINOS
NUMERO_PRODUTOS_TOTAL = NUMERO_PRODUTOS_G + NUMERO_PRODUTOS_H

# Âncoras por UF copiadas da tabela da seção 1 da especificação.
ANCORA_MUNICIPIOS_POR_UF: dict[str, int] = {
    "DF": 1,
    "RR": 15,
    "AP": 16,
    "AM": 62,
    "AC": 22,
    "RJ": 92,
    "MS": 79,
    "RO": 52,
    "AL": 102,
    "SP": 645,
    "SE": 75,
    "CE": 184,
    "RN": 167,
    "PI": 224,
    "TO": 139,
    "ES": 78,
    "GO": 246,
    "MT": 142,
    "PB": 223,
    "PE": 185,
    "PA": 144,
    "PR": 399,
    "BA": 417,
    "MA": 217,
    "RS": 497,
    "SC": 295,
    "MG": 853,
}
ANCORA_N_EFETIVO_POR_UF: dict[str, float] = {
    "DF": 1.0,
    "RR": 2.7,
    "AP": 2.9,
    "AM": 3.5,
    "AC": 4.6,
    "RJ": 6.2,
    "MS": 8.6,
    "RO": 9.3,
    "AL": 12.3,
    "SP": 13.0,
    "SE": 13.1,
    "CE": 13.8,
    "RN": 16.7,
    "PI": 18.3,
    "TO": 18.3,
    "ES": 18.3,
    "GO": 18.4,
    "MT": 20.5,
    "PB": 21.1,
    "PE": 23.3,
    "PA": 24.9,
    "PR": 27.3,
    "BA": 28.5,
    "MA": 34.4,
    "RS": 40.7,
    "SC": 44.4,
    "MG": 50.0,
}
# A tabela da especificação traz o n efetivo com uma casa decimal.
TOLERANCIA_ANCORA_N_EFETIVO = 0.05 + 1e-9
NUMERO_UFS = len(ANCORA_MUNICIPIOS_POR_UF)

REPLICAS_ENTRE_LOGS = 100


# ---------------------------------------------------------------------------
# Exceções e estruturas de dados
# ---------------------------------------------------------------------------


class ErroDadosUF(ValueError):
    """A base por UF não satisfaz as premissas do modelo."""


@dataclasses.dataclass(frozen=True)
class BaseUF:
    """Base municipal organizada por estado, pronta para as estatísticas.

    Attributes:
        dados: X, Y, aptos e contagens (mesma montagem do modelo regional).
        lista_ufs: Siglas dos estados em ordem alfabética (U,).
        regiao_da_uf: Região de cada estado, mesma ordem de `lista_ufs`.
        posicao_uf_do_municipio: Índice (em `lista_ufs`) do estado de cada município, (n,).
        indicador_uf: Matriz (U, n) com 1 onde o município pertence ao estado.
        mascara_demais_ufs_da_regiao: Matriz (U, U) com 1 em [u, v] se `v` é outro
            estado da MESMA região de `u` (diagonal zerada).
        dobra_do_municipio: Dobra da validação cruzada, `int(cd_municipio_tse) mod 5`, (n,).
        produtos_por_municipio: (n, 96) = [vec(X_i X_i'), vec(X_i Y_i')].
        populacao_por_uf: N_u[r] = contagem observada do grupo r no estado u, (U, 8).
        codigos_municipio: Código TSE de cada município, (n,).
    """

    dados: regional.DadosEcologicos
    lista_ufs: tuple[str, ...]
    regiao_da_uf: tuple[str, ...]
    posicao_uf_do_municipio: np.ndarray
    indicador_uf: np.ndarray
    mascara_demais_ufs_da_regiao: np.ndarray
    dobra_do_municipio: np.ndarray
    produtos_por_municipio: np.ndarray
    populacao_por_uf: np.ndarray


@dataclasses.dataclass(frozen=True)
class EstatisticasPorUF:
    """Somas brutas (sem normalizar) por estado, para um vetor de multiplicidades.

    Attributes:
        soma_pesos: W_u = soma m_i w_i, (U,).
        soma_quadrados_dos_pesos: soma m_i w_i^2, (U,). Com `soma_pesos` dá o n
            efetivo de Kish; cada cópia de um município reamostrado conta como linha.
        g_bruta: soma m_i w_i X_i X_i', (U, 8, 8).
        h_bruta: soma m_i w_i X_i Y_i', (U, 8, 4).
    """

    soma_pesos: np.ndarray
    soma_quadrados_dos_pesos: np.ndarray
    g_bruta: np.ndarray
    h_bruta: np.ndarray


@dataclasses.dataclass(frozen=True)
class EquacoesDaUF:
    """Equações normais combinadas (estado + região) de um estado.

    Attributes:
        equacoes: G e H normalizados por (1 + kappa / n_u) (mesmo argmin de J_u).
        n_efetivo: n efetivo de Kish do estado nos dados usados (0 se não há dados).
        peso_regiao: Peso relativo da região no ótimo, kappa / (n_u + kappa); 1 se
            só o termo da região é usado.
    """

    equacoes: regional.EquacoesNormais
    n_efetivo: float
    peso_regiao: float


@dataclasses.dataclass(frozen=True)
class AjusteUF:
    """Ajuste de um estado: beta (8, 4), n efetivo, peso da região e diagnóstico do solver.

    `numero_tentativas` é 1 quando o ponto inicial recebido convergiu; 2 quando foi
    preciso recorrer ao ponto inicial uniforme de reserva (ver `ajustar_beta_da_uf`).
    """

    beta: np.ndarray
    n_efetivo: float
    peso_regiao: float
    resultado_solver: regional.ResultadoAjuste
    numero_tentativas: int


@dataclasses.dataclass(frozen=True)
class EstimativaVersao:
    """Estimativa pontual de uma versão (UF, UF_SOZINHO ou UF_REGIAO).

    Attributes:
        codigo: Rótulo da versão.
        kappa: Peso da região usado (infinito em UF_REGIAO).
        ajustes: Ajuste de cada estado, na ordem de `lista_ufs`.
        betas: (U, 8, 4).
        votos: Fluxos em votos, (U, 8, 4).
        n_efetivo: n efetivo de Kish de cada estado (amostra completa), (U,).
        peso_regiao: Peso da região no resultado de cada estado, (U,), em [0, 1].
    """

    codigo: str
    kappa: float
    ajustes: list[AjusteUF]
    betas: np.ndarray
    votos: np.ndarray
    n_efetivo: np.ndarray
    peso_regiao: np.ndarray


@dataclasses.dataclass(frozen=True)
class ResultadoValidacaoCruzada:
    """Curva de validação cruzada por kappa.

    Attributes:
        kappas: Grade de kappa, (K,).
        erro_por_kappa: Erro de validação sum_i w_i ||Y_i - Yhat_i||^2, (K,).
        erro_por_kappa_e_uf: Mesmo erro decomposto por estado, (K, U).
        erro_regiao: Erro de referência com kappa = infinito (padrão da região).
        erro_regiao_por_uf: Decomposição do erro de referência por estado, (U,).
        posicao_kappa_otimo: Índice do argmin em `kappas` (empate: menor kappa).
        soma_pesos_total: soma w_i de todos os municípios (normalizador do erro).
        numero_ajustes: Quantidade de ajustes executados.
        numero_retentativas: Ajustes que precisaram do ponto inicial uniforme de reserva.
    """

    kappas: np.ndarray
    erro_por_kappa: np.ndarray
    erro_por_kappa_e_uf: np.ndarray
    erro_regiao: float
    erro_regiao_por_uf: np.ndarray
    posicao_kappa_otimo: int
    soma_pesos_total: float
    numero_ajustes: int
    numero_retentativas: int

    @property
    def kappa_otimo(self) -> float:
        """Kappa que minimiza o erro de validação."""
        return float(self.kappas[self.posicao_kappa_otimo])

    @property
    def na_borda_da_grade(self) -> bool:
        """Indica se o kappa ótimo é o primeiro ou o último da grade."""
        ultima_posicao = self.kappas.shape[0] - 1
        return self.posicao_kappa_otimo in (0, ultima_posicao)


@dataclasses.dataclass(frozen=True)
class ResultadoBootstrapUF:
    """Réplicas bootstrap da versão UF.

    Attributes:
        betas: (B, U, 8, 4).
        maior_numero_condicao: Maior cond(G) entre todos os ajustes.
        maior_numero_condicao_escalada: Maior cond(G) após a reescala do solver.
        total_iteracoes: Soma das iterações do SLSQP.
        maior_lacuna_dualidade: Maior lacuna de Frank-Wolfe observada.
        segundos: Tempo de relógio gasto.
        numero_retentativas: Ajustes que precisaram do ponto inicial uniforme de reserva.
    """

    betas: np.ndarray
    maior_numero_condicao: float
    maior_numero_condicao_escalada: float
    total_iteracoes: int
    maior_lacuna_dualidade: float
    segundos: float
    numero_retentativas: int


# ---------------------------------------------------------------------------
# Carregamento e montagem
# ---------------------------------------------------------------------------


def carregar_municipios_brasileiros(caminho_parquet: Path) -> pd.DataFrame:
    """Lê a base e mantém só os municípios brasileiros (`fl_exterior == False`).

    Args:
        caminho_parquet: Caminho de `presidente_municipio_turnos.parquet`.

    Returns:
        Os 5.571 municípios, com índice reiniciado.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        KeyError: Se faltar coluna obrigatória (do modelo regional ou `sg_uf`).
    """
    base_completa = regional.carregar_base_municipal(caminho_parquet)
    municipios = regional.selecionar_municipios_brasileiros(base_completa)

    if COLUNA_UF not in municipios.columns:
        raise KeyError(f"Coluna obrigatória ausente: {COLUNA_UF}")

    return municipios


def calcular_dobras(codigos_municipio: np.ndarray, numero_dobras: int) -> np.ndarray:
    """Dobra determinística da validação cruzada: `int(cd_municipio_tse) mod numero_dobras`.

    A regra é fixa para que as duas implementações usem exatamente os mesmos grupos.

    Args:
        codigos_municipio: Códigos TSE (texto com zeros à esquerda), (n,).
        numero_dobras: Número de dobras (5).

    Returns:
        Vetor inteiro (n,) com valores em [0, numero_dobras).

    Raises:
        ValueError: Se algum código não for numérico ou `numero_dobras` < 1.
    """
    if numero_dobras < 1:
        raise ValueError("numero_dobras deve ser positivo.")

    dobras = np.zeros(codigos_municipio.shape[0], dtype=np.int64)

    for posicao, codigo in enumerate(codigos_municipio):
        codigo_inteiro = int(codigo)
        dobras[posicao] = codigo_inteiro % numero_dobras

    return dobras


def calcular_produtos_por_municipio(
    matriz_origem: np.ndarray,
    matriz_destino: np.ndarray,
) -> np.ndarray:
    """Produtos por município que alimentam G e H: [vec(X_i X_i'), vec(X_i Y_i')].

    Args:
        matriz_origem: X, (n, 8).
        matriz_destino: Y, (n, 4).

    Returns:
        Matriz (n, 96): 64 colunas de X_i X_i' e 32 de X_i Y_i', ambos achatados por linhas.
    """
    numero_municipios = matriz_origem.shape[0]

    origem_coluna = matriz_origem[:, :, np.newaxis]
    origem_linha = matriz_origem[:, np.newaxis, :]
    destino_linha = matriz_destino[:, np.newaxis, :]

    produto_origem_origem = origem_coluna * origem_linha
    produto_origem_destino = origem_coluna * destino_linha

    produtos_g = produto_origem_origem.reshape(numero_municipios, NUMERO_PRODUTOS_G)
    produtos_h = produto_origem_destino.reshape(numero_municipios, NUMERO_PRODUTOS_H)
    return np.concatenate([produtos_g, produtos_h], axis=1)


def montar_base_uf(municipios: pd.DataFrame) -> BaseUF:
    """Organiza os municípios brasileiros por estado e pré-calcula os produtos.

    Args:
        municipios: Saída de `carregar_municipios_brasileiros`.

    Returns:
        A base por UF (UFs em ordem alfabética).

    Raises:
        ErroDadosUF: Se uma UF pertencer a mais de uma região.
    """
    dados = regional.montar_dados_ecologicos(municipios)
    siglas_municipio = municipios[COLUNA_UF].to_numpy(dtype=str)
    regiao_municipio = municipios[regional.COLUNA_REGIAO].to_numpy(dtype=str)

    siglas_ordenadas = np.unique(siglas_municipio)
    posicao_uf_do_municipio = np.searchsorted(siglas_ordenadas, siglas_municipio)
    numero_municipios = siglas_municipio.shape[0]
    numero_ufs = siglas_ordenadas.shape[0]

    lista_ufs: list[str] = []
    regiao_da_uf: list[str] = []
    for posicao_uf in range(numero_ufs):
        sigla = str(siglas_ordenadas[posicao_uf])
        regioes_da_uf = np.unique(regiao_municipio[posicao_uf_do_municipio == posicao_uf])
        if regioes_da_uf.shape[0] != 1:
            raise ErroDadosUF(f"UF {sigla} pertence a {regioes_da_uf.shape[0]} regiões.")
        lista_ufs.append(sigla)
        regiao_da_uf.append(str(regioes_da_uf[0]))

    indicador_uf = np.zeros((numero_ufs, numero_municipios))
    indicador_uf[posicao_uf_do_municipio, np.arange(numero_municipios)] = 1.0

    mascara_demais = np.zeros((numero_ufs, numero_ufs))
    for posicao_uf in range(numero_ufs):
        for posicao_outra in range(numero_ufs):
            mesma_regiao = regiao_da_uf[posicao_uf] == regiao_da_uf[posicao_outra]
            outra_uf = posicao_uf != posicao_outra
            if mesma_regiao and outra_uf:
                mascara_demais[posicao_uf, posicao_outra] = 1.0

    dobras = calcular_dobras(dados.codigo_municipio, NUMERO_DOBRAS)
    produtos = calcular_produtos_por_municipio(dados.matriz_origem, dados.matriz_destino)
    populacao_por_uf = indicador_uf @ dados.contagens_origem.astype(np.float64)

    return BaseUF(
        dados=dados,
        lista_ufs=tuple(lista_ufs),
        regiao_da_uf=tuple(regiao_da_uf),
        posicao_uf_do_municipio=posicao_uf_do_municipio,
        indicador_uf=indicador_uf,
        mascara_demais_ufs_da_regiao=mascara_demais,
        dobra_do_municipio=dobras,
        produtos_por_municipio=produtos,
        populacao_por_uf=populacao_por_uf,
    )


def substituir_destino(base: BaseUF, nova_matriz_destino: np.ndarray) -> BaseUF:
    """Devolve uma base idêntica, mas com outra matriz Y (usada nos dados sintéticos).

    Recalcula os produtos X_i Y_i'. Contagens e aptos do 2º turno NÃO são
    atualizados: a estimação só usa X, Y e `aptos_1t`.

    Args:
        base: Base original.
        nova_matriz_destino: Y substituto, (n, 4).

    Raises:
        ErroDadosUF: Se o shape de Y for incompatível.
    """
    formato_esperado = base.dados.matriz_destino.shape
    if nova_matriz_destino.shape != formato_esperado:
        raise ErroDadosUF(
            f"Y sintético com shape {nova_matriz_destino.shape}; esperado {formato_esperado}."
        )

    dados_novos = dataclasses.replace(base.dados, matriz_destino=nova_matriz_destino)
    produtos_novos = calcular_produtos_por_municipio(
        dados_novos.matriz_origem,
        nova_matriz_destino,
    )
    return dataclasses.replace(base, dados=dados_novos, produtos_por_municipio=produtos_novos)


# ---------------------------------------------------------------------------
# Estatísticas por estado, n efetivo e âncoras
# ---------------------------------------------------------------------------


def calcular_n_efetivo_kish(soma_pesos: np.ndarray, soma_quadrados_dos_pesos: np.ndarray) -> np.ndarray:
    """n efetivo de Kish por estado: (soma w)^2 / soma w^2; 0 onde não há dados.

    Args:
        soma_pesos: Soma dos pesos por estado, (U,).
        soma_quadrados_dos_pesos: Soma dos quadrados dos pesos por estado, (U,).

    Returns:
        Vetor (U,) com o tamanho efetivo.
    """
    n_efetivo = np.zeros_like(soma_pesos, dtype=np.float64)
    existe_dado = soma_quadrados_dos_pesos > 0
    n_efetivo[existe_dado] = soma_pesos[existe_dado] ** 2 / soma_quadrados_dos_pesos[existe_dado]
    return n_efetivo


def calcular_estatisticas_por_uf(base: BaseUF, multiplicidade: np.ndarray) -> EstatisticasPorUF:
    """Somas brutas por estado com pesos `w_i = aptos_1t_i * multiplicidade_i`.

    `multiplicidade` vale 1 para a amostra original, 0 para município excluído
    (dobra de validação) e k para município sorteado k vezes no bootstrap.

    Args:
        base: Base por UF.
        multiplicidade: Vezes que cada município entra na amostra, (n,).

    Returns:
        As estatísticas por estado.

    Raises:
        ErroDadosUF: Se `multiplicidade` tiver tamanho incompatível ou valor negativo.
    """
    numero_municipios = base.dados.aptos_1t.shape[0]
    if multiplicidade.shape != (numero_municipios,):
        raise ErroDadosUF("multiplicidade deve ter um valor por município.")
    if (multiplicidade < 0).any():
        raise ErroDadosUF("multiplicidade não pode ser negativa.")

    aptos = base.dados.aptos_1t
    pesos = aptos * multiplicidade
    quadrados_dos_pesos = multiplicidade * aptos**2

    soma_pesos = base.indicador_uf @ pesos
    soma_quadrados = base.indicador_uf @ quadrados_dos_pesos

    produtos_ponderados = base.produtos_por_municipio * pesos[:, np.newaxis]
    somas_dos_produtos = base.indicador_uf @ produtos_ponderados

    numero_ufs = base.indicador_uf.shape[0]
    g_bruta = somas_dos_produtos[:, :NUMERO_PRODUTOS_G].reshape(
        numero_ufs,
        regional.NUMERO_ORIGENS,
        regional.NUMERO_ORIGENS,
    )
    h_bruta = somas_dos_produtos[:, NUMERO_PRODUTOS_G:].reshape(
        numero_ufs,
        regional.NUMERO_ORIGENS,
        regional.NUMERO_DESTINOS,
    )
    return EstatisticasPorUF(
        soma_pesos=soma_pesos,
        soma_quadrados_dos_pesos=soma_quadrados,
        g_bruta=g_bruta,
        h_bruta=h_bruta,
    )


def somar_demais_ufs_da_regiao(
    base: BaseUF,
    estatisticas: EstatisticasPorUF,
) -> EstatisticasPorUF:
    """Estatísticas de `g \\ u` para cada estado `u`: soma exata dos estados irmãos.

    Para o DF, os irmãos são GO + MT + MS. Somar os irmãos (em vez de subtrair o
    estado do total da região) evita perda de precisão.

    Args:
        base: Base por UF (traz a máscara de estados irmãos).
        estatisticas: Estatísticas por estado.

    Returns:
        Estatísticas em que a linha `u` já é a soma dos demais estados da região de `u`.
    """
    mascara = base.mascara_demais_ufs_da_regiao

    soma_pesos = mascara @ estatisticas.soma_pesos
    soma_quadrados = mascara @ estatisticas.soma_quadrados_dos_pesos
    g_bruta = np.tensordot(mascara, estatisticas.g_bruta, axes=([1], [0]))
    h_bruta = np.tensordot(mascara, estatisticas.h_bruta, axes=([1], [0]))

    return EstatisticasPorUF(
        soma_pesos=soma_pesos,
        soma_quadrados_dos_pesos=soma_quadrados,
        g_bruta=g_bruta,
        h_bruta=h_bruta,
    )


def validar_ancoras_por_uf(base: BaseUF) -> tuple[list[regional.ResultadoAncora], list[str]]:
    """Confere âncoras nacionais, contagens de municípios por UF e n efetivo de Kish.

    Verifica: totais por categoria nos dois turnos e municípios por região
    (regional); soma de N_u[r] = âncora nacional; 27 UFs com o número de
    municípios da tabela da especificação; n efetivo de Kish (tolerância de
    arredondamento da tabela).

    Args:
        base: Base por UF.

    Returns:
        (lista de âncoras inteiras comparadas, lista de textos de divergência do n efetivo).
    """
    resultados = regional.validar_ancoras(base.dados)

    totais_por_origem = base.populacao_por_uf.sum(axis=0)
    for posicao, nome_origem in enumerate(regional.ORIGENS_1T):
        resultados.append(
            regional.ResultadoAncora(
                nome=f"soma_N_uf_{nome_origem}",
                esperado=regional.ANCORAS_ORIGEM_1T[nome_origem],
                obtido=int(round(totais_por_origem[posicao])),
            )
        )

    resultados.append(regional.ResultadoAncora("numero_de_ufs", NUMERO_UFS, len(base.lista_ufs)))

    municipios_por_uf = base.indicador_uf.sum(axis=1)
    for posicao_uf, sigla in enumerate(base.lista_ufs):
        esperado = ANCORA_MUNICIPIOS_POR_UF.get(sigla, -1)
        resultados.append(
            regional.ResultadoAncora(
                nome=f"municipios_{sigla}",
                esperado=esperado,
                obtido=int(municipios_por_uf[posicao_uf]),
            )
        )

    estatisticas = calcular_estatisticas_por_uf(
        base,
        np.ones(base.dados.aptos_1t.shape[0]),
    )
    n_efetivo = calcular_n_efetivo_kish(
        estatisticas.soma_pesos,
        estatisticas.soma_quadrados_dos_pesos,
    )
    divergencias_n_efetivo: list[str] = []
    for posicao_uf, sigla in enumerate(base.lista_ufs):
        esperado_n = ANCORA_N_EFETIVO_POR_UF.get(sigla, float("nan"))
        diferenca = abs(n_efetivo[posicao_uf] - esperado_n)
        if not diferenca <= TOLERANCIA_ANCORA_N_EFETIVO:
            divergencias_n_efetivo.append(
                f"{sigla}: n efetivo {n_efetivo[posicao_uf]:.3f}, tabela {esperado_n}"
            )

    return resultados, divergencias_n_efetivo


def exigir_ancoras_por_uf(base: BaseUF) -> None:
    """Interrompe se qualquer âncora (inteira ou n efetivo) divergir.

    Raises:
        regional.ErroAncora: Listando todas as divergências.
    """
    resultados, divergencias_n_efetivo = validar_ancoras_por_uf(base)
    regional.exigir_ancoras_aprovadas(resultados)

    if divergencias_n_efetivo:
        texto = " | ".join(divergencias_n_efetivo)
        raise regional.ErroAncora(f"n efetivo divergente da tabela: {texto}")

    LOGGER.info(
        "Âncoras aprovadas: %d verificações inteiras e n efetivo de %d UFs.",
        len(resultados),
        len(base.lista_ufs),
    )


# ---------------------------------------------------------------------------
# Equações combinadas e ajuste por estado
# ---------------------------------------------------------------------------


def montar_equacoes_da_uf(
    estatisticas_uf: EstatisticasPorUF,
    estatisticas_demais: EstatisticasPorUF,
    posicao_uf: int,
    kappa: float,
) -> EquacoesDaUF:
    """Combina o termo do estado com o termo da região sem o estado.

    G = G_u / W_u + (kappa / n_u) G_{g\\u} / W_{g\\u}, e H análogo, divididos por
    (1 + kappa / n_u). A divisão é uma constante positiva (mesmo argmin) que
    mantém G e H em escala O(1), coerente com as tolerâncias do solver regional.

    Casos só-região (G = G_{g\\u} / W_{g\\u}):
      * `kappa` infinito (versão UF_REGIAO);
      * estado sem dados nos pesos usados (DF fora do treino de uma dobra).

    Args:
        estatisticas_uf: Somas brutas do estado (amostra usada no ajuste).
        estatisticas_demais: Somas brutas de `g \\ u` (linha `posicao_uf`).
        posicao_uf: Índice do estado.
        kappa: Peso da região em "municípios a mais" (0 < kappa <= infinito).

    Returns:
        Equações normalizadas, n efetivo do estado e peso da região.

    Raises:
        ErroDadosUF: Se `kappa` não for positivo ou `g \\ u` não tiver peso.
    """
    if not kappa > 0:
        raise ErroDadosUF(f"kappa deve ser positivo (recebido {kappa}).")

    soma_pesos_regiao = float(estatisticas_demais.soma_pesos[posicao_uf])
    if not soma_pesos_regiao > 0:
        raise ErroDadosUF("A região sem o estado não tem peso positivo.")

    g_regiao = estatisticas_demais.g_bruta[posicao_uf] / soma_pesos_regiao
    h_regiao = estatisticas_demais.h_bruta[posicao_uf] / soma_pesos_regiao

    soma_pesos_uf = float(estatisticas_uf.soma_pesos[posicao_uf])
    soma_quadrados_uf = float(estatisticas_uf.soma_quadrados_dos_pesos[posicao_uf])
    estado_tem_dados = soma_pesos_uf > 0 and soma_quadrados_uf > 0

    n_efetivo = 0.0
    if estado_tem_dados:
        n_efetivo = soma_pesos_uf**2 / soma_quadrados_uf

    usar_so_regiao = math.isinf(kappa) or not estado_tem_dados
    if usar_so_regiao:
        equacoes_regiao = regional.EquacoesNormais(matriz_g=g_regiao, matriz_h=h_regiao)
        return EquacoesDaUF(equacoes=equacoes_regiao, n_efetivo=n_efetivo, peso_regiao=1.0)

    g_estado = estatisticas_uf.g_bruta[posicao_uf] / soma_pesos_uf
    h_estado = estatisticas_uf.h_bruta[posicao_uf] / soma_pesos_uf

    razao_regiao_estado = kappa / n_efetivo
    normalizador = 1.0 + razao_regiao_estado
    g_combinada = (g_estado + razao_regiao_estado * g_regiao) / normalizador
    h_combinada = (h_estado + razao_regiao_estado * h_regiao) / normalizador

    peso_regiao = kappa / (n_efetivo + kappa)
    equacoes = regional.EquacoesNormais(matriz_g=g_combinada, matriz_h=h_combinada)
    return EquacoesDaUF(equacoes=equacoes, n_efetivo=n_efetivo, peso_regiao=peso_regiao)


def ajustar_beta_da_uf(
    base: BaseUF,
    estatisticas_uf: EstatisticasPorUF,
    estatisticas_demais: EstatisticasPorUF,
    posicao_uf: int,
    kappa: float,
    beta_inicial: np.ndarray | None,
) -> AjusteUF:
    """Resolve o QP restrito de um estado para um kappa.

    O ótimo é único (G definida positiva), então o ponto inicial só afeta a
    velocidade. Mesmo assim o SLSQP, partindo de um ponto "quente" (solução de
    outro kappa ou do ponto pontual), pode parar com lacuna de dualidade um pouco
    acima do limite de certificação (1e-7). Nesse caso o ajuste é repetido uma vez
    a partir do ponto uniforme, SEM relaxar nenhum critério: a solução aceita
    continua exigindo sucesso do solver, viabilidade e lacuna <= 1e-7. Se as duas
    tentativas falharem, a exceção é levantada.

    Args:
        base: Base por UF (só para rotular erros).
        estatisticas_uf: Somas brutas do estado.
        estatisticas_demais: Somas brutas de `g \\ u`.
        posicao_uf: Índice do estado.
        kappa: Peso da região (pode ser infinito).
        beta_inicial: Ponto de partida viável (8, 4) ou None (uniforme).

    Returns:
        O ajuste do estado (com o número de tentativas usado).

    Raises:
        regional.ErroConvergenciaAjuste: Se o solver falhar em todas as tentativas
            (rotulado com UF e kappa).
    """
    montagem = montar_equacoes_da_uf(estatisticas_uf, estatisticas_demais, posicao_uf, kappa)

    pontos_iniciais: list[np.ndarray | None] = []
    if beta_inicial is not None:
        pontos_iniciais.append(beta_inicial)
    pontos_iniciais.append(None)

    ultimo_erro: regional.ErroConvergenciaAjuste | None = None
    for numero_tentativa, ponto_inicial in enumerate(pontos_iniciais, start=1):
        try:
            resultado_solver = regional.ajustar_beta_restrito(montagem.equacoes, ponto_inicial)
        except regional.ErroConvergenciaAjuste as erro_solver:
            ultimo_erro = erro_solver
            continue

        return AjusteUF(
            beta=resultado_solver.beta,
            n_efetivo=montagem.n_efetivo,
            peso_regiao=montagem.peso_regiao,
            resultado_solver=resultado_solver,
            numero_tentativas=numero_tentativa,
        )

    sigla = base.lista_ufs[posicao_uf]
    raise regional.ErroConvergenciaAjuste(
        f"UF {sigla}, kappa={kappa}, após {len(pontos_iniciais)} tentativa(s): {ultimo_erro}"
    ) from ultimo_erro


def ajustar_todas_as_ufs(
    base: BaseUF,
    estatisticas_uf: EstatisticasPorUF,
    estatisticas_demais: EstatisticasPorUF,
    kappa: float,
    betas_iniciais: np.ndarray | None,
) -> list[AjusteUF]:
    """Ajusta os 27 estados para um kappa.

    Args:
        base: Base por UF.
        estatisticas_uf: Somas brutas por estado.
        estatisticas_demais: Somas brutas de `g \\ u` por estado.
        kappa: Peso da região.
        betas_iniciais: (U, 8, 4) ou None.

    Returns:
        Lista de ajustes na ordem de `base.lista_ufs`.
    """
    ajustes: list[AjusteUF] = []

    for posicao_uf in range(len(base.lista_ufs)):
        beta_inicial = None
        if betas_iniciais is not None:
            beta_inicial = betas_iniciais[posicao_uf]

        ajuste = ajustar_beta_da_uf(
            base,
            estatisticas_uf,
            estatisticas_demais,
            posicao_uf,
            kappa,
            beta_inicial,
        )
        ajustes.append(ajuste)

    return ajustes


def empilhar_betas(ajustes: list[AjusteUF]) -> np.ndarray:
    """Empilha os betas dos estados em um array (U, 8, 4)."""
    numero_ufs = len(ajustes)
    betas = np.zeros((numero_ufs, regional.NUMERO_ORIGENS, regional.NUMERO_DESTINOS))

    for posicao_uf, ajuste in enumerate(ajustes):
        betas[posicao_uf] = ajuste.beta

    return betas


def calcular_votos_por_uf(betas: np.ndarray, populacao_por_uf: np.ndarray) -> np.ndarray:
    """Fluxos em votos: votos[u, r, c] = beta[u, r, c] * N_u[r].

    N_u[r] é a contagem observada do grupo no estado (não é estimada).

    Args:
        betas: (U, 8, 4) ou (B, U, 8, 4).
        populacao_por_uf: N_u[r], (U, 8).

    Returns:
        Mesmo shape de `betas`.
    """
    return betas * populacao_por_uf[:, :, np.newaxis]


# ---------------------------------------------------------------------------
# Validação cruzada
# ---------------------------------------------------------------------------


def calcular_erro_de_predicao(
    base: BaseUF,
    posicoes_municipios: np.ndarray,
    beta: np.ndarray,
) -> float:
    """Erro ponderado sum_i w_i ||Y_i - X_i beta||^2 nos municípios indicados.

    Args:
        base: Base por UF.
        posicoes_municipios: Linhas dos municípios avaliados.
        beta: beta (8, 4) do estado.

    Returns:
        O erro (0 se não houver municípios).
    """
    if posicoes_municipios.shape[0] == 0:
        return 0.0

    origem = base.dados.matriz_origem[posicoes_municipios]
    destino_real = base.dados.matriz_destino[posicoes_municipios]
    pesos = base.dados.aptos_1t[posicoes_municipios]

    destino_previsto = origem @ beta
    residuos = destino_real - destino_previsto
    erros_por_municipio = (residuos**2).sum(axis=1)
    return float((pesos * erros_por_municipio).sum())


def listar_posicoes_por_uf(base: BaseUF) -> list[np.ndarray]:
    """Linhas dos municípios de cada estado, na ordem de `lista_ufs`."""
    posicoes_por_uf: list[np.ndarray] = []

    for posicao_uf in range(len(base.lista_ufs)):
        posicoes = np.flatnonzero(base.posicao_uf_do_municipio == posicao_uf)
        posicoes_por_uf.append(posicoes)

    return posicoes_por_uf


def calcular_erro_de_referencia_da_regiao(
    base: BaseUF,
    estatisticas_demais_cheia: EstatisticasPorUF,
    estatisticas_uf_cheia: EstatisticasPorUF,
) -> tuple[np.ndarray, int]:
    """Erro de validação com kappa = infinito (padrão da região) e retentativas do solver.

    Com kappa infinito o beta do estado só depende de `g \\ u` (que não tem relação
    com as dobras), então o ajuste é único e todos os municípios do estado são
    "fora da amostra" do próprio estado.

    Returns:
        (erro por estado (U,), número de ajustes que precisaram do ponto inicial de reserva).
    """
    posicoes_por_uf = listar_posicoes_por_uf(base)
    numero_ufs = len(base.lista_ufs)
    erro_por_uf = np.zeros(numero_ufs)

    ajustes = ajustar_todas_as_ufs(
        base,
        estatisticas_uf_cheia,
        estatisticas_demais_cheia,
        KAPPA_REGIAO,
        None,
    )
    betas = empilhar_betas(ajustes)

    retentativas = 0
    for posicao_uf in range(numero_ufs):
        retentativas += ajustes[posicao_uf].numero_tentativas - 1
        erro_por_uf[posicao_uf] = calcular_erro_de_predicao(
            base,
            posicoes_por_uf[posicao_uf],
            betas[posicao_uf],
        )

    return erro_por_uf, retentativas


def executar_validacao_cruzada(
    base: BaseUF,
    kappas: tuple[float, ...],
    numero_dobras: int,
) -> ResultadoValidacaoCruzada:
    """Validação cruzada de 5 dobras para escolher um kappa único.

    Para cada kappa e dobra k, em cada estado: ajusta beta_u com os municípios do
    estado FORA da dobra k (n_u recalculado no treino), com o termo da região
    usando todos os municípios de `g \\ u`; prevê os municípios do estado na
    dobra k. Estado sem treino na dobra (DF) usa só o termo da região.

    Args:
        base: Base por UF.
        kappas: Grade de kappa (finitos).
        numero_dobras: Número de dobras.

    Returns:
        A curva de erro, o kappa ótimo (empate: menor kappa) e referências.
    """
    numero_ufs = len(base.lista_ufs)
    numero_municipios = base.dados.aptos_1t.shape[0]
    numero_kappas = len(kappas)

    multiplicidade_cheia = np.ones(numero_municipios)
    estatisticas_cheia = calcular_estatisticas_por_uf(base, multiplicidade_cheia)
    estatisticas_demais_cheia = somar_demais_ufs_da_regiao(base, estatisticas_cheia)

    posicoes_por_uf = listar_posicoes_por_uf(base)
    erro_por_kappa_e_uf = np.zeros((numero_kappas, numero_ufs))
    numero_ajustes = 0
    numero_retentativas = 0

    for dobra in range(numero_dobras):
        mascara_validacao = base.dobra_do_municipio == dobra
        multiplicidade_treino = (~mascara_validacao).astype(np.float64)
        estatisticas_treino = calcular_estatisticas_por_uf(base, multiplicidade_treino)

        posicoes_validacao_por_uf: list[np.ndarray] = []
        for posicao_uf in range(numero_ufs):
            posicoes_da_uf = posicoes_por_uf[posicao_uf]
            mascara_na_dobra = mascara_validacao[posicoes_da_uf]
            posicoes_validacao_por_uf.append(posicoes_da_uf[mascara_na_dobra])

        betas_do_kappa_anterior: dict[int, np.ndarray] = {}
        for posicao_kappa, kappa in enumerate(kappas):
            for posicao_uf in range(numero_ufs):
                posicoes_validacao = posicoes_validacao_por_uf[posicao_uf]
                if posicoes_validacao.shape[0] == 0:
                    continue

                beta_inicial = betas_do_kappa_anterior.get(posicao_uf)
                ajuste = ajustar_beta_da_uf(
                    base,
                    estatisticas_treino,
                    estatisticas_demais_cheia,
                    posicao_uf,
                    kappa,
                    beta_inicial,
                )
                numero_ajustes += 1
                numero_retentativas += ajuste.numero_tentativas - 1
                betas_do_kappa_anterior[posicao_uf] = ajuste.beta

                erro = calcular_erro_de_predicao(base, posicoes_validacao, ajuste.beta)
                erro_por_kappa_e_uf[posicao_kappa, posicao_uf] += erro

        LOGGER.info(
            "Validação cruzada: dobra %d/%d concluída (%d ajustes acumulados).",
            dobra + 1,
            numero_dobras,
            numero_ajustes,
        )

    erro_regiao_por_uf, retentativas_regiao = calcular_erro_de_referencia_da_regiao(
        base,
        estatisticas_demais_cheia,
        estatisticas_cheia,
    )
    numero_ajustes += numero_ufs
    numero_retentativas += retentativas_regiao

    erro_por_kappa = erro_por_kappa_e_uf.sum(axis=1)
    posicao_otima = int(np.argmin(erro_por_kappa))

    return ResultadoValidacaoCruzada(
        kappas=np.array(kappas, dtype=np.float64),
        erro_por_kappa=erro_por_kappa,
        erro_por_kappa_e_uf=erro_por_kappa_e_uf,
        erro_regiao=float(erro_regiao_por_uf.sum()),
        erro_regiao_por_uf=erro_regiao_por_uf,
        posicao_kappa_otimo=posicao_otima,
        soma_pesos_total=float(base.dados.aptos_1t.sum()),
        numero_ajustes=numero_ajustes,
        numero_retentativas=numero_retentativas,
    )


# ---------------------------------------------------------------------------
# Versões da especificação (pontual)
# ---------------------------------------------------------------------------


def estimar_versao(
    base: BaseUF,
    codigo: str,
    kappa: float,
    betas_iniciais: np.ndarray | None,
) -> EstimativaVersao:
    """Estimativa pontual (amostra original) de uma versão para um kappa.

    Args:
        base: Base por UF.
        codigo: Rótulo da versão (`UF`, `UF_SOZINHO` ou `UF_REGIAO`).
        kappa: Peso da região (`KAPPA_REGIAO` para UF_REGIAO).
        betas_iniciais: Pontos de partida (U, 8, 4) ou None.

    Returns:
        Betas, votos, n efetivo e peso da região dos 27 estados.
    """
    multiplicidade_cheia = np.ones(base.dados.aptos_1t.shape[0])
    estatisticas = calcular_estatisticas_por_uf(base, multiplicidade_cheia)
    estatisticas_demais = somar_demais_ufs_da_regiao(base, estatisticas)
    ajustes = ajustar_todas_as_ufs(base, estatisticas, estatisticas_demais, kappa, betas_iniciais)

    betas = empilhar_betas(ajustes)
    votos = calcular_votos_por_uf(betas, base.populacao_por_uf)

    numero_ufs = len(ajustes)
    n_efetivo = np.zeros(numero_ufs)
    peso_regiao = np.zeros(numero_ufs)
    for posicao_uf, ajuste in enumerate(ajustes):
        n_efetivo[posicao_uf] = ajuste.n_efetivo
        peso_regiao[posicao_uf] = ajuste.peso_regiao

    return EstimativaVersao(
        codigo=codigo,
        kappa=kappa,
        ajustes=ajustes,
        betas=betas,
        votos=votos,
        n_efetivo=n_efetivo,
        peso_regiao=peso_regiao,
    )


def medir_diferenca_por_ponto_inicial(
    base: BaseUF,
    estimativa: EstimativaVersao,
    outro_ponto_inicial: np.ndarray | None,
) -> float:
    """Maior |delta beta| ao reajustar a versão a partir de outro ponto inicial.

    Com G definida positiva o ótimo é único; a diferença mede só a tolerância
    numérica do solver (e denuncia ótimos mal determinados).

    Args:
        base: Base por UF.
        estimativa: Estimativa já calculada (de um ponto inicial qualquer).
        outro_ponto_inicial: Outro ponto de partida (U, 8, 4), ou None (uniforme).

    Returns:
        Maior diferença absoluta entre as duas soluções, sobre todos os estados e células.
    """
    reestimativa = estimar_versao(base, estimativa.codigo, estimativa.kappa, outro_ponto_inicial)
    diferencas = np.abs(reestimativa.betas - estimativa.betas)
    return float(diferencas.max())


# ---------------------------------------------------------------------------
# Bootstrap estratificado por estado
# ---------------------------------------------------------------------------


def gerar_multiplicidades_por_uf(
    base: BaseUF,
    numero_replicas: int,
    gerador: np.random.Generator,
) -> np.ndarray:
    """Sorteia quantas vezes cada município entra em cada réplica, estado a estado.

    Reamostrar n municípios com reposição dentro do estado equivale a sortear
    contagens Multinomial(n, 1/n, ..., 1/n). Os estados são sorteados na ordem de
    `base.lista_ufs` (alfabética), com um único gerador; assim a réplica é
    reproduzível e independe de paralelismo.

    Args:
        base: Base por UF.
        numero_replicas: B.
        gerador: Gerador pseudoaleatório já semeado.

    Returns:
        Matriz inteira (B, n) com as multiplicidades.
    """
    numero_municipios = base.dados.aptos_1t.shape[0]
    multiplicidades = np.zeros((numero_replicas, numero_municipios), dtype=np.int64)
    posicoes_por_uf = listar_posicoes_por_uf(base)

    for posicoes in posicoes_por_uf:
        tamanho_uf = posicoes.shape[0]
        probabilidades = np.full(tamanho_uf, 1.0 / tamanho_uf)
        contagens = gerador.multinomial(tamanho_uf, probabilidades, size=numero_replicas)
        multiplicidades[:, posicoes] = contagens

    return multiplicidades


def executar_bootstrap_uf(
    base: BaseUF,
    kappa: float,
    betas_iniciais: np.ndarray,
    multiplicidades: np.ndarray,
) -> ResultadoBootstrapUF:
    """Bootstrap da versão UF: reajusta os 27 estados em cada réplica (kappa fixo).

    Em cada réplica: estatísticas por estado com as multiplicidades sorteadas; termo
    da região formado pelos municípios reamostrados dos OUTROS estados da mesma
    réplica; n_u de Kish recalculado sobre os municípios reamostrados do estado
    (cada cópia conta como uma linha); kappa inalterado (kappa* não é reescolhido).

    Args:
        base: Base por UF.
        kappa: kappa* fixo.
        betas_iniciais: beta pontual da versão UF, (U, 8, 4); só ponto de partida
            (o ótimo é único).
        multiplicidades: (B, n) multiplicidades sorteadas por `gerar_multiplicidades_por_uf`.

    Returns:
        Todas as réplicas e estatísticas de diagnóstico do solver.

    Raises:
        regional.ErroConvergenciaAjuste: Se qualquer ajuste de qualquer réplica falhar
            (a mensagem traz o índice da réplica e a UF).
    """
    instante_inicial = time.perf_counter()
    numero_replicas = multiplicidades.shape[0]
    numero_ufs = len(base.lista_ufs)
    betas = np.zeros(
        (numero_replicas, numero_ufs, regional.NUMERO_ORIGENS, regional.NUMERO_DESTINOS)
    )
    maior_condicao = 0.0
    maior_condicao_escalada = 0.0
    total_iteracoes = 0
    maior_lacuna = 0.0
    numero_retentativas = 0

    for indice_replica in range(numero_replicas):
        multiplicidade = multiplicidades[indice_replica].astype(np.float64)
        estatisticas = calcular_estatisticas_por_uf(base, multiplicidade)
        estatisticas_demais = somar_demais_ufs_da_regiao(base, estatisticas)

        try:
            ajustes = ajustar_todas_as_ufs(
                base,
                estatisticas,
                estatisticas_demais,
                kappa,
                betas_iniciais,
            )
        except regional.ErroConvergenciaAjuste as erro_ajuste:
            raise regional.ErroConvergenciaAjuste(
                f"Réplica bootstrap {indice_replica}: {erro_ajuste}"
            ) from erro_ajuste

        betas[indice_replica] = empilhar_betas(ajustes)
        for ajuste in ajustes:
            resultado_solver = ajuste.resultado_solver
            maior_condicao = max(maior_condicao, resultado_solver.numero_condicao_g)
            maior_condicao_escalada = max(
                maior_condicao_escalada,
                resultado_solver.numero_condicao_g_escalada,
            )
            total_iteracoes += resultado_solver.numero_iteracoes
            maior_lacuna = max(maior_lacuna, resultado_solver.lacuna_dualidade)
            numero_retentativas += ajuste.numero_tentativas - 1

        replicas_concluidas = indice_replica + 1
        if replicas_concluidas % REPLICAS_ENTRE_LOGS == 0:
            LOGGER.info("Bootstrap: %d de %d réplicas concluídas.", replicas_concluidas, numero_replicas)

    return ResultadoBootstrapUF(
        betas=betas,
        maior_numero_condicao=maior_condicao,
        maior_numero_condicao_escalada=maior_condicao_escalada,
        total_iteracoes=total_iteracoes,
        maior_lacuna_dualidade=maior_lacuna,
        segundos=time.perf_counter() - instante_inicial,
        numero_retentativas=numero_retentativas,
    )


def prever_fracoes_destino_por_uf(base: BaseUF, betas: np.ndarray) -> np.ndarray:
    """Frações previstas do 2º turno: Yhat_i = X_i beta_(estado de i).

    Args:
        base: Base por UF.
        betas: (U, 8, 4).

    Returns:
        Matriz (n, 4) de frações previstas por destino.
    """
    numero_municipios = base.dados.matriz_origem.shape[0]
    fracoes_previstas = np.zeros((numero_municipios, regional.NUMERO_DESTINOS))
    posicoes_por_uf = listar_posicoes_por_uf(base)

    for posicao_uf, posicoes in enumerate(posicoes_por_uf):
        origem_da_uf = base.dados.matriz_origem[posicoes]
        fracoes_previstas[posicoes] = origem_da_uf @ betas[posicao_uf]

    return fracoes_previstas


# ---------------------------------------------------------------------------
# Coerência com o modelo regional (E1)
# ---------------------------------------------------------------------------


def agregar_votos_por_regiao(
    base: BaseUF,
    votos_por_uf: np.ndarray,
) -> dict[str, np.ndarray]:
    """Soma os fluxos dos estados por região e no Brasil.

    Args:
        base: Base por UF.
        votos_por_uf: Fluxos (U, 8, 4).

    Returns:
        Dicionário região (e `Brasil`) -> fluxos (8, 4).
    """
    fluxos: dict[str, np.ndarray] = {}

    for nome_regiao in regional.REGIOES:
        fluxo_da_regiao = np.zeros((regional.NUMERO_ORIGENS, regional.NUMERO_DESTINOS))
        for posicao_uf, regiao_da_uf in enumerate(base.regiao_da_uf):
            if regiao_da_uf == nome_regiao:
                fluxo_da_regiao = fluxo_da_regiao + votos_por_uf[posicao_uf]
        fluxos[nome_regiao] = fluxo_da_regiao

    fluxos[regional.ROTULO_BRASIL] = votos_por_uf.sum(axis=0)
    return fluxos


def carregar_betas_e1(caminho_csv: Path) -> dict[str, np.ndarray]:
    """Lê os betas da especificação E1 (regional) por região e para o Brasil.

    Args:
        caminho_csv: `transferencias.csv` da pasta regional.

    Returns:
        Dicionário região (e `Brasil`) -> beta (8, 4).

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ErroDadosUF: Se alguma célula do E1 faltar ou duplicar.
    """
    if not caminho_csv.is_file():
        raise FileNotFoundError(f"transferencias.csv do E1 não encontrado: {caminho_csv}")

    tabela = pd.read_csv(caminho_csv, sep=";", encoding="utf-8")
    tabela_e1 = tabela[tabela["especificacao"] == "E1"]

    rotulos = regional.REGIOES + (regional.ROTULO_BRASIL,)
    betas_e1: dict[str, np.ndarray] = {}
    for rotulo in rotulos:
        linhas_do_rotulo = tabela_e1[tabela_e1["regiao"] == rotulo]
        beta = np.zeros((regional.NUMERO_ORIGENS, regional.NUMERO_DESTINOS))

        for posicao_origem, origem in enumerate(regional.ORIGENS_1T):
            for posicao_destino, destino in enumerate(regional.DESTINOS_2T):
                mascara_origem = linhas_do_rotulo["origem_1t"] == origem
                mascara_destino = linhas_do_rotulo["destino_2t"] == destino
                celula = linhas_do_rotulo[mascara_origem & mascara_destino]
                if celula.shape[0] != 1:
                    raise ErroDadosUF(
                        f"E1 {rotulo} {origem}->{destino}: {celula.shape[0]} linhas (esperado 1)."
                    )
                beta[posicao_origem, posicao_destino] = float(celula["beta"].iloc[0])

        betas_e1[rotulo] = beta

    return betas_e1


def calcular_diferencas_para_e1(
    base: BaseUF,
    votos_por_uf: np.ndarray,
    betas_e1: dict[str, np.ndarray],
) -> pd.DataFrame:
    """Compara o beta agregado por região (soma dos fluxos dos estados) com o E1.

    Os modelos são diferentes, então não precisam coincidir; a diferença só mede
    a coerência entre o modelo por estado e o modelo regional.

    Args:
        base: Base por UF.
        votos_por_uf: Fluxos de uma versão, (U, 8, 4).
        betas_e1: Saída de `carregar_betas_e1`.

    Returns:
        Tabela longa: regiao, origem_1t, destino_2t, beta_uf_agregado, beta_e1, diferenca_abs.
    """
    fluxos_agregados = agregar_votos_por_regiao(base, votos_por_uf)

    linhas: list[dict[str, object]] = []
    for rotulo, fluxos in fluxos_agregados.items():
        beta_agregado = regional.converter_fluxos_em_beta(fluxos)
        beta_e1 = betas_e1[rotulo]

        for posicao_origem, origem in enumerate(regional.ORIGENS_1T):
            for posicao_destino, destino in enumerate(regional.DESTINOS_2T):
                valor_uf = float(beta_agregado[posicao_origem, posicao_destino])
                valor_e1 = float(beta_e1[posicao_origem, posicao_destino])
                linhas.append(
                    {
                        "regiao": rotulo,
                        "origem_1t": origem,
                        "destino_2t": destino,
                        "beta_uf_agregado": valor_uf,
                        "beta_e1": valor_e1,
                        "diferenca_abs": abs(valor_uf - valor_e1),
                    }
                )

    return pd.DataFrame(linhas)
