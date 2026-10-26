"""Montagem das tabelas e dos textos de saída da inferência ecológica.

Todas as funções deste módulo são puras: recebem resultados já calculados e
devolvem DataFrames ou strings. A gravação em disco fica nos scripts.
"""

import dataclasses

import numpy as np
import pandas as pd

import nucleo_inferencia as nucleo

ROTULOS_REGIOES_E_BRASIL: tuple[str, ...] = nucleo.REGIOES + (nucleo.ROTULO_BRASIL,)
POSICAO_BRASIL = len(nucleo.REGIOES)

# Linhas e células que respondem à pergunta principal e às secundárias.
ORIGENS_PRINCIPAIS: tuple[str, ...] = ("cury", "renan", "caiado")
CELULAS_DE_LEALDADE: tuple[tuple[str, str], ...] = (
    ("lula", "lula"),
    ("flavio", "flavio"),
    ("abstencao", "lula"),
    ("abstencao", "flavio"),
)

COLUNAS_TRANSFERENCIAS: tuple[str, ...] = (
    "especificacao",
    "regiao",
    "origem_1t",
    "destino_2t",
    "beta",
    "beta_ic_inf",
    "beta_ic_sup",
    "votos",
    "votos_ic_inf",
    "votos_ic_sup",
)
CASAS_DECIMAIS_BETA = 6
CASAS_DECIMAIS_VOTOS = 1

AVISO_INTERPRETACAO_IC = (
    "O IC 95% (bootstrap) mede apenas a variabilidade amostral entre municípios. "
    "Ele NÃO captura o viés da hipótese de constância (dentro de cada região, a "
    "fração de cada grupo que vai para cada destino é igual em todos os municípios)."
)


@dataclasses.dataclass(frozen=True)
class DiagnosticoAjuste:
    """Qualidade do ajuste de uma especificação, por região e Brasil.

    Todas as matrizes têm shape (6, 4): linhas = cinco regiões + Brasil, na
    ordem de ROTULOS_REGIOES_E_BRASIL; colunas = DESTINOS_2T.

    Attributes:
        total_previsto: soma_i aptos_2t_i * (X_i beta)_c.
        total_real: Contagem observada do destino no 2º turno.
        r2_ponderado: R² ponderado por aptos_1t (mesma régua nas três especificações).
    """

    total_previsto: np.ndarray
    total_real: np.ndarray
    r2_ponderado: np.ndarray


@dataclasses.dataclass(frozen=True)
class ResultadoEspecificacao:
    """Tudo o que se calculou para uma especificação (E1, E2 ou E3)."""

    especificacao: nucleo.EspecificacaoModelo
    estimativa: nucleo.EstimativaEspecificacao
    bootstrap: nucleo.ResultadoBootstrap
    diagnostico: DiagnosticoAjuste


# ---------------------------------------------------------------------------
# Empilhamento regiões + Brasil
# ---------------------------------------------------------------------------


def empilhar_pontual_regioes_e_brasil(
    por_regiao: np.ndarray,
    brasil: np.ndarray,
) -> np.ndarray:
    """Junta (5, 8, 4) e (8, 4) em (6, 8, 4), com o Brasil na última posição."""
    return np.concatenate([por_regiao, brasil[np.newaxis]], axis=0)


def empilhar_replicas_regioes_e_brasil(
    por_regiao: np.ndarray,
    brasil: np.ndarray,
) -> np.ndarray:
    """Junta (B, 5, 8, 4) e (B, 8, 4) em (B, 6, 8, 4), com o Brasil por último."""
    return np.concatenate([por_regiao, brasil[:, np.newaxis]], axis=1)


# ---------------------------------------------------------------------------
# transferencias.csv
# ---------------------------------------------------------------------------


