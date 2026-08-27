# -*- coding: utf-8 -*-
"""
aneel_lib.py — baixar (com cache) e extrair dados da base oficial da ANEEL.

Implementa as regras do handoff:
  - Vigência: DatInicioVigencia <= hoje <= DatFimVigencia.
  - Nunca escolhe silenciosamente entre registros ambíguos.
  - Nunca apaga valor existente quando não há registro vigente válido —
    quem decide isso é quem CHAMA esta lib (ela só reporta o status).
"""

import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd
import requests

import config

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Normalização de texto (comparações case/acento-insensíveis)
# ---------------------------------------------------------------------------

def normalizar(texto) -> str:
    """Maiúsculas, sem acento, sem espaço duplicado/nas pontas. Usado para
    comparar valores de colunas de texto sem depender de a ANEEL usar
    exatamente a mesma grafia/capitalização do handoff."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    texto = str(texto).strip()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"\s+", " ", texto)
    return texto.upper()


# ---------------------------------------------------------------------------
# Download com cache local
# ---------------------------------------------------------------------------

def _baixar_com_cache(url: str, nome_arquivo: str) -> str:
    os.makedirs(config.PASTA_CACHE, exist_ok=True)
    caminho = os.path.join(config.PASTA_CACHE, nome_arquivo)

    if os.path.exists(caminho):
        idade_horas = (time.time() - os.path.getmtime(caminho)) / 3600
        if idade_horas < config.VALIDADE_CACHE_HORAS:
            print(f"[cache] usando {caminho} (baixado há {idade_horas:.1f}h)")
            return caminho

    # Arquivo grande (dezenas de MB) — em rede corporativa (VPN, antivírus
    # ou proxy que inspeciona HTTPS) não é raro a conexão cair no meio do
    # download. Tenta algumas vezes com espera crescente antes de desistir.
    tentativas = 4
    espera = 3
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            print(f"Baixando {url} ... (tentativa {tentativa}/{tentativas})")
            with requests.get(url, headers=HEADERS, stream=True, timeout=180) as resp:
                resp.raise_for_status()
                tmp = caminho + ".tmp"
                total = 0
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
                        total += len(chunk)
                os.replace(tmp, caminho)
            print(f"  salvo em {caminho} ({total / 1_000_000:.1f} MB)")
            return caminho
        except requests.exceptions.RequestException as exc:
            ultimo_erro = exc
            if tentativa < tentativas:
                print(f"  falhou ({exc.__class__.__name__}: {exc}) — tentando de novo em {espera}s...")
                time.sleep(espera)
                espera *= 2
    raise RuntimeError(
        f"Não consegui baixar {url} depois de {tentativas} tentativas. "
        f"Último erro: {ultimo_erro}. Se estiver numa rede corporativa "
        f"(VPN/antivírus/proxy que inspeciona HTTPS), tente numa rede "
        f"diferente, ou rode de novo mais tarde."
    )


def _parse_datas(df: pd.DataFrame, colunas: list) -> None:
    """Converte colunas de data para datetime, gravando o resultado em
    '<coluna>_dt'. Usa o formato ISO confirmado contra o CSV real
    (AAAA-MM-DD) em vez de deixar o pandas adivinhar — com um arquivo
    deste tamanho (dezenas de MB, registros desde ~2010), inferência
    automática de formato pode acertar parte das linhas e falhar
    silenciosamente (virar NaT) em outra parte, o que é perigoso aqui:
    uma data de fim de vigência que virou NaT por engano é tratada como
    "vigência em aberto" e o registro passa a competir com o vigente de
    verdade, gerando falso AMBIGUO (foi exatamente isso que aconteceu
    com dayfirst=True sem formato fixo)."""
    for col in colunas:
        if col not in df.columns:
            continue
        preenchidas = df[col].notna() & (df[col].str.strip() != "")
        convertido = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")

        falhas = preenchidas & convertido.isna()
        if falhas.any():
            n_falhas = int(falhas.sum())
            print(
                f"[aviso] {n_falhas} valor(es) de '{col}' não bateram com o "
                f"formato AAAA-MM-DD esperado — tentando novamente sem formato "
                f"fixo só para essas linhas (pode ser um formato antigo/diferente)."
            )
            convertido.loc[falhas] = pd.to_datetime(
                df.loc[falhas, col], dayfirst=True, errors="coerce"
            )
            ainda_falhando = preenchidas & convertido.isna()
            if ainda_falhando.any():
                print(
                    f"[aviso] {int(ainda_falhando.sum())} valor(es) de '{col}' "
                    f"continuam sem conseguir converter mesmo assim — NÃO vão "
                    f"ser tratados como 'sem data' (vigência em aberto); ficam "
                    f"de fora dos registros vigentes até isso ser investigado."
                )

        df[col + "_dt"] = convertido
        # Distingue "campo realmente vazio na fonte" (ex.: DatFimVigencia em
        # branco = vigência ainda em aberto, de propósito) de "veio
        # preenchido mas não consegui converter" (bug/formato inesperado —
        # não deve ser tratado como em aberto, ver buscar_vigente).
        df[col + "_vazio_na_origem"] = ~preenchidas


def _ler_csv_flexivel(caminho: str) -> pd.DataFrame:
    """CSVs públicos brasileiros variam em encoding/separador — tenta as
    combinações mais comuns até uma produzir mais de uma coluna."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        for sep in (";", ","):
            try:
                df = pd.read_csv(
                    caminho, encoding=encoding, sep=sep, dtype=str, low_memory=False
                )
                if df.shape[1] > 1:
                    return df
            except Exception:
                continue
    raise RuntimeError(f"Não consegui interpretar o CSV: {caminho}")


