"""Montagem das tabelas e dos textos de saída da migração por estado.

Todas as funções são puras: recebem resultados já calculados e devolvem
DataFrames ou strings. A gravação em disco fica nos scripts (exceto
`gravar_texto` e `gravar_tabela_csv`, que só escrevem o que receberam).
"""

import dataclasses
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd

import nucleo_uf as nucleo

LOGGER = logging.getLogger(__name__)
regional = nucleo.regional

COLUNAS_TRANSFERENCIAS: tuple[str, ...] = (
    "especificacao",
    "uf",
    "nm_regiao",
    "origem_1t",
    "destino_2t",
    "beta",
    "beta_ic_inf",
    "beta_ic_sup",
    "votos",
    "votos_ic_inf",
    "votos_ic_sup",
    "n_efetivo",
    "kappa",
    "peso_regiao_pct",
)
CASAS_DECIMAIS_BETA = 6
CASAS_DECIMAIS_VOTOS = 1
CASAS_DECIMAIS_N_EFETIVO = 3
CASAS_DECIMAIS_PESO_PCT = 3
NUMERO_LINHAS_ESPERADO = 27 * 3 * 32

ORIGENS_PRINCIPAIS: tuple[str, ...] = ("cury", "renan", "caiado")
LIMITE_ALERTA_DIFERENCA_E1 = 0.10
LIMITE_ALERTA_PONTO_INICIAL = 1e-4
NOME_CURVA_CSV = "curva_validacao_cruzada.csv"
NOME_CURVA_POR_UF_CSV = "curva_validacao_cruzada_por_uf.csv"

AVISO_INTERPRETACAO_IC = (
    "O IC 95% (bootstrap) mede apenas a variabilidade amostral entre municípios, com "
    "kappa fixo em kappa*. Ele NÃO captura o viés da hipótese de constância (dentro "
    "do estado, a fração de cada grupo que vai para cada destino é igual em todos os "
    "municípios) nem o viés de empurrar o estado para o padrão dos demais."
)


@dataclasses.dataclass(frozen=True)
class ResultadosEstimacao:
    """Tudo o que a estimação (script 02) produziu, para montar os diagnósticos.

    Attributes:
        base: Base por UF.
        kappa_estrela: kappa* da validação cruzada.
        kappa_na_borda: Se kappa* está no primeiro ou no último ponto da grade.
        estimativas: Versão -> estimativa pontual.
        bootstrap: Réplicas da versão UF.
        semente: Semente do bootstrap.
        diferencas_e1: Versão -> tabela de diferenças para o E1.
        diferenca_ponto_inicial: Versão -> maior |delta beta| entre dois pontos iniciais.
        ufs_piores_que_regiao: UFs cujo erro de validação em kappa* supera o do padrão da região.
    """

    base: nucleo.BaseUF
    kappa_estrela: float
    kappa_na_borda: bool
    estimativas: dict[str, nucleo.EstimativaVersao]
    bootstrap: nucleo.ResultadoBootstrapUF
    semente: int
    diferencas_e1: dict[str, pd.DataFrame]
    diferenca_ponto_inicial: dict[str, float]
    ufs_piores_que_regiao: list[str]


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------


def formatar_numero(valor: float, casas: int) -> str:
    """Formata no padrão brasileiro: milhar com ponto, decimal com vírgula."""
    if math.isnan(valor):
        return "n/d"
    if math.isinf(valor):
        return "∞"

    texto_ingles = f"{valor:,.{casas}f}"
    texto_marcado = texto_ingles.replace(",", "#").replace(".", ",")
    return texto_marcado.replace("#", ".")


def formatar_cientifico(valor: float) -> str:
    """Notação científica com 2 casas e vírgula decimal (ex.: 6,91e+06)."""
    if math.isinf(valor):
        return "∞"
    return f"{valor:.2e}".replace(".", ",")


def formatar_kappa(kappa: float) -> str:
    """kappa legível: ∞ para infinito, vírgula decimal nos demais."""
    if math.isinf(kappa):
        return "∞"
    return formatar_numero(kappa, 2).rstrip("0").rstrip(",")


def montar_tabela_markdown(cabecalhos: list[str], linhas: list[list[str]]) -> str:
    """Tabela Markdown simples a partir de cabeçalhos e linhas já formatadas."""
    linha_cabecalho = "| " + " | ".join(cabecalhos) + " |"
    separador = "|" + "|".join(["---"] * len(cabecalhos)) + "|"

    linhas_texto = [linha_cabecalho, separador]
    for linha in linhas:
        linhas_texto.append("| " + " | ".join(linha) + " |")

    return "\n".join(linhas_texto)


def gravar_texto(caminho: Path, texto: str) -> None:
    """Grava um texto em UTF-8 (sobrescreve; os artefatos são regeneráveis)."""
    caminho.write_text(texto, encoding="utf-8")
    LOGGER.info("Gravado %s (%d caracteres).", caminho.name, len(texto))


def gravar_tabela_csv(caminho: Path, tabela: pd.DataFrame) -> None:
    """Grava uma tabela em CSV com `;`, UTF-8 e ponto decimal."""
    tabela.to_csv(caminho, sep=";", index=False, encoding="utf-8", na_rep="")
    LOGGER.info("Gravado %s (%d linhas).", caminho.name, tabela.shape[0])


# ---------------------------------------------------------------------------
# transferencias_uf.csv
# ---------------------------------------------------------------------------


