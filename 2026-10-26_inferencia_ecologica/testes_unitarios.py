"""Testes unitários das funções puras da inferência ecológica.

Cobrem: montagem de X e Y, identidade 'linha soma 1', âncoras, equações
normais, objetivo e gradiente, solver restrito (recuperação sem ruído,
restrições, invariância ao ponto inicial, falha explícita), população de
grupos, agregação de fluxos, bootstrap estratificado, percentis, R², fronteira
e a tabela `transferencias`. No final, um teste de integração com a base real
(pulado se o parquet não existir).

Uso:
    python3 -I testes_unitarios.py
"""

import dataclasses
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

PASTA_TRABALHO = Path(__file__).resolve().parent
# `python3 -I` remove a pasta do script do sys.path; este insert é explícito
# e restrito à pasta onde estão os módulos deste projeto.
sys.path.insert(0, str(PASTA_TRABALHO))

import nucleo_inferencia as nucleo  # noqa: E402
import saidas_inferencia as saidas  # noqa: E402

CAMINHO_BASE_REAL = (
    PASTA_TRABALHO.parent / "dados" / "processados" / "presidente_municipio_turnos.parquet"
)
SEMENTE_TESTES = 12345
TOLERANCIA_RECUPERACAO_SEM_RUIDO = 1e-5
MUNICIPIOS_POR_REGIAO_TESTE = 80


# ---------------------------------------------------------------------------
# Construtores de dados de teste
# ---------------------------------------------------------------------------


def construir_linha_municipio(
    codigo: str,
    regiao: str,
    exterior: bool,
    abstencao_1t: int,
    nao_instaladas_1t: int,
) -> dict[str, object]:
    """Linha mínima da base: componentes do 1º turno e do 2º turno com aptos coerentes."""
    votos_1t = {
        "votos_1t_13": 50,
        "votos_1t_22": 40,
        "votos_1t_70": 5,
        "votos_1t_14": 3,
        "votos_1t_55": 2,
        "votos_1t_30": 1,
        "votos_1t_80": 0,
        "votos_1t_16": 1,
        "votos_1t_27": 0,
        "votos_1t_21": 1,
        "votos_1t_35": 0,
        "votos_1t_29": 1,
    }
    brancos_1t = 2
    nulos_1t = 3
    aptos_1t = (
        sum(votos_1t.values()) + brancos_1t + nulos_1t + abstencao_1t + nao_instaladas_1t
    )

    votos_2t_lula = 60
    votos_2t_flavio = 45
    brancos_2t = 3
    nulos_2t = 2
    abstencao_2t = 8
    nao_instaladas_2t = 1
    aptos_2t = (
        votos_2t_lula + votos_2t_flavio + brancos_2t + nulos_2t + abstencao_2t + nao_instaladas_2t
    )

    linha: dict[str, object] = {
        "cd_municipio_tse": codigo,
        "nm_regiao": regiao,
        "fl_exterior": exterior,
        "aptos_1t": aptos_1t,
        "abstencao_1t": abstencao_1t,
        "nao_instaladas_1t": nao_instaladas_1t,
        "brancos_1t": brancos_1t,
        "nulos_1t": nulos_1t,
        "aptos_2t": aptos_2t,
        "abstencao_2t": abstencao_2t,
        "nao_instaladas_2t": nao_instaladas_2t,
        "brancos_2t": brancos_2t,
        "nulos_2t": nulos_2t,
        "votos_2t_13": votos_2t_lula,
        "votos_2t_22": votos_2t_flavio,
    }
    linha.update(votos_1t)
    return linha


def construir_base_minima() -> pd.DataFrame:
    """Três municípios brasileiros e um do exterior."""
    linhas = [
        construir_linha_municipio("00001", "Sul", False, 10, 0),
        construir_linha_municipio("00002", "Sul", False, 12, 3),
        construir_linha_municipio("00003", "Norte", False, 7, 0),
        construir_linha_municipio("00004", "Exterior", True, 20, 0),
    ]
    return pd.DataFrame(linhas)


def construir_dados_sinteticos_pequenos(
    gerador: np.random.Generator,
    beta_por_regiao: np.ndarray,
    com_ruido_multinomial: bool,
) -> nucleo.DadosEcologicos:
    """Dados sintéticos pequenos (5 regiões) onde o beta verdadeiro é conhecido.

    Args:
        gerador: Gerador pseudoaleatório.
        beta_por_regiao: beta verdadeiro, (5, 8, 4).
        com_ruido_multinomial: Se False, Y = X beta exatamente (sem ruído);
            se True, Y = contagem Multinomial(aptos, X beta) / aptos.

    Returns:
        DadosEcologicos coerentes (X vem de contagens inteiras).
    """
    regioes: list[str] = []
    for nome_regiao in nucleo.REGIOES:
        for _ in range(MUNICIPIOS_POR_REGIAO_TESTE):
            regioes.append(nome_regiao)
    regiao = np.array(regioes)
    numero_municipios = regiao.shape[0]

    aptos = gerador.integers(2000, 60000, size=numero_municipios)
    concentracao = np.array([6.0, 6.0, 1.0, 1.0, 1.0, 0.5, 2.0, 4.0])
    proporcoes = gerador.dirichlet(concentracao, size=numero_municipios)

    contagens_origem = np.zeros((numero_municipios, nucleo.NUMERO_ORIGENS), dtype=np.int64)
    for posicao_municipio in range(numero_municipios):
        contagens_origem[posicao_municipio] = gerador.multinomial(
            aptos[posicao_municipio],
            proporcoes[posicao_municipio],
        )
    matriz_origem = contagens_origem / aptos[:, np.newaxis]

    matriz_destino = np.zeros((numero_municipios, nucleo.NUMERO_DESTINOS))
    contagens_destino = np.zeros((numero_municipios, nucleo.NUMERO_DESTINOS), dtype=np.int64)
    for posicao_regiao, nome_regiao in enumerate(nucleo.REGIOES):
        posicoes = np.flatnonzero(regiao == nome_regiao)
        probabilidades = matriz_origem[posicoes] @ beta_por_regiao[posicao_regiao]
        if com_ruido_multinomial:
            sorteio = gerador.multinomial(aptos[posicoes], probabilidades)
            contagens_destino[posicoes] = sorteio
            matriz_destino[posicoes] = sorteio / aptos[posicoes, np.newaxis]
        else:
            matriz_destino[posicoes] = probabilidades
            contagens_destino[posicoes] = np.round(probabilidades * aptos[posicoes, np.newaxis])

    return nucleo.DadosEcologicos(
        codigo_municipio=np.array([f"{i:05d}" for i in range(numero_municipios)]),
        regiao=regiao,
        aptos_1t=aptos.astype(np.float64),
        aptos_2t=aptos.astype(np.float64),
        contagens_origem=contagens_origem,
        contagens_destino=contagens_destino,
        matriz_origem=matriz_origem,
        matriz_destino=matriz_destino,
    )


