#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ver_sigla_componentes.py — lista todos os valores únicos de SigNomeAgente
no arquivo de componentes que CONTÊM um pedaço de texto (case/acento
insensível). Usa o cache já baixado.

Uso:
    python ver_sigla_componentes.py CEEE
"""

import sys
from aneel_lib import carregar_componentes_tarifarios, normalizar

pedaco = sys.argv[1] if len(sys.argv) > 1 else "CEEE"

df = carregar_componentes_tarifarios()
pedaco_norm = normalizar(pedaco)

valores = sorted(df["SigNomeAgente"].dropna().unique().tolist())
achados = [v for v in valores if pedaco_norm in normalizar(v)]

print(f"{len(achados)} valor(es) de SigNomeAgente contendo {pedaco!r}:")
for v in achados:
    print(f"  - {v!r}")
