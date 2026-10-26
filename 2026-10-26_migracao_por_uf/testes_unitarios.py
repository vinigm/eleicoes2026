"""Testes da migração de votos por estado (nucleo_uf, saidas_uf, sintetico_uf).

Três famílias:
  * funções puras e casos de borda, sobre uma base sintética pequena (6 estados, 2 regiões,
    um estado com 1 município);
  * testes diferenciais: G e H pré-calculados contra o `calcular_equacoes_normais` regional
    sobre dados empilhados, e o solver SLSQP contra um algoritmo independente (gradiente
    projetado acelerado, FISTA) nos 27 estados da base real;
  * integração com a base real (âncoras, n efetivo de Kish, `transferencias_uf.csv` se existir).

Uso: python3 -I testes_unitarios.py
"""

import math
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

# `-I` remove a pasta do script do sys.path; ela é reinserida para achar os módulos locais.
PASTA_TRABALHO = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA_TRABALHO))

import nucleo_uf as nucleo  # noqa: E402
import saidas_uf as saidas  # noqa: E402
import sintetico_uf as sintetico  # noqa: E402

regional = nucleo.regional

SEMENTE_TESTES = 12345
CAMINHO_TRANSFERENCIAS_UF = PASTA_TRABALHO / "transferencias_uf.csv"
ITERACOES_REFERENCIA_FISTA = 8000
TOLERANCIA_BETA_FISTA = 1e-4
TOLERANCIA_OBJETIVO_FISTA = 1e-10

# Estados da base sintética: região -> {UF: número de municípios}.
ESTRUTURA_BASE_PEQUENA: dict[str, dict[str, int]] = {
    "Norte": {"AA": 40, "AB": 30, "AC": 25},
    "Sul": {"BA": 35, "BB": 30, "BC": 1},
}

BASE_REAL: nucleo.BaseUF | None = None


def setUpModule() -> None:
    """Carrega a base real uma única vez para os testes de integração."""
    global BASE_REAL
    municipios = nucleo.carregar_municipios_brasileiros(nucleo.CAMINHO_BASE_PARQUET)
    BASE_REAL = nucleo.montar_base_uf(municipios)


# ---------------------------------------------------------------------------
# Construção da base sintética pequena
# ---------------------------------------------------------------------------


def montar_municipios_sinteticos(semente: int) -> pd.DataFrame:
    """Municípios sintéticos com todas as colunas exigidas pelo modelo regional.

    X varia por município (Dirichlet); o 2º turno é sorteado de uma multinomial com
    um β qualquer apenas para fechar a identidade de soma (`aptos_2t` = soma do 2º turno).
    """
    gerador = np.random.default_rng(semente)
    concentracao = np.array([40.0, 40.0, 3.0, 3.0, 3.0, 1.0, 6.0, 20.0])
    linhas: list[dict[str, object]] = []
    codigo = 100

    for nome_regiao, ufs_da_regiao in ESTRUTURA_BASE_PEQUENA.items():
        for sigla, numero_municipios in ufs_da_regiao.items():
            for _ in range(numero_municipios):
                codigo += 1
                aptos = int(gerador.integers(3000, 80000))
                fracoes = gerador.dirichlet(concentracao)
                origem = gerador.multinomial(aptos, fracoes)
                destino = gerador.multinomial(aptos, fracoes[[0, 1, 6, 7]] / fracoes[[0, 1, 6, 7]].sum())
                linhas.append(
                    {
                        "sg_uf": sigla,
                        "nm_regiao": nome_regiao,
                        "cd_municipio_tse": f"{codigo:05d}",
                        "fl_exterior": False,
                        "aptos_1t": aptos,
                        "abstencao_1t": int(origem[7]),
                        "nao_instaladas_1t": 0,
                        "brancos_1t": int(origem[6]),
                        "nulos_1t": 0,
                        "votos_1t_13": int(origem[0]),
                        "votos_1t_22": int(origem[1]),
                        "votos_1t_70": int(origem[2]),
                        "votos_1t_14": int(origem[3]),
                        "votos_1t_55": int(origem[4]),
                        "votos_1t_30": int(origem[5]),
                        "votos_1t_80": 0,
                        "votos_1t_16": 0,
                        "votos_1t_27": 0,
                        "votos_1t_21": 0,
                        "votos_1t_35": 0,
                        "votos_1t_29": 0,
                        "aptos_2t": int(destino.sum()),
                        "abstencao_2t": int(destino[3]),
                        "nao_instaladas_2t": 0,
                        "brancos_2t": int(destino[2]),
                        "nulos_2t": 0,
                        "votos_2t_13": int(destino[0]),
                        "votos_2t_22": int(destino[1]),
                    }
                )

    return pd.DataFrame(linhas)


def montar_base_pequena() -> nucleo.BaseUF:
    """Base por UF pequena (6 estados; BC tem 1 município)."""
    municipios = montar_municipios_sinteticos(SEMENTE_TESTES)
    return nucleo.montar_base_uf(municipios)


def montar_base_pequena_sem_ruido(
    betas_verdadeiros: np.ndarray,
) -> nucleo.BaseUF:
    """Base pequena com Y = X beta_estado exato (sem ruído), para testes de recuperação."""
    base = montar_base_pequena()
    destino_exato = np.zeros_like(base.dados.matriz_destino)

    posicoes_por_uf = nucleo.listar_posicoes_por_uf(base)
    for posicao_uf, posicoes in enumerate(posicoes_por_uf):
        destino_exato[posicoes] = base.dados.matriz_origem[posicoes] @ betas_verdadeiros[posicao_uf]

    return nucleo.substituir_destino(base, destino_exato)


def calcular_estatisticas_cheias(base: nucleo.BaseUF) -> tuple[nucleo.EstatisticasPorUF, nucleo.EstatisticasPorUF]:
    """(estatísticas por UF, estatísticas de g\\u por UF) com a amostra completa."""
    multiplicidade = np.ones(base.dados.aptos_1t.shape[0])
    estatisticas = nucleo.calcular_estatisticas_por_uf(base, multiplicidade)
    estatisticas_demais = nucleo.somar_demais_ufs_da_regiao(base, estatisticas)
    return estatisticas, estatisticas_demais


# ---------------------------------------------------------------------------
# Referência independente: gradiente projetado acelerado (FISTA)
# ---------------------------------------------------------------------------


def projetar_no_simplex(vetor: np.ndarray, soma: float) -> np.ndarray:
    """Projeção euclidiana de `vetor` em {x >= 0, sum x = soma} (ordenação)."""
    ordenado = np.sort(vetor)[::-1]
    soma_acumulada = np.cumsum(ordenado) - soma
    posicoes = np.arange(1, vetor.size + 1)
    mascara_ativa = ordenado - soma_acumulada / posicoes > 0
    ultima_ativa = posicoes[mascara_ativa][-1]
    limiar = soma_acumulada[mascara_ativa][-1] / ultima_ativa
    return np.maximum(vetor - limiar, 0.0)