def sortear_beta_verdadeiro(gerador: np.random.Generator) -> np.ndarray:
    """beta (8, 4) com linhas Dirichlet (soma 1, estritamente dentro de [0, 1])."""
    return gerador.dirichlet(np.ones(nucleo.NUMERO_DESTINOS) * 2.0, size=nucleo.NUMERO_ORIGENS)


def construir_equacoes_de_dados(
    dados: nucleo.DadosEcologicos,
    pesos: np.ndarray,
) -> nucleo.EquacoesNormais:
    """Atalho: equações normais de todos os municípios de `dados`."""
    return nucleo.calcular_equacoes_normais(dados.matriz_origem, dados.matriz_destino, pesos)


# ---------------------------------------------------------------------------
# Montagem de X e Y
# ---------------------------------------------------------------------------


class TesteMontagemDeDados(unittest.TestCase):
    """Montagem das contagens, de X e de Y a partir da base."""

    def test_exterior_e_removido_e_indice_reiniciado(self) -> None:
        base = construir_base_minima()
        municipios = nucleo.selecionar_municipios_brasileiros(base)
        self.assertEqual(len(municipios), 3)
        self.assertNotIn("Exterior", set(municipios["nm_regiao"]))
        self.assertEqual(list(municipios.index), [0, 1, 2])

    def test_exterior_nulo_e_erro(self) -> None:
        base = construir_base_minima()
        base["fl_exterior"] = base["fl_exterior"].astype("object")
        base.loc[0, "fl_exterior"] = None
        with self.assertRaises(nucleo.ErroDadosInvalidos):
            nucleo.selecionar_municipios_brasileiros(base)

    def test_coluna_ausente_levanta_key_error(self) -> None:
        base = construir_base_minima().drop(columns=["votos_1t_55"])
        with self.assertRaises(KeyError):
            nucleo.selecionar_municipios_brasileiros(base)

    def test_contagens_de_origem_seguem_a_composicao_da_especificacao(self) -> None:
        municipios = nucleo.selecionar_municipios_brasileiros(construir_base_minima())
        contagens = nucleo.construir_contagens_origem(municipios)
        # Primeiro município: abstencao_1t=10, nao_instaladas_1t=0.
        esperado_primeiro = [50, 40, 5, 3, 2, 1 + 0 + 1 + 0 + 1 + 0 + 1, 2 + 3, 10 + 0]
        self.assertEqual(contagens[0].tolist(), esperado_primeiro)
        # Segundo município: não instaladas entram na abstenção.
        self.assertEqual(contagens[1, nucleo.ORIGENS_1T.index("abstencao")], 12 + 3)

    def test_contagens_de_destino_somam_brancos_nulos_e_nao_instaladas(self) -> None:
        municipios = nucleo.selecionar_municipios_brasileiros(construir_base_minima())
        contagens = nucleo.construir_contagens_destino(municipios)
        self.assertEqual(contagens[0].tolist(), [60, 45, 3 + 2, 8 + 1])

    def test_x_e_y_dividem_pelo_aptos_do_proprio_turno_e_somam_um(self) -> None:
        municipios = nucleo.selecionar_municipios_brasileiros(construir_base_minima())
        dados = nucleo.montar_dados_ecologicos(municipios)

        aptos_primeiro = municipios.loc[0, "aptos_1t"]
        self.assertAlmostEqual(dados.matriz_origem[0, 0], 50 / aptos_primeiro, places=15)
        aptos_segundo = municipios.loc[0, "aptos_2t"]
        self.assertAlmostEqual(dados.matriz_destino[0, 1], 45 / aptos_segundo, places=15)

        np.testing.assert_allclose(dados.matriz_origem.sum(axis=1), 1.0, rtol=0, atol=1e-12)
        np.testing.assert_allclose(dados.matriz_destino.sum(axis=1), 1.0, rtol=0, atol=1e-12)
        self.assertEqual(dados.matriz_origem.shape, (3, 8))
        self.assertEqual(dados.matriz_destino.shape, (3, 4))

    def test_identidade_violada_no_primeiro_turno_e_erro(self) -> None:
        municipios = nucleo.selecionar_municipios_brasileiros(construir_base_minima())
        municipios.loc[1, "aptos_1t"] = municipios.loc[1, "aptos_1t"] + 1
        with self.assertRaises(nucleo.ErroDadosInvalidos):
            nucleo.montar_dados_ecologicos(municipios)

    def test_identidade_violada_no_segundo_turno_e_erro(self) -> None:
        municipios = nucleo.selecionar_municipios_brasileiros(construir_base_minima())
        municipios.loc[2, "aptos_2t"] = municipios.loc[2, "aptos_2t"] - 1
        with self.assertRaises(nucleo.ErroDadosInvalidos):
            nucleo.montar_dados_ecologicos(municipios)

    def test_aptos_zero_e_erro(self) -> None:
        municipios = nucleo.selecionar_municipios_brasileiros(construir_base_minima())
        municipios.loc[0, "aptos_1t"] = 0
        with self.assertRaises(nucleo.ErroDadosInvalidos):
            nucleo.montar_dados_ecologicos(municipios)


