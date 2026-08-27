#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ver_colunas.py — imprime os nomes reais das colunas do CSV já baixado em
cache (não baixa de novo), e uma linha de exemplo da CEEE-D, para eu
conseguir corrigir os nomes de coluna usados em config.py/aneel_lib.py.

Uso:
    python ver_colunas.py
"""

import os
import config
from aneel_lib import _ler_csv_flexivel

caminho = os.path.join(
    config.PASTA_CACHE, "tarifas-homologadas-distribuidoras-energia-eletrica.csv"
)
if not os.path.exists(caminho):
    print(f"Não encontrei {caminho}. Rode 'python descobrir_sigagente.py' primeiro "
          "pra baixar o arquivo.")
    raise SystemExit(1)

df = _ler_csv_flexivel(caminho)

print(f"{len(df.columns)} colunas encontradas:\n")
for c in df.columns:
    print(f"  - {c!r}")

if "SigAgente" in df.columns:
    print("\nExemplo de linhas com SigAgente == 'CEEE-D':")
    sub = df[df["SigAgente"] == "CEEE-D"]
    print(f"({len(sub)} linhas encontradas)")
    if len(sub):
        print(sub.head(5).to_string())
else:
    print("\nAVISO: nem a coluna 'SigAgente' existe com esse nome exato — "
          "confira a lista de colunas acima.")