def resolver_por_fista(
    matriz_g: np.ndarray,
    matriz_h: np.ndarray,
    numero_iteracoes: int,
) -> np.ndarray:
    """Minimiza sum_c (b_c'G b_c - 2 b_c'H_c) nas 8 linhas-simplex por FISTA.

    Algoritmo diferente do SLSQP do solver regional: serve de referência independente.
    Reescala as variáveis por sqrt(G_rr) só para condicionamento (mesmo ótimo em beta).
    """
    fatores = np.sqrt(np.diag(matriz_g))
    g_escalada = matriz_g / np.outer(fatores, fatores)
    h_escalada = matriz_h / fatores[:, np.newaxis]
    constante_lipschitz = 2.0 * np.linalg.eigvalsh(g_escalada).max()

    ponto = np.tile(fatores[:, np.newaxis] / regional.NUMERO_DESTINOS, (1, regional.NUMERO_DESTINOS))
    ponto_extrapolado = ponto.copy()
    parametro_t = 1.0

    for _ in range(numero_iteracoes):
        gradiente = 2.0 * (g_escalada @ ponto_extrapolado - h_escalada)
        passo = ponto_extrapolado - gradiente / constante_lipschitz
        novo_ponto = np.zeros_like(passo)
        for posicao_origem in range(regional.NUMERO_ORIGENS):
            novo_ponto[posicao_origem] = projetar_no_simplex(
                passo[posicao_origem],
                fatores[posicao_origem],
            )
        novo_parametro_t = (1.0 + math.sqrt(1.0 + 4.0 * parametro_t**2)) / 2.0
        peso_momento = (parametro_t - 1.0) / novo_parametro_t
        ponto_extrapolado = novo_ponto + peso_momento * (novo_ponto - ponto)
        ponto = novo_ponto
        parametro_t = novo_parametro_t

    return ponto / fatores[:, np.newaxis]


# ---------------------------------------------------------------------------
# Funções puras
# ---------------------------------------------------------------------------


class TestKishEDobras(unittest.TestCase):
    """n efetivo de Kish e partição determinística em dobras."""

    def test_pesos_iguais_dao_n(self) -> None:
        soma_pesos = np.array([10.0 * 4])
        soma_quadrados = np.array([10.0**2 * 4])
        n_efetivo = nucleo.calcular_n_efetivo_kish(soma_pesos, soma_quadrados)
        self.assertAlmostEqual(float(n_efetivo[0]), 4.0, places=12)

    def test_valor_conhecido(self) -> None:
        # pesos 1 e 3: (1+3)^2 / (1+9) = 1,6
        n_efetivo = nucleo.calcular_n_efetivo_kish(np.array([4.0]), np.array([10.0]))
        self.assertAlmostEqual(float(n_efetivo[0]), 1.6, places=12)

    def test_um_municipio_dao_um(self) -> None:
        n_efetivo = nucleo.calcular_n_efetivo_kish(np.array([777.0]), np.array([777.0**2]))
        self.assertAlmostEqual(float(n_efetivo[0]), 1.0, places=12)

    def test_sem_dados_da_zero(self) -> None:
        n_efetivo = nucleo.calcular_n_efetivo_kish(np.array([0.0]), np.array([0.0]))
        self.assertEqual(float(n_efetivo[0]), 0.0)

    def test_dobras_usam_codigo_inteiro_modulo_5(self) -> None:
        codigos = np.array(["01007", "00005", "00019", "99999", "12345"])
        dobras = nucleo.calcular_dobras(codigos, 5)
        np.testing.assert_array_equal(dobras, np.array([2, 0, 4, 4, 0]))

    def test_dobras_codigo_nao_numerico_levanta_erro(self) -> None:
        with self.assertRaises(ValueError):
            nucleo.calcular_dobras(np.array(["ABC"]), 5)

    def test_dobras_numero_invalido_levanta_erro(self) -> None:
        with self.assertRaises(ValueError):
            nucleo.calcular_dobras(np.array(["00001"]), 0)