def calcular_intervalos_do_bootstrap(
    betas_bootstrap: np.ndarray,
    populacao_por_uf: np.ndarray,
) -> dict[str, np.ndarray]:
    """Limites do IC 95% (percentis 2,5 e 97,5) de beta e de votos, por estado.

    Os votos de cada réplica são beta * N_u[r] com N_u fixo (observado).

    Args:
        betas_bootstrap: (B, U, 8, 4).
        populacao_por_uf: (U, 8).

    Returns:
        Dicionário com `beta_inf`, `beta_sup`, `votos_inf`, `votos_sup`, cada (U, 8, 4).
    """
    votos_bootstrap = nucleo.calcular_votos_por_uf(betas_bootstrap, populacao_por_uf)

    beta_inf, beta_sup = regional.calcular_intervalo_percentil(betas_bootstrap)
    votos_inf, votos_sup = regional.calcular_intervalo_percentil(votos_bootstrap)
    return {
        "beta_inf": beta_inf,
        "beta_sup": beta_sup,
        "votos_inf": votos_inf,
        "votos_sup": votos_sup,
    }


def montar_tabela_transferencias(
    base: nucleo.BaseUF,
    estimativas: dict[str, nucleo.EstimativaVersao],
    intervalos: dict[str, np.ndarray],
) -> pd.DataFrame:
    """Tabela longa `transferencias_uf.csv`: 27 UFs x 3 versões x 32 células.

    Só a versão `UF` recebe intervalo; `UF_SOZINHO` e `UF_REGIAO` ficam com IC vazio.

    Args:
        base: Base por UF.
        estimativas: Versão -> estimativa pontual.
        intervalos: Saída de `calcular_intervalos_do_bootstrap` (versão UF).

    Returns:
        DataFrame com `COLUNAS_TRANSFERENCIAS`.

    Raises:
        ValueError: Se o número de linhas não for 2.592.
    """
    linhas: list[dict[str, object]] = []

    for codigo in nucleo.CODIGOS_VERSOES:
        estimativa = estimativas[codigo]
        tem_intervalo = codigo == nucleo.CODIGO_UF

        for posicao_uf, sigla in enumerate(base.lista_ufs):
            regiao = base.regiao_da_uf[posicao_uf]
            n_efetivo = round(float(estimativa.n_efetivo[posicao_uf]), CASAS_DECIMAIS_N_EFETIVO)
            peso_pct = round(
                100.0 * float(estimativa.peso_regiao[posicao_uf]),
                CASAS_DECIMAIS_PESO_PCT,
            )

            for posicao_origem, origem in enumerate(regional.ORIGENS_1T):
                for posicao_destino, destino in enumerate(regional.DESTINOS_2T):
                    celula = (posicao_uf, posicao_origem, posicao_destino)
                    linha: dict[str, object] = {
                        "especificacao": codigo,
                        "uf": sigla,
                        "nm_regiao": regiao,
                        "origem_1t": origem,
                        "destino_2t": destino,
                        "beta": round(float(estimativa.betas[celula]), CASAS_DECIMAIS_BETA),
                        "beta_ic_inf": np.nan,
                        "beta_ic_sup": np.nan,
                        "votos": round(float(estimativa.votos[celula]), CASAS_DECIMAIS_VOTOS),
                        "votos_ic_inf": np.nan,
                        "votos_ic_sup": np.nan,
                        "n_efetivo": n_efetivo,
                        "kappa": estimativa.kappa,
                        "peso_regiao_pct": peso_pct,
                    }
                    if tem_intervalo:
                        linha["beta_ic_inf"] = round(
                            float(intervalos["beta_inf"][celula]),
                            CASAS_DECIMAIS_BETA,
                        )
                        linha["beta_ic_sup"] = round(
                            float(intervalos["beta_sup"][celula]),
                            CASAS_DECIMAIS_BETA,
                        )
                        linha["votos_ic_inf"] = round(
                            float(intervalos["votos_inf"][celula]),
                            CASAS_DECIMAIS_VOTOS,
                        )
                        linha["votos_ic_sup"] = round(
                            float(intervalos["votos_sup"][celula]),
                            CASAS_DECIMAIS_VOTOS,
                        )
                    linhas.append(linha)

    tabela = pd.DataFrame(linhas, columns=list(COLUNAS_TRANSFERENCIAS))
    if tabela.shape[0] != NUMERO_LINHAS_ESPERADO:
        raise ValueError(
            f"transferencias_uf com {tabela.shape[0]} linhas; esperado {NUMERO_LINHAS_ESPERADO}."
        )
    return tabela


# ---------------------------------------------------------------------------
# Curva de validação cruzada
# ---------------------------------------------------------------------------


def montar_tabela_curva_cv(cv: nucleo.ResultadoValidacaoCruzada) -> pd.DataFrame:
    """Curva de erro por kappa (grade + referência kappa = infinito).

    Colunas: `kappa` (inf na referência), `erro_validacao`, `erro_por_peso`
    (erro / soma dos pesos) e `razao_ao_minimo` (erro / menor erro da grade).
    """
    kappas = list(cv.kappas) + [nucleo.KAPPA_REGIAO]
    erros = list(cv.erro_por_kappa) + [cv.erro_regiao]
    menor_erro = float(cv.erro_por_kappa.min())

    linhas: list[dict[str, float]] = []
    for kappa, erro in zip(kappas, erros):
        linhas.append(
            {
                "kappa": float(kappa),
                "erro_validacao": float(erro),
                "erro_por_peso": float(erro) / cv.soma_pesos_total,
                "razao_ao_minimo": float(erro) / menor_erro,
            }
        )
    return pd.DataFrame(linhas)


def ler_kappa_estrela_da_curva(tabela_curva: pd.DataFrame) -> tuple[float, bool]:
    """kappa* = argmin do erro entre os kappa finitos da curva gravada.

    Args:
        tabela_curva: Conteúdo de `curva_validacao_cruzada.csv`.

    Returns:
        (kappa*, se está na borda da grade). Empate: o menor kappa.

    Raises:
        ValueError: Se a curva não tiver kappa finito.
    """
    tabela_finita = tabela_curva[np.isfinite(tabela_curva["kappa"])].reset_index(drop=True)
    if tabela_finita.shape[0] == 0:
        raise ValueError("Curva de validação cruzada sem kappa finito.")

    posicao_otima = int(np.argmin(tabela_finita["erro_validacao"].to_numpy()))
    kappa_estrela = float(tabela_finita.loc[posicao_otima, "kappa"])
    ultima_posicao = tabela_finita.shape[0] - 1
    na_borda = posicao_otima in (0, ultima_posicao)
    return kappa_estrela, na_borda


