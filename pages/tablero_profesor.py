import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(page_title="Tablero del Profesor", page_icon="👨‍🏫", layout="wide")

# ==========================================
# 2. SISTEMA DE SEGURIDAD (Solo Profesores)
# ==========================================
st.title("👨‍🏫 Tablero Analítico del Profesor")
st.markdown("Visualiza el rendimiento de tus estudiantes para preparar tus clases presenciales.")

# Contraseña dura para el prototipo
PASSWORD_PROFESOR = "Alternancia2024"

contrasena_ingresada = st.text_input("🔑 Contraseña de acceso:", type="password")

if contrasena_ingresada != PASSWORD_PROFESOR:
    st.warning("Por favor, ingresa la contraseña correcta para acceder a las analíticas.")
    st.stop() # Esto detiene la ejecución del resto de la página si no hay contraseña

st.success("Acceso concedido.")
st.divider()

# ==========================================
# 3. CONEXIÓN A LA BASE DE DATOS
# ==========================================
@st.cache_resource
def iniciar_conexion():
    load_dotenv()
    return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

supabase = iniciar_conexion()

# ==========================================
# 4. EXTRACCIÓN Y PROCESAMIENTO DE DATOS
# ==========================================
with st.spinner("Extrayendo datos de aprendizaje..."):
    # Obtener estudiantes
    res_estudiantes = supabase.table("estudiantes").select("*").execute()
    df_estudiantes = pd.DataFrame(res_estudiantes.data)

    # Obtener historial cruzado con temas (Relación SQL de Supabase)
    res_historial = supabase.table("historial_aprendizaje").select("*, contenido_curricular(tema, subtema)").execute()
    
    if not res_historial.data:
        st.info("Aún no hay interacciones registradas por los estudiantes.")
        st.stop()

    # Procesar los datos relacionales para convertirlos en una tabla fácil de leer (Pandas)
    datos_planos = []
    for item in res_historial.data:
        # Extraemos el tema y subtema que vienen anidados desde Supabase
        tema = item.get("contenido_curricular", {}).get("tema", "Desconocido") if item.get("contenido_curricular") else "Desconocido"
        subtema = item.get("contenido_curricular", {}).get("subtema", "Desconocido") if item.get("contenido_curricular") else "Desconocido"
        
        datos_planos.append({
            "estudiante_id": item["estudiante_id"],
            "tema": tema,
            "subtema": subtema,
            "exitoso": item["fue_exitoso"],
            "fecha": item["fecha_interaccion"]
        })
    
    df_historial = pd.DataFrame(datos_planos)

# ==========================================
# 5. CÁLCULO DE MÉTRICAS CLAVE (KPIs)
# ==========================================
total_alumnos = len(df_estudiantes)
total_interacciones = len(df_historial)
tasa_exito_global = (df_historial["exitoso"].sum() / total_interacciones) * 100

# Encontrar el tema con más fallos (Para repasarlo en clase)
fallos_por_tema = df_historial[df_historial["exitoso"] == False].groupby("tema").size()
tema_critico = fallos_por_tema.idxmax() if not fallos_por_tema.empty else "Ninguno, ¡todo perfecto!"

# ==========================================
# 6. DISEÑO DEL DASHBOARD (Gráficas)
# ==========================================
# Fila 1: Tarjetas de resumen
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Alumnos", total_alumnos)
col2.metric("Interacciones con IA", total_interacciones)
col3.metric("Tasa de Éxito Global", f"{tasa_exito_global:.1f}%")
col4.metric("🚨 Tema a Repasar (Presencial)", tema_critico)

st.divider()

# Fila 2: Gráficas detalladas
col_izq, col_der = st.columns(2)

with col_izq:
    st.subheader("📊 Rendimiento por Tema")
    st.markdown("¿En qué temas están fallando más?")
    # Agrupamos por tema y calculamos el porcentaje de éxito
    exito_tema = df_historial.groupby("tema")["exitoso"].mean() * 100
    st.bar_chart(exito_tema)

with col_der:
    st.subheader("👥 Actividad Reciente")
    st.markdown("Interacciones de los alumnos en el tiempo")
    # Convertimos la fecha y agrupamos por día
    df_historial["fecha"] = pd.to_datetime(df_historial["fecha"]).dt.date
    actividad_diaria = df_historial.groupby("fecha").size()
    st.line_chart(actividad_diaria)

# Fila 3: Tabla detallada de estudiantes
st.subheader("📋 Lista de Estudiantes y Niveles")
st.dataframe(df_estudiantes[["nombre", "correo", "nivel_general"]], use_container_width=True)