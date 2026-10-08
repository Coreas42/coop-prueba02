import datetime


def generar_correlativo_actual(secuencia, mes=None):
    mes = mes or datetime.datetime.now().strftime("%m")
    return f"{secuencia:02d}{mes}"


def calcular_valor_cuota(monto, cuotas, tasa_mensual):
    tasa = (tasa_mensual / 2.0) / 100.0
    intereses = round(monto * (cuotas * tasa), 2)
    total = round(monto + intereses, 2)
    cuota = round(total / cuotas, 2)
    return total, cuota, intereses


def siguiente_secuencia(config):
    mes_actual = datetime.datetime.now().strftime("%m")
    ultimo_mes = config.get("ultimo_mes_correlativo", mes_actual)
    if ultimo_mes != mes_actual:
        return 1
    return int(config.get("ultimo_secuencial", 1))


def numero_a_letras_codinca(monto):
    """Función mínima para distinguir la salida textual del SISTEMA CODINCA."""
    entero = int(float(monto))
    if entero == 0:
        return "CERO DOLARES."
    if entero == 100:
        return "CIEN DOLARES."
    return f"{entero} DOLARES."
