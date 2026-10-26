"""Funções puras do teste de recuperação sintética por estado (seção 7 da especificação).

Gera β verdadeiro por estado (β do teste T1 da especificação regional com uma
perturbação por estado nas linhas caiado, cury e renan), sorteia contagens
`Y_i ~ Multinomial(aptos_1t_i, X_i · β_verdadeiro_u)` com o X real e mede o erro
de recuperação de β.

A orquestração e a gravação do relatório ficam em `03_teste_sintetico.py`.
"""

import numpy as np

import nucleo_uf as nucleo

regional = nucleo.regional

# β verdadeiro da região = matriz do teste T1 da especificação regional (seção 9).
# Linhas: lula, flavio, cury, renan, caiado, demais, branco_nulo, abstencao.
# Colunas: lula, flavio, branco_nulo, abstencao.
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
ORIGENS_PERTURBADAS: tuple[str, ...] = ("caiado", "cury", "renan")
AMPLITUDE_DESLOCAMENTO = 0.15
POSICAO_DESTINO_LULA = regional.DESTINOS_2T.index("lula")
POSICAO_DESTINO_FLAVIO = regional.DESTINOS_2T.index("flavio")


def posicoes_das_origens_perturbadas() -> list[int]:
    """Índices (em ORIGENS_1T) das linhas perturbadas: caiado, cury e renan."""
    posicoes: list[int] = []

    for origem in ORIGENS_PERTURBADAS:
        posicoes.append(regional.ORIGENS_1T.index(origem))

    return posicoes


def sortear_deslocamentos_por_uf(
    numero_ufs: int,
    gerador: np.random.Generator,
    amplitude: float = AMPLITUDE_DESLOCAMENTO,
) -> np.ndarray:
    """Sorteia o deslocamento delta_u ~ Uniforme[-amplitude; +amplitude] de cada estado.

    Args:
        numero_ufs: Número de estados.
        gerador: Gerador já semeado (estes são os PRIMEIROS sorteios da semente).
        amplitude: Meia-largura do sorteio; 0,15 na especificação. O valor 0 só é usado
            no experimento de controle (mundo sem heterogeneidade entre estados).

    Returns:
        Vetor (U,) na ordem alfabética das UFs.
    """
    return gerador.uniform(-amplitude, amplitude, size=numero_ufs)


def perturbar_linha(linha_beta: np.ndarray, deslocamento: float) -> np.ndarray:
    """Desloca `delta` de flavio para lula (ou o inverso se negativo), mantendo o simplex.

    O deslocamento efetivo é recortado em [-beta_lula, +beta_flavio] para que
    nenhuma célula fique negativa; a soma da linha continua igual a 1.

    Args:
        linha_beta: Linha de β (4,) no simplex.
        deslocamento: delta sorteado (positivo = mais lula).

    Returns:
        Nova linha (4,) no simplex.
    """
    beta_lula = float(linha_beta[POSICAO_DESTINO_LULA])
    beta_flavio = float(linha_beta[POSICAO_DESTINO_FLAVIO])
    deslocamento_efetivo = min(max(deslocamento, -beta_lula), beta_flavio)

    nova_linha = linha_beta.copy()
    nova_linha[POSICAO_DESTINO_LULA] = beta_lula + deslocamento_efetivo
    nova_linha[POSICAO_DESTINO_FLAVIO] = beta_flavio - deslocamento_efetivo
    return nova_linha


def montar_betas_verdadeiros_por_uf(
    beta_regiao: np.ndarray,
    deslocamentos: np.ndarray,
) -> np.ndarray:
    """β verdadeiro de cada estado: β da região com delta_u nas linhas caiado, cury e renan.

    Args:
        beta_regiao: β da região (8, 4).
        deslocamentos: delta_u por estado, (U,).

    Returns:
        Array (U, 8, 4).
    """
    numero_ufs = deslocamentos.shape[0]
    betas = np.zeros((numero_ufs, regional.NUMERO_ORIGENS, regional.NUMERO_DESTINOS))
    posicoes_perturbadas = posicoes_das_origens_perturbadas()

    for posicao_uf in range(numero_ufs):
        beta_da_uf = beta_regiao.copy()
        for posicao_origem in posicoes_perturbadas:
            beta_da_uf[posicao_origem] = perturbar_linha(
                beta_regiao[posicao_origem],
                float(deslocamentos[posicao_uf]),
            )
        betas[posicao_uf] = beta_da_uf

    return betas