class TesteAncoras(unittest.TestCase):
    """Validação das âncoras numéricas."""

    def test_ancora_aprovada_exige_igualdade_exata(self) -> None:
        self.assertTrue(nucleo.ResultadoAncora("x", 10, 10).aprovada)
        self.assertFalse(nucleo.ResultadoAncora("x", 10, 11).aprovada)

    def test_base_minima_diverge_das_ancoras_e_interrompe(self) -> None:
        municipios = nucleo.selecionar_municipios_brasileiros(construir_base_minima())
        dados = nucleo.montar_dados_ecologicos(municipios)
        resultados = nucleo.validar_ancoras(dados)
        self.assertTrue(any(not resultado.aprovada for resultado in resultados))
        with self.assertRaises(nucleo.ErroAncora):
            nucleo.exigir_ancoras_aprovadas(resultados)

    def test_lista_toda_aprovada_nao_levanta(self) -> None:
        resultados = [nucleo.ResultadoAncora("a", 1, 1), nucleo.ResultadoAncora("b", 2, 2)]
        nucleo.exigir_ancoras_aprovadas(resultados)

    def test_numero_de_ancoras_e_vinte(self) -> None:
        municipios = nucleo.selecionar_municipios_brasileiros(construir_base_minima())
        dados = nucleo.montar_dados_ecologicos(municipios)
        self.assertEqual(len(nucleo.validar_ancoras(dados)), 20)


# ---------------------------------------------------------------------------
# Equações normais, objetivo e gradiente
# ---------------------------------------------------------------------------


class TesteEquacoesNormaisEObjetivo(unittest.TestCase):
    """G, H, objetivo e gradiente."""

    def setUp(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES)
        self.beta_verdadeiro = np.tile(sortear_beta_verdadeiro(gerador), (5, 1, 1))
        self.dados = construir_dados_sinteticos_pequenos(gerador, self.beta_verdadeiro, True)
        self.pesos = self.dados.aptos_1t

    def test_g_e_h_conferem_com_soma_explicita_por_municipio(self) -> None:
        equacoes = construir_equacoes_de_dados(self.dados, self.pesos)

        matriz_g_manual = np.zeros((8, 8))
        matriz_h_manual = np.zeros((8, 4))
        for posicao_municipio in range(self.dados.regiao.shape[0]):
            linha_x = self.dados.matriz_origem[posicao_municipio]
            linha_y = self.dados.matriz_destino[posicao_municipio]
            peso = self.pesos[posicao_municipio]
            matriz_g_manual += peso * np.outer(linha_x, linha_x)
            matriz_h_manual += peso * np.outer(linha_x, linha_y)
        peso_total = self.pesos.sum()

        np.testing.assert_allclose(equacoes.matriz_g, matriz_g_manual / peso_total, rtol=1e-12)
        np.testing.assert_allclose(equacoes.matriz_h, matriz_h_manual / peso_total, rtol=1e-12)

    def test_g_e_simetrica(self) -> None:
        equacoes = construir_equacoes_de_dados(self.dados, self.pesos)
        np.testing.assert_allclose(equacoes.matriz_g, equacoes.matriz_g.T, rtol=0, atol=1e-15)

    def test_dimensoes_incompativeis_sao_erro(self) -> None:
        with self.assertRaises(nucleo.ErroDadosInvalidos):
            nucleo.calcular_equacoes_normais(
                self.dados.matriz_origem,
                self.dados.matriz_destino[:-1],
                self.pesos,
            )

    def test_peso_total_zero_e_erro(self) -> None:
        with self.assertRaises(nucleo.ErroDadosInvalidos):
            nucleo.calcular_equacoes_normais(
                self.dados.matriz_origem,
                self.dados.matriz_destino,
                np.zeros_like(self.pesos),
            )

    def test_objetivo_igual_a_soma_ponderada_dos_quadrados_menos_a_constante(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES + 1)
        beta_qualquer = sortear_beta_verdadeiro(gerador)
        equacoes = construir_equacoes_de_dados(self.dados, self.pesos)

        residuos = self.dados.matriz_destino - self.dados.matriz_origem @ beta_qualquer
        soma_quadrados = (self.pesos[:, np.newaxis] * residuos**2).sum() / self.pesos.sum()
        constante = (self.pesos[:, np.newaxis] * self.dados.matriz_destino**2).sum() / self.pesos.sum()

        valor_objetivo = nucleo.calcular_valor_objetivo(
            beta_qualquer.reshape(32),
            equacoes.matriz_g,
            equacoes.matriz_h,
        )
        self.assertAlmostEqual(valor_objetivo + constante, soma_quadrados, places=12)

    def test_gradiente_analitico_confere_com_diferencas_finitas(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES + 2)
        ponto = gerador.uniform(0.0, 1.0, size=32)
        equacoes = construir_equacoes_de_dados(self.dados, self.pesos)

        gradiente_analitico = nucleo.calcular_gradiente_objetivo(
            ponto,
            equacoes.matriz_g,
            equacoes.matriz_h,
        )

        passo = 1e-6
        gradiente_numerico = np.zeros(32)
        for posicao in range(32):
            ponto_acima = ponto.copy()
            ponto_abaixo = ponto.copy()
            ponto_acima[posicao] += passo
            ponto_abaixo[posicao] -= passo
            valor_acima = nucleo.calcular_valor_objetivo(
                ponto_acima, equacoes.matriz_g, equacoes.matriz_h
            )
            valor_abaixo = nucleo.calcular_valor_objetivo(
                ponto_abaixo, equacoes.matriz_g, equacoes.matriz_h
            )
            gradiente_numerico[posicao] = (valor_acima - valor_abaixo) / (2.0 * passo)

        np.testing.assert_allclose(gradiente_analitico, gradiente_numerico, rtol=1e-6, atol=1e-8)

    def test_matriz_de_restricao_soma_as_linhas(self) -> None:
        beta = np.arange(32, dtype=float).reshape(8, 4)
        somas = nucleo.MATRIZ_RESTRICAO_SOMA_LINHAS @ beta.reshape(32)
        np.testing.assert_array_equal(somas, beta.sum(axis=1))


# ---------------------------------------------------------------------------
# Solver restrito
# ---------------------------------------------------------------------------