def montar_tabela_cv_por_uf(
    base: nucleo.BaseUF,
    cv: nucleo.ResultadoValidacaoCruzada,
) -> pd.DataFrame:
    """Erro de validação por estado e kappa (formato longo; kappa = inf é o padrão da região).

    Colunas: `uf`, `kappa`, `erro_validacao`.
    """
    linhas: list[dict[str, object]] = []

    for posicao_uf, sigla in enumerate(base.lista_ufs):
        for posicao_kappa, kappa in enumerate(cv.kappas):
            linhas.append(
                {
                    "uf": sigla,
                    "kappa": float(kappa),
                    "erro_validacao": float(cv.erro_por_kappa_e_uf[posicao_kappa, posicao_uf]),
                }
            )
        linhas.append(
            {
                "uf": sigla,
                "kappa": nucleo.KAPPA_REGIAO,
                "erro_validacao": float(cv.erro_regiao_por_uf[posicao_uf]),
            }
        )

    return pd.DataFrame(linhas)


def listar_ufs_piores_que_a_regiao(
    tabela_por_uf: pd.DataFrame,
    kappa_estrela: float,
    ufs_sem_informacao: list[str],
) -> list[str]:
    """UFs em que o erro de validação em kappa* supera o do padrão da região (razão > 1).

    Args:
        tabela_por_uf: Saída de `montar_tabela_cv_por_uf`.
        kappa_estrela: kappa* escolhido.
        ufs_sem_informacao: UFs cuja validação não informa kappa (DF: 1 município), excluídas.

    Returns:
        Textos `UF (razão)`, em ordem alfabética de UF.
    """
    piores: list[str] = []
    siglas = sorted(tabela_por_uf["uf"].unique())

    for sigla in siglas:
        if sigla in ufs_sem_informacao:
            continue
        tabela_da_uf = tabela_por_uf[tabela_por_uf["uf"] == sigla]
        erro_estrela = float(tabela_da_uf[tabela_da_uf["kappa"] == kappa_estrela]["erro_validacao"].iloc[0])
        erro_regiao = float(tabela_da_uf[np.isinf(tabela_da_uf["kappa"])]["erro_validacao"].iloc[0])
        razao = erro_estrela / erro_regiao
        if razao > 1.0:
            piores.append(f"{sigla} ({formatar_numero(razao, 2)})")

    return piores


def listar_ufs_de_um_municipio(base: nucleo.BaseUF) -> list[str]:
    """UFs com um único município (DF): a validação cruzada não informa kappa para elas."""
    municipios_por_uf = base.indicador_uf.sum(axis=1)
    siglas: list[str] = []

    for posicao_uf, sigla in enumerate(base.lista_ufs):
        if municipios_por_uf[posicao_uf] <= 1:
            siglas.append(sigla)

    return siglas


