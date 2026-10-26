"""Orquestração da reimplementação B (migração de votos por UF).

Uso:

    python3 -I executar.py [--replicas 500]

Escreve, nesta pasta: transferencias_uf.csv, validacao_cruzada.md e
diagnosticos.md. O teste sintético roda em ``teste_sintetico.py``.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

PASTA_SAIDA = Path(__file__).resolve().parent
# O modo -I não inclui a pasta do script no sys.path; inclui-se explicitamente.
sys.path.insert(0, str(PASTA_SAIDA))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import migracao_uf_b as mig  # noqa: E402

LOGGER = logging.getLogger("executar_uf_b")

NUMERO_REPLICAS_PADRAO = 500
PERCENTIL_INFERIOR = 2.5
PERCENTIL_SUPERIOR = 97.5
LINHAS_ALVO = ["caiado", "cury", "renan"]
AVISO_IC = (
    "O IC (bootstrap) mede só a variabilidade amostral dentro de cada UF, com "
    "kappa e n_u fixos; NÃO captura o viés de a UF ser puxada para o padrão da "
    "região (nem o viés de a hipótese de constância falhar)."
)
# Células com IC praticamente degenerado (beta preso em 0 ou 1) ficam fora das razões de largura.
LARGURA_MINIMA_COMPARAVEL = 1e-4
LARGURA_MINIMA_VOTOS = 1.0
CODIGO_PRINCIPAL = "UF"
CODIGO_SOZINHO = "UF_SOZINHO"
CODIGO_REGIAO = "UF_REGIAO"


# ---------------------------------------------------------------------------
# Tabelas de saída
# ---------------------------------------------------------------------------


def montar_tabela_longa(
    dados: mig.DadosUf,
    codigo: str,
    ajuste: mig.AjustesUf,
    populacao_uf: np.ndarray,
    beta_ic_inf: np.ndarray | None,
    beta_ic_sup: np.ndarray | None,
) -> pd.DataFrame:
    """Uma tabela longa (27 UFs x 32 células) para uma versão do modelo."""
    linhas: list[dict[str, object]] = []
    for posicao_uf, sigla in enumerate(dados.ufs):
        for posicao_origem, nome_origem in enumerate(mig.ORIGENS):
            populacao = populacao_uf[posicao_uf, posicao_origem]
            for posicao_destino, nome_destino in enumerate(mig.DESTINOS):
                beta = ajuste.beta[posicao_uf, posicao_origem, posicao_destino]
                registro: dict[str, object] = {
                    "especificacao": codigo,
                    "uf": sigla,
                    "nm_regiao": dados.regiao_da_uf[posicao_uf],
                    "origem_1t": nome_origem,
                    "destino_2t": nome_destino,
                    "beta": beta,
                    "beta_ic_inf": np.nan,
                    "beta_ic_sup": np.nan,
                    "votos": beta * populacao,
                    "votos_ic_inf": np.nan,
                    "votos_ic_sup": np.nan,
                    "n_efetivo": ajuste.n_efetivo[posicao_uf],
                    "kappa": ajuste.kappa,
                    "peso_regiao_pct": 100.0 * ajuste.peso_regiao[posicao_uf],
                }
                if beta_ic_inf is not None and beta_ic_sup is not None:
                    limite_inferior = beta_ic_inf[posicao_uf, posicao_origem, posicao_destino]
                    limite_superior = beta_ic_sup[posicao_uf, posicao_origem, posicao_destino]
                    registro["beta_ic_inf"] = limite_inferior
                    registro["beta_ic_sup"] = limite_superior
                    registro["votos_ic_inf"] = limite_inferior * populacao
                    registro["votos_ic_sup"] = limite_superior * populacao
                linhas.append(registro)
    return pd.DataFrame(linhas)


def contar_celulas_fronteira(beta: np.ndarray) -> np.ndarray:
    """Células de beta (por UF) com valor 0 ou 1 dentro de 1e-9 -> (27,)."""
    na_borda = (beta < mig.LIMIAR_FRONTEIRA) | (beta > 1.0 - mig.LIMIAR_FRONTEIRA)
    return na_borda.sum(axis=(1, 2))


# ---------------------------------------------------------------------------
# Relatório da validação cruzada
# ---------------------------------------------------------------------------


def formatar_kappa(kappa: float) -> str:
    """Texto curto para kappa (inf vira 'inf')."""
    if np.isinf(kappa):
        return "inf"
    return f"{kappa:g}"


def calcular_erro_padrao_diferenca(
    validacao: mig.ResultadoValidacao, posicao_referencia: int
) -> np.ndarray:
    """Erro padrão da diferença de erro total (kappa - kappa*) sobre as unidades UF x dobra.

    Trata cada par (UF, dobra) como unidade independente; é só uma régua
    aproximada de quanto a diferença entre kappas é distinguível do ruído.
    """
    erros = validacao.erro_por_uf_dobra
    numero_grade = erros.shape[0]
    unidades_referencia = erros[posicao_referencia].reshape(-1)
    resultado = np.zeros(numero_grade)
    for posicao in range(numero_grade):
        unidades = erros[posicao].reshape(-1)
        diferencas = unidades - unidades_referencia
        desvio = float(np.std(diferencas, ddof=1))
        resultado[posicao] = desvio * np.sqrt(diferencas.size)
    return resultado


def escrever_validacao_md(
    caminho: Path,
    dados: mig.DadosUf,
    validacao: mig.ResultadoValidacao,
    kappa_otimo: float,
    n_efetivo: np.ndarray,
) -> dict[str, object]:
    """Escreve validacao_cruzada.md e devolve números usados no README/relatório."""
    grade = validacao.grade
    erro_total = validacao.erro_total()
    erro_por_uf = validacao.erro_por_uf()
    posicao_otima = grade.index(kappa_otimo)
    erro_padrao = calcular_erro_padrao_diferenca(validacao, posicao_otima)
    erro_infinito = float(erro_total[-1])
    erro_otimo = float(erro_total[posicao_otima])
    na_borda = posicao_otima in (0, len(grade) - 2)

    linhas: list[str] = []
    linhas.append("# Validação cruzada de kappa (implementação B)\n")
    linhas.append(
        "5 dobras por `int(cd_municipio_tse) mod 5`. Erro = soma de `w_i * ||Y_i - X_i beta_u||^2` "
        "nos municípios de teste, somado em UFs e dobras, `w_i = aptos_1t`. "
        f"Total de ajustes: {validacao.numero_ajustes}; não convergidos: {validacao.nao_convergidos}; "
        f"maior violação KKT: {validacao.violacao_kkt_maxima:.2e} (relativa {validacao.violacao_kkt_relativa_maxima:.2e}).\n"
    )
    linhas.append(f"## kappa* = {formatar_kappa(kappa_otimo)}\n")
    linhas.append(
        f"- Erro em kappa*: **{erro_otimo:.2f}**; em kappa = 0,25: **{erro_total[0]:.2f}**; "
        f"em kappa = inf (padrão da região): **{erro_infinito:.2f}**.\n"
        f"- kappa* na borda da grade: **{'SIM' if na_borda else 'não'}**.\n"
    )
    linhas.append("## Curva de erro\n")
    linhas.append("| kappa | erro total | erro / erro(kappa*) | (erro - erro*) / EP |")
    linhas.append("|---|---|---|---|")
    for posicao, kappa in enumerate(grade):
        razao = erro_total[posicao] / erro_otimo
        if posicao == posicao_otima:
            padronizado = "—"
        else:
            padronizado = f"{(erro_total[posicao] - erro_otimo) / erro_padrao[posicao]:.2f}"
        marcador = " **(kappa*)**" if posicao == posicao_otima else ""
        linhas.append(
            f"| {formatar_kappa(kappa)}{marcador} | {erro_total[posicao]:.2f} | {razao:.4f} | {padronizado} |"
        )
    linhas.append(
        "\nEP = erro padrão aproximado da diferença, tratando cada par (UF, dobra) como unidade independente "
        "(régua grosseira; as 135 unidades têm pesos muito desiguais).\n"
    )

    linhas.append("## Heterogeneidade entre UFs (crítica ao kappa único)\n")
    linhas.append(
        "kappa ótimo por UF (argmin do erro da própria UF na grade finita) e "
        "erro em kappa* relativo ao erro da própria UF em kappa = inf.\n"
    )
    linhas.append("| UF | n_u | % do erro total em kappa* | kappa ótimo da UF | erro(kappa*) / erro(inf) |")
    linhas.append("|---|---|---|---|---|")
    numero_finitos = len(grade) - 1
    kappas_otimos_por_uf: dict[str, float] = {}
    for posicao_uf, sigla in enumerate(dados.ufs):
        curva_uf = erro_por_uf[:numero_finitos, posicao_uf]
        curva_constante = float(np.ptp(curva_uf)) <= 1e-9 * float(np.abs(curva_uf).mean())
        kappa_uf = grade[int(np.argmin(curva_uf))]
        kappas_otimos_por_uf[sigla] = kappa_uf
        if curva_constante:
            texto_kappa_uf = "indiferente (UF sem município de treino na dobra de teste)"
        else:
            texto_kappa_uf = formatar_kappa(kappa_uf)
        participacao = 100.0 * erro_por_uf[posicao_otima, posicao_uf] / erro_otimo
        relativo = erro_por_uf[posicao_otima, posicao_uf] / erro_por_uf[-1, posicao_uf]
        linhas.append(
            f"| {sigla} | {n_efetivo[posicao_uf]:.1f} | {participacao:.1f} | "
            f"{texto_kappa_uf} | {relativo:.3f} |"
        )

    erro_relativo = erro_por_uf[:numero_finitos] / erro_por_uf[-1][None, :]
    criterio_normalizado = erro_relativo.sum(axis=1)
    kappa_normalizado = grade[int(np.argmin(criterio_normalizado))]
    maiores_erros = np.argsort(-erro_por_uf[posicao_otima])[:3]
    mascara_sem_maiores = np.ones(len(dados.ufs), dtype=bool)
    mascara_sem_maiores[maiores_erros] = False
    erro_sem_maiores = erro_por_uf[:numero_finitos][:, mascara_sem_maiores].sum(axis=1)
    kappa_sem_maiores = grade[int(np.argmin(erro_sem_maiores))]
    nomes_maiores = [dados.ufs[posicao] for posicao in maiores_erros]
    participacao_maiores = 100.0 * erro_por_uf[posicao_otima, maiores_erros].sum() / erro_otimo

    linhas.append("\n## Sensibilidade de kappa* ao critério de agregação\n")
    linhas.append(f"- Critério da especificação (soma bruta): kappa* = **{formatar_kappa(kappa_otimo)}**.")
    linhas.append(
        f"- Média dos erros relativos por UF (cada UF dividida pelo próprio erro em kappa = inf): "
        f"kappa = **{formatar_kappa(kappa_normalizado)}**."
    )
    linhas.append(
        f"- Sem as 3 UFs de maior erro ({', '.join(nomes_maiores)}; {participacao_maiores:.1f}% do erro): "
        f"kappa = **{formatar_kappa(kappa_sem_maiores)}**."
    )

    peso_por_dobra = np.zeros(mig.NUMERO_DOBRAS)
    contagem_por_dobra = np.zeros(mig.NUMERO_DOBRAS, dtype=np.int64)
    for numero_dobra in range(mig.NUMERO_DOBRAS):
        mascara = dados.dobra == numero_dobra
        peso_por_dobra[numero_dobra] = dados.peso[mascara].sum() / dados.peso.sum()
        contagem_por_dobra[numero_dobra] = int(mascara.sum())
    linhas.append("\n## Equilíbrio das dobras (`cd_municipio_tse mod 5`)\n")
    linhas.append("| dobra | municípios | % dos aptos_1t |")
    linhas.append("|---|---|---|")
    for numero_dobra in range(mig.NUMERO_DOBRAS):
        linhas.append(
            f"| {numero_dobra} | {contagem_por_dobra[numero_dobra]} | {100.0 * peso_por_dobra[numero_dobra]:.1f} |"
        )
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    return {
        "erro_otimo": erro_otimo,
        "erro_sozinho": float(erro_total[0]),
        "erro_infinito": erro_infinito,
        "na_borda": na_borda,
        "kappa_normalizado": kappa_normalizado,
        "kappa_sem_maiores": kappa_sem_maiores,
        "nomes_maiores": nomes_maiores,
        "participacao_maiores": participacao_maiores,
        "razao_erro_padrao": (erro_total - erro_otimo) / np.where(erro_padrao > 0, erro_padrao, np.nan),
        "peso_por_dobra": peso_por_dobra,
        "contagem_por_dobra": contagem_por_dobra,
    }


# ---------------------------------------------------------------------------
# Coerência com o E1 regional
# ---------------------------------------------------------------------------


def calcular_diferenca_beta_agregado(
    dados: mig.DadosUf,
    ajuste: mig.AjustesUf,
    populacao_uf: np.ndarray,
    beta_regioes: np.ndarray,
) -> dict[str, float]:
    """Diferença máxima em beta agregado (soma dos fluxos das UFs / soma de N_u) vs E1.

    Devolve, por linha-alvo, o máximo (em regiões e colunas) de |beta_agregado - beta_E1|.
    """
    resultado: dict[str, float] = {}
    for nome_origem in LINHAS_ALVO:
        posicao_origem = mig.ORIGENS.index(nome_origem)
        diferenca_maxima = 0.0
        for posicao_regiao, nome_regiao in enumerate(mig.REGIOES):
            posicoes_uf = [
                posicao
                for posicao, regiao in enumerate(dados.regiao_da_uf)
                if regiao == nome_regiao
            ]
            fluxo = np.zeros(mig.NUMERO_DESTINOS)
            populacao_total = 0.0
            for posicao_uf in posicoes_uf:
                populacao = populacao_uf[posicao_uf, posicao_origem]
                fluxo += ajuste.beta[posicao_uf, posicao_origem] * populacao
                populacao_total += populacao
            beta_agregado = fluxo / populacao_total
            beta_regional = beta_regioes[posicao_regiao, posicao_origem]
            diferenca = float(np.abs(beta_agregado - beta_regional).max())
            diferenca_maxima = max(diferenca_maxima, diferenca)
        resultado[nome_origem] = diferenca_maxima
    return resultado


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------


def gerar_diagnosticos_md(
    caminho: Path,
    dados: mig.DadosUf,
    ajustes: dict[str, mig.AjustesUf],
    coerencia: dict[str, dict[str, float]],
    kkt_regional: float,
    bootstrap_fixo: mig.ResultadoBootstrap,
    largura_fixa: np.ndarray,
    largura_recalculada: np.ndarray | None,
    votos_ic_n_fixo: np.ndarray,
    votos_ic_n_reamostrado: np.ndarray,
    numero_replicas: int,
    kappa_otimo: float,
) -> dict[str, object]:
    """Escreve diagnosticos.md e devolve números para o relatório final."""
    principal = ajustes[CODIGO_PRINCIPAL]
    sozinho = ajustes[CODIGO_SOZINHO]
    regiao = ajustes[CODIGO_REGIAO]
    fronteira_principal = contar_celulas_fronteira(principal.beta)
    fronteira_sozinho = contar_celulas_fronteira(sozinho.beta)
    fronteira_regiao = contar_celulas_fronteira(regiao.beta)

    linhas: list[str] = []
    linhas.append("# Diagnósticos (implementação B)\n")
    linhas.append(f"{AVISO_IC}\n")
    linhas.append("## Convergência e KKT dos ajustes pontuais\n")
    linhas.append(
        "Violação KKT medida em G, H normalizados (pesos somando 1). Estacionariedade: "
        "`|g_rc - mu_r|` no suporte; complementaridade: `max(mu_r - g_rc, 0)` fora do suporte; "
        "relativa = absoluta / (2 max|H|).\n"
    )
    linhas.append("| versão | kappa | KKT abs. máx | KKT rel. máx | resíduo grad. proj. máx | iterações máx | todos convergiram |")
    linhas.append("|---|---|---|---|---|---|---|")
    for codigo, ajuste in ajustes.items():
        linhas.append(
            f"| {codigo} | {formatar_kappa(ajuste.kappa)} | {ajuste.violacao_kkt.max():.2e} | "
            f"{ajuste.violacao_kkt_relativa.max():.2e} | {ajuste.residuo_projetado.max():.2e} | "
            f"{int(ajuste.iteracoes.max())} | {bool(ajuste.convergiu.all())} |"
        )
    linhas.append(f"| E1 regional refeito (5 regiões) | — | {kkt_regional:.2e} | — | — | — | — |")
    linhas.append(
        f"\nBootstrap UF (B={numero_replicas} x 27 UFs): KKT abs. máx **{bootstrap_fixo.violacao_kkt_maxima:.2e}**, "
        f"não convergidos {bootstrap_fixo.nao_convergidos}.\n"
    )

    linhas.append("## Peso da região, fronteira e condicionamento por UF\n")
    linhas.append(
        "`peso região = kappa/(n_u+kappa)` em %. Fronteira = células de beta (de 32) a menos de 1e-9 de 0 ou 1. "
        "Cond(G) = lambda_max/lambda_min da matriz normalizada do ajuste `UF`.\n"
    )
    linhas.append(
        "| UF | região | n_u | peso região UF (%) | peso região UF_SOZINHO (%) | fronteira UF | fronteira UF_SOZINHO | "
        "fronteira UF_REGIAO | cond(G) UF | cond(G) UF_SOZINHO | cond(G) UF_REGIAO |"
    )
    linhas.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for posicao_uf, sigla in enumerate(dados.ufs):
        linhas.append(
            f"| {sigla} | {dados.regiao_da_uf[posicao_uf]} | {principal.n_efetivo[posicao_uf]:.2f} | "
            f"{100 * principal.peso_regiao[posicao_uf]:.1f} | {100 * sozinho.peso_regiao[posicao_uf]:.1f} | "
            f"{fronteira_principal[posicao_uf]} | {fronteira_sozinho[posicao_uf]} | {fronteira_regiao[posicao_uf]} | "
            f"{principal.numero_condicao[posicao_uf]:.3g} | {sozinho.numero_condicao[posicao_uf]:.3g} | "
            f"{regiao.numero_condicao[posicao_uf]:.3g} |"
        )
    linhas.append(
        f"\nTotal de células na fronteira: UF {int(fronteira_principal.sum())}; "
        f"UF_SOZINHO {int(fronteira_sozinho.sum())}; UF_REGIAO {int(fronteira_regiao.sum())} (de {27 * 32} cada).\n"
    )

    linhas.append("## Plausibilidade (só reportar)\n")
    posicao_lula = mig.ORIGENS.index("lula")
    posicao_flavio = mig.ORIGENS.index("flavio")
    destino_lula = mig.DESTINOS.index("lula")
    destino_flavio = mig.DESTINOS.index("flavio")
    for codigo, ajuste in ajustes.items():
        lealdade_lula = ajuste.beta[:, posicao_lula, destino_lula]
        lealdade_flavio = ajuste.beta[:, posicao_flavio, destino_flavio]
        linhas.append(
            f"- {codigo}: min beta[lula->lula] = {lealdade_lula.min():.4f} ({dados.ufs[int(lealdade_lula.argmin())]}); "
            f"min beta[flavio->flavio] = {lealdade_flavio.min():.4f} ({dados.ufs[int(lealdade_flavio.argmin())]})."
        )

    linhas.append("\n## Coerência com o E1 regional (refeito aqui com o mesmo solver)\n")
    linhas.append(
        "Diferença máxima, em regiões e colunas, entre beta agregado (soma dos fluxos das UFs / soma de N_u) "
        "e o beta do E1 da região. Não precisam bater: são modelos diferentes.\n"
    )
    linhas.append("| versão | caiado | cury | renan |")
    linhas.append("|---|---|---|---|")
    for codigo, diferencas in coerencia.items():
        linhas.append(
            f"| {codigo} | {diferencas['caiado']:.4f} | {diferencas['cury']:.4f} | {diferencas['renan']:.4f} |"
        )

    linhas.append("\n## Sensibilidades do bootstrap\n")
    mediana_razao = float(np.median(votos_ic_n_reamostrado / votos_ic_n_fixo))
    linhas.append(
        f"- Votos com N_u reamostrado (em vez de N_u observado): razão mediana das larguras de IC = **{mediana_razao:.3f}** "
        "(nas células das linhas caiado, cury e renan)."
    )
    if largura_recalculada is not None:
        razao_n = largura_recalculada / largura_fixa
        linhas.append(
            f"- n_u recalculado em cada réplica (em vez de fixo): razão da largura do IC de beta, "
            f"mediana **{float(np.median(razao_n)):.3f}**, mínimo {float(razao_n.min()):.3f}, máximo {float(razao_n.max()):.3f}."
        )
    linhas.append(
        "- DF: a reamostragem do próprio estado é degenerada (1 município); o IC do DF reflete só a região.\n"
        f"- kappa fixo em kappa* = {formatar_kappa(kappa_otimo)}; n_u fixo no valor observado."
    )
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return {
        "fronteira_principal": int(fronteira_principal.sum()),
        "fronteira_sozinho": int(fronteira_sozinho.sum()),
        "fronteira_regiao": int(fronteira_regiao.sum()),
        "mediana_razao_n_reamostrado": mediana_razao,
    }


def calcular_larguras_linhas_alvo(beta_replicas: np.ndarray) -> np.ndarray:
    """Largura (p97,5 - p2,5) de beta nas células das linhas-alvo, (27 * 3 * 4,)."""
    inferior = np.percentile(beta_replicas, PERCENTIL_INFERIOR, axis=1)
    superior = np.percentile(beta_replicas, PERCENTIL_SUPERIOR, axis=1)
    posicoes = [mig.ORIGENS.index(nome) for nome in LINHAS_ALVO]
    largura = (superior - inferior)[:, posicoes, :]
    return largura.reshape(-1)


def principal(numero_replicas: int) -> None:
    """Roda a cadeia completa e escreve as saídas."""
    inicio = time.time()
    base = mig.carregar_base_brasil()
    dados, contagens_destino, aptos_2t = mig.montar_dados_uf(base)
    ancoras = mig.validar_ancoras_uf(dados, contagens_destino, aptos_2t)
    LOGGER.info("Âncoras: %d conferidas.", len(ancoras))
    momentos = mig.montar_momentos(dados)
    populacao_uf = mig.calcular_populacao_origem_uf(dados)
    n_efetivo = mig.calcular_kish_por_uf(dados)

    validacao = mig.validar_cruzado(dados, momentos)
    kappa_otimo = mig.escolher_kappa_otimo(validacao)
    LOGGER.info("kappa* = %s", formatar_kappa(kappa_otimo))
    resumo_cv = escrever_validacao_md(
        PASTA_SAIDA / "validacao_cruzada.md", dados, validacao, kappa_otimo, n_efetivo
    )

    ajustes: dict[str, mig.AjustesUf] = {}
    ajustes[CODIGO_PRINCIPAL] = mig.ajustar_ufs(dados, momentos, kappa_otimo)
    ajustes[CODIGO_SOZINHO] = mig.ajustar_ufs(dados, momentos, mig.KAPPA_SOZINHO)
    ajustes[CODIGO_REGIAO] = mig.ajustar_ufs(dados, momentos, mig.KAPPA_REGIAO)
    for codigo, ajuste in ajustes.items():
        LOGGER.info(
            "%s: KKT max %.2e (rel %.2e), convergiu=%s.",
            codigo,
            ajuste.violacao_kkt.max(),
            ajuste.violacao_kkt_relativa.max(),
            bool(ajuste.convergiu.all()),
        )

    beta_regioes, kkt_regional, _ = mig.ajustar_regioes_e1(dados, momentos)
    coerencia: dict[str, dict[str, float]] = {}
    for codigo, ajuste in ajustes.items():
        coerencia[codigo] = calcular_diferenca_beta_agregado(
            dados, ajuste, populacao_uf, beta_regioes
        )

    beta_pontual = ajustes[CODIGO_PRINCIPAL].beta
    bootstrap_fixo = mig.executar_bootstrap(
        dados, momentos, kappa_otimo, beta_pontual, n_efetivo, numero_replicas
    )
    bootstrap_recalculado = mig.executar_bootstrap(
        dados,
        momentos,
        kappa_otimo,
        beta_pontual,
        n_efetivo,
        numero_replicas,
        recalcular_n_efetivo=True,
    )
    beta_ic_inf = np.percentile(bootstrap_fixo.beta, PERCENTIL_INFERIOR, axis=1)
    beta_ic_sup = np.percentile(bootstrap_fixo.beta, PERCENTIL_SUPERIOR, axis=1)

    # Sensibilidade: votos com N_u reamostrado a cada réplica.
    votos_replicas = bootstrap_fixo.beta * bootstrap_fixo.populacao_reamostrada[:, :, :, None]
    votos_inf_reamostrado = np.percentile(votos_replicas, PERCENTIL_INFERIOR, axis=1)
    votos_sup_reamostrado = np.percentile(votos_replicas, PERCENTIL_SUPERIOR, axis=1)
    posicoes_alvo = [mig.ORIGENS.index(nome) for nome in LINHAS_ALVO]
    populacao_expandida = populacao_uf[:, :, None]
    largura_votos_fixo = ((beta_ic_sup - beta_ic_inf) * populacao_expandida)[:, posicoes_alvo, :]
    largura_votos_reamostrado = (votos_sup_reamostrado - votos_inf_reamostrado)[:, posicoes_alvo, :]
    mascara_largura = largura_votos_fixo > LARGURA_MINIMA_VOTOS
    votos_ic_n_fixo = largura_votos_fixo[mascara_largura]
    votos_ic_n_reamostrado = largura_votos_reamostrado[mascara_largura]

    largura_fixa = calcular_larguras_linhas_alvo(bootstrap_fixo.beta)
    largura_recalculada = calcular_larguras_linhas_alvo(bootstrap_recalculado.beta)
    mascara_larguras = largura_fixa > LARGURA_MINIMA_COMPARAVEL
    largura_fixa_filtrada = largura_fixa[mascara_larguras]
    largura_recalculada_filtrada = largura_recalculada[mascara_larguras]

    tabelas = [
        montar_tabela_longa(
            dados, CODIGO_PRINCIPAL, ajustes[CODIGO_PRINCIPAL], populacao_uf, beta_ic_inf, beta_ic_sup
        ),
        montar_tabela_longa(
            dados, CODIGO_SOZINHO, ajustes[CODIGO_SOZINHO], populacao_uf, None, None
        ),
        montar_tabela_longa(
            dados, CODIGO_REGIAO, ajustes[CODIGO_REGIAO], populacao_uf, None, None
        ),
    ]
    tabela = pd.concat(tabelas, ignore_index=True)
    if len(tabela) != 2592:
        raise ValueError(f"Esperadas 2.592 linhas, obtidas {len(tabela)}.")
    caminho_csv = PASTA_SAIDA / "transferencias_uf.csv"
    tabela.to_csv(caminho_csv, sep=";", index=False, encoding="utf-8", float_format="%.10g")
    LOGGER.info("Gravado %s (%d linhas).", caminho_csv.name, len(tabela))

    resumo_diag = gerar_diagnosticos_md(
        PASTA_SAIDA / "diagnosticos.md",
        dados,
        ajustes,
        coerencia,
        kkt_regional,
        bootstrap_fixo,
        largura_fixa_filtrada,
        largura_recalculada_filtrada,
        votos_ic_n_fixo,
        votos_ic_n_reamostrado,
        numero_replicas,
        kappa_otimo,
    )

    # Impressão dos números principais para o relatório final.
    principal_ajuste = ajustes[CODIGO_PRINCIPAL]
    LOGGER.info("RESUMO kappa*=%s; resumo_cv=%s", formatar_kappa(kappa_otimo), {
        chave: valor for chave, valor in resumo_cv.items() if chave not in ("peso_por_dobra", "contagem_por_dobra", "razao_erro_padrao")
    })
    LOGGER.info("RESUMO diag=%s", resumo_diag)
    for sigla in ["DF", "SP", "GO", "MG"]:
        posicao = dados.ufs.index(sigla)
        LOGGER.info("peso regiao %s = %.2f%%", sigla, 100 * principal_ajuste.peso_regiao[posicao])
    for sigla in ["GO", "SP", "MG"]:
        posicao_uf = dados.ufs.index(sigla)
        for destino in ["lula", "flavio"]:
            posicao_destino = mig.DESTINOS.index(destino)
            posicao_origem = mig.ORIGENS.index("caiado")
            LOGGER.info(
                "beta UF %s caiado->%s = %.4f [%.4f, %.4f]",
                sigla,
                destino,
                principal_ajuste.beta[posicao_uf, posicao_origem, posicao_destino],
                beta_ic_inf[posicao_uf, posicao_origem, posicao_destino],
                beta_ic_sup[posicao_uf, posicao_origem, posicao_destino],
            )
    LOGGER.info(
        "KKT max: UF %.2e, SOZINHO %.2e, REGIAO %.2e, E1 %.2e, CV %.2e, boot %.2e",
        ajustes[CODIGO_PRINCIPAL].violacao_kkt.max(),
        ajustes[CODIGO_SOZINHO].violacao_kkt.max(),
        ajustes[CODIGO_REGIAO].violacao_kkt.max(),
        kkt_regional,
        validacao.violacao_kkt_maxima,
        bootstrap_fixo.violacao_kkt_maxima,
    )
    LOGGER.info("Tempo total: %.1f s.", time.time() - inicio)


def interpretar_argumentos() -> argparse.Namespace:
    """Lê --replicas."""
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--replicas", type=int, default=NUMERO_REPLICAS_PADRAO)
    return analisador.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    argumentos = interpretar_argumentos()
    principal(argumentos.replicas)