class TesteSolverRestrito(unittest.TestCase):
    """Comportamento de `ajustar_beta_restrito`."""

    def setUp(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES)
        self.beta_verdadeiro = sortear_beta_verdadeiro(gerador)
        beta_por_regiao = np.tile(self.beta_verdadeiro, (5, 1, 1))
        self.dados_sem_ruido = construir_dados_sinteticos_pequenos(gerador, beta_por_regiao, False)
        self.dados_com_ruido = construir_dados_sinteticos_pequenos(gerador, beta_por_regiao, True)

    def test_sem_ruido_recupera_o_beta_verdadeiro(self) -> None:
        equacoes = construir_equacoes_de_dados(self.dados_sem_ruido, self.dados_sem_ruido.aptos_1t)
        ajuste = nucleo.ajustar_beta_restrito(equacoes)
        erro_maximo = np.abs(ajuste.beta - self.beta_verdadeiro).max()
        self.assertLess(erro_maximo, TOLERANCIA_RECUPERACAO_SEM_RUIDO)

    def test_restricoes_valem_com_ruido_e_beta_verdadeiro_na_fronteira(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES + 3)
        beta_com_zeros = sortear_beta_verdadeiro(gerador)
        beta_com_zeros[2] = [0.0, 0.7, 0.3, 0.0]
        beta_com_zeros[5] = [1.0, 0.0, 0.0, 0.0]
        beta_por_regiao = np.tile(beta_com_zeros, (5, 1, 1))
        dados = construir_dados_sinteticos_pequenos(gerador, beta_por_regiao, True)

        equacoes = construir_equacoes_de_dados(dados, dados.aptos_1t)
        ajuste = nucleo.ajustar_beta_restrito(equacoes)

        np.testing.assert_allclose(ajuste.beta.sum(axis=1), 1.0, rtol=0, atol=1e-9)
        self.assertGreaterEqual(ajuste.beta.min(), 0.0)
        self.assertLessEqual(ajuste.beta.max(), 1.0)
        self.assertLessEqual(ajuste.lacuna_dualidade, nucleo.TOLERANCIA_LACUNA_DUALIDADE)

    def test_solucao_e_otima_frente_a_candidatos_viaveis_aleatorios(self) -> None:
        equacoes = construir_equacoes_de_dados(self.dados_com_ruido, self.dados_com_ruido.aptos_1t)
        ajuste = nucleo.ajustar_beta_restrito(equacoes)
        objetivo_da_solucao = nucleo.calcular_valor_objetivo(
            ajuste.beta.reshape(32),
            equacoes.matriz_g,
            equacoes.matriz_h,
        )

        gerador = np.random.default_rng(SEMENTE_TESTES + 4)
        menor_folga = np.inf
        for _ in range(300):
            candidato_aleatorio = gerador.dirichlet(np.ones(4) * 0.5, size=8)
            mistura = gerador.uniform(0.0, 0.2)
            candidato = (1.0 - mistura) * ajuste.beta + mistura * candidato_aleatorio
            objetivo_candidato = nucleo.calcular_valor_objetivo(
                candidato.reshape(32),
                equacoes.matriz_g,
                equacoes.matriz_h,
            )
            menor_folga = min(menor_folga, objetivo_candidato - objetivo_da_solucao)

        self.assertGreaterEqual(menor_folga, -1e-12)

    def test_resultado_nao_depende_do_ponto_inicial(self) -> None:
        equacoes = construir_equacoes_de_dados(self.dados_com_ruido, self.dados_com_ruido.aptos_1t)
        gerador = np.random.default_rng(SEMENTE_TESTES + 5)
        pontos_iniciais = [
            None,
            np.tile([1.0, 0.0, 0.0, 0.0], (8, 1)),
            gerador.dirichlet(np.ones(4), size=8),
            gerador.dirichlet(np.ones(4), size=8),
        ]
        solucoes = []
        for ponto_inicial in pontos_iniciais:
            solucoes.append(nucleo.ajustar_beta_restrito(equacoes, ponto_inicial).beta)

        maior_diferenca = 0.0
        for solucao in solucoes[1:]:
            maior_diferenca = max(maior_diferenca, float(np.abs(solucao - solucoes[0]).max()))
        self.assertLess(maior_diferenca, 1e-4)

    def test_falha_de_convergencia_e_erro_explicito(self) -> None:
        equacoes = construir_equacoes_de_dados(self.dados_com_ruido, self.dados_com_ruido.aptos_1t)
        with mock.patch.object(nucleo, "MAXIMO_ITERACOES_SLSQP", 2):
            with self.assertRaises(nucleo.ErroConvergenciaAjuste):
                nucleo.ajustar_beta_restrito(equacoes)

    def test_lacuna_de_dualidade_acima_da_tolerancia_e_erro(self) -> None:
        equacoes = construir_equacoes_de_dados(self.dados_com_ruido, self.dados_com_ruido.aptos_1t)
        with mock.patch.object(nucleo, "TOLERANCIA_LACUNA_DUALIDADE", 0.0):
            with self.assertRaises(nucleo.ErroConvergenciaAjuste):
                nucleo.ajustar_beta_restrito(equacoes)

    def test_grupo_ausente_da_amostra_e_erro(self) -> None:
        dados = self.dados_com_ruido
        matriz_origem_sem_demais = dados.matriz_origem.copy()
        matriz_origem_sem_demais[:, nucleo.ORIGENS_1T.index("demais")] = 0.0
        equacoes = nucleo.calcular_equacoes_normais(
            matriz_origem_sem_demais,
            dados.matriz_destino,
            dados.aptos_1t,
        )
        with self.assertRaises(nucleo.ErroDadosInvalidos):
            nucleo.ajustar_beta_restrito(equacoes)

    def test_lacuna_de_dualidade_e_zero_no_otimo_trivial(self) -> None:
        # Se Y = X beta com beta em vértice (0 ou 1), o ótimo tem gradiente nulo.
        beta_vertice = np.zeros((8, 4))
        beta_vertice[:, 0] = 1.0
        matriz_g = np.eye(8)
        matriz_h = matriz_g @ beta_vertice
        lacuna = nucleo.calcular_lacuna_de_dualidade(beta_vertice, matriz_g, matriz_h)
        self.assertAlmostEqual(lacuna, 0.0, places=15)

    def test_numeros_de_condicao_sao_positivos_e_o_escalonamento_reduz(self) -> None:
        equacoes = construir_equacoes_de_dados(self.dados_com_ruido, self.dados_com_ruido.aptos_1t)
        ajuste = nucleo.ajustar_beta_restrito(equacoes)
        self.assertGreater(ajuste.numero_condicao_g, 1.0)
        self.assertLessEqual(ajuste.numero_condicao_g_escalada, ajuste.numero_condicao_g)