def montar_texto_validacao_cruzada(
    base: nucleo.BaseUF,
    cv: nucleo.ResultadoValidacaoCruzada,
    n_efetivo_por_uf: np.ndarray,
    data_criacao: str,
) -> str:
    """Texto de `validacao_cruzada.md`: curva, kappa* e decomposição por estado."""
    tabela_curva = montar_tabela_curva_cv(cv)
    kappa_estrela = cv.kappa_otimo
    posicao_sozinho = int(np.flatnonzero(cv.kappas == nucleo.KAPPA_SOZINHO)[0])

    linhas_curva: list[list[str]] = []
    for _, linha in tabela_curva.iterrows():
        kappa = float(linha["kappa"])
        marcador = ""
        if kappa == kappa_estrela:
            marcador = " **← κ\\***"
        if math.isinf(kappa):
            marcador = " (padrão da região)"
        if kappa == nucleo.KAPPA_SOZINHO:
            marcador = " (UF_SOZINHO)"
        linhas_curva.append(
            [
                formatar_kappa(kappa) + marcador,
                formatar_numero(float(linha["erro_validacao"]), 1),
                formatar_numero(float(linha["erro_por_peso"]) * 1e4, 4),
                formatar_numero(float(linha["razao_ao_minimo"]), 4),
            ]
        )
    tabela_curva_texto = montar_tabela_markdown(
        ["κ", "erro de validação Σ w‖Y−Ŷ‖²", "erro ÷ Σw (×10⁻⁴)", "erro ÷ menor erro"],
        linhas_curva,
    )

    ufs_de_um_municipio = listar_ufs_de_um_municipio(base)
    tabela_cv_por_uf = montar_tabela_cv_por_uf(base, cv)
    ufs_piores = listar_ufs_piores_que_a_regiao(tabela_cv_por_uf, kappa_estrela, ufs_de_um_municipio)
    texto_ufs_piores = ", ".join(ufs_piores)
    if not ufs_piores:
        texto_ufs_piores = "nenhuma"

    linhas_por_uf: list[list[str]] = []
    for posicao_uf, sigla in enumerate(base.lista_ufs):
        erro_regiao = float(cv.erro_regiao_por_uf[posicao_uf])
        erro_estrela = float(cv.erro_por_kappa_e_uf[cv.posicao_kappa_otimo, posicao_uf])
        erro_sozinho = float(cv.erro_por_kappa_e_uf[posicao_sozinho, posicao_uf])
        erros_da_uf = cv.erro_por_kappa_e_uf[:, posicao_uf]
        melhor_kappa_texto = formatar_kappa(float(cv.kappas[int(np.argmin(erros_da_uf))]))
        if sigla in ufs_de_um_municipio:
            melhor_kappa_texto = "n/d (1 município)"
        linhas_por_uf.append(
            [
                sigla,
                base.regiao_da_uf[posicao_uf],
                formatar_numero(float(n_efetivo_por_uf[posicao_uf]), 1),
                formatar_numero(erro_estrela / erro_regiao, 3),
                formatar_numero(erro_sozinho / erro_regiao, 3),
                melhor_kappa_texto,
            ]
        )
    tabela_por_uf = montar_tabela_markdown(
        ["UF", "região", "n efetivo", "erro κ\\* ÷ erro ∞", "erro κ=0,25 ÷ erro ∞", "melhor κ da grade (só a UF)"],
        linhas_por_uf,
    )

    posicao_vizinha = max(cv.posicao_kappa_otimo - 1, 0)
    erro_vizinho = float(cv.erro_por_kappa[posicao_vizinha])
    erro_otimo = float(cv.erro_por_kappa[cv.posicao_kappa_otimo])
    diferenca_vizinho_pct = 100.0 * (erro_vizinho / erro_otimo - 1.0)

    texto_borda = "**κ\\* não está na borda da grade.**"
    if cv.na_borda_da_grade:
        texto_borda = "**ALERTA: κ\\* está na borda da grade** (a grade não foi estendida)."

    partes = [
        "# Validação cruzada de κ — migração de votos por estado",
        "",
        f"Criado em {data_criacao}. Gerado por `01_validacao_cruzada.py`.",
        "",
        "## Resultado",
        "",
        f"- **κ\\* = {formatar_kappa(kappa_estrela)}**, argmin do erro de validação (um κ único para os 27 estados).",
        f"- {texto_borda}",
        f"- Erro em κ\\*: **{formatar_numero(erro_otimo, 1)}**; em κ = 0,25: "
        f"**{formatar_numero(float(cv.erro_por_kappa[posicao_sozinho]), 1)}**; em κ = ∞ (padrão da região): "
        f"**{formatar_numero(cv.erro_regiao, 1)}**.",
        f"- Erro em κ\\* é {formatar_numero(100.0 * (1.0 - erro_otimo / cv.erro_regiao), 1)}% menor que o do padrão da "
        f"região e {formatar_numero(100.0 * (1.0 - erro_otimo / float(cv.erro_por_kappa[posicao_sozinho])), 1)}% menor que o de κ = 0,25.",
        f"- O ponto vizinho à esquerda na grade (κ = {formatar_kappa(float(cv.kappas[posicao_vizinha]))}) tem erro "
        f"{formatar_numero(diferenca_vizinho_pct, 3)}% maior que o de κ\\*: a curva é rasa em torno do mínimo.",
        f"- **Estados em que o erro em κ\\* supera o do padrão da região** (razão erro κ\\* ÷ erro ∞ > 1, entre parênteses): {texto_ufs_piores}. "
        "Para eles, um κ único maior seria melhor; a escolha de um κ único (especificação) foi mantida.",
        "- **DF:** com 1 município, ele sempre sai do treino na própria dobra e o ajuste vira só o termo da região; o erro do DF é igual para todo κ e não informa a escolha.",
        "",
        "## Método (resumo)",
        "",
        "- Partição determinística: `dobra = int(cd_municipio_tse) mod 5`.",
        "- Para cada κ e dobra: cada estado é ajustado com os próprios municípios fora da dobra (n efetivo de Kish recalculado no treino) "
        "e com o termo da região usando TODOS os municípios dos demais estados da região.",
        "- DF (1 município): na dobra em que o município sai, β = ótimo só do termo da região (GO + MT + MS).",
        "- Erro de validação: `Σ_i w_i ‖Y_i − X_i β_u‖²` sobre todos os municípios e dobras, com `w_i = aptos_1t_i`.",
        f"- Ajustes SLSQP executados: {cv.numero_ajustes}. Todos convergiram e foram certificados (falha seria exceção).",
        f"- Ajustes que precisaram do ponto inicial uniforme de reserva (1ª tentativa, a partir da solução do κ anterior, ficou acima do limite de certificação): **{cv.numero_retentativas}**. "
        "O critério de certificação (lacuna de dualidade ≤ 1e-7) não foi relaxado.",
        "",
        "## Curva de erro por κ",
        "",
        tabela_curva_texto,
        "",
        "## Decomposição por estado (informativa)",
        "",
        "- Razão < 1: o estado erra menos fora da amostra do que com o padrão da região.",
        "- A última coluna é o melhor κ da grade olhando só aquele estado. **O método usa κ\\* único**; "
        "a coluna é só um retrato da heterogeneidade e é ruidosa nos estados pequenos.",
        "",
        tabela_por_uf,
        "",
    ]
    return "\n".join(partes)


# ---------------------------------------------------------------------------
# diagnosticos.md
# ---------------------------------------------------------------------------


