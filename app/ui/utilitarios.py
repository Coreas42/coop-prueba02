import customtkinter as ctk


class UtilitariosView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        ctk.CTkLabel(self, text="Utilitarios y respaldos").pack(padx=20, pady=20)
