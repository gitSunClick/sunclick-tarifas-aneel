# -*- coding: utf-8 -*-
"""Testes de calculos_tarifa.py — validados contra os 5 casos de teste da
seção 6 da especificação recebida da Nathalia ("ESPECIFICAÇÃO DE CÁLCULO DE
TARIFA — IMPLANTAÇÃO", 10/09/2026). Não depende de rede nem do resto do
projeto (além do próprio módulo)."""

from calculos_tarifa import (
    AliquotaInvalidaError,
    calcular_tarifa_distribuidora,
    resolver_flag_compensacao,
)

TOLERANCIA = 1e-6


def _quase_igual(a, b, tol=TOLERANCIA):
    return abs(a - b) < tol


# --- casos 1-5: exatamente os da seção 6 da especificação ------------------
CASOS = [
    # nome, te, tusd, pis_cofins, icms_te, icms_tusd, flag_te, flag_tusd, trci_esperado, tc_esperado
    ("Enel Ceará", 260.99, 488.78, 0.05, 0.20, 0.20, True, False, 986.5394736842105, 857.9131578947369),
    ("Cemig", 317.28, 541.30, 0.055, 0.21, 0.21, True, True, 1150.0636260129932, 1150.0636260129932),
    ("Distribuidora RJ (F)", 354.68, 462.35, 0.055, 0.24, 0.24, True, False, 1137.6079086605403, 983.1049846839321),
    ("ESS", 321.56, 492.68, 0.055, 0.18, 0.18, False, False, 1050.7678410117435, 861.6296296296298),
    ("Light", 310.26, 513.30, 0.055, 0.24, 0.24, True, False, 1146.7000835421888, 975.171261487051),
]

for nome, te, tusd, pis_cofins, icms_te, icms_tusd, flag_te, flag_tusd, trci_esp, tc_esp in CASOS:
    r = calcular_tarifa_distribuidora(
        te_sem_imposto=te,
        tusd_sem_imposto=tusd,
        aliq_pis_cofins=pis_cofins,
        aliq_icms_te=icms_te,
        aliq_icms_tusd=icms_tusd,
        flag_comp_icms_te=flag_te,
        flag_comp_icms_tusd=flag_tusd,
    )
    assert _quase_igual(r.tarifa_cheia, trci_esp), (
        f"{nome}: TRCI esperado {trci_esp}, veio {r.tarifa_cheia}"
    )
    assert _quase_igual(r.tarifa_compensada, tc_esp), (
        f"{nome}: TC esperado {tc_esp}, veio {r.tarifa_compensada}"
    )
    print(f"OK  {nome}: TRCI={r.tarifa_cheia:.6f} TC={r.tarifa_compensada:.6f} (bate com a especificação)")

# --- caso 6: tarifa_sem_imposto e valor_tributos consistentes ---------------
r = calcular_tarifa_distribuidora(
    te_sem_imposto=260.99, tusd_sem_imposto=488.78,
    aliq_pis_cofins=0.05, aliq_icms_te=0.20, aliq_icms_tusd=0.20,
    flag_comp_icms_te=True, flag_comp_icms_tusd=False,
)
assert _quase_igual(r.tarifa_sem_imposto, 260.99 + 488.78)
assert _quase_igual(r.valor_tributos, r.tarifa_cheia - r.tarifa_sem_imposto)
assert _quase_igual(r.carga_efetiva, 1 - (1 - 0.05) * (1 - 0.20))
print("OK  caso 6: tarifa_sem_imposto / valor_tributos / carga_efetiva consistentes com as fórmulas")

# --- caso 7: TUSDg com imposto (gross-up simples, sem compensação) --------
r = calcular_tarifa_distribuidora(
    te_sem_imposto=260.99, tusd_sem_imposto=488.78,
    aliq_pis_cofins=0.05, aliq_icms_te=0.20, aliq_icms_tusd=0.20,
    flag_comp_icms_te=True, flag_comp_icms_tusd=False,
    tusd_g_sem_imposto=16.37,
)
esperado_tusd_g = 16.37 / (1 - 0.05) / (1 - 0.20)
assert _quase_igual(r.tusd_g_com_imposto, esperado_tusd_g), (
    f"TUSDg com imposto esperado {esperado_tusd_g}, veio {r.tusd_g_com_imposto}"
)
print(f"OK  caso 7: TUSD G com imposto = {r.tusd_g_com_imposto:.6f} (gross-up simples, sem compensação)")

# --- caso 8: sem TUSDg informado -> None, não quebra ------------------------
r = calcular_tarifa_distribuidora(
    te_sem_imposto=260.99, tusd_sem_imposto=488.78,
    aliq_pis_cofins=0.05, aliq_icms_te=0.20, aliq_icms_tusd=0.20,
    flag_comp_icms_te=True, flag_comp_icms_tusd=False,
)
assert r.tusd_g_com_imposto is None
print("OK  caso 8: TUSDg não informado -> tusd_g_com_imposto=None (não quebra o cálculo do resto)")

# --- caso 9: alíquota inválida (>= 1) levanta erro, não devolve lixo -------
try:
    calcular_tarifa_distribuidora(
        te_sem_imposto=100, tusd_sem_imposto=100,
        aliq_pis_cofins=0.05, aliq_icms_te=1.0, aliq_icms_tusd=0.20,
        flag_comp_icms_te=True, flag_comp_icms_tusd=False,
    )
    raise AssertionError("esperava AliquotaInvalidaError com aliq_icms_te=1.0")
except AliquotaInvalidaError:
    print("OK  caso 9: alíquota >= 1 levanta AliquotaInvalidaError em vez de devolver número sem sentido")

# --- caso 10: alíquota negativa também é inválida ---------------------------
try:
    calcular_tarifa_distribuidora(
        te_sem_imposto=100, tusd_sem_imposto=100,
        aliq_pis_cofins=-0.01, aliq_icms_te=0.20, aliq_icms_tusd=0.20,
        flag_comp_icms_te=True, flag_comp_icms_tusd=False,
    )
    raise AssertionError("esperava AliquotaInvalidaError com aliq_pis_cofins negativa")
except AliquotaInvalidaError:
    print("OK  caso 10: alíquota negativa também levanta AliquotaInvalidaError")

# --- caso 11: regra de precedência override > default -----------------------
assert resolver_flag_compensacao(None, True) is True
assert resolver_flag_compensacao(None, False) is False
assert resolver_flag_compensacao(True, False) is True  # override vence o default
assert resolver_flag_compensacao(False, True) is False  # override vence o default
print("OK  caso 11: resolver_flag_compensacao segue COALESCE(override_distribuidora, default_uf)")

print("\nTodos os testes de calculos_tarifa.py passaram.")
