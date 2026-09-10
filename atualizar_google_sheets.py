#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
atualizar_google_sheets.py — extrai as tarifas vigentes das 31
distribuidoras e atualiza a planilha do Google Sheets (por nome de coluna,
sem recriar a tabela e sem apagar valores em caso de pendência).

ANTES DE RODAR ISTO:
  1. python descobrir_sigagente.py         → preencher sig_agente em config.py
  2. python validar_controle.py            → confirmar que bate com o portal (CEEE-RS)
  3. Conferir config.COLUNA_CHAVE_PLANILHA e config.COLUNAS_PLANILHA contra
     o cabeçalho real da sua planilha.

Variáveis de ambiente:
  GOOGLE_APPS_SCRIPT_URL         MÉTODO RECOMENDADO (evita totalmente o
                                 Google Cloud Console e a política
                                 "iam.disableServiceAccountKeyCreation"):
                                 URL do Web App do Apps Script vinculado à
                                 sua planilha (veja apps_script/Code.gs e
                                 apps_script/LEIA-ME.md). Quando definida,
                                 o script escreve via HTTP POST nesse Web
                                 App em vez de usar gspread/credenciais do
                                 Google Cloud.
  GOOGLE_APPS_SCRIPT_TOKEN       token secreto que você mesma define no
                                 topo do Code.gs, pra que só este script
                                 consiga escrever na planilha através do
                                 Web App (obrigatório junto com a URL
                                 acima).
  GOOGLE_SERVICE_ACCOUNT_FILE   caminho do JSON da service account
                                 (padrão: service_account.json nesta pasta)
                                 — só funciona se sua organização permitir
                                 criar chave de conta de serviço. Só é
                                 usado se GOOGLE_APPS_SCRIPT_URL e
                                 GOOGLE_OAUTH_CLIENT_FILE não estiverem
                                 definidos.
  GOOGLE_OAUTH_CLIENT_FILE       ALTERNATIVA ao acima, pra quando a política
                                 "iam.disableServiceAccountKeyCreation" da
                                 organização bloqueia a chave de conta de
                                 serviço: caminho do JSON de um OAuth Client
                                 ID tipo "Aplicativo para computador" (esse
                                 tipo de credencial não é bloqueado pela
                                 política). Na primeira execução abre o
                                 navegador pra você logar com sua própria
                                 conta Google e autorizar; depois disso fica
                                 salvo em GOOGLE_OAUTH_TOKEN_FILE e não pede
                                 login de novo. Com esse método você usa sua
                                 própria conta (que já tem acesso à
                                 planilha) — não precisa compartilhar nada
                                 com email de robô. Só é usado se
                                 GOOGLE_APPS_SCRIPT_URL não estiver
                                 definida.
  GOOGLE_OAUTH_TOKEN_FILE         onde salvar o token OAuth já autorizado
                                 (padrão: gspread_authorized_user.json
                                 nesta pasta). Não precisa existir na
                                 primeira vez.
  GOOGLE_SHEET_ID                ID da planilha — obrigatório apenas nos
                                 métodos gspread (service account/OAuth).
                                 Não é usado no método Apps Script, porque
                                 o Web App já roda vinculado à planilha.
  GOOGLE_WORKSHEET                nome exato da aba (obrigatório em
                                 qualquer método).
  DRY_RUN                        "true" (padrão) ou "false" — com true,
                                 só imprime o que mudaria, não escreve nada.

Uso:
    DRY_RUN=true  python atualizar_google_sheets.py   # sempre rode assim primeiro
    DRY_RUN=false python atualizar_google_sheets.py   # só depois de conferir o preview