class TestProdutosEEstatisticas(unittest.TestCase):
    """Pré-cálculo de G e H por estado e região sem o estado."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.base = montar_base_pequena()
        cls.estatisticas, cls.estatisticas_demais = calcular_estatisticas_cheias(cls.base)

    def test_produtos_por_municipio_formato_e_valores(self) -> None:
        origem = np.array([[0.5, 0.5, 0, 0, 0, 0, 0, 0], [1.0, 0, 0, 0, 0, 0, 0, 0]])
        destino = np.array([[0.2, 0.3, 0.1, 0.4], [1.0, 0, 0, 0]])
        produtos = nucleo.calcular_produtos_por_municipio(origem, destino)
        self.assertEqual(produtos.shape, (2, 96))
        produto_xx = produtos[0, :64].reshape(8, 8)
        produto_xy = produtos[0, 64:].reshape(8, 4)
        np.testing.assert_allclose(produto_xx, np.outer(origem[0], origem[0]), atol=1e-15)
        np.testing.assert_allclose(produto_xy, np.outer(origem[0], destino[0]), atol=1e-15)

    def test_g_h_por_uf_igual_ao_regional_sobre_os_municipios_do_estado(self) -> None:
        """Teste diferencial: G_u/W_u e H_u/W_u contra calcular_equacoes_normais regional."""
        posicoes_por_uf = nucleo.listar_posicoes_por_uf(self.base)
        for posicao_uf, posicoes in enumerate(posicoes_por_uf):
            equacoes_referencia = regional.calcular_equacoes_normais(
                self.base.dados.matriz_origem[posicoes],
                self.base.dados.matriz_destino[posicoes],
                self.base.dados.aptos_1t[posicoes],
            )
            soma_pesos = self.estatisticas.soma_pesos[posicao_uf]
            g_uf = self.estatisticas.g_bruta[posicao_uf] / soma_pesos
            h_uf = self.estatisticas.h_bruta[posicao_uf] / soma_pesos
            np.testing.assert_allclose(g_uf, equacoes_referencia.matriz_g, rtol=1e-12, atol=1e-15)
            np.testing.assert_allclose(h_uf, equacoes_referencia.matriz_h, rtol=1e-12, atol=1e-15)

    def test_demais_ufs_exclui_o_proprio_estado_e_so_a_mesma_regiao(self) -> None:
        for posicao_uf, sigla in enumerate(self.base.lista_ufs):
            soma_g_esperada = np.zeros((8, 8))
            soma_pesos_esperada = 0.0
            for posicao_outra, outra_sigla in enumerate(self.base.lista_ufs):
                mesma_regiao = self.base.regiao_da_uf[posicao_outra] == self.base.regiao_da_uf[posicao_uf]
                if mesma_regiao and outra_sigla != sigla:
                    soma_g_esperada += self.estatisticas.g_bruta[posicao_outra]
                    soma_pesos_esperada += self.estatisticas.soma_pesos[posicao_outra]
            np.testing.assert_allclose(
                self.estatisticas_demais.g_bruta[posicao_uf],
                soma_g_esperada,
                rtol=1e-12,
            )
            self.assertAlmostEqual(
                float(self.estatisticas_demais.soma_pesos[posicao_uf]),
                soma_pesos_esperada,
                places=6,
            )

    def test_multiplicidade_zero_exclui_o_municipio(self) -> None:
        multiplicidade = np.ones(self.base.dados.aptos_1t.shape[0])
        multiplicidade[:10] = 0.0
        estatisticas = nucleo.calcular_estatisticas_por_uf(self.base, multiplicidade)
        esperado = self.estatisticas.soma_pesos.sum() - self.base.dados.aptos_1t[:10].sum()
        self.assertAlmostEqual(float(estatisticas.soma_pesos.sum()), float(esperado), places=6)

    def test_multiplicidade_invalida_levanta_erro(self) -> None:
        with self.assertRaises(nucleo.ErroDadosUF):
            nucleo.calcular_estatisticas_por_uf(self.base, np.ones(3))
        multiplicidade_negativa = -np.ones(self.base.dados.aptos_1t.shape[0])
        with self.assertRaises(nucleo.ErroDadosUF):
            nucleo.calcular_estatisticas_por_uf(self.base, multiplicidade_negativa)

    def test_substituir_destino_formato_invalido(self) -> None:
        with self.assertRaises(nucleo.ErroDadosUF):
            nucleo.substituir_destino(self.base, np.zeros((3, 4)))


class TestEquacoesCombinadas(unittest.TestCase):
    """O QP combinado (estado + região sem o estado)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.base = montar_base_pequena()
        cls.estatisticas, cls.estatisticas_demais = calcular_estatisticas_cheias(cls.base)

    def test_equacoes_equivalem_ao_empilhamento_ponderado(self) -> None:
        """Teste diferencial: G, H combinados contra regional sobre dados empilhados.

        Empilhar os municípios do estado com peso w_i / W_u e os de g\\u com peso
        (kappa / n_u) w_i / W_{g\\u} e normalizar pela soma dos pesos deve dar o mesmo G e H.
        """
        kappa = 3.0
        posicao_uf = self.base.lista_ufs.index("AB")
        posicoes_por_uf = nucleo.listar_posicoes_por_uf(self.base)
        posicoes_estado = posicoes_por_uf[posicao_uf]

        posicoes_demais: list[int] = []
        for posicao_outra, sigla in enumerate(self.base.lista_ufs):
            mesma_regiao = self.base.regiao_da_uf[posicao_outra] == self.base.regiao_da_uf[posicao_uf]
            if mesma_regiao and posicao_outra != posicao_uf:
                posicoes_demais.extend(posicoes_por_uf[posicao_outra].tolist())
        posicoes_demais_array = np.array(posicoes_demais)

        aptos = self.base.dados.aptos_1t
        soma_pesos_estado = aptos[posicoes_estado].sum()
        soma_pesos_demais = aptos[posicoes_demais_array].sum()
        n_efetivo = soma_pesos_estado**2 / (aptos[posicoes_estado] ** 2).sum()

        pesos_estado = aptos[posicoes_estado] / soma_pesos_estado
        pesos_demais = (kappa / n_efetivo) * aptos[posicoes_demais_array] / soma_pesos_demais

        posicoes_empilhadas = np.concatenate([posicoes_estado, posicoes_demais_array])
        pesos_empilhados = np.concatenate([pesos_estado, pesos_demais])
        referencia = regional.calcular_equacoes_normais(
            self.base.dados.matriz_origem[posicoes_empilhadas],
            self.base.dados.matriz_destino[posicoes_empilhadas],
            pesos_empilhados,
        )

        montagem = nucleo.montar_equacoes_da_uf(
            self.estatisticas,
            self.estatisticas_demais,
            posicao_uf,
            kappa,
        )
        np.testing.assert_allclose(montagem.equacoes.matriz_g, referencia.matriz_g, rtol=1e-10, atol=1e-14)
        np.testing.assert_allclose(montagem.equacoes.matriz_h, referencia.matriz_h, rtol=1e-10, atol=1e-14)
        self.assertAlmostEqual(montagem.n_efetivo, float(n_efetivo), places=9)

    def test_peso_da_regiao_e_kappa_sobre_n_mais_kappa(self) -> None:
        posicao_uf = self.base.lista_ufs.index("AA")
        for kappa in (0.25, 1.0, 4.0, 64.0):
            montagem = nucleo.montar_equacoes_da_uf(
                self.estatisticas,
                self.estatisticas_demais,
                posicao_uf,
                kappa,
            )
            esperado = kappa / (montagem.n_efetivo + kappa)
            self.assertAlmostEqual(montagem.peso_regiao, esperado, places=12)

    def test_kappa_infinito_usa_so_a_regiao(self) -> None:
        posicao_uf = self.base.lista_ufs.index("BA")
        montagem = nucleo.montar_equacoes_da_uf(
            self.estatisticas,
            self.estatisticas_demais,
            posicao_uf,
            math.inf,
        )
        soma_pesos_regiao = self.estatisticas_demais.soma_pesos[posicao_uf]
        g_regiao = self.estatisticas_demais.g_bruta[posicao_uf] / soma_pesos_regiao
        np.testing.assert_allclose(montagem.equacoes.matriz_g, g_regiao, rtol=1e-12)
        self.assertEqual(montagem.peso_regiao, 1.0)

    def test_kappa_muito_grande_converge_para_a_regiao(self) -> None:
        posicao_uf = self.base.lista_ufs.index("BA")
        montagem_grande = nucleo.montar_equacoes_da_uf(
            self.estatisticas,
            self.estatisticas_demais,
            posicao_uf,
            1e12,
        )
        montagem_infinita = nucleo.montar_equacoes_da_uf(
            self.estatisticas,
            self.estatisticas_demais,
            posicao_uf,
            math.inf,
        )
        np.testing.assert_allclose(
            montagem_grande.equacoes.matriz_g,
            montagem_infinita.equacoes.matriz_g,
            rtol=1e-9,
        )

    def test_estado_sem_dados_usa_so_a_regiao(self) -> None:
        """DF fora do treino: peso zero no estado => ótimo só do termo da região."""
        posicao_uf = self.base.lista_ufs.index("BC")
        multiplicidade = np.ones(self.base.dados.aptos_1t.shape[0])
        posicoes_bc = nucleo.listar_posicoes_por_uf(self.base)[posicao_uf]
        multiplicidade[posicoes_bc] = 0.0
        estatisticas_treino = nucleo.calcular_estatisticas_por_uf(self.base, multiplicidade)
        montagem = nucleo.montar_equacoes_da_uf(
            estatisticas_treino,
            self.estatisticas_demais,
            posicao_uf,
            4.0,
        )
        self.assertEqual(montagem.peso_regiao, 1.0)
        self.assertEqual(montagem.n_efetivo, 0.0)

    def test_kappa_invalido_levanta_erro(self) -> None:
        posicao_uf = 0
        for kappa_invalido in (0.0, -1.0, math.nan):
            with self.assertRaises(nucleo.ErroDadosUF):
                nucleo.montar_equacoes_da_uf(
                    self.estatisticas,
                    self.estatisticas_demais,
                    posicao_uf,
                    kappa_invalido,
                )


