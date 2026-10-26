"""Confere nm_urna_candidato e sg_partido da tabela longa contra o CSV (1T) e o JSON (2T).

Uso: python3 -I c07_nomes_candidatos.py
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

# Raiz do projeto, dois níveis acima de `certificacao/`: roda de qualquer clone.
PASTA_PROJETO = Path(__file__).resolve().parents[2]
CAMINHO_LONGA = PASTA_PROJETO / "dados" / "processados" / "presidente_municipio_candidato_long.parquet"
ZIP_CANDIDATOS = PASTA_PROJETO / "votacao_candidato_munzona_2026.zip"
MEMBRO_CANDIDATOS = "votacao_candidato_munzona_2026_BR.csv"
JSON_2T_EXEMPLO = PASTA_PROJETO / "dados" / "json_tse" / "6258" / "dados" / "rr" / "rr03077-c0001-e006258-u.json"


def main() -> None:
    """Compara pares (numero, nome de urna, partido) entre longa, CSV e JSON."""
    longa = pd.read_parquet(CAMINHO_LONGA)
    pares_longa = longa[["nr_turno", "nr_candidato", "nm_urna_candidato", "sg_partido"]].drop_duplicates()
    with zipfile.ZipFile(ZIP_CANDIDATOS) as arquivo_zip:
        with arquivo_zip.open(MEMBRO_CANDIDATOS) as fluxo:
            csv = pd.read_csv(fluxo, sep=";", encoding="latin-1", dtype=str)
    pares_csv = csv[["NR_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO"]].drop_duplicates()
    print("pares distintos no CSV:", len(pares_csv), "(esperado 12)")
    pares_csv["nr_candidato"] = pares_csv["NR_CANDIDATO"].astype(int)
    pares_csv = pares_csv.set_index("nr_candidato")
    longa_1t = pares_longa[pares_longa["nr_turno"] == 1].set_index("nr_candidato")
    divergentes_1t = 0
    for numero in longa_1t.index:
        nome_ok = longa_1t.loc[numero, "nm_urna_candidato"] == pares_csv.loc[numero, "NM_URNA_CANDIDATO"]
        partido_ok = longa_1t.loc[numero, "sg_partido"] == pares_csv.loc[numero, "SG_PARTIDO"]
        if not (nome_ok and partido_ok):
            divergentes_1t += 1
            print("DIVERGE 1T:", numero)
    print("1T: candidatos com nome/partido divergente do CSV:", divergentes_1t)
    documento = json.loads(JSON_2T_EXEMPLO.read_text(encoding="utf-8"))
    pares_json: dict[int, tuple[str, str]] = {}
    for agremiacao in documento["carg"][0]["agr"]:
        for partido in agremiacao["par"]:
            for candidato in partido["cand"]:
                pares_json[int(candidato["n"])] = (candidato["nmu"], partido["sg"])
    longa_2t = pares_longa[pares_longa["nr_turno"] == 2].set_index("nr_candidato")
    for numero in longa_2t.index:
        nome_json, partido_json = pares_json[numero]
        nome_longa = longa_2t.loc[numero, "nm_urna_candidato"]
        partido_longa = longa_2t.loc[numero, "sg_partido"]
        print(f"2T {numero}: longa=({nome_longa},{partido_longa}) json=({nome_json},{partido_json})")


if __name__ == "__main__":
    main()
