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
tab_analiticas, tab_cargador, tab_registro, tab_asignaciones = st.tabs([
    "📊 Analíticas", 
    "🧠 Enseñar a la IA",
    "🧑‍🎓 Matricular",
    "🎯 Asignar Tutorías"
])

# ------------------------------------------
# PESTAÑA 1: ANALÍTICAS
# ------------------------------------------
with tab_analiticas:
    with st.spinner("Extrayendo datos de aprendizaje..."):
        try:
            res_estudiantes = supabase.table("estudiantes").select("*").execute()
            df_estudiantes = pd.DataFrame(res_estudiantes.data)

            # --- TABLA 1: REGISTRO GENERAL ---
            st.subheader("📋 Lista de Estudiantes Matriculados")
            if not df_estudiantes.empty:
                columnas_mostrar = ['nombre', 'correo', 'grado', 'nivel_general']
                df_registro = df_estudiantes[columnas_mostrar].copy()
                df_registro.columns = ['Nombre del Alumno', 'Correo', 'Grado', 'Nivel Base']
                st.dataframe(df_registro, use_container_width=True)
            else:
                st.info("No hay estudiantes matriculados en el sistema.")

            # --- TABLA 2: HISTORIAL DE EVALUACIONES ---
            st.divider()
            st.subheader("📝 Historial de Calificaciones y Entregas")
            st.markdown("Registro de todas las actividades entregadas y evaluadas por la IA.")
            
            try:
                res_eval = supabase.table("evaluaciones").select("*").order("created_at", desc=True).execute()
                
                if not res_eval.data:
                    st.info("Aún no hay actividades entregadas y evaluadas en el historial.")
                else:
                    df_eval = pd.DataFrame(res_eval.data)
                    df_completo = pd.merge(df_eval, df_estudiantes[['id', 'nombre', 'correo', 'grado']], left_on='estudiante_id', right_on='id', how='left')
                    df_completo = df_completo[['nombre', 'correo', 'grado', 'tarea', 'nota', 'feedback', 'created_at']]
                    df_completo['created_at'] = pd.to_datetime(df_completo['created_at']).dt.strftime("%Y-%m-%d %H:%M")
                    
                    df_completo.columns = ['Alumno', 'Correo', 'Grado', 'Actividad Evaluada', 'Nota /100', 'Feedback de la IA', 'Fecha de Entrega']
                    st.dataframe(df_completo, use_container_width=True)
                    
                    csv = df_completo.to_csv(index=False).encode('utf-8')
                    st.download_button(label="⬇️ Descargar Historial en Excel", data=csv, file_name="historial_calificaciones.csv", mime="text/csv", type="primary")
            except Exception as e:
                st.error(f"⚠️ Error cargando historial de notas. Asegúrate de tener la tabla 'evaluaciones'.")
        
        except Exception as e:
            st.error(f"Ocurrió un error general cargando las analíticas: {e}")

# ------------------------------------------
# PESTAÑA 2: CARGADOR DE CLASES
# ------------------------------------------
with tab_cargador:
    st.subheader("📚 Cargar nuevo contenido al Cerebro de la IA")
    with st.form("form_nueva_clase"):
        tema_input = st.text_input("Tema Principal (Ej: Ciencias Naturales)")
        subtema_input = st.text_input("Subtema (Ej: El Sistema Solar)")
        texto_clase_input = st.text_area("Apuntes Oficiales de la Clase", height=200)
        nivel_input = st.slider("Nivel de dificultad", 1, 5, 2)
        if st.form_submit_button("🧠 Guardar Clase"):
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
# PESTAÑA 3: REGISTRO DE ESTUDIANTES
# ------------------------------------------
with tab_registro:
    st.subheader("🧑‍🎓 Matricular Nuevo Estudiante")
    with st.form("form_nuevo_alumno"):
        nombre_nuevo = st.text_input("Nombre Completo")
        correo_nuevo = st.text_input("Correo Institucional")
        grado_nuevo = st.selectbox("Grado del Estudiante", ["6to Grado", "7mo Grado", "8vo Grado", "9no Grado", "10mo Grado", "11vo Grado"])
        nivel_nuevo = st.slider("Nivel académico inicial", 1, 5, 2)
        if st.form_submit_button("✅ Registrar Estudiante"):
            if not nombre_nuevo or not correo_nuevo:
                st.error("⚠️ Obligatorio: Nombre y Correo.")
            else:
                try:
                    validacion = supabase.table("estudiantes").select("id").eq("correo", correo_nuevo.strip().lower()).execute()
                    if validacion.data:
                        st.warning("⚠️ Correo ya registrado.")
                    else:
                        supabase.table("estudiantes").insert({
                            "nombre": nombre_nuevo, "correo": correo_nuevo.strip().lower(), "grado": grado_nuevo, "nivel_general": nivel_nuevo
                        }).execute()
                        st.success(f"🎉 ¡Matriculado con éxito!")
                except Exception as e:
                    st.error(f"❌ Error: {e}")