class TestAjuste(unittest.TestCase):
    """Solução do QP: recuperação sem ruído, limites de kappa, fallback e unicidade."""

    @classmethod
    def setUpClass(cls) -> None:
        beta_regiao = sintetico.BETA_REGIAO_T1
        deslocamentos = np.array([0.12, -0.10, 0.0, 0.0, 0.0, 0.0])
        cls.betas_verdadeiros = sintetico.montar_betas_verdadeiros_por_uf(beta_regiao, deslocamentos)
        # Estados AA e AB ganham β próprio (delta_u); os demais usam o β da região.
        cls.base = montar_base_pequena_sem_ruido(cls.betas_verdadeiros)
        cls.estatisticas, cls.estatisticas_demais = calcular_estatisticas_cheias(cls.base)

    def test_kappa_pequeno_recupera_o_beta_do_proprio_estado(self) -> None:
        posicao_uf = self.base.lista_ufs.index("AA")
        ajuste = nucleo.ajustar_beta_da_uf(
            self.base,
            self.estatisticas,
            self.estatisticas_demais,
            posicao_uf,
            1e-6,
            None,
        )
        erro_maximo = np.abs(ajuste.beta - self.betas_verdadeiros[posicao_uf]).max()
        self.assertLess(erro_maximo, 5e-3)

    def test_beta_constante_e_recuperado_para_qualquer_kappa(self) -> None:
        """Quando todos os estados da região compartilham β, qualquer kappa o recupera."""
        posicao_uf = self.base.lista_ufs.index("BA")
        for kappa in (0.25, 4.0, math.inf):
            ajuste = nucleo.ajustar_beta_da_uf(
                self.base,
                self.estatisticas,
                self.estatisticas_demais,
                posicao_uf,
                kappa,
                None,
            )
            erro_maximo = np.abs(ajuste.beta - self.betas_verdadeiros[posicao_uf]).max()
            self.assertLess(erro_maximo, 5e-3, msg=f"kappa={kappa}")

    def test_kappa_infinito_ignora_o_proprio_estado(self) -> None:
        """Com kappa infinito, mudar os dados do estado não muda beta (só a região importa)."""
        posicao_uf = self.base.lista_ufs.index("AA")
        ajuste_original = nucleo.ajustar_beta_da_uf(
            self.base,
            self.estatisticas,
            self.estatisticas_demais,
            posicao_uf,
            math.inf,
            None,
        )
        multiplicidade = np.ones(self.base.dados.aptos_1t.shape[0])
        posicoes_aa = nucleo.listar_posicoes_por_uf(self.base)[posicao_uf]
        multiplicidade[posicoes_aa] = 0.0
        estatisticas_sem_aa = nucleo.calcular_estatisticas_por_uf(self.base, multiplicidade)
        ajuste_sem_aa = nucleo.ajustar_beta_da_uf(
            self.base,
            estatisticas_sem_aa,
            self.estatisticas_demais,
            posicao_uf,
            math.inf,
            None,
        )
        np.testing.assert_allclose(ajuste_original.beta, ajuste_sem_aa.beta, atol=1e-12)

    def test_estado_de_um_municipio_tem_solucao_unica(self) -> None:
        """BC tem 1 município: G_estado tem posto 1, mas G combinado é definida positiva."""
        posicao_uf = self.base.lista_ufs.index("BC")
        montagem = nucleo.montar_equacoes_da_uf(
            self.estatisticas,
            self.estatisticas_demais,
            posicao_uf,
            4.0,
        )
        autovalor_minimo = np.linalg.eigvalsh(montagem.equacoes.matriz_g).min()
        self.assertGreater(autovalor_minimo, 0.0)

    def test_ponto_inicial_nao_muda_o_otimo(self) -> None:
        posicao_uf = self.base.lista_ufs.index("AB")
        ajuste_uniforme = nucleo.ajustar_beta_da_uf(
            self.base,
            self.estatisticas,
            self.estatisticas_demais,
            posicao_uf,
            4.0,
            None,
        )
        ponto_vertice = np.zeros((8, 4))
        ponto_vertice[:, 0] = 1.0
        ajuste_vertice = nucleo.ajustar_beta_da_uf(
            self.base,
            self.estatisticas,
            self.estatisticas_demais,
            posicao_uf,
            4.0,
            ponto_vertice,
        )
        np.testing.assert_allclose(ajuste_uniforme.beta, ajuste_vertice.beta, atol=1e-4)

    def test_linhas_do_beta_somam_um_e_ficam_em_zero_um(self) -> None:
        for posicao_uf in range(len(self.base.lista_ufs)):
            ajuste = nucleo.ajustar_beta_da_uf(
                self.base,
                self.estatisticas,
                self.estatisticas_demais,
                posicao_uf,
                4.0,
                None,
            )
            np.testing.assert_allclose(ajuste.beta.sum(axis=1), 1.0, atol=1e-8)
            self.assertGreaterEqual(float(ajuste.beta.min()), 0.0)
            self.assertLessEqual(float(ajuste.beta.max()), 1.0)

    def test_fallback_para_ponto_uniforme_quando_a_primeira_tentativa_falha(self) -> None:
        resultado_real = regional.ajustar_beta_restrito(
            nucleo.montar_equacoes_da_uf(
                self.estatisticas,
                self.estatisticas_demais,
                0,
                4.0,
            ).equacoes,
        )

        class SolverQueFalhaNaPrimeiraChamada:
            """Falha na 1ª chamada (ponto quente) e devolve o resultado real na 2ª."""

            def __init__(self) -> None:
                self.chamadas = 0

            def __call__(self, equacoes, beta_inicial=None):  # noqa: ANN001, ANN204
                self.chamadas += 1
                if self.chamadas == 1:
                    raise regional.ErroConvergenciaAjuste("lacuna acima do limite")
                return resultado_real

        solver_falso = SolverQueFalhaNaPrimeiraChamada()
        ponto_quente = np.full((8, 4), 0.25)
        with mock.patch.object(regional, "ajustar_beta_restrito", new=solver_falso):
            ajuste = nucleo.ajustar_beta_da_uf(
                self.base,
                self.estatisticas,
                self.estatisticas_demais,
                0,
                4.0,
                ponto_quente,
            )
        self.assertEqual(ajuste.numero_tentativas, 2)
        self.assertEqual(solver_falso.chamadas, 2)

    def test_falha_em_todas_as_tentativas_levanta_erro_rotulado(self) -> None:
        class SolverQueSempreFalha:
            """Falha sempre."""

            def __call__(self, equacoes, beta_inicial=None):  # noqa: ANN001, ANN204
                raise regional.ErroConvergenciaAjuste("sem convergência")

        with mock.patch.object(regional, "ajustar_beta_restrito", new=SolverQueSempreFalha()):
            with self.assertRaises(regional.ErroConvergenciaAjuste) as contexto:
                nucleo.ajustar_beta_da_uf(
                    self.base,
                    self.estatisticas,
                    self.estatisticas_demais,
                    0,
                    4.0,
                    np.full((8, 4), 0.25),
                )
        self.assertIn("UF AA", str(contexto.exception))
        self.assertIn("2 tentativa", str(contexto.exception))

    def test_votos_sao_beta_vezes_n(self) -> None:
        betas = np.full((6, 8, 4), 0.25)
        votos = nucleo.calcular_votos_por_uf(betas, self.base.populacao_por_uf)
        np.testing.assert_allclose(votos.sum(axis=2), self.base.populacao_por_uf, rtol=1e-12)


