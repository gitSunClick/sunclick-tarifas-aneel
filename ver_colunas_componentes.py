#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ver_colunas_componentes.py — mesma ideia do ver_colunas.py, mas pro
arquivo de componentes tarifários (usa o cache já baixado, não baixa de
novo). Ajuda a corrigir os nomes de coluna reais em aneel_lib.py.

Uso:
    python ver_colunas_componentes.py
"""

import os
import config
from aneel_lib import _ler_csv_flexivel

ano = config.ANO_COMPONENTES
caminho = os.path.join(config.PASTA_CACHE, f"componentes-tarifarias-{ano}.csv")
if not os.path.exists(caminho):
    print(f"Não encontrei {caminho}. Rode 'python descobrir_sigagente.py --componentes' "
          "primeiro pra baixar o arquivo.")
    raise SystemExit(1)

df = _ler_csv_flexivel(caminho)

print(f"{len(df.columns)} colunas encontradas:\n")
for c in df.columns:
    print(f"  - {c!r}")

# tenta achar a coluna que parece ser a sigla do agente, pra mostrar um exemplo
candidatas_sigla = [c for c in df.columns if "agente" in c.lower() or "sig" in c.lower()]
print(f"\nColunas candidatas a 'sigla do agente': {candidatas_sigla}")

if candidatas_sigla:
    col = candidatas_sigla[0]
    valores = sorted(df[col].dropna().unique().tolist())
    print(f"\n{len(valores)} valores únicos em {col!r} (10 primeiros): {valores[:10]}")
    if "CEEE-D" in valores:
        print(f"\nExemplo de linhas com {col} == 'CEEE-D':")
        print(df[df[col] == "CEEE-D"].head(5).to_string())

# tenta achar a coluna que parece listar o componente tarifário (ICMS/PIS/etc)
candidatas_componente = [c for c in df.columns if "component" in c.lower()]
print(f"\nColunas candidatas a 'componente tarifário': {candidatas_componente}")
if candidatas_componente:
    col = candidatas_componente[0]
    valores = sorted(df[col].dropna().unique().tolist())
    print(f"\n{len(valores)} valores únicos em {col!r}:")
    for v in valores:
        print(f"  - {v}")
