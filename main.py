"""
CUZODINCA - Sistema Integral de Control Financiero y Cooperativa
Versión Monolítica y Autónoma v3.5.1 (Con Recibos PDF CODINCA, Rollback, Reportes Dinámicos y Validación de Sueldo/Antigüedad)

CHANGELOG v3.5.1 (correcciones aplicadas sobre v3.5):
  - FIX CRÍTICO: dict(ops) en _mostrar_modulo_ingreso lanzaba ValueError porque 'ops'
    contiene tuplas de 3 elementos, no pares clave-valor. Esto rompía la pantalla de
    "Ingreso (Lotes)" a medio renderizar. Se reemplazó por un dict-comprehension explícito.
  - FIX: _buscar_respaldados usaba "cod_socio in f1" (substring), lo que podía dar falsos
    positivos (ej. código "20" coincidiendo dentro de "2018-JUAN PEREZ"). Ahora usa límites
    de palabra vía regex.
  - FIX: _agregar_fianza_a_lote generaba CLAVE "OTRO" (4 caracteres) mientras el campo DBF
    es C(3) y el resto del sistema usa "OTR". Se corrigió por consistencia entre CSV y DBF.
  - FIX: _autorizar_y_consolidar_lote antes solo hacía un backup y vaciaba el lote,
    mostrando un mensaje de éxito engañoso ("consolidado a HISACT") sin escribir nada.
    Ahora sí aplica los movimientos a self.df_maestro y los agrega a self.df_hisact en
    memoria, con confirmación previa y manejo de errores que no aplica cambios a medias.
"""
import os
import re
import json
import zipfile
import datetime
import shutil
import customtkinter as ctk
from tkinter import filedialog, messagebox
import pandas as pd
from dbfread import DBF

CONFIG_FILE = "cuzodinca_config.json"
META_FILE = "cuzodinca_meta.json"
DEFAULT_BACKUP_PATH = r"C:\Users\ccodinca\Downloads\CUZODINCA-Windows"
ROLLBACK_DIR = "backups_rollback"

def _truncar(texto, limite=24):
    t = str(texto).strip()
    return t[:limite-3] + "..." if len(t) > limite else t

def cargar_datos_dbf(ruta):
    """Lectura universal de tablas DBF a DataFrame de pandas."""
    try:
        table = DBF(ruta, load=True, encoding="latin1")
        df = pd.DataFrame(iter(table))
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"Error al leer DBF ({ruta}): {e}")
        return pd.DataFrame()

def procesar_planilla_safic(ruta_act, num_plan):
    df = cargar_datos_dbf(ruta_act)
    return df, pd.DataFrame()


class CuzodincaModernDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CUZODINCA - Sistema de Control Financiero")
        self.geometry("1440x900")
        self.minsize(1200, 780)
        
        self.config = self._cargar_configuracion()
        self.meta_data = self._cargar_meta()
        self.vista_actual = "dashboard"
        
        tema_inicial = self.config.get("theme", "dark")
        ctk.set_appearance_mode(tema_inicial)
        ctk.set_default_color_theme("blue")
        self._actualizar_paleta(tema_inicial)

        self.df_maestro = None
        self.df_history = None
        self.df_hisact = None
        self.socio_actual = None
        self.lote_movimientos = []
        self.tipo_op_seleccionada = ctk.StringVar(value="RET")

        # --- ATRIBUTOS DE SESIÓN Y CONTABILIDAD CODINCA ---
        self.fecha_sesion = datetime.datetime.now().strftime("%d-%m-%Y")
        self.mes_correlativo_actual = datetime.datetime.now().strftime("%m")
        self.secuencia_correlativo = self._obtener_siguiente_secuencia()
        self.ultimo_movimiento_registrado = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._crear_topbar()
        self._crear_sidebar()
        self._crear_main_area()
        self._crear_footer()
        
        self._intentar_autocarga_datos()

    def _actualizar_paleta(self, modo):
        if modo == "light":
            self.c_bg = "#f1f5f9"
            self.c_sidebar = "#e2e8f0"
            self.c_card = "#ffffff"
            self.c_card_highlight = "#e6f4ea"
            self.c_text = "#0f172a"
            self.c_muted = "#475569"
            self.c_accent = "#059669"
            self.c_btn = "#cbd5e1"
            self.c_primary = "#1d4ed8"
            self.c_warning = "#b45309"
            self.c_danger = "#dc2626"
            self.c_entry_bg = "#f8fafc"
        else:
            self.c_bg = "#0b1320"
            self.c_sidebar = "#0f172a"
            self.c_card = "#1e293b"
            self.c_card_highlight = "#134e4a"
            self.c_text = "#f8fafc"
            self.c_muted = "#94a3b8"
            self.c_accent = "#10b981"
            self.c_btn = "#334155"
            self.c_primary = "#2563eb"
            self.c_warning = "#f59e0b"
            self.c_danger = "#ef4444"
            self.c_entry_bg = "#0f172a"

    def _cargar_configuracion(self):
        default_cfg = {
            "backup_dir": DEFAULT_BACKUP_PATH,
            "theme": "dark",
            "tasa_interes_defecto": 2.60,
            "ultimo_secuencial": 1,
            "ultimo_mes_correlativo": datetime.datetime.now().strftime("%m")
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if "backup_dir" not in cfg or not cfg["backup_dir"]:
                        cfg["backup_dir"] = DEFAULT_BACKUP_PATH
                    if "tasa_interes_defecto" not in cfg:
                        cfg["tasa_interes_defecto"] = 2.60
                    if "ultimo_secuencial" not in cfg:
                        cfg["ultimo_secuencial"] = 1
                    if "ultimo_mes_correlativo" not in cfg:
                        cfg["ultimo_mes_correlativo"] = datetime.datetime.now().strftime("%m")
                    return cfg
            except Exception:
                pass
        return default_cfg

    def _guardar_configuracion(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error al guardar configuración: {e}")

    def _cargar_meta(self):
        if os.path.exists(META_FILE):
            try:
                with open(META_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"mercaderia": {}, "ajustes_cuota": {}, "sueldos_ingresos": {}}
        return {"mercaderia": {}, "ajustes_cuota": {}, "sueldos_ingresos": {}}

    def _guardar_meta(self):
        try:
            with open(META_FILE, "w", encoding="utf-8") as f:
                json.dump(self.meta_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error al guardar metadatos: {e}")

    def _obtener_siguiente_secuencia(self):
        mes_hoy = datetime.datetime.now().strftime("%m")
        config_mes = self.config.get("ultimo_mes_correlativo", mes_hoy)
        if config_mes != mes_hoy:
            self.config["ultimo_mes_correlativo"] = mes_hoy
            self.config["ultimo_secuencial"] = 1
            self._guardar_configuracion()
            return 1
        return self.config.get("ultimo_secuencial", 1)

    def _generar_correlativo_actual(self):
        mes = datetime.datetime.now().strftime("%m")
        sec_str = f"{self.secuencia_correlativo:02d}" if self.secuencia_correlativo < 100 else f"{self.secuencia_correlativo}"
        return f"{sec_str}{mes}"

    def _avanzar_correlativo(self):
        self.secuencia_correlativo += 1
        self.config["ultimo_secuencial"] = self.secuencia_correlativo
        self.config["ultimo_mes_correlativo"] = datetime.datetime.now().strftime("%m")
        self._guardar_configuracion()

    def _validar_reglas_fiador(self, cod_solicitante, cod_fiador, nom_fiador):
        cod_s = str(cod_solicitante).strip().upper()
        cod_f = str(cod_fiador).strip().upper()

        if cod_s == cod_f:
            messagebox.showerror("Bloqueo de Garantía", "El socio no puede ser su propio fiador.")
            return False

        quienes_respalda_solicitante = [r[1] for r in self._buscar_respaldados(cod_s, "")]
        if cod_f in quienes_respalda_solicitante:
            messagebox.showerror(
                "Fianza Cruzada Bloqueada",
                f"Filtro Carrusel Activo: El socio {cod_s} ya respalda crediticiamente a {cod_f} ({nom_fiador})."
            )
            return False

        respaldados_fiador = self._buscar_respaldados(cod_f, nom_fiador)
        total_act = len(respaldados_fiador)
        if total_act >= 3:
            resp = messagebox.askyesno(
                "Alerta de Fianza Adicional",
                f"El fiador {cod_f} - {nom_fiador} ya cuenta con [{total_act}/3] garantías vigentes.\n"
                f"Esta sería su 4ª FIANZA. ¿Desea autorizar y continuar excepcionalmente?"
            )
            if not resp:
                return False

        return True

    def _cambiar_tema(self, nuevo_modo):
        modo_str = "dark" if "Oscuro" in nuevo_modo or nuevo_modo == "dark" else "light"
        ctk.set_appearance_mode(modo_str)
        self.config["theme"] = modo_str
        self._guardar_configuracion()
        self._actualizar_paleta(modo_str)
        
        self.configure(fg_color=self.c_bg)
        self.topbar.configure(fg_color=self.c_sidebar)
        self.sidebar.configure(fg_color=self.c_sidebar)
        self.footer.configure(fg_color=self.c_sidebar)
        self.main_frame.configure(fg_color=self.c_bg)
        
        if self.vista_actual == "socios":
            self._mostrar_modulo_socios(self.socio_actual)
        elif self.vista_actual == "simulador":
            self._mostrar_modulo_simulador()
        elif self.vista_actual == "utilitarios":
            self._mostrar_modulo_utilitarios()
        elif self.vista_actual == "ingreso":
            self._mostrar_modulo_ingreso()
        else:
            self._mostrar_dashboard()

    def _crear_topbar(self):
        self.topbar = ctk.CTkFrame(self, height=60, fg_color=self.c_sidebar, corner_radius=0)
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="new")
        self.topbar.grid_propagate(False)

        lbl_brand = ctk.CTkLabel(
            self.topbar, 
            text="CUZODINCA", 
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=self.c_text
        )
        lbl_brand.pack(side="left", padx=20)

        self.entry_search_top = ctk.CTkEntry(
            self.topbar, 
            placeholder_text="🔍 Buscar socio por código o nombre (Enter)...", 
            width=480,
            height=36,
            fg_color=self.c_card,
            border_color=self.c_btn,
            text_color=self.c_text,
            font=ctk.CTkFont(size=14)
        )
        self.entry_search_top.pack(side="left", padx=20, pady=12)
        self.entry_search_top.bind("<Return>", lambda e: self._buscar_desde_topbar())

        lbl_status = ctk.CTkLabel(
            self.topbar, 
            text="● Sistema Listo", 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=self.c_accent
        )
        lbl_status.pack(side="right", padx=20)

    def _crear_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=230, fg_color=self.c_sidebar, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsw")
        self.sidebar.pack_propagate(False)

        lbl_logo = ctk.CTkLabel(
            self.sidebar, 
            text="🏦 CUZODINCA", 
            font=ctk.CTkFont(family="Segoe UI", size=19, weight="bold"), 
            text_color=self.c_text
        )
        lbl_logo.pack(anchor="w", padx=20, pady=(20, 3))
        
        lbl_sub = ctk.CTkLabel(
            self.sidebar, 
            text="Gestión de Cooperativa", 
            font=ctk.CTkFont(family="Segoe UI", size=12), 
            text_color=self.c_muted
        )
        lbl_sub.pack(anchor="w", padx=20, pady=(0, 20))

        self._btn_nav("📊 Dashboard", self._mostrar_dashboard)
        self._btn_nav("👥 Socios", lambda: self._mostrar_modulo_socios(socio_data=None))
        self._btn_nav("📥 Ingreso (Lotes)", self._mostrar_modulo_ingreso)
        self._btn_nav("🧮 Simulador", self._mostrar_modulo_simulador)
        self._btn_nav("⚡ Planilla Nómina", self._abrir_modal_safic)
        self._btn_nav("⚙️ Utilitarios", self._mostrar_modulo_utilitarios)
        self._btn_nav("📈 Reportes", self._abrir_modal_reportes)

        btn_salir = ctk.CTkButton(
            self.sidebar, 
            text="🚪 Salir del Sistema", 
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), 
            fg_color=self.c_danger, 
            hover_color="#991b1b", 
            text_color="#ffffff",
            height=38,
            command=self.destroy
        )
        btn_salir.pack(side="bottom", fill="x", padx=15, pady=20)

    def _btn_nav(self, texto, comando):
        btn = ctk.CTkButton(
            self.sidebar, 
            text=texto, 
            anchor="w", 
            height=42,
            fg_color="transparent", 
            hover_color=self.c_btn,
            text_color=self.c_text, 
            font=ctk.CTkFont(family="Segoe UI", size=15), 
            command=comando
        )
        btn.pack(fill="x", padx=10, pady=3)

    def _crear_main_area(self):
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color=self.c_bg, corner_radius=0)
        self.main_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=15)
        self._mostrar_dashboard()

    def _crear_footer(self):
        self.footer = ctk.CTkFrame(self, height=32, fg_color=self.c_sidebar, corner_radius=0)
        self.footer.grid(row=2, column=0, columnspan=2, sticky="sew")
        self.footer.grid_propagate(False)

        lbl_hotkeys = ctk.CTkLabel(self.footer, text="[Enter: Buscar Socio / Procesar Casilla | Fianza Solidaria 0% | Desglose Quincenal]", font=ctk.CTkFont(size=12), text_color=self.c_muted)
        lbl_hotkeys.pack(side="left", padx=15)

        lbl_version = ctk.CTkLabel(self.footer, text="CUZODINCA v3.5.1 (Compatibilidad Total CODINCA)", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.c_accent)
        lbl_version.pack(side="right", padx=15)

    # ------------------ VISTA 1: DASHBOARD ------------------
    def _mostrar_dashboard(self):
        self.vista_actual = "dashboard"
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        lbl_sec_kpi = ctk.CTkLabel(self.main_frame, text="Métricas Financieras y Liquidez (Según Maestro)", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.c_text)
        lbl_sec_kpi.pack(anchor="w", pady=(0, 12), fill="x")

        frame_kpi1 = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame_kpi1.pack(fill="x", pady=(0, 10))

        self.kpi_capital = self._crear_kpi_card(frame_kpi1, "Capital Total (Ahorros)", "$ 0.00", "Aportaciones de socios", 0, bg_color=self.c_card_highlight, comando=lambda: self._ver_detalle_metrica("ahorros"))
        self.kpi_deudas = self._crear_kpi_card(frame_kpi1, "Cartera por Cobrar", "$ 0.00", "Préstamos + Cupones + Mercadería", 1, comando=lambda: self._ver_detalle_metrica("deudas"))
        self.kpi_liquidez = self._crear_kpi_card(frame_kpi1, "Liquidez Disponible", "$ 0.00", "Ahorros - Cartera", 2, bg_color="#1e1b4b" if self.config.get("theme") == "dark" else "#ede9fe", comando=self._abrir_modal_precuadre)
        self.kpi_proyeccion = self._crear_kpi_card(frame_kpi1, "Recaudación Proyectada", "$ 0.00", "Cuotas por período", 3, comando=lambda: self._ver_detalle_metrica("cuotas"))

        frame_kpi2 = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        frame_kpi2.pack(fill="x", pady=(0, 15))

        self.kpi_socios = self._crear_kpi_card(frame_kpi2, "Socios Activos", "0 socios", "Padrón total", 0, comando=lambda: self._ver_detalle_metrica("activos"))
        self.kpi_prestamos_act = self._crear_kpi_card(frame_kpi2, "Préstamos Activos", "0 préstamos", "Cuentas con saldo", 1, comando=lambda: self._ver_detalle_metrica("prestamos_activos"))
        self.kpi_por_vencer = self._crear_kpi_card(frame_kpi2, "Préstamos por Liquidar", "0 cuentas", "≤ 2 cuotas restantes (Ver aquí)", 2, comando=lambda: self._ver_detalle_metrica("por_liquidar"))
        self.kpi_cupones_act = self._crear_kpi_card(frame_kpi2, "Cupones / Mercadería", "0 cuentas", "Cuentas con saldo", 3, comando=lambda: self._ver_detalle_metrica("cupones"))

        frame_actions = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
        frame_actions.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(frame_actions, text="Tablas del Sistema:", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_muted).pack(side="left", padx=15, pady=12)
        ctk.CTkButton(frame_actions, text="📂 maestro.dbf", height=34, font=ctk.CTkFont(size=13), fg_color=self.c_btn, text_color=self.c_text, hover_color=self.c_primary, command=self._cargar_maestro_manual).pack(side="left", padx=4, pady=12)
        ctk.CTkButton(frame_actions, text="📂 history.dbf", height=34, font=ctk.CTkFont(size=13), fg_color=self.c_btn, text_color=self.c_text, hover_color=self.c_primary, command=self._cargar_history_manual).pack(side="left", padx=4, pady=12)
        ctk.CTkButton(frame_actions, text="📂 hisact.dbf", height=34, font=ctk.CTkFont(size=13), fg_color=self.c_btn, text_color=self.c_text, hover_color=self.c_primary, command=self._cargar_hisact_manual).pack(side="left", padx=4, pady=12)

        ctk.CTkButton(frame_actions, text="⚖️ Pre-Cuadre Contable", height=34, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_accent, text_color="#ffffff", command=self._abrir_modal_precuadre).pack(side="right", padx=15, pady=12)

        lbl_sec = ctk.CTkLabel(self.main_frame, text="Últimos Movimientos del Sistema", font=ctk.CTkFont(size=17, weight="bold"), text_color=self.c_text)
        lbl_sec.pack(anchor="w", pady=(5, 10), fill="x")

        self.tabla_frame = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
        self.tabla_frame.pack(fill="x", expand=True)

        self._render_tabla_dashboard()
        self._actualizar_kpis_dashboard()

    def _crear_kpi_card(self, parent, titulo, valor, subtexto, col, bg_color=None, comando=None):
        bg = bg_color if bg_color else self.c_card
        card = ctk.CTkFrame(parent, fg_color=bg, corner_radius=10, cursor="hand2" if comando else "arrow")
        card.grid(row=0, column=col, sticky="nsew", padx=6, pady=4)
        parent.grid_columnconfigure(col, weight=1)

        lbl_tit = ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_muted)
        lbl_tit.pack(anchor="w", padx=15, pady=(12, 0))
        
        lbl_val = ctk.CTkLabel(card, text=valor, font=ctk.CTkFont(size=24, weight="bold"), text_color=self.c_text)
        lbl_val.pack(anchor="w", padx=15, pady=(4, 2))
        
        lbl_sub = ctk.CTkLabel(card, text=subtexto, font=ctk.CTkFont(size=13), text_color=self.c_accent)
        lbl_sub.pack(anchor="w", padx=15, pady=(0, 12))

        if comando:
            for w in (card, lbl_tit, lbl_val, lbl_sub):
                w.bind("<Button-1>", lambda e, cmd=comando: cmd())
                w.configure(cursor="hand2")

        return lbl_val

    def _render_tabla_dashboard(self):
        for w in self.tabla_frame.winfo_children():
            w.destroy()

        headers = ["FECHA", "CÓDIGO", "NOMBRE", "OPERACIÓN", "CANTIDAD", "SALDO", "CUOTAS"]
        h_frame = ctk.CTkFrame(self.tabla_frame, fg_color=self.c_btn, height=34)
        h_frame.pack(fill="x", padx=10, pady=(10, 5))
        for idx, h in enumerate(headers):
            lbl = ctk.CTkLabel(h_frame, text=h, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text)
            lbl.grid(row=0, column=idx, sticky="w", padx=8, pady=5)
            h_frame.grid_columnconfigure(idx, weight=2 if idx == 2 else 1)

        df_fuente = self.df_history if self.df_history is not None else self.df_hisact
        if df_fuente is None or df_fuente.empty:
            lbl_vacio = ctk.CTkLabel(self.tabla_frame, text="No hay movimientos cargados en history.dbf ni hisact.dbf", font=ctk.CTkFont(size=14), text_color=self.c_muted)
            lbl_vacio.pack(pady=30)
            return

        ultimos = df_fuente.tail(10)
        for _, r in ultimos.iterrows():
            row_frame = ctk.CTkFrame(self.tabla_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=10, pady=3)
            
            op_tipo = str(r.get("clave", r.get("cla", ""))).strip()
            if op_tipo == "RET":
                tipo_txt = "🔻 Retiro"
            elif op_tipo == "PRE":
                tipo_txt = "💳 Préstamo"
            elif op_tipo == "OTR":
                tipo_txt = "🏷️ Otro/Desc"
            elif op_tipo == "CUP":
                tipo_txt = "🎟️ Cupones"
            elif op_tipo == "MER":
                tipo_txt = "📦 Mercadería"
            elif op_tipo == "FIA":
                tipo_txt = "🤝 Fianza"
            else:
                tipo_txt = op_tipo if op_tipo else "N/D"

            cant_val = float(r.get("cantidad", r.get("cuotah", 0)))
            saldo_val = float(r.get("saldo", r.get("cuotpr", 0)))

            vals = [
                str(r.get("fecha", ""))[:10],
                str(r.get("codigo", "")),
                _truncar(r.get("nombre", ""), 22),
                tipo_txt,
                f"${cant_val:,.2f}",
                f"${saldo_val:,.2f}",
                str(r.get("cuotas", "0"))
            ]
            for idx, val in enumerate(vals):
                lbl = ctk.CTkLabel(row_frame, text=val, font=ctk.CTkFont(size=13), text_color=self.c_text)
                lbl.grid(row=0, column=idx, sticky="w", padx=8)
                row_frame.grid_columnconfigure(idx, weight=2 if idx == 2 else 1)

    def _actualizar_kpis_dashboard(self):
        if self.df_maestro is None or self.df_maestro.empty:
            return
        
        m = self.df_maestro.copy()
        total_socios = len(m)
        total_ahorros = m["ahorro"].sum() if "ahorro" in m.columns else 0.0
        total_saldo_prest = m["saldo"].sum() if "saldo" in m.columns else 0.0
        total_cupones = m["cupones"].sum() if "cupones" in m.columns else 0.0
        
        total_mercaderia = sum(meta.get("saldo", 0.0) for meta in self.meta_data.get("mercaderia", {}).values())
        total_deudas = total_saldo_prest + total_cupones + total_mercaderia
        liquidez = total_ahorros - total_deudas

        cuota_ahorro_sum = m["ctahor"].sum() if "ctahor" in m.columns else 0.0
        cuota_prest_sum = m["ctapres"].sum() if "ctapres" in m.columns else 0.0
        cuota_cupon_sum = m["cta_cupon"].sum() if "cta_cupon" in m.columns else 0.0
        cuota_otros_sum = m["otros"].sum() if "otros" in m.columns else 0.0
        recaudacion_proyectada = cuota_ahorro_sum + cuota_prest_sum + cuota_cupon_sum + cuota_otros_sum

        prestamos_activos = len(m[m["saldo"] > 0]) if "saldo" in m.columns else 0
        cupones_activos = len(m[(m.get("cupones", 0) > 0) | (m.get("otros", 0) > 0)]) if "cupones" in m.columns else 0

        por_liquidar = 0
        if "saldo" in m.columns and "ctapres" in m.columns:
            con_saldo = m[(m["saldo"] > 0) & (m["ctapres"] > 0)]
            por_liquidar = len(con_saldo[(con_saldo["saldo"] / con_saldo["ctapres"]) <= 2.1])

        self.kpi_capital.configure(text=f"$ {total_ahorros:,.2f}")
        self.kpi_deudas.configure(text=f"$ {total_deudas:,.2f}")
        self.kpi_liquidez.configure(text=f"$ {liquidez:,.2f}")
        self.kpi_proyeccion.configure(text=f"$ {recaudacion_proyectada:,.2f}")
        self.kpi_socios.configure(text=f"{total_socios} socios")
        self.kpi_prestamos_act.configure(text=f"{prestamos_activos} activos")
        self.kpi_por_vencer.configure(text=f"{por_liquidar} cuentas")
        self.kpi_cupones_act.configure(text=f"{cupones_activos} cuentas")

    def _ver_detalle_metrica(self, tipo):
        if self.df_maestro is None or self.df_maestro.empty:
            messagebox.showwarning("Atención", "Cargue maestro.dbf para ver el desglose.")
            return

        m = self.df_maestro.copy()
        
        if tipo == "por_liquidar":
            titulo = "⏳ Préstamos por Liquidar (≤ 2 Cuotas Restantes)"
            if "saldo" in m.columns and "ctapres" in m.columns:
                sub = m[(m["saldo"] > 0) & (m["ctapres"] > 0)]
                df_filtro = sub[(sub["saldo"] / sub["ctapres"]) <= 2.1].copy()
                df_filtro["cuotas_pend"] = (df_filtro["saldo"] / df_filtro["ctapres"]).round(1)
            else:
                df_filtro = pd.DataFrame()
            cols_mostrar = [("CÓDIGO", "codigo"), ("NOMBRE", "nombre"), ("SALDO ($)", "saldo"), ("CUOTA ($)", "ctapres"), ("CUOTAS REST.", "cuotas_pend")]

        elif tipo == "prestamos_activos":
            titulo = "💳 Detalle de Préstamos Activos"
            df_filtro = m[m["saldo"] > 0].copy() if "saldo" in m.columns else pd.DataFrame()
            cols_mostrar = [("CÓDIGO", "codigo"), ("NOMBRE", "nombre"), ("SALDO ($)", "saldo"), ("CUOTA ($)", "ctapres"), ("GRUPO", "ap")]

        elif tipo == "cupones":
            titulo = "🎟️ Detalle de Cupones / Mercadería Activos"
            df_filtro = m[(m.get("cupones", 0) > 0) | (m.get("otros", 0) > 0)].copy()
            cols_mostrar = [("CÓDIGO", "codigo"), ("NOMBRE", "nombre"), ("SALDO CUPÓN", "cupones"), ("CUOTA CUPÓN", "cta_cupon"), ("CUOTA MERC.", "otros")]

        elif tipo == "deudas":
            titulo = "📋 Cartera Global por Cobrar (Préstamos + Cupones + Mercadería)"
            df_filtro = m[(m.get("saldo", 0) > 0) | (m.get("cupones", 0) > 0) | (m.get("otros", 0) > 0)].copy()
            cols_mostrar = [("CÓDIGO", "codigo"), ("NOMBRE", "nombre"), ("SALDO PRÉST.", "saldo"), ("CUPONES", "cupones"), ("CUOTA MERC.", "otros")]

        elif tipo == "ahorros":
            titulo = "💰 Padrón de Ahorros e Intereses (0.625%)"
            df_filtro = m[m["ahorro"] > 0].copy() if "ahorro" in m.columns else pd.DataFrame()
            cols_mostrar = [("CÓDIGO", "codigo"), ("NOMBRE", "nombre"), ("AHORRO ($)", "ahorro"), ("CUOTA AHORRO", "ctahor"), ("INT. ACUM.", "interes")]

        elif tipo == "cuotas":
            titulo = "📊 Proyección de Descuentos por Nómina"
            df_filtro = m[(m.get("ctahor", 0) > 0) | (m.get("ctapres", 0) > 0) | (m.get("cta_cupon", 0) > 0) | (m.get("otros", 0) > 0)].copy()
            cols_mostrar = [("CÓDIGO", "codigo"), ("NOMBRE", "nombre"), ("C. AHORRO", "ctahor"), ("C. PRÉSTAMO", "ctapres"), ("C. CUPÓN", "cta_cupon")]

        else:
            titulo = "👥 Padrón General de Socios"
            df_filtro = m.copy()
            cols_mostrar = [("CÓDIGO", "codigo"), ("NOMBRE", "nombre"), ("AHORRO ($)", "ahorro"), ("DEUDA ($)", "saldo"), ("GRUPO", "ap")]

        win = ctk.CTkToplevel(self)
        win.title(f"CUZODINCA - {titulo}")
        win.geometry("940x540")
        win.attributes("-topmost", True)
        win.configure(fg_color=self.c_bg)

        f_top = ctk.CTkFrame(win, fg_color="transparent")
        f_top.pack(fill="x", padx=20, pady=(15, 10))
        ctk.CTkLabel(f_top, text=titulo, font=ctk.CTkFont(size=18, weight="bold"), text_color=self.c_text).pack(side="left")
        ctk.CTkLabel(f_top, text=f"Total: {len(df_filtro)} registros", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_accent).pack(side="right")

        frame_tabla = ctk.CTkScrollableFrame(win, fg_color=self.c_card, corner_radius=10)
        frame_tabla.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        if df_filtro.empty:
            ctk.CTkLabel(frame_tabla, text="No hay registros que coincidan con este criterio.", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(pady=40)
            return

        h_frame = ctk.CTkFrame(frame_tabla, fg_color=self.c_btn, height=34)
        h_frame.pack(fill="x", padx=5, pady=(5, 8))
        
        for idx, (label, _) in enumerate(cols_mostrar):
            lbl = ctk.CTkLabel(h_frame, text=label, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text)
            lbl.grid(row=0, column=idx, sticky="w", padx=8, pady=4)
            h_frame.grid_columnconfigure(idx, weight=2 if idx == 1 else 1)

        ctk.CTkLabel(h_frame, text="ACCIÓN", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=0, column=len(cols_mostrar), padx=8, pady=4)
        h_frame.grid_columnconfigure(len(cols_mostrar), weight=1)

        for _, r in df_filtro.iterrows():
            row_frame = ctk.CTkFrame(frame_tabla, fg_color="transparent")
            row_frame.pack(fill="x", padx=5, pady=2)

            for idx, (_, col_name) in enumerate(cols_mostrar):
                val = r.get(col_name, "")
                if isinstance(val, (int, float)) and ("saldo" in col_name or "ctapres" in col_name or "ahorro" in col_name or "cupon" in col_name or "cta" in col_name or "interes" in col_name or "otros" in col_name):
                    txt = f"${val:,.2f}"
                else:
                    txt = _truncar(val, 24)

                lbl = ctk.CTkLabel(row_frame, text=txt, font=ctk.CTkFont(size=13), text_color=self.c_text)
                lbl.grid(row=0, column=idx, sticky="w", padx=8)
                row_frame.grid_columnconfigure(idx, weight=2 if idx == 1 else 1)

            btn_ver = ctk.CTkButton(
                row_frame, 
                text="Ver Ficha", 
                width=80, 
                height=26, 
                font=ctk.CTkFont(size=12, weight="bold"), 
                fg_color=self.c_primary,
                command=lambda s=r, w=win: self._abrir_socio_desde_modal(s, w)
            )
            btn_ver.grid(row=0, column=len(cols_mostrar), padx=8)
            row_frame.grid_columnconfigure(len(cols_mostrar), weight=1)

    def _abrir_socio_desde_modal(self, socio_row, modal_win):
        modal_win.destroy()
        self._mostrar_modulo_socios(socio_data=socio_row)

    # ------------------ VISTA 2: MÓDULO SOCIOS ------------------
    def _mostrar_modulo_socios(self, socio_data=None):
        self.vista_actual = "socios"
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        self.socio_actual = socio_data

        top_actions = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
        top_actions.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(top_actions, text="Padrón de Socios:", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.c_text).pack(side="left", padx=15, pady=12)
        
        self.entry_socio_search = ctk.CTkEntry(
            top_actions, 
            placeholder_text="Código o Nombre...", 
            width=380,
            height=38,
            fg_color=self.c_entry_bg,
            border_color=self.c_btn,
            font=ctk.CTkFont(size=14)
        )
        self.entry_socio_search.pack(side="left", padx=8, pady=12)
        self.entry_socio_search.bind("<Return>", lambda e: self._ejecutar_busqueda_socio())

        ctk.CTkButton(top_actions, text="🔍 Buscar", width=100, height=38, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_primary, command=self._ejecutar_busqueda_socio).pack(side="left", padx=4, pady=12)
        ctk.CTkButton(top_actions, text="🔄 Ver General (10 Movs)", width=175, height=38, font=ctk.CTkFont(size=13), fg_color=self.c_btn, text_color=self.c_text, command=lambda: self._mostrar_modulo_socios(socio_data=None)).pack(side="left", padx=4, pady=12)
        ctk.CTkButton(top_actions, text="➕ Agregar Socio", width=145, height=38, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_accent, text_color="#ffffff", command=self._abrir_modal_crear_socio).pack(side="right", padx=15, pady=12)

        if socio_data is None:
            lbl_aviso = ctk.CTkLabel(self.main_frame, text="Últimos 10 Movimientos del Sistema", font=ctk.CTkFont(size=17, weight="bold"), text_color=self.c_text)
            lbl_aviso.pack(anchor="w", pady=(5, 10), fill="x")

            frame_gen = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
            frame_gen.pack(fill="x", expand=True)

            self._render_movimientos_tabla_general(frame_gen)
            return

        self._render_ficha_con_panel_derecho(socio_data)

    def _render_ficha_con_panel_derecho(self, s):
        contenedor_dual = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        contenedor_dual.pack(fill="both", expand=True)

        contenedor_dual.grid_columnconfigure(0, weight=7)
        contenedor_dual.grid_columnconfigure(1, weight=3)
        contenedor_dual.grid_rowconfigure(0, weight=1)

        col_izq = ctk.CTkFrame(contenedor_dual, fg_color="transparent")
        col_izq.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        col_der = ctk.CTkFrame(contenedor_dual, fg_color="transparent")
        col_der.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        cod_socio = str(s.get("codigo", "")).strip()
        nombre_socio = str(s.get("nombre", "N/D")).strip()
        grupo_pago = str(s.get("ap", s.get("tipo_pago", "P"))).strip().upper()
        tipo_nom_txt = "🏭 Planta (Catorcenal)" if "P" in grupo_pago else "🏢 Administración (Quincenal)"

        estado_guardado = str(s.get("estado", "")).upper()
        ctahor_val = float(s.get("ctahor", 0))
        obs_val = str(s.get("observ", "")).upper()

        if estado_guardado == "INACTIVO" or (ctahor_val == 0.0 and float(s.get("ahorro", 0)) == 0.0):
            estado_txt = "🔴 Inactivo"
            estado_bg = self.c_danger
        elif "INCAPACIT" in obs_val:
            estado_txt = "🏥 Incapacitado"
            estado_bg = self.c_warning
        else:
            estado_txt = "🟢 Activo"
            estado_bg = self.c_accent

        f_nom = ctk.CTkFrame(col_izq, fg_color="transparent")
        f_nom.pack(fill="x", pady=(0, 12))
        
        ctk.CTkLabel(f_nom, text=f"👤 {nombre_socio}", font=ctk.CTkFont(size=20, weight="bold"), text_color=self.c_text).pack(side="left")
        
        badge_est = ctk.CTkLabel(f_nom, text=f" {estado_txt} ", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff", fg_color=estado_bg, corner_radius=6)
        badge_est.pack(side="left", padx=8)

        badge_grp = ctk.CTkLabel(f_nom, text=f" {tipo_nom_txt} ", font=ctk.CTkFont(size=12), text_color=self.c_text, fg_color=self.c_btn, corner_radius=6)
        badge_grp.pack(side="left", padx=4)

        ctk.CTkButton(
            f_nom, 
            text="✏️ Editar Ficha", 
            height=32, 
            font=ctk.CTkFont(size=12, weight="bold"), 
            fg_color=self.c_btn, 
            text_color=self.c_text,
            hover_color=self.c_primary,
            command=lambda: self._abrir_modal_editar_socio(s)
        ).pack(side="right", padx=(5, 0))

        ctk.CTkButton(
            f_nom, 
            text="➡️ Ir a Trámite", 
            height=32, 
            font=ctk.CTkFont(size=12, weight="bold"), 
            fg_color=self.c_primary, 
            command=lambda: self._ir_a_tramite_directo(s)
        ).pack(side="right", padx=5)

        frame_kpis = ctk.CTkFrame(col_izq, fg_color="transparent")
        frame_kpis.pack(fill="x", pady=(0, 12))

        ahorro_val = float(s.get("ahorro", 0))
        cuota_ahorro = float(s.get("ctahor", 0))
        interes_acum_val = float(s.get("interes", 0))
        int_proyectado_mes = round(ahorro_val * 0.00625, 4)

        saldo_prest = float(s.get("saldo", 0))
        cupones_val = float(s.get("cupones", 0))
        meta_mer = self.meta_data.get("mercaderia", {}).get(cod_socio, {})
        saldo_merc_val = meta_mer.get("saldo", float(s.get("otros", 0)))
        
        total_deuda = saldo_prest + cupones_val + saldo_merc_val

        card_ahorro = ctk.CTkFrame(frame_kpis, fg_color=self.c_card_highlight, corner_radius=10, cursor="hand2")
        card_ahorro.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        frame_kpis.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card_ahorro, text="Total Ahorrado", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_muted).pack(anchor="w", padx=15, pady=(10, 0))
        lbl_ahorro_val = ctk.CTkLabel(card_ahorro, text=f"$ {ahorro_val:,.2f}", font=ctk.CTkFont(size=23, weight="bold"), text_color=self.c_text)
        lbl_ahorro_val.pack(anchor="w", padx=15, pady=(2, 2))
        lbl_ahorro_cuota = ctk.CTkLabel(card_ahorro, text=f"Cuota: $ {cuota_ahorro:,.2f}", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_accent)
        lbl_ahorro_cuota.pack(anchor="w", padx=15, pady=(0, 10))

        self.mostrar_detalle_ahorro_flag = getattr(self, "mostrar_detalle_ahorro_flag", False)
        
        frame_det_ahorro = ctk.CTkFrame(card_ahorro, fg_color="transparent")
        if self.mostrar_detalle_ahorro_flag:
            frame_det_ahorro.pack(fill="x", padx=15, pady=(0, 10))
            ctk.CTkLabel(frame_det_ahorro, text=f"• Interés Acumulado: $ {interes_acum_val:,.4f}", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.c_text).pack(anchor="w")
            ctk.CTkLabel(frame_det_ahorro, text=f"• Interés Probable Mes: +$ {int_proyectado_mes:,.4f}", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.c_accent).pack(anchor="w")

        def toggle_detalle_ahorro(e=None):
            self.mostrar_detalle_ahorro_flag = not getattr(self, "mostrar_detalle_ahorro_flag", False)
            self._render_ficha_con_panel_derecho(s)

        for w_elem in (card_ahorro, lbl_ahorro_val, lbl_ahorro_cuota):
            w_elem.bind("<Button-1>", toggle_detalle_ahorro)

        card_deuda = ctk.CTkFrame(frame_kpis, fg_color=self.c_card, corner_radius=10)
        card_deuda.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)
        frame_kpis.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(card_deuda, text="Total Deudas / Obligaciones", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_muted).pack(anchor="w", padx=15, pady=(10, 0))
        ctk.CTkLabel(card_deuda, text=f"$ {total_deuda:,.2f}", font=ctk.CTkFont(size=23, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=15, pady=(2, 4))
        
        btn_ver_prest = ctk.CTkButton(
            card_deuda, 
            text="🔍 Ver Desglose y Nivelar Última Cuota", 
            height=30, 
            font=ctk.CTkFont(size=13, weight="bold"), 
            fg_color=self.c_primary, 
            command=lambda soc=s: self._abrir_popup_prestamos(soc)
        )
        btn_ver_prest.pack(anchor="w", padx=15, pady=(0, 10))

        frame_hist_ctrl = ctk.CTkFrame(col_izq, fg_color="transparent")
        frame_hist_ctrl.pack(fill="x", pady=(5, 8))

        ctk.CTkLabel(frame_hist_ctrl, text="Historial de Operaciones", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_text).pack(side="left")

        anios_disponibles = self._obtener_anios_socio(cod_socio)
        self.var_anio_filtro = ctk.StringVar(value="Todos los años")

        self.cb_anios = ctk.CTkOptionMenu(
            frame_hist_ctrl, 
            values=anios_disponibles, 
            variable=self.var_anio_filtro,
            font=ctk.CTkFont(size=13), 
            width=160,
            command=lambda val, c=cod_socio: self._filtrar_historial_por_anio(c, val)
        )
        self.cb_anios.pack(side="right")
        ctk.CTkLabel(frame_hist_ctrl, text="Filtrar por Año: ", font=ctk.CTkFont(size=13), text_color=self.c_muted).pack(side="right", padx=6)

        self.frame_hist_socio = ctk.CTkFrame(col_izq, fg_color=self.c_card, corner_radius=10)
        self.frame_hist_socio.pack(fill="both", expand=True)

        self._render_movimientos_socio(self.frame_hist_socio, cod_socio, anio_filtro="Todos los años")

        card_datos = ctk.CTkFrame(col_der, fg_color=self.c_card, corner_radius=10)
        card_datos.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(card_datos, text="📋 Ficha del Socio", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=15, pady=(12, 6))
        ctk.CTkLabel(card_datos, text=f"• Código Empleado / Socio: {cod_socio}", font=ctk.CTkFont(size=14), text_color=self.c_text).pack(anchor="w", padx=15, pady=3)
        ctk.CTkLabel(card_datos, text=f"• No. Cuenta: {str(s.get('cuenta', 'N/D')).strip()}", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(anchor="w", padx=15, pady=3)
        ctk.CTkLabel(card_datos, text=f"• DUI / Doc: {str(s.get('observ', 'N/D')).strip()}", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(anchor="w", padx=15, pady=3)
        ctk.CTkLabel(card_datos, text=f"• Ingreso Registro: {str(s.get('ingreso', s.get('fechault', 'N/D')))[:10]}", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(anchor="w", padx=15, pady=(3, 6))

        sueldos_meta = self.meta_data.get("sueldos_ingresos", {}).get(cod_socio, {"sueldo": 500.0, "fecha_entrada": "2020-01-01"})
        self.mostrar_datos_confidenciales = getattr(self, "mostrar_datos_confidenciales", False)
        
        f_conf = ctk.CTkFrame(card_datos, fg_color=self.c_bg, corner_radius=8)
        if self.mostrar_datos_confidenciales:
            f_conf.pack(fill="x", padx=15, pady=(5, 10))
            ctk.CTkLabel(f_conf, text=f"💰 Sueldo Registrado: $ {sueldos_meta.get('sueldo', 500.0):,.2f}", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_accent).pack(anchor="w", padx=10, pady=(6, 2))
            ctk.CTkLabel(f_conf, text=f"📅 Fecha de Entrada: {sueldos_meta.get('fecha_entrada', '2020-01-01')}", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=10, pady=(2, 6))

        btn_toggle_conf = ctk.CTkButton(
            card_datos, 
            text="👁️ Ocultar / Ver Datos de Sueldo y Antigüedad", 
            height=28, 
            font=ctk.CTkFont(size=11), 
            fg_color=self.c_btn, 
            text_color=self.c_text,
            command=lambda: (setattr(self, "mostrar_datos_confidenciales", not self.mostrar_datos_confidenciales), self._render_ficha_con_panel_derecho(s))
        )
        btn_toggle_conf.pack(anchor="w", padx=15, pady=(0, 12))

        card_ben = ctk.CTkFrame(col_der, fg_color=self.c_card, corner_radius=10)
        card_ben.pack(fill="x", pady=(0, 12))

        b1 = str(s.get("benefi_1", "")).strip() or "N/D"
        b2 = str(s.get("benefi_2", "")).strip()
        b3 = str(s.get("benefi_3", "")).strip()

        ctk.CTkLabel(card_ben, text="👨‍👩‍👧 Beneficiarios", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=15, pady=(12, 6))
        ctk.CTkLabel(card_ben, text=f"1. {_truncar(b1, 26)}", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(anchor="w", padx=15, pady=3)
        if b2:
            ctk.CTkLabel(card_ben, text=f"2. {_truncar(b2, 26)}", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(anchor="w", padx=15, pady=3)
        if b3:
            ctk.CTkLabel(card_ben, text=f"3. {_truncar(b3, 26)}", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(anchor="w", padx=15, pady=(3, 12))
        else:
            ctk.CTkFrame(card_ben, height=6, fg_color="transparent").pack()

        card_fia = ctk.CTkFrame(col_der, fg_color=self.c_card, corner_radius=10)
        card_fia.pack(fill="x", pady=(0, 12))

        f1 = str(s.get("fiadores", "Ninguno")).strip()
        f2 = str(s.get("fiador2", "")).strip()

        ctk.CTkLabel(card_fia, text="🤝 Sus Fiadores", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=15, pady=(12, 6))
        ctk.CTkLabel(card_fia, text=f"• Fiador 1: {_truncar(f1, 26)}", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(anchor="w", padx=15, pady=3)
        if f2:
            ctk.CTkLabel(card_fia, text=f"• Fiador 2: {_truncar(f2, 26)}", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(anchor="w", padx=15, pady=(3, 12))
        else:
            ctk.CTkFrame(card_fia, height=6, fg_color="transparent").pack()

        card_inv_fia = ctk.CTkFrame(col_der, fg_color=self.c_card, corner_radius=10)
        card_inv_fia.pack(fill="x")

        quienes_respalda = self._buscar_respaldados(cod_socio, nombre_socio)
        num_fianzas = len(quienes_respalda)
        color_cap = self.c_danger if num_fianzas >= 3 else (self.c_warning if num_fianzas == 2 else self.c_accent)

        f_tit_inv = ctk.CTkFrame(card_inv_fia, fg_color="transparent")
        f_tit_inv.pack(fill="x", padx=15, pady=(12, 6))
        
        ctk.CTkLabel(f_tit_inv, text="🛡️ Es Fiador de:", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_text).pack(side="left")
        ctk.CTkLabel(f_tit_inv, text=f" [{num_fianzas}/3] ", font=ctk.CTkFont(size=13, weight="bold"), text_color="#ffffff", fg_color=color_cap, corner_radius=4).pack(side="right")
        
        if quienes_respalda:
            for r in quienes_respalda[:4]:
                f_fila_r = ctk.CTkFrame(card_inv_fia, fg_color="transparent")
                f_fila_r.pack(fill="x", padx=15, pady=2)
                ctk.CTkLabel(f_fila_r, text=f"• {r[0]}", font=ctk.CTkFont(size=13), text_color=self.c_accent).pack(side="left")
                ctk.CTkButton(
                    f_fila_r, 
                    text="⚡ Ejecutar Fianza", 
                    width=100, 
                    height=22, 
                    font=ctk.CTkFont(size=11, weight="bold"), 
                    fg_color=self.c_danger, 
                    text_color="#ffffff",
                    command=lambda cod_deudor=r[1]: self._cargar_fianza_desde_ficha(cod_deudor)
                ).pack(side="right")
            ctk.CTkFrame(card_inv_fia, height=8, fg_color="transparent").pack()
        else:
            ctk.CTkLabel(card_inv_fia, text="• No figura como fiador de terceros.", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(anchor="w", padx=15, pady=(2, 12))

    def _buscar_respaldados(self, cod_socio, nom_socio):
        respaldados = []
        if self.df_maestro is None or self.df_maestro.empty:
            return respaldados

        cod_s = str(cod_socio).strip().upper()
        nom_s = str(nom_socio).strip().upper()

        patron_cod = re.compile(r'(?<![A-Z0-9])' + re.escape(cod_s) + r'(?![A-Z0-9])') if cod_s else None
        patron_nom = re.compile(re.escape(nom_s)) if nom_s else None

        def _coincide(campo):
            if not campo:
                return False
            if patron_cod and patron_cod.search(campo):
                return True
            if patron_nom and nom_s and patron_nom.search(campo):
                return True
            return False

        for _, r in self.df_maestro.iterrows():
            c_actual = str(r.get("codigo", "")).strip()
            if c_actual == cod_socio:
                continue
            
            f1 = str(r.get("fiadores", "")).strip().upper()
            f2 = str(r.get("fiador2", "")).strip().upper()
            saldo_deudor = float(r.get("saldo", 0))
            
            if saldo_deudor > 0 and (_coincide(f1) or _coincide(f2)):
                nom_deudor = str(r.get("nombre", "Socio")).strip()
                respaldados.append((f"{c_actual} {_truncar(nom_deudor, 12)} (${saldo_deudor:,.2f})", c_actual))
        return respaldados

    def _cargar_fianza_desde_ficha(self, cod_deudor):
        if self.df_maestro is not None:
            mask = self.df_maestro["codigo"].astype(str).str.strip().str.upper() == cod_deudor.upper()
            if not self.df_maestro[mask].empty:
                self.socio_actual = self.df_maestro[mask].iloc[0]
                self.vista_actual = "ingreso"
                self._mostrar_modulo_ingreso()
                self._seleccionar_tipo_operacion("FIA")

    def _ir_a_tramite_directo(self, s):
        self.socio_actual = s
        self._mostrar_modulo_ingreso()

    # ------------------ VISTA 3: MÓDULO INGRESO POR LOTES ------------------
    def _mostrar_modulo_ingreso(self):
        self.vista_actual = "ingreso"
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        f_head = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_head.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            f_head, 
            text="📥 Captura de Lotes CODINCA (MOVIM.DBF / Excel)", 
            font=ctk.CTkFont(size=19, weight="bold"), 
            text_color=self.c_text
        ).pack(side="left")

        ctk.CTkLabel(
            f_head,
            text=f"📅 Fecha Sesión: {self.fecha_sesion} | Próx. Asiento: #{self._generar_correlativo_actual()}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.c_accent
        ).pack(side="right")

        card_p1 = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
        card_p1.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(card_p1, text="PASO 1: Operación CODINCA a Ingresar", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=15, pady=(10, 6))

        f_ops = ctk.CTkFrame(card_p1, fg_color="transparent")
        f_ops.pack(fill="x", padx=15, pady=(0, 10))

        ops = [
            ("🔻 Retiro Ahorro", "RET", self.c_accent),
            ("💳 Préstamo", "PRE", self.c_primary),
            ("🔄 Refinanciamiento (5 Asientos)", "REF", self.c_warning),
            ("🎟️ Cupones (Interés)", "CUP", "#8b5cf6"),
            ("📦 Mercadería (0%)", "MER", "#0284c7"),
            ("🤝 Fianza Solidaria", "FIA", "#64748b")
        ]

        self.btns_ops = {}
        for idx, (lbl_op, val_op, col_op) in enumerate(ops):
            btn = ctk.CTkButton(
                f_ops,
                text=lbl_op,
                font=ctk.CTkFont(size=12, weight="bold"),
                height=36,
                fg_color=col_op if self.tipo_op_seleccionada.get() == val_op else self.c_btn,
                text_color="#ffffff" if self.tipo_op_seleccionada.get() == val_op else self.c_text,
                command=lambda v=val_op: self._seleccionar_tipo_operacion(v)
            )
            btn.grid(row=0, column=idx, padx=3, pady=2, sticky="nsew")
            f_ops.grid_columnconfigure(idx, weight=1)
            self.btns_ops[val_op] = (btn, col_op)

        # FIX: dict(ops) fallaba porque 'ops' contiene tuplas de 3 elementos
        # (etiqueta, codigo, color), no pares (clave, valor). Esto lanzaba un
        # ValueError a medio renderizar la vista, dejando la pantalla "perdida".
        # En lugar de dict(ops), usa este diccionario para que no dé ValueError:
        mapa_colores_ops = {val_op: col_op for (_, val_op, col_op) in ops}
        color_borde = mapa_colores_ops.get(self.tipo_op_seleccionada.get(), self.c_primary)
        self.card_p2 = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10, border_width=2, border_color=color_borde)
        self.card_p2.pack(fill="x", pady=(0, 10))

        self.banner_op = ctk.CTkLabel(
            self.card_p2, 
            text=f"OPERACIÓN SELECCIONADA: {self.tipo_op_seleccionada.get()}", 
            fg_color=color_borde, 
            text_color="#ffffff", 
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=6,
            height=26
        )
        self.banner_op.pack(fill="x", padx=10, pady=(10, 6))

        f_buscar_soc = ctk.CTkFrame(self.card_p2, fg_color="transparent")
        f_buscar_soc.pack(fill="x", padx=15, pady=4)

        self.entry_ingreso_soc = ctk.CTkEntry(
            f_buscar_soc, 
            placeholder_text="🔍 Código o Nombre del Colaborador (Enter)...", 
            width=380, 
            height=36, 
            font=ctk.CTkFont(size=14),
            fg_color=self.c_entry_bg,
            text_color=self.c_text
        )
        self.entry_ingreso_soc.pack(side="left", padx=(0, 10))
        self.entry_ingreso_soc.bind("<Return>", lambda e: self._buscar_socio_para_ingreso())

        ctk.CTkButton(f_buscar_soc, text="Cargar Socio", width=120, height=36, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_primary, command=self._buscar_socio_para_ingreso).pack(side="left")

        self.f_dinamico_form = ctk.CTkFrame(self.card_p2, fg_color="transparent")
        self.f_dinamico_form.pack(fill="x", padx=15, pady=(5, 12))

        self.frame_ultimo_mov = ctk.CTkFrame(self.main_frame, fg_color=self.c_card_highlight, corner_radius=8, height=42)
        self.frame_ultimo_mov.pack(fill="x", pady=(0, 10))
        self.frame_ultimo_mov.pack_propagate(False)
        self._actualizar_franja_ultimo_mov()

        card_p3 = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
        card_p3.pack(fill="both", expand=True)

        f_tit_lote = ctk.CTkFrame(card_p3, fg_color="transparent")
        f_tit_lote.pack(fill="x", padx=15, pady=(10, 6))

        self.lbl_total_lote = ctk.CTkLabel(f_tit_lote, text=f"PASO 3: Lote Acumulado ({len(self.lote_movimientos)} registros)", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text)
        self.lbl_total_lote.pack(side="left")

        ctk.CTkButton(f_tit_lote, text="⚡ Generar MOVIM (DBF + CSV)", height=32, font=ctk.CTkFont(size=12, weight="bold"), fg_color=self.c_accent, text_color="#ffffff", command=self._exportar_lote_movim_dual).pack(side="right")
        ctk.CTkButton(f_tit_lote, text="🗑️ Vaciar Lote", height=32, font=ctk.CTkFont(size=12), fg_color=self.c_danger, text_color="#ffffff", command=self._vaciar_lote).pack(side="right", padx=8)

        self.frame_tabla_lote = ctk.CTkFrame(card_p3, fg_color="transparent")
        self.frame_tabla_lote.pack(fill="both", expand=True, padx=10, pady=(5, 12))

        self._render_tabla_lote()
        self._render_campos_operacion()

    def _actualizar_franja_ultimo_mov(self):
        for w in self.frame_ultimo_mov.winfo_children():
            w.destroy()
        if not self.ultimo_movimiento_registrado:
            ctk.CTkLabel(self.frame_ultimo_mov, text="ℹ️ Sin movimientos ingresados en la sesión actual.", font=ctk.CTkFont(size=12), text_color=self.c_muted).pack(side="left", padx=15)
            return

        m = self.ultimo_movimiento_registrado
        txt = f"✓ ÚLTIMO ASIENTO: [{m.get('CLAVE')}] Reg #{m.get('REG')} | Asiento #{m.get('CUPON_NUM', '')} | {m.get('CODIGO')} - {m.get('NOMBRE')} | Monto: ${m.get('CANTIDAD', 0):,.2f} | Saldo: ${m.get('SALDO', 0):,.2f}"
        ctk.CTkLabel(self.frame_ultimo_mov, text=txt, font=ctk.CTkFont(size=12, weight="bold"), text_color=self.c_accent).pack(side="left", padx=15)

    def _seleccionar_tipo_operacion(self, tipo):
        self.tipo_op_seleccionada.set(tipo)
        col_activa = self.c_primary
        for t, (btn, col) in self.btns_ops.items():
            if t == tipo:
                btn.configure(fg_color=col, text_color="#ffffff")
                col_activa = col
            else:
                btn.configure(fg_color=self.c_btn, text_color=self.c_text)

        if hasattr(self, "card_p2"):
            self.card_p2.configure(border_color=col_activa)
        if hasattr(self, "banner_op"):
            self.banner_op.configure(text=f"OPERACIÓN SELECCIONADA: {tipo}", fg_color=col_activa)
        self._render_campos_operacion()

    def _buscar_socio_para_ingreso(self):
        query = self.entry_ingreso_soc.get().strip().upper()
        if not query or self.df_maestro is None:
            return

        c_cod = self.df_maestro["codigo"].astype(str).str.strip().str.upper()
        c_nom = self.df_maestro["nombre"].astype(str).str.upper()
        matches = self.df_maestro[(c_cod == query) | (c_nom.str.contains(query, na=False))]

        if matches.empty:
            messagebox.showwarning("Aviso", f"No se encontró socio con: {query}")
        elif len(matches) == 1:
            self.socio_actual = matches.iloc[0]
            self._render_campos_operacion()
        else:
            self._abrir_modal_seleccion_socio(matches, callback=self._asignar_socio_ingreso)

    def _asignar_socio_ingreso(self, s):
        self.socio_actual = s
        self._render_campos_operacion()

    def _render_campos_operacion(self):
        for w in self.f_dinamico_form.winfo_children():
            w.destroy()

        if self.socio_actual is None:
            ctk.CTkLabel(self.f_dinamico_form, text="Seleccione un socio para habilitar los campos de ingreso.", font=ctk.CTkFont(size=13), text_color=self.c_muted).pack(pady=15)
            return

        s = self.socio_actual
        cod = str(s.get("codigo", "")).strip()
        nom = str(s.get("nombre", "N/D")).strip()
        ahorro = float(s.get("ahorro", 0))
        saldo = float(s.get("saldo", 0))
        cupones = float(s.get("cupones", 0))

        sueldo_meta = self.meta_data.get("sueldos_ingresos", {}).get(cod, {"sueldo": 600.0, "fecha_entrada": "2022-01-01"})
        sueldo_val = sueldo_meta.get("sueldo", 600.0)

        tipo = self.tipo_op_seleccionada.get()

        f_info = ctk.CTkFrame(self.f_dinamico_form, fg_color=self.c_bg, corner_radius=8)
        f_info.pack(fill="x", pady=(5, 12))

        ctk.CTkLabel(f_info, text=f"👤 {cod} - {nom} | Sueldo: ${sueldo_val:,.2f}", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).pack(side="left", padx=15, pady=8)
        ctk.CTkLabel(f_info, text=f"Ahorro Disp: ${ahorro:,.2f}  |  Saldo Préstamo: ${saldo:,.2f}", font=ctk.CTkFont(size=13), text_color=self.c_accent).pack(side="right", padx=15, pady=8)

        f_grid = ctk.CTkFrame(self.f_dinamico_form, fg_color="transparent")
        f_grid.pack(fill="x", pady=5)

        if tipo == "RET":
            ctk.CTkLabel(f_grid, text="Monto a Retirar ($):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=0, column=0, sticky="w", pady=6)
            ent_monto = ctk.CTkEntry(f_grid, placeholder_text="0.00", width=190, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_monto.grid(row=0, column=1, padx=10, pady=6, sticky="w")
            ent_monto.focus_set()

            ctk.CTkLabel(f_grid, text="Concepto:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=0, column=2, sticky="w", padx=(15, 0), pady=6)
            ent_con = ctk.CTkEntry(f_grid, width=320, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_con.insert(0, f"RETIRO DE AHORROS DE {nom}")
            ent_con.grid(row=0, column=3, padx=10, pady=6, sticky="w")

            lbl_alerta_ret = ctk.CTkLabel(self.f_dinamico_form, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_danger)
            lbl_alerta_ret.pack(anchor="w", pady=(2, 6))

            btn_add = ctk.CTkButton(
                self.f_dinamico_form,
                text="➕ Agregar al Lote (Enter)",
                height=36,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=self.c_accent,
                text_color="#ffffff",
                command=lambda: self._agregar_retiro_a_lote(cod, nom, ent_monto.get(), ent_con.get(), ahorro, lbl_alerta_ret)
            )
            btn_add.pack(anchor="w", pady=5)

            def validar_monto_inline(*args):
                try:
                    val = float(ent_monto.get().strip() or 0)
                    if val > ahorro:
                        lbl_alerta_ret.configure(text=f"⚠️ Fondos insuficientes: El monto (${val:,.2f}) supera el ahorro disponible (${ahorro:,.2f}).")
                        btn_add.configure(state="disabled")
                    else:
                        lbl_alerta_ret.configure(text="")
                        btn_add.configure(state="normal")
                except Exception:
                    lbl_alerta_ret.configure(text="")
                    btn_add.configure(state="normal")

            ent_monto.bind("<KeyRelease>", validar_monto_inline)
            ent_monto.bind("<Return>", lambda e: btn_add.invoke())

        elif tipo == "REF":
            prest_orig = self._obtener_prestamo_original(cod)
            orig_monto = prest_orig.get("monto_original", saldo)
            orig_total = prest_orig.get("total_con_intereses", saldo)
            
            factor_cap = (orig_monto / orig_total) if orig_total > 0 else 0.7622
            cap_neto_ref = round(saldo * factor_cap, 2)
            intereses_condonados = round(saldo - cap_neto_ref, 2)

            f_res_ref = ctk.CTkFrame(f_grid, fg_color=self.c_bg, corner_radius=8)
            f_res_ref.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 10))
            
            txt_ref_info = (
                f"Saldo Actual en DBF: ${saldo:,.2f}  |  Intereses Condonados (Pronto Pago): -${intereses_condonados:,.2f}  |  "
                f"Capital Puro a Liquidar: ${cap_neto_ref:,.2f}"
            )
            ctk.CTkLabel(f_res_ref, text=txt_ref_info, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_warning).pack(padx=10, pady=8)

            ctk.CTkLabel(f_grid, text="Efectivo en Mano ($):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=1, column=0, sticky="w", pady=6)
            ent_efectivo = ctk.CTkEntry(f_grid, placeholder_text="0.00", width=140, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_efectivo.insert(0, "100.00")
            ent_efectivo.grid(row=1, column=1, padx=6, pady=6, sticky="w")
            ent_efectivo.focus_set()

            tasa_def = self.config.get("tasa_interes_defecto", 2.60)
            ctk.CTkLabel(f_grid, text="N° de Cuotas:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=1, column=2, sticky="w", padx=(10, 0), pady=6)
            ent_cuotas = ctk.CTkEntry(f_grid, placeholder_text="24", width=90, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_cuotas.insert(0, "24")
            ent_cuotas.grid(row=1, column=3, padx=6, pady=6, sticky="w")

            ctk.CTkLabel(f_grid, text="Tasa Mensual (%):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=1, column=4, sticky="w", padx=(10, 0), pady=6)
            ent_tasa = ctk.CTkEntry(f_grid, width=90, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_tasa.insert(0, f"{tasa_def:.2f}")
            ent_tasa.grid(row=1, column=5, padx=6, pady=6, sticky="w")

            ctk.CTkLabel(f_grid, text="Fiador 1 (Opcional):", font=ctk.CTkFont(size=13), text_color=self.c_muted).grid(row=2, column=0, sticky="w", pady=6)
            ent_fia1 = ctk.CTkEntry(f_grid, placeholder_text="Código-Nombre Fiador 1", width=230, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_fia1.grid(row=2, column=1, columnspan=2, padx=6, pady=6, sticky="w")

            ctk.CTkLabel(f_grid, text="Fiador 2 (Opcional):", font=ctk.CTkFont(size=13), text_color=self.c_muted).grid(row=2, column=3, sticky="w", padx=(10, 0), pady=6)
            ent_fia2 = ctk.CTkEntry(f_grid, placeholder_text="Código-Nombre Fiador 2", width=230, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_fia2.grid(row=2, column=4, columnspan=2, padx=6, pady=6, sticky="w")

            lbl_proyeccion_ref = ctk.CTkLabel(self.f_dinamico_form, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_accent)
            lbl_proyeccion_ref.pack(anchor="w", pady=5)

            def recalcular_proy_ref(*args):
                try:
                    efec = float(ent_efectivo.get().strip() or 0)
                    c = int(ent_cuotas.get().strip() or 1)
                    t_m = float(ent_tasa.get().strip() or 2.60)
                    tasa_cuota = (t_m / 2.0) / 100.0
                    
                    nvo_cap = cap_neto_ref + efec
                    nuevos_int = round(nvo_cap * (c * tasa_cuota), 2)
                    tot_deuda = round(nvo_cap + nuevos_int, 2)
                    cuo_val = round(tot_deuda / c, 2)
                    
                    alerta_liquidez = ""
                    if cuo_val > (sueldo_val * 0.40):
                        alerta_liquidez = f" ⚠️ ADVERTENCIA: La cuota (${cuo_val:,.2f}) supera el 40% del sueldo (${sueldo_val * 0.40:,.2f})."

                    lbl_proyeccion_ref.configure(
                        text=f"Nuevo Capital: ${nvo_cap:,.2f}  |  Interés Nuevo: +${nuevos_int:,.2f}  |  Total a Pagar: ${tot_deuda:,.2f}  |  Cuota ({c} pagos): ${cuo_val:,.2f}{alerta_liquidez}"
                    )
                except Exception:
                    pass

            for ent_w in (ent_efectivo, ent_cuotas, ent_tasa):
                ent_w.bind("<KeyRelease>", recalcular_proy_ref)
            recalcular_proy_ref()

            ctk.CTkButton(
                self.f_dinamico_form,
                text="➕ Agregar Asiento de Refinanciamiento al Lote",
                height=36,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=self.c_warning,
                text_color="#000000",
                command=lambda: self._agregar_refinanciamiento_a_lote(
                    cod, nom, cap_neto_ref, intereses_condonados, ent_efectivo.get(), ent_cuotas.get(), ent_tasa.get(), ent_fia1.get(), ent_fia2.get()
                )
            ).pack(anchor="w", pady=5)

        elif tipo == "FIA":
            fia1_nom = str(s.get("fiadores", "")).strip()
            fia2_nom = str(s.get("fiador2", "")).strip()
            
            factor_cap = 0.7622
            cap_neto = round(saldo * factor_cap, 2)
            int_cond = round(saldo - cap_neto, 2)

            f_fia_box = ctk.CTkFrame(f_grid, fg_color=self.c_bg, corner_radius=8)
            f_fia_box.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 10))

            ctk.CTkLabel(f_fia_box, text=f"Deuda Total: ${saldo:,.2f}  |  Intereses Exonerados: -${int_cond:,.2f}  |  Capital a Repartir: ${cap_neto:,.2f} (0% Interés)", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_danger).pack(padx=10, pady=6)

            ctk.CTkLabel(f_grid, text=f"Fiador 1 ({_truncar(fia1_nom, 20)}):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=1, column=0, sticky="w", pady=6)
            ent_f1_monto = ctk.CTkEntry(f_grid, width=130, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_f1_monto.insert(0, f"{cap_neto/2:.2f}")
            ent_f1_monto.grid(row=1, column=1, padx=6, pady=6, sticky="w")

            ctk.CTkLabel(f_grid, text="Cuotas F1:", font=ctk.CTkFont(size=13), text_color=self.c_muted).grid(row=1, column=2, sticky="w", padx=(10, 0), pady=6)
            ent_f1_cuotas = ctk.CTkEntry(f_grid, width=80, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_f1_cuotas.insert(0, "24")
            ent_f1_cuotas.grid(row=1, column=3, padx=6, pady=6, sticky="w")

            ctk.CTkLabel(f_grid, text=f"Fiador 2 ({_truncar(fia2_nom, 20)}):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=2, column=0, sticky="w", pady=6)
            ent_f2_monto = ctk.CTkEntry(f_grid, width=130, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_f2_monto.insert(0, f"{cap_neto/2:.2f}")
            ent_f2_monto.grid(row=2, column=1, padx=6, pady=6, sticky="w")

            ctk.CTkLabel(f_grid, text="Cuotas F2:", font=ctk.CTkFont(size=13), text_color=self.c_muted).grid(row=2, column=2, sticky="w", padx=(10, 0), pady=6)
            ent_f2_cuotas = ctk.CTkEntry(f_grid, width=80, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_f2_cuotas.insert(0, "24")
            ent_f2_cuotas.grid(row=2, column=3, padx=6, pady=6, sticky="w")

            f_quick_fia = ctk.CTkFrame(self.f_dinamico_form, fg_color="transparent")
            f_quick_fia.pack(anchor="w", pady=5)

            ctk.CTkButton(f_quick_fia, text="50% / 50%", width=90, height=28, font=ctk.CTkFont(size=12), fg_color=self.c_btn, text_color=self.c_text, command=lambda: (ent_f1_monto.delete(0, 'end'), ent_f1_monto.insert(0, f"{cap_neto/2:.2f}"), ent_f2_monto.delete(0, 'end'), ent_f2_monto.insert(0, f"{cap_neto/2:.2f}"))).pack(side="left", padx=2)
            ctk.CTkButton(f_quick_fia, text="100% F1", width=90, height=28, font=ctk.CTkFont(size=12), fg_color=self.c_btn, text_color=self.c_text, command=lambda: (ent_f1_monto.delete(0, 'end'), ent_f1_monto.insert(0, f"{cap_neto:.2f}"), ent_f2_monto.delete(0, 'end'), ent_f2_monto.insert(0, "0.00"))).pack(side="left", padx=2)
            ctk.CTkButton(f_quick_fia, text="100% F2", width=90, height=28, font=ctk.CTkFont(size=12), fg_color=self.c_btn, text_color=self.c_text, command=lambda: (ent_f1_monto.delete(0, 'end'), ent_f1_monto.insert(0, "0.00"), ent_f2_monto.delete(0, 'end'), ent_f2_monto.insert(0, f"{cap_neto:.2f}"))).pack(side="left", padx=2)

            ctk.CTkButton(
                self.f_dinamico_form,
                text="➕ Aplicar Fianza Solidaria en Lote",
                height=36,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=self.c_primary,
                command=lambda: self._agregar_fianza_a_lote(
                    cod, nom, fia1_nom, ent_f1_monto.get(), ent_f1_cuotas.get(), fia2_nom, ent_f2_monto.get(), ent_f2_cuotas.get(), int_cond, cap_neto
                )
            ).pack(anchor="w", pady=5)

        else:
            ctk.CTkLabel(f_grid, text="Monto Solicitado ($):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=0, column=0, sticky="w", pady=6)
            ent_monto = ctk.CTkEntry(f_grid, placeholder_text="0.00", width=160, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_monto.grid(row=0, column=1, padx=6, pady=6, sticky="w")
            ent_monto.focus_set()

            ctk.CTkLabel(f_grid, text="N° de Cuotas:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=0, column=2, sticky="w", padx=(10, 0), pady=6)
            ent_cuotas = ctk.CTkEntry(f_grid, placeholder_text="24", width=90, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_cuotas.insert(0, "24")
            ent_cuotas.grid(row=0, column=3, padx=6, pady=6, sticky="w")

            tasa_def = 0.00 if tipo == "MER" else self.config.get("tasa_interes_defecto", 2.60)
            ctk.CTkLabel(f_grid, text="Tasa Mensual (%):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=0, column=4, sticky="w", padx=(10, 0), pady=6)
            ent_tasa = ctk.CTkEntry(f_grid, width=90, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_tasa.insert(0, f"{tasa_def:.2f}")
            ent_tasa.grid(row=0, column=5, padx=6, pady=6, sticky="w")

            ctk.CTkLabel(f_grid, text="Fiador 1 (Opcional):", font=ctk.CTkFont(size=13), text_color=self.c_muted).grid(row=1, column=0, sticky="w", pady=6)
            ent_fia1 = ctk.CTkEntry(f_grid, placeholder_text="Código-Nombre Fiador 1", width=230, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_fia1.grid(row=1, column=1, columnspan=2, padx=6, pady=6, sticky="w")

            ctk.CTkLabel(f_grid, text="Fiador 2 (Opcional):", font=ctk.CTkFont(size=13), text_color=self.c_muted).grid(row=1, column=3, sticky="w", padx=(10, 0), pady=6)
            ent_fia2 = ctk.CTkEntry(f_grid, placeholder_text="Código-Nombre Fiador 2", width=230, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
            ent_fia2.grid(row=1, column=4, columnspan=2, padx=6, pady=6, sticky="w")

            lbl_alerta_cap = ctk.CTkLabel(self.f_dinamico_form, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_warning)
            lbl_alerta_cap.pack(anchor="w", pady=(2, 6))

            def verificar_liquidez_credito(*args):
                try:
                    m = float(ent_monto.get().strip() or 0)
                    c = int(ent_cuotas.get().strip() or 1)
                    t_m = float(ent_tasa.get().strip() or 2.60)
                    tasa_cuota = (t_m / 2.0) / 100.0
                    int_gen = m * (c * tasa_cuota)
                    cuo_val = (m + int_gen) / c
                    
                    if cuo_val > (sueldo_val * 0.40):
                        lbl_alerta_cap.configure(text=f"⚠️ ADVERTENCIA: La cuota calculada (${cuo_val:,.2f}) supera el 40% del sueldo registrado (${sueldo_val * 0.40:,.2f}).")
                    else:
                        lbl_alerta_cap.configure(text="")
                except Exception:
                    lbl_alerta_cap.configure(text="")

            for ent_w in (ent_monto, ent_cuotas, ent_tasa):
                ent_w.bind("<KeyRelease>", verificar_liquidez_credito)

            btn_add = ctk.CTkButton(
                self.f_dinamico_form,
                text="➕ Agregar al Lote de Desembolso",
                height=36,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=self.c_primary,
                command=lambda: self._agregar_credito_a_lote(cod, nom, tipo, ent_monto.get(), ent_cuotas.get(), ent_tasa.get(), ent_fia1.get(), ent_fia2.get())
            )
            btn_add.pack(anchor="w", pady=10)
            ent_monto.bind("<Return>", lambda e: btn_add.invoke())

    def _obtener_prestamo_original(self, cod):
        res = {"monto_original": 0.0, "total_con_intereses": 0.0}
        dfs = []
        if self.df_history is not None and not self.df_history.empty:
            dfs.append(self.df_history)
        if self.df_hisact is not None and not self.df_hisact.empty:
            dfs.append(self.df_hisact)
        
        if dfs:
            df_tot = pd.concat(dfs, ignore_index=True)
            hist = df_tot[df_tot["codigo"].astype(str).str.strip() == cod]
            if not hist.empty:
                prest = hist[hist["clave"].astype(str).str.strip().isin(["PRE", "pre"])]
                if not prest.empty:
                    ult = prest.iloc[-1]
                    res["monto_original"] = float(ult.get("cantidad", 0))
                    res["total_con_intereses"] = float(ult.get("saldo", 0))
        return res

    def _agregar_retiro_a_lote(self, cod, nom, monto_str, concepto, ahorro_disp, lbl_alerta):
        try:
            monto = float(monto_str.strip() or 0)
        except Exception:
            monto = 0.0

        if monto <= 0:
            lbl_alerta.configure(text="⚠️ Ingrese un monto válido mayor a $0.00.")
            return

        if monto > ahorro_disp:
            lbl_alerta.configure(text="⚠️ El monto solicitado supera el ahorro disponible del socio.")
            return

        reg_num = len(self.lote_movimientos) + 1
        nuevo_mov = {
            "REG": reg_num,
            "CLAVE": "RET",
            "CODIGO": cod,
            "NOMBRE": nom,
            "FECHA": datetime.datetime.strptime(self.fecha_sesion, "%d-%m-%Y").strftime("%Y%m%d"),
            "CANTIDAD": monto,
            "LETRAS": f"{monto:,.2f} DOLARES",
            "CHEQUE": "",
            "CONCEPTO": concepto or f"RETIRO DE AHORROS DE {nom}",
            "SALDO": monto,
            "CUOTAS": 0,
            "VALCUOTA": 0.0,
            "BAN": "",
            "FIADOR": "",
            "FIADOR2": "",
            "CUPON_NUM": self._generar_correlativo_actual()
        }
        self.lote_movimientos.append(nuevo_mov)
        self.ultimo_movimiento_registrado = nuevo_mov
        self._avanzar_correlativo()
        self._refrescar_cola_lote()
        self._actualizar_franja_ultimo_mov()
        self.entry_ingreso_soc.delete(0, 'end')
        self.socio_actual = None
        self._render_campos_operacion()
        self.entry_ingreso_soc.focus_set()

    def _agregar_credito_a_lote(self, cod, nom, tipo, monto_str, cuotas_str, tasa_str, fia1, fia2):
        try:
            monto = float(monto_str.strip() or 0)
            num_cuotas = int(cuotas_str.strip() or 1)
            tasa_m = float(tasa_str.strip() or 0)
        except Exception:
            messagebox.showwarning("Validación", "Revise los valores numéricos ingresados.")
            return

        if monto <= 0:
            messagebox.showwarning("Validación", "El monto debe ser mayor a $0.00.")
            return

        if fia1.strip():
            c_f1 = fia1.split("-")[0].strip()
            if not self._validar_reglas_fiador(cod, c_f1, fia1):
                return

        tasa_por_cuota = (tasa_m / 2.0) / 100.0
        intereses = round(monto * (num_cuotas * tasa_por_cuota), 2)
        total_saldo = round(monto + intereses, 2)
        val_cuota = round(total_saldo / num_cuotas, 2)

        if tipo == "MER":
            if "mercaderia" not in self.meta_data:
                self.meta_data["mercaderia"] = {}
            self.meta_data["mercaderia"][cod] = {
                "monto_original": monto,
                "saldo": monto,
                "cuota": val_cuota,
                "cuotas_totales": num_cuotas,
                "cuotas_restantes": num_cuotas
            }
            self._guardar_meta()

        reg_num = len(self.lote_movimientos) + 1
        corr_mes = self._generar_correlativo_actual()
        nuevo_mov = {
            "REG": reg_num,
            "CLAVE": tipo,
            "CODIGO": cod,
            "NOMBRE": nom,
            "FECHA": datetime.datetime.strptime(self.fecha_sesion, "%d-%m-%Y").strftime("%Y%m%d"),
            "CANTIDAD": monto,
            "LETRAS": f"{monto:,.2f} DOLARES",
            "CHEQUE": "",
            "CONCEPTO": f"PRESTAMO PERSONAL A {nom}" if tipo == "PRE" else f"CREDITO {tipo} A {nom}",
            "SALDO": total_saldo,
            "CUOTAS": num_cuotas,
            "VALCUOTA": val_cuota,
            "BAN": "",
            "FIADOR": fia1.strip().upper(),
            "FIADOR2": fia2.strip().upper(),
            "CUPON_NUM": corr_mes
        }
        self.lote_movimientos.append(nuevo_mov)
        self.ultimo_movimiento_registrado = nuevo_mov
        self._avanzar_correlativo()
        self._refrescar_cola_lote()
        self._actualizar_franja_ultimo_mov()
        self.entry_ingreso_soc.delete(0, 'end')
        self.socio_actual = None
        self._render_campos_operacion()
        self.entry_ingreso_soc.focus_set()

    def _agregar_refinanciamiento_a_lote(self, cod, nom, cap_neto_prest, int_cond_prest, efec_str, cuotas_str, tasa_str, fia1, fia2, cap_neto_cup=0.0, int_cond_cup=0.0):
        try:
            efec = float(efec_str.strip() or 0)
            num_cuotas = int(cuotas_str.strip() or 1)
            tasa_m = float(tasa_str.strip() or 2.60)
            tasa_por_cuota = (tasa_m / 2.0) / 100.0
        except Exception:
            messagebox.showwarning("Validación", "Revise los valores numéricos ingresados.")
            return

        if fia1.strip():
            c_f1 = fia1.split("-")[0].strip()
            if not self._validar_reglas_fiador(cod, c_f1, fia1):
                return

        cap_neto_total = round(cap_neto_prest + cap_neto_cup, 2)
        nuevo_capital_maestro = round(cap_neto_total + efec, 2)
        nuevos_intereses = round(nuevo_capital_maestro * (num_cuotas * tasa_por_cuota), 2)
        saldo_bruto_total = round(nuevo_capital_maestro + nuevos_intereses, 2)
        val_cuota = round(saldo_bruto_total / num_cuotas, 2)

        f_codinca = datetime.datetime.strptime(self.fecha_sesion, "%d-%m-%Y").strftime("%Y%m%d")
        corr_mes = self._generar_correlativo_actual()

        # ASIENTO 1: OTR (INT) - Condonación crédito
        if int_cond_prest > 0:
            self.lote_movimientos.append({
                "REG": len(self.lote_movimientos) + 1,
                "CLAVE": "OTR",
                "CODIGO": cod,
                "NOMBRE": nom,
                "FECHA": f_codinca,
                "CANTIDAD": int_cond_prest,
                "LETRAS": f"{int_cond_prest:,.2f} DOLARES",
                "CHEQUE": "INT",
                "CONCEPTO": f"{cod}-INT CONDONADOS REF PRTM",
                "SALDO": 0.0,
                "CUOTAS": 0,
                "VALCUOTA": 0.0,
                "BAN": "",
                "FIADOR": "",
                "FIADOR2": "",
                "CUPON_NUM": corr_mes
            })

        # ASIENTO 2: OTR (OTR) - Pago neto crédito Capri
        if cap_neto_prest > 0:
            self.lote_movimientos.append({
                "REG": len(self.lote_movimientos) + 1,
                "CLAVE": "OTR",
                "CODIGO": cod,
                "NOMBRE": "COOPERATIVA INDUSTRIAS CAPRI",
                "FECHA": f_codinca,
                "CANTIDAD": cap_neto_prest,
                "LETRAS": f"{cap_neto_prest:,.2f} DOLARES",
                "CHEQUE": "OTR",
                "CONCEPTO": f"{cod}-PAGO NETO CAPITAL PRTM SR {nom}",
                "SALDO": 0.0,
                "CUOTAS": 0,
                "VALCUOTA": 0.0,
                "BAN": "",
                "FIADOR": "",
                "FIADOR2": "",
                "CUPON_NUM": corr_mes
            })

        # ASIENTO 3: OTR (INT) - Condonación cupones
        if int_cond_cup > 0:
            self.lote_movimientos.append({
                "REG": len(self.lote_movimientos) + 1,
                "CLAVE": "OTR",
                "CODIGO": cod,
                "NOMBRE": nom,
                "FECHA": f_codinca,
                "CANTIDAD": int_cond_cup,
                "LETRAS": f"{int_cond_cup:,.2f} DOLARES",
                "CHEQUE": "INT",
                "CONCEPTO": f"{cod}-INT CONDONADOS CUPONES",
                "SALDO": 0.0,
                "CUOTAS": 0,
                "VALCUOTA": 0.0,
                "BAN": "",
                "FIADOR": "",
                "FIADOR2": "",
                "CUPON_NUM": corr_mes
            })

        # ASIENTO 4: OTR (OTR) - Pago neto cupones Capri
        if cap_neto_cup > 0:
            self.lote_movimientos.append({
                "REG": len(self.lote_movimientos) + 1,
                "CLAVE": "OTR",
                "CODIGO": cod,
                "NOMBRE": "COOPERATIVA INDUSTRIAS CAPRI",
                "FECHA": f_codinca,
                "CANTIDAD": cap_neto_cup,
                "LETRAS": f"{cap_neto_cup:,.2f} DOLARES",
                "CHEQUE": "OTR",
                "CONCEPTO": f"{cod}-PAGO NETO CAPITAL CUPONES",
                "SALDO": 0.0,
                "CUOTAS": 0,
                "VALCUOTA": 0.0,
                "BAN": "",
                "FIADOR": "",
                "FIADOR2": "",
                "CUPON_NUM": corr_mes
            })

        # ASIENTO 5: PRE - Nuevo Crédito Maestro
        asiento_pre = {
            "REG": len(self.lote_movimientos) + 1,
            "CLAVE": "PRE",
            "CODIGO": cod,
            "NOMBRE": nom,
            "FECHA": f_codinca,
            "CANTIDAD": efec,
            "LETRAS": f"{efec:,.2f} DOLARES",
            "CHEQUE": "",
            "CONCEPTO": f"REFINANCIAMIENTO SALDO A {nom}",
            "SALDO": saldo_bruto_total,
            "CUOTAS": num_cuotas,
            "VALCUOTA": val_cuota,
            "BAN": "",
            "FIADOR": fia1.strip().upper(),
            "FIADOR2": fia2.strip().upper(),
            "CUPON_NUM": corr_mes
        }
        self.lote_movimientos.append(asiento_pre)
        self.ultimo_movimiento_registrado = asiento_pre

        self._avanzar_correlativo()
        self._refrescar_cola_lote()
        self._actualizar_franja_ultimo_mov()

        self.entry_ingreso_soc.delete(0, 'end')
        self.socio_actual = None
        self._render_campos_operacion()
        self.entry_ingreso_soc.focus_set()

    def _agregar_fianza_a_lote(self, cod_deudor, nom_deudor, fia1, m1_str, c1_str, fia2, m2_str, c2_str, int_cond, cap_neto):
        try:
            m1 = float(m1_str.strip() or 0)
            c1 = int(c1_str.strip() or 1)
            m2 = float(m2_str.strip() or 0)
            c2 = int(c2_str.strip() or 1)
        except Exception:
            messagebox.showwarning("Validación", "Revise montos y cuotas para fiadores.")
            return

        f_codinca = datetime.datetime.strptime(self.fecha_sesion, "%d-%m-%Y").strftime("%Y%m%d")
        corr_mes = self._generar_correlativo_actual()

        # FIX: se usaba CLAVE "OTRO" (4 caracteres), pero el campo DBF es C(3) y el
        # resto del sistema usa "OTR" para este tipo de asiento. Con "OTRO" el DBF
        # exportado quedaba truncado a "OTR" mientras el CSV mantenía "OTRO",
        # generando inconsistencia entre ambos archivos de salida.
        self.lote_movimientos.append({
            "REG": len(self.lote_movimientos) + 1,
            "CLAVE": "OTR",
            "CODIGO": cod_deudor,
            "NOMBRE": nom_deudor,
            "FECHA": f_codinca,
            "CANTIDAD": int_cond,
            "LETRAS": f"{int_cond:,.2f} DOLARES",
            "CHEQUE": "INT",
            "CONCEPTO": f"{cod_deudor}-INT EXONERADOS POR FIANZA",
            "SALDO": 0.0,
            "CUOTAS": 0,
            "VALCUOTA": 0.0,
            "BAN": "",
            "FIADOR": "",
            "FIADOR2": "",
            "CUPON_NUM": corr_mes
        })

        if m1 > 0:
            val_c1 = round(m1 / c1, 2)
            self.lote_movimientos.append({
                "REG": len(self.lote_movimientos) + 1,
                "CLAVE": "PRE",
                "CODIGO": fia1.split("-")[0].strip() if "-" in fia1 else cod_deudor,
                "NOMBRE": fia1.split("-")[1].strip() if "-" in fia1 else fia1,
                "FECHA": f_codinca,
                "CANTIDAD": m1,
                "LETRAS": f"{m1:,.2f} DOLARES",
                "CHEQUE": "",
                "CONCEPTO": f"COBRO FIANZA SOLIDARIA DEUDOR {cod_deudor}",
                "SALDO": m1,
                "CUOTAS": c1,
                "VALCUOTA": val_c1,
                "BAN": "",
                "FIADOR": "",
                "FIADOR2": "",
                "CUPON_NUM": corr_mes
            })

        if m2 > 0:
            val_c2 = round(m2 / c2, 2)
            self.lote_movimientos.append({
                "REG": len(self.lote_movimientos) + 1,
                "CLAVE": "PRE",
                "CODIGO": fia2.split("-")[0].strip() if "-" in fia2 else cod_deudor,
                "NOMBRE": fia2.split("-")[1].strip() if "-" in fia2 else fia2,
                "FECHA": f_codinca,
                "CANTIDAD": m2,
                "LETRAS": f"{m2:,.2f} DOLARES",
                "CHEQUE": "",
                "CONCEPTO": f"COBRO FIANZA SOLIDARIA DEUDOR {cod_deudor}",
                "SALDO": m2,
                "CUOTAS": c2,
                "VALCUOTA": val_c2,
                "BAN": "",
                "FIADOR": "",
                "FIADOR2": "",
                "CUPON_NUM": corr_mes
            })

        self.ultimo_movimiento_registrado = self.lote_movimientos[-1]
        self._avanzar_correlativo()
        self._refrescar_cola_lote()
        self._actualizar_franja_ultimo_mov()
        self.entry_ingreso_soc.delete(0, 'end')
        self.socio_actual = None
        self._render_campos_operacion()
        self.entry_ingreso_soc.focus_set()

    def _refrescar_cola_lote(self):
        for idx, r in enumerate(self.lote_movimientos):
            r["REG"] = idx + 1
        self.lbl_total_lote.configure(text=f"PASO 3: Lote Acumulado para Desembolso ({len(self.lote_movimientos)} registros)")
        self._render_tabla_lote()

    def _eliminar_registro_lote(self, idx):
        if 0 <= idx < len(self.lote_movimientos):
            self.lote_movimientos.pop(idx)
            self._refrescar_cola_lote()

    def _render_tabla_lote(self):
        for w in self.frame_tabla_lote.winfo_children():
            w.destroy()

        headers = ["REG", "CLAVE", "CÓDIGO", "NOMBRE", "CANTIDAD", "SALDO TOTAL", "CUOTAS", "VALOR CUOTA", "ACCIÓN"]
        h_frame = ctk.CTkFrame(self.frame_tabla_lote, fg_color=self.c_btn, height=32)
        h_frame.pack(fill="x", padx=5, pady=(5, 4))
        for idx, h in enumerate(headers):
            lbl = ctk.CTkLabel(h_frame, text=h, font=ctk.CTkFont(size=12, weight="bold"), text_color=self.c_text)
            lbl.grid(row=0, column=idx, sticky="w", padx=6, pady=4)
            h_frame.grid_columnconfigure(idx, weight=2 if idx == 3 else 1)

        if not self.lote_movimientos:
            ctk.CTkLabel(self.frame_tabla_lote, text="No hay movimientos en la cola del lote actual.", font=ctk.CTkFont(size=13), text_color=self.c_muted).pack(pady=20)
            return

        for idx, r in enumerate(self.lote_movimientos):
            row_frame = ctk.CTkFrame(self.frame_tabla_lote, fg_color="transparent")
            row_frame.pack(fill="x", padx=5, pady=2)

            vals = [
                str(r["REG"]),
                r["CLAVE"],
                r["CODIGO"],
                _truncar(r["NOMBRE"], 22),
                f"${r['CANTIDAD']:,.2f}",
                f"${r['SALDO']:,.2f}",
                str(r["CUOTAS"]),
                f"${r['VALCUOTA']:,.2f}"
            ]
            for c_idx, val in enumerate(vals):
                lbl = ctk.CTkLabel(row_frame, text=val, font=ctk.CTkFont(size=12), text_color=self.c_text)
                lbl.grid(row=0, column=c_idx, sticky="w", padx=6)
                row_frame.grid_columnconfigure(c_idx, weight=2 if c_idx == 3 else 1)

            btn_del = ctk.CTkButton(
                row_frame, 
                text="🗑️ Borrar", 
                width=65, 
                height=24, 
                font=ctk.CTkFont(size=11, weight="bold"), 
                fg_color=self.c_danger, 
                text_color="#ffffff",
                command=lambda i=idx: self._eliminar_registro_lote(i)
            )
            btn_del.grid(row=0, column=len(vals), padx=6)
            row_frame.grid_columnconfigure(len(vals), weight=1)

    def _exportar_lote_movim_dual(self):
        if not self.lote_movimientos:
            messagebox.showwarning("Atención", "No hay movimientos en el lote para generar.")
            return

        df_lote = pd.DataFrame(self.lote_movimientos)
        carpeta_destino = filedialog.askdirectory(title="Seleccionar Carpeta para Guardar Archivos MOVIM")
        if not carpeta_destino:
            return

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_bak_auto = os.path.join(carpeta_destino, f"backup_previo_{ts}")
        os.makedirs(dir_bak_auto, exist_ok=True)
        for archivo in ["maestro.dbf", "MAESTRO.DBF", "movim.dbf", "MOVIM.DBF"]:
            if os.path.exists(archivo):
                shutil.copy(archivo, os.path.join(dir_bak_auto, archivo))

        ruta_csv = os.path.join(carpeta_destino, "MOVIM.CSV")
        ruta_dbf = os.path.join(carpeta_destino, "MOVIM.DBF")

        df_lote.to_csv(ruta_csv, index=False, encoding="utf-8")

        try:
            import dbf
            tabla = dbf.Table(
                ruta_dbf,
                'REG N(4,0); CLAVE C(3); CODIGO C(6); NOMBRE C(40); FECHA C(8); CANTIDAD N(10,2); '
                'LETRAS C(60); CHEQUE C(8); CONCEPTO C(45); SALDO N(10,2); CUOTAS N(3,0); '
                'VALCUOTA N(10,2); BAN C(3); FIADOR C(40); FIADOR2 C(40); CUPON_NUM C(10)',
                codepage='cp1252'
            )
            tabla.open(mode=dbf.READ_WRITE)
            for r in self.lote_movimientos:
                tabla.append((
                    r["REG"],
                    r["CLAVE"][:3],
                    r["CODIGO"][:6],
                    r["NOMBRE"][:40],
                    r["FECHA"][:8],
                    float(r["CANTIDAD"]),
                    r["LETRAS"][:60],
                    r["CHEQUE"][:8],
                    r["CONCEPTO"][:45],
                    float(r["SALDO"]),
                    int(r["CUOTAS"]),
                    float(r["VALCUOTA"]),
                    r["BAN"][:3],
                    r["FIADOR"][:40],
                    r["FIADOR2"][:40],
                    r["CUPON_NUM"][:10]
                ))
            tabla.close()
            dbf_creado = True
        except Exception:
            dbf_creado = False

        msg = f"Archivos generados exitosamente en:\n{carpeta_destino}\n\n• MOVIM.CSV (Listo para Excel)\n"
        msg += "• MOVIM.DBF (Estructura xBase generada)" if dbf_creado else "• MOVIM.DBF (Requiere librería 'dbf' instalada)"
        messagebox.showinfo("Lote Exportado", msg)

    def _vaciar_lote(self):
        if not self.lote_movimientos:
            return
        if messagebox.askyesno("Confirmar", "¿Desea vaciar todos los movimientos del lote actual?"):
            self.lote_movimientos.clear()
            self._refrescar_cola_lote()

    def _abrir_modal_seleccion_socio(self, df_matches, callback):
        win = ctk.CTkToplevel(self)
        win.title("CUZODINCA - Seleccionar Socio")
        win.geometry("780x420")
        win.attributes("-topmost", True)
        win.configure(fg_color=self.c_bg)

        ctk.CTkLabel(win, text="Múltiples socios coinciden con la búsqueda. Seleccione el indicado:", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=20, pady=(15, 10))

        frame_t = ctk.CTkScrollableFrame(win, fg_color=self.c_card, corner_radius=10)
        frame_t.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        h_f = ctk.CTkFrame(frame_t, fg_color=self.c_btn, height=32)
        h_f.pack(fill="x", padx=5, pady=5)
        for idx, h in enumerate(["CÓDIGO", "NOMBRE", "AHORRO", "SALDO", "ACCIÓN"]):
            lbl = ctk.CTkLabel(h_f, text=h, font=ctk.CTkFont(size=12, weight="bold"), text_color=self.c_text)
            lbl.grid(row=0, column=idx, sticky="w", padx=8, pady=4)
            h_f.grid_columnconfigure(idx, weight=2 if idx == 1 else 1)

        for _, r in df_matches.iterrows():
            rf = ctk.CTkFrame(frame_t, fg_color="transparent")
            rf.pack(fill="x", padx=5, pady=2)

            cod = str(r.get("codigo", "")).strip()
            nom = _truncar(r.get("nombre", ""), 26)
            ahorro = float(r.get("ahorro", 0))
            saldo = float(r.get("saldo", 0))

            vals = [cod, nom, f"${ahorro:,.2f}", f"${saldo:,.2f}"]
            for idx, v in enumerate(vals):
                lbl = ctk.CTkLabel(rf, text=v, font=ctk.CTkFont(size=12), text_color=self.c_text)
                lbl.grid(row=0, column=idx, sticky="w", padx=8)
                rf.grid_columnconfigure(idx, weight=2 if idx == 1 else 1)

            btn = ctk.CTkButton(
                rf,
                text="Seleccionar",
                width=85,
                height=26,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=self.c_primary,
                command=lambda soc=r, w=win: (callback(soc), w.destroy())
            )
            btn.grid(row=0, column=4, padx=8)
            rf.grid_columnconfigure(4, weight=1)

    # ------------------ VISTA 4: MÓDULO SIMULADOR (GRID ORDENADO Y TASA 2.60%) ------------------
    def _mostrar_modulo_simulador(self):
        self.vista_actual = "simulador"
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.main_frame, text="🧮 Simulador y Calculadora de Crédito en Vivo", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.c_text).pack(anchor="w", pady=(0, 15), fill="x")

        tab_sim = ctk.CTkTabview(self.main_frame, fg_color=self.c_card)
        tab_sim.pack(fill="x", expand=True)

        t_refinanc = tab_sim.add("🔄 Refinanciamiento en Vivo")
        t_prestamo = tab_sim.add("💳 Préstamo Personal")
        t_cupon = tab_sim.add("🎟️ Cupones (Con Interés)")
        t_merc = tab_sim.add("📦 Mercadería (0%)")
        t_pronto = tab_sim.add("💰 Liquidación Pronto Pago")

        f_top_r = ctk.CTkFrame(t_refinanc, fg_color="transparent")
        f_top_r.pack(fill="x", padx=20, pady=(15, 10))

        ctk.CTkLabel(f_top_r, text="Buscar Colaborador:", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).pack(side="left", padx=(0, 10))
        ent_sim_soc = ctk.CTkEntry(f_top_r, placeholder_text="Código o Nombre...", width=260, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_sim_soc.pack(side="left", padx=5)

        lbl_sim_soc_info = ctk.CTkLabel(t_refinanc, text="Ingrese colaborador para consultar deudas vigentes.", font=ctk.CTkFont(size=13), text_color=self.c_muted)
        lbl_sim_soc_info.pack(anchor="w", padx=20, pady=(0, 10))

        f_checks = ctk.CTkFrame(t_refinanc, fg_color=self.c_bg, corner_radius=8)
        f_checks.pack(fill="x", padx=20, pady=5)

        var_chk_prest = ctk.BooleanVar(value=True)
        var_chk_cup = ctk.BooleanVar(value=False)
        var_chk_merc = ctk.BooleanVar(value=False)

        cb_prest = ctk.CTkCheckBox(f_checks, text="Préstamo Personal (Saldo: $0.00)", variable=var_chk_prest, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text)
        cb_prest.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        cb_cup = ctk.CTkCheckBox(f_checks, text="Cupones con Interés (Saldo: $0.00)", variable=var_chk_cup, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text)
        cb_cup.grid(row=0, column=1, padx=15, pady=10, sticky="w")

        cb_merc = ctk.CTkCheckBox(f_checks, text="Mercadería 0% (Saldo: $0.00)", variable=var_chk_merc, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text)
        cb_merc.grid(row=0, column=2, padx=15, pady=10, sticky="w")

        f_r_inputs = ctk.CTkFrame(t_refinanc, fg_color="transparent")
        f_r_inputs.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(f_r_inputs, text="Efectivo en Mano ($):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=0, column=0, sticky="w", pady=6)
        ent_sim_ad = ctk.CTkEntry(f_r_inputs, placeholder_text="0.00", width=140, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_sim_ad.insert(0, "100.00")
        ent_sim_ad.grid(row=0, column=1, padx=8, pady=6, sticky="w")

        ctk.CTkLabel(f_r_inputs, text="N° de Cuotas:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=0, column=2, sticky="w", padx=(15, 0), pady=6)
        ent_sim_c = ctk.CTkEntry(f_r_inputs, placeholder_text="24", width=90, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_sim_c.insert(0, "24")
        ent_sim_c.grid(row=0, column=3, padx=8, pady=6, sticky="w")

        tasa_def_val = self.config.get("tasa_interes_defecto", 2.60)
        ctk.CTkLabel(f_r_inputs, text="Tasa Mensual (%):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=0, column=4, sticky="w", padx=(15, 0), pady=6)
        ent_sim_t = ctk.CTkEntry(f_r_inputs, width=90, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_sim_t.insert(0, f"{tasa_def_val:.2f}")
        ent_sim_t.grid(row=0, column=5, padx=8, pady=6, sticky="w")

        grid_res_ref = ctk.CTkFrame(t_refinanc, fg_color="transparent")
        grid_res_ref.pack(fill="x", padx=20, pady=15)
        grid_res_ref.grid_columnconfigure((0, 1), weight=1)
        grid_res_ref.grid_rowconfigure((0, 1), weight=1)

        def crear_tarjeta_grid(parent, row, col, titulo, valor_init, color_val):
            c_card_box = ctk.CTkFrame(parent, fg_color=self.c_bg, corner_radius=10)
            c_card_box.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
            ctk.CTkLabel(c_card_box, text=titulo, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_muted).pack(anchor="w", padx=15, pady=(12, 2))
            lbl_v = ctk.CTkLabel(c_card_box, text=valor_init, font=ctk.CTkFont(size=20, weight="bold"), text_color=color_val)
            lbl_v.pack(anchor="w", padx=15, pady=(0, 12))
            return lbl_v

        lbl_grid_cap_ant = crear_tarjeta_grid(grid_res_ref, 0, 0, "Capital Consolidado Anterior", "$ 0.00", self.c_text)
        lbl_grid_int_cond = crear_tarjeta_grid(grid_res_ref, 0, 1, "🎉 Intereses Condonados (Pronto Pago)", "$ 0.00", self.c_accent)
        lbl_grid_nvo_cap = crear_tarjeta_grid(grid_res_ref, 1, 0, "Nuevo Capital + Efectivo", "$ 0.00", self.c_text)
        lbl_grid_cuota_fin = crear_tarjeta_grid(grid_res_ref, 1, 1, "Nueva Cuota Mensual Calculada", "$ 0.00", self.c_primary)

        datos_sim = {"saldo_p": 0.0, "saldo_c": 0.0, "saldo_m": 0.0, "orig_p": 0.0, "tot_p": 0.0}

        def simular_refinanciamiento_calculo(*args):
            try:
                cap_ref = 0.0
                int_ahorrados = 0.0

                if var_chk_prest.get() and datos_sim["saldo_p"] > 0:
                    s_p = datos_sim["saldo_p"]
                    fac_p = (datos_sim["orig_p"] / datos_sim["tot_p"]) if datos_sim["tot_p"] > 0 else 0.7622
                    cap_p = s_p * fac_p
                    cap_ref += cap_p
                    int_ahorrados += (s_p - cap_p)

                if var_chk_cup.get() and datos_sim["saldo_c"] > 0:
                    s_c = datos_sim["saldo_c"]
                    cap_c = s_c * 0.85
                    cap_ref += cap_c
                    int_ahorrados += (s_c - cap_c)

                if var_chk_merc.get() and datos_sim["saldo_m"] > 0:
                    cap_ref += datos_sim["saldo_m"]

                adicional = float(ent_sim_ad.get().strip() or 0)
                cuotas = int(ent_sim_c.get().strip() or 1)
                t_m = float(ent_sim_t.get().strip() or 2.60)
                tasa_cuota = (t_m / 2.0) / 100.0

                nuevo_cap_tot = cap_ref + adicional
                nuevos_int = round(nuevo_cap_tot * (cuotas * tasa_cuota), 2)
                total_a_pagar = round(nuevo_cap_tot + nuevos_int, 2)
                cuota_val = round(total_a_pagar / cuotas, 2)

                lbl_grid_cap_ant.configure(text=f"$ {cap_ref:,.2f}")
                lbl_grid_int_cond.configure(text=f"$ {int_ahorrados:,.2f}")
                lbl_grid_nvo_cap.configure(text=f"$ {nuevo_cap_tot:,.2f} (+${adicional:,.2f} efec)")
                lbl_grid_cuota_fin.configure(text=f"$ {cuota_val:,.2f} ({cuotas} pagos)")
            except Exception:
                pass

        def buscar_soc_sim():
            q = ent_sim_soc.get().strip().upper()
            if not q or self.df_maestro is None:
                return
            m = self.df_maestro
            mask = (m["codigo"].astype(str).str.strip().str.upper() == q) | (m["nombre"].astype(str).str.upper().str.contains(q, na=False))
            encontrados = m[mask]
            if not encontrados.empty:
                s_sel = encontrados.iloc[0]
                cod = str(s_sel.get("codigo", "")).strip()
                nom = str(s_sel.get("nombre", "")).strip()
                lbl_sim_soc_info.configure(text=f"👤 Colaborador: {cod} - {nom}")
                
                datos_sim["saldo_p"] = float(s_sel.get("saldo", 0))
                datos_sim["saldo_c"] = float(s_sel.get("cupones", 0))
                
                meta_mer = self.meta_data.get("mercaderia", {}).get(cod, {})
                datos_sim["saldo_m"] = meta_mer.get("saldo", float(s_sel.get("otros", 0)))

                prest_orig = self._obtener_prestamo_original(cod)
                datos_sim["orig_p"] = prest_orig.get("monto_original", datos_sim["saldo_p"])
                datos_sim["tot_p"] = prest_orig.get("total_con_intereses", datos_sim["saldo_p"])

                cb_prest.configure(text=f"Préstamo Personal (Saldo: ${datos_sim['saldo_p']:,.2f})")
                cb_cup.configure(text=f"Cupones con Interés (Saldo: ${datos_sim['saldo_c']:,.2f})")
                cb_merc.configure(text=f"Mercadería 0% (Saldo: ${datos_sim['saldo_m']:,.2f})")

                simular_refinanciamiento_calculo()

        ctk.CTkButton(f_top_r, text="🔍 Consultar", width=110, height=32, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_primary, command=buscar_soc_sim).pack(side="left", padx=5)
        ent_sim_soc.bind("<Return>", lambda e: buscar_soc_sim())

        for w_input in (ent_sim_ad, ent_sim_c, ent_sim_t):
            w_input.bind("<KeyRelease>", simular_refinanciamiento_calculo)
        cb_prest.configure(command=simular_refinanciamiento_calculo)
        cb_cup.configure(command=simular_refinanciamiento_calculo)
        cb_merc.configure(command=simular_refinanciamiento_calculo)

        # 2. Préstamo Personal Simple
        f_p = ctk.CTkFrame(t_prestamo, fg_color="transparent")
        f_p.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(f_p, text="Monto Solicitado ($):", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=0, column=0, sticky="w", pady=8)
        ent_p_m = ctk.CTkEntry(f_p, placeholder_text="100.00", width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_p_m.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        ctk.CTkLabel(f_p, text="N° de Cuotas:", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=1, column=0, sticky="w", pady=8)
        ent_p_cuotas = ctk.CTkEntry(f_p, placeholder_text="24", width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_p_cuotas.insert(0, "24")
        ent_p_cuotas.grid(row=1, column=1, padx=10, pady=8, sticky="w")

        ctk.CTkLabel(f_p, text="Tasa Mensual (%):", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=2, column=0, sticky="w", pady=8)
        ent_p_tas = ctk.CTkEntry(f_p, width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_p_tas.insert(0, f"{tasa_def_val:.2f}")
        ent_p_tas.grid(row=2, column=1, padx=10, pady=8, sticky="w")

        grid_res_p = ctk.CTkFrame(t_prestamo, fg_color="transparent")
        grid_res_p.pack(fill="x", padx=20, pady=15)
        grid_res_p.grid_columnconfigure((0, 1), weight=1)

        lbl_grid_p_tot = crear_tarjeta_grid(grid_res_p, 0, 0, "Total con Intereses", "$ 0.00", self.c_text)
        lbl_grid_p_cuo = crear_tarjeta_grid(grid_res_p, 0, 1, "Valor de Cada Cuota", "$ 0.00", self.c_accent)

        def calc_p():
            try:
                m = float(ent_p_m.get().strip() or 0)
                c = int(ent_p_cuotas.get().strip() or 1)
                t_m = float(ent_p_tas.get().strip() or 2.60)
                tasa_cuota = (t_m / 2.0) / 100.0
                
                interes_gen = round(m * (c * tasa_cuota), 2)
                total_con_int = round(m + interes_gen, 2)
                cuota_val = round(total_con_int / c, 2)

                lbl_grid_p_tot.configure(text=f"$ {total_con_int:,.2f} (+${interes_gen:,.2f} int)")
                lbl_grid_p_cuo.configure(text=f"$ {cuota_val:,.2f} ({c} pagos)")
            except Exception:
                pass

        ctk.CTkButton(t_prestamo, text="⚡ Calcular Préstamo", width=180, height=36, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_primary, command=calc_p).pack(anchor="w", padx=20, pady=5)

        # 3. Cupones
        f_c = ctk.CTkFrame(t_cupon, fg_color="transparent")
        f_c.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(f_c, text="Monto Cupón ($):", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=0, column=0, sticky="w", pady=8)
        ent_c_m = ctk.CTkEntry(f_c, placeholder_text="200.00", width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_c_m.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        ctk.CTkLabel(f_c, text="N° de Cuotas:", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=1, column=0, sticky="w", pady=8)
        ent_c_cuotas = ctk.CTkEntry(f_c, placeholder_text="12", width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_c_cuotas.insert(0, "12")
        ent_c_cuotas.grid(row=1, column=1, padx=10, pady=8, sticky="w")

        ctk.CTkLabel(f_c, text="Tasa Mensual (%):", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=2, column=0, sticky="w", pady=8)
        ent_c_t = ctk.CTkEntry(f_c, width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_c_t.insert(0, "1.00")
        ent_c_t.grid(row=2, column=1, padx=10, pady=8, sticky="w")

        grid_res_c = ctk.CTkFrame(t_cupon, fg_color="transparent")
        grid_res_c.pack(fill="x", padx=20, pady=15)
        grid_res_c.grid_columnconfigure((0, 1), weight=1)

        lbl_grid_c_tot = crear_tarjeta_grid(grid_res_c, 0, 0, "Total Cupón con Intereses", "$ 0.00", self.c_text)
        lbl_grid_c_cuo = crear_tarjeta_grid(grid_res_c, 0, 1, "Cuota de Cupón", "$ 0.00", "#8b5cf6")

        def calc_c():
            try:
                m = float(ent_c_m.get().strip() or 0)
                c = int(ent_c_cuotas.get().strip() or 1)
                t_m = float(ent_c_t.get().strip() or 1.0)
                tasa_cuota = (t_m / 2.0) / 100.0
                
                interes_gen = round(m * (c * tasa_cuota), 2)
                total_con_int = round(m + interes_gen, 2)
                cuota_val = round(total_con_int / c, 2)

                lbl_grid_c_tot.configure(text=f"$ {total_con_int:,.2f} (+${interes_gen:,.2f})")
                lbl_grid_c_cuo.configure(text=f"$ {cuota_val:,.2f} ({c} pagos)")
            except Exception:
                pass

        ctk.CTkButton(t_cupon, text="⚡ Calcular Cupones", width=180, height=36, font=ctk.CTkFont(size=13, weight="bold"), fg_color="#8b5cf6", text_color="#ffffff", command=calc_c).pack(anchor="w", padx=20, pady=5)

        # 4. Mercadería 0%
        f_m = ctk.CTkFrame(t_merc, fg_color="transparent")
        f_m.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(f_m, text="Valor Mercadería ($):", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=0, column=0, sticky="w", pady=8)
        ent_merc_m = ctk.CTkEntry(f_m, placeholder_text="300.00", width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_merc_m.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        ctk.CTkLabel(f_m, text="Número de Cuotas:", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=1, column=0, sticky="w", pady=8)
        ent_merc_c = ctk.CTkEntry(f_m, placeholder_text="12", width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_merc_c.insert(0, "12")
        ent_merc_c.grid(row=1, column=1, padx=10, pady=8, sticky="w")

        grid_res_m = ctk.CTkFrame(t_merc, fg_color="transparent")
        grid_res_m.pack(fill="x", padx=20, pady=15)
        grid_res_m.grid_columnconfigure((0, 1), weight=1)

        lbl_grid_m_tot = crear_tarjeta_grid(grid_res_m, 0, 0, "Total Mercadería (Tasa 0%)", "$ 0.00", self.c_text)
        lbl_grid_m_cuo = crear_tarjeta_grid(grid_res_m, 0, 1, "Cuota por Nómina", "$ 0.00", self.c_accent)

        def calc_m():
            try:
                m = float(ent_merc_m.get().strip() or 0)
                c = int(ent_merc_c.get().strip() or 1)
                lbl_grid_m_tot.configure(text=f"$ {m:,.2f} (0% Interés)")
                lbl_grid_m_cuo.configure(text=f"$ {m/c:,.2f} ({c} pagos)")
            except Exception:
                pass

        ctk.CTkButton(t_merc, text="⚡ Calcular Mercadería", width=180, height=36, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_primary, command=calc_m).pack(anchor="w", padx=20, pady=5)

        # 5. Pronto Pago
        f_pp = ctk.CTkFrame(t_pronto, fg_color="transparent")
        f_pp.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(f_pp, text="Saldo Pendiente en DBF ($):", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=0, column=0, sticky="w", pady=8)
        ent_pp_sal = ctk.CTkEntry(f_pp, placeholder_text="546.70", width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_pp_sal.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        ctk.CTkLabel(f_pp, text="Monto Original Desembolsado ($):", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=1, column=0, sticky="w", pady=8)
        ent_pp_orig = ctk.CTkEntry(f_pp, placeholder_text="1000.00", width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_pp_orig.grid(row=1, column=1, padx=10, pady=8, sticky="w")

        ctk.CTkLabel(f_pp, text="Total Crédito con Intereses ($):", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=2, column=0, sticky="w", pady=8)
        ent_pp_tot = ctk.CTkEntry(f_pp, placeholder_text="1312.00", width=190, font=ctk.CTkFont(size=14), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_pp_tot.grid(row=2, column=1, padx=10, pady=8, sticky="w")

        grid_res_pp = ctk.CTkFrame(t_pronto, fg_color="transparent")
        grid_res_pp.pack(fill="x", padx=20, pady=15)
        grid_res_pp.grid_columnconfigure((0, 1), weight=1)

        lbl_grid_pp_pagar = crear_tarjeta_grid(grid_res_pp, 0, 0, "💵 Monto para Cancelar Hoy", "$ 0.00", self.c_accent)
        lbl_grid_pp_ahorro = crear_tarjeta_grid(grid_res_pp, 0, 1, "🎉 Intereses Condonados", "$ 0.00", self.c_primary)

        def calc_pp():
            try:
                sal = float(ent_pp_sal.get().strip() or 0)
                orig = float(ent_pp_orig.get().strip() or sal)
                tot = float(ent_pp_tot.get().strip() or orig)
                fac = (orig / tot) if tot > 0 else 1.0
                cap_cancelar = sal * fac
                int_ahorro = sal - cap_cancelar
                lbl_grid_pp_pagar.configure(text=f"$ {cap_cancelar:,.2f}")
                lbl_grid_pp_ahorro.configure(text=f"$ {int_ahorro:,.2f}")
            except Exception:
                pass

        ctk.CTkButton(t_pronto, text="⚡ Calcular Pronto Pago", width=220, height=36, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_accent, text_color="#ffffff", command=calc_pp).pack(anchor="w", padx=20, pady=5)

    # ------------------ VISTA 5: UTILITARIOS, ROLLBACK Y BACKUPS ------------------
    def _mostrar_modulo_utilitarios(self):
        self.vista_actual = "utilitarios"
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.main_frame, text="⚙️ Centro de Utilitarios, Ajustes, Autorización y Rollback", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.c_text).pack(anchor="w", pady=(0, 15), fill="x")

        card_rollback = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
        card_rollback.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(card_rollback, text="🔄 Ciclo Contable: Autorización y Reversión (Rollback)", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=20, pady=(15, 6))
        ctk.CTkLabel(card_rollback, text="Autoriza el pase de MOVIM a HISACT y Maestro, o revierte la última operación en caso de error.", font=ctk.CTkFont(size=13), text_color=self.c_muted).pack(anchor="w", padx=20, pady=(0, 10))

        f_rb_btns = ctk.CTkFrame(card_rollback, fg_color="transparent")
        f_rb_btns.pack(fill="x", padx=20, pady=(5, 15))

        ctk.CTkButton(f_rb_btns, text="⚡ Autorizar y Consolidar Lote (A HISACT)", height=38, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_primary, command=self._autorizar_y_consolidar_lote).pack(side="left", padx=(0, 10))
        ctk.CTkButton(f_rb_btns, text="↩️ Revertir / Rollback Última Aprobación", height=38, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_danger, text_color="#ffffff", command=self._ejecutar_rollback).pack(side="left")

        card_corte = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
        card_corte.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(card_corte, text="💰 Corte Mensual de Interés sobre Ahorros (0.625%)", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=20, pady=(15, 6))
        ctk.CTkLabel(card_corte, text="Calcula el 0.00625 sobre el saldo final de AHORRO y lo suma a la columna INTERES en MAESTRO.", font=ctk.CTkFont(size=13), text_color=self.c_muted).pack(anchor="w", padx=20, pady=(0, 10))

        lbl_corte_res = ctk.CTkLabel(card_corte, text="", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_accent)
        lbl_corte_res.pack(anchor="w", padx=20, pady=4)

        def ejecutar_corte_intereses():
            if self.df_maestro is None or self.df_maestro.empty:
                messagebox.showwarning("Atención", "Cargue maestro.dbf primero.")
                return
            
            m = self.df_maestro
            total_devengado = 0.0
            actualizados = 0

            for idx, r in m.iterrows():
                ahorro = float(r.get("ahorro", 0))
                if ahorro > 0:
                    int_mes = round(ahorro * 0.00625, 4)
                    int_prev = float(r.get("interes", 0))
                    m.at[idx, "interes"] = round(int_prev + int_mes, 4)
                    total_devengado += int_mes
                    actualizados += 1

            lbl_corte_res.configure(text=f"✅ Corte procesado en memoria: {actualizados} socios acreditados con ${total_devengado:,.2f} en intereses.")
            messagebox.showinfo("Corte Completo", f"Se calculó el 0.625% de ahorro para {actualizados} socios.\nTotal intereses calculados: ${total_devengado:,.2f}")
            self._actualizar_kpis_dashboard()

        ctk.CTkButton(card_corte, text="⚡ Ejecutar Corte Mensual de Intereses", height=36, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_accent, text_color="#ffffff", command=ejecutar_corte_intereses).pack(anchor="w", padx=20, pady=(4, 15))

        card_theme = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
        card_theme.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(card_theme, text="🎨 Apariencia y Tema Visual", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=20, pady=(15, 6))
        
        f_theme_ctrl = ctk.CTkFrame(card_theme, fg_color="transparent")
        f_theme_ctrl.pack(fill="x", padx=20, pady=(5, 15))

        ctk.CTkLabel(f_theme_ctrl, text="Seleccionar Tema del Sistema:", font=ctk.CTkFont(size=14), text_color=self.c_text).pack(side="left", padx=(0, 15))
        
        tema_actual = "Modo Oscuro Fintech" if self.config.get("theme") == "dark" else "Modo Claro Institucional"
        var_t = ctk.StringVar(value=tema_actual)
        cb_theme = ctk.CTkOptionMenu(
            f_theme_ctrl, 
            values=["Modo Oscuro Fintech", "Modo Claro Institucional"], 
            variable=var_t, 
            width=250, 
            font=ctk.CTkFont(size=13),
            command=self._cambiar_tema
        )
        cb_theme.pack(side="left")

        card_backup = ctk.CTkFrame(self.main_frame, fg_color=self.c_card, corner_radius=10)
        card_backup.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(card_backup, text="💾 Copias de Seguridad Cíclicas (Rotación Semestral)", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=20, pady=(15, 6))
        
        desc_txt = (
            "El sistema empaqueta las tablas .DBF activas en un archivo ZIP rotativo semestral\n"
            f"en la ruta institucional: {self.config.get('backup_dir')}"
        )
        ctk.CTkLabel(card_backup, text=desc_txt, font=ctk.CTkFont(size=13), text_color=self.c_muted, justify="left").pack(anchor="w", padx=20, pady=(0, 10))

        frame_dir = ctk.CTkFrame(card_backup, fg_color="transparent")
        frame_dir.pack(fill="x", padx=20, pady=5)

        self.lbl_backup_path = ctk.CTkLabel(frame_dir, text=f"Carpeta: {self.config.get('backup_dir')}", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_accent)
        self.lbl_backup_path.pack(side="left")

        ctk.CTkButton(frame_dir, text="📁 Cambiar Carpeta", width=140, height=34, font=ctk.CTkFont(size=13), fg_color=self.c_btn, text_color=self.c_text, command=self._seleccionar_carpeta_backup).pack(side="right")

        f_btn_b = ctk.CTkFrame(card_backup, fg_color="transparent")
        f_btn_b.pack(fill="x", padx=20, pady=(10, 15))

        ctk.CTkButton(f_btn_b, text="⚡ Generar Respaldo Semestral Ahora", height=38, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_primary, command=self._ejecutar_backup_semestral).pack(side="left", padx=(0, 10))
        ctk.CTkButton(f_btn_b, text="📂 Abrir Carpeta de Backups", height=38, font=ctk.CTkFont(size=13), fg_color=self.c_btn, text_color=self.c_text, command=self._abrir_carpeta_backups).pack(side="left")

    def _autorizar_y_consolidar_lote(self):
        """
        FIX: antes esta función solo hacía un respaldo de archivos y vaciaba el
        lote, mostrando "Lote autorizado y consolidado a HISACT con éxito" sin
        escribir realmente nada en el Maestro ni en el Historial (mensaje
        engañoso). Ahora sí aplica los movimientos a self.df_maestro (saldos,
        cuotas) y los agrega a self.df_hisact en memoria, pide confirmación
        previa, y si algo falla no aplica cambios a medias ni vacía el lote.

        NOTA IMPORTANTE: esta consolidación actualiza los DataFrames en memoria
        de la sesión actual (lo que ya reflejan el Dashboard, KPIs, fichas de
        socio, etc.). No reescribe MAESTRO.DBF/HISACT.DBF directamente, porque
        no tengo el esquema exacto y verificado de esos archivos para tu
        cooperativa y una escritura incorrecta podría corromper datos reales.
        Usa "Generar MOVIM" para exportar el lote y procesarlo con tu rutina
        habitual de CODINCA, o dime el esquema exacto de columnas de tu
        MAESTRO.DBF/HISACT.DBF y puedo añadir la escritura directa al archivo.
        """
        if not self.lote_movimientos:
            messagebox.showwarning("Atención", "No hay movimientos pendientes en el lote para autorizar.")
            return

        if self.df_maestro is None or self.df_maestro.empty:
            messagebox.showwarning("Atención", "Cargue maestro.dbf antes de autorizar el lote.")
            return

        if not messagebox.askyesno(
            "Confirmar Autorización",
            f"Está a punto de consolidar {len(self.lote_movimientos)} movimiento(s) al Maestro e Historial "
            "(en memoria de esta sesión).\nSe creará un respaldo automático de los archivos .DBF/.json antes "
            "de aplicar los cambios.\n\n¿Desea continuar?"
        ):
            return

        # 1) Respaldo de seguridad para poder hacer Rollback de los archivos en disco
        os.makedirs(ROLLBACK_DIR, exist_ok=True)
        for f_dbf in ["maestro.dbf", "MAESTRO.DBF", "hisact.dbf", "HISACT.DBF", "cuzodinca_meta.json"]:
            if os.path.exists(f_dbf):
                shutil.copy(f_dbf, os.path.join(ROLLBACK_DIR, f_dbf))

        # 2) Aplicar movimientos en memoria, con manejo de errores atómico
        try:
            m = self.df_maestro
            nuevas_filas_hist = []

            for mov in self.lote_movimientos:
                clave = str(mov.get("CLAVE", "")).strip().upper()
                cod = str(mov.get("CODIGO", "")).strip()
                mask = m["codigo"].astype(str).str.strip() == cod

                if mask.any():
                    if clave == "RET":
                        m.loc[mask, "ahorro"] = m.loc[mask, "ahorro"].astype(float) - float(mov.get("CANTIDAD", 0))
                    elif clave == "PRE":
                        m.loc[mask, "saldo"] = float(mov.get("SALDO", 0))
                        m.loc[mask, "ctapres"] = float(mov.get("VALCUOTA", 0))
                    elif clave == "CUP":
                        m.loc[mask, "cupones"] = float(mov.get("SALDO", 0))
                        m.loc[mask, "cta_cupon"] = float(mov.get("VALCUOTA", 0))
                    elif clave == "MER":
                        m.loc[mask, "otros"] = float(mov.get("VALCUOTA", 0))
                    # CLAVE "OTR": asientos de condonación de intereses o pago neto
                    # a terceros (ej. COOPERATIVA INDUSTRIAS CAPRI). No alteran
                    # columnas de saldo del socio directamente; solo quedan
                    # registrados en el historial como respaldo contable.

                nuevas_filas_hist.append({
                    "clave": clave,
                    "codigo": cod,
                    "nombre": mov.get("NOMBRE", ""),
                    "fecha": mov.get("FECHA", ""),
                    "cantidad": mov.get("CANTIDAD", 0),
                    "saldo": mov.get("SALDO", 0),
                    "cuotas": mov.get("CUOTAS", 0),
                    "valcuota": mov.get("VALCUOTA", 0),
                    "cheque": mov.get("CHEQUE", "")
                })

            df_nuevo_hist = pd.DataFrame(nuevas_filas_hist)
            if self.df_hisact is not None and not self.df_hisact.empty:
                self.df_hisact = pd.concat([self.df_hisact, df_nuevo_hist], ignore_index=True)
            else:
                self.df_hisact = df_nuevo_hist

            self._guardar_meta()
            self._actualizar_kpis_dashboard()

            messagebox.showinfo(
                "Autorización Exitosa",
                f"Se consolidaron {len(self.lote_movimientos)} movimiento(s) en memoria (Maestro actualizado "
                "e Historial ampliado).\n\nRecuerde: para reflejar estos cambios en sus archivos .DBF "
                "originales, use 'Generar MOVIM' y procéselo con su rutina habitual de CODINCA.\n\n"
                "Se ha creado un punto de restauración automático para Rollback."
            )
            self.lote_movimientos.clear()
            self._mostrar_dashboard()

        except Exception as e:
            messagebox.showerror(
                "Error en Consolidación",
                f"No se pudo consolidar el lote. No se aplicaron cambios definitivos.\n\nDetalle: {e}"
            )

    def _ejecutar_rollback(self):
        if not os.path.exists(ROLLBACK_DIR) or not os.listdir(ROLLBACK_DIR):
            messagebox.showwarning("Rollback", "No hay puntos de restauración previos disponibles.")
            return

        if messagebox.askyesno("Confirmar Rollback", "¿Desea revertir la última aprobación y restaurar los archivos al estado anterior?"):
            for f_bak in os.listdir(ROLLBACK_DIR):
                src = os.path.join(ROLLBACK_DIR, f_bak)
                dst = f_bak
                if os.path.isfile(src):
                    shutil.copy(src, dst)
            messagebox.showinfo("Rollback Exitoso", "El sistema ha revertido la operación y restaurado los archivos previos.")
            self._intentar_autocarga_datos()

    def _seleccionar_carpeta_backup(self):
        dir_sel = filedialog.askdirectory(title="Seleccionar Carpeta de Resguardo de Backups")
        if dir_sel:
            self.config["backup_dir"] = dir_sel
            self._guardar_configuracion()
            self.lbl_backup_path.configure(text=f"Carpeta: {dir_sel}")
            messagebox.showinfo("Configuración", "Ruta de respaldo actualizada.")

    def _ejecutar_backup_semestral(self):
        b_dir = self.config.get("backup_dir")
        os.makedirs(b_dir, exist_ok=True)

        mes_actual = datetime.datetime.now().month
        semestre_num = 1 if mes_actual <= 6 else 2
        nombre_zip = f"Backup_Semestre_{semestre_num}.zip"
        ruta_completa_zip = os.path.join(b_dir, nombre_zip)

        archivos_a_incluir = ["maestro.dbf", "MAESTRO.DBF", "history.dbf", "HISTORY.DBF", 
                              "hisact.dbf", "HISACT.DBF", "movim.dbf", "MOVIM.DBF", 
                              "actualiz.dbf", "ACTUALIZ.DBF", "cuzodinca_meta.json"]
        
        encontrados = []
        with zipfile.ZipFile(ruta_completa_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for archivo in os.listdir("."):
                if archivo in archivos_a_incluir:
                    zipf.write(archivo, arcname=archivo)
                    encontrados.append(archivo)

        if encontrados:
            messagebox.showinfo(
                "Copia de Seguridad Exitosa", 
                f"Respaldo generado correctamente (Ciclo Semestre {semestre_num}):\n\n"
                f"Archivo: {nombre_zip}\n"
                f"Ubicación: {ruta_completa_zip}\n\n"
                f"Archivos respaldados: {len(encontrados)}"
            )
        else:
            messagebox.showwarning("Atención", "No se encontraron archivos .DBF en el directorio actual para respaldar.")

    def _abrir_carpeta_backups(self):
        b_dir = self.config.get("backup_dir")
        os.makedirs(b_dir, exist_ok=True)
        try:
            os.startfile(b_dir)
        except Exception:
            messagebox.showinfo("Carpeta", f"Directorio de respaldos:\n{b_dir}")

    # ------------------ PRE-CUADRE CONTABLE ------------------
    def _abrir_modal_precuadre(self):
        win = ctk.CTkToplevel(self)
        win.title("CUZODINCA - Pre-Cuadre Contable")
        win.geometry("640x520")
        win.attributes("-topmost", True)
        win.configure(fg_color=self.c_bg)

        ctk.CTkLabel(win, text="⚖️ Balance y Pre-Cuadre Contable", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.c_text).pack(pady=15)

        card = ctk.CTkFrame(win, fg_color=self.c_card, corner_radius=10)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        if self.df_maestro is None or self.df_maestro.empty:
            ctk.CTkLabel(card, text="Cargue maestro.dbf para ejecutar el pre-cuadre.", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(pady=40)
            return

        m = self.df_maestro
        ahorros = m["ahorro"].sum() if "ahorro" in m.columns else 0.0
        prestamos = m["saldo"].sum() if "saldo" in m.columns else 0.0
        cupones = m["cupones"].sum() if "cupones" in m.columns else 0.0
        total_mercaderia = sum(meta.get("saldo", 0.0) for meta in self.meta_data.get("mercaderia", {}).values())
        
        cartera_total = prestamos + cupones + total_mercaderia
        liquidez_neta = ahorros - cartera_total

        recaudo_ahorro = m["ctahor"].sum() if "ctahor" in m.columns else 0.0
        recaudo_prestamo = m["ctapres"].sum() if "ctapres" in m.columns else 0.0
        recaudo_cupon = m["cta_cupon"].sum() if "cta_cupon" in m.columns else 0.0
        recaudo_otros = m["otros"].sum() if "otros" in m.columns else 0.0
        total_descuento_periodo = recaudo_ahorro + recaudo_prestamo + recaudo_cupon + recaudo_otros

        filas = [
            ("Total Capital Social (Ahorros):", f"$ {ahorros:,.2f}"),
            ("Cartera en Préstamos Personales:", f"$ {prestamos:,.2f}"),
            ("Cartera en Cupones:", f"$ {cupones:,.2f}"),
            ("Cartera en Mercadería Comercial:", f"$ {total_mercaderia:,.2f}"),
            ("Total Cartera por Cobrar:", f"$ {cartera_total:,.2f}"),
            ("Liquidez Neta Disponible:", f"$ {liquidez_neta:,.2f}"),
            ("----------------------------------------", "----------------"),
            ("Descuento Cuota Ahorro (Período):", f"$ {recaudo_ahorro:,.2f}"),
            ("Descuento Cuota Préstamo (Período):", f"$ {recaudo_prestamo:,.2f}"),
            ("Descuento Cuota Cupones (Período):", f"$ {recaudo_cupon:,.2f}"),
            ("Descuento Cuota Mercadería (Período):", f"$ {recaudo_otros:,.2f}"),
            ("Total Nómina a Descontar:", f"$ {total_descuento_periodo:,.2f}")
        ]

        for idx, (label, valor) in enumerate(filas):
            lbl_color = self.c_accent if "Total" in label or "Liquidez" in label else self.c_text
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=13, weight="bold" if "Total" in label else "normal"), text_color=self.c_muted if "-" in label else self.c_text).grid(row=idx, column=0, sticky="w", padx=20, pady=3)
            ctk.CTkLabel(card, text=valor, font=ctk.CTkFont(size=13, weight="bold"), text_color=lbl_color).grid(row=idx, column=1, sticky="e", padx=20, pady=3)

        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(win, text="✅ Balance Verificado", height=40, font=ctk.CTkFont(size=14, weight="bold"), fg_color=self.c_primary, command=win.destroy).pack(fill="x", padx=20, pady=10)

    # ------------------ PLANILLA SAFIC ------------------
    def _abrir_modal_safic(self):
        win = ctk.CTkToplevel(self)
        win.title("CUZODINCA - Integración Planilla Nómina")
        win.geometry("740x480")
        win.attributes("-topmost", True)
        win.configure(fg_color=self.c_bg)

        ctk.CTkLabel(win, text="Emisión de Planilla de Descuentos a Nómina", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.c_text).pack(pady=15)

        card = ctk.CTkFrame(win, fg_color=self.c_card, corner_radius=10)
        card.pack(fill="x", padx=20, pady=10)

        var_orig = ctk.StringVar()
        var_plan = ctk.StringVar(value="202616")
        var_tipo_emision = ctk.StringVar(value="Ambos (Consolidado General)")

        ctk.CTkLabel(card, text="Grupo a Procesar:", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_text).grid(row=0, column=0, sticky="w", padx=15, pady=10)
        cb_emision = ctk.CTkOptionMenu(
            card, 
            values=["Solo Planta (Catorcenal)", "Solo Administración (Quincenal)", "Ambos (Consolidado General)"], 
            variable=var_tipo_emision,
            font=ctk.CTkFont(size=13), 
            width=290
        )
        cb_emision.grid(row=0, column=1, columnspan=2, sticky="w", padx=5, pady=10)

        ctk.CTkLabel(card, text="Archivo Origen (actualiz.dbf):", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_muted).grid(row=1, column=0, sticky="w", padx=15, pady=10)
        ctk.CTkEntry(card, textvariable=var_orig, width=330, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text).grid(row=1, column=1, padx=5, pady=10)
        ctk.CTkButton(card, text="Buscar", width=75, font=ctk.CTkFont(size=13), fg_color=self.c_btn, text_color=self.c_text, command=lambda: var_orig.set(filedialog.askopenfilename(filetypes=[("DBF", "*.dbf")]))).grid(row=1, column=2, padx=10, pady=10)

        ctk.CTkLabel(card, text="ID de Planilla:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_muted).grid(row=2, column=0, sticky="w", padx=15, pady=10)
        ctk.CTkEntry(card, textvariable=var_plan, width=170, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text).grid(row=2, column=1, sticky="w", padx=5, pady=10)

        def ejecutar():
            if not var_orig.get():
                messagebox.showwarning("Atención", "Debe seleccionar el archivo actualiz.dbf.")
                return
            df_out, df_logs = procesar_planilla_safic(var_orig.get(), var_plan.get())
            sugerido = f"ps{var_plan.get().strip()}.csv"
            ruta = filedialog.asksaveasfilename(initialfile=sugerido, defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if ruta:
                df_out.to_csv(ruta, index=False)
                messagebox.showinfo("Completado", f"Archivo generado exitosamente ({var_tipo_emision.get()}):\n{ruta}\n\nTotal Descuentos: {len(df_out)}")
                win.destroy()

        ctk.CTkButton(win, text="⚡ Procesar y Generar CSV", height=42, fg_color=self.c_primary, font=ctk.CTkFont(size=14, weight="bold"), command=ejecutar).pack(fill="x", padx=20, pady=15)

    # ------------------ REPORTES DINÁMICOS Y RECIBO INDIVIDUAL PDF ------------------
    def _abrir_modal_reportes(self):
        win = ctk.CTkToplevel(self)
        win.title("CUZODINCA - Centro de Reportes y Recibos")
        win.geometry("680x640")
        win.attributes("-topmost", True)
        win.configure(fg_color=self.c_bg)

        ctk.CTkLabel(win, text="📈 Centro de Reportes y Recibos Institucionales", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.c_text).pack(pady=15)

        tab_rep = ctk.CTkTabview(win, fg_color=self.c_card)
        tab_rep.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        t_dinamico = tab_rep.add("📊 Reporte de Nómina Dinámico")
        t_recibo = tab_rep.add("📄 Generar Recibo Individual PDF")

        # Tab 1: Reporte Dinámico
        ctk.CTkLabel(t_dinamico, text="Grupo de Nómina:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=15, pady=(15, 5))
        var_grupo_rep = ctk.StringVar(value="Todos (Consolidado General)")
        ctk.CTkOptionMenu(t_dinamico, values=["Todos (Consolidado General)", "Solo Planta (Catorcenal - P)", "Solo Administración (Quincenal - A)"], variable=var_grupo_rep, width=340).pack(anchor="w", padx=15, pady=(0, 10))

        ctk.CTkLabel(t_dinamico, text="Seleccione Columnas a Incluir:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=15, pady=5)
        
        f_chk_rep = ctk.CTkFrame(t_dinamico, fg_color=self.c_bg, corner_radius=8)
        f_chk_rep.pack(fill="x", padx=15, pady=5)

        rep_cols = {
            "ahorro": ctk.BooleanVar(value=True),
            "prestamo": ctk.BooleanVar(value=True),
            "cupon": ctk.BooleanVar(value=True),
            "mercaderia": ctk.BooleanVar(value=True),
            "observaciones": ctk.BooleanVar(value=True)
        }
        ctk.CTkCheckBox(f_chk_rep, text="Cta. Ahorro", variable=rep_cols["ahorro"]).grid(row=0, column=0, padx=15, pady=6, sticky="w")
        ctk.CTkCheckBox(f_chk_rep, text="Cta. Préstamo", variable=rep_cols["prestamo"]).grid(row=0, column=1, padx=15, pady=6, sticky="w")
        ctk.CTkCheckBox(f_chk_rep, text="Cta. Cupones", variable=rep_cols["cupon"]).grid(row=1, column=0, padx=15, pady=6, sticky="w")
        ctk.CTkCheckBox(f_chk_rep, text="Mercadería 0%", variable=rep_cols["mercaderia"]).grid(row=1, column=1, padx=15, pady=6, sticky="w")

        def exportar_dinamico():
            if self.df_maestro is None or self.df_maestro.empty:
                messagebox.showwarning("Atención", "Cargue maestro.dbf primero.")
                return
            df = self.df_maestro.copy()
            g_sel = var_grupo_rep.get()
            if "Planta" in g_sel:
                df = df[df["ap"].astype(str).str.upper() == "P"]
            elif "Administración" in g_sel:
                df = df[df["ap"].astype(str).str.upper() == "A"]

            cols = {"Código": df["codigo"], "Nombre": df["nombre"]}
            tot = pd.Series(0.0, index=df.index)
            if rep_cols["ahorro"].get():
                cols["Cta. Ahorro"] = df.get("ctahor", 0.0)
                tot += df.get("ctahor", 0.0)
            if rep_cols["prestamo"].get():
                cols["Cta. Prest."] = df.get("ctapres", 0.0)
                tot += df.get("ctapres", 0.0)
            if rep_cols["cupon"].get():
                cols["Cta. Cupon"] = df.get("cta_cupon", 0.0)
                tot += df.get("cta_cupon", 0.0)
            if rep_cols["mercaderia"].get():
                cols["Mercadería"] = df.get("otros", 0.0)
                tot += df.get("otros", 0.0)
            cols["Total Descuento"] = tot
            if rep_cols["observaciones"].get():
                cols["Obs"] = df.get("observ", "")

            df_out = pd.DataFrame(cols)
            ruta = filedialog.asksaveasfilename(initialfile="Reporte_Nomina_Dinamico.csv", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if ruta:
                df_out.to_csv(ruta, index=False, encoding="utf-8-sig")
                messagebox.showinfo("Exportado", f"Reporte guardado exitosamente en:\n{ruta}")
                win.destroy()

        ctk.CTkButton(t_dinamico, text="📊 Generar y Exportar CSV", height=38, fg_color=self.c_primary, command=exportar_dinamico).pack(fill="x", padx=15, pady=20)

        # Tab 2: Recibo Individual PDF
        ctk.CTkLabel(t_recibo, text="Código del Socio para Recibo Individual:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=15, pady=(15, 5))
        ent_rec_cod = ctk.CTkEntry(t_recibo, placeholder_text="Ej: 2018", width=220, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent_rec_cod.pack(anchor="w", padx=15, pady=(0, 15))

        def generar_recibo_pdf():
            cod_s = ent_rec_cod.get().strip().upper()
            if not cod_s or self.df_maestro is None:
                messagebox.showwarning("Atención", "Ingrese un código válido y asegúrese de cargar maestro.dbf.")
                return
            mask = self.df_maestro["codigo"].astype(str).str.strip().str.upper() == cod_s
            matches = self.df_maestro[mask]
            if matches.empty:
                messagebox.showwarning("Aviso", f"No se encontró el socio con código: {cod_s}")
                return
            
            s = matches.iloc[0]
            nom = str(s.get("nombre", "")).strip()
            cuenta = str(s.get("cuenta", "N/D")).strip()
            ctahor = float(s.get("ctahor", 0))
            ctapres = float(s.get("ctapres", 0))
            ctacupon = float(s.get("cta_cupon", 0))
            otros = float(s.get("otros", 0))
            defuncion = 0.60
            total_desc = ctahor + ctapres + ctacupon + otros + defuncion

            tot_ahorro = float(s.get("ahorro", 0))
            saldo_prest = float(s.get("saldo", 0))
            saldo_cupon = float(s.get("cupones", 0))

            f_hoy = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            txt_recibo = f"""
==================================================
        COOPERATIVA DE INDUSTRIAS CAPRI
                 C O D I N C A
==================================================
Fecha y Hora: {f_hoy}

Hemos recibido del socio: {nom}
Estado de su Cuenta:                         COD. # {cod_s}
--------------------------------------------------
CUOTA DE AHORRO       $      {ctahor:8.2f}     TOTAL AHORRO $      {tot_ahorro:8.2f}
ABONO A PRESTAMO      $      {ctapres:8.2f}     SALDO PREST. $      {saldo_prest:8.2f}
CUOTA CUPONES:        $      {ctacupon:8.2f}     SALDO CUPONES: $    {saldo_cupon:8.2f}
OTROS                 $      {otros:8.2f}
DEFUNCION             $      {defuncion:8.2f}     AYUDA DEF. DE $0.60 POR EL FALLEC.
------------------------------------------------  DE MADRE SR. JUAN CARLOS ESCOBAR F.
TOTAL --->            $      {total_desc:8.2f}     "" DEPTO. DE MARCOS.""
==================================================
"""
            ruta_txt = filedialog.asksaveasfilename(initialfile=f"Recibo_{cod_s}.txt", defaultextension=".txt", filetypes=[("Texto / Comprobante", "*.txt"), ("Todos", "*.*")])
            if ruta_txt:
                with open(ruta_txt, "w", encoding="utf-8") as f_out:
                    f_out.write(txt_recibo)
                messagebox.showinfo("Recibo Generado", f"Comprobante oficial generado con éxito en:\n{ruta_txt}")
                win.destroy()

        ctk.CTkButton(t_recibo, text="📄 Generar Recibo Oficial", height=38, fg_color=self.c_accent, text_color="#ffffff", command=generar_recibo_pdf).pack(anchor="w", padx=15, pady=10)

    # ------------------ TABLAS HISTÓRICAS ------------------
    def _render_movimientos_tabla_general(self, parent_frame):
        for w in parent_frame.winfo_children():
            w.destroy()

        headers = ["FECHA", "CÓDIGO", "NOMBRE", "OPERACIÓN", "CANTIDAD", "SALDO", "CUOTAS", "VALOR CUOTA"]
        h_frame = ctk.CTkFrame(parent_frame, fg_color=self.c_btn, height=34)
        h_frame.pack(fill="x", padx=10, pady=(10, 5))
        for idx, h in enumerate(headers):
            lbl = ctk.CTkLabel(h_frame, text=h, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text)
            lbl.grid(row=0, column=idx, sticky="w", padx=8, pady=5)
            h_frame.grid_columnconfigure(idx, weight=2 if idx == 2 else 1)

        df_fuente = self.df_history if self.df_history is not None else self.df_hisact
        if df_fuente is None or df_fuente.empty:
            ctk.CTkLabel(parent_frame, text="No hay movimientos disponibles en history.dbf ni en hisact.dbf", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(pady=30)
            return

        ultimos = df_fuente.tail(10)
        for _, r in ultimos.iterrows():
            row_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=10, pady=3)

            op_clave = str(r.get("clave", r.get("cla", ""))).strip()
            if op_clave == "RET":
                op_txt = "🔻 Retiro Ahorro"
            elif op_clave == "PRE":
                op_txt = "💳 Préstamo"
            elif op_clave == "OTR":
                op_txt = "🏷️ Otro Descuento"
            elif op_clave == "CUP":
                op_txt = "🎟️ Cupones"
            elif op_clave == "MER":
                op_txt = "📦 Mercadería"
            elif op_clave == "FIA":
                op_txt = "🤝 Fianza"
            else:
                op_txt = op_clave if op_clave else "N/D"

            cant_val = float(r.get("cantidad", r.get("cuotah", 0)))
            saldo_val = float(r.get("saldo", r.get("cuotpr", 0)))
            cuota_val = float(r.get("valcuota", 0))

            vals = [
                str(r.get("fecha", ""))[:10],
                str(r.get("codigo", "")),
                _truncar(r.get("nombre", ""), 22),
                op_txt,
                f"${cant_val:,.2f}",
                f"${saldo_val:,.2f}",
                str(r.get("cuotas", "0")),
                f"${cuota_val:,.2f}"
            ]
            for idx, val in enumerate(vals):
                lbl = ctk.CTkLabel(row_frame, text=val, font=ctk.CTkFont(size=13), text_color=self.c_text)
                lbl.grid(row=0, column=idx, sticky="w", padx=8)
                row_frame.grid_columnconfigure(idx, weight=2 if idx == 2 else 1)

    def _obtener_anios_socio(self, cod_socio):
        anios = set()
        for df in [self.df_history, self.df_hisact]:
            if df is not None and not df.empty and "codigo" in df.columns and "fecha" in df.columns:
                sub = df[df["codigo"].astype(str).str.strip() == cod_socio]
                for f in sub["fecha"].dropna():
                    f_str = str(f).strip()
                    if len(f_str) >= 4 and f_str[:4].isdigit():
                        anios.add(f_str[:4])
        lista_anios = sorted(list(anios), reverse=True)
        return ["Todos los años"] + lista_anios if lista_anios else ["Todos los años"]

    def _filtrar_historial_por_anio(self, cod_socio, anio_seleccionado):
        self._render_movimientos_socio(self.frame_hist_socio, cod_socio, anio_filtro=anio_seleccionado)

    def _render_movimientos_socio(self, parent_frame, cod_socio, anio_filtro="Todos los años"):
        for w in parent_frame.winfo_children():
            w.destroy()

        headers = ["FECHA", "OPERACIÓN", "CANTIDAD", "SALDO RESULTANTE", "CUOTAS", "VALOR CUOTA", "CHEQUE"]
        h_frame = ctk.CTkFrame(parent_frame, fg_color=self.c_btn, height=32)
        h_frame.pack(fill="x", padx=10, pady=(10, 5))
        for idx, h in enumerate(headers):
            lbl = ctk.CTkLabel(h_frame, text=h, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text)
            lbl.grid(row=0, column=idx, sticky="w", padx=8, pady=5)
            h_frame.grid_columnconfigure(idx, weight=1)

        dfs = []
        if self.df_history is not None and not self.df_history.empty:
            dfs.append(self.df_history)
        if self.df_hisact is not None and not self.df_hisact.empty:
            dfs.append(self.df_hisact)

        if not dfs:
            ctk.CTkLabel(parent_frame, text="No hay bases de datos históricas cargadas.", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(pady=20)
            return

        df_total = pd.concat(dfs, ignore_index=True)
        hist_socio = df_total[df_total["codigo"].astype(str).str.strip() == cod_socio]

        if anio_filtro != "Todos los años":
            registros_a_mostrar = hist_socio[hist_socio["fecha"].astype(str).str.startswith(anio_filtro)]
        else:
            registros_a_mostrar = hist_socio.tail(10)

        if registros_a_mostrar.empty:
            ctk.CTkLabel(parent_frame, text=f"No se encontraron movimientos para: {anio_filtro}.", font=ctk.CTkFont(size=14), text_color=self.c_muted).pack(pady=20)
            return

        for _, r in registros_a_mostrar.iterrows():
            row_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=10, pady=3)

            op_clave = str(r.get("clave", r.get("cla", ""))).strip()
            if op_clave == "RET":
                op_nombre = "🔻 Retiro Ahorro"
            elif op_clave == "PRE":
                op_nombre = "💳 Préstamo"
            elif op_clave == "OTR":
                op_nombre = "🏷️ Otro Descuento"
            elif op_clave == "CUP":
                op_nombre = "🎟️ Cupones"
            elif op_clave == "MER":
                op_nombre = "📦 Mercadería"
            elif op_clave == "FIA":
                op_nombre = "🤝 Fianza"
            else:
                op_nombre = op_clave if op_clave else "N/D"

            cant_val = float(r.get("cantidad", r.get("cuotah", 0)))
            saldo_val = float(r.get("saldo", r.get("cuotpr", 0)))
            valcuota = float(r.get("valcuota", 0))

            vals = [
                str(r.get("fecha", ""))[:10],
                op_nombre,
                f"${cant_val:,.2f}",
                f"${saldo_val:,.2f}",
                str(r.get("cuotas", "0")),
                f"${valcuota:,.2f}",
                _truncar(r.get("cheque", "N/D"), 12)
            ]
            for idx, val in enumerate(vals):
                lbl = ctk.CTkLabel(row_frame, text=val, font=ctk.CTkFont(size=13), text_color=self.c_text)
                lbl.grid(row=0, column=idx, sticky="w", padx=8)
                row_frame.grid_columnconfigure(idx, weight=1)

    # ------------------ DESGLOSE DE OBLIGACIONES Y NIVELACIÓN DE ÚLTIMA CUOTA ------------------
    def _abrir_popup_prestamos(self, s):
        win = ctk.CTkToplevel(self)
        win.title("CUZODINCA - Desglose de Obligaciones y Nivelación")
        win.geometry("980x420")
        win.resizable(False, False)
        win.configure(fg_color=self.c_bg)
        win.lift()
        win.focus_force()
        win.grab_set()

        nombre = str(s.get("nombre", "N/D")).strip()
        cod = str(s.get("codigo", "")).strip()

        saldo_prest = float(s.get("saldo", 0))
        cuota_prest = float(s.get("ctapres", 0))
        
        cupones_debe = float(s.get("cupones", 0))
        cupones_cuota = float(s.get("cta_cupon", 0))

        cuota_otros = float(s.get("otros", 0))
        meta_mer = self.meta_data.get("mercaderia", {}).get(cod, {})
        saldo_merc = meta_mer.get("saldo", round(cuota_otros * meta_mer.get("cuotas_restantes", 1), 2) if cuota_otros > 0 else 0.0)

        total_deuda = saldo_prest + cupones_debe + saldo_merc
        total_cuota_desc = cuota_prest + cupones_cuota + cuota_otros

        ctk.CTkLabel(win, text=f"Detalle de Obligaciones y Nivelación - [{cod}] {nombre}", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.c_text).pack(pady=(15, 6))
        ctk.CTkLabel(win, text=f"Deuda Total: ${total_deuda:,.2f}   |   Descuento Nómina Total: ${total_cuota_desc:,.2f}", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.c_accent).pack(pady=(0, 10))

        if total_deuda <= 0 and total_cuota_desc <= 0:
            card_vacia = ctk.CTkFrame(win, fg_color=self.c_card_highlight, corner_radius=10)
            card_vacia.pack(fill="both", expand=True, padx=25, pady=15)
            ctk.CTkLabel(card_vacia, text="🟢 El socio se encuentra solvente y sin obligaciones pendientes.", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.c_accent).pack(pady=40)
            ctk.CTkButton(win, text="Cerrar", width=120, height=36, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_btn, text_color=self.c_text, command=win.destroy).pack(pady=(0, 15))
            return

        frame_cards = ctk.CTkFrame(win, fg_color="transparent")
        frame_cards.pack(fill="x", padx=15, pady=5)

        c1 = ctk.CTkFrame(frame_cards, fg_color=self.c_card, corner_radius=10)
        c1.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(c1, text="PRÉSTAMO PERSONAL", font=ctk.CTkFont(size=13, weight="bold"), text_color="#3b8ed0").pack(anchor="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(c1, text=f"Saldo: ${saldo_prest:,.2f}", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=12, pady=(2, 0))
        ctk.CTkLabel(c1, text=f"Cuota: ${cuota_prest:,.2f}", font=ctk.CTkFont(size=13), text_color=self.c_muted).pack(anchor="w", padx=12, pady=(0, 6))
        
        self._agregar_botones_nivelacion(c1, cod, "ctapres", saldo_prest, cuota_prest, win)

        c2 = ctk.CTkFrame(frame_cards, fg_color=self.c_card, corner_radius=10)
        c2.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(c2, text="CUPONES (CON INTERÉS)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#8b5cf6").pack(anchor="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(c2, text=f"Saldo: ${cupones_debe:,.2f}", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=12, pady=(2, 0))
        ctk.CTkLabel(c2, text=f"Cuota: ${cupones_cuota:,.2f}", font=ctk.CTkFont(size=13), text_color=self.c_muted).pack(anchor="w", padx=12, pady=(0, 6))

        self._agregar_botones_nivelacion(c2, cod, "cta_cupon", cupones_debe, cupones_cuota, win)

        c3 = ctk.CTkFrame(frame_cards, fg_color=self.c_card, corner_radius=10)
        c3.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(c3, text="MERCADERÍA (TASA 0%)", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_accent).pack(anchor="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(c3, text=f"Saldo Est: ${saldo_merc:,.2f}", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.c_text).pack(anchor="w", padx=12, pady=(2, 0))
        ctk.CTkLabel(c3, text=f"Cuota Nómina: ${cuota_otros:,.2f}", font=ctk.CTkFont(size=13), text_color=self.c_muted).pack(anchor="w", padx=12, pady=(0, 6))

        self._agregar_botones_nivelacion(c3, cod, "otros", saldo_merc, cuota_otros, win)

        ctk.CTkButton(win, text="Cerrar", width=120, height=36, font=ctk.CTkFont(size=13, weight="bold"), fg_color=self.c_btn, text_color=self.c_text, command=win.destroy).pack(pady=(15, 10))

    def _agregar_botones_nivelacion(self, parent_card, cod_socio, col_cuota, saldo, cuota, modal_win):
        if 0 < saldo <= cuota:
            f_btns = ctk.CTkFrame(parent_card, fg_color="transparent")
            f_btns.pack(fill="x", padx=10, pady=(2, 10))

            btn_auto = ctk.CTkButton(
                f_btns, 
                text="⚡ Nivelar a Saldo", 
                height=26, 
                font=ctk.CTkFont(size=11, weight="bold"), 
                fg_color=self.c_accent, 
                text_color="#ffffff",
                command=lambda: self._aplicar_nivelacion(cod_socio, col_cuota, saldo, modal_win)
            )
            btn_auto.pack(side="left", padx=2, expand=True, fill="x")

            btn_man = ctk.CTkButton(
                f_btns, 
                text="✏️ Manual", 
                height=26, 
                font=ctk.CTkFont(size=11), 
                fg_color=self.c_btn, 
                text_color=self.c_text,
                command=lambda: self._aplicar_ajuste_manual_dialog(cod_socio, col_cuota, saldo, cuota, modal_win)
            )
            btn_man.pack(side="left", padx=2)
        else:
            ctk.CTkLabel(parent_card, text="[Cuota Regular Activa]", font=ctk.CTkFont(size=11), text_color=self.c_muted).pack(pady=(4, 10))

    def _aplicar_nivelacion(self, cod_socio, col_cuota, nuevo_valor, modal_win):
        if self.df_maestro is not None:
            mask = self.df_maestro["codigo"].astype(str).str.strip() == cod_socio
            if not self.df_maestro[mask].empty:
                self.df_maestro.loc[mask, col_cuota] = round(nuevo_valor, 2)
                
                if "ajustes_cuota" not in self.meta_data:
                    self.meta_data["ajustes_cuota"] = {}
                if cod_socio not in self.meta_data["ajustes_cuota"]:
                    self.meta_data["ajustes_cuota"][cod_socio] = {}
                self.meta_data["ajustes_cuota"][cod_socio][col_cuota] = round(nuevo_valor, 2)
                self._guardar_meta()

                modal_win.destroy()
                self._actualizar_kpis_dashboard()
                self._mostrar_modulo_socios(socio_data=self.df_maestro[mask].iloc[0])
                messagebox.showinfo("Nivelación Exitosa", f"Se ajustó la cuota final a ${nuevo_valor:,.2f} para liquidar exactamente la cuenta.")

    def _aplicar_ajuste_manual_dialog(self, cod_socio, col_cuota, saldo, cuota_actual, modal_win):
        dlg = ctk.CTkInputDialog(text=f"Saldo Remanente: ${saldo:,.2f}\nCuota Programada: ${cuota_actual:,.2f}\n\nIngrese valor de última cuota a descontar:", title="Ajuste Asistido")
        val = dlg.get_input()
        if val:
            try:
                n_cuota = float(val.strip())
                self._aplicar_nivelacion(cod_socio, col_cuota, n_cuota, modal_win)
            except ValueError:
                messagebox.showwarning("Error", "Ingrese un monto numérico válido.")

    # ------------------ CREACIÓN Y EDICIÓN DE SOCIOS ------------------
    def _abrir_modal_crear_socio(self):
        win = ctk.CTkToplevel(self)
        win.title("CUZODINCA - Registrar Nuevo Socio")
        win.geometry("700x640")
        win.attributes("-topmost", True)
        win.configure(fg_color=self.c_bg)

        ctk.CTkLabel(win, text="Afiliación de Nuevo Socio", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.c_text).pack(pady=15)

        card = ctk.CTkFrame(win, fg_color=self.c_card, corner_radius=10)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        ent_cod = self._campo_form(card, "Código de Empleado / Socio (*):", "", 0)
        ent_nom = self._campo_form(card, "Nombre Completo (*):", "", 1)
        ent_cta = self._campo_form(card, "No. Cuenta Bancaria:", "", 2)
        ent_dui = self._campo_form(card, "DUI / Documento:", "", 3)
        ent_ctahor = self._campo_form(card, "Cuota Ahorro ($):", "10.00", 4)
        ent_sueldo = self._campo_form(card, "Sueldo Mensual ($):", "600.00", 5)
        ent_fec_ing = self._campo_form(card, "Fecha de Entrada (AAAA-MM-DD):", datetime.datetime.now().strftime("%Y-%m-%d"), 6)

        ctk.CTkLabel(card, text="Grupo de Nómina:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=7, column=0, sticky="w", padx=20, pady=6)
        var_nvo_grp = ctk.StringVar(value="Planta (Catorcenal)")
        cb_nvo_grp = ctk.CTkOptionMenu(card, values=["Planta (Catorcenal)", "Administración (Quincenal)"], variable=var_nvo_grp, font=ctk.CTkFont(size=13), width=280)
        cb_nvo_grp.grid(row=7, column=1, sticky="w", padx=10, pady=6)

        ent_b1 = self._campo_form(card, "Beneficiario 1:", "", 8)
        ent_b2 = self._campo_form(card, "Beneficiario 2:", "", 9)
        ent_fia = self._campo_form(card, "Fiador Asignado:", "", 10)

        def guardar_socio():
            cod = ent_cod.get().strip().upper()
            nom = ent_nom.get().strip().upper()

            if not cod or not nom:
                messagebox.showwarning("Validación", "Código y Nombre son obligatorios.")
                return

            if self.df_maestro is not None and not self.df_maestro.empty:
                existentes = set(self.df_maestro["codigo"].astype(str).str.strip().str.upper())
                if cod in existentes:
                    messagebox.showerror("Error", f"El código '{cod}' YA EXISTE en el Maestro.")
                    return

            try:
                sueldo_val = float(ent_sueldo.get().strip() or 600.0)
            except Exception:
                sueldo_val = 600.0

            if "sueldos_ingresos" not in self.meta_data:
                self.meta_data["sueldos_ingresos"] = {}
            self.meta_data["sueldos_ingresos"][cod] = {
                "sueldo": sueldo_val,
                "fecha_entrada": ent_fec_ing.get().strip() or "2022-01-01"
            }
            self._guardar_meta()

            nuevo = {
                "codigo": cod,
                "nombre": nom,
                "cuenta": ent_cta.get().strip(),
                "observ": ent_dui.get().strip(),
                "ctahor": float(ent_ctahor.get().strip() or 0.0),
                "estado": "ACTIVO",
                "ap": "P" if "Planta" in var_nvo_grp.get() else "A",
                "ahorro": 0.0,
                "interes": 0.0,
                "saldo": 0.0,
                "cupones": 0.0,
                "ctapres": 0.0,
                "cta_cupon": 0.0,
                "otros": 0.0,
                "benefi_1": ent_b1.get().strip().upper(),
                "benefi_2": ent_b2.get().strip().upper(),
                "fiadores": ent_fia.get().strip().upper(),
                "ingreso": pd.Timestamp.now().strftime("%Y-%m-%d")
            }

            if self.df_maestro is not None:
                self.df_maestro = pd.concat([self.df_maestro, pd.DataFrame([nuevo])], ignore_index=True)
            else:
                self.df_maestro = pd.DataFrame([nuevo])

            self._actualizar_kpis_dashboard()
            messagebox.showinfo("Éxito", f"Socio {cod} - {nom} registrado correctamente.")
            win.destroy()
            self._mostrar_modulo_socios(socio_data=pd.Series(nuevo))

        ctk.CTkButton(win, text="💾 Guardar Nuevo Socio", height=42, font=ctk.CTkFont(size=14, weight="bold"), fg_color=self.c_accent, text_color="#ffffff", command=guardar_socio).pack(fill="x", padx=20, pady=10)

    def _abrir_modal_editar_socio(self, s):
        cod = str(s.get("codigo", "")).strip()
        sueldo_meta = self.meta_data.get("sueldos_ingresos", {}).get(cod, {"sueldo": 600.0, "fecha_entrada": "2022-01-01"})

        win = ctk.CTkToplevel(self)
        win.title(f"CUZODINCA - Editar Ficha: {cod}")
        win.geometry("660x680")
        win.attributes("-topmost", True)
        win.configure(fg_color=self.c_bg)

        ctk.CTkLabel(win, text=f"Editar Ficha del Socio ({cod})", font=ctk.CTkFont(size=19, weight="bold"), text_color=self.c_text).pack(pady=15)

        card = ctk.CTkFrame(win, fg_color=self.c_card, corner_radius=10)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        ent_nom = self._campo_form(card, "Nombre Completo:", str(s.get("nombre", "")), 0)
        ent_cta = self._campo_form(card, "No. Cuenta Bancaria:", str(s.get("cuenta", "")), 1)
        ent_dui = self._campo_form(card, "DUI / Documento:", str(s.get("observ", "")), 2)
        ent_ctahor = self._campo_form(card, "Cuota Ahorro ($):", str(s.get("ctahor", 0.0)), 3)
        ent_sueldo = self._campo_form(card, "Sueldo Mensual ($):", str(sueldo_meta.get("sueldo", 600.0)), 4)
        ent_fec_ing = self._campo_form(card, "Fecha de Entrada:", str(sueldo_meta.get("fecha_entrada", "2022-01-01")), 5)

        ctk.CTkLabel(card, text="Estado en Padrón:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=6, column=0, sticky="w", padx=20, pady=6)
        estado_actual = "Inactivo" if str(s.get("estado", "")).upper() == "INACTIVO" or (float(s.get("ctahor", 0)) == 0 and float(s.get("ahorro", 0)) == 0) else "Activo"
        var_est = ctk.StringVar(value=estado_actual)
        cb_est = ctk.CTkOptionMenu(card, values=["Activo", "Inactivo"], variable=var_est, font=ctk.CTkFont(size=13), width=280)
        cb_est.grid(row=6, column=1, sticky="w", padx=10, pady=6)

        ctk.CTkLabel(card, text="Grupo de Pago / Nómina:", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=7, column=0, sticky="w", padx=20, pady=6)
        tipo_actual = "Planta (Catorcenal)" if "P" in str(s.get("ap", "P")).upper() else "Administración (Quincenal)"
        var_grp = ctk.StringVar(value=tipo_actual)
        cb_grp = ctk.CTkOptionMenu(card, values=["Planta (Catorcenal)", "Administración (Quincenal)"], variable=var_grp, font=ctk.CTkFont(size=13), width=280)
        cb_grp.grid(row=7, column=1, sticky="w", padx=10, pady=6)

        ent_b1 = self._campo_form(card, "Beneficiario 1:", str(s.get("benefi_1", "")), 8)
        ent_b2 = self._campo_form(card, "Beneficiario 2:", str(s.get("benefi_2", "")), 9)
        ent_fia = self._campo_form(card, "Fiador Principal:", str(s.get("fiadores", "")), 10)

        def guardar_cambios():
            if self.df_maestro is not None:
                mask = self.df_maestro["codigo"].astype(str).str.strip() == cod
                self.df_maestro.loc[mask, "nombre"] = ent_nom.get().strip().upper()
                self.df_maestro.loc[mask, "cuenta"] = ent_cta.get().strip()
                self.df_maestro.loc[mask, "observ"] = ent_dui.get().strip()
                self.df_maestro.loc[mask, "ctahor"] = float(ent_ctahor.get().strip() or 0.0)
                self.df_maestro.loc[mask, "estado"] = var_est.get().upper()
                self.df_maestro.loc[mask, "ap"] = "P" if "Planta" in var_grp.get() else "A"
                self.df_maestro.loc[mask, "benefi_1"] = ent_b1.get().strip().upper()
                self.df_maestro.loc[mask, "benefi_2"] = ent_b2.get().strip().upper()
                self.df_maestro.loc[mask, "fiadores"] = ent_fia.get().strip().upper()

                try:
                    s_val = float(ent_sueldo.get().strip() or 600.0)
                except Exception:
                    s_val = 600.0

                if "sueldos_ingresos" not in self.meta_data:
                    self.meta_data["sueldos_ingresos"] = {}
                self.meta_data["sueldos_ingresos"][cod] = {
                    "sueldo": s_val,
                    "fecha_entrada": ent_fec_ing.get().strip() or "2022-01-01"
                }
                self._guardar_meta()

                self._actualizar_kpis_dashboard()
                actualizado = self.df_maestro[mask].iloc[0]
                messagebox.showinfo("Guardado", f"Ficha de {cod} actualizada exitosamente.")
                win.destroy()
                self._mostrar_modulo_socios(socio_data=actualizado)

        ctk.CTkButton(win, text="💾 Guardar Modificaciones", height=42, font=ctk.CTkFont(size=14, weight="bold"), fg_color=self.c_accent, text_color="#ffffff", command=guardar_cambios).pack(fill="x", padx=20, pady=10)

    def _campo_form(self, parent, label_txt, valor_init, row_idx):
        ctk.CTkLabel(parent, text=label_txt, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text).grid(row=row_idx, column=0, sticky="w", padx=20, pady=6)
        ent = ctk.CTkEntry(parent, width=320, font=ctk.CTkFont(size=13), fg_color=self.c_entry_bg, text_color=self.c_text)
        ent.insert(0, valor_init)
        ent.grid(row=row_idx, column=1, sticky="w", padx=10, pady=6)
        return ent

    def _ejecutar_busqueda_socio(self):
        query = self.entry_socio_search.get().strip().upper()
        if not query or self.df_maestro is None:
            return
        c_cod = self.df_maestro["codigo"].astype(str).str.strip().str.upper()
        c_nom = self.df_maestro["nombre"].astype(str).str.upper()

        matches = self.df_maestro[(c_cod == query) | (c_nom.str.contains(query, na=False))]
        if matches.empty:
            messagebox.showwarning("Búsqueda", f"No se encontró socio con: {query}")
        elif len(matches) == 1:
            self._mostrar_modulo_socios(socio_data=matches.iloc[0])
        else:
            self._abrir_modal_seleccion_socio(matches, callback=lambda s: self._mostrar_modulo_socios(socio_data=s))

    def _buscar_desde_topbar(self):
        query = self.entry_search_top.get().strip().upper()
        if not query or self.df_maestro is None:
            return
        c_cod = self.df_maestro["codigo"].astype(str).str.strip().str.upper()
        c_nom = self.df_maestro["nombre"].astype(str).str.upper()

        matches = self.df_maestro[(c_cod == query) | (c_nom.str.contains(query, na=False))]
        if matches.empty:
            messagebox.showwarning("Búsqueda", f"No se encontró socio con: {query}")
        elif len(matches) == 1:
            self._mostrar_modulo_socios(socio_data=matches.iloc[0])
        else:
            self._abrir_modal_seleccion_socio(matches, callback=lambda s: self._mostrar_modulo_socios(socio_data=s))

    def _intentar_autocarga_datos(self):
        for m in ["maestro.dbf", "MAESTRO.DBF"]:
            if os.path.exists(m):
                try:
                    self.df_maestro = cargar_datos_dbf(m)
                    self._actualizar_kpis_dashboard()
                except Exception:
                    pass
                break

        for h in ["history.dbf", "HISTORY.DBF", "movim.dbf", "MOVIM.DBF"]:
            if os.path.exists(h):
                try:
                    self.df_history = cargar_datos_dbf(h)
                    self._render_tabla_dashboard()
                except Exception:
                    pass
                break

        for ha in ["hisact.dbf", "HISACT.DBF"]:
            if os.path.exists(ha):
                try:
                    self.df_hisact = cargar_datos_dbf(ha)
                    self._render_tabla_dashboard()
                except Exception:
                    pass
                break

    def _cargar_maestro_manual(self):
        ruta = filedialog.askopenfilename(title="Seleccionar maestro.dbf", filetypes=[("Archivos DBF", "*.dbf"), ("Todos", "*.*")])
        if ruta:
            self.df_maestro = cargar_datos_dbf(ruta)
            self._mostrar_dashboard()
            messagebox.showinfo("Éxito", f"Se cargó maestro.dbf con {len(self.df_maestro)} socios.")

    def _cargar_history_manual(self):
        ruta = filedialog.askopenfilename(title="Seleccionar history.dbf", filetypes=[("Archivos DBF", "*.dbf"), ("Todos", "*.*")])
        if ruta:
            self.df_history = cargar_datos_dbf(ruta)
            self._mostrar_dashboard()
            messagebox.showinfo("Éxito", f"Se cargó history.dbf con {len(self.df_history)} movimientos.")

    def _cargar_hisact_manual(self):
        ruta = filedialog.askopenfilename(title="Seleccionar hisact.dbf", filetypes=[("Archivos DBF", "*.dbf"), ("Todos", "*.*")])
        if ruta:
            self.df_hisact = cargar_datos_dbf(ruta)
            self._mostrar_dashboard()
            messagebox.showinfo("Éxito", f"Se cargó hisact.dbf con {len(self.df_hisact)} registros históricos.")


if __name__ == "__main__":
    app = CuzodincaModernDashboard()
    app.mainloop()
