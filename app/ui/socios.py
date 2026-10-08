import customtkinter as ctk
from app.theme import get_theme


class SociosView(ctk.CTkFrame):
    def __init__(self, master, app_context):
        super().__init__(master)
        self.app = app_context
        self.theme = get_theme(self.app.config.get("theme", "dark"))
        self.configure(fg_color=self.theme["c_bg"])
        self.pack(fill="both", expand=True)

    def renderizar_socio(self, socio_data):
        for w in self.winfo_children():
            w.destroy()
        
        if socio_data is None:
            ctk.CTkLabel(
                self,
                text="Seleccione un socio para ver su ficha.",
                font=ctk.CTkFont(size=14),
                text_color=self.theme["c_muted"]
            ).pack(pady=40)
            return
        
        cod = str(socio_data.get("codigo", "")).strip()
        nom = str(socio_data.get("nombre", "")).strip()
        
        ctk.CTkLabel(
            self,
            text=f"Ficha del Socio: {cod} - {nom}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.theme["c_text"]
        ).pack(anchor="w", padx=20, pady=15)
