import customtkinter as ctk
from app.theme import get_theme


class IngresoView(ctk.CTkFrame):
    def __init__(self, master, app_context):
        super().__init__(master)
        self.app = app_context
        self.theme = get_theme(self.app.config.get("theme", "dark"))
        self.configure(fg_color=self.theme["c_bg"])
        self.pack(fill="both", expand=True)
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="Ingreso de Lotes - Captura de Movimientos",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme["c_text"]
        ).pack(anchor="w", padx=20, pady=15)
        
        info = ctk.CTkLabel(
            self,
            text="Módulo para registrar: Retiros, Créditos, Refinanciamientos y Fianzas.",
            font=ctk.CTkFont(size=13),
            text_color=self.theme["c_muted"]
        )
        info.pack(anchor="w", padx=20, pady=(0, 15))
