#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
descobrir_sigagente.py — passo 15.2 do handoff: inspecionar os valores
reais de SigAgente e de DscComponenteTarifario na base da ANEEL, e sugerir
o DE/PARA para as 31 distribuidoras de config.py.

Uso:
    python descobrir_sigagente.py                 # sugere SigAgente para cada distribuidora
    python descobrir_sigagente.py --listar-tudo    # lista todos os SigAgente únicos encontrados
    python descobrir_sigagente.py --componentes    # lista os rótulos únicos de DscComponenteTarifario

Isso NÃO escreve nada em config.py automaticamente — só sugere. Copie os
valores confirmados manualmente para o campo "sig_agente" de cada
distribuidora em config.py.
"""

import argparse
import difflib

import config
from aneel_lib import carregar_tarifas_homologadas, carregar_componentes_tarifarios, normalizar


def sugerir_mapeamento():
    print("Baixando/carregando base de tarifas homologadas (pode demorar na 1ª vez)...")
    df = carregar_tarifas_homologadas()
    valores_unicos = sorted(df["SigAgente"].dropna().unique().tolist())
    print(f"\n{len(valores_unicos)} valores únicos de SigAgente encontrados na base.\n")

    print(f"{'Nome interno (config.py)':35s} -> Sugestão de SigAgente (confira antes de aceitar!)")
    print("-" * 90)
    for dist in config.DISTRIBUIDORAS:
        nome = dist["nome_interno"]
        alvo_norm = normalizar(nome)
        # ranqueia todos os valores reais pela similaridade de string com o nome interno
        candidatos = difflib.get_close_matches(
            alvo_norm, [normalizar(v) for v in valores_unicos], n=3, cutoff=0.3
        )
        # mapeia de volta para a grafia original
        candidatos_originais = []
        for c in candidatos:
            for v in valores_unicos:
                if normalizar(v) == c and v not in candidatos_originais:
                    candidatos_originais.append(v)
                    break
        sugestao = " | ".join(candidatos_originais) if candidatos_originais else "(nenhum candidato próximo)"
        marcador = "  [já preenchido]" if dist.get("sig_agente") else ""
        print(f"{nome:35s} -> {sugestao}{marcador}")

    print(
        "\nATENÇÃO: isso é uma sugestão por similaridade de texto, não uma "
        "confirmação. Distribuidoras que trocaram de nome/grupo societário "
        "(comuns no setor elétrico) podem não bater com o nome antigo. "
        "Confirme cada uma antes de colar em config.py — o ideal é validar "
        "pelo menos a CEEE-RS contra o valor de controle "
        "(python validar_controle.py)."
    )


def listar_tudo():
    df = carregar_tarifas_homologadas()
    for v in sorted(df["SigAgente"].dropna().unique().tolist()):
        print(v)


def listar_componentes():
    df = carregar_componentes_tarifarios()
    print("Valores únicos de DscComponenteTarifario encontrados:\n")
    for v in sorted(df["DscComponenteTarifario"].dropna().unique().tolist()):
        print(v)
    print(
        "\nSe ICMS/PIS/COFINS/FIO B aparecerem escritos de forma diferente "
        "do esperado, ajuste config.COMPONENTES_DESEJADOS de acordo."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--listar-tudo", action="store_true")
    parser.add_argument("--componentes", action="store_true")
    args = parser.parse_args()

    if args.componentes:
        listar_componentes()
    elif args.listar_tudo:
        listar_tudo()
    else:
        sugerir_mapeamento()
