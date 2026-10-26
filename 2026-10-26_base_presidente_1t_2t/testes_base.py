"""Testes mínimos das funções puras (e dos fluxos de arquivo com dublês) da base.

Cobre:
    * 01_coletar_json_2t.py: caminhos/URLs, validação de JSON, classificação de
      erro transitório, backoff, retentativas com cliente falso, idempotência.
    * 02_montar_base.py: normalização do código de município, mapa UF -> região
      (28 siglas), parse de um JSON de município, config, grade com zeros
      explícitos, anti-join, pivotagem e montagem da base.
    * 03_conciliar.py: parse de JSON, detecção de divergência de âncora e de
      violação de identidade contábil.

Os módulos são carregados pelo caminho do arquivo porque seus nomes começam
com dígito (não são importáveis com "import"). Nenhum teste acessa a rede nem
os dados reais.

Execução:
    python3 -I testes_base.py
"""

import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

import httpx
import pandas as pd

PASTA_TESTES = Path(__file__).resolve().parent

sys.dont_write_bytecode = True


def carregar_modulo(nome_modulo: str, nome_arquivo: str) -> ModuleType:
    """Carrega um script do projeto como módulo, a partir do caminho do arquivo.

    Args:
        nome_modulo: Nome a registrar em sys.modules.
        nome_arquivo: Arquivo dentro da pasta de testes.

    Returns:
        Módulo carregado (o bloco "__main__" do script não é executado).
    """
    caminho = PASTA_TESTES / nome_arquivo
    especificacao = importlib.util.spec_from_file_location(nome_modulo, caminho)
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[nome_modulo] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


COLETA = carregar_modulo("coleta_01", "01_coletar_json_2t.py")
MONTAGEM = carregar_modulo("montagem_02", "02_montar_base.py")
CONCILIACAO = carregar_modulo("conciliacao_03", "03_conciliar.py")

SIGLAS_ESPERADAS_28 = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO", "ZZ",
}


def montar_json_municipio_exemplo() -> dict:
    """Devolve um JSON de município reduzido, no formato do TSE (valores em texto).

    Valores de São Paulo (capital) no 2º turno: 3.097.923 + 3.864.354 = 6.962.277.
    Os nulos totais (tvn) são 216.904 = nulos (vn) + técnicos (vnt).
    """
    return {
        "ele": "6258",
        "t": "2",
        "tpabr": "mu",
        "cdabr": "71072",
        "tf": "s",
        "carg": [
            {
                "cd": "1",
                "nmn": "Presidente",
                "agr": [
                    {
                        "par": [
                            {
                                "sg": "PL",
                                "cand": [{"n": "22", "nmu": "FLAVIO BOLSONARO", "vap": "3097923"}],
                            }
                        ]
                    },
                    {
                        "par": [
                            {
                                "sg": "PT",
                                "cand": [{"n": "13", "nmu": "LULA", "vap": "3864354"}],
                            },
                            {"sg": "PSB"},
                        ]
                    },
                ],
            }
        ],
        "s": {"pst": "100,00"},
        "e": {"te": "9145969", "c": "7284071", "a": "1861898", "esni": "0"},
        "v": {
            "tv": "7284071",
            "vv": "6962277",
            "vb": "104890",
            "tvn": "216904",
            "vn": "200000",
            "vnt": "16904",
        },
    }


# --------------------------------------------------------------------------
# Dublês de cliente HTTP
# --------------------------------------------------------------------------


class RespostaFalsa:
    """Resposta HTTP mínima usada nos testes."""

    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class ClienteFalso:
    """Cliente HTTP que devolve, em ordem, respostas ou exceções programadas."""

    def __init__(self, desfechos: list) -> None:
        self.desfechos = list(desfechos)
        self.urls_chamadas: list[str] = []

    def get(self, url: str) -> RespostaFalsa:
        self.urls_chamadas.append(url)
        desfecho = self.desfechos.pop(0)
        if isinstance(desfecho, Exception):
            raise desfecho
        return desfecho


# --------------------------------------------------------------------------
# Script 01
# --------------------------------------------------------------------------


class TestesColetaCaminhos(unittest.TestCase):
    """Caminhos, URLs e validação de entradas externas."""

    def test_caminho_relativo_nacional_uf_e_municipio(self) -> None:
        self.assertEqual(
            COLETA.montar_caminho_relativo_dados("br", None),
            "dados/br/br-c0001-e006258-u.json",
        )
        self.assertEqual(
            COLETA.montar_caminho_relativo_dados("sp", None),
            "dados/sp/sp-c0001-e006258-u.json",
        )
        self.assertEqual(
            COLETA.montar_caminho_relativo_dados("sp", "71072"),
            "dados/sp/sp71072-c0001-e006258-u.json",
        )
        self.assertEqual(
            COLETA.montar_caminho_relativo_dados("zz", "01120"),
            "dados/zz/zz01120-c0001-e006258-u.json",
        )

    def test_rejeita_sigla_e_codigo_inseguros(self) -> None:
        sigla_invalida = ["../", "SP", "s", "spp", "s1", ""]
        for sigla in sigla_invalida:
            with self.assertRaises(COLETA.ConteudoInvalidoError):
                COLETA.montar_caminho_relativo_dados(sigla, None)

        codigos_invalidos = ["1007", "abcde", "../../", "123456", ""]
        for codigo in codigos_invalidos:
            with self.assertRaises(COLETA.ConteudoInvalidoError):
                COLETA.montar_caminho_relativo_dados("sp", codigo)

    def test_tarefas_espelham_url_no_disco(self) -> None:
        config = {
            "abr": [
                {"cd": "ac", "mu": [{"cd": "01120"}]},
                {"cd": "zz", "mu": [{"cd": "29254"}]},
            ]
        }
        tarefas = COLETA.montar_tarefas(config)

        self.assertEqual(len(tarefas), 5)
        tarefa_municipio = tarefas[3]
        self.assertEqual(tarefa_municipio.tipo_abrangencia, "mu")
        self.assertEqual(
            tarefa_municipio.url,
            "https://resultados.tse.jus.br/oficial/ele2026/6258/dados/ac/ac01120-c0001-e006258-u.json",
        )
        caminho_esperado = COLETA.PASTA_DESTINO / "dados" / "ac" / "ac01120-c0001-e006258-u.json"
        self.assertEqual(tarefa_municipio.caminho_destino, caminho_esperado)

    def test_config_com_municipio_repetido_e_rejeitado(self) -> None:
        config = {"abr": [{"cd": "ac", "mu": [{"cd": "01120"}, {"cd": "01120"}]}]}
        with self.assertRaises(COLETA.ConteudoInvalidoError):
            COLETA.extrair_municipios_do_config(config)


