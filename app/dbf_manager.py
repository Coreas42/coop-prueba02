import pandas as pd
from dbfread import DBF


def cargar_datos_dbf(ruta):
    """Lee una tabla DBF y la devuelve como DataFrame normalizado."""
    try:
        table = DBF(ruta, load=True, encoding="latin1")
        df = pd.DataFrame(iter(table))
        if not df.empty:
            df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"Error al leer DBF ({ruta}): {e}")
        return pd.DataFrame()


def exportar_df_a_csv(df, ruta):
    df.to_csv(ruta, index=False, encoding="utf-8-sig")


def normalizar_codigo(valor):
    return str(valor).strip().upper()