def montar_tabela_transferencias(resultado: ResultadoEspecificacao) -> pd.DataFrame:
    """Tabela longa de beta e fluxos (com IC 95%) de uma especificação.

    Uma linha por (região ou Brasil) x origem x destino. Os IC são percentis
    2,5 e 97,5 das réplicas bootstrap.

    Args:
        resultado: Estimativa pontual e réplicas bootstrap da especificação.

    Returns:
        DataFrame com as colunas de COLUNAS_TRANSFERENCIAS.
    """
    estimativa = resultado.estimativa
    bootstrap = resultado.bootstrap

    beta_pontual = empilhar_pontual_regioes_e_brasil(
        estimativa.beta_por_regiao,
        estimativa.beta_brasil,
    )
    votos_pontual = empilhar_pontual_regioes_e_brasil(
        estimativa.fluxos_por_regiao,
        estimativa.fluxos_brasil,
    )
    beta_replicas = empilhar_replicas_regioes_e_brasil(
        bootstrap.beta_por_regiao,
        bootstrap.beta_brasil,
    )
    votos_replicas = empilhar_replicas_regioes_e_brasil(
        bootstrap.fluxos_por_regiao,
        bootstrap.fluxos_brasil,
    )

    beta_ic_inf, beta_ic_sup = nucleo.calcular_intervalo_percentil(beta_replicas)
    votos_ic_inf, votos_ic_sup = nucleo.calcular_intervalo_percentil(votos_replicas)

    linhas: list[dict[str, object]] = []
    for posicao_regiao, rotulo_regiao in enumerate(ROTULOS_REGIOES_E_BRASIL):
        for posicao_origem, nome_origem in enumerate(nucleo.ORIGENS_1T):
            for posicao_destino, nome_destino in enumerate(nucleo.DESTINOS_2T):
                celula = (posicao_regiao, posicao_origem, posicao_destino)
                linhas.append(
                    {
                        "especificacao": resultado.especificacao.nome,
                        "regiao": rotulo_regiao,
                        "origem_1t": nome_origem,
                        "destino_2t": nome_destino,
                        "beta": round(float(beta_pontual[celula]), CASAS_DECIMAIS_BETA),
                        "beta_ic_inf": round(float(beta_ic_inf[celula]), CASAS_DECIMAIS_BETA),
                        "beta_ic_sup": round(float(beta_ic_sup[celula]), CASAS_DECIMAIS_BETA),
                        "votos": round(float(votos_pontual[celula]), CASAS_DECIMAIS_VOTOS),
                        "votos_ic_inf": round(float(votos_ic_inf[celula]), CASAS_DECIMAIS_VOTOS),
                        "votos_ic_sup": round(float(votos_ic_sup[celula]), CASAS_DECIMAIS_VOTOS),
                    }
                )

    tabela = pd.DataFrame(linhas)
    return tabela[list(COLUNAS_TRANSFERENCIAS)]


# ---------------------------------------------------------------------------
# Diagnósticos de ajuste
# ---------------------------------------------------------------------------


def calcular_diagnostico_ajuste(
    dados: nucleo.DadosEcologicos,
    estimativa: nucleo.EstimativaEspecificacao,
) -> DiagnosticoAjuste:
    """Calcula total previsto x real e R² ponderado por região e Brasil.

    O total previsto usa `aptos_2t` como denominador (Y é fração dos aptos do
    2º turno). O R² é ponderado por `aptos_1t` em todas as especificações,
    inclusive E3, para que as três sejam comparáveis na mesma régua.

    Args:
        dados: Dados reais.
        estimativa: Estimativa pontual da especificação.

    Returns:
        Matrizes (6, 4) de previsto, real e R².
    """
    fracoes_previstas = nucleo.prever_fracoes_destino(
        dados.matriz_origem,
        dados.regiao,
        estimativa.beta_por_regiao,
    )

    numero_linhas = len(ROTULOS_REGIOES_E_BRASIL)
    total_previsto = np.zeros((numero_linhas, nucleo.NUMERO_DESTINOS))
    total_real = np.zeros((numero_linhas, nucleo.NUMERO_DESTINOS))
    r2_ponderado = np.zeros((numero_linhas, nucleo.NUMERO_DESTINOS))

    for posicao_regiao, rotulo_regiao in enumerate(ROTULOS_REGIOES_E_BRASIL):
        if rotulo_regiao == nucleo.ROTULO_BRASIL:
            posicoes = np.arange(dados.regiao.shape[0])
        else:
            posicoes = np.flatnonzero(dados.regiao == rotulo_regiao)

        total_previsto[posicao_regiao] = nucleo.calcular_total_previsto_destino(
            fracoes_previstas[posicoes],
            dados.aptos_2t[posicoes],
        )
        total_real[posicao_regiao] = dados.contagens_destino[posicoes].sum(axis=0)
        r2_ponderado[posicao_regiao] = nucleo.calcular_r2_ponderado(
            dados.matriz_destino[posicoes],
            fracoes_previstas[posicoes],
            dados.aptos_1t[posicoes],
        )

    return DiagnosticoAjuste(
        total_previsto=total_previsto,
        total_real=total_real,
        r2_ponderado=r2_ponderado,
    )


