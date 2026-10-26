"""Medicao 1: 1T da tabela x CSV bruto de dados abertos (celula a celula).

Reagrega os CSVs do TSE (dentro dos zips, sem extrair) por municipio com
codigo proprio e compara com as colunas de 1T da base. Tambem grava o 1T
reagregado em certificacao/csv_1t_agregado.parquet para a medicao 2.

Uso: python3 -I c02_tabela_x_csv_1t.py
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# Raiz do projeto, dois níveis acima de `certificacao/`: roda de qualquer clone.
PASTA_PROJETO = Path(__file__).resolve().parents[2]
PASTA_CERTIFICACAO = PASTA_PROJETO / "2026-10-26_base_presidente_1t_2t" / "certificacao"
CAMINHO_BASE = PASTA_PROJETO / "dados" / "processados" / "presidente_municipio_turnos.parquet"
ZIP_CANDIDATOS = PASTA_PROJETO / "votacao_candidato_munzona_2026.zip"
MEMBRO_CANDIDATOS = "votacao_candidato_munzona_2026_BR.csv"
ZIP_DETALHE = PASTA_PROJETO / "detalhe_votacao_munzona_2026.zip"
MEMBRO_DETALHE = "detalhe_votacao_munzona_2026_BR.csv"
CAMINHO_SAIDA_AGREGADO = PASTA_CERTIFICACAO / "csv_1t_agregado.parquet"

CODIGO_CARGO_PRESIDENTE = "1"
NUMEROS_CANDIDATOS = [13, 14, 16, 21, 22, 27, 29, 30, 35, 55, 70, 80]

# Coluna da base (sem sufixo de turno) -> coluna do CSV de detalhe.
MAPA_DETALHE = {
    "aptos": "QT_APTOS",
    "comparecimento": "QT_COMPARECIMENTO",
    "abstencao": "QT_ABSTENCOES",
    "nao_instaladas": "QT_ELEITORES_SECOES_NAO_INSTALADAS",
    "validos": "QT_TOTAL_VOTOS_VALIDOS",
    "brancos": "QT_VOTOS_BRANCOS",
    "nulos": "QT_TOTAL_VOTOS_NULOS",
}
COLUNA_VOTOS_CANDIDATO = "QT_VOTOS_NOMINAIS_VALIDOS"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
registro = logging.getLogger("c02")


def ler_csv_do_zip(caminho_zip: Path, membro: str) -> pd.DataFrame:
    """Le um CSV (latin-1, ';') de dentro de um zip, tudo como texto."""
    with zipfile.ZipFile(caminho_zip) as arquivo_zip:
        with arquivo_zip.open(membro) as fluxo:
            tabela = pd.read_csv(fluxo, sep=";", encoding="latin-1", dtype=str)
    registro.info("Lido %s::%s com %d linhas.", caminho_zip.name, membro, len(tabela))
    return tabela


def preparar_chave(tabela: pd.DataFrame) -> pd.DataFrame:
    """Filtra presidente e cria chave (sg_uf, cd_municipio_tse com 5 digitos)."""
    so_presidente = tabela[tabela["CD_CARGO"] == CODIGO_CARGO_PRESIDENTE].copy()
    so_presidente["sg_uf"] = so_presidente["SG_UF"]
    so_presidente["cd_municipio_tse"] = so_presidente["CD_MUNICIPIO"].str.zfill(5)
    return so_presidente


def agregar_detalhe(detalhe: pd.DataFrame) -> pd.DataFrame:
    """Soma as zonas de cada municipio nas 7 colunas de contagem."""
    copia = detalhe.copy()
    colunas_csv = list(MAPA_DETALHE.values())
    for coluna in colunas_csv:
        copia[coluna] = pd.to_numeric(copia[coluna], errors="raise").astype("int64")
    somas = copia.groupby(["sg_uf", "cd_municipio_tse"])[colunas_csv].sum()
    somas = somas.rename(columns={v: k + "_1t" for k, v in MAPA_DETALHE.items()})
    return somas


def agregar_candidatos(candidatos: pd.DataFrame) -> pd.DataFrame:
    """Soma votos nominais validos por municipio e candidato (colunas largas)."""
    copia = candidatos.copy()
    copia[COLUNA_VOTOS_CANDIDATO] = pd.to_numeric(
        copia[COLUNA_VOTOS_CANDIDATO], errors="raise"
    ).astype("int64")
    copia["nr_candidato"] = pd.to_numeric(copia["NR_CANDIDATO"], errors="raise").astype("int64")
    somas = copia.pivot_table(
        index=["sg_uf", "cd_municipio_tse"],
        columns="nr_candidato",
        values=COLUNA_VOTOS_CANDIDATO,
        aggfunc="sum",
        fill_value=0,
    )
    somas.columns = ["votos_1t_" + str(numero) for numero in somas.columns]
    return somas


def comparar_colunas(base: pd.DataFrame, referencia: pd.DataFrame, colunas: list[str]) -> list[str]:
    """Compara coluna a coluna (tolerancia zero) e devolve linhas de relatorio."""
    linhas: list[str] = []
    total_celulas_divergentes = 0
    for coluna in colunas:
        valores_base = base[coluna].to_numpy(dtype="int64")
        valores_ref = referencia[coluna].to_numpy(dtype="int64")
        divergentes = valores_base != valores_ref
        quantidade = int(divergentes.sum())
        total_celulas_divergentes += quantidade
        soma_absoluta = int(np.abs(valores_base - valores_ref).sum())
        linhas.append(f"{coluna}: divergentes={quantidade} soma_abs_dif={soma_absoluta}")
    linhas.append(f"TOTAL celulas divergentes: {total_celulas_divergentes} de {len(colunas) * len(base)}")
    return linhas


def main() -> None:
    """Executa a medicao 1."""
    base = pd.read_parquet(CAMINHO_BASE)
    base = base.set_index(["sg_uf", "cd_municipio_tse"])

    detalhe = preparar_chave(ler_csv_do_zip(ZIP_DETALHE, MEMBRO_DETALHE))
    candidatos = preparar_chave(ler_csv_do_zip(ZIP_CANDIDATOS, MEMBRO_CANDIDATOS))
    registro.info("Detalhe: %d linhas presidente; candidatos: %d.", len(detalhe), len(candidatos))

    candidatos_fora_da_lista = sorted(
        set(pd.to_numeric(candidatos["NR_CANDIDATO"]).unique()) - set(NUMEROS_CANDIDATOS)
    )
    registro.info("Candidatos no CSV fora dos 12 esperados: %s", candidatos_fora_da_lista)

    agregado_detalhe = agregar_detalhe(detalhe)
    agregado_candidatos = agregar_candidatos(candidatos)
    agregado = agregado_detalhe.join(agregado_candidatos, how="outer")
    registro.info("Municipios no CSV agregado: %d", len(agregado))

    chaves_base = set(base.index)
    chaves_csv = set(agregado.index)
    so_na_base = sorted(chaves_base - chaves_csv)
    so_no_csv = sorted(chaves_csv - chaves_base)
    registro.info("Chaves so na base: %d %s", len(so_na_base), so_na_base[:5])
    registro.info("Chaves so no CSV: %d %s", len(so_no_csv), so_no_csv[:5])
    nulos_no_agregado = int(agregado.isna().sum().sum())
    registro.info("Nulos no agregado do CSV: %d", nulos_no_agregado)

    agregado.reset_index().to_parquet(CAMINHO_SAIDA_AGREGADO, index=False)

    chaves_comuns = base.index.intersection(agregado.index)
    base_comum = base.loc[chaves_comuns]
    csv_comum = agregado.loc[chaves_comuns]

    colunas_1t = [coluna + "_1t" for coluna in MAPA_DETALHE]
    colunas_1t += ["votos_1t_" + str(numero) for numero in NUMEROS_CANDIDATOS]
    linhas = comparar_colunas(base_comum, csv_comum, colunas_1t)
    for linha in linhas:
        print(linha)

    # Anchoras nacionais do 1T a partir do CSV (independentes da tabela).
    print("CSV 1T soma nacional:", {coluna: int(csv_comum[coluna].sum()) for coluna in colunas_1t})


if __name__ == "__main__":
    main()