class TestesColetaValidacao(unittest.TestCase):
    """Validação do conteúdo JSON baixado."""

    def test_resultado_valido_passa(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        COLETA.validar_conteudo_apuracao(conteudo, "mu", "71072")

    def test_resultado_de_outro_municipio_e_rejeitado(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        with self.assertRaises(COLETA.ConteudoInvalidoError):
            COLETA.validar_conteudo_apuracao(conteudo, "mu", "71073")

    def test_turno_ou_eleicao_errados_sao_rejeitados(self) -> None:
        conteudo_turno_1 = montar_json_municipio_exemplo()
        conteudo_turno_1["t"] = "1"
        with self.assertRaises(COLETA.ConteudoInvalidoError):
            COLETA.validar_conteudo_apuracao(conteudo_turno_1, "mu", "71072")

        conteudo_outra_eleicao = montar_json_municipio_exemplo()
        conteudo_outra_eleicao["ele"] = "6257"
        with self.assertRaises(COLETA.ConteudoInvalidoError):
            COLETA.validar_conteudo_apuracao(conteudo_outra_eleicao, "mu", "71072")

    def test_campo_obrigatorio_ausente_e_rejeitado(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        del conteudo["v"]
        with self.assertRaises(COLETA.ConteudoInvalidoError):
            COLETA.validar_conteudo_apuracao(conteudo, "mu", "71072")

    def test_objeto_que_nao_e_dicionario_e_rejeitado(self) -> None:
        with self.assertRaises(COLETA.ConteudoInvalidoError):
            COLETA.validar_conteudo_apuracao([1, 2], "mu", "71072")

    def test_totalizacao_final(self) -> None:
        self.assertTrue(COLETA.totalizacao_esta_final({"tf": "s"}))
        self.assertFalse(COLETA.totalizacao_esta_final({"tf": "n"}))
        self.assertFalse(COLETA.totalizacao_esta_final({}))


class TestesColetaRede(unittest.TestCase):
    """Classificação de erro, backoff e retentativas (sem rede)."""

    def test_codigos_http_transitorios(self) -> None:
        for codigo in (500, 502, 503, 504, 429):
            self.assertTrue(COLETA.codigo_http_e_transitorio(codigo), codigo)
        for codigo in (200, 301, 400, 403, 404):
            self.assertFalse(COLETA.codigo_http_e_transitorio(codigo), codigo)

    def test_backoff_exponencial_sem_jitter(self) -> None:
        esperas = []
        for tentativa in (1, 2, 3, 4):
            esperas.append(COLETA.calcular_espera_backoff(tentativa, 0.0))
        self.assertEqual(esperas, [1.0, 2.0, 4.0, 8.0])
        self.assertEqual(COLETA.calcular_espera_backoff(1, 0.25), 1.25)

    def test_retenta_apos_5xx_e_timeout_e_depois_sucesso(self) -> None:
        cliente = ClienteFalso(
            [
                RespostaFalsa(503),
                httpx.ReadTimeout("timeout simulado"),
                RespostaFalsa(200, b"{}"),
            ]
        )
        with mock.patch.object(COLETA.time, "sleep") as sono_falso:
            corpo, tentativas = COLETA.baixar_com_retentativas(cliente, "http://exemplo/a.json")

        self.assertEqual(corpo, b"{}")
        self.assertEqual(tentativas, 3)
        self.assertEqual(sono_falso.call_count, 2)

    def test_404_falha_na_primeira_tentativa_sem_retentar(self) -> None:
        cliente = ClienteFalso([RespostaFalsa(404)])
        with mock.patch.object(COLETA.time, "sleep") as sono_falso:
            with self.assertRaises(COLETA.FalhaDownloadError) as contexto:
                COLETA.baixar_com_retentativas(cliente, "http://exemplo/a.json")

        self.assertEqual(contexto.exception.tentativas, 1)
        self.assertEqual(len(cliente.urls_chamadas), 1)
        sono_falso.assert_not_called()

    def test_esgota_tentativas_em_timeout_persistente(self) -> None:
        desfechos = []
        for _ in range(COLETA.MAXIMO_TENTATIVAS):
            desfechos.append(httpx.ConnectTimeout("timeout simulado"))
        cliente = ClienteFalso(desfechos)

        with mock.patch.object(COLETA.time, "sleep"):
            with self.assertRaises(COLETA.FalhaDownloadError) as contexto:
                COLETA.baixar_com_retentativas(cliente, "http://exemplo/a.json")

        self.assertEqual(contexto.exception.tentativas, COLETA.MAXIMO_TENTATIVAS)
        self.assertEqual(len(cliente.urls_chamadas), COLETA.MAXIMO_TENTATIVAS)


class TestesColetaArquivos(unittest.TestCase):
    """Idempotência e gravação atômica, em pasta temporária."""

    def criar_tarefa_em(self, pasta: Path) -> object:
        return COLETA.TarefaDownload(
            tipo_abrangencia="mu",
            codigo_abrangencia="71072",
            url="http://exemplo/sp71072.json",
            caminho_destino=pasta / "dados" / "sp" / "sp71072-c0001-e006258-u.json",
        )

    def test_baixa_valida_grava_e_depois_pula(self) -> None:
        corpo_valido = json_para_bytes(montar_json_municipio_exemplo())

        with tempfile.TemporaryDirectory() as pasta_temporaria:
            tarefa = self.criar_tarefa_em(Path(pasta_temporaria))

            cliente_primeira = ClienteFalso([RespostaFalsa(200, corpo_valido)])
            primeiro = COLETA.processar_tarefa(cliente_primeira, tarefa)
            self.assertEqual(primeiro.situacao, COLETA.SituacaoDownload.BAIXADO)
            self.assertTrue(tarefa.caminho_destino.is_file())

            cliente_segunda = ClienteFalso([])
            segundo = COLETA.processar_tarefa(cliente_segunda, tarefa)
            self.assertEqual(segundo.situacao, COLETA.SituacaoDownload.PULADO)
            self.assertEqual(cliente_segunda.urls_chamadas, [])

    def test_arquivo_local_corrompido_ou_parcial_e_baixado_de_novo(self) -> None:
        corpo_valido = json_para_bytes(montar_json_municipio_exemplo())

        with tempfile.TemporaryDirectory() as pasta_temporaria:
            tarefa = self.criar_tarefa_em(Path(pasta_temporaria))
            tarefa.caminho_destino.parent.mkdir(parents=True)

            tarefa.caminho_destino.write_bytes(b'{"ele": "6258", ')
            self.assertFalse(COLETA.arquivo_local_esta_completo(tarefa))

            conteudo_parcial = montar_json_municipio_exemplo()
            conteudo_parcial["tf"] = "n"
            tarefa.caminho_destino.write_bytes(json_para_bytes(conteudo_parcial))
            self.assertFalse(COLETA.arquivo_local_esta_completo(tarefa))

            tarefa.caminho_destino.write_bytes(corpo_valido)
            self.assertTrue(COLETA.arquivo_local_esta_completo(tarefa))

    def test_conteudo_invalido_vira_falha_e_nao_grava(self) -> None:
        with tempfile.TemporaryDirectory() as pasta_temporaria:
            tarefa = self.criar_tarefa_em(Path(pasta_temporaria))
            cliente = ClienteFalso([RespostaFalsa(200, b"<html>erro</html>")])

            resultado = COLETA.processar_tarefa(cliente, tarefa)

            self.assertEqual(resultado.situacao, COLETA.SituacaoDownload.FALHOU)
            self.assertFalse(tarefa.caminho_destino.exists())

    def test_404_vira_falha_explicita(self) -> None:
        with tempfile.TemporaryDirectory() as pasta_temporaria:
            tarefa = self.criar_tarefa_em(Path(pasta_temporaria))
            cliente = ClienteFalso([RespostaFalsa(404)])

            resultado = COLETA.processar_tarefa(cliente, tarefa)

            self.assertEqual(resultado.situacao, COLETA.SituacaoDownload.FALHOU)
            self.assertIn("404", resultado.mensagem_erro)


def json_para_bytes(conteudo: dict) -> bytes:
    """Serializa um dicionário em JSON UTF-8 (usado para simular respostas)."""
    import json

    return json.dumps(conteudo).encode("utf-8")


# --------------------------------------------------------------------------
# Script 02
# --------------------------------------------------------------------------


class TestesNormalizacaoCodigo(unittest.TestCase):
    """Normalização do código TSE de município para 5 dígitos."""

    def test_completa_zeros_a_esquerda(self) -> None:
        self.assertEqual(MONTAGEM.normalizar_codigo_municipio("1007"), "01007")
        self.assertEqual(MONTAGEM.normalizar_codigo_municipio("7"), "00007")

    def test_mantem_codigo_ja_normalizado(self) -> None:
        self.assertEqual(MONTAGEM.normalizar_codigo_municipio("01007"), "01007")
        self.assertEqual(MONTAGEM.normalizar_codigo_municipio("21539"), "21539")

    def test_ignora_espacos_nas_pontas(self) -> None:
        self.assertEqual(MONTAGEM.normalizar_codigo_municipio(" 1007 "), "01007")

    def test_formatos_equivalentes_dao_a_mesma_chave(self) -> None:
        com_aspas = MONTAGEM.normalizar_codigo_municipio("01007")
        sem_aspas = MONTAGEM.normalizar_codigo_municipio("1007")
        self.assertEqual(com_aspas, sem_aspas)

    def test_rejeita_valores_invalidos(self) -> None:
        for valor in ("", "   ", "abc", "1007.0", "-1007", "123456", "01 007"):
            with self.assertRaises(ValueError, msg=repr(valor)):
                MONTAGEM.normalizar_codigo_municipio(valor)


class TestesRegiao(unittest.TestCase):
    """Mapa UF -> região cobrindo as 28 siglas."""

    def test_cobre_exatamente_as_28_siglas(self) -> None:
        self.assertEqual(set(MONTAGEM.REGIAO_POR_UF.keys()), SIGLAS_ESPERADAS_28)
        self.assertEqual(len(MONTAGEM.REGIAO_POR_UF), 28)

    def test_regiao_de_cada_sigla(self) -> None:
        esperado = {
            "Norte": {"AC", "AP", "AM", "PA", "RO", "RR", "TO"},
            "Nordeste": {"AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"},
            "Centro-Oeste": {"DF", "GO", "MT", "MS"},
            "Sudeste": {"ES", "MG", "RJ", "SP"},
            "Sul": {"PR", "RS", "SC"},
            "Exterior": {"ZZ"},
        }
        for regiao, siglas in esperado.items():
            for sigla in siglas:
                self.assertEqual(MONTAGEM.obter_regiao_da_uf(sigla), regiao, sigla)

    def test_sigla_desconhecida_ou_minuscula_levanta_erro(self) -> None:
        for sigla in ("XX", "sp", "", "BR"):
            with self.assertRaises(ValueError, msg=repr(sigla)):
                MONTAGEM.obter_regiao_da_uf(sigla)


class TestesConversaoInteiro(unittest.TestCase):
    """Conversão rígida de números em texto do JSON."""

    def test_aceita_somente_digitos(self) -> None:
        self.assertEqual(MONTAGEM.converter_para_inteiro("7284071", "c"), 7284071)
        self.assertEqual(MONTAGEM.converter_para_inteiro("0", "c"), 0)
        self.assertEqual(MONTAGEM.converter_para_inteiro(" 12 ", "c"), 12)

    def test_rejeita_formatos_estranhos(self) -> None:
        for valor in ("", "1,5", "-1", "1.000", "1e3", "abc"):
            with self.assertRaises(ValueError, msg=repr(valor)):
                MONTAGEM.converter_para_inteiro(valor, "campo")

    def test_rejeita_nao_texto(self) -> None:
        with self.assertRaises(ValueError):
            MONTAGEM.converter_para_inteiro(10, "campo")


class TestesParseJsonMunicipio(unittest.TestCase):
    """Parse de um JSON de município a partir de um dicionário pequeno."""

    def test_extrai_metricas_e_candidatos(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        apuracao = MONTAGEM.extrair_apuracao_municipio(conteudo)

        self.assertEqual(apuracao.totalizacao_final, "s")
        self.assertEqual(apuracao.percentual_secoes_apuradas, "100,00")
        self.assertEqual(apuracao.aptos, 9145969)
        self.assertEqual(apuracao.comparecimento, 7284071)
        self.assertEqual(apuracao.abstencao, 1861898)
        self.assertEqual(apuracao.nao_instaladas, 0)
        self.assertEqual(apuracao.validos, 6962277)
        self.assertEqual(apuracao.brancos, 104890)

    def test_nulos_usa_total_de_nulos_que_inclui_tecnicos(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        apuracao = MONTAGEM.extrair_apuracao_municipio(conteudo)

        # tvn = 216.904 = vn (200.000) + vnt (16.904): a base usa o total.
        self.assertEqual(apuracao.nulos, 216904)

    def test_candidatos_com_numero_nome_partido_e_votos(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        apuracao = MONTAGEM.extrair_apuracao_municipio(conteudo)

        por_numero = {}
        for candidato in apuracao.candidatos:
            por_numero[candidato.numero_candidato] = candidato

        self.assertEqual(set(por_numero.keys()), {13, 22})
        self.assertEqual(por_numero[22].votos, 3097923)
        self.assertEqual(por_numero[22].sigla_partido, "PL")
        self.assertEqual(por_numero[22].nome_urna, "FLAVIO BOLSONARO")
        self.assertEqual(por_numero[13].votos, 3864354)
        self.assertEqual(por_numero[13].sigla_partido, "PT")

    def test_identidades_do_exemplo(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        apuracao = MONTAGEM.extrair_apuracao_municipio(conteudo)

        soma_votos_candidatos = 0
        for candidato in apuracao.candidatos:
            soma_votos_candidatos += candidato.votos

        self.assertEqual(soma_votos_candidatos, apuracao.validos)
        self.assertEqual(
            apuracao.comparecimento,
            apuracao.validos + apuracao.brancos + apuracao.nulos,
        )
        self.assertEqual(
            apuracao.aptos,
            apuracao.comparecimento + apuracao.abstencao + apuracao.nao_instaladas,
        )

    def test_candidato_repetido_e_rejeitado(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        agrupamentos = conteudo["carg"][0]["agr"]
        agrupamentos[1]["par"][0]["cand"].append(copy.deepcopy(agrupamentos[0]["par"][0]["cand"][0]))
        with self.assertRaises(ValueError):
            MONTAGEM.extrair_apuracao_municipio(conteudo)

    def test_campo_ausente_levanta_keyerror(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        del conteudo["e"]["esni"]
        with self.assertRaises(KeyError):
            MONTAGEM.extrair_apuracao_municipio(conteudo)

    def test_numero_nao_inteiro_levanta_valueerror(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        conteudo["v"]["vv"] = "6.962.277"
        with self.assertRaises(ValueError):
            MONTAGEM.extrair_apuracao_municipio(conteudo)

    def test_mais_de_um_cargo_ou_cargo_errado_levanta_valueerror(self) -> None:
        dois_cargos = montar_json_municipio_exemplo()
        dois_cargos["carg"].append(copy.deepcopy(dois_cargos["carg"][0]))
        with self.assertRaises(ValueError):
            MONTAGEM.extrair_apuracao_municipio(dois_cargos)

        cargo_errado = montar_json_municipio_exemplo()
        cargo_errado["carg"][0]["cd"] = "3"
        with self.assertRaises(ValueError):
            MONTAGEM.extrair_apuracao_municipio(cargo_errado)

    def test_identificacao_do_json(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        MONTAGEM.validar_identificacao_json(conteudo, "SP", "71072")

        with self.assertRaises(ValueError):
            MONTAGEM.validar_identificacao_json(conteudo, "SP", "71073")

        turno_1 = montar_json_municipio_exemplo()
        turno_1["t"] = "1"
        with self.assertRaises(ValueError):
            MONTAGEM.validar_identificacao_json(turno_1, "SP", "71072")


class TestesConfigMunicipios(unittest.TestCase):
    """Conversão do config do TSE na espinha de municípios."""

    def montar_config(self) -> dict:
        return {
            "abr": [
                {"cd": "ac", "mu": [{"cd": "01120", "cdi": "1200013", "nm": "ACRELÂNDIA"}]},
                {"cd": "zz", "mu": [{"cd": "29254", "cdi": "", "nm": "ABIDJÃ"}]},
            ]
        }

    def test_uf_em_maiusculas_e_ibge_nulo_no_exterior(self) -> None:
        municipios = MONTAGEM.converter_config_em_municipios(self.montar_config())

        self.assertEqual(len(municipios), 2)
        self.assertEqual(municipios[0].sg_uf, "AC")
        self.assertEqual(municipios[0].cd_municipio_tse, "01120")
        self.assertEqual(municipios[0].cd_municipio_ibge, "1200013")
        self.assertEqual(municipios[1].sg_uf, "ZZ")
        self.assertIsNone(municipios[1].cd_municipio_ibge)

    def test_ibge_invalido_e_rejeitado(self) -> None:
        config = self.montar_config()
        config["abr"][0]["mu"][0]["cdi"] = "12000"
        with self.assertRaises(ValueError):
            MONTAGEM.converter_config_em_municipios(config)

    def test_municipio_repetido_e_rejeitado(self) -> None:
        config = self.montar_config()
        config["abr"][0]["mu"].append(copy.deepcopy(config["abr"][0]["mu"][0]))
        with self.assertRaises(ValueError):
            MONTAGEM.converter_config_em_municipios(config)

    def test_espinha_tem_regiao_e_flag_de_exterior(self) -> None:
        municipios = MONTAGEM.converter_config_em_municipios(self.montar_config())
        espinha = MONTAGEM.montar_tabela_municipios_config(municipios)

        self.assertEqual(list(espinha.columns), MONTAGEM.COLUNAS_IDENTIFICACAO)
        linha_acre = espinha[espinha["sg_uf"] == "AC"].iloc[0]
        linha_exterior = espinha[espinha["sg_uf"] == "ZZ"].iloc[0]
        self.assertEqual(linha_acre["nm_regiao"], "Norte")
        self.assertFalse(linha_acre["fl_exterior"])
        self.assertEqual(linha_exterior["nm_regiao"], "Exterior")
        self.assertTrue(linha_exterior["fl_exterior"])


def montar_chaves(pares: list[tuple[str, str]]) -> pd.DataFrame:
    """Cria uma tabela de chaves (sg_uf, cd_municipio_tse) a partir de pares."""
    return pd.DataFrame(pares, columns=["sg_uf", "cd_municipio_tse"])


class TestesGradeDeVotos(unittest.TestCase):
    """Zero explícito para município sem voto de um candidato."""

    def test_preenche_zero_e_conta_celulas_preenchidas(self) -> None:
        chaves = montar_chaves([("AC", "01007"), ("AC", "01015")])
        observados = pd.DataFrame(
            {
                "sg_uf": ["AC", "AC", "AC"],
                "cd_municipio_tse": ["01007", "01007", "01015"],
                "nr_candidato": [13, 22, 13],
                "votos": [10, 20, 5],
            }
        )

        completo, preenchidas = MONTAGEM.completar_grade_de_votos(observados, chaves, (13, 22))

        self.assertEqual(len(completo), 4)
        self.assertEqual(preenchidas, 1)
        self.assertEqual(str(completo["votos"].dtype), "int64")

        mascara = (completo["cd_municipio_tse"] == "01015") & (completo["nr_candidato"] == 22)
        self.assertEqual(int(completo.loc[mascara, "votos"].iloc[0]), MONTAGEM.VOTOS_CANDIDATO_AUSENTE)
        self.assertEqual(int(completo["votos"].sum()), 35)

    def test_candidato_fora_do_esperado_e_rejeitado(self) -> None:
        chaves = montar_chaves([("AC", "01007")])
        observados = pd.DataFrame(
            {"sg_uf": ["AC"], "cd_municipio_tse": ["01007"], "nr_candidato": [99], "votos": [1]}
        )
        with self.assertRaises(ValueError):
            MONTAGEM.completar_grade_de_votos(observados, chaves, (13, 22))

    def test_municipio_fora_da_lista_de_chaves_e_rejeitado(self) -> None:
        chaves = montar_chaves([("AC", "01007")])
        observados = pd.DataFrame(
            {"sg_uf": ["AC"], "cd_municipio_tse": ["99999"], "nr_candidato": [13], "votos": [1]}
        )
        with self.assertRaises(ValueError):
            MONTAGEM.completar_grade_de_votos(observados, chaves, (13, 22))

    def test_linha_duplicada_e_rejeitada(self) -> None:
        chaves = montar_chaves([("AC", "01007")])
        observados = pd.DataFrame(
            {
                "sg_uf": ["AC", "AC"],
                "cd_municipio_tse": ["01007", "01007"],
                "nr_candidato": [13, 13],
                "votos": [1, 2],
            }
        )
        with self.assertRaises(ValueError):
            MONTAGEM.completar_grade_de_votos(observados, chaves, (13, 22))

    def test_sem_nenhum_voto_observado_tudo_zero(self) -> None:
        chaves = montar_chaves([("AC", "01007")])
        observados = pd.DataFrame(
            {
                "sg_uf": pd.Series([], dtype="str"),
                "cd_municipio_tse": pd.Series([], dtype="str"),
                "nr_candidato": pd.Series([], dtype="int64"),
                "votos": pd.Series([], dtype="int64"),
            }
        )
        completo, preenchidas = MONTAGEM.completar_grade_de_votos(observados, chaves, (13, 22))
        self.assertEqual(preenchidas, 2)
        self.assertEqual(int(completo["votos"].sum()), 0)


class TestesAntiJoin(unittest.TestCase):
    """Anti-join nos dois sentidos entre as chaves dos turnos."""

    def test_sem_orfaos(self) -> None:
        chaves_1t = montar_chaves([("AC", "01007"), ("SP", "71072")])
        chaves_2t = montar_chaves([("SP", "71072"), ("AC", "01007")])
        somente_1t, somente_2t = MONTAGEM.comparar_chaves_entre_turnos(chaves_1t, chaves_2t)
        self.assertTrue(somente_1t.empty)
        self.assertTrue(somente_2t.empty)

    def test_detecta_orfao_em_cada_sentido(self) -> None:
        chaves_1t = montar_chaves([("AC", "01007"), ("AC", "01015")])
        chaves_2t = montar_chaves([("AC", "01007"), ("SP", "71072")])
        somente_1t, somente_2t = MONTAGEM.comparar_chaves_entre_turnos(chaves_1t, chaves_2t)

        self.assertEqual(somente_1t.to_dict("records"), [{"sg_uf": "AC", "cd_municipio_tse": "01015"}])
        self.assertEqual(somente_2t.to_dict("records"), [{"sg_uf": "SP", "cd_municipio_tse": "71072"}])

    def test_codigo_sem_normalizar_gera_orfao_nos_dois_lados(self) -> None:
        # Demonstra o risco que a normalização evita: "1007" != "01007".
        chaves_1t = montar_chaves([("AC", "1007")])
        chaves_2t = montar_chaves([("AC", "01007")])
        somente_1t, somente_2t = MONTAGEM.comparar_chaves_entre_turnos(chaves_1t, chaves_2t)
        self.assertEqual(len(somente_1t), 1)
        self.assertEqual(len(somente_2t), 1)

    def test_aborta_se_houver_orfaos(self) -> None:
        orfao = montar_chaves([("AC", "01015")])
        vazio = montar_chaves([])
        with tempfile.TemporaryDirectory() as pasta_temporaria:
            caminho_orfaos = Path(pasta_temporaria) / "orfaos.csv"
            with mock.patch.object(MONTAGEM, "CAMINHO_ORFAOS", caminho_orfaos):
                with self.assertRaises(MONTAGEM.ChavesOrfasError):
                    MONTAGEM.abortar_se_houver_orfaos(orfao, vazio)
                self.assertTrue(caminho_orfaos.is_file())

                MONTAGEM.abortar_se_houver_orfaos(vazio, vazio)


class TestesAgregacaoPrimeiroTurno(unittest.TestCase):
    """Soma de zonas, normalização de código e validações do CSV do 1º turno."""

    def montar_detalhe_bruto(self) -> pd.DataFrame:
        linhas = [
            # Mesmo município com código em dois formatos e duas zonas; ST S e N somam juntos.
            ["AC", "1007", "9", "N", "1", "Presidente", "100", "80", "20", "0", "70", "5", "5"],
            ["AC", "01007", "10", "N", "1", "Presidente", "50", "40", "10", "0", "35", "2", "3"],
            ["AC", "01007", "10", "S", "1", "Presidente", "0", "3", "0", "0", "3", "0", "0"],
            ["SP", "71072", "1", "N", "1", "Presidente", "7", "6", "1", "0", "6", "0", "0"],
        ]
        colunas = [
            "SG_UF",
            "CD_MUNICIPIO",
            "NR_ZONA",
            "ST_VOTO_EM_TRANSITO",
            "NR_TURNO",
            "DS_CARGO",
            "QT_APTOS",
            "QT_COMPARECIMENTO",
            "QT_ABSTENCOES",
            "QT_ELEITORES_SECOES_NAO_INSTALADAS",
            "QT_TOTAL_VOTOS_VALIDOS",
            "QT_VOTOS_BRANCOS",
            "QT_TOTAL_VOTOS_NULOS",
        ]
        return pd.DataFrame(linhas, columns=colunas)

    def test_soma_zonas_e_junta_formatos_de_codigo(self) -> None:
        detalhe_bruto = self.montar_detalhe_bruto()
        colunas_numericas = list(MONTAGEM.METRICA_POR_COLUNA_DETALHE_1T.keys())
        preparado = MONTAGEM.preparar_tabela_1t(
            detalhe_bruto,
            colunas_numericas,
            MONTAGEM.COLUNAS_CHAVE_ZONA_DETALHE_1T,
            "detalhe de teste",
        )
        metricas = MONTAGEM.agregar_metricas_1t(preparado)

        self.assertEqual(len(metricas), 2)
        linha_acre = metricas[metricas["cd_municipio_tse"] == "01007"].iloc[0]
        self.assertEqual(int(linha_acre["aptos_1t"]), 150)
        self.assertEqual(int(linha_acre["comparecimento_1t"]), 123)
        self.assertEqual(int(linha_acre["validos_1t"]), 108)
        self.assertEqual(str(metricas["aptos_1t"].dtype), "int64")

    def test_voto_em_transito_ou_turno_inesperado_e_rejeitado(self) -> None:
        colunas_numericas = list(MONTAGEM.METRICA_POR_COLUNA_DETALHE_1T.keys())

        com_transito_invalido = self.montar_detalhe_bruto()
        com_transito_invalido.loc[0, "ST_VOTO_EM_TRANSITO"] = "X"
        with self.assertRaises(ValueError):
            MONTAGEM.preparar_tabela_1t(
                com_transito_invalido,
                colunas_numericas,
                MONTAGEM.COLUNAS_CHAVE_ZONA_DETALHE_1T,
                "teste",
            )

        com_turno_2 = self.montar_detalhe_bruto()
        com_turno_2.loc[0, "NR_TURNO"] = "2"
        with self.assertRaises(ValueError):
            MONTAGEM.preparar_tabela_1t(
                com_turno_2,
                colunas_numericas,
                MONTAGEM.COLUNAS_CHAVE_ZONA_DETALHE_1T,
                "teste",
            )

    def test_numero_negativo_ou_decimal_e_rejeitado(self) -> None:
        tabela = pd.DataFrame({"valor": ["1", "-2"]})
        with self.assertRaises(ValueError):
            MONTAGEM.converter_colunas_para_inteiro(tabela, ["valor"])

        tabela_decimal = pd.DataFrame({"valor": ["1", "2.5"]})
        with self.assertRaises(ValueError):
            MONTAGEM.converter_colunas_para_inteiro(tabela_decimal, ["valor"])

    def test_chave_duplicada_na_zona_e_rejeitada(self) -> None:
        detalhe_bruto = self.montar_detalhe_bruto()
        duplicada = pd.concat([detalhe_bruto, detalhe_bruto.iloc[[0]]], ignore_index=True)
        colunas_numericas = list(MONTAGEM.METRICA_POR_COLUNA_DETALHE_1T.keys())
        with self.assertRaises(ValueError):
            MONTAGEM.preparar_tabela_1t(
                duplicada,
                colunas_numericas,
                MONTAGEM.COLUNAS_CHAVE_ZONA_DETALHE_1T,
                "teste",
            )


class TestesMontagemDaBase(unittest.TestCase):
    """Pivotagem e junção final."""

    def montar_votos_completos(self, numeros: tuple[int, ...]) -> pd.DataFrame:
        linhas = []
        for chave in (("AC", "01007"), ("SP", "71072")):
            for numero in numeros:
                linhas.append([chave[0], chave[1], numero, numero * 10])
        return pd.DataFrame(linhas, columns=["sg_uf", "cd_municipio_tse", "nr_candidato", "votos"])

    def test_pivotagem_ordem_nome_e_tipo_das_colunas(self) -> None:
        votos = self.montar_votos_completos((22, 13))
        colunas = MONTAGEM.pivotar_votos_para_colunas(votos, "2t", (13, 22))

        self.assertEqual(list(colunas.columns), ["sg_uf", "cd_municipio_tse", "votos_2t_13", "votos_2t_22"])
        self.assertEqual(str(colunas["votos_2t_13"].dtype), "int64")
        self.assertEqual(int(colunas["votos_2t_13"].iloc[0]), 130)
        self.assertEqual(int(colunas["votos_2t_22"].iloc[0]), 220)

    def test_ordem_das_colunas_finais(self) -> None:
        ordem = MONTAGEM.montar_ordem_colunas_base()
        self.assertEqual(len(ordem), 34)
        self.assertEqual(len(set(ordem)), 34)
        self.assertEqual(ordem[:6], MONTAGEM.COLUNAS_IDENTIFICACAO)
        self.assertEqual(ordem[6], "aptos_1t")
        self.assertIn("votos_1t_80", ordem)
        self.assertEqual(ordem[-2:], ["votos_2t_13", "votos_2t_22"])

    def montar_tabelas_de_um_turno(self, rotulo: str, numeros: tuple[int, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
        linhas_metricas = []
        for chave in (("AC", "01007"), ("SP", "71072")):
            linha = {"sg_uf": chave[0], "cd_municipio_tse": chave[1]}
            for metrica in MONTAGEM.METRICAS_DO_TURNO:
                linha[f"{metrica}_{rotulo}"] = 1
            linhas_metricas.append(linha)
        metricas = pd.DataFrame(linhas_metricas)
        votos = MONTAGEM.pivotar_votos_para_colunas(self.montar_votos_completos(numeros), rotulo, numeros)
        return metricas, votos

    def montar_espinha(self) -> pd.DataFrame:
        municipios = [
            MONTAGEM.MunicipioConfig("AC", "01007", "1200138", "BUJARI"),
            MONTAGEM.MunicipioConfig("SP", "71072", "3550308", "SÃO PAULO"),
        ]
        return MONTAGEM.montar_tabela_municipios_config(municipios)

    def test_base_final_tem_colunas_ordenadas_e_inteiros(self) -> None:
        metricas_1t, votos_1t = self.montar_tabelas_de_um_turno("1t", MONTAGEM.NUMEROS_CANDIDATOS_1T)
        metricas_2t, votos_2t = self.montar_tabelas_de_um_turno("2t", MONTAGEM.NUMEROS_CANDIDATOS_2T)

        base = MONTAGEM.montar_base_por_municipio(
            self.montar_espinha(),
            metricas_1t,
            votos_1t,
            metricas_2t,
            votos_2t,
        )

        self.assertEqual(list(base.columns), MONTAGEM.montar_ordem_colunas_base())
        self.assertEqual(len(base), 2)
        colunas_numericas = [coluna for coluna in base.columns if coluna not in MONTAGEM.COLUNAS_IDENTIFICACAO]
        for coluna in colunas_numericas:
            self.assertEqual(str(base[coluna].dtype), "int64", coluna)
        self.assertFalse(base[colunas_numericas].isna().any().any())

    def test_municipio_faltando_em_um_turno_e_erro_e_nao_nulo(self) -> None:
        metricas_1t, votos_1t = self.montar_tabelas_de_um_turno("1t", MONTAGEM.NUMEROS_CANDIDATOS_1T)
        metricas_2t, votos_2t = self.montar_tabelas_de_um_turno("2t", MONTAGEM.NUMEROS_CANDIDATOS_2T)
        metricas_2t_incompleta = metricas_2t.iloc[[0]]

        with self.assertRaises(ValueError):
            MONTAGEM.montar_base_por_municipio(
                self.montar_espinha(),
                metricas_1t,
                votos_1t,
                metricas_2t_incompleta,
                votos_2t,
            )

    def test_tabelas_do_2t_a_partir_das_apuracoes(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        apuracao = MONTAGEM.extrair_apuracao_municipio(conteudo)
        apuracoes = {("SP", "71072"): apuracao}

        metricas, votos, catalogo = MONTAGEM.montar_tabelas_2t(apuracoes)

        self.assertEqual(int(metricas["aptos_2t"].iloc[0]), 9145969)
        self.assertEqual(int(metricas["nulos_2t"].iloc[0]), 216904)
        self.assertEqual(sorted(votos["nr_candidato"].tolist()), [13, 22])
        self.assertEqual(set(catalogo["nr_candidato"]), {13, 22})

    def test_candidato_inesperado_no_2t_e_rejeitado(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        conteudo["carg"][0]["agr"][0]["par"][0]["cand"][0]["n"] = "99"
        apuracao = MONTAGEM.extrair_apuracao_municipio(conteudo)
        with self.assertRaises(ValueError):
            MONTAGEM.montar_tabelas_2t({("SP", "71072"): apuracao})


# --------------------------------------------------------------------------
# Script 03
# --------------------------------------------------------------------------


def montar_base_com_valores_das_ancoras() -> pd.DataFrame:
    """Cria uma base mínima (2 linhas) cujas somas reproduzem exatamente as âncoras."""
    exterior = CONCILIACAO.ANCORAS_1T_EXTERIOR
    linha_brasil: dict = {"sg_uf": "SP", "nm_municipio": "BRASIL"}
    linha_exterior: dict = {"sg_uf": "ZZ", "nm_municipio": "EXTERIOR"}

    for numero, total in CONCILIACAO.ANCORAS_1T_VOTOS_POR_CANDIDATO.items():
        linha_brasil[f"votos_1t_{numero}"] = total
        linha_exterior[f"votos_1t_{numero}"] = 0

    for metrica, total in CONCILIACAO.ANCORAS_1T_METRICAS.items():
        valor_exterior = exterior.get(metrica, 0)
        linha_brasil[f"{metrica}_1t"] = total - valor_exterior
        linha_exterior[f"{metrica}_1t"] = valor_exterior

    for numero, total in CONCILIACAO.ANCORAS_2T_VOTOS_POR_CANDIDATO.items():
        linha_brasil[f"votos_2t_{numero}"] = total
        linha_exterior[f"votos_2t_{numero}"] = 0

    for metrica, total in CONCILIACAO.ANCORAS_2T_METRICAS.items():
        linha_brasil[f"{metrica}_2t"] = total
        linha_exterior[f"{metrica}_2t"] = 0

    return pd.DataFrame([linha_brasil, linha_exterior])


class TestesConciliacao(unittest.TestCase):
    """A conciliação aprova dados corretos e reprova dados adulterados."""

    def test_parse_de_json_para_conciliacao(self) -> None:
        valores = CONCILIACAO.extrair_valores_json(montar_json_municipio_exemplo())

        self.assertEqual(valores.valores["aptos"], 9145969)
        self.assertEqual(valores.valores["nulos"], 216904)
        self.assertEqual(valores.valores["votos_13"], 3864354)
        self.assertEqual(valores.valores["votos_22"], 3097923)
        self.assertEqual(valores.total_votos, 7284071)
        self.assertEqual(valores.totalizacao_final, "s")

    def test_candidato_ausente_conta_zero(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        conteudo["carg"][0]["agr"][0]["par"][0]["cand"] = []
        valores = CONCILIACAO.extrair_valores_json(conteudo)
        self.assertEqual(valores.valores["votos_22"], 0)

    def test_json_sem_bloco_obrigatorio_levanta_erro(self) -> None:
        conteudo = montar_json_municipio_exemplo()
        del conteudo["v"]
        with self.assertRaises(CONCILIACAO.ErroJsonConciliacaoError):
            CONCILIACAO.extrair_valores_json(conteudo)

    def test_ancoras_aprovam_base_correta(self) -> None:
        resultado = CONCILIACAO.checar_ancoras(montar_base_com_valores_das_ancoras())
        self.assertEqual(resultado.status, CONCILIACAO.STATUS_APROVADO, resultado.resumo)

    def test_ancoras_reprovam_um_voto_a_mais(self) -> None:
        base = montar_base_com_valores_das_ancoras()
        base.loc[0, "votos_2t_13"] = base.loc[0, "votos_2t_13"] + 1
        resultado = CONCILIACAO.checar_ancoras(base)
        self.assertEqual(resultado.status, CONCILIACAO.STATUS_REPROVADO)
        self.assertIn("divergências: 1", resultado.resumo)

    def montar_base_consistente_para_identidades(self) -> pd.DataFrame:
        linhas = []
        for sigla, codigo in (("AC", "01007"), ("SP", "71072")):
            linha = {"sg_uf": sigla, "cd_municipio_tse": codigo, "nm_municipio": codigo}
            for rotulo, numeros in (("1t", CONCILIACAO.NUMEROS_CANDIDATOS_1T), ("2t", CONCILIACAO.NUMEROS_CANDIDATOS_2T)):
                soma_candidatos = 0
                for numero in numeros:
                    linha[f"votos_{rotulo}_{numero}"] = 10
                    soma_candidatos += 10
                linha[f"validos_{rotulo}"] = soma_candidatos
                linha[f"brancos_{rotulo}"] = 2
                linha[f"nulos_{rotulo}"] = 3
                comparecimento = soma_candidatos + 2 + 3
                linha[f"comparecimento_{rotulo}"] = comparecimento
                linha[f"abstencao_{rotulo}"] = 7
                linha[f"nao_instaladas_{rotulo}"] = 1
                linha[f"aptos_{rotulo}"] = comparecimento + 7 + 1
            linhas.append(linha)
        return pd.DataFrame(linhas)

    def test_identidades_aprovam_base_consistente(self) -> None:
        base = self.montar_base_consistente_para_identidades()
        resultado = CONCILIACAO.checar_identidades(base, (0, []))
        self.assertEqual(resultado.status, CONCILIACAO.STATUS_APROVADO, resultado.detalhes)

    def test_identidades_reprovam_cada_tipo_de_violacao(self) -> None:
        colunas_adulteradas = [
            "comparecimento_1t",
            "aptos_2t",
            "validos_2t",
            "votos_1t_55",
        ]
        for coluna in colunas_adulteradas:
            base = self.montar_base_consistente_para_identidades()
            base.loc[1, coluna] = base.loc[1, coluna] + 1
            resultado = CONCILIACAO.checar_identidades(base, (0, []))
            self.assertEqual(resultado.status, CONCILIACAO.STATUS_REPROVADO, coluna)

    def test_identidade_do_json_tv_diferente_de_comparecimento_reprova(self) -> None:
        base = self.montar_base_consistente_para_identidades()
        resultado = CONCILIACAO.checar_identidades(base, (1, ["  - SP/71072: tv=1 c=2"]))
        self.assertEqual(resultado.status, CONCILIACAO.STATUS_REPROVADO)

    def test_formatacao_de_inteiro(self) -> None:
        self.assertEqual(CONCILIACAO.formatar_inteiro(56104503), "56.104.503")
        self.assertEqual(CONCILIACAO.formatar_inteiro(0), "0")
        self.assertEqual(CONCILIACAO.formatar_inteiro(-9524), "-9.524")


if __name__ == "__main__":
    unittest.main(verbosity=2)
