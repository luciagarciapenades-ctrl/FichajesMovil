import os
import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_cookies_controller import CookieController 
import geopy.distance
from streamlit_geolocation import streamlit_geolocation

# Option 1: Use double backslashes
LOGO_PATH = "C:\\FichajesMovil\\assets\\logo_penades.webp"



# Coordenadas de la oficina de Almansa, Albacete
OFFICE_COORD = (38.85019, -1.02822)

# =========================
# Cookies / Sesión
# =========================
controller = CookieController()

# =========================
# Utilidades Home (Inicio)
# =========================
def _spanish_date(d: datetime) -> str:
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    return f"Hoy, {d.day} de {meses[d.month-1]}"

def _saludo(hora: int) -> str:
    if 6 <= hora < 13: return "¡Buenos días"
    if 13 <= hora < 20: return "¡Buenas tardes"
    return "¡Buenas noches"

def _leer_notificaciones(usuario: str) -> pd.DataFrame:
    """
    Lee notificaciones desde un CSV sencillo:
    columnas: usuario,titulo,fecha,leido (0/1)
    """
    try:
        df = pd.read_csv("notificaciones.csv")
        if "leido" not in df.columns:
            df["leido"] = 0
        df["leido"] = df["leido"].fillna(0).astype(int)
        return df[df["usuario"] == usuario].copy()
    except FileNotFoundError:
        return pd.DataFrame(columns=["usuario","titulo","fecha","leido"])

def _marcar_todas_leidas(usuario: str):
    try:
        df_all = pd.read_csv("notificaciones.csv")
    except FileNotFoundError:
        return
    if "leido" not in df_all.columns:
        df_all["leido"] = 0
    df_all.loc[df_all["usuario"] == usuario, "leido"] = 1
    df_all.to_csv("notificaciones.csv", index=False)

