import streamlit as st
import pandas as pd
import login as login
import os
import sqlite3
from datetime import datetime, date, timedelta
import config as cfg

BASE_DIR = st.secrets.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(BASE_DIR, exist_ok=True)

DB_FICHAJES = os.path.join(BASE_DIR, "fichajes.db")
DB_RRHH     = os.path.join(BASE_DIR, "rrhh.db")
BAJAS_DIR   = os.path.join(BASE_DIR, "bajas_adjuntos")
os.makedirs(BAJAS_DIR, exist_ok=True)

archivo = __file__.split("\\")[-1]   # nombre del archivo actual
login.generarLogin(archivo)


# ======== Config DB (SQLite) ========
DB_FILE = cfg.RRHH_DB
VAC_TABLE = "vacaciones"
BAJ_TABLE = "bajas"


def get_conn():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    return sqlite3.connect(DB_FILE)

def ensure_tables():
    with get_conn() as conn:
        cur = conn.cursor()
        # Vacaciones
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {VAC_TABLE}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                fecha_inicio TEXT NOT NULL,   -- YYYY-MM-DD
                fecha_fin    TEXT NOT NULL,   -- YYYY-MM-DD
                dias INTEGER NOT NULL,
                comentario TEXT,
                estado TEXT NOT NULL DEFAULT 'Pendiente',  -- Pendiente | Aprobado | Rechazado | Cancelado
                fecha_solicitud TEXT NOT NULL              -- YYYY-MM-DD HH:MM:SS
            );
        """)
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{VAC_TABLE}_usuario ON {VAC_TABLE}(usuario);")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{VAC_TABLE}_estado  ON {VAC_TABLE}(estado);")

        # Bajas / permisos
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {BAJ_TABLE}(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL,
                tipo TEXT NOT NULL,              -- Enfermedad común | Accidente laboral | Paternidad/Maternidad | Otros
                fecha_inicio TEXT NOT NULL,      -- YYYY-MM-DD
                fecha_fin TEXT,                  -- opcional
                descripcion TEXT,
                archivos TEXT,                   -- rutas separadas por ';'
                estado TEXT NOT NULL DEFAULT 'Notificada',
                fecha_registro TEXT NOT NULL     -- YYYY-MM-DD HH:MM:SS
            );
        """)
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{BAJ_TABLE}_usuario ON {BAJ_TABLE}(usuario);")
        conn.commit()