def montar_secao_ancoras(base: nucleo.BaseUF) -> str:
    """Seção de âncoras: Σ_u N_u[r], municípios e n efetivo por UF."""
    resultados, divergencias = nucleo.validar_ancoras_por_uf(base)
    todas_aprovadas = all(resultado.aprovada for resultado in resultados)
    status = "PASS"
    if not todas_aprovadas or divergencias:
        status = "FAIL"

    totais_por_origem = base.populacao_por_uf.sum(axis=0)
    linhas_origem: list[list[str]] = []
    for posicao, origem in enumerate(regional.ORIGENS_1T):
        esperado = regional.ANCORAS_ORIGEM_1T[origem]
        obtido = int(round(totais_por_origem[posicao]))
        situacao = "ok"
        if esperado != obtido:
            situacao = "DIVERGE"
        linhas_origem.append(
            [origem, formatar_numero(obtido, 0), formatar_numero(esperado, 0), situacao]
        )
    tabela_origem = montar_tabela_markdown(
        ["origem", "Σ_u N_u[r]", "âncora", "situação"],
        linhas_origem,
    )

    estatisticas = nucleo.calcular_estatisticas_por_uf(
        base,
        np.ones(base.dados.aptos_1t.shape[0]),
    )
    n_efetivo = nucleo.calcular_n_efetivo_kish(
        estatisticas.soma_pesos,
        estatisticas.soma_quadrados_dos_pesos,
    )
    municipios_por_uf = base.indicador_uf.sum(axis=1)
    linhas_uf: list[list[str]] = []
    for posicao_uf, sigla in enumerate(base.lista_ufs):
        linhas_uf.append(
            [
                sigla,
                str(int(municipios_por_uf[posicao_uf])),
                str(nucleo.ANCORA_MUNICIPIOS_POR_UF[sigla]),
                formatar_numero(float(n_efetivo[posicao_uf]), 2),
                formatar_numero(nucleo.ANCORA_N_EFETIVO_POR_UF[sigla], 1),
            ]
        )
    tabela_uf = montar_tabela_markdown(
        ["UF", "municípios", "tabela da especificação", "n efetivo (Kish) calculado", "tabela da especificação"],
        linhas_uf,
    )

    partes = [
        "## Âncoras",
        "",
        f"- **Status: {status}** ({len(resultados)} verificações inteiras; n efetivo de {len(base.lista_ufs)} UFs na tolerância de arredondamento da tabela).",
        "- Totais nacionais dos dois turnos, aptos e municípios por região: idênticos aos da especificação regional.",
        "- 27 UFs com as contagens de municípios da tabela da especificação.",
        "",
        tabela_origem,
        "",
        tabela_uf,
        "",
    ]
    return "\n".join(partes)


def montar_secao_peso_da_regiao(resultados: ResultadosEstimacao) -> str:
    """Peso da região por estado (κ / (n_u + κ), em %) nas três versões."""
    base = resultados.base
    estimativa_uf = resultados.estimativas[nucleo.CODIGO_UF]
    estimativa_sozinho = resultados.estimativas[nucleo.CODIGO_UF_SOZINHO]
    municipios_por_uf = base.indicador_uf.sum(axis=1)

    linhas: list[list[str]] = []
    for posicao_uf, sigla in enumerate(base.lista_ufs):
        linhas.append(
            [
                sigla,
                base.regiao_da_uf[posicao_uf],
                str(int(municipios_por_uf[posicao_uf])),
                formatar_numero(float(estimativa_uf.n_efetivo[posicao_uf]), 1),
                formatar_numero(100.0 * float(estimativa_uf.peso_regiao[posicao_uf]), 1),
                formatar_numero(100.0 * float(estimativa_sozinho.peso_regiao[posicao_uf]), 1),
                "100,0",
            ]
        )
    cabecalhos = [
        "UF",
        "região",
        "municípios",
        "n efetivo",
        f"peso da região UF (κ={formatar_kappa(resultados.kappa_estrela)}), %",
        "peso UF_SOZINHO (κ=0,25), %",
        "peso UF_REGIAO (κ=∞), %",
    ]
    tabela = montar_tabela_markdown(cabecalhos, linhas)

    pesos = estimativa_uf.peso_regiao
    posicao_menor = int(np.argmin(pesos))
    posicao_maior = int(np.argmax(pesos))
    partes = [
        "## Peso da região por estado",
        "",
        "- Peso da região = `κ / (n_u + κ)`: a região entra como κ municípios a mais contra `n_u` municípios efetivos do estado.",
        f"- Menor peso (versão UF): **{base.lista_ufs[posicao_menor]} {formatar_numero(100.0 * float(pesos[posicao_menor]), 1)}%**; "
        f"maior: **{base.lista_ufs[posicao_maior]} {formatar_numero(100.0 * float(pesos[posicao_maior]), 1)}%**.",
        "",
        tabela,
        "",
    ]
    return "\n".join(partes)


def listar_celulas_fronteira_de_uf(beta: np.ndarray) -> list[str]:
    """Textos `origem→destino=0|1` das células de beta na fronteira (± 1e-6)."""
    celulas = regional.listar_celulas_na_fronteira(beta)
    textos: list[str] = []

    for origem, destino, valor in celulas:
        extremo = "0"
        if valor >= 0.5:
            extremo = "1"
        textos.append(f"{origem}→{destino}={extremo}")

    return textos


def montar_secao_fronteira(resultados: ResultadosEstimacao) -> str:
    """Células de beta na fronteira (0 ou 1), por estado e versão."""
    base = resultados.base
    linhas_contagem: list[list[str]] = []
    linhas_detalhe: list[str] = []

    for posicao_uf, sigla in enumerate(base.lista_ufs):
        contagens: list[str] = []
        for codigo in nucleo.CODIGOS_VERSOES:
            beta = resultados.estimativas[codigo].betas[posicao_uf]
            celulas = listar_celulas_fronteira_de_uf(beta)
            contagens.append(str(len(celulas)))
            if codigo == nucleo.CODIGO_UF:
                texto_celulas = ", ".join(celulas)
                linhas_detalhe.append(f"- **{sigla}** ({len(celulas)}): {texto_celulas}")
        linhas_contagem.append([sigla] + contagens)

    tabela = montar_tabela_markdown(
        ["UF", "UF (κ\\*)", "UF_SOZINHO", "UF_REGIAO"],
        linhas_contagem,
    )
    partes = [
        "## Células de β na fronteira (= 0 ou = 1)",
        "",
        "- Tolerância de 1e-6. Fronteira ativa indica tensão do modelo (a restrição `0 ≤ β ≤ 1` está pesando).",
        "- Cada estado tem 32 células. Contagem por versão:",
        "",
        tabela,
        "",
        "- Células na fronteira da versão **UF** (κ\\*):",
        "",
    ]
    partes.extend(linhas_detalhe)
    partes.append("")
    return "\n".join(partes)