def calcular_diferenca_maxima_em_celulas_principais(
    beta_a: np.ndarray,
    beta_b: np.ndarray,
) -> float:
    """Maior |beta_a - beta_b| nas linhas cury/renan/caiado e nas 4 células de lealdade."""
    diferenca_absoluta = np.abs(beta_a - beta_b)
    maior_diferenca = 0.0

    for nome_origem in ORIGENS_PRINCIPAIS:
        posicao_origem = nucleo.ORIGENS_1T.index(nome_origem)
        maior_diferenca = max(maior_diferenca, float(diferenca_absoluta[posicao_origem].max()))

    for nome_origem, nome_destino in CELULAS_DE_LEALDADE:
        posicao_origem = nucleo.ORIGENS_1T.index(nome_origem)
        posicao_destino = nucleo.DESTINOS_2T.index(nome_destino)
        maior_diferenca = max(
            maior_diferenca,
            float(diferenca_absoluta[posicao_origem, posicao_destino]),
        )

    return maior_diferenca


# ---------------------------------------------------------------------------
# Formatação Markdown
# ---------------------------------------------------------------------------


def formatar_tabela_markdown(cabecalho: list[str], linhas: list[list[str]]) -> str:
    """Renderiza uma tabela Markdown simples (sem dependência de `tabulate`)."""
    linha_cabecalho = "| " + " | ".join(cabecalho) + " |"
    linha_separadora = "|" + "|".join(["---"] * len(cabecalho)) + "|"

    linhas_texto = [linha_cabecalho, linha_separadora]
    for linha in linhas:
        linhas_texto.append("| " + " | ".join(linha) + " |")

    return "\n".join(linhas_texto)


def formatar_beta_com_ic(valor: float, limite_inferior: float, limite_superior: float) -> str:
    """Formata `0.477 [0.451; 0.503]`."""
    return f"{valor:.3f} [{limite_inferior:.3f}; {limite_superior:.3f}]"


def formatar_votos_com_ic(valor: float, limite_inferior: float, limite_superior: float) -> str:
    """Formata votos em milhares, com IC: `1.234 [1.100; 1.300]` (mil votos)."""
    valor_mil = valor / 1000.0
    inferior_mil = limite_inferior / 1000.0
    superior_mil = limite_superior / 1000.0
    return f"{valor_mil:,.0f} [{inferior_mil:,.0f}; {superior_mil:,.0f}]"


def montar_tabela_beta_brasil_markdown(resultado: ResultadoEspecificacao) -> str:
    """Tabela 8x4 do beta do Brasil com IC 95%."""
    beta_ic_inf, beta_ic_sup = nucleo.calcular_intervalo_percentil(resultado.bootstrap.beta_brasil)
    beta_pontual = resultado.estimativa.beta_brasil

    cabecalho = ["origem 1º turno"] + list(nucleo.DESTINOS_2T)
    linhas: list[list[str]] = []
    for posicao_origem, nome_origem in enumerate(nucleo.ORIGENS_1T):
        linha = [f"**{nome_origem}**"]
        for posicao_destino in range(nucleo.NUMERO_DESTINOS):
            texto_celula = formatar_beta_com_ic(
                beta_pontual[posicao_origem, posicao_destino],
                beta_ic_inf[posicao_origem, posicao_destino],
                beta_ic_sup[posicao_origem, posicao_destino],
            )
            linha.append(texto_celula)
        linhas.append(linha)

    return formatar_tabela_markdown(cabecalho, linhas)


