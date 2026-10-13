import customtkinter as ctk
from app.ui.dashboard import DashboardView


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = DashboardView()
    app.mainloop()


if __name__ == "__main__":
    main()
