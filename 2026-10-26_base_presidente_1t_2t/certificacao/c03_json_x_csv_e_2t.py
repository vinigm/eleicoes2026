"""Medicoes 2, 3 (parte 1) e 4: JSON 1T x CSV 1T, tabela 2T x JSON 2T, aptos.

Le os JSONs de municipio de 6257 (1T) e 6258 (2T) com parser proprio, grava
os dois quadros em parquet (certificacao/json_1t.parquet e json_2t.parquet) e
compara:
    * JSON 1T x CSV 1T reagregado (csv_1t_agregado.parquet, gerado por c02);
    * tabela (colunas de 2T) x JSON 2T;
    * aptos entre turnos em tres pares de fontes.

Uso: python3 -I c03_json_x_csv_e_2t.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

# Raiz do projeto, dois níveis acima de `certificacao/`: roda de qualquer clone.
PASTA_PROJETO = Path(__file__).resolve().parents[2]
PASTA_CERTIFICACAO = PASTA_PROJETO / "2026-10-26_base_presidente_1t_2t" / "certificacao"
CAMINHO_BASE = PASTA_PROJETO / "dados" / "processados" / "presidente_municipio_turnos.parquet"
PASTA_JSON = PASTA_PROJETO / "dados" / "json_tse"
CAMINHO_CSV_AGREGADO = PASTA_CERTIFICACAO / "csv_1t_agregado.parquet"

NUMEROS_CANDIDATOS_1T = [13, 14, 16, 21, 22, 27, 29, 30, 35, 55, 70, 80]
NUMEROS_CANDIDATOS_2T = [13, 22]
CONTAGENS = [
    "aptos",
    "comparecimento",
    "abstencao",
    "nao_instaladas",
    "validos",
    "brancos",
    "nulos",
]
QUANTIDADE_EXEMPLOS = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
registro = logging.getLogger("c03")


def caminho_json_municipio(codigo_eleicao: str, uf_minuscula: str, codigo_tse: str) -> Path:
    """Monta o caminho local que espelha a URL oficial do TSE."""
    nome = f"{uf_minuscula}{codigo_tse}-c0001-e00{codigo_eleicao}-u.json"
    return PASTA_JSON / codigo_eleicao / "dados" / uf_minuscula / nome


def extrair_votos_candidatos(documento: dict) -> dict[int, int]:
    """Percorre carg[0].agr[].par[].cand[] e devolve {numero: votos}."""
    cargos = documento["carg"]
    if len(cargos) != 1:
        raise ValueError(f"Esperado 1 cargo, achei {len(cargos)}")
    votos_por_candidato: dict[int, int] = {}
    for agremiacao in cargos[0]["agr"]:
        for partido in agremiacao["par"]:
            for candidato in partido["cand"]:
                numero = int(candidato["n"])
                if numero in votos_por_candidato:
                    raise ValueError(f"Candidato {numero} duplicado")
                votos_por_candidato[numero] = int(candidato["vap"])
    return votos_por_candidato


def interpretar_documento(documento: dict, prefixo_votos: str) -> dict[str, int | str]:
    """Converte um JSON de municipio em linha plana com as colunas da base."""
    bloco_e = documento["e"]
    bloco_v = documento["v"]
    linha: dict[str, int | str] = {
        "aptos": int(bloco_e["te"]),
        "comparecimento": int(bloco_e["c"]),
        "abstencao": int(bloco_e["a"]),
        "nao_instaladas": int(bloco_e["esni"]),
        "validos": int(bloco_v["vv"]),
        "brancos": int(bloco_v["vb"]),
        "nulos": int(bloco_v["tvn"]),
        "meta_ele": documento["ele"],
        "meta_turno": documento["t"],
        "meta_cdabr": documento["cdabr"],
        "meta_tpabr": documento["tpabr"],
        "meta_totalizacao_pct": documento["s"]["pstn"],
        "meta_geracao": documento["dg"] + " " + documento["hg"],
    }
    votos = extrair_votos_candidatos(documento)
    for numero, quantidade in votos.items():
        linha[prefixo_votos + str(numero)] = quantidade
    return linha


def carregar_municipios_json(codigo_eleicao: str, sufixo_turno: str) -> pd.DataFrame:
    """Le todos os municipios (lista da config) de uma eleicao.

    Args:
        codigo_eleicao: "6257" (1T) ou "6258" (2T).
        sufixo_turno: "1t" ou "2t", usado no prefixo das colunas de votos.

    Returns:
        Quadro indexado por (sg_uf maiusculo, cd_municipio_tse).
    """
    caminho_config = PASTA_JSON / codigo_eleicao / "config" / f"mun-e00{codigo_eleicao}-cm.json"
    config = json.loads(caminho_config.read_text(encoding="utf-8"))
    linhas: list[dict[str, int | str]] = []
    prefixo_votos = f"votos_{sufixo_turno}_"
    for bloco_uf in config["abr"]:
        uf_minuscula = bloco_uf["cd"]
        for municipio in bloco_uf["mu"]:
            codigo_tse = municipio["cd"]
            caminho = caminho_json_municipio(codigo_eleicao, uf_minuscula, codigo_tse)
            documento = json.loads(caminho.read_text(encoding="utf-8"))
            linha = interpretar_documento(documento, prefixo_votos)
            linha["sg_uf"] = uf_minuscula.upper()
            linha["cd_municipio_tse"] = codigo_tse
            linha["cd_municipio_ibge_json"] = municipio.get("cdi", "")
            linhas.append(linha)
    quadro = pd.DataFrame(linhas)
    registro.info("Eleicao %s: %d municipios lidos.", codigo_eleicao, len(quadro))
    return quadro.set_index(["sg_uf", "cd_municipio_tse"]).sort_index()


def validar_metadados(quadro: pd.DataFrame, codigo_eleicao: str, turno: str) -> None:
    """Imprime verificacoes de metadados do JSON (eleicao, turno, totalizacao)."""
    print(f"[meta {codigo_eleicao}] ele unicos={sorted(quadro['meta_ele'].unique())} "
          f"turno unicos={sorted(quadro['meta_turno'].unique())} "
          f"tpabr={sorted(quadro['meta_tpabr'].unique())}")
    print(f"[meta {codigo_eleicao}] totalizacao % unicos={sorted(quadro['meta_totalizacao_pct'].unique())}")
    cdabr_confere = (quadro["meta_cdabr"].to_numpy() == quadro.index.get_level_values(1).to_numpy())
    print(f"[meta {codigo_eleicao}] cdabr == cd da config em {int(cdabr_confere.sum())}/{len(quadro)}")
    print(f"[meta {codigo_eleicao}] geracao min/max: {quadro['meta_geracao'].min()} / {quadro['meta_geracao'].max()}")
    if turno not in set(quadro["meta_turno"].unique()):
        print(f"[meta {codigo_eleicao}] ATENCAO: turno esperado {turno} ausente")


def descrever_divergencias(
    rotulo: str,
    quadro_a: pd.DataFrame,
    quadro_b: pd.DataFrame,
    colunas_a: list[str],
    colunas_b: list[str],
) -> pd.DataFrame:
    """Compara duas fontes coluna a coluna, tolerancia zero.

    Args:
        rotulo: Texto de identificacao da comparacao.
        quadro_a: Primeira fonte (mesmo indice de quadro_b).
        quadro_b: Segunda fonte.
        colunas_a: Colunas de A.
        colunas_b: Colunas de B, na mesma ordem das de A.

    Returns:
        Quadro com a diferenca (A - B) por municipio e coluna, util para detalhar.
    """
    indice_comum = quadro_a.index.intersection(quadro_b.index)
    print(f"\n=== {rotulo} === municipios em comum: {len(indice_comum)} "
          f"(A={len(quadro_a)}, B={len(quadro_b)})")
    diferencas = pd.DataFrame(index=indice_comum)
    total_celulas_divergentes = 0
    for coluna_a, coluna_b in zip(colunas_a, colunas_b):
        valores_a = quadro_a.loc[indice_comum, coluna_a].to_numpy(dtype="int64")
        valores_b = quadro_b.loc[indice_comum, coluna_b].to_numpy(dtype="int64")
        diferenca = valores_a - valores_b
        diferencas[coluna_a] = diferenca
        quantidade = int((diferenca != 0).sum())
        total_celulas_divergentes += quantidade
        print(f"{coluna_a} vs {coluna_b}: municipios divergentes={quantidade} "
              f"soma_abs={int(np.abs(diferenca).sum())} soma_liquida={int(diferenca.sum())}")
    municipios_com_divergencia = int((diferencas.to_numpy() != 0).any(axis=1).sum())
    print(f"TOTAL celulas divergentes={total_celulas_divergentes} de {diferencas.size}; "
          f"municipios com ao menos 1 divergencia={municipios_com_divergencia}")
    return diferencas


def mostrar_maiores_exemplos(diferencas: pd.DataFrame, coluna: str) -> None:
    """Imprime os municipios com maior diferenca absoluta numa coluna."""
    absolutos = diferencas[coluna].abs().sort_values(ascending=False)
    maiores = absolutos.head(QUANTIDADE_EXEMPLOS).index
    print(f"Maiores diferencas em {coluna}:")
    for chave in maiores:
        valor = int(diferencas.loc[chave, coluna])
        if valor != 0:
            print(f"   {chave}: {valor:+d}")


def analisar_aptos(
    base: pd.DataFrame,
    json_1t: pd.DataFrame,
    json_2t: pd.DataFrame,
    csv_1t: pd.DataFrame,
) -> None:
    """Medicao 4: aptos entre turnos em tres pares de fontes."""
    pares = {
        "tabela aptos_1t vs aptos_2t": (base["aptos_1t"], base["aptos_2t"]),
        "JSON1T vs JSON2T": (json_1t["aptos"], json_2t["aptos"]),
        "CSV1T vs JSON2T": (csv_1t["aptos_1t"], json_2t["aptos"]),
        "CSV1T vs JSON1T": (csv_1t["aptos_1t"], json_1t["aptos"]),
    }
    print("\n=== MEDICAO 4: aptos entre turnos ===")
    for rotulo, (serie_a, serie_b) in pares.items():
        indice_comum = serie_a.index.intersection(serie_b.index)
        diferenca = serie_a.loc[indice_comum].to_numpy(dtype="int64") - serie_b.loc[
            indice_comum
        ].to_numpy(dtype="int64")
        positivos = diferenca > 0
        negativos = diferenca < 0
        print(
            f"{rotulo}: municipios diferentes={int((diferenca != 0).sum())} "
            f"(A>B={int(positivos.sum())}, A<B={int(negativos.sum())}); "
            f"soma A-B={int(diferenca.sum())}; soma+={int(diferenca[positivos].sum())}; "
            f"soma-={int(diferenca[negativos].sum())}; max|dif|={int(np.abs(diferenca).max())}"
        )


def main() -> None:
    """Orquestra as medicoes."""
    base = pd.read_parquet(CAMINHO_BASE).set_index(["sg_uf", "cd_municipio_tse"]).sort_index()
    csv_1t = pd.read_parquet(CAMINHO_CSV_AGREGADO).set_index(["sg_uf", "cd_municipio_tse"]).sort_index()

    json_1t = carregar_municipios_json("6257", "1t")
    json_2t = carregar_municipios_json("6258", "2t")
    json_1t.to_parquet(PASTA_CERTIFICACAO / "json_1t.parquet")
    json_2t.to_parquet(PASTA_CERTIFICACAO / "json_2t.parquet")
    validar_metadados(json_1t, "6257", "1")
    validar_metadados(json_2t, "6258", "2")

    colunas_votos_1t = [f"votos_1t_{numero}" for numero in NUMEROS_CANDIDATOS_1T]
    candidatos_json_1t = sorted(
        coluna for coluna in json_1t.columns if coluna.startswith("votos_1t_")
    )
    print("candidatos no JSON 1T:", candidatos_json_1t)
    print("candidatos no JSON 2T:", sorted(c for c in json_2t.columns if c.startswith("votos_2t_")))
    print("nulos nos votos JSON 1T:", int(json_1t[colunas_votos_1t].isna().sum().sum()))

    # Medicao 2: JSON 1T x CSV 1T
    colunas_csv = [coluna + "_1t" for coluna in CONTAGENS] + colunas_votos_1t
    colunas_json = CONTAGENS + colunas_votos_1t
    diferencas_m2 = descrever_divergencias(
        "MEDICAO 2: JSON1T (A) x CSV1T (B)", json_1t, csv_1t, colunas_json, colunas_csv
    )
    for coluna in colunas_json:
        if (diferencas_m2[coluna] != 0).any():
            mostrar_maiores_exemplos(diferencas_m2, coluna)
    diferencas_m2.to_parquet(PASTA_CERTIFICACAO / "dif_json1t_menos_csv1t.parquet")

    # Medicao 3: tabela 2T x JSON 2T
    colunas_tabela_2t = [coluna + "_2t" for coluna in CONTAGENS] + [
        f"votos_2t_{numero}" for numero in NUMEROS_CANDIDATOS_2T
    ]
    colunas_json_2t = CONTAGENS + [f"votos_2t_{numero}" for numero in NUMEROS_CANDIDATOS_2T]
    diferencas_m3 = descrever_divergencias(
        "MEDICAO 3: tabela2T (A) x JSON2T (B)", base, json_2t, colunas_tabela_2t, colunas_json_2t
    )
    for coluna in colunas_tabela_2t:
        if (diferencas_m3[coluna] != 0).any():
            mostrar_maiores_exemplos(diferencas_m3, coluna)

    # Tabela 1T x JSON 1T tambem (a base e a mesma do CSV, mas fecha o triangulo)
    descrever_divergencias(
        "TRIANGULO: tabela1T (A) x JSON1T (B)", base, json_1t, colunas_csv, colunas_json
    )

    # codigo IBGE da config JSON vs base
    ibge_base = base["cd_municipio_ibge"]
    ibge_json = json_1t["cd_municipio_ibge_json"]
    ibge_json_2t = json_2t["cd_municipio_ibge_json"]
    brasil = ~base["fl_exterior"].to_numpy()
    divergentes_ibge = (ibge_base[brasil].to_numpy() != ibge_json[brasil].to_numpy()).sum()
    divergentes_ibge_2t = (ibge_base[brasil].to_numpy() != ibge_json_2t[brasil].to_numpy()).sum()
    print(f"\nIBGE base x config JSON1T no Brasil: divergentes={int(divergentes_ibge)}; x JSON2T: {int(divergentes_ibge_2t)}")
    print("IBGE JSON no exterior (valores unicos):", sorted(ibge_json[~brasil].unique())[:5])

    analisar_aptos(base, json_1t, json_2t, csv_1t)


if __name__ == "__main__":
    main()