def montar_tabela_fluxos_brasil_markdown(resultado: ResultadoEspecificacao) -> str:
    """Tabela 8x4 dos fluxos em votos do Brasil (milhares de votos) com IC 95%."""
    votos_ic_inf, votos_ic_sup = nucleo.calcular_intervalo_percentil(
        resultado.bootstrap.fluxos_brasil
    )
    votos_pontual = resultado.estimativa.fluxos_brasil

    cabecalho = ["origem 1º turno"] + list(nucleo.DESTINOS_2T)
    linhas: list[list[str]] = []
    for posicao_origem, nome_origem in enumerate(nucleo.ORIGENS_1T):
        linha = [f"**{nome_origem}**"]
        for posicao_destino in range(nucleo.NUMERO_DESTINOS):
            texto_celula = formatar_votos_com_ic(
                votos_pontual[posicao_origem, posicao_destino],
                votos_ic_inf[posicao_origem, posicao_destino],
                votos_ic_sup[posicao_origem, posicao_destino],
            )
            linha.append(texto_celula)
        linhas.append(linha)

    return formatar_tabela_markdown(cabecalho, linhas)


def montar_tabela_regional_principal_markdown(resultado: ResultadoEspecificacao) -> str:
    """Beta por região (pontual) das origens cury/renan/caiado e das células de lealdade."""
    cabecalho = ["região", "origem"] + list(nucleo.DESTINOS_2T)
    linhas: list[list[str]] = []

    for posicao_regiao, nome_regiao in enumerate(nucleo.REGIOES):
        beta_da_regiao = resultado.estimativa.beta_por_regiao[posicao_regiao]
        for nome_origem in ORIGENS_PRINCIPAIS + ("lula", "flavio", "abstencao"):
            posicao_origem = nucleo.ORIGENS_1T.index(nome_origem)
            linha = [nome_regiao, nome_origem]
            for posicao_destino in range(nucleo.NUMERO_DESTINOS):
                valor = beta_da_regiao[posicao_origem, posicao_destino]
                linha.append(f"{valor:.3f}")
            linhas.append(linha)

    return formatar_tabela_markdown(cabecalho, linhas)


def montar_tabela_comparacao_especificacoes_markdown(
    resultados: dict[str, ResultadoEspecificacao],
) -> str:
    """Beta do Brasil de E1, E2 e E3 lado a lado nas origens principais."""
    cabecalho = ["origem", "especificação"] + list(nucleo.DESTINOS_2T)
    linhas: list[list[str]] = []

    for nome_origem in ORIGENS_PRINCIPAIS + ("lula", "flavio", "abstencao"):
        posicao_origem = nucleo.ORIGENS_1T.index(nome_origem)
        for nome_especificacao, resultado in resultados.items():
            beta_brasil = resultado.estimativa.beta_brasil
            linha = [f"**{nome_origem}**", nome_especificacao]
            for posicao_destino in range(nucleo.NUMERO_DESTINOS):
                linha.append(f"{beta_brasil[posicao_origem, posicao_destino]:.3f}")
            linhas.append(linha)

    return formatar_tabela_markdown(cabecalho, linhas)


def montar_tabela_erro_total_previsto_markdown(diagnostico: DiagnosticoAjuste) -> str:
    """Erro relativo (%) do total previsto do 2º turno em relação ao real."""
    cabecalho = ["região"] + list(nucleo.DESTINOS_2T)
    linhas: list[list[str]] = []

    for posicao_regiao, rotulo_regiao in enumerate(ROTULOS_REGIOES_E_BRASIL):
        previsto = diagnostico.total_previsto[posicao_regiao]
        real = diagnostico.total_real[posicao_regiao]
        erro_percentual = 100.0 * (previsto - real) / real
        linha = [rotulo_regiao]
        for posicao_destino in range(nucleo.NUMERO_DESTINOS):
            linha.append(f"{erro_percentual[posicao_destino]:+.3f}%")
        linhas.append(linha)

    return formatar_tabela_markdown(cabecalho, linhas)


