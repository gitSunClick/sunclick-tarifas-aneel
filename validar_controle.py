#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validar_controle.py — handoff, seção 15.3: "Reproduzir primeiro o registro
vigente de Equatorial CEEE e comparar com o portal" antes de confiar na
extração para as outras 30 distribuidoras.

Compara o que o script extrai da base oficial com o valor visto
manualmente no portal (config.CONTROLE_VALIDACAO):
  TUSD 478,63 | TE 343,37 | REH Nº 3.547 de 18/11/2025 | 01/01/2026–21/11/2026

Uso:
    python validar_controle.py
"""

import sys

import config
from aneel_lib import buscar_vigente, carregar_tarifas_homologadas


def main():
    alvo = config.CONTROLE_VALIDACAO
    dist = next(
        (d for d in config.DISTRIBUIDORAS if d["nome_interno"] == alvo["nome_interno"]),
        None,
    )
    if dist is None:
        print(f"ERRO: '{alvo['nome_interno']}' não está em config.DISTRIBUIDORAS.")
        sys.exit(1)
    if not dist.get("sig_agente"):
        print(
            f"ERRO: config.py ainda não tem o SigAgente de '{alvo['nome_interno']}' "
            "preenchido. Rode primeiro: python descobrir_sigagente.py"
        )
        sys.exit(1)

    print(f"Carregando base oficial e buscando '{alvo['nome_interno']}' "
          f"(SigAgente={dist['sig_agente']!r})...")
    df = carregar_tarifas_homologadas()
    resultado = buscar_vigente(df, dist["sig_agente"], config.FILTRO_TUSD_TE)

    print(f"\nStatus da busca: {resultado.status}")
    if resultado.observacao:
        print(f"Observação: {resultado.observacao}")

    if resultado.status != "OK":
        print("\nNão foi possível validar — veja as linhas candidatas abaixo (se houver):")
        colunas_debug = [
            c for c in ("SigAgente", "DscBaseTarifa", "DscSubgrupo", "DscModalidadeTarifaria",
                        "DscClasse", "DscSubClasse", "DscDetalhe", "DatInicioVigencia",
                        "DatFimVigencia", "VlrTusd", "VlrTe")
            if c in resultado.linhas.columns
        ]
        print(resultado.linhas[colunas_debug].to_string(index=False))
        sys.exit(1)

    linha = resultado.linhas.iloc[0]
    tusd_extraido = linha["VlrTUSD_num"]
    te_extraido = linha["VlrTE_num"]

    print("\nRegistro encontrado:")
    print(f"  TUSD ................. {tusd_extraido}")
    print(f"  TE .................... {te_extraido}")
    print(f"  Resolução ............. {linha.get('DscREH')}")
    print(f"  Início de vigência .... {linha.get('DatInicioVigencia')}")
    print(f"  Fim de vigência ....... {linha.get('DatFimVigencia')}")

    ok_tusd = abs(tusd_extraido - alvo["tusd_esperado"]) < 0.01
    ok_te = abs(te_extraido - alvo["te_esperado"]) < 0.01

    print("\n" + "=" * 60)
    if ok_tusd and ok_te:
        print("RESULTADO: PASSOU — bate com o valor de controle do portal.")
        print("Pode seguir para validar TUSD G e depois as outras distribuidoras.")
    else:
        print("RESULTADO: FALHOU — não bate com o valor de controle do portal.")
        print(f"  Esperado: TUSD {alvo['tusd_esperado']} / TE {alvo['te_esperado']}")
        print(f"  Extraído: TUSD {tusd_extraido} / TE {te_extraido}")
        print(
            "\nNão prossiga para as outras distribuidoras/Google Sheets até "
            "entender essa diferença (pode ser SigAgente errado, filtro "
            "errado, ou o portal ter atualizado desde a captura do valor "
            "de controle)."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
