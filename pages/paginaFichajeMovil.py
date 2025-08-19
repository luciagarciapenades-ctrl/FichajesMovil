import streamlit as st
import pandas as pd
from datetime import datetime
import os, sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))  # sube de /pages a la raíz
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


import login as login

import sqlite3
from datetime import datetime, timezone
import config as cfg
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase
import cv2
import av
import numpy as np
import qrcode
import time
import re



IS_CLOUD = "/mount/src" in os.getcwd()
DEFAULT_DATA_DIR = "/mount/data" if IS_CLOUD else os.path.join(os.path.dirname(__file__), "data")

BASE_DIR = st.secrets.get("DATA_DIR", DEFAULT_DATA_DIR)
os.makedirs(BASE_DIR, exist_ok=True)

DB_FICHAJES = os.path.join(BASE_DIR, "fichajes.db")
DB_RRHH     = os.path.join(BASE_DIR, "rrhh.db")
BAJAS_DIR   = os.path.join(BASE_DIR, "bajas_adjuntos")
os.makedirs(BAJAS_DIR, exist_ok=True)


archivo = __file__.split("\\")[-1]   # nombre del archivo actual
login.generarLogin(archivo)




# ======== Config DB (SQLite) ========
DB_FILE = DB_FICHAJES
TABLE = "fichajes"

def get_conn():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    return sqlite3.connect(DB_FILE)

def ensure_schema():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empleado TEXT NOT NULL,
                fecha_local TEXT NOT NULL,   -- 'YYYY-MM-DD HH:MM:SS'
                fecha_utc   TEXT NOT NULL,   -- 'YYYY-MM-DD HH:MM:SS' (UTC)
                tipo TEXT NOT NULL CHECK (tipo IN ('Entrada','Salida')),
                observaciones TEXT,
                fuente TEXT DEFAULT 'movil',
                created_at_utc TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()

def insertar_fichaje(empleado: str, tipo: str, observaciones: str) -> dict:
    """Inserta el fichaje usando el instante real de pulsación."""
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)
    registro = {
        "empleado": empleado,
        "fecha_local": now_local.strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_utc":   now_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "tipo": tipo,
        "observaciones": observaciones or ""
    }
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE} (empleado, fecha_local, fecha_utc, tipo, observaciones) "
            "VALUES (?, ?, ?, ?, ?);",
            (registro["empleado"], registro["fecha_local"], registro["fecha_utc"],
             registro["tipo"], registro["observaciones"])
        )
        conn.commit()
    return registro

def cargar_historial(limit=100, empleado_filtro=None):
    with get_conn() as conn:
        base = f"SELECT empleado, fecha_local, tipo, observaciones FROM {TABLE} "
        params = []
        if empleado_filtro:
            base += "WHERE empleado = ? "
            params.append(empleado_filtro)
        base += "ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return pd.read_sql_query(base, conn, params=params)

# ====== UI ======
ensure_schema()
# Variable compartida para almacenar contenido del QR
if "qr_data" not in st.session_state:
    st.session_state.qr_data = ""

class QRScanner(VideoTransformerBase):
    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)
        if data:
            st.session_state.qr_data = data
        return img
st.header("Fichaje")

st.info("Escanea el código QR de la oficina para habilitar el fichaje.")
webrtc_streamer(key="qr", video_transformer_factory=QRScanner)

# Valor secreto esperado en el QR
valor_esperado = "penades-fichaje-autorizado-2025"

if st.session_state.qr_data == valor_esperado:
    st.success("QR válido detectado. Puedes fichar.")
    permitir_fichaje = True
else:
    permitir_fichaje = False
    st.warning("Esperando escaneo de QR válido para permitir fichaje.")

# El usuario debe estar logueado y se usa directamente (no hay selector)
usuario_log = st.session_state.get("usuario")
if not usuario_log:
    st.warning("Inicia sesión para fichar.")
    st.stop()




# Observaciones opcionales
observaciones = st.text_area("Observaciones (opcional)", placeholder="Escribe un comentario si lo necesitas")

# Dos botones: ENTRADA / SALIDA
c1, c2 = st.columns(2)
if permitir_fichaje:
    with c1:
        if st.button("Fichar ENTRADA", type="primary", use_container_width=True):
            try:
                reg = insertar_fichaje(usuario_log, "Entrada", observaciones)
                st.success(f"Entrada registrada — {reg['fecha_local']}")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error al registrar la entrada: {e}")

    with c2:
        if st.button("Fichar SALIDA", use_container_width=True):
            try:
                reg = insertar_fichaje(usuario_log, "Salida", observaciones)
                st.success(f"Salida registrada — {reg['fecha_local']}")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error al registrar la salida: {e}")
else:
    st.stop()




# Historial (solo del usuario logueado)
st.subheader("Tus últimos fichajes")
df_hist = cargar_historial(limit=200, empleado_filtro=usuario_log)
# Renombrar las columnas del DataFrame
df_hist = df_hist.rename(columns={
    "empleado": "Empleado",
    "fecha_local": "Fecha y hora",
    "tipo": "Tipo de fichaje",
    "observaciones": "Observaciones"
})
st.dataframe(df_hist, use_container_width=True)