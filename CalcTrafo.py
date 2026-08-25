"""
TP1 TME 2026-2Q - Grupo 3
Calculadora parametrica para transformador RM8 / N87

IMPORTANTE:
- El diseño electromagnético usa los datos de la consigna y del datasheet RM8.
- La lista de diámetros disponibles en el pañol NO fue provista. Completar WIRE_DIAMETERS_MM
  para que el programa sugiera combinaciones reales de alambre.
- La estimación de pérdidas de núcleo y de inductancia de dispersión requiere supuestos
  adicionales; se dejan parametrizados y claramente separados.
"""

from math import pi, sqrt, ceil
from fractions import Fraction

# =========================
# ENTRADAS DEL GRUPO 3
# =========================
VIN = 7.0                 # V, nivel positivo aplicado al primario
F = 75e3                  # Hz
D = 0.533                 # duty
RATIO_N2_N1 = 1.875       # N2/N1 = 15/8
N_SECONDARIES = 3
J = 4.0                   # A/mm2
IDC_NOM = 1.15            # A
IDC_TOL = 0.10            # ±10 %
B_LIMIT = 0.200           # T, límite impuesto por consigna

# Núcleo RM8 B65811J0000R087
AE = 64e-6                # m2
AMIN = 55e-6              # m2
VE = 2430e-9              # m3
AL0 = 3300e-9             # H/turn^2, ungapped nominal
MU0 = 4*pi*1e-7

# Carrete B65812N1008D002
AN_TOTAL = 28.4            # mm2, sección total de bobinado
MLT = 42e-3                # m, longitud media por espira
AR = 50e-6                 # ohm, Rcu/N^2 del datasheet
KW = 0.40                  # criterio de diseño (clase: transformador común 0.3...0.4)

# Gap disponible
GAP_OPTIONS_MM = [0.0, 0.1, 0.2, 0.3, 0.4]

# Completar con los diámetros REALES disponibles en el pañol.
WIRE_DIAMETERS_MM = []

# Supuestos opcionales para modelo equivalente
K_COUPLING_EST = 0.97      # SOLO estimación; reemplazar por medición
PV_CORE_EST_KW_M3 = 7.0    # SOLO estimación típica aprox. para ~56 mT, 75 kHz, 100°C


def al_with_gap(gap_mm):
    """AL nominal agregando reluctancia de un gap total externo."""
    g = gap_mm * 1e-3
    if g == 0:
        return AL0
    return 1.0 / (1.0/AL0 + g/(MU0*AE))


def flux_components(N1, gap_mm, idc):
    """Bac es amplitud AC; Bdc es el corrimiento por IDC; Bmax = Bac + Bdc."""
    AL = al_with_gap(gap_mm)
    bac = VIN*D/(2*F*N1*AMIN)
    bdc = N1*idc*AL/AMIN
    return bac, bdc, bac+bdc


def choose_turns_and_gap():
    """
    Busca una relación exacta N2/N1 y el menor gap disponible que respete B_LIMIT
    al máximo IDC especificado.
    """
    ratio = Fraction(str(RATIO_N2_N1)).limit_denominator(1000)
    idc_max = IDC_NOM*(1+IDC_TOL)

    candidates = []
    for gap in GAP_OPTIONS_MM:
        for mult in range(1, 50):
            N1 = ratio.denominator * mult
            N2 = ratio.numerator * mult
            bac, bdc, bmax = flux_components(N1, gap, idc_max)
            if bmax <= B_LIMIT:
                AL = al_with_gap(gap)
                Lm = AL*N1**2
                candidates.append((gap, N1, N2, bmax, Lm))
                break

    if not candidates:
        raise RuntimeError("No hay solución con los gaps/espiras buscados.")

    # Prioridad: mínimo gap; dentro del mismo gap, mínimo N1.
    return sorted(candidates, key=lambda x: (x[0], x[1]))[0], candidates


def skin_depth_mm():
    return 66.0/sqrt(F)


