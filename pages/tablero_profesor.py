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
st.markdown("Visualiza el rendimiento y gestiona el conocimiento de la IA.")

# Contraseña dura para el prototipo
PASSWORD_PROFESOR = "Alternancia2024"

contrasena_ingresada = st.text_input("🔑 Contraseña de acceso:", type="password")

if contrasena_ingresada != PASSWORD_PROFESOR:
    st.warning("Por favor, ingresa la contraseña correcta para acceder al portal docente.")
    st.stop() # Esto detiene la ejecución del resto de la página si no hay contraseña

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
    # Cargamos el modelo en caché para que no se descargue cada vez que guardas una clase
    return SentenceTransformer('all-MiniLM-L6-v2')

supabase = iniciar_conexion()

# ==========================================
# 4. INTERFAZ DE PESTAÑAS (TABS)
# ==========================================
tab_analiticas, tab_cargador = st.tabs(["📊 Analíticas de Estudiantes", "🧠 Enseñar a la IA (Cargar Clase)"])

# ------------------------------------------
# PESTAÑA 1: ANALÍTICAS (El tablero anterior)
# ------------------------------------------
with tab_analiticas:
    with st.spinner("Extrayendo datos de aprendizaje..."):
        # Obtener estudiantes
        res_estudiantes = supabase.table("estudiantes").select("*").execute()
        df_estudiantes = pd.DataFrame(res_estudiantes.data)

        # Obtener historial cruzado con temas (Relación SQL de Supabase)
        res_historial = supabase.table("historial_aprendizaje").select("*, contenido_curricular(tema, subtema)").execute()
        
        if not res_historial.data:
            st.info("Aún no hay interacciones registradas por los estudiantes.")
        else:
            # Procesar los datos relacionales para convertirlos en una tabla fácil de leer (Pandas)
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

            # CÁLCULO DE MÉTRICAS CLAVE (KPIs)
            total_alumnos = len(df_estudiantes)
            total_interacciones = len(df_historial)
            tasa_exito_global = (df_historial["exitoso"].sum() / total_interacciones) * 100

            fallos_por_tema = df_historial[df_historial["exitoso"] == False].groupby("tema").size()
            tema_critico = fallos_por_tema.idxmax() if not fallos_por_tema.empty else "Ninguno, ¡todo perfecto!"

            # DISEÑO DEL DASHBOARD
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
    st.markdown("Usa este formulario para agregar apuntes nuevos. La Inteligencia Artificial los leerá, los convertirá en vectores matemáticos y los memorizará al instante.")

    # Creamos un formulario visual
    with st.form("form_nueva_clase"):
        tema_input = st.text_input("Tema Principal (Ej: Ciencias Naturales, Matemáticas)")
        subtema_input = st.text_input("Subtema (Ej: El Sistema Solar, Ecuaciones Lineales)")
        texto_clase_input = st.text_area("Apuntes Oficiales de la Clase (Escribe toda la teoría aquí)", height=250)
        nivel_input = st.slider("Nivel de dificultad estimado", min_value=1, max_value=5, value=2)
        
        # Botón de envío
        submit_btn = st.form_submit_button("🧠 Guardar Clase en el Cerebro")

        # Lógica cuando el profesor presiona el botón
        if submit_btn:
            if not tema_input or not texto_clase_input:
                st.error("⚠️ El Tema Principal y los Apuntes son campos obligatorios.")
            else:
                with st.spinner("Procesando vectores y subiendo a la base de datos..."):
                    try:
                        # 1. Cargamos el modelo y creamos el vector
                        modelo_vectores = cargar_modelo_vectores()
                        vector_matematico = modelo_vectores.encode(texto_clase_input).tolist()

                        # 2. Preparamos los datos para Supabase
                        data = {
                            "tema": tema_input,
                            "subtema": subtema_input,
                            "contenido_texto": texto_clase_input,
                            "nivel_dificultad": nivel_input,
                            "embedding": vector_matematico
                        }
                        
                        # 3. Guardamos en la nube
                        supabase.table("contenido_curricular").insert(data).execute()
                        st.success(f"✅ ¡Éxito! El tema '{tema_input}: {subtema_input}' ha sido asimilado. Tus alumnos ya pueden preguntar sobre esto en el chat principal.")
                        
                    except Exception as e:
                        st.error(f"❌ Ocurrió un error de conexión: {e}")