# ---------------------------------------------------------------------------
# População de grupos, fluxos e agregação
# ---------------------------------------------------------------------------


class TesteFluxosEAgregacao(unittest.TestCase):
    """N_reg, fluxos em votos e agregação Brasil."""

    def setUp(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES + 10)
        self.beta_por_regiao = np.zeros((5, 8, 4))
        for posicao_regiao in range(5):
            self.beta_por_regiao[posicao_regiao] = sortear_beta_verdadeiro(gerador)
        self.dados = construir_dados_sinteticos_pequenos(gerador, self.beta_por_regiao, False)
        self.indices = nucleo.indices_por_regiao(self.dados.regiao)
        self.populacao = nucleo.calcular_populacao_de_grupos_por_regiao(
            self.dados.contagens_origem,
            self.indices,
        )
        self.multiplicidade_unitaria = np.ones(self.dados.regiao.shape[0], dtype=np.int64)

    def test_populacao_de_grupos_confere_com_a_formula_aptos_vezes_x(self) -> None:
        for posicao_regiao, nome_regiao in enumerate(nucleo.REGIOES):
            posicoes = self.indices[nome_regiao]
            aptos_da_regiao = self.dados.aptos_1t[posicoes]
            x_da_regiao = self.dados.matriz_origem[posicoes]
            esperado = (aptos_da_regiao[:, np.newaxis] * x_da_regiao).sum(axis=0)
            np.testing.assert_allclose(self.populacao[posicao_regiao], esperado, rtol=1e-12)

    def test_populacao_soma_os_aptos_da_regiao(self) -> None:
        for posicao_regiao, nome_regiao in enumerate(nucleo.REGIOES):
            aptos_da_regiao = self.dados.aptos_1t[self.indices[nome_regiao]].sum()
            self.assertEqual(self.populacao[posicao_regiao].sum(), aptos_da_regiao)

    def test_indices_por_regiao_cobrem_todos_os_municipios_sem_repeticao(self) -> None:
        todas_as_posicoes = np.concatenate([self.indices[nome] for nome in nucleo.REGIOES])
        self.assertEqual(np.sort(todas_as_posicoes).tolist(), list(range(self.dados.regiao.shape[0])))

    def test_regiao_desconhecida_e_erro(self) -> None:
        regiao_com_intrusa = self.dados.regiao.copy()
        regiao_com_intrusa[0] = "Atlantida"
        with self.assertRaises(nucleo.ErroDadosInvalidos):
            nucleo.indices_por_regiao(regiao_com_intrusa)

    def test_fluxos_somam_a_populacao_do_grupo(self) -> None:
        fluxos = nucleo.calcular_fluxos_em_votos(self.beta_por_regiao[0], self.populacao[0])
        np.testing.assert_allclose(fluxos.sum(axis=1), self.populacao[0], rtol=1e-12)

    def test_converter_fluxos_em_beta_inverte_o_calculo_de_fluxos(self) -> None:
        fluxos = nucleo.calcular_fluxos_em_votos(self.beta_por_regiao[1], self.populacao[1])
        beta_recuperado = nucleo.converter_fluxos_em_beta(fluxos)
        np.testing.assert_allclose(beta_recuperado, self.beta_por_regiao[1], rtol=1e-12)

    def test_origem_sem_fluxo_total_e_erro(self) -> None:
        fluxos = np.ones((8, 4))
        fluxos[3] = 0.0
        with self.assertRaises(nucleo.ErroDadosInvalidos):
            nucleo.converter_fluxos_em_beta(fluxos)

    def test_e1_recupera_beta_regional_e_o_brasil_e_media_ponderada_por_n(self) -> None:
        estimativa = nucleo.estimar_especificacao(
            self.dados,
            nucleo.ESPECIFICACAO_E1,
            self.indices,
            self.populacao,
            self.multiplicidade_unitaria,
        )
        np.testing.assert_allclose(
            estimativa.beta_por_regiao,
            self.beta_por_regiao,
            rtol=0,
            atol=TOLERANCIA_RECUPERACAO_SEM_RUIDO,
        )

        fluxo_esperado = np.zeros((8, 4))
        for posicao_regiao in range(5):
            fluxo_esperado += self.beta_por_regiao[posicao_regiao] * self.populacao[posicao_regiao][:, np.newaxis]
        beta_brasil_esperado = fluxo_esperado / fluxo_esperado.sum(axis=1, keepdims=True)

        np.testing.assert_allclose(
            estimativa.beta_brasil,
            beta_brasil_esperado,
            rtol=0,
            atol=TOLERANCIA_RECUPERACAO_SEM_RUIDO,
        )
        np.testing.assert_allclose(
            estimativa.fluxos_brasil.sum(axis=1),
            self.populacao.sum(axis=0),
            rtol=1e-12,
        )
        np.testing.assert_allclose(estimativa.beta_brasil.sum(axis=1), 1.0, rtol=0, atol=1e-12)

    def test_e2_usa_o_mesmo_beta_em_todas_as_regioes(self) -> None:
        estimativa = nucleo.estimar_especificacao(
            self.dados,
            nucleo.ESPECIFICACAO_E2,
            self.indices,
            self.populacao,
            self.multiplicidade_unitaria,
        )
        self.assertEqual(list(estimativa.resultados_ajuste.keys()), [nucleo.ROTULO_BRASIL])
        for posicao_regiao in range(5):
            np.testing.assert_allclose(
                estimativa.beta_por_regiao[posicao_regiao],
                estimativa.beta_brasil,
                rtol=0,
                atol=1e-15,
            )

    def test_e3_ignora_aptos_nos_pesos_e_e1_usa(self) -> None:
        pesos_e1 = nucleo.calcular_pesos_do_ajuste(
            self.dados,
            nucleo.ESPECIFICACAO_E1,
            self.multiplicidade_unitaria,
        )
        pesos_e3 = nucleo.calcular_pesos_do_ajuste(
            self.dados,
            nucleo.ESPECIFICACAO_E3,
            self.multiplicidade_unitaria,
        )
        np.testing.assert_array_equal(pesos_e1, self.dados.aptos_1t)
        np.testing.assert_array_equal(pesos_e3, np.ones(self.dados.regiao.shape[0]))

    def test_multiplicidade_multiplica_o_peso(self) -> None:
        multiplicidade = np.full(self.dados.regiao.shape[0], 3, dtype=np.int64)
        pesos = nucleo.calcular_pesos_do_ajuste(self.dados, nucleo.ESPECIFICACAO_E1, multiplicidade)
        np.testing.assert_array_equal(pesos, 3.0 * self.dados.aptos_1t)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