# ---------------------------------------------------------------------------
# Validação cruzada e bootstrap
# ---------------------------------------------------------------------------


class TestValidacaoCruzada(unittest.TestCase):
    """Curva de erro, estado de 1 município e escolha de kappa."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.base = montar_base_pequena()
        cls.kappas = (0.25, 1.0, 4.0, 16.0)
        cls.resultado = nucleo.executar_validacao_cruzada(cls.base, cls.kappas, nucleo.NUMERO_DOBRAS)

    def test_formato_da_curva(self) -> None:
        self.assertEqual(self.resultado.erro_por_kappa.shape, (4,))
        self.assertEqual(self.resultado.erro_por_kappa_e_uf.shape, (4, 6))
        self.assertTrue(np.all(self.resultado.erro_por_kappa > 0))
        self.assertGreater(self.resultado.erro_regiao, 0.0)

    def test_erro_total_e_a_soma_dos_erros_por_uf(self) -> None:
        np.testing.assert_allclose(
            self.resultado.erro_por_kappa_e_uf.sum(axis=1),
            self.resultado.erro_por_kappa,
            rtol=1e-12,
        )

    def test_kappa_otimo_e_o_argmin_da_grade(self) -> None:
        posicao = int(np.argmin(self.resultado.erro_por_kappa))
        self.assertEqual(self.resultado.kappa_otimo, self.kappas[posicao])

    def test_estado_de_um_municipio_tem_erro_igual_para_todo_kappa(self) -> None:
        """BC sempre sai do treino na própria dobra: ajuste = só região, erro independe de kappa."""
        posicao_bc = self.base.lista_ufs.index("BC")
        erros_bc = self.resultado.erro_por_kappa_e_uf[:, posicao_bc]
        # O beta só da região é resolvido várias vezes a partir de pontos iniciais distintos;
        # a diferença restante é a tolerância do solver (lacuna <= 1e-7), não efeito de kappa.
        np.testing.assert_allclose(erros_bc, erros_bc[0], rtol=1e-5)
        self.assertAlmostEqual(
            float(erros_bc[0]),
            float(self.resultado.erro_regiao_por_uf[posicao_bc]),
            places=9,
        )

    def test_curva_reproduzida_na_mao_para_uma_dobra_e_um_kappa(self) -> None:
        """Recalcula na mão (laços simples) o erro de validação de um estado e compara."""
        kappa = 4.0
        posicao_uf = self.base.lista_ufs.index("AA")
        posicoes_uf = nucleo.listar_posicoes_por_uf(self.base)[posicao_uf]
        _, estatisticas_demais = calcular_estatisticas_cheias(self.base)

        erro_manual = 0.0
        for dobra in range(nucleo.NUMERO_DOBRAS):
            multiplicidade = (self.base.dobra_do_municipio != dobra).astype(float)
            estatisticas_treino = nucleo.calcular_estatisticas_por_uf(self.base, multiplicidade)
            ajuste = nucleo.ajustar_beta_da_uf(
                self.base,
                estatisticas_treino,
                estatisticas_demais,
                posicao_uf,
                kappa,
                None,
            )
            for posicao_municipio in posicoes_uf:
                if self.base.dobra_do_municipio[posicao_municipio] != dobra:
                    continue
                origem = self.base.dados.matriz_origem[posicao_municipio]
                destino = self.base.dados.matriz_destino[posicao_municipio]
                previsto = origem @ ajuste.beta
                erro_manual += self.base.dados.aptos_1t[posicao_municipio] * float(((destino - previsto) ** 2).sum())

        posicao_kappa = self.kappas.index(kappa)
        erro_funcao = float(self.resultado.erro_por_kappa_e_uf[posicao_kappa, posicao_uf])
        self.assertAlmostEqual(erro_manual, erro_funcao, delta=1e-6 * max(erro_funcao, 1e-12))


class TestBootstrap(unittest.TestCase):
    """Multiplicidades estratificadas por estado e reprodutibilidade."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.base = montar_base_pequena()

    def test_soma_por_estado_igual_ao_numero_de_municipios(self) -> None:
        gerador = np.random.default_rng(1)
        multiplicidades = nucleo.gerar_multiplicidades_por_uf(self.base, 20, gerador)
        posicoes_por_uf = nucleo.listar_posicoes_por_uf(self.base)
        for posicoes in posicoes_por_uf:
            somas = multiplicidades[:, posicoes].sum(axis=1)
            np.testing.assert_array_equal(somas, posicoes.shape[0])
        self.assertTrue((multiplicidades >= 0).all())

    def test_estado_de_um_municipio_e_degenerado(self) -> None:
        gerador = np.random.default_rng(2)
        multiplicidades = nucleo.gerar_multiplicidades_por_uf(self.base, 20, gerador)
        posicao_bc = self.base.lista_ufs.index("BC")
        posicoes_bc = nucleo.listar_posicoes_por_uf(self.base)[posicao_bc]
        np.testing.assert_array_equal(multiplicidades[:, posicoes_bc], 1)

    def test_mesma_semente_reproduz_e_outra_semente_difere(self) -> None:
        primeira = nucleo.gerar_multiplicidades_por_uf(self.base, 10, np.random.default_rng(7))
        segunda = nucleo.gerar_multiplicidades_por_uf(self.base, 10, np.random.default_rng(7))
        terceira = nucleo.gerar_multiplicidades_por_uf(self.base, 10, np.random.default_rng(8))
        np.testing.assert_array_equal(primeira, segunda)
        self.assertFalse(np.array_equal(primeira, terceira))

    def test_executar_bootstrap_formato_viabilidade_e_reprodutibilidade(self) -> None:
        estimativa = nucleo.estimar_versao(self.base, nucleo.CODIGO_UF, 4.0, None)
        multiplicidades = nucleo.gerar_multiplicidades_por_uf(self.base, 6, np.random.default_rng(3))

        primeiro = nucleo.executar_bootstrap_uf(self.base, 4.0, estimativa.betas, multiplicidades)
        segundo = nucleo.executar_bootstrap_uf(self.base, 4.0, estimativa.betas, multiplicidades)

        self.assertEqual(primeiro.betas.shape, (6, 6, 8, 4))
        np.testing.assert_allclose(primeiro.betas.sum(axis=3), 1.0, atol=1e-8)
        self.assertGreaterEqual(float(primeiro.betas.min()), 0.0)
        np.testing.assert_allclose(primeiro.betas, segundo.betas, atol=1e-5)
        self.assertGreater(primeiro.maior_numero_condicao, 1.0)

    def test_replica_com_multiplicidade_um_reproduz_a_estimativa_pontual(self) -> None:
        estimativa = nucleo.estimar_versao(self.base, nucleo.CODIGO_UF, 4.0, None)
        multiplicidades = np.ones((1, self.base.dados.aptos_1t.shape[0]), dtype=np.int64)
        resultado = nucleo.executar_bootstrap_uf(self.base, 4.0, estimativa.betas, multiplicidades)
        np.testing.assert_allclose(resultado.betas[0], estimativa.betas, atol=1e-5)