def montar_tabela_total_brasil_markdown(diagnostico: DiagnosticoAjuste) -> str:
    """Total previsto x real do 2º turno no Brasil, por destino."""
    cabecalho = ["destino", "previsto", "real", "diferença"]
    linhas: list[list[str]] = []

    for posicao_destino, nome_destino in enumerate(nucleo.DESTINOS_2T):
        previsto = diagnostico.total_previsto[POSICAO_BRASIL, posicao_destino]
        real = diagnostico.total_real[POSICAO_BRASIL, posicao_destino]
        linhas.append(
            [nome_destino, f"{previsto:,.0f}", f"{real:,.0f}", f"{previsto - real:+,.0f}"]
        )

    return formatar_tabela_markdown(cabecalho, linhas)


def montar_tabela_r2_markdown(diagnostico: DiagnosticoAjuste) -> str:
    """R² ponderado por destino, por região e Brasil."""
    cabecalho = ["região"] + list(nucleo.DESTINOS_2T)
    linhas: list[list[str]] = []

    for posicao_regiao, rotulo_regiao in enumerate(ROTULOS_REGIOES_E_BRASIL):
        linha = [rotulo_regiao]
        for posicao_destino in range(nucleo.NUMERO_DESTINOS):
            linha.append(f"{diagnostico.r2_ponderado[posicao_regiao, posicao_destino]:.4f}")
        linhas.append(linha)

    return formatar_tabela_markdown(cabecalho, linhas)


def montar_tabela_convergencia_markdown(resultado: ResultadoEspecificacao) -> str:
    """Iterações, número de condição de G e lacuna de dualidade por unidade de ajuste."""
    cabecalho = [
        "unidade de ajuste",
        "iterações SLSQP",
        "cond(G)",
        "cond(G escalada)",
        "lacuna de dualidade",
    ]
    linhas: list[list[str]] = []

    for rotulo_unidade, ajuste in resultado.estimativa.resultados_ajuste.items():
        linhas.append(
            [
                rotulo_unidade,
                str(ajuste.numero_iteracoes),
                f"{ajuste.numero_condicao_g:.3e}",
                f"{ajuste.numero_condicao_g_escalada:.3e}",
                f"{ajuste.lacuna_dualidade:.2e}",
            ]
        )

    return formatar_tabela_markdown(cabecalho, linhas)


def listar_fronteiras_markdown(resultado: ResultadoEspecificacao) -> list[str]:
    """Bullets com as células de beta na fronteira (0 ou 1) de cada unidade de ajuste."""
    linhas_texto: list[str] = []

    for rotulo_unidade, ajuste in resultado.estimativa.resultados_ajuste.items():
        celulas = nucleo.listar_celulas_na_fronteira(ajuste.beta)
        if not celulas:
            linhas_texto.append(f"- **{rotulo_unidade}**: nenhuma célula na fronteira.")
            continue

        descricoes: list[str] = []
        for nome_origem, nome_destino, valor in celulas:
            descricoes.append(f"{nome_origem}→{nome_destino}={valor:.4f}")
        linhas_texto.append(
            f"- **{rotulo_unidade}**: {len(celulas)} célula(s) na fronteira: "
            + "; ".join(descricoes)
        )

    return linhas_texto


def contar_celulas_na_fronteira(resultado: ResultadoEspecificacao) -> int:
    """Total de células de beta na fronteira somando todas as unidades de ajuste."""
    total_celulas = 0

    for ajuste in resultado.estimativa.resultados_ajuste.values():
        celulas = nucleo.listar_celulas_na_fronteira(ajuste.beta)
        total_celulas += len(celulas)

    return total_celulas
