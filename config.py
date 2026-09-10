# -*- coding: utf-8 -*-
"""
config.py — toda a configuração editável do projeto fica aqui.

Duas coisas neste arquivo ainda precisam ser preenchidas por você antes do
script funcionar de ponta a ponta (nenhuma delas eu conseguia validar sem
acesso à sua planilha real / à base completa da ANEEL):

  1. SIG_AGENTE em cada distribuidora de DISTRIBUIDORAS — rode
     `python descobrir_sigagente.py` para eu (o script) sugerir o valor
     certo automaticamente a partir da base oficial.
  2. COLUNAS_PLANILHA — os nomes EXATOS das colunas na sua planilha do
     Google Sheets (copie exatamente como está no cabeçalho da planilha,
     incluindo maiúsculas/acentos/quebras de linha).
"""

# ---------------------------------------------------------------------------
# Fontes oficiais da ANEEL (Dados Abertos / CKAN)
# ---------------------------------------------------------------------------

# Base de tarifas homologadas (TUSD/TE por Sigla, Subgrupo, Modalidade,
# Classe, Subclasse, Detalhe, com vigência).
URL_TARIFAS_HOMOLOGADAS = (
    "https://dadosabertos.aneel.gov.br/dataset/5a583f3e-1646-4f67-bf0f-"
    "69db4203e89e/resource/fcf2906c-7c32-4b9b-a637-054e7a5234f4/download/"
    "tarifas-homologadas-distribuidoras-energia-eletrica.csv"
)

# Componentes tarifários (ICMS, PIS, COFINS, Fio B, Bandeira, etc.) —
# arquivo é por ano; ajuste ANO_COMPONENTES conforme necessário (o site
# publica um CSV por ano, ex.: componentes-tarifarias-2026.csv).
ANO_COMPONENTES = 2026
URL_COMPONENTES_TARIFARIOS_TEMPLATE = (
    "https://dadosabertos.aneel.gov.br/dataset/613e6b74-1a4b-4c48-a231-"
    "096815e96bd5/resource/e8717aa8-2521-453f-bf16-fbb9a16eea39/download/"
    "componentes-tarifarias-{ano}.csv"
)
# ATENÇÃO: o resource_id acima (e8717aa8-...) foi confirmado apenas para o
# arquivo de 2026. Se ANO_COMPONENTES mudar para outro ano, essa URL vai
# apontar para o arquivo errado — confirme a URL certa em
# https://dadosabertos.aneel.gov.br/dataset/componentes-tarifarias antes de
# trocar o ano.

# Pasta onde os CSVs baixados ficam em cache (evita rebaixar ~toda hora;
# arquivos são grandes). Apagar a pasta força um novo download.
PASTA_CACHE = "cache_aneel"
# 7 dias — subi bastante esse valor (era 20h) porque baixar esse arquivo
# (~90MB) repetidamente em pouco tempo parece disparar um bloqueio
# temporário no portal da ANEEL para o IP de quem baixa. Durante
# desenvolvimento/teste, prefira reaproveitar o cache; quando precisar
# forçar dados novos de propósito (ex.: rodar de verdade em produção),
# apague a pasta cache_aneel/ manualmente em vez de baixar toda hora.
VALIDADE_CACHE_HORAS = 24 * 7


# ---------------------------------------------------------------------------
# Regras de filtro tarifário (definidas no handoff, seção 3)
# ---------------------------------------------------------------------------
# Nomes de coluna confirmados em 26/08/2026 rodando contra o CSV real
# (ver_colunas.py) — divergem um pouco do dicionário de dados em PDF da
# ANEEL (ex.: DscBaseTarifa no PDF é DscBaseTarifaria no CSV real).

FILTRO_TUSD_TE = {
    "DscBaseTarifaria": "Tarifa de Aplicação",
    "DscSubGrupo": "B1",
    "DscModalidadeTarifaria": "Convencional",
    "DscClasse": "Residencial",
    "DscSubClasse": "Residencial",
    "DscDetalhe": "Não se aplica",
}

