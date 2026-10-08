"""Motor de acceso a datos DBF y metadatos JSON."""
import os
import pandas as pd
from dbfread import DBF
from app.config import load_meta, save_meta


class DBFEngine:
    """Gestor de lectura/escritura de archivos DBF y metadatos."""

    def __init__(self):
        self.meta_data = load_meta()
        self.df_maestro = None
        self.df_history = None
        self.df_hisact = None

    def leer_maestro_df(self, ruta="maestro.dbf"):
        if not os.path.exists(ruta):
            ruta_upper = ruta.upper()
            if os.path.exists(ruta_upper):
                ruta = ruta_upper
            else:
                return pd.DataFrame()
        try:
            table = DBF(ruta, load=True, encoding="latin1")
            df = pd.DataFrame(iter(table))
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]
            self.df_maestro = df
            return df
        except Exception as e:
            print(f"Error al leer MAESTRO.DBF: {e}")
            return pd.DataFrame()

    def leer_history_df(self, ruta="history.dbf"):
        if not os.path.exists(ruta):
            ruta_upper = ruta.upper()
            if os.path.exists(ruta_upper):
                ruta = ruta_upper
            else:
                return pd.DataFrame()
        try:
            table = DBF(ruta, load=True, encoding="latin1")
            df = pd.DataFrame(iter(table))
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]
            self.df_history = df
            return df
        except Exception as e:
            print(f"Error al leer HISTORY.DBF: {e}")
            return pd.DataFrame()

    def leer_hisact_df(self, ruta="hisact.dbf"):
        if not os.path.exists(ruta):
            ruta_upper = ruta.upper()
            if os.path.exists(ruta_upper):
                ruta = ruta_upper
            else:
                return pd.DataFrame()
        try:
            table = DBF(ruta, load=True, encoding="latin1")
            df = pd.DataFrame(iter(table))
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]
            self.df_hisact = df
            return df
        except Exception as e:
            print(f"Error al leer HISACT.DBF: {e}")
            return pd.DataFrame()

    def obtener_prestamo_original(self, cod_socio):
        """Obtiene datos del préstamo original de un socio."""
        if self.df_maestro is None or self.df_maestro.empty:
            return {"monto_original": 0.0, "total_con_intereses": 0.0}
        
        mask = self.df_maestro["codigo"].astype(str).str.strip() == cod_socio
        if self.df_maestro[mask].empty:
            return {"monto_original": 0.0, "total_con_intereses": 0.0}
        
        registro = self.df_maestro[mask].iloc[0]
        saldo = float(registro.get("saldo", 0))
        
        return {
            "monto_original": saldo * 0.7622,
            "total_con_intereses": saldo
        }

    def registrar_compra_mercaderia(self, cod_socio, monto, valor_cuota, cuotas):
        """Registra una compra de mercancía en metadatos."""
        if "mercaderia" not in self.meta_data:
            self.meta_data["mercaderia"] = {}
        
        self.meta_data["mercaderia"][cod_socio] = {
            "saldo": monto,
            "cuota": valor_cuota,
            "cuotas_restantes": cuotas,
            "tasa": 0.0
        }
        save_meta(self.meta_data)

    def registrar_ajuste_cuota(self, cod_socio, columna_cuota, nuevo_valor):
        """Registra un ajuste de cuota en metadatos."""
        if "ajustes_cuota" not in self.meta_data:
            self.meta_data["ajustes_cuota"] = {}
        
        self.meta_data["ajustes_cuota"][cod_socio] = {
            "columna": columna_cuota,
            "valor": nuevo_valor
        }
        save_meta(self.meta_data)
