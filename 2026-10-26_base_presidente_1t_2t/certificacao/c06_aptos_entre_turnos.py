"""Medicao 4 (aprofundamento): o que sustenta a diferenca de aptos 1T x 2T.

Fatos medidos:
    * distribuicao da diferenca aptos_2t - aptos_1t por municipio e por UF;
    * relacao com o arquivo de transferencia temporaria (TTE / voto em
      transito), que o TSE publica SOMENTE para o 1T (NR_TURNO == 1);
    * relacao com a variacao de comparecimento.

Uso: python3 -I c06_aptos_entre_turnos.py
"""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# Raiz do projeto, dois níveis acima de `certificacao/`: roda de qualquer clone.
PASTA_PROJETO = Path(__file__).resolve().parents[2]
CAMINHO_BASE = PASTA_PROJETO / "dados" / "processados" / "presidente_municipio_turnos.parquet"
ZIP_TTE = PASTA_PROJETO / "perfil_comparecimento_abstencao_eleitor_tte_2026.zip"
PASTA_JSON = PASTA_PROJETO / "dados" / "json_tse"
MEMBRO_TTE = "perfil_comparecimento_abstencao_eleitor_tte_2026.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
registro = logging.getLogger("c06")


def correlacao(serie_a: pd.Series, serie_b: pd.Series) -> float:
    """Correlacao de Pearson entre duas series alinhadas."""
    return float(np.corrcoef(serie_a.to_numpy(dtype="float64"), serie_b.to_numpy(dtype="float64"))[0, 1])


def ler_tte() -> pd.DataFrame:
    """Le o CSV de TTE (1T) e cria chaves de origem e destino."""
    with zipfile.ZipFile(ZIP_TTE) as arquivo_zip:
        with arquivo_zip.open(MEMBRO_TTE) as fluxo:
            tabela = pd.read_csv(fluxo, sep=";", encoding="latin-1", dtype=str)
    tabela["aptos_tte"] = pd.to_numeric(tabela["QT_APTOS_EM_TTE"]).astype("int64")
    tabela["chave_origem"] = tabela["SG_UF_ORIGEM"] + "|" + tabela["CD_MUNICIPIO_ORIGEM"].str.zfill(5)
    tabela["chave_destino"] = tabela["SG_UF_DESTINO"] + "|" + tabela["CD_MUNICIPIO_DESTINO"].str.zfill(5)
    registro.info("TTE: %d linhas; turnos=%s", len(tabela), sorted(tabela["NR_TURNO"].unique()))
    return tabela


def saldo_tte(tabela: pd.DataFrame, indice: pd.Index) -> pd.Series:
    """Saldo por municipio = aptos em TTE que chegam - aptos em TTE que saem."""
    entradas = tabela.groupby("chave_destino")["aptos_tte"].sum()
    saidas = tabela.groupby("chave_origem")["aptos_tte"].sum()
    saldo = entradas.sub(saidas, fill_value=0)
    return saldo.reindex(indice).fillna(0).astype("int64")


def ler_secoes_json(codigo_eleicao: str) -> pd.Series:
    """Total de secoes (s.ts) por municipio, lido direto dos JSONs oficiais."""
    caminho_config = PASTA_JSON / codigo_eleicao / "config" / f"mun-e00{codigo_eleicao}-cm.json"
    config = json.loads(caminho_config.read_text(encoding="utf-8"))
    total_por_chave: dict[str, int] = {}
    for bloco_uf in config["abr"]:
        uf_minuscula = bloco_uf["cd"]
        for municipio in bloco_uf["mu"]:
            codigo_tse = municipio["cd"]
            nome = f"{uf_minuscula}{codigo_tse}-c0001-e00{codigo_eleicao}-u.json"
            caminho = PASTA_JSON / codigo_eleicao / "dados" / uf_minuscula / nome
            documento = json.loads(caminho.read_text(encoding="utf-8"))
            total_por_chave[uf_minuscula.upper() + "|" + codigo_tse] = int(documento["s"]["ts"])
    return pd.Series(total_por_chave, dtype="int64")