def montar_secao_condicao(resultados: ResultadosEstimacao) -> str:
    """Número de condição de G por estado e versão; máximo no bootstrap."""
    base = resultados.base
    linhas: list[list[str]] = []
    maior_condicao_pontual = 0.0

    for posicao_uf, sigla in enumerate(base.lista_ufs):
        linha = [sigla]
        ajuste_uf = resultados.estimativas[nucleo.CODIGO_UF].ajustes[posicao_uf]
        linha.append(formatar_cientifico(ajuste_uf.resultado_solver.numero_condicao_g))
        linha.append(formatar_cientifico(ajuste_uf.resultado_solver.numero_condicao_g_escalada))

        for codigo in (nucleo.CODIGO_UF_SOZINHO, nucleo.CODIGO_UF_REGIAO):
            ajuste = resultados.estimativas[codigo].ajustes[posicao_uf]
            linha.append(formatar_cientifico(ajuste.resultado_solver.numero_condicao_g))

        for codigo in nucleo.CODIGOS_VERSOES:
            ajuste = resultados.estimativas[codigo].ajustes[posicao_uf]
            maior_condicao_pontual = max(
                maior_condicao_pontual,
                ajuste.resultado_solver.numero_condicao_g,
            )
        linhas.append(linha)

    tabela = montar_tabela_markdown(
        ["UF", "cond(G) UF", "cond(G) UF após reescala", "cond(G) UF_SOZINHO", "cond(G) UF_REGIAO"],
        linhas,
    )
    bootstrap = resultados.bootstrap
    partes = [
        "## Número de condição de G",
        "",
        f"- Limite de alerta: {formatar_cientifico(regional.LIMITE_NUMERO_CONDICAO_ALTO)}.",
        f"- Maior cond(G) nos ajustes pontuais (3 versões x 27 estados): **{formatar_cientifico(maior_condicao_pontual)}**.",
        f"- Maior cond(G) nos {bootstrap.betas.shape[0] * len(base.lista_ufs)} ajustes do bootstrap: **{formatar_cientifico(bootstrap.maior_numero_condicao)}** "
        f"(após a reescala por √G_rr do solver: {formatar_cientifico(bootstrap.maior_numero_condicao_escalada)}).",
        "- A condição alta de G vem dos grupos minúsculos (ex.: `demais`, ~0,4% dos aptos); o solver reescala as variáveis por √G_rr (mesmo ótimo em β).",
        "- G é definida positiva em todos os estados (inclusive DF) porque `G_{g\\u}` é.",
        "",
        tabela,
        "",
    ]
    return "\n".join(partes)


def montar_secao_solver(resultados: ResultadosEstimacao) -> str:
    """Convergência, lacuna de dualidade e sensibilidade ao ponto inicial."""
    maior_lacuna_pontual = 0.0
    numero_ajustes_pontuais = 0
    retentativas_pontuais = 0
    for codigo in nucleo.CODIGOS_VERSOES:
        for ajuste in resultados.estimativas[codigo].ajustes:
            maior_lacuna_pontual = max(maior_lacuna_pontual, ajuste.resultado_solver.lacuna_dualidade)
            numero_ajustes_pontuais += 1
            retentativas_pontuais += ajuste.numero_tentativas - 1
    numero_ajustes_bootstrap = resultados.bootstrap.betas.shape[0] * len(resultados.base.lista_ufs)

    linhas: list[list[str]] = []
    for codigo in nucleo.CODIGOS_VERSOES:
        diferenca = resultados.diferenca_ponto_inicial[codigo]
        linhas.append([codigo, formatar_cientifico(diferenca)])
    tabela = montar_tabela_markdown(
        ["versão", "maior diferença absoluta em β entre dois pontos iniciais"],
        linhas,
    )

    partes = [
        "## Convergência e estabilidade do solver",
        "",
        "- Todo ajuste exige `success` do SLSQP, viabilidade (soma e limites a 1e-8) e lacuna de dualidade de Frank-Wolfe ≤ 1e-7. Falha = exceção.",
        f"- Ajustes pontuais: {numero_ajustes_pontuais} ({len(nucleo.CODIGOS_VERSOES)} versões x {len(resultados.base.lista_ufs)} UFs); "
        f"**zero falhas**; maior lacuna de dualidade **{formatar_cientifico(maior_lacuna_pontual)}**.",
        f"- Bootstrap: {numero_ajustes_bootstrap} ajustes; **zero falhas**; maior lacuna **{formatar_cientifico(resultados.bootstrap.maior_lacuna_dualidade)}**.",
        f"- Ajustes que precisaram do ponto inicial uniforme de reserva (a 1ª tentativa, de ponto \"quente\", ficou acima do limite de certificação; critério não relaxado): "
        f"pontuais **{retentativas_pontuais}**, bootstrap **{resultados.bootstrap.numero_retentativas}**.",
        "- Unicidade (G definida positiva): o ótimo não depende do ponto inicial. Verificação empírica, reajustando os 27 estados a partir de outro ponto inicial "
        "(UF e UF_SOZINHO: uniforme em vez da solução da região; UF_REGIAO: solução de UF em vez do uniforme):",
        "",
        tabela,
        "",
    ]
    return "\n".join(partes)


