def validar_fiador(cod_solicitante, cod_fiador, nombre_fiador, buscar_respaldados):
    if cod_solicitante == cod_fiador:
        return False, "El socio no puede ser su propio fiador."

    quienes_respalda_solicitante = [r[1] for r in buscar_respaldados(cod_solicitante, "")]
    if cod_fiador in quienes_respalda_solicitante:
        return False, "Filtro carrusel activado: no se puede registrar esa fianza."

    respaldados_fiador = buscar_respaldados(cod_fiador, nombre_fiador)
    if len(respaldados_fiador) >= 3:
        return True, "Alerta: esta sería la 4ta fianza."

    return True, ""