# Subgrupo A4 confirmado em 27/08/2026 contra a planilha de referência da
# Nathalia (aba ANEEL_BASE: Amazonas Energia, Subgrupo A4 + Geração, TUSD
# 13,74 — bate exatamente com a coluna TUSD G da aba TARIFAS_SUNCLICK). O
# handoff.docx original dizia A2; A4 é o que está validado na prática.
FILTRO_TUSD_G = {
    "DscBaseTarifaria": "Tarifa de Aplicação",
    "DscSubGrupo": "A4",
    "DscModalidadeTarifaria": "Geração",
}

# Rótulos procurados na coluna DscComponenteTarifario do arquivo de
# componentes tarifários. São "contém" (case/acento-insensível), não
# igualdade exata. Confirmados contra o CSV real em 26/08/2026 — os 41
# valores possíveis são todos variações de TUSD_* / TE_* (ex.: TUSD_FioB,
# TUSD_CDE, TE_PeD...).
#
# IMPORTANTE: ICMS, PIS e COFINS NÃO existem nesse arquivo (nem em nenhum
# outro dataset dos Dados Abertos da ANEEL — pesquisei e não há dataset
# de impostos lá). Faz sentido: ICMS é imposto estadual (cada estado
# publica o seu, não é algo que a ANEEL centraliza) e PIS/COFINS federal
# não é um "componente tarifário" da distribuidora nesse sentido. Por
# isso essas 3 colunas foram REMOVIDAS da extração automática — o script
# não mexe nelas na planilha (nem apaga, nem preenche). Se vocês tiverem
# outra fonte pra ICMS/PIS/COFINS (ex.: tabela interna, SEFAZ de cada
# estado), dá pra plugar depois como mais uma etapa separada.
COMPONENTES_DESEJADOS = {
    "fio_b": ["fiob"],  # "TUSD_FioB" na base real (sem espaço)
}

# Filtro extra pro Fio B (e, no futuro, outros componentes de B1 Residencial).
# Mesma combinação de FILTRO_TUSD_TE, mas com os nomes de coluna reais do
# arquivo de COMPONENTES tarifários (confirmado em 27/08/2026 rodando
# ver_fiob.py) — divergem dos nomes usados no arquivo de tarifas homologadas:
#   DscSubGrupo      -> DscSubGrupoTarifario
#   DscClasse        -> DscClasseConsumidor
#   DscSubClasse     -> DscSubClasseConsumidor
#   DscDetalhe       -> DscDetalheConsumidor
# Esse arquivo também tem uma coluna a mais (DscPostoTarifario: Ponta/Fora
# ponta/Intermediário/Não se aplica) que não existe no arquivo de tarifas
# homologadas — sem filtrar por ela, cada distribuidora tinha 3-4 "Fio B"
# vigentes ao mesmo tempo (um por posto tarifário) e a busca dava AMBIGUO
# pra quase todo mundo.
FILTRO_COMPONENTES_B1_RESIDENCIAL = {
    "DscBaseTarifaria": "Tarifa de Aplicação",
    "DscSubGrupoTarifario": "B1",
    "DscModalidadeTarifaria": "Convencional",
    "DscClasseConsumidor": "Residencial",
    "DscSubClasseConsumidor": "Residencial",
    "DscDetalheConsumidor": "Não se aplica",
    "DscPostoTarifario": "Não se aplica",
}