def main() -> None:
    """Executa a analise."""
    base = pd.read_parquet(CAMINHO_BASE)
    base["chave"] = base["sg_uf"] + "|" + base["cd_municipio_tse"]
    base = base.set_index("chave")
    delta_aptos = base["aptos_2t"] - base["aptos_1t"]
    print("=== distribuicao de delta aptos (2T - 1T) ===")
    print("municipios com delta != 0:", int((delta_aptos != 0).sum()), "de", len(base))
    print("quantis do delta nos 3.779 diferentes:")
    print(delta_aptos[delta_aptos != 0].describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).to_string())
    print("delta unitario (+-1) em:", int((delta_aptos.abs() == 1).sum()), "municipios")

    print("\n=== saldo por UF (soma do delta) ===")
    saldo_por_uf = delta_aptos.groupby(base["sg_uf"]).sum()
    print(saldo_por_uf.to_dict())
    print("UFs com saldo != 0:", int((saldo_por_uf != 0).sum()), "de", len(saldo_por_uf))
    print("soma positiva por UF e negativa por UF (fluxo bruto):")
    positivos = delta_aptos.clip(lower=0).groupby(base["sg_uf"]).sum()
    negativos = delta_aptos.clip(upper=0).groupby(base["sg_uf"]).sum()
    print(pd.DataFrame({"mais": positivos, "menos": negativos}).T.to_string())

    print("\n=== delta aptos x delta comparecimento / abstencao ===")
    delta_comparecimento = base["comparecimento_2t"] - base["comparecimento_1t"]
    delta_abstencao = base["abstencao_2t"] - base["abstencao_1t"]
    print("corr(delta aptos, delta comparecimento)=%.4f" % correlacao(delta_aptos, delta_comparecimento))
    print("corr(delta aptos, delta abstencao)=%.4f" % correlacao(delta_aptos, delta_abstencao))
    print("delta aptos != delta (comparecimento+abstencao) em:", int(
        (delta_aptos != (delta_comparecimento + delta_abstencao)).sum()
    ), "municipios (deve ser 0 pela identidade interna)")

    print("\n=== TTE (somente 1T) ===")
    tabela_tte = ler_tte()
    print("aptos em TTE no 1T por tipo:", tabela_tte.groupby("DS_TIPO_TRANSFERENCIA")["aptos_tte"].sum().to_dict())
    print("total aptos em TTE 1T:", int(tabela_tte["aptos_tte"].sum()))
    chaves_tte = set(tabela_tte["chave_origem"]) | set(tabela_tte["chave_destino"])
    fora_da_base = chaves_tte - set(base.index)
    print("chaves TTE (origem/destino) fora da base:", len(fora_da_base))
    saldo_total = saldo_tte(tabela_tte, base.index)
    print("saldo TTE 1T (todos os tipos): municipios != 0:", int((saldo_total != 0).sum()),
          "| soma bruta |saldo|:", int(saldo_total.abs().sum()))
    print("corr(delta aptos, saldo TTE 1T total)=%.4f" % correlacao(delta_aptos, saldo_total))
    print("corr(delta aptos, -saldo TTE 1T total)=%.4f" % correlacao(delta_aptos, -saldo_total))
    for tipo in sorted(tabela_tte["DS_TIPO_TRANSFERENCIA"].unique()):
        recorte = tabela_tte[tabela_tte["DS_TIPO_TRANSFERENCIA"] == tipo]
        saldo_tipo = saldo_tte(recorte, base.index)
        print("tipo %-22s corr(delta aptos, saldo)=%+.4f  munic. com saldo!=0=%d" % (
            tipo, correlacao(delta_aptos, saldo_tipo), int((saldo_tipo != 0).sum())
        ))
    saldo_por_uf_tte = saldo_total.groupby(base["sg_uf"]).sum()
    print("saldo TTE 1T por UF (todos os tipos):", saldo_por_uf_tte.to_dict())

    print("\n=== delta aptos x numero de secoes (JSON s.ts) ===")
    secoes_1t = ler_secoes_json("6257").reindex(base.index)
    secoes_2t = ler_secoes_json("6258").reindex(base.index)
    delta_secoes = secoes_2t - secoes_1t
    print("municipios com delta secoes != 0:", int((delta_secoes != 0).sum()),
          "| soma delta secoes:", int(delta_secoes.sum()))
    print("corr(delta aptos, delta secoes)=%.4f" % correlacao(delta_aptos, delta_secoes))
    print("delta aptos != 0 com delta secoes == 0:", int(((delta_aptos != 0) & (delta_secoes == 0)).sum()))


if __name__ == "__main__":
    main()