# ------------------------------------------
# PESTAÑA 4: ASIGNAR TUTORÍAS 
# ------------------------------------------
with tab_asignaciones:
    st.subheader("🎯 Asignar Tutorías por Asignatura")
    st.markdown("Asigna misiones específicas. El alumno verá un panel con sus tutorías separadas por materia.")
    
    res_lista = supabase.table("estudiantes").select("id, nombre").execute()
    df_lista = pd.DataFrame(res_lista.data)
    
    if df_lista.empty:
        st.warning("No hay estudiantes registrados aún.")
    else:
        with st.form("form_asignacion"):
            col1, col2 = st.columns(2)
            with col1:
                estudiante_seleccionado = st.selectbox("1. Selecciona al alumno:", options=df_lista['id'], format_func=lambda x: df_lista[df_lista['id'] == x]['nombre'].values[0])
            with col2:
                asignatura = st.selectbox("2. Área / Asignatura:", ["Biología", "Matemáticas", "Física", "Química", "Lenguaje", "Historia", "Inglés", "Otra"])
            
            nueva_tarea = st.text_area("3. Instrucción o actividad a realizar (Ej: Explicar las partes de la célula):")
            nueva_complejidad = st.radio("4. Nivel de exigencia:", ["Básico", "Intermedio", "Avanzado"], horizontal=True)
            nueva_rubrica = st.text_area("5. Rúbrica de evaluación (Opcional):", placeholder="Ej: Restar puntos si hay mala ortografía.")
            
            col_btn1, col_btn2 = st.columns(2)
            if col_btn1.form_submit_button("🚀 Crear Tutoría"):
                if nueva_tarea:
                    try:
                        supabase.table("tutorias").insert({
                            "estudiante_id": estudiante_seleccionado, "asignatura": asignatura, "mision": nueva_tarea, 
                            "complejidad": nueva_complejidad, "rubrica": nueva_rubrica, "estado": "pendiente"
                        }).execute()
                        st.success(f"✅ Tutoría de {asignatura} creada con éxito. El alumno la verá en su panel.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar. Detalle: {e}")
                else:
                    st.error("Debes escribir una tarea.")
            
            if col_btn2.form_submit_button("🧹 Borrar asignación actual"):
                st.info("Para borrar tutorías, el alumno debe completarlas, o puedes gestionarlas directamente desde Supabase.")
        
        st.divider()
        st.subheader("📋 Tutorías Pendientes Activas")
        
        # --- AQUÍ ESTÁ LA SOLUCIÓN AL ERROR DEL TABLERO ---
        try:
            # Traemos las tutorías pendientes sin el filtro complejo que causaba el error
            res_tutorias = supabase.table("tutorias").select("*").eq("estado", "pendiente").order("created_at", desc=True).execute()
            
            if not res_tutorias.data:
                st.info("No tienes alumnos con tutorías pendientes en este momento.")
            else:
                df_tut = pd.DataFrame(res_tutorias.data)
                
                # Cruzamos los IDs con la lista de alumnos directamente en Python con Pandas
                df_tut = pd.merge(df_tut, df_lista[['id', 'nombre']], left_on='estudiante_id', right_on='id', how='left')
                
                # Dejamos la tabla limpia
                df_tut = df_tut[['nombre', 'asignatura', 'mision', 'complejidad']]
                df_tut.columns = ['Alumno', 'Asignatura', 'Misión Asignada', 'Complejidad']
                
                st.dataframe(df_tut, use_container_width=True)
        except Exception as e:
            st.error(f"Error al cargar las asignaciones pendientes. Detalle técnico: {e}")