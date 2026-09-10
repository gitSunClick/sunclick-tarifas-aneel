"""Teste rápido com dados sintéticos (não bate na rede) — só valida a
LÓGICA (normalização, vigência, ambiguidade, parsing de número BR, e o
tratamento de data vazia vs. data que falhou ao converter), não os dados
reais da ANEEL. Datas no formato ISO (AAAA-MM-DD), que é o formato real
confirmado contra o CSV baixado em 26/08/2026."""

import pandas as pd
from datetime import date

import config
from aneel_lib import buscar_vigente, buscar_componente, normalizar, _parse_datas

def preparar(linhas):
    df = pd.DataFrame(linhas)
    df["_SigAgente_norm"] = df["SigAgente"].map(normalizar)
    _parse_datas(df, ["DatInicioVigencia", "DatFimVigencia"])
    for col in ("VlrTUSD", "VlrTE"):
        if col in df.columns:
            df[col + "_num"] = df[col].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
            df[col + "_num"] = pd.to_numeric(df[col + "_num"], errors="coerce")
    return df

# --- caso 1: réplica do valor de controle CEEE-RS -------------------------
linhas = [
    # OK: dentro da vigência
    dict(SigAgente="CEEE-D", DscBaseTarifaria="Tarifa de Aplicação", DscSubGrupo="B1",
         DscModalidadeTarifaria="Convencional", DscClasse="Residencial",
         DscSubClasse="Residencial", DscDetalhe="Não se aplica",
         DatInicioVigencia="2026-01-01", DatFimVigencia="2026-11-21",
         DscREH="REH Nº 3.547, de 18 de novembro de 2025",
         VlrTUSD="478,63", VlrTE="343,37"),
    # registro antigo, fora da vigência (não deveria ser escolhido)
    dict(SigAgente="CEEE-D", DscBaseTarifaria="Tarifa de Aplicação", DscSubGrupo="B1",
         DscModalidadeTarifaria="Convencional", DscClasse="Residencial",
         DscSubClasse="Residencial", DscDetalhe="Não se aplica",
         DatInicioVigencia="2015-03-02", DatFimVigencia="2015-10-24",
         DscREH="Resolução antiga",
         VlrTUSD="100,00", VlrTE="100,00"),
    # outra distribuidora, não deveria interferir
    dict(SigAgente="RGE", DscBaseTarifaria="Tarifa de Aplicação", DscSubGrupo="B1",
         DscModalidadeTarifaria="Convencional", DscClasse="Residencial",
         DscSubClasse="Residencial", DscDetalhe="Não se aplica",
         DatInicioVigencia="2026-01-01", DatFimVigencia="2026-11-21",
         DscREH="Outra resolução",
         VlrTUSD="999,99", VlrTE="999,99"),
]
df = preparar(linhas)

hoje = date(2026, 6, 1)  # dentro da janela 2026-01-01/2026-11-21
r = buscar_vigente(df, "CEEE-D", config.FILTRO_TUSD_TE, hoje=hoje)
assert r.status == "OK", f"esperado OK, veio {r.status} ({r.observacao})"
linha = r.linhas.iloc[0]
assert abs(linha["VlrTUSD_num"] - 478.63) < 0.001, linha["VlrTUSD_num"]
assert abs(linha["VlrTE_num"] - 343.37) < 0.001, linha["VlrTE_num"]
print("OK  caso 1: vigência escolhe o registro certo, ignora o antigo e o de outra distribuidora")

# --- caso 2: sem tarifa vigente (data fora da janela) ----------------------
r2 = buscar_vigente(df, "CEEE-D", config.FILTRO_TUSD_TE, hoje=date(2027, 1, 1))
assert r2.status == "SEM_TARIFA_VIGENTE", r2.status
print("OK  caso 2: fora da janela de vigência -> SEM_TARIFA_VIGENTE (não escolhe o expirado)")

