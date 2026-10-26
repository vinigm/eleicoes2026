"""Estima a migração de votos do 1º para o 2º turno (E1, E2, E3) com bootstrap.

Fluxo:
    1. Lê a base e valida as âncoras (para se alguma divergir).
    2. Estima E1, E2 e E3 sobre a amostra original.
    3. Roda o bootstrap estratificado (B réplicas, mesma amostragem nas três).
    4. Calcula diagnósticos de ajuste.
    5. Grava `transferencias.csv` e `diagnosticos.md`.

Uso (a partir de qualquer diretório):
    python3 -I 01_estimar_transferencias.py
"""

import datetime
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PASTA_TRABALHO = Path(__file__).resolve().parent
# `python3 -I` remove a pasta do script do sys.path; este insert é explícito
# e restrito à pasta onde estão os módulos deste projeto.
sys.path.insert(0, str(PASTA_TRABALHO))

import nucleo_inferencia as nucleo  # noqa: E402
import saidas_inferencia as saidas  # noqa: E402

LOGGER = logging.getLogger("estimar_transferencias")

CAMINHO_BASE = (
    PASTA_TRABALHO.parent / "dados" / "processados" / "presidente_municipio_turnos.parquet"
)
CAMINHO_TRANSFERENCIAS = PASTA_TRABALHO / "transferencias.csv"
CAMINHO_DIAGNOSTICOS = PASTA_TRABALHO / "diagnosticos.md"
LIMIAR_CONCENTRACAO_REGIONAL = 0.8
SEPARADOR_CSV = ";"
CODIFICACAO_SAIDA = "utf-8"