class TesteBootstrap(unittest.TestCase):
    """Reamostragem estratificada, réplicas e percentis."""

    def setUp(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES + 20)
        beta_por_regiao = np.tile(sortear_beta_verdadeiro(gerador), (5, 1, 1))
        self.dados = construir_dados_sinteticos_pequenos(gerador, beta_por_regiao, True)
        self.indices = nucleo.indices_por_regiao(self.dados.regiao)
        self.populacao = nucleo.calcular_populacao_de_grupos_por_regiao(
            self.dados.contagens_origem,
            self.indices,
        )

    def test_soma_das_multiplicidades_por_regiao_e_o_tamanho_da_regiao(self) -> None:
        gerador = np.random.default_rng(nucleo.SEMENTE_PADRAO)
        multiplicidades = nucleo.gerar_multiplicidades_bootstrap(
            self.indices,
            self.dados.regiao.shape[0],
            50,
            gerador,
        )
        self.assertEqual(multiplicidades.shape, (50, self.dados.regiao.shape[0]))
        self.assertGreaterEqual(multiplicidades.min(), 0)
        for nome_regiao in nucleo.REGIOES:
            posicoes = self.indices[nome_regiao]
            somas = multiplicidades[:, posicoes].sum(axis=1)
            np.testing.assert_array_equal(somas, np.full(50, posicoes.shape[0]))

    def test_mesma_semente_gera_as_mesmas_multiplicidades(self) -> None:
        primeira = nucleo.gerar_multiplicidades_bootstrap(
            self.indices, self.dados.regiao.shape[0], 10, np.random.default_rng(99)
        )
        segunda = nucleo.gerar_multiplicidades_bootstrap(
            self.indices, self.dados.regiao.shape[0], 10, np.random.default_rng(99)
        )
        np.testing.assert_array_equal(primeira, segunda)

    def test_media_da_multiplicidade_e_um(self) -> None:
        gerador = np.random.default_rng(nucleo.SEMENTE_PADRAO)
        multiplicidades = nucleo.gerar_multiplicidades_bootstrap(
            self.indices,
            self.dados.regiao.shape[0],
            400,
            gerador,
        )
        media_por_municipio = multiplicidades.mean(axis=0)
        self.assertAlmostEqual(float(media_por_municipio.mean()), 1.0, places=12)

    def test_percentis_do_ic(self) -> None:
        amostras = np.arange(1, 102, dtype=float).reshape(101, 1)  # 1..101
        limite_inferior, limite_superior = nucleo.calcular_intervalo_percentil(amostras)
        self.assertAlmostEqual(float(limite_inferior[0]), 3.5, places=12)
        self.assertAlmostEqual(float(limite_superior[0]), 98.5, places=12)

    def test_replicas_do_bootstrap_respeitam_restricoes_e_formato(self) -> None:
        numero_replicas = 8
        gerador = np.random.default_rng(nucleo.SEMENTE_PADRAO)
        multiplicidades = nucleo.gerar_multiplicidades_bootstrap(
            self.indices,
            self.dados.regiao.shape[0],
            numero_replicas,
            gerador,
        )
        multiplicidade_unitaria = np.ones(self.dados.regiao.shape[0], dtype=np.int64)
        estimativa_pontual = nucleo.estimar_especificacao(
            self.dados,
            nucleo.ESPECIFICACAO_E1,
            self.indices,
            self.populacao,
            multiplicidade_unitaria,
        )
        bootstrap = nucleo.executar_bootstrap(
            self.dados,
            nucleo.ESPECIFICACAO_E1,
            self.indices,
            self.populacao,
            multiplicidades,
            estimativa_pontual,
        )
        self.assertEqual(bootstrap.beta_por_regiao.shape, (numero_replicas, 5, 8, 4))
        self.assertEqual(bootstrap.beta_brasil.shape, (numero_replicas, 8, 4))
        np.testing.assert_allclose(bootstrap.beta_por_regiao.sum(axis=3), 1.0, rtol=0, atol=1e-9)
        np.testing.assert_allclose(bootstrap.beta_brasil.sum(axis=2), 1.0, rtol=0, atol=1e-9)
        # N_reg é fixo: o fluxo total de cada grupo no Brasil não varia entre réplicas.
        totais_de_fluxo = bootstrap.fluxos_brasil.sum(axis=2)
        for posicao_replica in range(numero_replicas):
            np.testing.assert_allclose(
                totais_de_fluxo[posicao_replica],
                self.populacao.sum(axis=0),
                rtol=1e-12,
            )

    def test_replica_com_multiplicidade_unitaria_reproduz_a_estimativa_pontual(self) -> None:
        multiplicidade_unitaria = np.ones(self.dados.regiao.shape[0], dtype=np.int64)
        estimativa_pontual = nucleo.estimar_especificacao(
            self.dados,
            nucleo.ESPECIFICACAO_E2,
            self.indices,
            self.populacao,
            multiplicidade_unitaria,
        )
        bootstrap = nucleo.executar_bootstrap(
            self.dados,
            nucleo.ESPECIFICACAO_E2,
            self.indices,
            self.populacao,
            multiplicidade_unitaria[np.newaxis, :],
            estimativa_pontual,
        )
        np.testing.assert_allclose(
            bootstrap.beta_brasil[0],
            estimativa_pontual.beta_brasil,
            rtol=0,
            atol=1e-6,
        )

    def test_falha_de_convergencia_na_replica_informa_a_replica(self) -> None:
        multiplicidade_unitaria = np.ones(self.dados.regiao.shape[0], dtype=np.int64)
        estimativa_pontual = nucleo.estimar_especificacao(
            self.dados,
            nucleo.ESPECIFICACAO_E2,
            self.indices,
            self.populacao,
            multiplicidade_unitaria,
        )
        multiplicidades_aleatorias = nucleo.gerar_multiplicidades_bootstrap(
            self.indices,
            self.dados.regiao.shape[0],
            1,
            np.random.default_rng(nucleo.SEMENTE_PADRAO),
        )
        with mock.patch.object(nucleo, "MAXIMO_ITERACOES_SLSQP", 1):
            with self.assertRaises(nucleo.ErroConvergenciaAjuste) as contexto:
                nucleo.executar_bootstrap(
                    self.dados,
                    nucleo.ESPECIFICACAO_E2,
                    self.indices,
                    self.populacao,
                    multiplicidades_aleatorias,
                    estimativa_pontual,
                )
        self.assertIn("Réplica bootstrap 0", str(contexto.exception))


