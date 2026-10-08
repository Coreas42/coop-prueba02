"""Paleta de temas para la interfaz CUZODINCA."""

THEMES = {
    "dark": {
        "c_bg": "#0b1320",
        "c_sidebar": "#0f172a",
        "c_card": "#1e293b",
        "c_card_highlight": "#134e4a",
        "c_text": "#f8fafc",
        "c_muted": "#94a3b8",
        "c_accent": "#10b981",
        "c_btn": "#334155",
        "c_primary": "#2563eb",
        "c_warning": "#f59e0b",
        "c_danger": "#ef4444",
        "c_entry_bg": "#0f172a",
    },
    "light": {
        "c_bg": "#f1f5f9",
        "c_sidebar": "#e2e8f0",
        "c_card": "#ffffff",
        "c_card_highlight": "#e6f4ea",
        "c_text": "#0f172a",
        "c_muted": "#475569",
        "c_accent": "#059669",
        "c_btn": "#cbd5e1",
        "c_primary": "#1d4ed8",
        "c_warning": "#b45309",
        "c_danger": "#dc2626",
        "c_entry_bg": "#f8fafc",
    },
}

def get_theme(mode="dark"):
    return THEMES.get(mode, THEMES["dark"])