# ---------------------------------------------------------------------------
# Teste sintético
# ---------------------------------------------------------------------------


class TestSintetico(unittest.TestCase):
    """Perturbação de β, sorteio multinomial e erro ponderado."""

    def test_perturbar_linha_mantem_o_simplex(self) -> None:
        linha_caiado = sintetico.BETA_REGIAO_T1[regional.ORIGENS_1T.index("caiado")]
        for deslocamento in (-0.15, -0.05, 0.0, 0.05, 0.15):
            nova_linha = sintetico.perturbar_linha(linha_caiado, deslocamento)
            self.assertAlmostEqual(float(nova_linha.sum()), 1.0, places=12)
            self.assertGreaterEqual(float(nova_linha.min()), 0.0)
            self.assertAlmostEqual(float(nova_linha[0] - linha_caiado[0]), deslocamento, places=12)
            self.assertAlmostEqual(float(nova_linha[1] - linha_caiado[1]), -deslocamento, places=12)

    def test_perturbar_linha_recorta_para_nao_ficar_negativa(self) -> None:
        linha = np.array([0.10, 0.20, 0.30, 0.40])
        nova_para_cima = sintetico.perturbar_linha(linha, 0.9)
        nova_para_baixo = sintetico.perturbar_linha(linha, -0.9)
        np.testing.assert_allclose(nova_para_cima, [0.30, 0.0, 0.30, 0.40], atol=1e-12)
        np.testing.assert_allclose(nova_para_baixo, [0.0, 0.30, 0.30, 0.40], atol=1e-12)

    def test_betas_verdadeiros_so_mudam_nas_tres_linhas(self) -> None:
        deslocamentos = np.array([0.1, -0.1, 0.0])
        betas = sintetico.montar_betas_verdadeiros_por_uf(sintetico.BETA_REGIAO_T1, deslocamentos)
        posicoes_perturbadas = sintetico.posicoes_das_origens_perturbadas()
        for posicao_uf in range(3):
            for posicao_origem in range(regional.NUMERO_ORIGENS):
                igual = np.allclose(betas[posicao_uf, posicao_origem], sintetico.BETA_REGIAO_T1[posicao_origem])
                if posicao_origem in posicoes_perturbadas and deslocamentos[posicao_uf] != 0.0:
                    self.assertFalse(igual)
                else:
                    self.assertTrue(igual)
        np.testing.assert_allclose(betas.sum(axis=2), 1.0, atol=1e-12)

    def test_posicoes_perturbadas_sao_caiado_cury_renan(self) -> None:
        posicoes = sintetico.posicoes_das_origens_perturbadas()
        nomes = [regional.ORIGENS_1T[posicao] for posicao in posicoes]
        self.assertEqual(sorted(nomes), ["caiado", "cury", "renan"])

    def test_deslocamentos_dentro_da_amplitude_e_reprodutiveis(self) -> None:
        primeiro = sintetico.sortear_deslocamentos_por_uf(27, np.random.default_rng(20261025))
        segundo = sintetico.sortear_deslocamentos_por_uf(27, np.random.default_rng(20261025))
        np.testing.assert_array_equal(primeiro, segundo)
        self.assertLessEqual(float(np.abs(primeiro).max()), sintetico.AMPLITUDE_DESLOCAMENTO)
        controle = sintetico.sortear_deslocamentos_por_uf(27, np.random.default_rng(1), 0.0)
        np.testing.assert_array_equal(controle, np.zeros(27))

    def test_destino_sintetico_soma_um_e_segue_a_esperanca(self) -> None:
        base = montar_base_pequena()
        betas = np.tile(sintetico.BETA_REGIAO_T1, (6, 1, 1))
        destino = sintetico.sortear_destino_sintetico(base, betas, np.random.default_rng(5))
        np.testing.assert_allclose(destino.sum(axis=1), 1.0, atol=1e-12)
        esperado = np.zeros_like(destino)
        for posicao_uf, posicoes in enumerate(nucleo.listar_posicoes_por_uf(base)):
            esperado[posicoes] = base.dados.matriz_origem[posicoes] @ betas[posicao_uf]
        pesos = base.dados.aptos_1t
        media_sorteada = (pesos[:, np.newaxis] * destino).sum(axis=0) / pesos.sum()
        media_esperada = (pesos[:, np.newaxis] * esperado).sum(axis=0) / pesos.sum()
        np.testing.assert_allclose(media_sorteada, media_esperada, atol=2e-3)

    def test_erro_ponderado_zero_quando_igual_e_valor_conhecido(self) -> None:
        verdadeiros = np.tile(sintetico.BETA_REGIAO_T1, (2, 1, 1))
        populacao = np.ones((2, 8))
        self.assertEqual(sintetico.calcular_erro_absoluto_ponderado(verdadeiros, verdadeiros, populacao), 0.0)

        estimados = verdadeiros.copy()
        posicao_caiado = regional.ORIGENS_1T.index("caiado")
        estimados[0, posicao_caiado, 0] += 0.4
        # um único |erro| de 0,4 em 1 de 4 destinações de (UF 0, caiado); 6 pares (UF, origem) com peso 1.
        esperado = (0.4 / 4.0) / 6.0
        obtido = sintetico.calcular_erro_absoluto_ponderado(estimados, verdadeiros, populacao)
        self.assertAlmostEqual(obtido, esperado, places=12)

    def test_erro_ponderado_respeita_os_pesos_n(self) -> None:
        verdadeiros = np.tile(sintetico.BETA_REGIAO_T1, (2, 1, 1))
        estimados = verdadeiros.copy()
        posicao_cury = regional.ORIGENS_1T.index("cury")
        estimados[1, posicao_cury, 2] += 0.4
        populacao = np.ones((2, 8))
        populacao[1, posicao_cury] = 100.0
        pesos_totais = populacao[:, sintetico.posicoes_das_origens_perturbadas()].sum()
        esperado = (100.0 * 0.4 / 4.0) / pesos_totais
        obtido = sintetico.calcular_erro_absoluto_ponderado(estimados, verdadeiros, populacao)
        self.assertAlmostEqual(obtido, esperado, places=12)