def montar_secao_ajuste(resultados: ResultadosEstimacao) -> str:
    """Total previsto x real do 2º turno e R² ponderado, Brasil, três versões."""
    base = resultados.base
    dados = base.dados

    total_real = dados.contagens_destino.sum(axis=0).astype(np.float64)
    linhas_total: list[list[str]] = []
    linhas_r2: list[list[str]] = []
    totais_previstos: dict[str, np.ndarray] = {}
    r2_por_versao: dict[str, np.ndarray] = {}

    for codigo in nucleo.CODIGOS_VERSOES:
        betas = resultados.estimativas[codigo].betas
        fracoes_previstas = nucleo.prever_fracoes_destino_por_uf(base, betas)
        totais_previstos[codigo] = regional.calcular_total_previsto_destino(
            fracoes_previstas,
            dados.aptos_2t,
        )
        r2_por_versao[codigo] = regional.calcular_r2_ponderado(
            dados.matriz_destino,
            fracoes_previstas,
            dados.aptos_1t,
        )

    for posicao_destino, destino in enumerate(regional.DESTINOS_2T):
        linha_total = [destino, formatar_numero(float(total_real[posicao_destino]), 0)]
        linha_r2 = [destino]
        for codigo in nucleo.CODIGOS_VERSOES:
            linha_total.append(formatar_numero(float(totais_previstos[codigo][posicao_destino]), 0))
            linha_r2.append(formatar_numero(float(r2_por_versao[codigo][posicao_destino]), 4))
        linhas_total.append(linha_total)
        linhas_r2.append(linha_r2)

    tabela_total = montar_tabela_markdown(
        ["destino", "real", "previsto UF", "previsto UF_SOZINHO", "previsto UF_REGIAO"],
        linhas_total,
    )
    tabela_r2 = montar_tabela_markdown(
        ["destino", "R² UF", "R² UF_SOZINHO", "R² UF_REGIAO"],
        linhas_r2,
    )
    partes = [
        "## Ajuste (dentro da amostra, Brasil)",
        "",
        "- Total previsto = `Σ_i aptos_2t_i · (X_i β_estado(i))_c`; R² ponderado por `aptos_1t`.",
        "- É ajuste DENTRO da amostra: UF_SOZINHO tende a ajustar melhor aqui por construção; quem mede desempenho fora da amostra é a validação cruzada.",
        "",
        tabela_total,
        "",
        tabela_r2,
        "",
    ]
    return "\n".join(partes)


def calcular_maior_diferenca(tabela_diferencas: pd.DataFrame, origem: str) -> tuple[float, str]:
    """Maior diferença absoluta de beta para uma origem e onde ela ocorre."""
    linhas_da_origem = tabela_diferencas[tabela_diferencas["origem_1t"] == origem]
    posicao_maior = int(np.argmax(linhas_da_origem["diferenca_abs"].to_numpy()))
    linha = linhas_da_origem.iloc[posicao_maior]
    local = f"{linha['regiao']}, {origem}→{linha['destino_2t']}"
    return float(linha["diferenca_abs"]), local


def montar_secao_coerencia_e1(resultados: ResultadosEstimacao) -> str:
    """Compara o β agregado por região (soma dos estados) com o E1 regional."""
    rotulos = regional.REGIOES + (regional.ROTULO_BRASIL,)

    diferencas_uf = resultados.diferencas_e1[nucleo.CODIGO_UF]
    linhas_detalhe: list[list[str]] = []
    for origem in ORIGENS_PRINCIPAIS:
        linha = [origem]
        for rotulo in rotulos:
            selecao = diferencas_uf[
                (diferencas_uf["origem_1t"] == origem) & (diferencas_uf["regiao"] == rotulo)
            ]
            maior = float(selecao["diferenca_abs"].max())
            linha.append(formatar_numero(maior, 3))
        linhas_detalhe.append(linha)
    tabela_detalhe = montar_tabela_markdown(["origem (UF)"] + list(rotulos), linhas_detalhe)

    linhas_resumo: list[list[str]] = []
    for codigo in nucleo.CODIGOS_VERSOES:
        tabela_versao = resultados.diferencas_e1[codigo]
        linha = [codigo]
        for origem in ORIGENS_PRINCIPAIS:
            maior, local = calcular_maior_diferenca(tabela_versao, origem)
            linha.append(f"{formatar_numero(maior, 3)} ({local})")
        linhas_resumo.append(linha)
    cabecalho_resumo = ["versão"] + list(ORIGENS_PRINCIPAIS)
    tabela_resumo = montar_tabela_markdown(cabecalho_resumo, linhas_resumo)

    partes = [
        "## Coerência com o E1 (modelo regional)",
        "",
        "- Soma dos fluxos dos estados por região e no Brasil → β agregado; comparado ao β do E1 (`../2026-10-26_inferencia_ecologica/transferencias.csv`).",
        "- Os modelos são diferentes: **não precisam bater**. A diferença é reportada, não corrigida.",
        "- Maior diferença absoluta em β (entre as 4 destinações e entre as 5 regiões + Brasil), por origem e versão, com o local:",
        "",
        tabela_resumo,
        "",
        "- Detalhe da versão UF: maior |Δβ| por região (sobre as 4 destinações):",
        "",
        tabela_detalhe,
        "",
    ]
    return "\n".join(partes)


def montar_secao_bootstrap(resultados: ResultadosEstimacao) -> str:
    """Parâmetros e ressalvas do bootstrap."""
    bootstrap = resultados.bootstrap
    numero_replicas = bootstrap.betas.shape[0]

    beta_pontual = resultados.estimativas[nucleo.CODIGO_UF].betas
    beta_inferior, beta_superior = regional.calcular_intervalo_percentil(bootstrap.betas)
    fora_do_intervalo = (beta_pontual < beta_inferior - 1e-9) | (beta_pontual > beta_superior + 1e-9)
    numero_fora = int(fora_do_intervalo.sum())
    numero_celulas = int(fora_do_intervalo.size)
    partes = [
        "## Bootstrap",
        "",
        f"- B = **{numero_replicas}** réplicas, semente **{resultados.semente}**, só para a versão `UF`.",
        "- Reamostragem de municípios com reposição **dentro de cada estado**; o termo da região usa os municípios reamostrados dos outros estados da mesma réplica.",
        f"- **κ fica fixo em κ\\* = {formatar_kappa(resultados.kappa_estrela)}**; não é reescolhido por réplica (o IC ignora a incerteza de κ).",
        "- O n efetivo de Kish `n_u` é recalculado em cada réplica sobre os municípios reamostrados (cada cópia conta como uma linha), "
        "então o peso da região varia entre réplicas.",
        "- `N_u[r]` (contagem do grupo no estado) é observado e fixo; os votos de cada réplica são `β · N_u[r]`.",
        "- **DF:** a reamostragem do próprio estado é degenerada (1 município, sempre ele mesmo); o intervalo do DF reflete só a região (GO + MT + MS reamostrados).",
        f"- Células (UF x origem x destino) com β pontual FORA do IC percentil: **{numero_fora} de {numero_celulas}** "
        f"({formatar_numero(100.0 * numero_fora / numero_celulas, 2)}%).",
        f"- Tempo do bootstrap: {formatar_numero(bootstrap.segundos, 1)} s (serial).",
        f"- {AVISO_INTERPRETACAO_IC}",
        "- `UF_SOZINHO` e `UF_REGIAO` saem sem intervalo (colunas de IC vazias).",
        "",
    ]
    return "\n".join(partes)


