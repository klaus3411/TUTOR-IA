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
    "🎯 Asignar Tareas"
])

# ------------------------------------------
# PESTAÑA 1: ANALÍTICAS
# ------------------------------------------
with tab_analiticas:
    with st.spinner("Extrayendo datos de aprendizaje..."):
        try:
            res_estudiantes = supabase.table("estudiantes").select("*").execute()
            df_estudiantes = pd.DataFrame(res_estudiantes.data)

            res_historial = supabase.table("historial_aprendizaje").select("*, contenido_curricular(tema, subtema)").execute()
            
            if not res_historial.data:
                st.info("Aún no hay interacciones registradas por los estudiantes.")
            else:
                datos_planos = []
                for item in res_historial.data:
                    tema = item.get("contenido_curricular", {}).get("tema", "Desconocido") if item.get("contenido_curricular") else "Desconocido"
                    datos_planos.append({
                        "estudiante_id": item["estudiante_id"],
                        "tema": tema,
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
            with col_der:
                st.subheader("👥 Actividad Reciente")
                df_historial["fecha"] = pd.to_datetime(df_historial["fecha"]).dt.date
                actividad_diaria = df_historial.groupby("fecha").size()
                st.line_chart(actividad_diaria)

            # ==========================================
            # TABLA: HISTORIAL COMPLETO DE EVALUACIONES
            # ==========================================
            st.divider()
            st.subheader("📋 Historial de Calificaciones")
            st.markdown("Registro de todas las actividades entregadas y evaluadas por la IA en el tiempo.")
            
            try:
                # 1. Extraer el historial de la nueva tabla
                res_eval = supabase.table("evaluaciones").select("*").order("created_at", desc=True).execute()
                
                if not res_eval.data:
                    st.info("Aún no hay actividades entregadas y evaluadas.")
                else:
                    df_eval = pd.DataFrame(res_eval.data)
                    
                    # 2. Cruzar los datos con los nombres de los estudiantes
                    df_completo = pd.merge(df_eval, df_estudiantes[['id', 'nombre', 'correo', 'grado']], left_on='estudiante_id', right_on='id', how='left')
                    
                    # 3. Limpiar y ordenar las columnas
                    df_completo = df_completo[['nombre', 'correo', 'grado', 'tarea', 'nota', 'feedback', 'created_at']]
                    df_completo['created_at'] = pd.to_datetime(df_completo['created_at']).dt.strftime("%Y-%m-%d %H:%M")
                    
                    # 4. Renombrar para que se vea profesional
                    df_completo.columns = ['Alumno', 'Correo', 'Grado', 'Actividad Evaluada', 'Nota /100', 'Feedback de la IA', 'Fecha de Entrega']
                    
                    # 5. Mostrar la tabla en pantalla
                    st.dataframe(df_completo, use_container_width=True)
                    
                    # 6. Botón de exportación
                    csv = df_completo.to_csv(index=False).encode('utf-8')
                    st.markdown("¿Necesitas pasar estas notas a tu sistema oficial?")
                    st.download_button(
                        label="⬇️ Descargar Historial en Excel (CSV)",
                        data=csv,
                        file_name="historial_calificaciones_ia.csv",
                        mime="text/csv",
                        type="primary" 
                    )
            except Exception as e:
                st.error(f"⚠️ Por favor crea la tabla 'evaluaciones' en Supabase para ver el historial de notas.")

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
        submit_btn = st.form_submit_button("🧠 Guardar Clase")

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
# PESTAÑA 3: REGISTRO DE ESTUDIANTES
# ------------------------------------------
with tab_registro:
    st.subheader("🧑‍🎓 Matricular Nuevo Estudiante")
    with st.form("form_nuevo_alumno"):
        nombre_nuevo = st.text_input("Nombre Completo")
        correo_nuevo = st.text_input("Correo Institucional")
        grado_nuevo = st.selectbox("Grado del Estudiante", ["6to Grado", "7mo Grado", "8vo Grado", "9no Grado", "10mo Grado", "11vo Grado"])
        nivel_nuevo = st.slider("Nivel académico inicial", 1, 5, 2)
        
        btn_registrar = st.form_submit_button("✅ Registrar Estudiante")
        
        if btn_registrar:
            if not nombre_nuevo or not correo_nuevo:
                st.error("⚠️ El nombre y el correo son obligatorios.")
            else:
                correo_limpio = correo_nuevo.strip().lower()
                with st.spinner("Registrando..."):
                    try:
                        validacion = supabase.table("estudiantes").select("id").eq("correo", correo_limpio).execute()
                        if validacion.data:
                            st.warning("⚠️ Este correo ya está registrado.")
                        else:
                            supabase.table("estudiantes").insert({
                                "nombre": nombre_nuevo,
                                "correo": correo_limpio,
                                "grado": grado_nuevo,
                                "nivel_general": nivel_nuevo
                            }).execute()
                            st.success(f"🎉 ¡{nombre_nuevo} matriculado con éxito!")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

# ------------------------------------------
# PESTAÑA 4: ASIGNAR TAREAS
# ------------------------------------------
with tab_asignaciones:
    st.subheader("🎯 Asignar Actividades y Complejidad")
    
    res_lista = supabase.table("estudiantes").select("id, nombre, asignacion_actual, complejidad_asignacion").execute()
    df_lista = pd.DataFrame(res_lista.data)
    
    if df_lista.empty:
        st.warning("No hay estudiantes registrados aún.")
    else:
        estudiante_seleccionado = st.selectbox(
            "Selecciona al alumno:", 
            options=df_lista['id'], 
            format_func=lambda x: df_lista[df_lista['id'] == x]['nombre'].values[0]
        )
        
        datos_estudiante = df_lista[df_lista['id'] == estudiante_seleccionado].iloc[0]
        tarea_previa = datos_estudiante['asignacion_actual'] if datos_estudiante['asignacion_actual'] else "Ninguna actividad asignada"
        
        st.caption(f"📌 Tarea actual: {tarea_previa}")
        
        with st.form("form_asignacion"):
            nueva_tarea = st.text_area("Instrucción o actividad a realizar:")
            nueva_complejidad = st.radio("Nivel de exigencia:", ["Básico", "Intermedio", "Avanzado"], horizontal=True)
            # ! NUEVO: Rúbrica personalizable por el docente al momento de asignar
            nueva_rubrica = st.text_area("Rúbrica de evaluación (Opcional):", placeholder="Ej: Quita 10 puntos si tiene mala ortografía. Debe mencionar las 3 partes de la célula.")
            
            col1, col2 = st.columns(2)
            btn_asignar = col1.form_submit_button("🚀 Asignar a la IA")
            btn_limpiar = col2.form_submit_button("🧹 Borrar asignación actual")
            
            if btn_asignar:
                if nueva_tarea:
                    datos_update = {
                        "asignacion_actual": nueva_tarea,
                        "complejidad_asignacion": nueva_complejidad
                    }
                    if nueva_rubrica:
                        datos_update["rubrica_evaluacion"] = nueva_rubrica
                        
                    supabase.table("estudiantes").update(datos_update).eq("id", estudiante_seleccionado).execute()
                    st.success("✅ Actividad y rúbrica asignadas con éxito.")
                    st.rerun()
                else:
                    st.error("Debes escribir una tarea.")
                    
            if btn_limpiar:
                supabase.table("estudiantes").update({
                    "asignacion_actual": None,
                    "complejidad_asignacion": None,
                    "rubrica_evaluacion": None,
                    "ultima_nota": None,
                    "ultimo_feedback": None
                }).eq("id", estudiante_seleccionado).execute()
                st.success("✅ Asignación y notas borradas. La IA volverá a modo libre.")
                st.rerun()