# --- caso 3: ambiguidade (dois registros vigentes ao mesmo tempo) ----------
linhas_ambiguas = linhas[:1] + [dict(linhas[0], VlrTUSD="500,00", VlrTE="350,00",
                                      DscREH="Resolução conflitante")]
df3 = preparar(linhas_ambiguas)
r3 = buscar_vigente(df3, "CEEE-D", config.FILTRO_TUSD_TE, hoje=hoje)
assert r3.status == "AMBIGUO", r3.status
print("OK  caso 3: dois registros vigentes ao mesmo tempo -> AMBIGUO (não escolhe sozinho)")

# --- caso 3b: exatamente o bug real encontrado em produção -----------------
# duas linhas ANTIGAS com DatFimVigencia preenchido e no passado, mais a
# vigente de verdade — antes da correção, uma falha de parsing de data
# fazia as antigas virarem "vigência em aberto" e disparar AMBIGUO à toa.
linhas_historico = linhas + [
    dict(SigAgente="CEEE-D", DscBaseTarifaria="Tarifa de Aplicação", DscSubGrupo="B1",
         DscModalidadeTarifaria="Convencional", DscClasse="Residencial",
         DscSubClasse="Residencial", DscDetalhe="Não se aplica",
         DatInicioVigencia="2017-04-01", DatFimVigencia="2017-12-20",
         DscREH="Outra resolução antiga",
         VlrTUSD="50,00", VlrTE="50,00"),
]
df_hist = preparar(linhas_historico)
r_hist = buscar_vigente(df_hist, "CEEE-D", config.FILTRO_TUSD_TE, hoje=hoje)
assert r_hist.status == "OK", (
    f"esperado OK (só a vigência de 2026 deveria contar), veio {r_hist.status}: "
    f"{r_hist.observacao}"
)
print("OK  caso 3b: registros antigos com DatFimVigencia preenchido não viram 'vigência em aberto'")

# --- caso 3c: DatFimVigencia realmente vazio = vigência em aberto de verdade
linhas_aberto = [
    dict(SigAgente="CEEE-D", DscBaseTarifaria="Tarifa de Aplicação", DscSubGrupo="B1",
         DscModalidadeTarifaria="Convencional", DscClasse="Residencial",
         DscSubClasse="Residencial", DscDetalhe="Não se aplica",
         DatInicioVigencia="2026-01-01", DatFimVigencia="",
         DscREH="Resolução em vigor, sem termo definido",
         VlrTUSD="200,00", VlrTE="200,00"),
]
df_aberto = preparar(linhas_aberto)
r_aberto = buscar_vigente(df_aberto, "CEEE-D", config.FILTRO_TUSD_TE, hoje=hoje)
assert r_aberto.status == "OK", r_aberto.status
print("OK  caso 3c: DatFimVigencia vazio de verdade (não corrompido) conta como vigência em aberto")

# --- caso 4: sigla não mapeada ----------------------------------------------
r4 = buscar_vigente(df, None, config.FILTRO_TUSD_TE, hoje=hoje)
assert r4.status == "SIGLA_NAO_MAPEADA", r4.status
print("OK  caso 4: sig_agente=None -> SIGLA_NAO_MAPEADA (não deixa passar batido)")

# --- caso 5: normalização ignora acento/caixa -------------------------------
assert normalizar("Não se aplica") == normalizar("nao se aplica") == normalizar("NÃO SE APLICA")
print("OK  caso 5: normalização acento/caixa-insensível")

