import json
import os

CONFIG_FILE = "data/config/cuzodinca_config.json"
META_FILE = "data/config/cuzodinca_meta.json"
DEFAULT_BACKUP_PATH = r"C:\Users\ccodinca\Downloads\CUZODINCA-Windows"


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
    return load_json(CONFIG_FILE, {
        "backup_dir": DEFAULT_BACKUP_PATH,
        "theme": "dark",
        "tasa_interes_defecto": 2.60,
        "ultimo_secuencial": 1,
        "ultimo_mes_correlativo": "01",
    })


def load_meta():
    ensure_directories()
    return load_json(META_FILE, {
        "mercaderia": {},
        "ajustes_cuota": {},
        "sueldos_ingresos": {},
    })


def save_config(config):
    ensure_directories()
    save_json(CONFIG_FILE, config)


def save_meta(meta):
    ensure_directories()
    save_json(META_FILE, meta)
