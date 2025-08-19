# config.py
import os
import streamlit as st

# Definir BASE_DIR primero
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configuración de secrets.toml
secrets_path = os.path.abspath(os.path.join(BASE_DIR, '.streamlit', 'secrets.toml'))
os.environ['STREAMLIT_SECRETS_FILE'] = secrets_path

def path(*parts):
    return os.path.join(BASE_DIR, *parts)

# Rutas compartidas
USERS_CSV   = path("usuarios.csv")
FICHAJES_DB = path("fichajes.db")
RRHH_DB     = path("rrhh.db")
BAJAS_DIR   = path("bajas_adjuntos")
os.makedirs(BAJAS_DIR, exist_ok=True)