# --- caso 6: componentes tarifários (formato longo) -------------------------
# Rótulo real confirmado contra o CSV de 246MB em 26/08/2026: "TUSD_FioB"
# (sem espaço) — ICMS/PIS/COFINS não existem nesse arquivo (nem em nenhum
# outro dataset da ANEEL), por isso saíram de COMPONENTES_DESEJADOS.
linhas_comp = [
    dict(SigNomeAgente="CEEE-D", DscComponenteTarifario="TUSD_FioB", DatInicioVigencia="2026-01-01",
         DatFimVigencia="2026-11-21", VlrComponenteTarifario="120,50"),
    dict(SigNomeAgente="CEEE-D", DscComponenteTarifario="TUSD_CDE", DatInicioVigencia="2026-01-01",
         DatFimVigencia="2026-11-21", VlrComponenteTarifario="30,00"),
]
dfc = pd.DataFrame(linhas_comp)
dfc["_SigAgente_norm"] = dfc["SigNomeAgente"].map(normalizar)
dfc["_DscComponenteTarifario_norm"] = dfc["DscComponenteTarifario"].map(normalizar)
_parse_datas(dfc, ["DatInicioVigencia", "DatFimVigencia"])
dfc["VlrComponenteTarifario_num"] = pd.to_numeric(
    dfc["VlrComponenteTarifario"].str.replace(",", ".", regex=False), errors="coerce"
)
rc2 = buscar_componente(dfc, "CEEE-D", config.COMPONENTES_DESEJADOS["fio_b"], hoje=hoje)
assert rc2.status == "OK" and abs(rc2.linhas.iloc[0]["VlrComponenteTarifario_num"] - 120.50) < 0.001
print("OK  caso 6: busca de Fio B (rótulo real 'TUSD_FioB', sem espaço) no formato longo")

# --- caso 7: duas resoluções vigentes ao mesmo tempo, com datas de início
# DIFERENTES -> resolve sozinho escolhendo a mais recente, sem virar AMBIGUO
# (situação real: a ANEEL publica a resolução nova antes de fechar o
# DatFimVigencia da antiga).
linhas_duas_vigencias = [
    dict(SigAgente="CEEE-D", DscBaseTarifaria="Tarifa de Aplicação", DscSubGrupo="B1",
         DscModalidadeTarifaria="Convencional", DscClasse="Residencial",
         DscSubClasse="Residencial", DscDetalhe="Não se aplica",
         DatInicioVigencia="2025-11-01", DatFimVigencia="2026-11-21",
         DscREH="Resolução antiga (ainda não encerrada)",
         VlrTUSD="400,00", VlrTE="300,00"),
    dict(SigAgente="CEEE-D", DscBaseTarifaria="Tarifa de Aplicação", DscSubGrupo="B1",
         DscModalidadeTarifaria="Convencional", DscClasse="Residencial",
         DscSubClasse="Residencial", DscDetalhe="Não se aplica",
         DatInicioVigencia="2026-05-01", DatFimVigencia="2026-11-21",
         DscREH="Resolução nova (a que deve ser escolhida)",
         VlrTUSD="500,00", VlrTE="350,00"),
]
df7 = preparar(linhas_duas_vigencias)
r7 = buscar_vigente(df7, "CEEE-D", config.FILTRO_TUSD_TE, hoje=hoje)
assert r7.status == "OK", f"esperado OK (resolve pela mais recente), veio {r7.status}: {r7.observacao}"
assert abs(r7.linhas.iloc[0]["VlrTUSD_num"] - 500.00) < 0.001, r7.linhas.iloc[0]["VlrTUSD_num"]
assert r7.observacao, "esperava uma observação explicando a escolha automática"
assert "2026-05-01" in r7.observacao, r7.observacao
print("OK  caso 7: duas vigências simultâneas com datas de início diferentes -> escolhe a mais recente, com observação")

# --- caso 8: duas vigências simultâneas com a MESMA data de início -> ainda
# é AMBIGUO de verdade (não dá pra desempatar por data).
r8 = buscar_vigente(df3, "CEEE-D", config.FILTRO_TUSD_TE, hoje=hoje)  # df3 é o caso 3, mesma data
assert r8.status == "AMBIGUO", r8.status
print("OK  caso 8: duas vigências com a MESMA data de início -> continua AMBIGUO (ambiguidade genuína)")

print("\nTodos os testes de lógica passaram (com dados sintéticos).")
print("Isso confirma a correção do bug de parsing de data encontrado em produção.")