# ---------------------------------------------------------------------------
# Diagnósticos e saídas
# ---------------------------------------------------------------------------


class TesteDiagnosticos(unittest.TestCase):
    """R², totais previstos e fronteira."""

    def test_r2_vale_um_para_previsao_perfeita(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES + 30)
        destino = gerador.uniform(size=(50, 4))
        pesos = gerador.uniform(1.0, 5.0, size=50)
        r2 = nucleo.calcular_r2_ponderado(destino, destino.copy(), pesos)
        np.testing.assert_allclose(r2, 1.0, rtol=0, atol=1e-15)

    def test_r2_vale_zero_para_previsao_igual_a_media_ponderada(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES + 31)
        destino = gerador.uniform(size=(50, 4))
        pesos = gerador.uniform(1.0, 5.0, size=50)
        media_ponderada = (pesos[:, np.newaxis] * destino).sum(axis=0) / pesos.sum()
        previsao = np.tile(media_ponderada, (50, 1))
        r2 = nucleo.calcular_r2_ponderado(destino, previsao, pesos)
        np.testing.assert_allclose(r2, 0.0, rtol=0, atol=1e-12)

    def test_r2_e_nan_quando_nao_ha_variancia(self) -> None:
        destino = np.full((10, 4), 0.25)
        previsao = np.full((10, 4), 0.20)
        r2 = nucleo.calcular_r2_ponderado(destino, previsao, np.ones(10))
        self.assertTrue(np.isnan(r2).all())

    def test_r2_pondera_pelos_pesos(self) -> None:
        destino = np.array([[0.0, 0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0], [0.5, 0.5, 0.5, 0.5]])
        previsao = np.array([[0.0] * 4, [1.0] * 4, [0.0] * 4])
        r2_pesos_iguais = nucleo.calcular_r2_ponderado(destino, previsao, np.ones(3))
        r2_ultimo_irrelevante = nucleo.calcular_r2_ponderado(
            destino, previsao, np.array([1.0, 1.0, 1e-9])
        )
        self.assertLess(r2_pesos_iguais[0], r2_ultimo_irrelevante[0])
        np.testing.assert_allclose(r2_ultimo_irrelevante, 1.0, rtol=0, atol=1e-6)

    def test_total_previsto_usa_aptos_do_segundo_turno(self) -> None:
        fracoes = np.array([[0.5, 0.5, 0.0, 0.0], [0.25, 0.25, 0.25, 0.25]])
        aptos_2t = np.array([100.0, 400.0])
        total = nucleo.calcular_total_previsto_destino(fracoes, aptos_2t)
        np.testing.assert_allclose(total, [150.0, 150.0, 100.0, 100.0])

    def test_prever_fracoes_usa_o_beta_da_regiao_de_cada_municipio(self) -> None:
        matriz_origem = np.tile(np.eye(8)[0], (2, 1))  # os dois municípios só têm `lula`
        regiao = np.array(["Sul", "Norte"])
        beta_por_regiao = np.zeros((5, 8, 4))
        beta_por_regiao[nucleo.REGIOES.index("Sul"), 0] = [1.0, 0.0, 0.0, 0.0]
        beta_por_regiao[nucleo.REGIOES.index("Norte"), 0] = [0.0, 0.0, 0.0, 1.0]
        previsao = nucleo.prever_fracoes_destino(matriz_origem, regiao, beta_por_regiao)
        np.testing.assert_array_equal(previsao, [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]])

    def test_fronteira_detecta_zero_um_e_respeita_a_tolerancia(self) -> None:
        beta = np.full((8, 4), 0.25)
        beta[0] = [1.0, 0.0, 0.0, 0.0]
        beta[1] = [nucleo.TOLERANCIA_FRONTEIRA_BETA, 0.5, 0.5 - nucleo.TOLERANCIA_FRONTEIRA_BETA, 0.0]
        beta[2] = [2 * nucleo.TOLERANCIA_FRONTEIRA_BETA, 0.5, 0.5, 0.0]
        celulas = nucleo.listar_celulas_na_fronteira(beta)
        descritas = []
        for nome_origem, nome_destino, _ in celulas:
            descritas.append((nome_origem, nome_destino))

        self.assertIn(("lula", "lula"), descritas)
        self.assertIn(("lula", "flavio"), descritas)
        self.assertIn(("flavio", "lula"), descritas)  # exatamente na tolerância
        self.assertIn(("flavio", "abstencao"), descritas)
        self.assertNotIn(("cury", "lula"), descritas)  # acima da tolerância
        self.assertIn(("cury", "abstencao"), descritas)

    def test_sem_celulas_na_fronteira(self) -> None:
        self.assertEqual(nucleo.listar_celulas_na_fronteira(np.full((8, 4), 0.25)), [])


