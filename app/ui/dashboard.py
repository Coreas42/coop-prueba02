import customtkinter as ctk

from app.config import load_config
from app.dbf_manager import cargar_archivos_principales


class DashboardView(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.archivos_dbf = cargar_archivos_principales()

        ctk.set_appearance_mode(self.config.theme)

        self.title("CUZODINCA")
        self.geometry("1200x700")
        self.configure(fg_color="#0b1320")

        self._build_ui()

    def _build_ui(self):
        self.title_label = ctk.CTkLabel(
            self,
            text="CUZODINCA - Dashboard Base",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#f8fafc",
        )
        self.title_label.pack(anchor="w", padx=25, pady=(25, 10))

        self.status_frame = ctk.CTkFrame(self, fg_color="#111827", corner_radius=10)
        self.status_frame.pack(fill="x", padx=25, pady=10)

        archivos = self.archivos_dbf
        maestro = "✅ maestro.dbf cargado" if "maestro.dbf" in archivos else "⚠️ maestro.dbf no encontrado"
        history = "✅ history.dbf cargado" if "history.dbf" in archivos else "⚠️ history.dbf no encontrado"
        hisact = "✅ hisact.dbf cargado" if "hisact.dbf" in archivos else "⚠️ hisact.dbf no encontrado"

        self.lbl_status = ctk.CTkLabel(
            self.status_frame,
            text=f"Tema: {self.config.theme}\n{maestro}\n{history}\n{hisact}\nTasa por defecto: {self.config.tasa_interes_defecto:.2f}%",
            justify="left",
            font=ctk.CTkFont(size=14),
            text_color="#d1d5db",
        )
        self.lbl_status.pack(anchor="w", padx=18, pady=18)

        self.info_label = ctk.CTkLabel(
            self,
            text="La lógica financiera y la carga de DBF ya fueron separadas a módulos reutilizables.",
            font=ctk.CTkFont(size=15),
            text_color="#94a3b8",
        )
        self.info_label.pack(anchor="w", padx=25, pady=(10, 5))

        self.next_button = ctk.CTkButton(
            self,
            text="Refactorización base lista",
            width=260,
            height=42,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self.destroy,
        )
        self.next_button.pack(anchor="w", padx=25, pady=(10, 0))