# ---------------------------------------------------------------------------
# Distribuidoras
# ---------------------------------------------------------------------------
# Lista substituída em 27/08/2026 pelos valores REAIS da coluna
# "Distribuidora" da planilha de referência da Nathalia (aba
# TARIFAS_SUNCLICK) — são 33 linhas, não as 31 do handoff.docx original.
# "nome_interno" tem que ser IDÊNTICO ao texto da célula na planilha
# (é a chave usada pra achar a linha certa) — não mude a grafia.
#
# A aba SOP dessa planilha (manual do processo antigo) menciona que a
# ANEEL renomeou várias distribuidoras (ex.: "Cemar" → "Equatorial MA" no
# De-Para do processo antigo) — por isso sig_agente pode ser bem
# diferente de nome_interno.
#
# Em 27/08/2026 a Nathalia colou a lista completa dos 116 SigAgente reais
# da base (rodando `descobrir_sigagente.py --listar-tudo`). Bati essa
# lista contra os 33 nomes abaixo à mão. A maioria eu marco como
# confirmada (bate exato ou é uma renomeação de aquisição bem conhecida
# do setor — ex. Equatorial comprou várias distribuidoras do Norte/
# Nordeste, Neoenergia comprou CEB e Celpe). MAS ainda não rodei
# `atualizar_google_sheets.py --dry-run` contra a base de verdade pra
# confirmar que cada uma tem tarifa vigente com esse sig_agente — isso é
# o próximo passo, e vai pegar qualquer erro aqui (aparece como
# SEM_TARIFA_VIGENTE se o código estiver errado).
#
# 4 casos ficaram com sig_agente=None de propósito — não tenho confiança
# pra adivinhar (ver observação em cada um):
DISTRIBUIDORAS = [
    {"nome_interno": "AmE", "uf": "AM", "sig_agente": "Âmbar Amazonas"},  # Amazonas Energia foi comprada pelo grupo Âmbar Energia
    {"nome_interno": "Ceal", "uf": "AL", "sig_agente": "EQUATORIAL AL"},  # Equatorial comprou a Ceal, renomeou Equatorial Alagoas
    {"nome_interno": "CEB-DIS", "uf": "DF", "sig_agente": "Neoenergia Brasília"},  # Neoenergia comprou a CEB
    {"nome_interno": "CEEE-D", "uf": "RS", "sig_agente": "CEEE-D"},  # controle: TUSD 478,63 / TE 343,37 — confirmado 26/08/2026
    {"nome_interno": "Celesc-DIS", "uf": "SC", "sig_agente": "CELESC"},
    {"nome_interno": "Celpa", "uf": "PA", "sig_agente": "EQUATORIAL PA"},  # Equatorial comprou a Celpa
    {"nome_interno": "Celpe", "uf": "PE", "sig_agente": "Neoenergia PE"},  # Neoenergia comprou a Celpe
    {"nome_interno": "Cemar", "uf": "MA", "sig_agente": "EQUATORIAL MA"},  # confirmado pela aba SOP da planilha
    {"nome_interno": "Cemig-D", "uf": "MG", "sig_agente": "CEMIG-D"},
    {"nome_interno": "Cepisa", "uf": "PI", "sig_agente": "EQUATORIAL PI"},  # Equatorial comprou a Cepisa
    {"nome_interno": "Energisa Rondônia", "uf": "RO", "sig_agente": "ERO"},  # era "Ceron" — renomeada na planilha em 09/2026 (Energisa comprou/renomeou a Ceron); sig_agente ERO confirmado 27/08/2026 continua valendo, a ANEEL não mudou o nome na base dela
    {"nome_interno": "Coelba", "uf": "BA", "sig_agente": "COELBA"},
    {"nome_interno": "Copel-DIS", "uf": "PR", "sig_agente": "COPEL-DIS"},
    {"nome_interno": "Cosern", "uf": "RN", "sig_agente": "COSERN"},
    {"nome_interno": "CPFL Paulista", "uf": "SP", "sig_agente": "CPFL-PAULISTA"},
    {"nome_interno": "CPFL Piratininga", "uf": "SP", "sig_agente": "CPFL-PIRATINING"},
    {"nome_interno": "CPFL Santa Cruz (agrupada)", "uf": "SP", "sig_agente": "CPFL Santa Cruz"},  # confirmado 27/08/2026 via print do portal ANEEL (coluna "Sigla") — não é agregação, existe sozinha na base como "CPFL Santa Cruz"
    {"nome_interno": "DMED", "uf": "MG", "sig_agente": "DMED"},
    {"nome_interno": "EDP ES", "uf": "ES", "sig_agente": "EDP ES"},
    {"nome_interno": "EDP SP", "uf": "SP", "sig_agente": "EDP SP"},
    {"nome_interno": "Elektro", "uf": "SP", "sig_agente": "ELEKTRO"},
    {"nome_interno": "EMS", "uf": "MS", "sig_agente": "EMS"},
    {"nome_interno": "EMT", "uf": "MT", "sig_agente": "EMT"},
    {"nome_interno": "Enel CE", "uf": "CE", "sig_agente": "ENEL CE"},
    {"nome_interno": "ENEL GO", "uf": "GO", "sig_agente": "EQUATORIAL GO"},  # confirmado 27/08/2026 rodando ver_sigla_tarifas.py contra o CSV real — Goiás foi comprada pela Equatorial, não pela Enel; o nome na planilha da Nathalia está desatualizado
    {"nome_interno": "Enel RJ", "uf": "RJ", "sig_agente": "ENEL RJ"},
    {"nome_interno": "Enel SP", "uf": "SP", "sig_agente": "ELETROPAULO"},  # confirmado 27/08/2026 rodando ver_sigla_tarifas.py contra o CSV real — "Enel SP" (visto no print do outro portal da ANEEL) não existe nesse dataset; o nome técnico ainda é o pré-rebranding "ELETROPAULO"
    {"nome_interno": "EPB", "uf": "PB", "sig_agente": "EPB"},
    {"nome_interno": "ESE", "uf": "SE", "sig_agente": "ESE"},
    {"nome_interno": "ESS (agrupada)", "uf": "SP", "sig_agente": "ESS"},  # confirmado 27/08/2026 rodando ver_sigla_tarifas.py contra o CSV real — não é agregação, existe sozinha na base como "ESS"
    {"nome_interno": "ETO", "uf": "TO", "sig_agente": "ETO"},
    {"nome_interno": "Light", "uf": "RJ", "sig_agente": "LIGHT SESA"},
    {"nome_interno": "RGE (agrupada)", "uf": "RS", "sig_agente": "RGE"},  # confirmado 27/08/2026 via print do portal ANEEL (coluna "Sigla") — não é agregação, existe sozinha na base como "RGE"
]

