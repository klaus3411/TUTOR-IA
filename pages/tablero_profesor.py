import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(page_title="Tablero del Profesor", page_icon="👨‍🏫", layout="wide")

# ==========================================
# 2. SISTEMA DE SEGURIDAD (Solo Profesores)
# ==========================================
st.title("👨‍🏫 Tablero Analítico del Profesor")
st.markdown("Visualiza el rendimiento, gestiona el conocimiento de la IA y administra a tus alumnos.")

# Contraseña dura para el prototipo
PASSWORD_PROFESOR = "Alternancia2024"

contrasena_ingresada = st.text_input("🔑 Contraseña de acceso:", type="password")

if contrasena_ingresada != PASSWORD_PROFESOR:
    st.warning("Por favor, ingresa la contraseña correcta para acceder al portal docente.")
    st.stop() 

st.success("Acceso concedido.")
st.divider()

# ==========================================
# 3. CONEXIÓN A BD Y CARGA DE MODELO
# ==========================================
@st.cache_resource
def iniciar_conexion():
    load_dotenv()
    return create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

@st.cache_resource
def cargar_modelo_vectores():
    return SentenceTransformer('all-MiniLM-L6-v2')

supabase = iniciar_conexion()

# ==========================================
# 4. INTERFAZ DE PESTAÑAS (TABS)
# ==========================================
# ¡NUEVO! Agregamos una tercera pestaña para el registro de estudiantes
tab_analiticas, tab_cargador, tab_registro = st.tabs([
    "📊 Analíticas de Estudiantes", 
    "🧠 Enseñar a la IA (Cargar Clase)",
    "🧑‍🎓 Registrar Estudiantes"
])

# ------------------------------------------
# PESTAÑA 1: ANALÍTICAS
# ------------------------------------------
with tab_analiticas:
    with st.spinner("Extrayendo datos de aprendizaje..."):
        res_estudiantes = supabase.table("estudiantes").select("*").execute()
        df_estudiantes = pd.DataFrame(res_estudiantes.data)

        res_historial = supabase.table("historial_aprendizaje").select("*, contenido_curricular(tema, subtema)").execute()
        
        if not res_historial.data:
            st.info("Aún no hay interacciones registradas por los estudiantes.")
        else:
            datos_planos = []
            for item in res_historial.data:
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

            total_alumnos = len(df_estudiantes)
            total_interacciones = len(df_historial)
            tasa_exito_global = (df_historial["exitoso"].sum() / total_interacciones) * 100 if total_interacciones > 0 else 0

            fallos_por_tema = df_historial[df_historial["exitoso"] == False].groupby("tema").size()
            tema_critico = fallos_por_tema.idxmax() if not fallos_por_tema.empty else "Ninguno, ¡todo perfecto!"

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Alumnos", total_alumnos)
            col2.metric("Interacciones IA", total_interacciones)
            col3.metric("Tasa de Éxito", f"{tasa_exito_global:.1f}%")
            col4.metric("🚨 Repasar en Clase", tema_critico)

            st.divider()

            col_izq, col_der = st.columns(2)

            with col_izq:
                st.subheader("📊 Rendimiento por Tema")
                exito_tema = df_historial.groupby("tema")["exitoso"].mean() * 100
                st.bar_chart(exito_tema)

            with col_der:
                st.subheader("👥 Actividad Reciente")
                df_historial["fecha"] = pd.to_datetime(df_historial["fecha"]).dt.date
                actividad_diaria = df_historial.groupby("fecha").size()
                st.line_chart(actividad_diaria)

            st.subheader("📋 Lista de Estudiantes")
            st.dataframe(df_estudiantes[["nombre", "correo", "nivel_general"]], use_container_width=True)

# ------------------------------------------
# PESTAÑA 2: CARGADOR DE CLASES
# ------------------------------------------
with tab_cargador:
    st.subheader("📚 Cargar nuevo contenido al Cerebro de la IA")
    with st.form("form_nueva_clase"):
        tema_input = st.text_input("Tema Principal (Ej: Ciencias Naturales)")
        subtema_input = st.text_input("Subtema (Ej: El Sistema Solar)")
        texto_clase_input = st.text_area("Apuntes Oficiales de la Clase", height=200)
        nivel_input = st.slider("Nivel de dificultad estimado", 1, 5, 2)
        submit_btn = st.form_submit_button("🧠 Guardar Clase en el Cerebro")

        if submit_btn:
            if not tema_input or not texto_clase_input:
                st.error("⚠️ Tema y Apuntes son obligatorios.")
            else:
                with st.spinner("Procesando vectores..."):
                    try:
                        modelo_vectores = cargar_modelo_vectores()
                        vector_matematico = modelo_vectores.encode(texto_clase_input).tolist()
                        supabase.table("contenido_curricular").insert({
                            "tema": tema_input, "subtema": subtema_input,
                            "contenido_texto": texto_clase_input, "nivel_dificultad": nivel_input,
                            "embedding": vector_matematico
                        }).execute()
                        st.success("✅ Clase asimilada correctamente.")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

# ------------------------------------------
# PESTAÑA 3: REGISTRO DE ESTUDIANTES (NUEVA)
# ------------------------------------------
with tab_registro:
    st.subheader("🧑‍🎓 Matricular Nuevo Estudiante")
    st.markdown("Agrega a tus alumnos aquí para que puedan iniciar sesión en el portal.")
    
    with st.form("form_nuevo_alumno"):
        nombre_nuevo = st.text_input("Nombre Completo (Ej: Ana Gómez)")
        # .strip().lower() se usará luego para asegurar que no haya espacios por error
        correo_nuevo = st.text_input("Correo Institucional (Ej: ana.gomez@colegio.edu.co)")
        nivel_nuevo = st.slider("Nivel académico inicial (1 = Básico, 5 = Avanzado)", 1, 5, 2)
        
        btn_registrar = st.form_submit_button("✅ Registrar Estudiante")
        
        if btn_registrar:
            if not nombre_nuevo or not correo_nuevo:
                st.error("⚠️ El nombre y el correo son obligatorios.")
            else:
                correo_limpio = correo_nuevo.strip().lower()
                with st.spinner("Registrando en la base de datos..."):
                    try:
                        # 1. Verificar si el correo ya existe para no duplicar
                        validacion = supabase.table("estudiantes").select("id").eq("correo", correo_limpio).execute()
                        if validacion.data:
                            st.warning(f"⚠️ El correo {correo_limpio} ya está registrado.")
                        else:
                            # 2. Insertar el nuevo estudiante
                            supabase.table("estudiantes").insert({
                                "nombre": nombre_nuevo,
                                "correo": correo_limpio,
                                "nivel_general": nivel_nuevo
                            }).execute()
                            st.success(f"🎉 ¡{nombre_nuevo} matriculado con éxito! Ya puede iniciar sesión con el correo {correo_limpio}.")
                    except Exception as e:
                        st.error(f"❌ Ocurrió un error al conectar con la base de datos: {e}")