"""

import os
import sys
from datetime import date

import config
from aneel_lib import (
    buscar_componente,
    buscar_vigente,
    carregar_componentes_tarifarios,
    carregar_tarifas_homologadas,
)

DRY_RUN = os.environ.get("DRY_RUN", "true").strip().lower() != "false"
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "service_account.json"),
)
GOOGLE_OAUTH_CLIENT_FILE = os.environ.get("GOOGLE_OAUTH_CLIENT_FILE")
GOOGLE_OAUTH_TOKEN_FILE = os.environ.get(
    "GOOGLE_OAUTH_TOKEN_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "gspread_authorized_user.json"),
)
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
GOOGLE_WORKSHEET = os.environ.get("GOOGLE_WORKSHEET")
GOOGLE_APPS_SCRIPT_URL = os.environ.get("GOOGLE_APPS_SCRIPT_URL")
GOOGLE_APPS_SCRIPT_TOKEN = os.environ.get("GOOGLE_APPS_SCRIPT_TOKEN")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def extrair_distribuidora(dist, df_tarifas, df_componentes, hoje):
    """Devolve um dict {campo_interno: valor} + status/observação para uma
    distribuidora. Nunca lança exceção — problemas viram status/observação
    para não interromper as outras 30."""
    nome = dist["nome_interno"]
    sig = dist.get("sig_agente")

    r_tusd_te = buscar_vigente(df_tarifas, sig, config.FILTRO_TUSD_TE, hoje)
    if r_tusd_te.status != "OK":
        return {
            "nome_interno": nome,
            "status": r_tusd_te.status,
            "observacao": r_tusd_te.observacao,
            "valores": {},
        }

    linha = r_tusd_te.linhas.iloc[0]
    valores = {
        "tusd": linha["VlrTUSD_num"],
        "te": linha["VlrTE_num"],
        "resolucao": linha.get("DscREH", ""),
        "inicio_vigencia": linha.get("DatInicioVigencia", ""),
    }

    # Notas de desambiguação (quando duas resoluções estavam vigentes ao
    # mesmo tempo e a lib escolheu a mais recente sozinha) não podem ser
    # descartadas silenciosamente — viram parte da observação final, pra
    # ficar visível na planilha que uma escolha automática foi feita.
    notas = []
    if r_tusd_te.observacao:
        notas.append(f"TUSD/TE: {r_tusd_te.observacao}")

    r_tusd_g = buscar_vigente(df_tarifas, sig, config.FILTRO_TUSD_G, hoje)
    if r_tusd_g.status == "OK":
        valores["tusd_g"] = r_tusd_g.linhas.iloc[0]["VlrTUSD_num"]
        if r_tusd_g.observacao:
            notas.append(f"TUSD-G: {r_tusd_g.observacao}")
    else:
        valores["tusd_g"] = None  # não encontrado não é erro fatal aqui, só fica em branco

    status_componentes = []
    for campo, rotulos in config.COMPONENTES_DESEJADOS.items():
        r = buscar_componente(
            df_componentes, sig, rotulos,
            filtros_extra=config.FILTRO_COMPONENTES_B1_RESIDENCIAL,
            hoje=hoje,
        )
        if r.status == "OK":
            valores[campo] = r.linhas.iloc[0]["VlrComponenteTarifario_num"]
            if r.observacao:
                notas.append(f"{campo}: {r.observacao}")
        else:
            valores[campo] = None
            status_componentes.append(f"{campo}:{r.status}")

    if status_componentes:
        notas.append("; ".join(status_componentes))

    observacao = " | ".join(notas)
    return {
        "nome_interno": nome,
        "status": "OK",
        "observacao": observacao,
        "valores": valores,
    }


def imprimir_preview(resultados):
    print("\n" + "=" * 100)
    print("PREVIEW (nada foi escrito no Google Sheets ainda)")
    print("=" * 100)
    for r in resultados:
        print(f"\n{r['nome_interno']}  ->  status: {r['status']}")
        if r["observacao"]:
            print(f"   observação: {r['observacao']}")
        for campo, valor in r["valores"].items():
            print(f"   {campo:20s} = {valor}")

    total = len(resultados)
    ok = sum(1 for r in resultados if r["status"] == "OK")
    print(f"\n{ok}/{total} distribuidoras com tarifa vigente encontrada.")
    pendentes = [r for r in resultados if r["status"] != "OK"]
    if pendentes:
        print(f"{len(pendentes)} pendência(s) — essas linhas NÃO terão os valores de tarifa "
              f"tocados na planilha, só a coluna de status:")
        for r in pendentes:
            print(f"   - {r['nome_interno']}: {r['status']} ({r['observacao']})")


def _autorizar_gspread():
    """Devolve um cliente gspread já autorizado. Usa OAuth (login com a
    própria conta Google) se GOOGLE_OAUTH_CLIENT_FILE estiver definido —
    necessário quando a política de organização
    "iam.disableServiceAccountKeyCreation" bloqueia a criação de chave de
    conta de serviço. Caso contrário, usa o fluxo antigo de service account."""
    import gspread

    if GOOGLE_OAUTH_CLIENT_FILE:
        if not os.path.exists(GOOGLE_OAUTH_CLIENT_FILE):
            print(
                f"ERRO: credencial OAuth não encontrada em '{GOOGLE_OAUTH_CLIENT_FILE}'. "
                f"Confira o caminho em GOOGLE_OAUTH_CLIENT_FILE."
            )
            sys.exit(1)
        # gspread.oauth() já devolve um cliente autorizado (não precisa de
        # gspread.authorize() depois). Na primeira execução abre o navegador
        # pra login/consentimento; nas próximas usa o token salvo em
        # GOOGLE_OAUTH_TOKEN_FILE sem pedir login de novo.
        return gspread.oauth(
            scopes=SCOPES,
            credentials_filename=GOOGLE_OAUTH_CLIENT_FILE,
            authorized_user_filename=GOOGLE_OAUTH_TOKEN_FILE,
        )

    from google.oauth2.service_account import Credentials

    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        print(
            f"ERRO: credencial não encontrada em '{GOOGLE_SERVICE_ACCOUNT_FILE}'. "
            f"Se sua organização bloqueia a criação de chave de conta de serviço, "
            f"defina GOOGLE_OAUTH_CLIENT_FILE em vez disso. Veja o README."
        )
        sys.exit(1)

    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _montar_linhas_apps_script(resultados):
    """Converte os resultados internos em uma lista de {chave, status_texto,
    campos: {nome_coluna: valor}} — já com os nomes de coluna reais (via
    config.COLUNAS_PLANILHA), pra o Apps Script não precisar conhecer
    config.py."""
    linhas = []
    for r in resultados:
        campos = {}
        if r["status"] == "OK":
            for campo, valor in r["valores"].items():
                if valor is None:
                    continue
                nome_coluna = config.COLUNAS_PLANILHA.get(campo)
                if nome_coluna:
                    campos[nome_coluna] = valor
        texto_status = r["status"] if r["status"] == "OK" else f"{r['status']}: {r['observacao']}"
        linhas.append({
            "chave": r["nome_interno"],
            "status_texto": texto_status,
            "campos": campos,
        })
    return linhas


def escrever_via_apps_script(resultados):
    """Escreve na planilha via HTTP POST num Web App do Apps Script
    vinculado à planilha — não usa gspread nem credenciais do Google Cloud
    (contorna totalmente a política iam.disableServiceAccountKeyCreation).
    Veja apps_script/Code.gs e apps_script/LEIA-ME.md."""
    import requests

    if not GOOGLE_APPS_SCRIPT_TOKEN:
        print(
            "ERRO: GOOGLE_APPS_SCRIPT_URL está definida mas GOOGLE_APPS_SCRIPT_TOKEN não. "
            "Defina o mesmo token secreto que você colocou no topo do Code.gs."
        )
        sys.exit(1)
    if not GOOGLE_WORKSHEET:
        print("ERRO: defina GOOGLE_WORKSHEET antes de rodar com DRY_RUN=false.")
        sys.exit(1)

    payload = {
        "token": GOOGLE_APPS_SCRIPT_TOKEN,
        "worksheet": GOOGLE_WORKSHEET,
        "coluna_chave": config.COLUNA_CHAVE_PLANILHA,
        "coluna_status": config.COLUNAS_PLANILHA["status"],
        "linhas": _montar_linhas_apps_script(resultados),
    }

    resp = requests.post(GOOGLE_APPS_SCRIPT_URL, json=payload, timeout=120)
    try:
        dados = resp.json()
    except ValueError:
        print(f"ERRO: resposta inesperada do Apps Script (status {resp.status_code}):\n{resp.text[:2000]}")
        sys.exit(1)

    if dados.get("erro"):
        print(f"ERRO retornado pelo Apps Script: {dados['erro']}")
        sys.exit(1)

    print(f"\n{dados.get('atualizadas', 0)} linha(s) atualizada(s) na planilha (via Apps Script).")
    naoencontradas = dados.get("nao_encontradas") or []
    if naoencontradas:
        print(
            f"{len(naoencontradas)} distribuidora(s) do config.py não foram encontradas na "
            f"coluna '{config.COLUNA_CHAVE_PLANILHA}' da planilha (nenhuma foi tocada): "
            f"{naoencontradas}"
        )


def escrever_via_gspread(resultados):
    if not GOOGLE_SHEET_ID or not GOOGLE_WORKSHEET:
        print("ERRO: defina GOOGLE_SHEET_ID e GOOGLE_WORKSHEET antes de rodar com DRY_RUN=false.")
        sys.exit(1)

    cliente = _autorizar_gspread()
    aba = cliente.open_by_key(GOOGLE_SHEET_ID).worksheet(GOOGLE_WORKSHEET)

    cabecalho = aba.row_values(1)
    if config.COLUNA_CHAVE_PLANILHA not in cabecalho:
        print(
            f"ERRO: a coluna-chave '{config.COLUNA_CHAVE_PLANILHA}' "
            f"(config.COLUNA_CHAVE_PLANILHA) não existe no cabeçalho da aba. "
            f"Cabeçalho encontrado: {cabecalho}"
        )
        sys.exit(1)

    col_chave_idx = cabecalho.index(config.COLUNA_CHAVE_PLANILHA) + 1
    chaves_planilha = aba.col_values(col_chave_idx)  # inclui o cabeçalho na posição 0

    # garante que a coluna de status existe (cria no final se faltar)
    col_status_nome = config.COLUNAS_PLANILHA["status"]
    if col_status_nome not in cabecalho:
        nova_col_idx = len(cabecalho) + 1
        aba.update_cell(1, nova_col_idx, col_status_nome)
        cabecalho.append(col_status_nome)

    naoencontradas = []
    atualizadas = 0
    for r in resultados:
        # procura a linha da distribuidora pela coluna-chave (tenta nome
        # interno exato primeiro; ajuste aqui se sua planilha usa outra
        # convenção, ex.: sigla oficial em vez do nome interno).
        try:
            linha_idx = chaves_planilha.index(r["nome_interno"]) + 1  # 1-based, já inclui cabeçalho
        except ValueError:
            naoencontradas.append(r["nome_interno"])
            continue

        # status sempre é atualizado
        col_status_idx = cabecalho.index(col_status_nome) + 1
        texto_status = r["status"] if r["status"] == "OK" else f"{r['status']}: {r['observacao']}"
        aba.update_cell(linha_idx, col_status_idx, texto_status)

        if r["status"] != "OK":
            # regra do handoff: nunca apagar valor existente numa pendência
            continue

        for campo, valor in r["valores"].items():
            if valor is None:
                continue
            nome_coluna = config.COLUNAS_PLANILHA.get(campo)
            if not nome_coluna or nome_coluna not in cabecalho:
                continue
            col_idx = cabecalho.index(nome_coluna) + 1
            aba.update_cell(linha_idx, col_idx, valor)
        atualizadas += 1

    print(f"\n{atualizadas} linha(s) atualizada(s) na planilha.")
    if naoencontradas:
        print(
            f"{len(naoencontradas)} distribuidora(s) do config.py não foram encontradas na "
            f"coluna '{config.COLUNA_CHAVE_PLANILHA}' da planilha (nenhuma foi tocada): "
            f"{naoencontradas}"
        )


def escrever_google_sheets(resultados):
    """Ponto de entrada único: escolhe o método de escrita disponível.
    Prioridade: Apps Script (recomendado, sem Google Cloud) > gspread
    (OAuth ou service account)."""
    if GOOGLE_APPS_SCRIPT_URL:
        escrever_via_apps_script(resultados)
    else:
        escrever_via_gspread(resultados)


def main():
    hoje = date.today()
    print(f"Data de referência para vigência: {hoje.isoformat()}")
    print(f"Modo: {'DRY RUN (nada será escrito)' if DRY_RUN else 'ESCRITA REAL no Google Sheets'}")

    sem_mapeamento = [d["nome_interno"] for d in config.DISTRIBUIDORAS if not d.get("sig_agente")]
    if sem_mapeamento:
        print(
            f"\nAVISO: {len(sem_mapeamento)} distribuidora(s) ainda sem SigAgente em config.py "
            f"(rode `python descobrir_sigagente.py`): {sem_mapeamento}\n"
        )

    print("Carregando bases oficiais da ANEEL...")
    df_tarifas = carregar_tarifas_homologadas()
    df_componentes = carregar_componentes_tarifarios()

    resultados = [
        extrair_distribuidora(dist, df_tarifas, df_componentes, hoje)
        for dist in config.DISTRIBUIDORAS
    ]

    imprimir_preview(resultados)

    if DRY_RUN:
        print("\nDRY_RUN ativo — nada foi escrito. Rode com DRY_RUN=false para gravar de verdade.")
        return

    resposta = input("\nConfirma a gravação na planilha real? [digite SIM] ")
    if resposta.strip().upper() != "SIM":
        print("Cancelado.")
        return

    escrever_google_sheets(resultados)


if __name__ == "__main__":
    main()