# Valor de controle validado visualmente no portal (handoff, seção 4) —
# usado por `validar_controle.py` / `atualizar_google_sheets.py --dry-run`
# para conferir se a extração está batendo com o portal antes de confiar
# nos outros 32 registros.
CONTROLE_VALIDACAO = {
    "nome_interno": "CEEE-D",
    "tusd_esperado": 478.63,
    "te_esperado": 343.37,
    "resolucao_esperada": "REH Nº 3.547, de 18 de novembro de 2025",
    "inicio_vigencia_esperado": "2026-01-01",
    "fim_vigencia_esperado": "2026-11-21",
}


# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------

# Nome exato da coluna, na sua planilha, que identifica a distribuidora
# (a "chave" citada no handoff). Ajuste para o nome real usado na sua
# planilha — eu não tive acesso a ela para confirmar.
COLUNA_CHAVE_PLANILHA = "Distribuidora"

# Mapa: campo interno -> nome EXATO do cabeçalho na sua planilha do Google
# Sheets. Os nomes abaixo são um ponto de partida baseado no handoff
# (seção 2) — confirme/ajuste para bater exatamente com sua planilha antes
# de rodar fora de DRY_RUN, porque o gspread só encontra a coluna se o
# texto for idêntico.
COLUNAS_PLANILHA = {
    "tusd": "TUSD",
    "te": "TE",
    "resolucao": "Resolução Homologatória",
    "inicio_vigencia": "Início de vigência",
    "tusd_g": "TUSD G - Gp A (<25kV) R$/ kW",
    "icms": "ICMS",
    "pis": "PIS",
    "cofins": "COFINS",
    "fio_b": "FIO B",
    # Coluna extra criada pelo script para registrar OK / pendências —
    # se não existir na planilha, o script cria automaticamente.
    "status": "Status atualização",
}