def conductor_targets(N1, N2):
    # El carrete tiene dos secciones físicas: una para primario y otra para los 3 secundarios.
    aw_section = AN_TOTAL/2
    copper_area_section = aw_section*KW

    s1_total = copper_area_section/N1
    s2_each = copper_area_section/(N_SECONDARIES*N2)

    d1_equiv = sqrt(4*s1_total/pi)
    d2 = sqrt(4*s2_each/pi)
    return aw_section, copper_area_section, s1_total, s2_each, d1_equiv, d2


def suggest_wire_combo(target_area_mm2, diameters, max_strands=20):
    """
    Sugiere combinación de hilos en paralelo.
    Cada hilo debe cumplir d/2 <= skin depth.
    Prioriza área >= objetivo con el menor exceso.
    """
    if not diameters:
        return None
    delta = skin_depth_mm()
    best = None
    for d in diameters:
        if d/2 > delta:
            continue
        area_one = pi*d*d/4
        for n in range(1, max_strands+1):
            area = n*area_one
            if area >= target_area_mm2:
                excess = area-target_area_mm2
                cand = (excess, n, d, area)
                if best is None or cand < best:
                    best = cand
                break
    return best


def main():
    chosen, candidates = choose_turns_and_gap()
    gap, N1, N2, bmax_worst, Lm = chosen
    AL = al_with_gap(gap)
    idc_max = IDC_NOM*(1+IDC_TOL)

    bac_nom, bdc_nom, bmax_nom = flux_components(N1, gap, IDC_NOM)
    bac_w, bdc_w, _ = flux_components(N1, gap, idc_max)

    ton = D/F
    delta_i_pp = VIN*ton/Lm
    iac_rms = (delta_i_pp/2)/sqrt(3)
    i1_base_rms = sqrt(IDC_NOM**2 + iac_rms**2)

    v_off_mag = VIN*D/(1-D)
    v1_rms = sqrt(D*VIN**2 + (1-D)*v_off_mag**2)
    v2_pos = VIN*RATIO_N2_N1
    v2_off_mag = v_off_mag*RATIO_N2_N1
    v2_rect_avg = v2_pos*D

    aw_sec, acu_sec, s1, s2, d1eq, d2 = conductor_targets(N1, N2)
    delta = skin_depth_mm()
    max_d_skin = 2*delta
    max_s_skin = pi*delta**2

    l1_path = N1*MLT
    l2_each = N2*MLT
    rho_cu = 0.01724 # ohm mm2 / m
    r1_target = rho_cu*l1_path/s1
    r2_target = rho_cu*l2_each/s2

    # Inductancias
    L2 = AL*N2**2
    M = sqrt(Lm*L2) * K_COUPLING_EST
    Lsigma1_est = Lm*(1-K_COUPLING_EST**2)

    # Núcleo: estimación típica, NO garantía.
    pcore_est = PV_CORE_EST_KW_M3*1e3*VE
    rp_est = v1_rms**2/pcore_est if pcore_est > 0 else float("inf")

    print("\n=== DISEÑO ELECTROMAGNÉTICO ===")
    print(f"N1 = {N1} espiras")
    print(f"N2 = {N2} espiras por secundario, x {N_SECONDARIES}")
    print(f"Relación exacta = {N2/N1:.6f}")
    print(f"Gap elegido = {gap:.1f} mm")
    print(f"AL(gap) ≈ {AL*1e9:.1f} nH/espira²")
    print(f"Lm = {Lm*1e6:.2f} uH")
    print(f"L2 (cada secundario, abierto) ≈ {L2*1e6:.2f} uH")

    print("\n=== FLUJO ===")
    print(f"Bac = {bac_nom*1e3:.2f} mT")
    print(f"Bdc nominal = {bdc_nom*1e3:.2f} mT")
    print(f"Bmax nominal = {bmax_nom*1e3:.2f} mT")
    print(f"Bdc a IDC máximo = {bdc_w*1e3:.2f} mT")
    print(f"Bmax a IDC máximo = {bmax_worst*1e3:.2f} mT < {B_LIMIT*1e3:.0f} mT")

    print("\n=== CORRIENTE DE MAGNETIZACIÓN ===")
    print(f"ΔIm pp ≈ {delta_i_pp:.3f} A")
    print(f"Im,ac,rms ≈ {iac_rms:.3f} A")
    print(f"I1,rms base (IDC + magnetización, sin carga) ≈ {i1_base_rms:.3f} A")

    print("\n=== TENSIONES ===")
    print(f"V1 off = -{v_off_mag:.3f} V para balance volt-segundo")
    print(f"V1 rms ≈ {v1_rms:.3f} V")
    print(f"V2 durante ton = +{v2_pos:.3f} V")
    print(f"V2 durante toff = -{v2_off_mag:.3f} V")
    print(f"Promedio rectificado ideal de la fase positiva ≈ {v2_rect_avg:.3f} V")

    print("\n=== VENTANA / CONDUCTORES ===")
    print(f"AN total = {AN_TOTAL:.2f} mm² -> {aw_sec:.2f} mm² por sección física")
    print(f"Kw = {KW:.2f} -> cobre efectivo ≈ {acu_sec:.2f} mm² por sección")
    print(f"Primario: sección total objetivo ≈ {s1:.3f} mm² (diámetro sólido equivalente {d1eq:.3f} mm)")
    print(f"Cada secundario: sección objetivo ≈ {s2:.3f} mm² (diámetro {d2:.3f} mm)")
    print(f"Skin depth δ ≈ {delta:.3f} mm -> diámetro individual recomendado <= {max_d_skin:.3f} mm")
    print(f"Área máxima por hilo circular para r<=δ ≈ {max_s_skin:.3f} mm²")

    pcombo = suggest_wire_combo(s1, WIRE_DIAMETERS_MM)
    scombo = suggest_wire_combo(s2, WIRE_DIAMETERS_MM)
    if pcombo:
        _, n, d, area = pcombo
        print(f"Sugerencia primario con pañol: {n} x Ø{d:.3f} mm = {area:.3f} mm²")
    else:
        print("Primario: falta cargar WIRE_DIAMETERS_MM para elegir alambre real.")
    if scombo:
        _, n, d, area = scombo
        print(f"Sugerencia secundario: {n} x Ø{d:.3f} mm = {area:.3f} mm²")
    else:
        print("Secundarios: falta cargar WIRE_DIAMETERS_MM para elegir alambre real.")

    print("\n=== LARGOS Y Rdc (usando sección objetivo) ===")
    print(f"Longitud de trayecto primario ≈ {l1_path:.3f} m")
    print(f"Longitud de cada secundario ≈ {l2_each:.3f} m")
    print(f"R1,dc objetivo ≈ {r1_target:.4f} ohm")
    print(f"R2,dc objetivo por secundario ≈ {r2_target:.4f} ohm")
    print(f"AR datasheet (sin corregir reparto de ventana): R1={AR*N1**2:.4f} ohm, R2={AR*N2**2:.4f} ohm")

    print("\n=== MODELO EQUIVALENTE (PARTE ESTIMADA) ===")
    print(f"k supuesto = {K_COUPLING_EST:.3f}")
    print(f"M estimada ≈ {M*1e6:.2f} uH")
    print(f"Ldispersión primaria estimada ≈ {Lsigma1_est*1e6:.2f} uH")
    print(f"Pcore típica estimada ≈ {pcore_est*1e3:.1f} mW")
    print(f"Rp referida al primario ≈ {rp_est/1e3:.1f} kohm")
    print("ATENCIÓN: k, Ldispersión y Pcore deben validarse/ajustarse con medición o datos más específicos.")

    print("\n=== CANDIDATOS POR GAP (primer N exacto que cumple B) ===")
    for g, n1, n2, bm, lm in candidates:
        print(f"g={g:.1f} mm: N1={n1}, N2={n2}, Bmax_worst={bm*1e3:.1f} mT, Lm={lm*1e6:.1f} uH")


if __name__ == "__main__":
    main()