def coletar_alertas(resultados: ResultadosEstimacao) -> list[str]:
    """Alertas objetivos para o relatório (nada é corrigido em silêncio)."""
    alertas: list[str] = []
    base = resultados.base

    if resultados.kappa_na_borda:
        alertas.append(
            f"κ\\* = {formatar_kappa(resultados.kappa_estrela)} está na borda da grade (grade não estendida)."
        )

    maior_condicao = resultados.bootstrap.maior_numero_condicao
    for codigo in nucleo.CODIGOS_VERSOES:
        for ajuste in resultados.estimativas[codigo].ajustes:
            maior_condicao = max(maior_condicao, ajuste.resultado_solver.numero_condicao_g)
    if maior_condicao > regional.LIMITE_NUMERO_CONDICAO_ALTO:
        alertas.append(
            f"cond(G) máximo {formatar_cientifico(maior_condicao)} acima de "
            f"{formatar_cientifico(regional.LIMITE_NUMERO_CONDICAO_ALTO)}."
        )

    for codigo in nucleo.CODIGOS_VERSOES:
        diferenca = resultados.diferenca_ponto_inicial[codigo]
        if diferenca > LIMITE_ALERTA_PONTO_INICIAL:
            alertas.append(
                f"{codigo}: β varia até {formatar_cientifico(diferenca)} conforme o ponto inicial (> {formatar_cientifico(LIMITE_ALERTA_PONTO_INICIAL)})."
            )

    for codigo in nucleo.CODIGOS_VERSOES:
        tabela = resultados.diferencas_e1[codigo]
        for origem in ORIGENS_PRINCIPAIS:
            maior, local = calcular_maior_diferenca(tabela, origem)
            if maior > LIMITE_ALERTA_DIFERENCA_E1:
                alertas.append(
                    f"{codigo} × E1: |Δβ| {formatar_numero(maior, 3)} para {origem} ({local}) "
                    f"(limite editorial de alerta: {formatar_numero(LIMITE_ALERTA_DIFERENCA_E1, 2)})."
                )

    estimativa_uf = resultados.estimativas[nucleo.CODIGO_UF]
    ufs_com_muita_fronteira: list[str] = []
    for posicao_uf, sigla in enumerate(base.lista_ufs):
        celulas = listar_celulas_fronteira_de_uf(estimativa_uf.betas[posicao_uf])
        celulas_principais = 0
        for texto in celulas:
            origem_da_celula = texto.split("→")[0]
            if origem_da_celula in ORIGENS_PRINCIPAIS:
                celulas_principais += 1
        if celulas_principais >= 6:
            ufs_com_muita_fronteira.append(f"{sigla} ({celulas_principais}/12)")
    if ufs_com_muita_fronteira:
        alertas.append(
            "Versão UF com 6 ou mais das 12 células de cury/renan/caiado na fronteira: "
            + ", ".join(ufs_com_muita_fronteira)
            + "."
        )

    if resultados.ufs_piores_que_regiao:
        alertas.append(
            "Erro de validação em κ\\* maior que o do padrão da região (razão > 1) em: "
            + ", ".join(resultados.ufs_piores_que_regiao)
            + " (ver `validacao_cruzada.md`)."
        )

    alertas.append(
        "DF tem 1 município: o IC do DF reflete só a região (GO + MT + MS); o ponto do DF é "
        f"{formatar_numero(100.0 * float(estimativa_uf.peso_regiao[base.lista_ufs.index('DF')]), 1)}% região."
    )
    return alertas


def montar_texto_diagnosticos(
    resultados: ResultadosEstimacao,
    data_criacao: str,
) -> str:
    """Texto completo de `diagnosticos.md`."""
    alertas = coletar_alertas(resultados)
    linhas_alertas: list[str] = []
    for alerta in alertas:
        linhas_alertas.append(f"- {alerta}")

    partes = [
        "# Diagnósticos — migração de votos por estado (presidente 2026, 1º → 2º turno)",
        "",
        f"Criado em {data_criacao}. Gerado por `02_estimar_uf.py`. Método: `ESPECIFICACAO.md` desta pasta.",
        "",
        f"- {AVISO_INTERPRETACAO_IC}",
        f"- κ\\* = **{formatar_kappa(resultados.kappa_estrela)}** (ver `validacao_cruzada.md`).",
        "",
        "## Alertas",
        "",
        "\n".join(linhas_alertas),
        "",
        montar_secao_ancoras(resultados.base),
        montar_secao_peso_da_regiao(resultados),
        montar_secao_fronteira(resultados),
        montar_secao_condicao(resultados),
        montar_secao_solver(resultados),
        montar_secao_ajuste(resultados),
        montar_secao_coerencia_e1(resultados),
        montar_secao_bootstrap(resultados),
    ]
    return "\n".join(partes)
