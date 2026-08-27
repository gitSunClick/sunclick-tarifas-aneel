#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ver_fiob.py — diagnóstico: mostra TODAS as linhas de "Fio B" (contendo
"fiob" no rótulo) para uma distribuidora, com todas as colunas, pra
descobrir por que a busca está dando AMBIGUO ou SEM_TARIFA_VIGENTE em
praticamente todas as distribuidoras. Usa o cache já baixado (não baixa
de novo).

Uso:
    python ver_fiob.py [SIG_AGENTE]

Se não passar SIG_AGENTE, usa "CEEE-D" como padrão.
"""

import sys
import pandas as pd

import config
from aneel_lib import carregar_componentes_tarifarios, normalizar

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

sig = sys.argv[1] if len(sys.argv) > 1 else "CEEE-D"

df = carregar_componentes_tarifarios()

print(f"Colunas disponíveis no arquivo de componentes ({len(df.columns)}):")
for c in df.columns:
    print(f"  - {c}")

mask = df["_SigAgente_norm"] == normalizar(sig)
mask &= df["_DscComponenteTarifario_norm"].str.contains("FIOB", na=False)
linhas = df[mask]

print(f"\n{len(linhas)} linha(s) de 'Fio B' encontradas para sig_agente={sig!r}:\n")
# imprime só as colunas mais relevantes pra não poluir demais, mas todas as colunas existem no df
colunas_interessantes = [c for c in df.columns if c in linhas.columns and not c.startswith("_")]
print(linhas[colunas_interessantes].to_string())