def sortear_destino_sintetico(
    base: nucleo.BaseUF,
    betas_verdadeiros_por_uf: np.ndarray,
    gerador: np.random.Generator,
) -> np.ndarray:
    """Sorteia Y_i ~ Multinomial(aptos_1t_i, X_i · beta_u) com o X real.

    Os estados são sorteados na ordem de `lista_ufs` (alfabética). Y é devolvido
    em fração dos aptos do 1º turno (cada linha soma 1).

    Args:
        base: Base real (fornece X e aptos_1t).
        betas_verdadeiros_por_uf: (U, 8, 4).
        gerador: Gerador já semeado (usado depois dos deslocamentos).

    Returns:
        Y sintético (n, 4).
    """
    numero_municipios = base.dados.matriz_origem.shape[0]
    destino_sintetico = np.zeros((numero_municipios, regional.NUMERO_DESTINOS))
    aptos_inteiros = base.dados.aptos_1t.astype(np.int64)
    posicoes_por_uf = nucleo.listar_posicoes_por_uf(base)

    for posicao_uf, posicoes in enumerate(posicoes_por_uf):
        origem_da_uf = base.dados.matriz_origem[posicoes]
        probabilidades = origem_da_uf @ betas_verdadeiros_por_uf[posicao_uf]
        probabilidades = np.clip(probabilidades, 0.0, None)
        probabilidades = probabilidades / probabilidades.sum(axis=1, keepdims=True)

        contagens = gerador.multinomial(aptos_inteiros[posicoes], probabilidades)
        destino_sintetico[posicoes] = contagens / base.dados.aptos_1t[posicoes, np.newaxis]

    return destino_sintetico


def calcular_erro_absoluto_ponderado(
    betas_estimados: np.ndarray,
    betas_verdadeiros: np.ndarray,
    populacao_por_uf: np.ndarray,
) -> float:
    """Erro médio absoluto de β nas linhas caiado, cury e renan, ponderado por N_u[r].

    Para cada (estado, origem perturbada) toma a média, sobre as 4 destinações, de
    |beta_estimado - beta_verdadeiro| e pondera por N_u[r] (contagem do grupo no estado).

    Args:
        betas_estimados: (U, 8, 4).
        betas_verdadeiros: (U, 8, 4).
        populacao_por_uf: N_u[r], (U, 8).

    Returns:
        O erro ponderado (escalar).
    """
    posicoes = posicoes_das_origens_perturbadas()

    diferencas = np.abs(betas_estimados - betas_verdadeiros)
    erro_por_uf_e_origem = diferencas[:, posicoes, :].mean(axis=2)
    pesos = populacao_por_uf[:, posicoes]

    return float((pesos * erro_por_uf_e_origem).sum() / pesos.sum())


def calcular_erro_por_origem(
    betas_estimados: np.ndarray,
    betas_verdadeiros: np.ndarray,
    populacao_por_uf: np.ndarray,
) -> dict[str, float]:
    """Mesmo erro de `calcular_erro_absoluto_ponderado`, separado por origem perturbada."""
    diferencas = np.abs(betas_estimados - betas_verdadeiros)
    erros: dict[str, float] = {}

    for origem in ORIGENS_PERTURBADAS:
        posicao = regional.ORIGENS_1T.index(origem)
        erro_por_uf = diferencas[:, posicao, :].mean(axis=1)
        pesos = populacao_por_uf[:, posicao]
        erros[origem] = float((pesos * erro_por_uf).sum() / pesos.sum())

    return erros


def calcular_erro_por_uf(
    betas_estimados: np.ndarray,
    betas_verdadeiros: np.ndarray,
    populacao_por_uf: np.ndarray,
) -> np.ndarray:
    """Erro médio absoluto de β nas 3 linhas perturbadas, por estado (ponderado por N_u[r])."""
    posicoes = posicoes_das_origens_perturbadas()

    diferencas = np.abs(betas_estimados - betas_verdadeiros)
    erro_por_uf_e_origem = diferencas[:, posicoes, :].mean(axis=2)
    pesos = populacao_por_uf[:, posicoes]

    return (pesos * erro_por_uf_e_origem).sum(axis=1) / pesos.sum(axis=1)
