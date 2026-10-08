import customtkinter as ctk


class SociosView(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True)
        ctk.CTkLabel(self, text="Ficha de socios").pack(padx=20, pady=20)
