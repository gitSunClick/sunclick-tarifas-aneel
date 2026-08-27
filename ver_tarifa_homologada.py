#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ver_tarifa_homologada.py — mostra TODAS as linhas do arquivo de tarifas
homologadas (TUSD/TE) para um sig_agente, sem aplicar filtro nenhum de
subgrupo/modalidade/classe. Usa o cache já baixado.

Uso:
    python ver_tarifa_homologada.py "Enel SP"
"""

import sys
import pandas as pd

from aneel_lib import carregar_tarifas_homologadas, normalizar

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

sig = sys.argv[1] if len(sys.argv) > 1 else "Enel SP"

df = carregar_tarifas_homologadas()
mask = df["_SigAgente_norm"] == normalizar(sig)
linhas = df[mask]

print(f"{len(linhas)} linha(s) encontradas para sig_agente={sig!r}:\n")
colunas_interessantes = [
    c for c in [
        "SigAgente", "DscBaseTarifaria", "DscSubGrupo", "DscModalidadeTarifaria",
        "DscClasse", "DscSubClasse", "DscDetalhe", "DatInicioVigencia",
        "DatFimVigencia", "DscREH", "VlrTUSD", "VlrTE",
    ] if c in linhas.columns
]
print(linhas[colunas_interessantes].to_string())
