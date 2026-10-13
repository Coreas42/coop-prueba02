import customtkinter as ctk
import datetime
import pandas as pd
from app.config import load_config, AppConfig
from app.core.dbf_engine import DBFEngine
from app.theme import get_theme


class DashboardView(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config_obj = load_config()
        self.config = self.config_obj.to_dict()
        self.db_engine = DBFEngine()
        
        theme = get_theme(self.config.get("theme", "dark"))
        self.theme = theme
        
        ctk.set_appearance_mode(self.config.get("theme", "dark"))
        ctk.set_default_color_theme("blue")
        
        self.title("CUZODINCA - Sistema de Control Financiero")
        self.geometry("1440x900")
        self.minsize(1200, 780)
        self.configure(fg_color=self.theme["c_bg"])
        
        # Cargar datos
        self.df_maestro = self.db_engine.leer_maestro_df()
        self.df_history = self.db_engine.leer_history_df()
        self.df_hisact = self.db_engine.leer_hisact_df()
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self._create_topbar()
        self._create_sidebar()
        self._create_main_area()
        self._create_footer()

    def _create_topbar(self):
        topbar = ctk.CTkFrame(self, height=60, fg_color=self.theme["c_sidebar"], corner_radius=0)
        topbar.grid(row=0, column=0, columnspan=2, sticky="new")
        topbar.grid_propagate(False)
        
        lbl_brand = ctk.CTkLabel(
            topbar,
            text="CUZODINCA",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme["c_text"]
        )
        lbl_brand.pack(side="left", padx=20)
        
        lbl_status = ctk.CTkLabel(
            topbar,
            text="● Sistema Listo",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme["c_accent"]
        )
        lbl_status.pack(side="right", padx=20)

    def _create_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=230, fg_color=self.theme["c_sidebar"], corner_radius=0)
        sidebar.grid(row=1, column=0, sticky="nsw")
        sidebar.pack_propagate(False)
        
        lbl_logo = ctk.CTkLabel(
            sidebar,
            text="🏦 CUZODINCA",
            font=ctk.CTkFont(size=19, weight="bold"),
            text_color=self.theme["c_text"]
        )
        lbl_logo.pack(anchor="w", padx=20, pady=(20, 3))
        
        lbl_sub = ctk.CTkLabel(
            sidebar,
            text="Gestión de Cooperativa",
            font=ctk.CTkFont(size=12),
            text_color=self.theme["c_muted"]
        )
        lbl_sub.pack(anchor="w", padx=20, pady=(0, 20))
        
        btn_exit = ctk.CTkButton(
            sidebar,
            text="🚪 Salir del Sistema",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.theme["c_danger"],
            text_color="#ffffff",
            height=38,
            command=self.destroy
        )
        btn_exit.pack(side="bottom", fill="x", padx=15, pady=20)

    def _create_main_area(self):
        main_frame = ctk.CTkFrame(self, fg_color=self.theme["c_bg"], corner_radius=0)
        main_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=15)
        
        title = ctk.CTkLabel(
            main_frame,
            text="Dashboard Principal - CUZODINCA v3.5 (Modular)",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.theme["c_text"]
        )
        title.pack(anchor="w", pady=(0, 10))
        
        info = ctk.CTkLabel(
            main_frame,
            text="Base de datos y módulos cargados correctamente.",
            font=ctk.CTkFont(size=13),
            text_color=self.theme["c_muted"]
        )
        info.pack(anchor="w", pady=(0, 20))
        
        # KPI Cards
        if self.df_maestro is not None and not self.df_maestro.empty:
            num_socios = len(self.df_maestro)
            ahorros = float(self.df_maestro["ahorro"].sum()) if "ahorro" in self.df_maestro.columns else 0.0
            cartera = float(self.df_maestro["saldo"].sum()) if "saldo" in self.df_maestro.columns else 0.0
            
            kpi_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            kpi_frame.pack(fill="x", pady=10)
            
            self._create_kpi_card(kpi_frame, "👥 Socios Activos", f"{num_socios}", "En el sistema", 0)
            self._create_kpi_card(kpi_frame, "💰 Capital Social", f"${ahorros:,.2f}", "Fondos disponibles", 1)
            self._create_kpi_card(kpi_frame, "📊 Cartera en Créditos", f"${cartera:,.2f}", "Por cobrar", 2)

    def _create_kpi_card(self, parent, titulo, valor, subtexto, col):
        card = ctk.CTkFrame(parent, fg_color=self.theme["c_card"], corner_radius=10)
        card.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(size=13, weight="bold"), text_color=self.theme["c_muted"]).pack(anchor="w", padx=15, pady=(12, 0))
        ctk.CTkLabel(card, text=valor, font=ctk.CTkFont(size=22, weight="bold"), text_color=self.theme["c_text"]).pack(anchor="w", padx=15, pady=(4, 2))
        ctk.CTkLabel(card, text=subtexto, font=ctk.CTkFont(size=12), text_color=self.theme["c_accent"]).pack(anchor="w", padx=15, pady=(0, 12))

    def _create_footer(self):
        footer = ctk.CTkFrame(self, height=32, fg_color=self.theme["c_sidebar"], corner_radius=0)
        footer.grid(row=2, column=0, columnspan=2, sticky="sew")
        footer.grid_propagate(False)
        
        lbl_version = ctk.CTkLabel(footer, text="CUZODINCA v3.5 (Modular x CODINCA)", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.theme["c_accent"])
        lbl_version.pack(side="right", padx=15)
