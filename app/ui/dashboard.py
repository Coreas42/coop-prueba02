import customtkinter as ctk


class DashboardView(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CUZODINCA")
        self.geometry("1400x900")
        self.configure(fg_color="#0b1320")

        self._build_ui()

    def _build_ui(self):
        lbl = ctk.CTkLabel(
            self,
            text="CUZODINCA - Dashboard Base",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#f8fafc",
        )
        lbl.pack(padx=20, pady=20)

        info = ctk.CTkLabel(
            self,
            text="Módulo base separado y listo para migrar la lógica actual del sistema.",
            font=ctk.CTkFont(size=14),
            text_color="#94a3b8",
        )
        info.pack(padx=20, pady=(0, 20))

        btn = ctk.CTkButton(
            self,
            text="Sistema Preparado para Refactorización",
            width=320,
            height=42,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self.destroy,
        )
        btn.pack(padx=20, pady=10)
