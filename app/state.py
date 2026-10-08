class AppState:
    def __init__(self):
        self.df_maestro = None
        self.df_history = None
        self.df_hisact = None
        self.df_listado = None
        self.socio_actual = None
        self.lote_movimientos = []
        self.fecha_sesion = None
        self.secuencia_correlativo = 1
        self.ultimo_movimiento_registrado = None
        self.config = {}
        self.meta_data = {}