# ---------------------------------------------------------------------------
# Saídas e formatação
# ---------------------------------------------------------------------------


class TestSaidas(unittest.TestCase):
    """Formatação brasileira, curva e kappa*."""

    def test_formatar_numero(self) -> None:
        self.assertEqual(saidas.formatar_numero(1234567.891, 2), "1.234.567,89")
        self.assertEqual(saidas.formatar_numero(0.5, 3), "0,500")
        self.assertEqual(saidas.formatar_numero(math.inf, 2), "∞")
        self.assertEqual(saidas.formatar_numero(math.nan, 2), "n/d")

    def test_formatar_kappa(self) -> None:
        self.assertEqual(saidas.formatar_kappa(0.25), "0,25")
        self.assertEqual(saidas.formatar_kappa(4.0), "4")
        self.assertEqual(saidas.formatar_kappa(256.0), "256")
        self.assertEqual(saidas.formatar_kappa(math.inf), "∞")

    def test_tabela_markdown(self) -> None:
        texto = saidas.montar_tabela_markdown(["a", "b"], [["1", "2"]])
        self.assertEqual(texto, "| a | b |\n|---|---|\n| 1 | 2 |")

    def test_kappa_estrela_ignora_infinito_e_empate_pega_o_menor(self) -> None:
        curva = pd.DataFrame(
            {
                "kappa": [0.25, 1.0, 4.0, 16.0, math.inf],
                "erro_validacao": [5.0, 3.0, 3.0, 4.0, 0.1],
            }
        )
        kappa_estrela, na_borda = saidas.ler_kappa_estrela_da_curva(curva)
        self.assertEqual(kappa_estrela, 1.0)
        self.assertFalse(na_borda)

    def test_kappa_estrela_na_borda(self) -> None:
        curva = pd.DataFrame({"kappa": [0.25, 1.0, math.inf], "erro_validacao": [1.0, 2.0, 0.5]})
        kappa_estrela, na_borda = saidas.ler_kappa_estrela_da_curva(curva)
        self.assertEqual(kappa_estrela, 0.25)
        self.assertTrue(na_borda)

    def test_intervalos_do_bootstrap_com_replicas_iguais_colapsam_no_ponto(self) -> None:
        beta = np.full((3, 8, 4), 0.25)
        betas_bootstrap = np.tile(beta, (50, 1, 1, 1))
        populacao = np.full((3, 8), 100.0)
        intervalos = saidas.calcular_intervalos_do_bootstrap(betas_bootstrap, populacao)
        np.testing.assert_allclose(intervalos["beta_inf"], beta, atol=1e-15)
        np.testing.assert_allclose(intervalos["beta_sup"], beta, atol=1e-15)
        np.testing.assert_allclose(intervalos["votos_inf"], 25.0, atol=1e-12)

    def test_listar_ufs_piores_que_a_regiao(self) -> None:
        tabela = pd.DataFrame(
            {
                "uf": ["AA", "AA", "BB", "BB", "DF", "DF"],
                "kappa": [4.0, math.inf, 4.0, math.inf, 4.0, math.inf],
                "erro_validacao": [2.0, 1.0, 1.0, 2.0, 5.0, 1.0],
            }
        )
        piores = saidas.listar_ufs_piores_que_a_regiao(tabela, 4.0, ["DF"])
        self.assertEqual(piores, ["AA (2,00)"])


# ---------------------------------------------------------------------------
# Integração com a base real
# ---------------------------------------------------------------------------