def guardar_vacaciones(usuario:str, fi:date, ff:date, dias:int, comentario:str):
    with get_conn() as conn:
        conn.execute(f"""
            INSERT INTO {VAC_TABLE}(usuario, fecha_inicio, fecha_fin, dias, comentario, estado, fecha_solicitud)
            VALUES (?, ?, ?, ?, ?, 'Pendiente', ?)
        """, (usuario, fi.strftime("%Y-%m-%d"), ff.strftime("%Y-%m-%d"), dias, comentario or "", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

def listar_vacaciones(usuario:str)->pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(
            f"SELECT id, fecha_inicio, fecha_fin, dias, comentario, estado, fecha_solicitud "
            f"FROM {VAC_TABLE} WHERE usuario=? ORDER BY id DESC",
            conn, params=(usuario,)
        )

def cancelar_vacacion(id_:int, usuario:str):
    with get_conn() as conn:
        conn.execute(f"UPDATE {VAC_TABLE} SET estado='Cancelado' WHERE id=? AND usuario=?", (id_, usuario))
        conn.commit()

def guardar_baja(usuario:str, tipo:str, fi:date, ff:date|None, descripcion:str, archivos_paths:list[str]):
    rutas = ";".join(archivos_paths) if archivos_paths else ""
    with get_conn() as conn:
        conn.execute(f"""
            INSERT INTO {BAJ_TABLE}(usuario, tipo, fecha_inicio, fecha_fin, descripcion, archivos, estado, fecha_registro)
            VALUES (?, ?, ?, ?, ?, ?, 'Notificada', ?)
        """, (usuario, tipo, fi.strftime("%Y-%m-%d"), ff.strftime("%Y-%m-%d") if ff else None,
              descripcion or "", rutas, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

def listar_bajas(usuario:str)->pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(
            f"SELECT id, tipo, fecha_inicio, IFNULL(fecha_fin,'') AS fecha_fin, descripcion, estado, archivos, fecha_registro "
            f"FROM {BAJ_TABLE} WHERE usuario=? ORDER BY id DESC",
            conn, params=(usuario,)
        )

# ================= UI ==================
ensure_tables()

st.header("Ausencias")

if 'usuario' not in st.session_state:
    st.warning("Acceso denegado. Inicia sesión.")
    st.stop()

usuario_actual = st.session_state['usuario']

tab1, tab2 = st.tabs(["Vacaciones", "Bajas / Permisos"])

# ---- Tab Vacaciones ----
with tab1:
    st.subheader("Solicitud de vacaciones")
    col1, col2 = st.columns(2)
    with col1:
        fi = st.date_input("Fecha de inicio", min_value=date.today(), value=date.today())
    with col2:
        ff = st.date_input("Fecha de fin", min_value=fi, value=max(fi, date.today()))

    if ff < fi:
        st.error("La fecha de fin no puede ser anterior a la fecha de inicio.")
    else:
        dias = (ff - fi).days + 1
        st.info(f"Días solicitados: **{dias}**")

    comentario = st.text_area("Comentario (opcional)")

    cols_btn = st.columns(2)
    with cols_btn[0]:
        if st.button("Enviar solicitud", type="primary", use_container_width=True, disabled=ff < fi):
            try:
                guardar_vacaciones(usuario_actual, fi, ff, dias, comentario)
                st.success("Solicitud enviada. Estado: Pendiente")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar la solicitud: {e}")

    st.markdown("---")
    st.caption("Tus solicitudes")
    dfv = listar_vacaciones(usuario_actual)
    if dfv.empty:
        st.info("Aún no has realizado solicitudes de vacaciones.")
    else:
        # Botón de cancelar para las pendientes
        for _, row in dfv.iterrows():
            with st.container(border=True):
                st.write(f"📅 {row['fecha_inicio']} → {row['fecha_fin']}  ·  {row['dias']} día(s)  ·  **{row['estado']}**")
                if str(row['comentario']).strip():
                    st.caption(row['comentario'])
                if row['estado'] == 'Pendiente':
                    if st.button("Cancelar", key=f"cancel_{row['id']}"):
                        cancelar_vacacion(int(row['id']), usuario_actual)
                        st.success("Solicitud cancelada.")
                        st.rerun()

# ---- Tab Bajas / Permisos ----
with tab2:
    st.subheader("Comunicar baja o permiso")
    tipos = ["Enfermedad común", "Accidente laboral", "Paternidad/Maternidad", "Hospitalización familiar", "Cita médica", "Otros"]
    tipo = st.selectbox("Tipo", tipos)
    c1, c2 = st.columns(2)
    with c1:
        fi_b = st.date_input("Fecha de inicio", value=date.today())
    with c2:
        ff_b = st.date_input("Fecha de fin (opcional)", value=date.today())
        usar_fin = st.checkbox("Indicar fecha fin", value=False)
    descripcion = st.text_area("Descripción / Observaciones (opcional)")

    st.write("Adjuntar documentos (PDF/JPG/PNG/DOCX)")
    files = st.file_uploader("Selecciona archivos", type=["pdf","jpg","jpeg","png","docx"], accept_multiple_files=True)

    # Guardar
    if st.button("Notificar baja / permiso", type="primary"):
        try:
            # Guardar adjuntos
            carpeta = os.path.join(cfg.BAJAS_DIR, usuario_actual)
            os.makedirs(carpeta, exist_ok=True)
            saved = []
            if files:
                for f in files:
                    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{f.name}"
                    path = os.path.join(carpeta, safe_name)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    saved.append(path)
            guardar_baja(usuario_actual, tipo, fi_b, (ff_b if usar_fin else None), descripcion, saved)
            st.success("Baja / permiso registrado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al registrar la baja: {e}")

    st.markdown("---")
    st.caption("Tus bajas / permisos comunicados")
    dfb = listar_bajas(usuario_actual)
    if dfb.empty:
        st.info("No hay bajas ni permisos registrados.")
    else:
        # Mostrar con posibilidad de descargar adjuntos
        for _, row in dfb.iterrows():
            with st.container(border=True):
                rango = f"{row['fecha_inicio']}" + (f" → {row['fecha_fin']}" if str(row['fecha_fin']).strip() else "")
                st.write(f"🧾 **{row['tipo']}** · {rango} · **{row['estado']}**")
                if str(row['descripcion']).strip():
                    st.caption(row['descripcion'])
                if str(row['archivos']).strip():
                    st.caption("Adjuntos:")
                    rutas = str(row['archivos']).split(';')
                    for i, ruta in enumerate([r for r in rutas if r]):
                        try:
                            with open(ruta, "rb") as f:
                                st.download_button(f"Descargar adjunto {i+1}", f.read(), file_name=os.path.basename(ruta), key=f"dl_{row['id']}_{i}")
                        except Exception:
                            st.caption(f"• {os.path.basename(ruta)} (no encontrado)")