def carregar_tarifas_homologadas() -> pd.DataFrame:
    caminho = _baixar_com_cache(
        config.URL_TARIFAS_HOMOLOGADAS,
        "tarifas-homologadas-distribuidoras-energia-eletrica.csv",
    )
    df = _ler_csv_flexivel(caminho)
    df["_SigAgente_norm"] = df.get("SigAgente", "").map(normalizar)
    _parse_datas(df, ["DatInicioVigencia", "DatFimVigencia"])
    # VlrTUSD / VlrTE: nomes confirmados contra o CSV real em 26/08/2026
    # (o dicionário de dados em PDF da ANEEL usava VlrTusd/VlrTe, minúsculo).
    for col in ("VlrTUSD", "VlrTE"):
        if col in df.columns:
            df[col + "_num"] = (
                df[col].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
            )
            df[col + "_num"] = pd.to_numeric(df[col + "_num"], errors="coerce")
    return df


def carregar_componentes_tarifarios(ano: Optional[int] = None) -> pd.DataFrame:
    ano = ano or config.ANO_COMPONENTES
    url = config.URL_COMPONENTES_TARIFARIOS_TEMPLATE.format(ano=ano)
    caminho = _baixar_com_cache(url, f"componentes-tarifarias-{ano}.csv")
    df = _ler_csv_flexivel(caminho)
    # Esse arquivo usa 'SigNomeAgente' (confirmado 26/08/2026 contra o CSV
    # real), diferente do 'SigAgente' usado no arquivo de tarifas
    # homologadas — normalizamos os dois pro mesmo nome interno pra
    # buscar_componente() poder ser genérico.
    col_sigla = "SigNomeAgente" if "SigNomeAgente" in df.columns else "SigAgente"
    df["_SigAgente_norm"] = df.get(col_sigla, "").map(normalizar)
    df["_DscComponenteTarifario_norm"] = df.get("DscComponenteTarifario", "").map(normalizar)
    _parse_datas(df, ["DatInicioVigencia", "DatFimVigencia"])
    if "VlrComponenteTarifario" in df.columns:
        df["VlrComponenteTarifario_num"] = (
            df["VlrComponenteTarifario"]
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        df["VlrComponenteTarifario_num"] = pd.to_numeric(
            df["VlrComponenteTarifario_num"], errors="coerce"
        )
    return df


def _coluna_normalizada(df: pd.DataFrame, coluna: str) -> pd.Series:
    """Devolve a versão normalizada (maiúscula, sem acento) de uma coluna,
    calculando uma única vez por DataFrame e guardando o resultado numa
    coluna auxiliar (`__norm__<coluna>`) pra reaproveitar depois.

    Sem isso, buscar_vigente()/buscar_componente() reprocessavam a coluna
    inteira do zero (unicodedata + regex, linha por linha) a cada uma das
    33 distribuidoras — no arquivo de componentes (bem maior, formato
    longo) isso deixava o dry run visivelmente mais lento a cada
    distribuidora processada. Com o cache, cada coluna só é normalizada
    uma vez, não 33 vezes."""
    cache_col = f"__norm__{coluna}"
    if cache_col not in df.columns:
        df[cache_col] = df[coluna].map(normalizar)
    return df[cache_col]


# ---------------------------------------------------------------------------
# Seleção do registro vigente (com detecção de ambiguidade)
# ---------------------------------------------------------------------------

@dataclass
class ResultadoBusca:
    status: str  # "OK" | "SEM_TARIFA_VIGENTE" | "AMBIGUO" | "SIGLA_NAO_MAPEADA"
    linhas: pd.DataFrame = field(default_factory=pd.DataFrame)
    observacao: str = ""


def buscar_vigente(
    df: pd.DataFrame,
    sig_agente: Optional[str],
    filtros: dict,
    hoje: Optional[date] = None,
) -> ResultadoBusca:
    """Aplica os filtros (comparação normalizada) + a regra de vigência, e
    devolve exatamente um status: OK (1 linha), SEM_TARIFA_VIGENTE (0
    linhas), AMBIGUO (>1 linha) ou SIGLA_NAO_MAPEADA (sig_agente é None)."""
    if not sig_agente:
        return ResultadoBusca("SIGLA_NAO_MAPEADA", observacao="SigAgente não mapeado em config.py")

    hoje = hoje or date.today()
    mask = df["_SigAgente_norm"] == normalizar(sig_agente)

    for coluna, valor_esperado in filtros.items():
        if coluna not in df.columns:
            return ResultadoBusca(
                "ERRO_ESTRUTURA",
                observacao=f"Coluna '{coluna}' não existe na base baixada — a ANEEL pode ter mudado o layout.",
            )
        mask &= _coluna_normalizada(df, coluna) == normalizar(valor_esperado)

    candidatos = df[mask].copy()

    # Regra de vigência: DatInicioVigencia <= hoje <= DatFimVigencia.
    # "Fim de vigência em aberto" só conta quando o campo já vinha vazio na
    # fonte (vigência realmente sem data de término definida) — se veio
    # preenchido e não deu pra converter, NÃO tratamos como em aberto (ver
    # _parse_datas), senão um registro antigo com data corrompida "ganha"
    # vigência eterna por engano.
    hoje_ts = pd.Timestamp(hoje)
    vigentes = candidatos[
        (candidatos["DatInicioVigencia_dt"] <= hoje_ts)
        & (
            candidatos["DatFimVigencia_vazio_na_origem"]
            | (candidatos["DatFimVigencia_dt"] >= hoje_ts)
        )
    ]

    if vigentes.empty:
        obs = "Nenhum registro com vigência ativa hoje."
        if not candidatos.empty:
            obs += f" ({len(candidatos)} registro(s) do agente/filtro encontrados, mas fora da vigência.)"
        return ResultadoBusca("SEM_TARIFA_VIGENTE", linhas=candidatos, observacao=obs)

    if len(vigentes) > 1:
        return ResultadoBusca(
            "AMBIGUO",
            linhas=vigentes,
            observacao=f"{len(vigentes)} registros vigentes simultaneamente — não dá pra escolher sozinho.",
        )

    return ResultadoBusca("OK", linhas=vigentes)


def buscar_componente(
    df_componentes: pd.DataFrame,
    sig_agente: Optional[str],
    rotulos_possiveis: list,
    filtros_extra: Optional[dict] = None,
    hoje: Optional[date] = None,
) -> ResultadoBusca:
    """Mesma lógica de buscar_vigente, mas para o arquivo de componentes
    tarifários (formato longo: um componente por linha)."""
    if not sig_agente:
        return ResultadoBusca("SIGLA_NAO_MAPEADA", observacao="SigAgente não mapeado em config.py")

    hoje = hoje or date.today()
    mask = df_componentes["_SigAgente_norm"] == normalizar(sig_agente)

    rotulos_norm = tuple(sorted(normalizar(r) for r in rotulos_possiveis))
    cache_col = f"__rotulo_match__{rotulos_norm}"
    if cache_col not in df_componentes.columns:
        # mesma ideia do cache de _coluna_normalizada: com poucos "campos"
        # distintos em config.COMPONENTES_DESEJADOS (hoje só fio_b), esse
        # .apply() roda com os MESMOS rótulos em todas as 33 distribuidoras
        # — calcula uma vez e reaproveita, em vez de rodar a busca de
        # substring linha a linha 33 vezes.
        df_componentes[cache_col] = df_componentes["_DscComponenteTarifario_norm"].apply(
            lambda v: any(r in v for r in rotulos_norm)
        )
    mask &= df_componentes[cache_col]

    for coluna, valor_esperado in (filtros_extra or {}).items():
        if coluna in df_componentes.columns:
            mask &= _coluna_normalizada(df_componentes, coluna) == normalizar(valor_esperado)

    candidatos = df_componentes[mask].copy()

    hoje_ts = pd.Timestamp(hoje)
    vigentes = candidatos[
        (candidatos["DatInicioVigencia_dt"] <= hoje_ts)
        & (
            candidatos["DatFimVigencia_vazio_na_origem"]
            | (candidatos["DatFimVigencia_dt"] >= hoje_ts)
        )
    ]

    if vigentes.empty:
        return ResultadoBusca("SEM_TARIFA_VIGENTE", linhas=candidatos, observacao="Nenhum componente vigente encontrado.")
    if len(vigentes) > 1:
        return ResultadoBusca(
            "AMBIGUO", linhas=vigentes,
            observacao=f"{len(vigentes)} componentes vigentes simultaneamente para os rótulos {rotulos_possiveis}.",
        )
    return ResultadoBusca("OK", linhas=vigentes)
