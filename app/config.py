from dataclasses import dataclass
import json
import os

CONFIG_FILE = "data/config/cuzodinca_config.json"
META_FILE = "data/config/cuzodinca_meta.json"
DEFAULT_BACKUP_PATH = r"C:\Users\ccodinca\Downloads\CUZODINCA-Windows"


@dataclass
class AppConfig:
    backup_dir: str = DEFAULT_BACKUP_PATH
    theme: str = "dark"
    tasa_interes_defecto: float = 2.60
    ultimo_secuencial: int = 1
    ultimo_mes_correlativo: str = "01"

    def to_dict(self):
        return {
            "backup_dir": self.backup_dir,
            "theme": self.theme,
            "tasa_interes_defecto": self.tasa_interes_defecto,
            "ultimo_secuencial": self.ultimo_secuencial,
            "ultimo_mes_correlativo": self.ultimo_mes_correlativo,
        }

    @classmethod
    def from_dict(cls, payload):
        data = payload or {}
        return cls(
            backup_dir=data.get("backup_dir", DEFAULT_BACKUP_PATH),
            theme=data.get("theme", "dark"),
            tasa_interes_defecto=float(data.get("tasa_interes_defecto", 2.60)),
            ultimo_secuencial=int(data.get("ultimo_secuencial", 1)),
            ultimo_mes_correlativo=str(data.get("ultimo_mes_correlativo", "01")),
        )


def ensure_directories():
    os.makedirs("data/config", exist_ok=True)
    os.makedirs("data/backups", exist_ok=True)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)


def load_config():
    ensure_directories()
    config_data = load_json(CONFIG_FILE, {
        "backup_dir": DEFAULT_BACKUP_PATH,
        "theme": "dark",
        "tasa_interes_defecto": 2.60,
        "ultimo_secuencial": 1,
        "ultimo_mes_correlativo": "01",
    })
    return AppConfig.from_dict(config_data)


def save_config(config):
    ensure_directories()
    save_json(CONFIG_FILE, config.to_dict())


def load_meta():
    ensure_directories()
    return load_json(META_FILE, {
        "mercaderia": {},
        "ajustes_cuota": {},
        "sueldos_ingresos": {},
    })


def save_meta(meta):
    ensure_directories()
    save_json(META_FILE, meta)
