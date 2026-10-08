import customtkinter as ctk


class IngresoView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        ctk.CTkLabel(self, text="Ingreso de lotes").pack(padx=20, pady=20)