def configurar_logging() -> None:
    """Configura log no stderr com horário e nível."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def carregar_dados_reais() -> nucleo.DadosEcologicos:
    """Lê a base real, remove o exterior, monta X e Y e valida as âncoras.

    Returns:
        Dados prontos para estimação.

    Raises:
        ErroAncora: Se qualquer âncora divergir (a execução deve parar).
    """
    base_completa = nucleo.carregar_base_municipal(CAMINHO_BASE)
    municipios = nucleo.selecionar_municipios_brasileiros(base_completa)
    dados = nucleo.montar_dados_ecologicos(municipios)

    resultados_ancoras = nucleo.validar_ancoras(dados)
    for resultado_ancora in resultados_ancoras:
        situacao = "PASS" if resultado_ancora.aprovada else "FAIL"
        LOGGER.info(
            "Âncora %s: esperado=%d obtido=%d [%s]",
            resultado_ancora.nome,
            resultado_ancora.esperado,
            resultado_ancora.obtido,
            situacao,
        )
    nucleo.exigir_ancoras_aprovadas(resultados_ancoras)

    return dados


def estimar_todas_as_especificacoes(
    dados: nucleo.DadosEcologicos,
) -> dict[str, saidas.ResultadoEspecificacao]:
    """Roda E1, E2 e E3: estimativa pontual, bootstrap e diagnóstico de ajuste.

    As três especificações usam exatamente as mesmas multiplicidades bootstrap
    (mesma semente, um único sorteio), então as réplicas são comparáveis.

    Args:
        dados: Dados reais validados.

    Returns:
        Resultados indexados pelo nome da especificação.
    """
    indices_regionais = nucleo.indices_por_regiao(dados.regiao)
    populacao_de_grupos = nucleo.calcular_populacao_de_grupos_por_regiao(
        dados.contagens_origem,
        indices_regionais,
    )
    numero_municipios = dados.regiao.shape[0]
    multiplicidade_unitaria = np.ones(numero_municipios, dtype=np.int64)

    gerador = np.random.default_rng(nucleo.SEMENTE_PADRAO)
    multiplicidades = nucleo.gerar_multiplicidades_bootstrap(
        indices_regionais,
        numero_municipios,
        nucleo.NUMERO_REPLICAS_BOOTSTRAP,
        gerador,
    )
    LOGGER.info(
        "Multiplicidades bootstrap sorteadas: %d réplicas, semente %d.",
        multiplicidades.shape[0],
        nucleo.SEMENTE_PADRAO,
    )

    resultados: dict[str, saidas.ResultadoEspecificacao] = {}
    for especificacao in nucleo.ESPECIFICACOES:
        inicio = time.perf_counter()
        estimativa_pontual = nucleo.estimar_especificacao(
            dados,
            especificacao,
            indices_regionais,
            populacao_de_grupos,
            multiplicidade_unitaria,
        )
        LOGGER.info("%s: estimativa pontual concluída.", especificacao.nome)

        bootstrap = nucleo.executar_bootstrap(
            dados,
            especificacao,
            indices_regionais,
            populacao_de_grupos,
            multiplicidades,
            estimativa_pontual,
        )
        duracao = time.perf_counter() - inicio
        LOGGER.info(
            "%s: bootstrap concluído em %.1fs (maior cond(G)=%.3e, iterações SLSQP=%d).",
            especificacao.nome,
            duracao,
            bootstrap.maior_numero_condicao,
            bootstrap.total_iteracoes_solver,
        )

        diagnostico = saidas.calcular_diagnostico_ajuste(dados, estimativa_pontual)
        resultados[especificacao.nome] = saidas.ResultadoEspecificacao(
            especificacao=especificacao,
            estimativa=estimativa_pontual,
            bootstrap=bootstrap,
            diagnostico=diagnostico,
        )

    return resultados


def listar_concentracoes_regionais_extremas(
    resultado: saidas.ResultadoEspecificacao,
) -> list[str]:
    """Células regionais das origens principais com beta >= LIMIAR_CONCENTRACAO_REGIONAL.

    Heurística de alerta (não é regra do modelo): um grupo pequeno de eleitores
    de Cury, Renan ou Caiado indo quase inteiro para um único destino, dentro
    de uma região, costuma indicar grupo pouco identificado e não preferência real.

    Returns:
        Uma descrição por célula, com o IC 95% do bootstrap.
    """
    beta_ic_inf, beta_ic_sup = nucleo.calcular_intervalo_percentil(
        resultado.bootstrap.beta_por_regiao
    )
    descricoes: list[str] = []

    for posicao_regiao, nome_regiao in enumerate(nucleo.REGIOES):
        for nome_origem in saidas.ORIGENS_PRINCIPAIS:
            posicao_origem = nucleo.ORIGENS_1T.index(nome_origem)
            for posicao_destino, nome_destino in enumerate(nucleo.DESTINOS_2T):
                celula = (posicao_regiao, posicao_origem, posicao_destino)
                valor = resultado.estimativa.beta_por_regiao[celula]
                if valor >= LIMIAR_CONCENTRACAO_REGIONAL:
                    texto_beta = saidas.formatar_beta_com_ic(
                        valor,
                        beta_ic_inf[celula],
                        beta_ic_sup[celula],
                    )
                    descricoes.append(
                        f"{nome_regiao} {nome_origem}→{nome_destino} = {texto_beta}"
                    )

    return descricoes


def montar_secao_alertas(resultados: dict[str, saidas.ResultadoEspecificacao]) -> list[str]:
    """Resume alertas automáticos: fronteira, número de condição e lacuna do solver."""
    linhas: list[str] = ["## Alertas", ""]

    for nome_especificacao, resultado in resultados.items():
        ajustes = resultado.estimativa.resultados_ajuste.values()
        maior_condicao_pontual = max(ajuste.numero_condicao_g for ajuste in ajustes)
        maior_lacuna_pontual = max(ajuste.lacuna_dualidade for ajuste in ajustes)
        celulas_fronteira = saidas.contar_celulas_na_fronteira(resultado)
        maior_condicao_bootstrap = resultado.bootstrap.maior_numero_condicao

        linhas.append(f"- **{nome_especificacao}**")
        linhas.append(
            f"  - células na fronteira (0 ou 1) na estimativa pontual: **{celulas_fronteira}**"
        )
        linhas.append(f"  - maior cond(G) pontual: **{maior_condicao_pontual:.3e}**")
        linhas.append(
            f"  - maior cond(G) entre as {nucleo.NUMERO_REPLICAS_BOOTSTRAP} réplicas: "
            f"**{maior_condicao_bootstrap:.3e}**"
        )
        linhas.append(f"  - maior lacuna de dualidade pontual: {maior_lacuna_pontual:.2e}")

        if maior_condicao_bootstrap > nucleo.LIMITE_NUMERO_CONDICAO_ALTO:
            linhas.append(
                f"  - ⚠️ cond(G) acima de {nucleo.LIMITE_NUMERO_CONDICAO_ALTO:.0e}: "
                "unicidade numericamente frágil."
            )

    linhas.append("")
    concentracoes = listar_concentracoes_regionais_extremas(resultados["E1"])
    linhas.append(
        f"- **E1, concentração extrema regional** (β ≥ {LIMIAR_CONCENTRACAO_REGIONAL} em "
        "cury/renan/caiado; heurística de alerta, indica grupo pouco identificado):"
    )
    if concentracoes:
        for descricao in concentracoes:
            linhas.append(f"  - {descricao}")
    else:
        linhas.append("  - nenhuma.")
    linhas.append("")
    linhas.append(
        "- Convergência: nenhuma falha. Qualquer falha de convergência, solução inviável "
        "ou lacuna de dualidade acima de "
        f"{nucleo.TOLERANCIA_LACUNA_DUALIDADE:.0e} interromperia a execução com erro."
    )
    linhas.append("")
    return linhas


def montar_secao_notas_metodologicas() -> list[str]:
    """Decisões de implementação onde a especificação admitia mais de uma leitura."""
    return [
        "## Decisões de implementação (ambiguidades da especificação)",
        "",
        "- **N_reg fixo no bootstrap:** os totais de cada grupo por região "
        "(`N_reg[r] = Σ aptos_1t · X[r]`) são dados observados, não estimados; só o `β` "
        "é reestimado em cada réplica. O IC dos fluxos mede, portanto, incerteza de `β`.",
        "- **E3 com bootstrap:** a especificação define IC para E1 e E2; E3 também recebeu "
        "bootstrap (mesmas multiplicidades) para preencher as colunas de IC do CSV.",
        "- **E2 por região:** as linhas regionais de E2 repetem o `β` nacional; os fluxos "
        "regionais usam `β_nacional · N_reg`.",
        "- **Total previsto** usa `aptos_2t` como denominador (Y é fração dos aptos do 2º "
        "turno). Os fluxos em votos usam `aptos_1t` (contagem do grupo no 1º turno): a soma "
        "dos fluxos por destino difere do total real do 2º turno só pelo erro do ajuste e "
        "pela diferença de aptos entre turnos (−149 aptos no Brasil).",
        "- **R² ponderado** usa peso `aptos_1t` em E1, E2 e E3 (mesma régua).",
        "- **Pesos:** o ajuste pondera por `aptos_1t` mesmo com Y normalizado por `aptos_2t`, "
        "como na especificação. `aptos_2t − aptos_1t` soma −149 no Brasil; 3.725 municípios "
        "diferem, com diferença relativa máxima de 0,32%.",
        "- **Solver:** SLSQP sobre 32 parâmetros com gradiente analítico, restrições de "
        "soma por linha e limites [0, 1]. As variáveis são reescaladas por `d_r = sqrt(G_rr)` "
        "(o `cond(G)` cai de ~1e6 para ~5e2 no espaço do solver; o ótimo é o mesmo). "
        f"`ftol`={nucleo.TOLERANCIA_FUNCAO_SLSQP:.0e} com objetivo multiplicado por "
        f"{nucleo.ESCALA_OBJETIVO_SLSQP:.0f} (ftol efetivo "
        f"{nucleo.TOLERANCIA_FUNCAO_SLSQP / nucleo.ESCALA_OBJETIVO_SLSQP:.0e}). "
        "Medido na base real: SLSQP direto, sem reescala, com `ftol=1e-12` devolvia betas que "
        "diferiam até 0,44 (Centro-Oeste) conforme o ponto inicial; com a reescala, a "
        "diferença máxima entre 6 pontos iniciais (E1, E3, regiões e nacional) foi 8e-6.",
        "- **Certificado de ótimo:** a lacuna de Frank-Wolfe "
        "(limite superior de objetivo − ótimo) é calculada em todo ajuste e exigida "
        f"≤ {nucleo.TOLERANCIA_LACUNA_DUALIDADE:.0e}.",
        "- **Ponto inicial:** uniforme (0,25) na estimativa pontual; o `β` pontual em cada "
        "réplica bootstrap (só acelera, o problema é convexo).",
        "- **Fronteira:** célula com `β ≤ 1e-6` ou `β ≥ 1 − 1e-6`.",
        "- **Percentis:** `np.percentile` com interpolação linear (2,5 e 97,5).",
        "",
    ]


def montar_diagnosticos_markdown(
    dados: nucleo.DadosEcologicos,
    resultados: dict[str, saidas.ResultadoEspecificacao],
    duracao_total_segundos: float,
) -> str:
    """Monta o texto de `diagnosticos.md`.

    Args:
        dados: Dados reais.
        resultados: Resultados de E1, E2 e E3.
        duracao_total_segundos: Tempo de execução, para registro.

    Returns:
        Conteúdo Markdown completo.
    """
    resultado_e1 = resultados["E1"]
    resultado_e2 = resultados["E2"]
    resultado_e3 = resultados["E3"]

    data_execucao = datetime.date.today().strftime("%d/%m/%Y")
    linhas: list[str] = [
        "# Diagnósticos — inferência ecológica da migração de votos (presidente 2026)",
        "",
        f"Gerado em {data_execucao} por `01_estimar_transferencias.py` · "
        f"{dados.regiao.shape[0]} municípios · B = {nucleo.NUMERO_REPLICAS_BOOTSTRAP} · "
        f"semente {nucleo.SEMENTE_PADRAO} · tempo {duracao_total_segundos:.0f}s.",
        "",
        f"> **Leitura do IC.** {saidas.AVISO_INTERPRETACAO_IC}",
        "",
    ]

    linhas.extend(montar_secao_alertas(resultados))

    linhas.append("## 1. Âncoras")
    linhas.append("")
    linhas.append(
        "Todas as 20 âncoras da especificação (somas por categoria nos dois turnos, aptos, "
        "municípios total e por região) foram conferidas por igualdade exata de inteiros, "
        "e as linhas de X e Y somam 1 (desvio máximo ~2e-16)."
    )
    linhas.append("")
    for resultado_ancora in nucleo.validar_ancoras(dados):
        situacao = "PASS" if resultado_ancora.aprovada else "FAIL"
        linhas.append(
            f"- `{resultado_ancora.nome}`: {resultado_ancora.obtido:,} "
            f"(esperado {resultado_ancora.esperado:,}) — **{situacao}**"
        )
    linhas.append("")

    linhas.append("## 2. Resultado principal — E1, Brasil, β com IC 95%")
    linhas.append("")
    linhas.append(f"> {saidas.AVISO_INTERPRETACAO_IC}")
    linhas.append("")
    linhas.append(saidas.montar_tabela_beta_brasil_markdown(resultado_e1))
    linhas.append("")
    linhas.append("### Fluxos em votos (E1, Brasil, milhares de votos)")
    linhas.append("")
    linhas.append(saidas.montar_tabela_fluxos_brasil_markdown(resultado_e1))
    linhas.append("")
    linhas.append("### E1 por região (β pontual, origens principais e lealdade)")
    linhas.append("")
    linhas.append(saidas.montar_tabela_regional_principal_markdown(resultado_e1))
    linhas.append("")

    linhas.append("## 3. Sensibilidade — E1 × E2 × E3 (β do Brasil)")
    linhas.append("")
    linhas.append(saidas.montar_tabela_comparacao_especificacoes_markdown(resultados))
    linhas.append("")
    diferenca_e1_e2 = saidas.calcular_diferenca_maxima_em_celulas_principais(
        resultado_e1.estimativa.beta_brasil,
        resultado_e2.estimativa.beta_brasil,
    )
    diferenca_e1_e3 = saidas.calcular_diferenca_maxima_em_celulas_principais(
        resultado_e1.estimativa.beta_brasil,
        resultado_e3.estimativa.beta_brasil,
    )
    diferenca_total_e1_e2 = float(
        np.abs(resultado_e1.estimativa.beta_brasil - resultado_e2.estimativa.beta_brasil).max()
    )
    diferenca_total_e1_e3 = float(
        np.abs(resultado_e1.estimativa.beta_brasil - resultado_e3.estimativa.beta_brasil).max()
    )
    linhas.append(
        f"- Diferença máxima **E1 × E2** nas linhas cury/renan/caiado e nas 4 células de "
        f"lealdade: **{diferenca_e1_e2:.4f}** (na matriz inteira: {diferenca_total_e1_e2:.4f})."
    )
    linhas.append(
        f"- Diferença máxima **E1 × E3** nas mesmas células: **{diferenca_e1_e3:.4f}** "
        f"(na matriz inteira: {diferenca_total_e1_e3:.4f})."
    )
    linhas.append(
        "- Diferença grande entre E1 e E2 sinaliza viés de agregação (β que varia por região "
        "ajustado por um β único). É reportada, não corrigida."
    )
    linhas.append("")

    linhas.append("## 4. Ajuste")
    linhas.append("")
    for nome_especificacao, resultado in resultados.items():
        linhas.append(f"### {nome_especificacao} — erro relativo do total previsto do 2º turno")
        linhas.append("")
        linhas.append(saidas.montar_tabela_erro_total_previsto_markdown(resultado.diagnostico))
        linhas.append("")
        linhas.append(f"### {nome_especificacao} — R² ponderado por destino (peso aptos_1t)")
        linhas.append("")
        linhas.append(saidas.montar_tabela_r2_markdown(resultado.diagnostico))
        linhas.append("")
    linhas.append("### E1 — total previsto × real, Brasil")
    linhas.append("")
    linhas.append(saidas.montar_tabela_total_brasil_markdown(resultado_e1.diagnostico))
    linhas.append("")

    linhas.append("## 5. Células de β na fronteira (0 ou 1)")
    linhas.append("")
    linhas.append(
        "Fronteira ativa indica tensão do modelo (o ótimo sem restrição sairia de [0, 1]) "
        "ou grupo pouco identificado."
    )
    linhas.append("")
    for nome_especificacao, resultado in resultados.items():
        linhas.append(f"### {nome_especificacao}")
        linhas.append("")
        linhas.extend(saidas.listar_fronteiras_markdown(resultado))
        linhas.append("")

    linhas.append("## 6. Plausibilidade (só reportada, nunca forçada)")
    linhas.append("")
    posicao_lula = nucleo.ORIGENS_1T.index("lula")
    posicao_flavio = nucleo.ORIGENS_1T.index("flavio")
    destino_lula = nucleo.DESTINOS_2T.index("lula")
    destino_flavio = nucleo.DESTINOS_2T.index("flavio")
    cabecalho = ["especificação", "região", "β[lula→lula]", "β[flavio→flavio]"]
    linhas_tabela: list[list[str]] = []
    for nome_especificacao, resultado in resultados.items():
        beta_empilhado = saidas.empilhar_pontual_regioes_e_brasil(
            resultado.estimativa.beta_por_regiao,
            resultado.estimativa.beta_brasil,
        )
        for posicao_regiao, rotulo_regiao in enumerate(saidas.ROTULOS_REGIOES_E_BRASIL):
            lealdade_lula = beta_empilhado[posicao_regiao, posicao_lula, destino_lula]
            lealdade_flavio = beta_empilhado[posicao_regiao, posicao_flavio, destino_flavio]
            linhas_tabela.append(
                [
                    nome_especificacao,
                    rotulo_regiao,
                    f"{lealdade_lula:.3f}",
                    f"{lealdade_flavio:.3f}",
                ]
            )
    linhas.append(saidas.formatar_tabela_markdown(cabecalho, linhas_tabela))
    linhas.append("")

    linhas.append("## 7. Convergência do solver (estimativa pontual)")
    linhas.append("")
    for nome_especificacao, resultado in resultados.items():
        linhas.append(f"### {nome_especificacao}")
        linhas.append("")
        linhas.append(saidas.montar_tabela_convergencia_markdown(resultado))
        linhas.append("")

    linhas.extend(montar_secao_notas_metodologicas())
    return "\n".join(linhas)


def montar_resumo_para_log(resultados: dict[str, saidas.ResultadoEspecificacao]) -> list[str]:
    """Linhas curtas com os números principais (E1, Brasil) para o log."""
    resultado_e1 = resultados["E1"]
    resultado_e2 = resultados["E2"]
    beta_ic_inf, beta_ic_sup = nucleo.calcular_intervalo_percentil(
        resultado_e1.bootstrap.beta_brasil
    )
    beta_pontual = resultado_e1.estimativa.beta_brasil

    linhas_resumo: list[str] = []
    for nome_origem in saidas.ORIGENS_PRINCIPAIS + ("lula", "flavio", "abstencao"):
        posicao_origem = nucleo.ORIGENS_1T.index(nome_origem)
        textos_destinos: list[str] = []
        for posicao_destino, nome_destino in enumerate(nucleo.DESTINOS_2T):
            texto_beta = saidas.formatar_beta_com_ic(
                beta_pontual[posicao_origem, posicao_destino],
                beta_ic_inf[posicao_origem, posicao_destino],
                beta_ic_sup[posicao_origem, posicao_destino],
            )
            textos_destinos.append(f"{nome_destino}={texto_beta}")
        linhas_resumo.append(f"E1 Brasil {nome_origem}: " + " | ".join(textos_destinos))

    diferenca = saidas.calcular_diferenca_maxima_em_celulas_principais(
        resultado_e1.estimativa.beta_brasil,
        resultado_e2.estimativa.beta_brasil,
    )
    linhas_resumo.append(f"Diferença máxima E1×E2 (linhas principais): {diferenca:.4f}")
    return linhas_resumo


def gravar_saidas(tabela_transferencias: pd.DataFrame, texto_diagnosticos: str) -> None:
    """Grava `transferencias.csv` e `diagnosticos.md` na pasta de trabalho.

    Os arquivos são regeneráveis; uma nova execução os sobrescreve.
    """
    tabela_transferencias.to_csv(
        CAMINHO_TRANSFERENCIAS,
        sep=SEPARADOR_CSV,
        index=False,
        encoding=CODIFICACAO_SAIDA,
    )
    LOGGER.info(
        "Gravado %s (%d linhas).",
        CAMINHO_TRANSFERENCIAS,
        tabela_transferencias.shape[0],
    )

    CAMINHO_DIAGNOSTICOS.write_text(texto_diagnosticos, encoding=CODIFICACAO_SAIDA)
    LOGGER.info("Gravado %s.", CAMINHO_DIAGNOSTICOS)


def main() -> None:
    """Executa a estimação completa e grava as saídas."""
    configurar_logging()
    inicio = time.perf_counter()

    dados = carregar_dados_reais()
    resultados = estimar_todas_as_especificacoes(dados)

    tabelas_por_especificacao: list[pd.DataFrame] = []
    for resultado in resultados.values():
        tabela_da_especificacao = saidas.montar_tabela_transferencias(resultado)
        tabelas_por_especificacao.append(tabela_da_especificacao)
    tabela_transferencias = pd.concat(tabelas_por_especificacao, ignore_index=True)

    duracao_total = time.perf_counter() - inicio
    texto_diagnosticos = montar_diagnosticos_markdown(dados, resultados, duracao_total)
    gravar_saidas(tabela_transferencias, texto_diagnosticos)

    for linha_resumo in montar_resumo_para_log(resultados):
        LOGGER.info(linha_resumo)
    LOGGER.info("Concluído em %.1fs.", duracao_total)


if __name__ == "__main__":
    main()