class TestBaseReal(unittest.TestCase):
    """Âncoras, n efetivo de Kish e verificação independente do solver nos 27 estados."""

    def test_ancoras_nacionais_ufs_e_kish(self) -> None:
        resultados, divergencias_n_efetivo = nucleo.validar_ancoras_por_uf(BASE_REAL)
        divergentes = [resultado.nome for resultado in resultados if not resultado.aprovada]
        self.assertEqual(divergentes, [])
        self.assertEqual(divergencias_n_efetivo, [])
        nucleo.exigir_ancoras_por_uf(BASE_REAL)

    def test_soma_das_populacoes_por_uf_e_a_ancora(self) -> None:
        totais = BASE_REAL.populacao_por_uf.sum(axis=0)
        self.assertEqual(int(round(totais[regional.ORIGENS_1T.index("caiado")])), 2_600_440)
        self.assertEqual(int(round(totais[regional.ORIGENS_1T.index("cury")])), 3_438_835)
        self.assertEqual(int(round(totais[regional.ORIGENS_1T.index("renan")])), 2_667_307)

    def test_vinte_e_sete_ufs_cada_uma_em_uma_regiao_e_df_com_go_mt_ms(self) -> None:
        self.assertEqual(len(BASE_REAL.lista_ufs), 27)
        posicao_df = BASE_REAL.lista_ufs.index("DF")
        irmas: list[str] = []
        for posicao_outra, sigla in enumerate(BASE_REAL.lista_ufs):
            if BASE_REAL.mascara_demais_ufs_da_regiao[posicao_df, posicao_outra] == 1.0:
                irmas.append(sigla)
        self.assertEqual(sorted(irmas), ["GO", "MS", "MT"])

    def test_dobras_cobrem_as_cinco_classes(self) -> None:
        contagem = np.bincount(BASE_REAL.dobra_do_municipio, minlength=5)
        self.assertEqual(contagem.sum(), 5571)
        self.assertTrue((contagem > 900).all())

    def test_solver_contra_fista_nos_27_estados_e_tres_versoes(self) -> None:
        """Teste diferencial: SLSQP (regional) x gradiente projetado acelerado independente."""
        estatisticas, estatisticas_demais = calcular_estatisticas_cheias(BASE_REAL)
        casos = (4.0, nucleo.KAPPA_SOZINHO, nucleo.KAPPA_REGIAO)
        maior_diferenca_beta = 0.0
        maior_diferenca_objetivo = 0.0

        for kappa in casos:
            for posicao_uf in range(len(BASE_REAL.lista_ufs)):
                ajuste = nucleo.ajustar_beta_da_uf(
                    BASE_REAL,
                    estatisticas,
                    estatisticas_demais,
                    posicao_uf,
                    kappa,
                    None,
                )
                montagem = nucleo.montar_equacoes_da_uf(estatisticas, estatisticas_demais, posicao_uf, kappa)
                beta_fista = resolver_por_fista(
                    montagem.equacoes.matriz_g,
                    montagem.equacoes.matriz_h,
                    ITERACOES_REFERENCIA_FISTA,
                )
                diferenca_beta = float(np.abs(beta_fista - ajuste.beta).max())
                objetivo_fista = regional.calcular_valor_objetivo(
                    beta_fista.reshape(32),
                    montagem.equacoes.matriz_g,
                    montagem.equacoes.matriz_h,
                )
                diferenca_objetivo = abs(objetivo_fista - ajuste.resultado_solver.valor_objetivo)
                maior_diferenca_beta = max(maior_diferenca_beta, diferenca_beta)
                maior_diferenca_objetivo = max(maior_diferenca_objetivo, diferenca_objetivo)

        print(
            f"\n[FISTA x SLSQP] maior |dbeta| = {maior_diferenca_beta:.2e}; "
            f"maior |dobjetivo| = {maior_diferenca_objetivo:.2e}"
        )
        self.assertLess(maior_diferenca_beta, TOLERANCIA_BETA_FISTA)
        self.assertLess(maior_diferenca_objetivo, TOLERANCIA_OBJETIVO_FISTA)

    def test_carregar_betas_e1_linhas_somam_um(self) -> None:
        betas_e1 = nucleo.carregar_betas_e1(nucleo.CAMINHO_TRANSFERENCIAS_E1)
        self.assertEqual(sorted(betas_e1.keys()), sorted(list(regional.REGIOES) + [regional.ROTULO_BRASIL]))
        for rotulo, beta in betas_e1.items():
            np.testing.assert_allclose(beta.sum(axis=1), 1.0, atol=1e-5, err_msg=rotulo)

    def test_diferencas_para_e1_de_si_mesmo_sao_zero(self) -> None:
        """Se os fluxos por estado fossem o E1 da região, a diferença seria zero (aprox. de arredondamento)."""
        betas_e1 = nucleo.carregar_betas_e1(nucleo.CAMINHO_TRANSFERENCIAS_E1)
        betas_por_uf = np.zeros((27, 8, 4))
        for posicao_uf, regiao in enumerate(BASE_REAL.regiao_da_uf):
            betas_por_uf[posicao_uf] = betas_e1[regiao]
        votos = nucleo.calcular_votos_por_uf(betas_por_uf, BASE_REAL.populacao_por_uf)
        tabela = nucleo.calcular_diferencas_para_e1(BASE_REAL, votos, betas_e1)
        regioes = tabela[tabela["regiao"].isin(list(regional.REGIOES))]
        self.assertLess(float(regioes["diferenca_abs"].max()), 1e-5)


@unittest.skipUnless(CAMINHO_TRANSFERENCIAS_UF.is_file(), "transferencias_uf.csv ainda não gerado")
class TestSaidaGerada(unittest.TestCase):
    """Estrutura e consistência interna de `transferencias_uf.csv`."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tabela = pd.read_csv(CAMINHO_TRANSFERENCIAS_UF, sep=";", encoding="utf-8")

    def test_formato(self) -> None:
        self.assertEqual(self.tabela.shape[0], 2592)
        self.assertEqual(list(self.tabela.columns), list(saidas.COLUNAS_TRANSFERENCIAS))
        self.assertEqual(sorted(self.tabela["especificacao"].unique()), sorted(nucleo.CODIGOS_VERSOES))
        self.assertEqual(self.tabela["uf"].nunique(), 27)

    def test_beta_de_cada_linha_soma_um(self) -> None:
        soma = self.tabela.groupby(["especificacao", "uf", "origem_1t"])["beta"].sum()
        np.testing.assert_allclose(soma.to_numpy(), 1.0, atol=1e-5)

    def test_votos_somam_a_populacao_do_grupo(self) -> None:
        soma = self.tabela.groupby(["especificacao", "uf", "origem_1t"])["votos"].sum().reset_index()
        for _, linha in soma.iterrows():
            posicao_uf = BASE_REAL.lista_ufs.index(linha["uf"])
            posicao_origem = regional.ORIGENS_1T.index(linha["origem_1t"])
            esperado = BASE_REAL.populacao_por_uf[posicao_uf, posicao_origem]
            self.assertAlmostEqual(float(linha["votos"]), float(esperado), delta=0.5)

    def test_ic_so_na_versao_uf_e_ordenado(self) -> None:
        com_ic = self.tabela[self.tabela["especificacao"] == nucleo.CODIGO_UF]
        sem_ic = self.tabela[self.tabela["especificacao"] != nucleo.CODIGO_UF]
        self.assertTrue(com_ic["beta_ic_inf"].notna().all())
        self.assertTrue(sem_ic["beta_ic_inf"].isna().all())
        self.assertTrue(sem_ic["votos_ic_sup"].isna().all())
        self.assertTrue((com_ic["beta_ic_inf"] <= com_ic["beta_ic_sup"]).all())
        self.assertTrue((com_ic["votos_ic_inf"] <= com_ic["votos_ic_sup"]).all())

    def test_kappa_e_peso_da_regiao(self) -> None:
        linhas_regiao = self.tabela[self.tabela["especificacao"] == nucleo.CODIGO_UF_REGIAO]
        self.assertTrue((linhas_regiao["peso_regiao_pct"] == 100.0).all())
        linhas_uf = self.tabela[self.tabela["especificacao"] == nucleo.CODIGO_UF]
        kappa_estrela = float(linhas_uf["kappa"].iloc[0])
        esperado = 100.0 * kappa_estrela / (linhas_uf["n_efetivo"] + kappa_estrela)
        # O n efetivo do CSV tem 3 casas decimais; o arredondamento move o peso em até ~0,005 p.p.
        np.testing.assert_allclose(linhas_uf["peso_regiao_pct"].to_numpy(), esperado.to_numpy(), atol=1e-2)
        linhas_df = linhas_uf[linhas_uf["uf"] == "DF"]
        self.assertAlmostEqual(float(linhas_df["n_efetivo"].iloc[0]), 1.0, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
