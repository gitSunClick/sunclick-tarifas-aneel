#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ver_sigla_tarifas.py — lista todos os valores únicos de SigAgente no
arquivo de TARIFAS HOMOLOGADAS (TUSD/TE) que CONTÊM um pedaço de texto
(case/acento insensível). Usa o cache já baixado.

Uso:
    python ver_sigla_tarifas.py ENEL
"""

import sys
from aneel_lib import carregar_tarifas_homologadas, normalizar

pedaco = sys.argv[1] if len(sys.argv) > 1 else "ENEL"

df = carregar_tarifas_homologadas()
pedaco_norm = normalizar(pedaco)

valores = sorted(df["SigAgente"].dropna().unique().tolist())
achados = [v for v in valores if pedaco_norm in normalizar(v)]

print(f"{len(achados)} valor(es) de SigAgente contendo {pedaco!r}:")
for v in achados:
    print(f"  - {v!r}")