class TesteTabelaTransferencias(unittest.TestCase):
    """Formato do `transferencias.csv`."""

    def test_formato_colunas_e_consistencia(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES + 40)
        beta_por_regiao = np.tile(sortear_beta_verdadeiro(gerador), (5, 1, 1))
        dados = construir_dados_sinteticos_pequenos(gerador, beta_por_regiao, True)
        indices = nucleo.indices_por_regiao(dados.regiao)
        populacao = nucleo.calcular_populacao_de_grupos_por_regiao(dados.contagens_origem, indices)
        multiplicidade_unitaria = np.ones(dados.regiao.shape[0], dtype=np.int64)
        multiplicidades = nucleo.gerar_multiplicidades_bootstrap(
            indices,
            dados.regiao.shape[0],
            20,
            np.random.default_rng(nucleo.SEMENTE_PADRAO),
        )

        estimativa = nucleo.estimar_especificacao(
            dados, nucleo.ESPECIFICACAO_E1, indices, populacao, multiplicidade_unitaria
        )
        bootstrap = nucleo.executar_bootstrap(
            dados, nucleo.ESPECIFICACAO_E1, indices, populacao, multiplicidades, estimativa
        )
        diagnostico = saidas.calcular_diagnostico_ajuste(dados, estimativa)
        resultado = saidas.ResultadoEspecificacao(
            nucleo.ESPECIFICACAO_E1, estimativa, bootstrap, diagnostico
        )

        tabela = saidas.montar_tabela_transferencias(resultado)

        self.assertEqual(list(tabela.columns), list(saidas.COLUNAS_TRANSFERENCIAS))
        self.assertEqual(len(tabela), 6 * 8 * 4)
        self.assertEqual(set(tabela["regiao"]), set(nucleo.REGIOES) | {nucleo.ROTULO_BRASIL})
        self.assertEqual(set(tabela["especificacao"]), {"E1"})
        self.assertTrue((tabela["beta_ic_inf"] <= tabela["beta_ic_sup"]).all())
        self.assertTrue((tabela["votos_ic_inf"] <= tabela["votos_ic_sup"]).all())

        soma_beta_por_linha_de_origem = tabela.groupby(["regiao", "origem_1t"])["beta"].sum()
        np.testing.assert_allclose(soma_beta_por_linha_de_origem.to_numpy(), 1.0, rtol=0, atol=1e-5)

        votos_brasil = tabela[tabela["regiao"] == nucleo.ROTULO_BRASIL]
        votos_regioes = tabela[tabela["regiao"] != nucleo.ROTULO_BRASIL]
        soma_brasil = votos_brasil["votos"].sum()
        soma_regioes = votos_regioes["votos"].sum()
        self.assertAlmostEqual(soma_brasil, soma_regioes, delta=1.0)
        self.assertAlmostEqual(soma_brasil, dados.aptos_1t.sum(), delta=1.0)

    def test_diagnostico_ajuste_tem_shape_e_fecha_o_total_do_segundo_turno(self) -> None:
        gerador = np.random.default_rng(SEMENTE_TESTES + 41)
        beta_por_regiao = np.tile(sortear_beta_verdadeiro(gerador), (5, 1, 1))
        dados = construir_dados_sinteticos_pequenos(gerador, beta_por_regiao, True)
        indices = nucleo.indices_por_regiao(dados.regiao)
        populacao = nucleo.calcular_populacao_de_grupos_por_regiao(dados.contagens_origem, indices)
        estimativa = nucleo.estimar_especificacao(
            dados,
            nucleo.ESPECIFICACAO_E2,
            indices,
            populacao,
            np.ones(dados.regiao.shape[0], dtype=np.int64),
        )
        diagnostico = saidas.calcular_diagnostico_ajuste(dados, estimativa)

        self.assertEqual(diagnostico.total_previsto.shape, (6, 4))
        total_previsto_brasil = diagnostico.total_previsto[saidas.POSICAO_BRASIL].sum()
        self.assertAlmostEqual(total_previsto_brasil, dados.aptos_2t.sum(), delta=1e-6)
        soma_das_regioes = diagnostico.total_real[:5].sum(axis=0)
        np.testing.assert_array_equal(soma_das_regioes, diagnostico.total_real[saidas.POSICAO_BRASIL])


# ---------------------------------------------------------------------------
# Integração com a base real
# ---------------------------------------------------------------------------


@unittest.skipUnless(CAMINHO_BASE_REAL.is_file(), "base real não encontrada")
class TesteBaseReal(unittest.TestCase):
    """Âncoras e invariância do solver na base real."""

    @classmethod
    def setUpClass(cls) -> None:
        base = nucleo.carregar_base_municipal(CAMINHO_BASE_REAL)
        municipios = nucleo.selecionar_municipios_brasileiros(base)
        cls.dados = nucleo.montar_dados_ecologicos(municipios)

    def test_todas_as_ancoras_aprovadas(self) -> None:
        resultados = nucleo.validar_ancoras(self.dados)
        for resultado in resultados:
            self.assertTrue(resultado.aprovada, msg=f"{resultado.nome}: {resultado}")
        self.assertEqual(self.dados.regiao.shape[0], 5571)

    def test_solver_independe_do_ponto_inicial_em_cada_regiao(self) -> None:
        indices = nucleo.indices_por_regiao(self.dados.regiao)
        gerador = np.random.default_rng(SEMENTE_TESTES + 50)
        pontos_iniciais = [
            None,
            np.tile([0.0, 0.0, 0.0, 1.0], (8, 1)),
            gerador.dirichlet(np.ones(4), size=8),
        ]
        pior_diferenca = 0.0
        for nome_regiao in nucleo.REGIOES:
            posicoes = indices[nome_regiao]
            equacoes = nucleo.calcular_equacoes_normais(
                self.dados.matriz_origem[posicoes],
                self.dados.matriz_destino[posicoes],
                self.dados.aptos_1t[posicoes],
            )
            solucoes = []
            for ponto_inicial in pontos_iniciais:
                solucoes.append(nucleo.ajustar_beta_restrito(equacoes, ponto_inicial).beta)
            for solucao in solucoes[1:]:
                pior_diferenca = max(pior_diferenca, float(np.abs(solucao - solucoes[0]).max()))

        self.assertLess(pior_diferenca, 1e-4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
