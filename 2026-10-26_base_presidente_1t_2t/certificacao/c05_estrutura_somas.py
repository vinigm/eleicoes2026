"""Medicoes 5 e 6: estrutura da base, tabela longa e somas nacionais/por UF.

Medicao 5: chave unica, 5.757 linhas, contagem por UF, tipos int64 sem NaN,
cd_municipio_ibge (7 digitos, unico, nulo so no exterior), nm_regiao por UF,
coerencia da tabela longa com a larga.
Medicao 6: somas nacionais vs ancoras e somas por UF vs CSV bruto (1T) e vs
JSON (2T), calculadas por este script.

Uso: python3 -I c05_estrutura_somas.py   (requer c02 e c03 ja executados)
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

# Raiz do projeto, dois níveis acima de `certificacao/`: roda de qualquer clone.
PASTA_PROJETO = Path(__file__).resolve().parents[2]
PASTA_CERTIFICACAO = PASTA_PROJETO / "2026-10-26_base_presidente_1t_2t" / "certificacao"
CAMINHO_BASE = PASTA_PROJETO / "dados" / "processados" / "presidente_municipio_turnos.parquet"
CAMINHO_LONGA = PASTA_PROJETO / "dados" / "processados" / "presidente_municipio_candidato_long.parquet"
CAMINHO_CSV_BASE = PASTA_PROJETO / "dados" / "processados" / "presidente_municipio_turnos.csv"

TOTAL_MUNICIPIOS = 5757
TOTAL_BRASIL = 5571
TOTAL_EXTERIOR = 186
NUMEROS_1T = [13, 14, 16, 21, 22, 27, 29, 30, 35, 55, 70, 80]
NUMEROS_2T = [13, 22]
CONTAGENS = ["aptos", "comparecimento", "abstencao", "nao_instaladas", "validos", "brancos", "nulos"]

REGIAO_POR_UF = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
    "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
    "ZZ": "Exterior",
}

ANCORAS_1T = {
    "votos_1t_22": 56104503, "votos_1t_13": 53879538, "validos_1t": 119300788,
    "brancos_1t": 2300798, "nulos_1t": 3674249, "comparecimento_1t": 125275835,
    "abstencao_1t": 33469244, "aptos_1t": 158745502,
}
ANCORAS_2T = {
    "votos_2t_13": 64256232, "votos_2t_22": 59826041, "validos_2t": 124082273,
    "brancos_2t": 1430496, "nulos_2t": 2723305, "comparecimento_2t": 128236074,
    "abstencao_2t": 30509005, "aptos_2t": 158745502,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
registro = logging.getLogger("c05")


def verificar(descricao: str, condicao: bool) -> None:
    """Imprime PASS/FAIL de uma verificacao."""
    print(("PASS " if condicao else "FAIL ") + descricao)


def medir_estrutura(base: pd.DataFrame) -> None:
    """Medicao 5 sobre a tabela larga."""
    print("\n=== MEDICAO 5: estrutura ===")
    verificar(f"5.757 linhas (achei {len(base)})", len(base) == TOTAL_MUNICIPIOS)
    verificar("34 colunas", base.shape[1] == 34)
    chaves_duplicadas = int(base.duplicated(["sg_uf", "cd_municipio_tse"]).sum())
    verificar(f"chave (sg_uf, cd_municipio_tse) unica (duplicadas={chaves_duplicadas})", chaves_duplicadas == 0)
    verificar(
        "cd_municipio_tse: str de 5 digitos",
        bool(base["cd_municipio_tse"].str.fullmatch(r"\d{5}").all()),
    )
    contagem_uf = base["sg_uf"].value_counts().sort_index()
    print("linhas por UF:", contagem_uf.to_dict())
    verificar(f"28 siglas (achei {len(contagem_uf)})", len(contagem_uf) == 28)
    verificar("ZZ tem 186 linhas", int(contagem_uf.get("ZZ", 0)) == TOTAL_EXTERIOR)
    verificar("fl_exterior True <=> sg_uf == ZZ", bool((base["fl_exterior"] == (base["sg_uf"] == "ZZ")).all()))
    verificar(f"{TOTAL_BRASIL} municipios no Brasil", int((~base["fl_exterior"]).sum()) == TOTAL_BRASIL)

    colunas_numericas = [c for c in base.columns if c.endswith(("_1t", "_2t")) or c.startswith("votos_")]
    tipos_nao_int64 = [c for c in colunas_numericas if str(base[c].dtype) != "int64"]
    nulos_numericos = int(base[colunas_numericas].isna().sum().sum())
    negativos = int((base[colunas_numericas] < 0).sum().sum())
    verificar(f"{len(colunas_numericas)} colunas numericas, todas int64 (fora: {tipos_nao_int64})", not tipos_nao_int64)
    verificar(f"sem NaN nas colunas numericas ({nulos_numericos})", nulos_numericos == 0)
    verificar(f"sem valores negativos ({negativos})", negativos == 0)

    brasil = base[~base["fl_exterior"]]
    exterior = base[base["fl_exterior"]]
    verificar("IBGE brasileiros: 7 digitos", bool(brasil["cd_municipio_ibge"].str.fullmatch(r"\d{7}").all()))
    verificar("IBGE brasileiros: nao nulo", int(brasil["cd_municipio_ibge"].isna().sum()) == 0)
    verificar("IBGE brasileiros: unico", int(brasil["cd_municipio_ibge"].duplicated().sum()) == 0)
    verificar("IBGE exterior: todos nulos", int(exterior["cd_municipio_ibge"].notna().sum()) == 0)
    esperado_regiao = base["sg_uf"].map(REGIAO_POR_UF)
    verificar("nm_regiao correto nas 28 siglas", bool((esperado_regiao == base["nm_regiao"]).all()))
    print("nm_regiao por UF distintos:", base.groupby("sg_uf")["nm_regiao"].nunique().max())
    verificar("nm_municipio sem nulos/vazios", bool(base["nm_municipio"].notna().all() and (base["nm_municipio"].str.strip() != "").all()))

    # Identidades internas que qualquer turno deve cumprir.
    for sufixo in ("1t", "2t"):
        aptos = base[f"aptos_{sufixo}"]
        compareceu = base[f"comparecimento_{sufixo}"]
        abstencao = base[f"abstencao_{sufixo}"]
        validos = base[f"validos_{sufixo}"]
        brancos = base[f"brancos_{sufixo}"]
        nulos = base[f"nulos_{sufixo}"]
        nao_instaladas = base[f"nao_instaladas_{sufixo}"]
        ident_comp = int(((compareceu + abstencao + nao_instaladas) != aptos).sum())
        ident_votos = int(((validos + brancos + nulos) != compareceu).sum())
        sem_nao_instaladas = int(((compareceu + abstencao) != aptos).sum())
        print(f"identidade {sufixo}: aptos != comparecimento+abstencao+nao_instaladas em {ident_comp} municipios "
              f"(sem somar nao_instaladas seriam {sem_nao_instaladas}); "
              f"validos+brancos+nulos!=comparecimento em {ident_votos} municipios")
    soma_1t = base[[f"votos_1t_{n}" for n in NUMEROS_1T]].sum(axis=1)
    soma_2t = base[[f"votos_2t_{n}" for n in NUMEROS_2T]].sum(axis=1)
    print(f"soma candidatos != validos: 1T em {int((soma_1t != base['validos_1t']).sum())}; "
          f"2T em {int((soma_2t != base['validos_2t']).sum())} municipios")


def medir_tabela_longa(base: pd.DataFrame, longa: pd.DataFrame) -> None:
    """Coerencia da tabela longa com a larga, celula a celula."""
    print("\n=== MEDICAO 5b: tabela longa x larga ===")
    print("colunas longa:", list(longa.columns), "| dtypes:", {c: str(t) for c, t in longa.dtypes.items()})
    esperado_linhas = TOTAL_MUNICIPIOS * (len(NUMEROS_1T) + len(NUMEROS_2T))
    verificar(f"linhas = 5757*14 = {esperado_linhas} (achei {len(longa)})", len(longa) == esperado_linhas)
    duplicadas = int(longa.duplicated(["nr_turno", "sg_uf", "cd_municipio_tse", "nr_candidato"]).sum())
    verificar(f"chave longa unica (duplicadas={duplicadas})", duplicadas == 0)
    nulos = int(longa.isna().sum().sum())
    verificar(f"sem nulos na longa ({nulos})", nulos == 0)
    for turno_longa in sorted(longa["nr_turno"].unique()):
        candidatos_do_turno = sorted(longa.loc[longa["nr_turno"] == turno_longa, "nr_candidato"].unique())
        print(f"candidatos no turno {turno_longa}:", candidatos_do_turno)

    pares_nome = longa[["nr_candidato", "nm_urna_candidato", "sg_partido"]].drop_duplicates()
    print("nr_candidato -> (nome, partido) distintos por candidato (deve ser 1):",
          int(pares_nome.groupby("nr_candidato").size().max()))
    print(pares_nome.sort_values("nr_candidato").to_string(index=False))

    divergencias_totais = 0
    celulas = 0
    for turno, numeros in ((1, NUMEROS_1T), (2, NUMEROS_2T)):
        longa_turno = longa[longa["nr_turno"] == turno]
        pivo = longa_turno.pivot(index=["sg_uf", "cd_municipio_tse"], columns="nr_candidato", values="votos")
        base_indexada = base.set_index(["sg_uf", "cd_municipio_tse"])
        for numero in numeros:
            valores_longa = pivo[numero].reindex(base_indexada.index).to_numpy(dtype="float64")
            valores_larga = base_indexada[f"votos_{turno}t_{numero}"].to_numpy(dtype="float64")
            divergentes = int((~(valores_longa == valores_larga)).sum())
            divergencias_totais += divergentes
            celulas += len(valores_larga)
    verificar(f"longa == larga em todas as {celulas} celulas (divergentes={divergencias_totais})", divergencias_totais == 0)


def medir_somas(base: pd.DataFrame) -> None:
    """Medicao 6: somas nacionais vs ancoras e por UF vs fontes brutas."""
    print("\n=== MEDICAO 6: somas nacionais ===")
    for ancoras in (ANCORAS_1T, ANCORAS_2T):
        for coluna, esperado in ancoras.items():
            obtido = int(base[coluna].sum())
            verificar(f"{coluna}: tabela={obtido:,} ancora={esperado:,}", obtido == esperado)

    csv_agregado = pd.read_parquet(PASTA_CERTIFICACAO / "csv_1t_agregado.parquet")
    json_2t = pd.read_parquet(PASTA_CERTIFICACAO / "json_2t.parquet").reset_index()
    json_1t = pd.read_parquet(PASTA_CERTIFICACAO / "json_1t.parquet").reset_index()

    print("\n=== MEDICAO 6b: somas por UF (tabela vs CSV 1T; tabela vs JSON 2T; tabela vs JSON 1T) ===")
    colunas_1t = [c + "_1t" for c in CONTAGENS] + [f"votos_1t_{n}" for n in NUMEROS_1T]
    soma_base_1t = base.groupby("sg_uf")[colunas_1t].sum()
    soma_csv_1t = csv_agregado.groupby("sg_uf")[colunas_1t].sum()
    dif_1t = (soma_base_1t - soma_csv_1t.reindex(soma_base_1t.index)).abs().to_numpy().sum()
    print(f"1T tabela x CSV: soma abs de diferencas em UF x coluna = {int(dif_1t)} ({soma_base_1t.shape[0]} UFs x {soma_base_1t.shape[1]} colunas)")

    colunas_2t = [c + "_2t" for c in CONTAGENS] + [f"votos_2t_{n}" for n in NUMEROS_2T]
    colunas_json_2t = CONTAGENS + [f"votos_2t_{n}" for n in NUMEROS_2T]
    soma_base_2t = base.groupby("sg_uf")[colunas_2t].sum()
    soma_json_2t = json_2t.groupby("sg_uf")[colunas_json_2t].sum()
    soma_json_2t.columns = colunas_2t
    dif_2t = (soma_base_2t - soma_json_2t.reindex(soma_base_2t.index)).abs().to_numpy().sum()
    print(f"2T tabela x JSON: soma abs de diferencas em UF x coluna = {int(dif_2t)}")

    colunas_json_1t = CONTAGENS + [f"votos_1t_{n}" for n in NUMEROS_1T]
    soma_json_1t = json_1t.groupby("sg_uf")[colunas_json_1t].sum()
    soma_json_1t.columns = colunas_1t
    dif_json_1t = (soma_base_1t - soma_json_1t.reindex(soma_base_1t.index)).abs().to_numpy().sum()
    print(f"1T tabela x JSON: soma abs de diferencas em UF x coluna = {int(dif_json_1t)}")

    # Totais nacionais das duas fontes de 1T (CSV e JSON), independentes da tabela.
    for nome, quadro, colunas in (("CSV1T", csv_agregado, colunas_1t), ("JSON1T", json_1t, colunas_json_1t)):
        totais = {}
        for coluna in colunas:
            totais[coluna] = int(quadro[coluna].sum())
        print(f"totais nacionais {nome}:", totais)

    # Sanidade dos parquet vs csv exportado do construtor (so conferencia de espelho).
    espelho = pd.read_csv(CAMINHO_CSV_BASE, sep=";", dtype={"cd_municipio_tse": str, "cd_municipio_ibge": str})
    print("CSV espelho: shape", espelho.shape)
    colunas_comuns = [c for c in base.columns if c in espelho.columns]
    numericas = [c for c in colunas_comuns if str(base[c].dtype) == "int64"]
    divergentes_espelho = int((base[numericas].to_numpy() != espelho[numericas].to_numpy()).sum())
    print(f"CSV espelho vs parquet: celulas numericas divergentes={divergentes_espelho}")


def main() -> None:
    """Orquestra as medicoes 5 e 6."""
    base = pd.read_parquet(CAMINHO_BASE)
    longa = pd.read_parquet(CAMINHO_LONGA)
    medir_estrutura(base)
    medir_tabela_longa(base, longa)
    medir_somas(base)


if __name__ == "__main__":
    main()