def render_home(usuario: str):
    # Portada sin navegación lateral automática y con FONDO en degradado
    st.set_page_config(layout="wide", initial_sidebar_state="collapsed")
    st.markdown("""
    <style>
      /* Oculta la navegación automática del sidebar (pero no el sidebar entero) */
      div[data-testid="stSidebarNav"]{ display:none !important; }

      /* Fondo de TODA la app en degradado suave */
      [data-testid="stAppViewContainer"]{
        background: linear-gradient(180deg,#DDF1FA 0%,#FAF7E9 85%) !important;
      }

      /* Badge de notificaciones */
      .notif-badge{
        display:inline-block; background:#E11D48; color:#fff;
        border-radius:999px; font-size:12px; padding:2px 6px; line-height:1;
        margin-left:6px;
      }
    </style>
    """, unsafe_allow_html=True)

    # 1 Cargar notificaciones 
    ahora = datetime.now()
    df_notif = _leer_notificaciones(usuario)
    pendientes = df_notif[df_notif["leido"] == 0]
    n_pend = int(pendientes.shape[0])


    st.image(LOGO_PATH, use_column_width=True, width=420)

    # Saludo y fecha
    st.markdown('<div class="hero">', unsafe_allow_html=True)
    st.markdown(f"<h2 style='margin:0'>{_saludo(ahora.hour)}, {usuario}!</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='font-size:20px;opacity:.8;margin-top:6px'>{_spanish_date(ahora)}</p>", unsafe_allow_html=True)
    bell = st.button("🔔", key="home_bell", help="Ver notificaciones")
    if n_pend > 0:
        st.markdown(f"<div class='badge'>{n_pend}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Lógica de geolocalización para recordatorios (al cargar la página de inicio)
    location = streamlit_geolocation()
    if location and location['latitude'] is not 0 and location['longitude'] is not 0:
        user_coord = (location['latitude'], location['longitude'])
        distance_km = geopy.distance.geodesic(OFFICE_COORD, user_coord).km
        
        # Umbral de 100 metros
        if distance_km <= 0.5:
            st.info("¡Estás cerca de la oficina! Recuerda fichar tu entrada o salida.")

    # Listado de notificaciones
    if bell:
        st.session_state["show_notifs"] = True
    if st.session_state.get("show_notifs", False):
        with st.expander(f"Notificaciones ({n_pend} pendientes)", expanded=True):
            if n_pend == 0:
                st.info("No tienes notificaciones pendientes.")
            else:
                for _, r in pendientes.iterrows():
                    st.markdown(f"**• {r.get('titulo','(sin título)')}** — {r.get('fecha','')}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Marcar todas como leídas"):
                    _marcar_todas_leidas(usuario)
                    st.session_state["show_notifs"] = False
                    st.rerun()
            with c2:
                if st.button("Cerrar"):
                    st.session_state["show_notifs"] = False
                    st.rerun()

    st.markdown("### ")
    # Accesos tipo “barra inferior”
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🗓️ Fichaje", use_container_width=True):
            st.switch_page("pages/paginaFichajeMovil.py")   
    with c2:
        if st.button("🧾 Ausencias", use_container_width=True):
            st.switch_page("pages/paginaAusenciaMovil.py")
    with c3:
        if st.button("🧾 Modificar fechas", use_container_width=True):
            st.switch_page("pages/paginaModFechaMovil.py")     

    


# =========================
# Lógica original (menús/permisos)
# =========================
USUARIOS_CSV = os.path.join(os.path.dirname(__file__), "usuarios.csv")
PAGINAS_CSV = os.path.join(os.path.dirname(__file__), "rol_paginas.csv")

def validarUsuario(usuario, clave):
    """Valida usuario y clave contra usuarios.csv"""
    dfusuarios = pd.read_csv(USUARIOS_CSV)
    ok = len(dfusuarios[(dfusuarios['usuario'] == usuario) & (dfusuarios['clave'] == clave)]) > 0
    return bool(ok)

def generarMenu(usuario):
    """Menú lateral simple con enlaces fijos por rol"""
    with st.sidebar:
        st.image(LOGO_PATH, use_column_width=True)
        dfusuarios = pd.read_csv(USUARIOS_CSV)
        dfUsuario = dfusuarios[(dfusuarios['usuario'] == usuario)]
        nombre = dfUsuario['nombre'].values[0]
        rol = dfUsuario['rol'].values[0]
        st.write(f"Hola **:blue-background[{nombre}]** ")
        st.caption(f"Rol: {rol}")
        #st.page_link("inicio.py", label="Inicio", icon=":material/home:")
        st.subheader("Tableros")
        if rol in ['Fichaje','admin', 'empleado']:
            st.page_link("pages/paginaFichajeMovil.py", label="Fichajes", icon=":material/sell:")
        if rol in ['Ausencia','admin','empleado']:
            st.page_link("pages/paginaAusenciaMovil.py", label="Ausencia", icon=":material/group:")
        if rol in ['Modificación fecha','admin','empleado']:
            st.page_link("pages/paginaModFechaMovil.py", label="Modificaciones de fechas", icon=":material/group:")
        
        btnSalir = st.button("Salir")
        if btnSalir:
            st.session_state.clear()
            controller.remove('usuario')
            st.rerun()

def validarPagina(pagina, usuario):
    """Valida si un usuario tiene permiso a 'pagina' usando rol_paginas.csv o secrets."""
    dfusuarios = pd.read_csv(USUARIOS_CSV)
    dfPaginas = pd.read_csv(PAGINAS_CSV)
    dfUsuario = dfusuarios[(dfusuarios['usuario'] == usuario)]
    rol = dfUsuario['rol'].values[0]
    dfPagina = dfPaginas[(dfPaginas['pagina'].str.contains(pagina))]
    if len(dfPagina) > 0:
        if rol in dfPagina['roles'].values[0] or rol == "admin" or st.secrets.get("tipoPermiso","rol") == "rol":
            return True
        else:
            return False
    else:
        return False

def generarMenuRoles(usuario):
    """Menú lateral según csv de páginas/roles, con opción de ocultar o deshabilitar."""
    with st.sidebar:
        st.image(LOGO_PATH, use_column_width=True)
        dfusuarios = pd.read_csv(USUARIOS_CSV)
        dfPaginas = pd.read_csv(PAGINAS_CSV)
        dfUsuario = dfusuarios[(dfusuarios['usuario'] == usuario)]
        nombre = dfUsuario['nombre'].values[0]
        rol = dfUsuario['rol'].values[0]
        st.write(f"Hola **:blue-background[{nombre}]** ")
        st.caption(f"Rol: {rol}")
        st.subheader("Opciones")

        ocultar = str(st.secrets.get("ocultarOpciones", "False")) == "True"
        if ocultar:
            if rol != 'admin':
                dfPaginas = dfPaginas[dfPaginas['roles'].str.contains(rol)]
            for _, row in dfPaginas.iterrows():
                icono = row['icono']
                st.page_link(row['pagina'], label=row['nombre'], icon=f":material/{icono}:")
        else:
            for _, row in dfPaginas.iterrows():
                deshabilitarOpcion = True
                if (rol in row["roles"]) or rol == "admin":
                    deshabilitarOpcion = False
                icono = row['icono']
                st.page_link(row['pagina'], label=row['nombre'], icon=f":material/{icono}:", disabled=deshabilitarOpcion)

        btnSalir = st.button("Salir")
        if btnSalir:
            st.session_state.clear()
            controller.remove('usuario')
            st.rerun()

# =========================
# Login / Routing
# =========================
def generarLogin(archivo):
    """Monta el login, portada y menús."""
    # Recupera cookie si existe
    usuario = controller.get('usuario')
    if usuario:
        st.session_state['usuario'] = usuario

    if 'usuario' in st.session_state:
        # Portada Inicio limpia con notificaciones
        if archivo.lower() == "inicio.py":
            render_home(st.session_state['usuario'])
        else:
            # Menú lateral (por roles de página o por roles simples)
            if st.secrets.get("tipoPermiso","rol") == "rolpagina":
                generarMenuRoles(st.session_state['usuario'])
            else:
                generarMenu(st.session_state['usuario'])

            # Validación de permisos para la página actual
            if not validarPagina(archivo, st.session_state['usuario']):
                st.error(f"No tiene permisos para acceder a esta página {archivo}", icon=":material/gpp_maybe:")
                st.stop()
    else:
        # Formulario de login
        with st.form('frmLogin'):
            parUsuario = st.text_input('Usuario')
            parPassword = st.text_input('Password', type='password')
            btnLogin = st.form_submit_button('Ingresar', type='primary')
            if btnLogin:
                if validarUsuario(parUsuario, parPassword):
                    st.session_state['usuario'] = parUsuario
                    controller.set('usuario', parUsuario)
                    st.rerun()
                else:
                    st.error("Usuario o clave inválidos", icon=":material/gpp_maybe:")

