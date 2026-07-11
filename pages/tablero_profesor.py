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

            st.subheader("📋 Lista de Estudiantes Matriculados")
            if not df_estudiantes.empty:
                columnas_mostrar = ['nombre', 'correo', 'grado', 'nivel_general']
                df_registro = df_estudiantes[columnas_mostrar].copy()
                df_registro.columns = ['Nombre del Alumno', 'Correo', 'Grado', 'Nivel Base']
                st.dataframe(df_registro, use_container_width=True)
            else:
                st.info("No hay estudiantes matriculados en el sistema.")

            st.divider()
            st.subheader("📝 Historial de Calificaciones y Entregas")
            st.markdown("Registro general de todas las actividades entregadas y evaluadas por la IA.")
            
            try:
                res_eval = supabase.table("evaluaciones").select("*").order("created_at", desc=True).execute()
                
                if not res_eval.data:
                    st.info("Aún no hay actividades entregadas y evaluadas en el historial.")
                else:
                    df_eval = pd.DataFrame(res_eval.data)
                    df_completo = pd.merge(df_eval, df_estudiantes[['id', 'nombre', 'correo', 'grado']], left_on='estudiante_id', right_on='id', how='left')
                    df_completo_mostrar = df_completo[['nombre', 'correo', 'grado', 'tarea', 'nota', 'feedback', 'created_at']].copy()
                    df_completo_mostrar['created_at'] = pd.to_datetime(df_completo_mostrar['created_at']).dt.strftime("%Y-%m-%d %H:%M")
                    
                    df_completo_mostrar.columns = ['Alumno', 'Correo', 'Grado', 'Actividad Evaluada', 'Nota /100', 'Feedback de la IA', 'Fecha de Entrega']
                    st.dataframe(df_completo_mostrar, use_container_width=True)
                    
                    csv = df_completo_mostrar.to_csv(index=False).encode('utf-8')
                    st.download_button(label="⬇️ Descargar Historial en Excel", data=csv, file_name="historial_calificaciones.csv", mime="text/csv", type="primary")

                    st.divider()
                    st.subheader("🔍 Auditoría Detallada de Entregas")
                    st.markdown("Revisa la evidencia de los alumnos o **elimina los registros de prueba**.")
                    
                    for item in res_eval.data:
                        nombre_al = df_estudiantes[df_estudiantes['id'] == item['estudiante_id']]['nombre'].values[0] if not df_estudiantes[df_estudiantes['id'] == item['estudiante_id']].empty else "Alumno Desconocido"
                        
                        with st.expander(f"📚 {nombre_al} | {item['tarea']} | Nota: {item['nota']}/100"):
                            st.write(f"**🗣️ Feedback de la IA:** {item['feedback']}")
                            st.markdown("**📂 Evidencia del Estudiante (Conversación y Archivos):**")
                            st.code(item.get('historial_evidencia', 'No hay evidencia guardada.'), language="json")
                            
                            col_vacia, col_borrar = st.columns([4, 1])
                            with col_borrar:
                                if st.button("🗑️ Eliminar registro", key=f"del_{item['id']}"):
                                    try:
                                        supabase.table("evaluaciones").delete().eq("id", item['id']).execute()
                                        st.success("¡Registro eliminado con éxito!")
                                        st.rerun() 
                                    except Exception as e:
                                        st.error(f"Error al eliminar: {e}")

            except Exception as e:
                st.error(f"⚠️ Error cargando historial de notas. Detalle: {e}")
        
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
    st.subheader("🎯 Panel de Control de Tutorías")
    st.markdown("Selecciona un alumno para ver sus tareas pendientes y asignarle nuevas misiones.")
    
    res_lista = supabase.table("estudiantes").select("id, nombre").execute()
    df_lista = pd.DataFrame(res_lista.data)
    
    if df_lista.empty:
        st.warning("No hay estudiantes registrados aún.")
    else:
        estudiante_seleccionado = st.selectbox(
            "👤 Selecciona al alumno:", 
            options=df_lista['id'], 
            format_func=lambda x: df_lista[df_lista['id'] == x]['nombre'].values[0]
        )
        
        nombre_estudiante = df_lista[df_lista['id'] == estudiante_seleccionado]['nombre'].values[0]
        st.divider()
        
        col_form, col_pendientes = st.columns([1, 1], gap="large")
        
        with col_form:
            st.markdown(f"### 🚀 Nueva Misión para {nombre_estudiante}")
            with st.form("form_asignacion"):
                asignatura = st.selectbox("Área / Asignatura:", ["Biología", "Matemáticas", "Física", "Química", "Lenguaje", "Historia", "Inglés", "Otra"])
                nueva_tarea = st.text_area("Instrucción o actividad (Ej: Explicar las partes de la célula):")
                nueva_complejidad = st.radio("Nivel de exigencia:", ["Básico", "Intermedio", "Avanzado"], horizontal=True)
                nueva_rubrica = st.text_area("Rúbrica de evaluación (Opcional):", placeholder="Ej: Restar puntos si hay mala ortografía.")
                
                # --- NUEVO: INTERRUPTOR DE MODO VOZ ---
                nueva_voz = st.checkbox("🎙️ Activar charla por Voz (La IA hablará en voz alta sus respuestas)")
                
                if st.form_submit_button("✅ Crear y Asignar Tutoría", type="primary"):
                    if nueva_tarea:
                        try:
                            # Añadimos "modo_voz" a la base de datos
                            supabase.table("tutorias").insert({
                                "estudiante_id": estudiante_seleccionado, 
                                "asignatura": asignatura, 
                                "mision": nueva_tarea, 
                                "complejidad": nueva_complejidad, 
                                "rubrica": nueva_rubrica, 
                                "estado": "pendiente",
                                "modo_voz": nueva_voz 
                            }).execute()
                            st.success(f"Tutoría de {asignatura} creada con éxito.")
                            st.rerun() 
                        except Exception as e:
                            st.error(f"Error al guardar. Asegúrate de haber creado la columna 'modo_voz' (boolean) en Supabase. Detalle: {e}")
                    else:
                        st.error("Debes escribir una tarea.")
        
        with col_pendientes:
            st.markdown(f"### 📋 Misiones Pendientes")
            try:
                res_tutorias = supabase.table("tutorias").select("*").eq("estudiante_id", estudiante_seleccionado).eq("estado", "pendiente").order("created_at", desc=True).execute()
                
                if not res_tutorias.data:
                    st.info(f"¡Excelente! **{nombre_estudiante}** está al día y no tiene tutorías pendientes.")
                else:
                    df_tut = pd.DataFrame(res_tutorias.data)
                    
                    # Añadimos un indicador visual si la misión es por voz
                    df_tut['Tipo'] = df_tut.get('modo_voz', pd.Series([False]*len(df_tut))).apply(lambda x: "🎙️ Voz" if x else "✍️ Texto")
                    
                    df_tut = df_tut[['asignatura', 'mision', 'Tipo']]
                    df_tut.columns = ['Asignatura', 'Misión Asignada', 'Modalidad']
                    st.dataframe(df_tut, use_container_width=True, hide_index=True)
                    st.caption(f"Total pendientes: {len(df_tut)}")
            except Exception as e:
                st.error(f"Error al cargar las asignaciones pendientes. Detalle: {e}")