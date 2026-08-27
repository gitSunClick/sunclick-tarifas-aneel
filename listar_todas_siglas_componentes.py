#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lista TODOS os valores únicos de SigNomeAgente no arquivo de
componentes tarifários (usa o cache já baixado)."""
from aneel_lib import carregar_componentes_tarifarios

df = carregar_componentes_tarifarios()
valores = sorted(df["SigNomeAgente"].dropna().unique().tolist())
print(f"{len(valores)} valores únicos de SigNomeAgente:\n")
for v in valores:
    print(f"  - {v!r}")
