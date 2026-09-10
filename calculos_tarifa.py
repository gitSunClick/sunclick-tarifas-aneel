# -*- coding: utf-8 -*-
"""
calculos_tarifa.py — cálculo de TRCI (Tarifa Cheia Com Imposto) e TC (Tarifa
Compensada), a partir das tarifas SEM imposto já extraídas pelo aneel_lib.py
(TE e TUSD em R$/MWh, TUSD G em R$/kW).

Implementa exatamente as regras da especificação recebida da Nathalia
(planilha "ESPECIFICAÇÃO DE CÁLCULO DE TARIFA — IMPLANTAÇÃO", seções 3 e 6),
validadas linha a linha contra os 5 casos de teste da seção 6 (ver
teste_calculos_tarifa.py) — todos batem exatamente (diferença < 1e-6).

REGRAS (seção 3 da especificação, replicadas ao pé da letra):
  te_com_imposto     = te_sem_imposto   / (1 - aliq_pis_cofins) / (1 - aliq_icms_te)
  tusd_com_imposto   = tusd_sem_imposto / (1 - aliq_pis_cofins) / (1 - aliq_icms_tusd)
  tarifa_sem_imposto = te_sem_imposto + tusd_sem_imposto
  tarifa_cheia (TRCI)= te_com_imposto + tusd_com_imposto
  icms_te_efet       = aliq_icms_te   se flag_comp_icms_te   senão 0
  icms_tusd_efet     = aliq_icms_tusd se flag_comp_icms_tusd senão 0
  tarifa_compensada (TC) = te_sem_imposto/(1-aliq_pis_cofins)/(1-icms_te_efet)
                         + tusd_sem_imposto/(1-aliq_pis_cofins)/(1-icms_tusd_efet)
  valor_tributos     = tarifa_cheia - tarifa_sem_imposto
  carga_efetiva      = 1 - (1 - aliq_pis_cofins) * (1 - aliq_icms)

TUSDg (R$/kW) é cobrança de demanda, não entra na tarifa de energia — só
calculamos ela "com impostos" (mesmo gross-up da TUSD, com a alíquota de
ICMS-TUSD), sem versão compensada (a especificação não define regra de
compensação pra TUSDg).

Restrições da especificação, todas respeitadas aqui:
  1. Tributo "por dentro": sempre dividir por (1 - alíquota), nunca
     multiplicar por (1 + alíquota).
  2. PIS/COFINS e ICMS são dois estágios separados — nunca somar as
     alíquotas antes de aplicar.
  3. TE e TUSD calculados separadamente, só depois somados.
  4. Validar alíquota < 1 (senão a divisão por (1-alíquota) explode ou
     inverte o sinal) — levanta ValueError em vez de devolver um número
     sem sentido.
  5. Arredondamento é só de exibição — este módulo devolve tudo em ponto
     flutuante de precisão total (double), sem arredondar em nenhum
     lugar; quem exibe (a planilha) decide quantas casas mostrar.
  6. Unidade canônica: R$/MWh para TE/TUSD/tarifas; R$/kW para TUSD G.
"""

from dataclasses import dataclass
from typing import Optional


class AliquotaInvalidaError(ValueError):
    """Uma alíquota fora do intervalo [0, 1) foi passada — dividir por
    (1 - alíquota) com alíquota >= 1 não tem sentido econômico (dá zero,
    negativo ou divisão por zero)."""


def _validar_aliquota(nome: str, valor: float) -> None:
    if valor is None or valor < 0 or valor >= 1:
        raise AliquotaInvalidaError(
            f"Alíquota '{nome}' inválida: {valor!r} — precisa estar em [0, 1)."
        )


def resolver_flag_compensacao(override: Optional[bool], default_uf: bool) -> bool:
    """Regra de precedência da especificação: COALESCE(override_distribuidora,
    default_uf). override=None significa 'sem condição negociada' — usa o
    default do estado; override=True/False é a condição negociada específica
    daquela distribuidora, que sempre vence."""
    return default_uf if override is None else bool(override)


@dataclass
class ResultadoCalculoTarifa:
    te_com_imposto: float
    tusd_com_imposto: float
    tarifa_sem_imposto: float
    tarifa_cheia: float  # TRCI
    tarifa_compensada: float  # TC
    valor_tributos: float
    carga_efetiva: float
    tusd_g_com_imposto: Optional[float]
    icms_te_efet: float
    icms_tusd_efet: float


def calcular_tarifa_distribuidora(
    te_sem_imposto: float,
    tusd_sem_imposto: float,
    aliq_pis_cofins: float,
    aliq_icms_te: float,
    aliq_icms_tusd: float,
    flag_comp_icms_te: bool,
    flag_comp_icms_tusd: bool,
    tusd_g_sem_imposto: Optional[float] = None,
) -> ResultadoCalculoTarifa:
    """Calcula TRCI (tarifa_cheia) e TC (tarifa_compensada) pra uma
    distribuidora, seguindo exatamente as fórmulas da seção 3 da
    especificação. te_sem_imposto/tusd_sem_imposto em R$/MWh;
    tusd_g_sem_imposto (opcional) em R$/kW.

    flag_comp_icms_te/flag_comp_icms_tusd já devem vir RESOLVIDAS (depois de
    aplicar resolver_flag_compensacao) — este função não conhece UF nem
    overrides, só os booleanos finais."""
    _validar_aliquota("aliq_pis_cofins", aliq_pis_cofins)
    _validar_aliquota("aliq_icms_te", aliq_icms_te)
    _validar_aliquota("aliq_icms_tusd", aliq_icms_tusd)

    te_com_imposto = te_sem_imposto / (1 - aliq_pis_cofins) / (1 - aliq_icms_te)
    tusd_com_imposto = tusd_sem_imposto / (1 - aliq_pis_cofins) / (1 - aliq_icms_tusd)

    tarifa_sem_imposto = te_sem_imposto + tusd_sem_imposto
    tarifa_cheia = te_com_imposto + tusd_com_imposto  # TRCI

    icms_te_efet = aliq_icms_te if flag_comp_icms_te else 0.0
    icms_tusd_efet = aliq_icms_tusd if flag_comp_icms_tusd else 0.0

    tarifa_compensada = (  # TC
        te_sem_imposto / (1 - aliq_pis_cofins) / (1 - icms_te_efet)
        + tusd_sem_imposto / (1 - aliq_pis_cofins) / (1 - icms_tusd_efet)
    )

    valor_tributos = tarifa_cheia - tarifa_sem_imposto
    # Carga efetiva "de referência": usa a alíquota de ICMS-TUSD como base
    # (na prática ICMS-TE e ICMS-TUSD são a mesma alíquota estadual — a
    # especificação só define uma "aliq_icms" genérica na fórmula B40).
    carga_efetiva = 1 - (1 - aliq_pis_cofins) * (1 - aliq_icms_tusd)

    tusd_g_com_imposto = None
    if tusd_g_sem_imposto is not None:
        tusd_g_com_imposto = tusd_g_sem_imposto / (1 - aliq_pis_cofins) / (1 - aliq_icms_tusd)

    return ResultadoCalculoTarifa(
        te_com_imposto=te_com_imposto,
        tusd_com_imposto=tusd_com_imposto,
        tarifa_sem_imposto=tarifa_sem_imposto,
        tarifa_cheia=tarifa_cheia,
        tarifa_compensada=tarifa_compensada,
        valor_tributos=valor_tributos,
        carga_efetiva=carga_efetiva,
        tusd_g_com_imposto=tusd_g_com_imposto,
        icms_te_efet=icms_te_efet,
        icms_tusd_efet=icms_tusd_efet,
    )
