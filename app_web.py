import streamlit as st
import os
import json  # ¡ESTA ES LA LÍNEA QUE SOLUCIONA TU ERROR!
from dotenv import load_dotenv
from supabase import create_client, Client
from groq import Groq
from sentence_transformers import SentenceTransformer
import streamlit.components.v1 as components

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA WEB
# ==========================================
st.set_page_config(page_title="Portal Educativo - Alternancia", page_icon="🏫", layout="centered")

# --- VARIABLE DE BRANDING (Pon aquí el link de tu logo) ---
URL_LOGO_COLEGIO = "https://scontent.fctg2-1.fna.fbcdn.net/v/t39.30808-6/377432631_785816130218699_8439928282516365142_n.jpg?stp=dst-jpg_tt6&cstp=mx1080x1080&ctp=s1080x1080&_nc_cat=111&ccb=1-7&_nc_sid=6ee11a&_nc_ohc=QkM_KdoM6-8Q7kNvwHZLafy&_nc_oc=Ado8PMT8UfZ5Na3A5PElaVATxsfC2uGumMesGdurEkH6giRzWqSz1reFRnxInqrbSwo&_nc_zt=23&_nc_ht=scontent.fctg2-1.fna&_nc_gid=8GpDrRfgp9dp29bAVZcYkg&_nc_ss=7b289&oh=00_AQA17yO0TLEY20eEhXYhcluOHLBzxi2TEmATg-_PeChiTg&oe=6A544484" 


# ==========================================
# 1.5 INYECCIÓN PWA (App Instalable)
# ==========================================
components.html("""
<script>
    try {
        const parentDoc = window.parent.document;
        const parentWin = window.parent;
        const manifest = {
            "name": "Portal Educativo IA", "short_name": "Portal IA", "theme_color": "#1E3A8A", "background_color": "#F3F4F6",
            "display": "standalone", "orientation": "portrait", "scope": "/", "start_url": "/",
            "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/167/167707.png", "sizes": "512x512", "type": "image/png"}]
        };
        const blob = new Blob([JSON.stringify(manifest)], {type: 'application/json'});
        const manifestURL = URL.createObjectURL(blob);
        const oldLink = parentDoc.querySelector('link[rel="manifest"]');
        if(oldLink) oldLink.remove();
        parentDoc.head.insertAdjacentHTML('beforeend', `<link rel="manifest" href="${manifestURL}">`);
    } catch (e) {}
</script>
""", height=0)

# ==========================================
# 2. CARGA DE SISTEMAS EN MEMORIA
# ==========================================
@st.cache_resource
def iniciar_sistemas():
    load_dotenv()
    supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    cliente_groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    modelo_vectores = SentenceTransformer('all-MiniLM-L6-v2')
    return supabase, cliente_groq, modelo_vectores

supabase, cliente_groq, modelo_vectores = iniciar_sistemas()

# ==========================================
# 3. FUNCIONES DEL TUTOR Y EVALUADOR
# ==========================================
def obtener_perfil(correo):
    respuesta = supabase.table("estudiantes").select("*").eq("correo", correo).execute()
    return respuesta.data[0] if respuesta.data else None

def evaluar_actividad(tutoria, historial_chat):
    """Motor de evaluación objetivo usando los datos de la tutoría específica."""
    rubrica = tutoria.get('rubrica') or 'Evalúa de forma estricta del 0 al 100 qué tanto entendió el estudiante el tema. Revisa su esfuerzo y precisión.'
    tarea_asignada = tutoria['mision']
    
    prompt_evaluador = f"""
    Eres un profesor de {tutoria['asignatura']}. Tu tarea es EVALUAR la interacción.
    TAREA ASIGNADA: {tarea_asignada}
    RÚBRICA: {rubrica}
    
    HISTORIAL DE LA CONVERSACIÓN:
    {historial_chat}
    
    Genera tu respuesta ÚNICAMENTE en JSON con este formato exacto:
    {{
        "nota": <número 0 al 100>,
        "feedback": "<Retroalimentación principal>",
        "puntos_fuertes": "<Qué hizo bien>",
        "areas_mejora": "<En qué debe mejorar>"
    }}
    """
    
    respuesta = cliente_groq.chat.completions.create(
        messages=[{"role": "user", "content": prompt_evaluador}],
        model="llama-3.1-8b-instant",
        response_format={"type": "json_object"},
        temperature=0.1 
    )
    return respuesta.choices[0].message.content

def generar_respuesta(perfil, tutoria, pregunta, historial_chat):
    vector_pregunta = modelo_vectores.encode(pregunta).tolist()
    resultados = supabase.rpc("match_contenido_curricular", {
        "query_embedding": vector_pregunta, "match_threshold": 0.3, "match_count": 1 
    }).execute()

    texto_oficial = "No hay apuntes específicos en la base de datos para esta pregunta."
    if resultados.data:
        texto_oficial = resultados.data[0]["contenido_texto"]

    grado = perfil.get('grado', 'un grado escolar')
    
    instrucciones = f"""Eres un tutor pedagógico de {tutoria['asignatura']}, excepcionalmente amable. 
    El estudiante está en: {grado}. Usa el método socrático y guíalo a resolver su tarea.
    
    REGLAS ESTRICTAS:
    1. Escribe ÚNICAMENTE tu próximo turno. NUNCA asumas la respuesta del alumno.
    2. Haz UNA SOLA pregunta a la vez.
    
    MISIÓN DEL ALUMNO: {tutoria['mision']}
    COMPLEJIDAD: {tutoria['complejidad']}
    """

    mensajes_api = [{"role": "system", "content": f"{instrucciones}\n\nINFO OFICIAL:\n{texto_oficial}"}]
    
    for msg in historial_chat[-8:]:
        mensajes_api.append({"role": msg["role"], "content": msg["content"]})

    respuesta_ia = cliente_groq.chat.completions.create(
        messages=mensajes_api,
        model="llama-3.1-8b-instant",
        temperature=0.7
    )
    return respuesta_ia.choices[0].message.content

# ==========================================
# 4. INTERFAZ GRÁFICA (UI)
# ==========================================
st.title("🏫 Portal Educativo")
st.markdown("<p style='font-size: 1.1rem; color: #4B5563;'>Tus tutorías personalizadas por asignatura.</p>", unsafe_allow_html=True)
st.divider()

with st.sidebar:
    st.image(URL_LOGO_COLEGIO, width=120) 
    
    # --- RESTAURAMOS EL TÍTULO CORRECTO ---
    st.header("Identificación Estudiantil")
    correo_input = st.text_input("Ingresa tu correo institucional:")
    
    if correo_input:
        perfil = obtener_perfil(correo_input)
        if perfil:
            st.session_state['usuario_valido'] = True
            st.session_state['perfil'] = perfil
            st.markdown(f"### 👋 Hola, {perfil['nombre']}")
            st.metric("Grado", perfil.get('grado', 'No asignado'))
        else:
            st.error("Correo no encontrado.")
            st.session_state['usuario_valido'] = False
            
    # --- BOTÓN DISCRETO PARA EL PROFESOR ---
    st.divider()
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'><a href='/tablero_profesor' target='_self' style='color: #9CA3AF; text-decoration: none; font-size: 0.8rem;'>👨‍🏫 Acceso Docente</a></p>", unsafe_allow_html=True)

# ==========================================
# ÁREA PRINCIPAL: PANEL DE TUTORÍAS Y CHAT
# ==========================================
if st.session_state.get('usuario_valido', False):
    perfil_actual = st.session_state['perfil']
    
    # Si el alumno NO ha seleccionado una tutoría, mostramos su PANEL DE MISIONES
    if 'tutoria_activa' not in st.session_state:
        st.subheader("📚 Tus Tutorías Pendientes")
        
        try:
            res_tutorias = supabase.table("tutorias").select("*").eq("estudiante_id", perfil_actual['id']).eq("estado", "pendiente").execute()
            tutorias_pendientes = res_tutorias.data
            
            if not tutorias_pendientes:
                st.success("¡Felicidades! No tienes tutorías pendientes en este momento. Eres libre. 🎉")
            else:
                st.markdown("Selecciona la asignatura con la que deseas trabajar hoy:")
                
                # Crear "Tarjetas" visuales para cada tutoría
                for tutoria in tutorias_pendientes:
                    with st.container():
                        st.markdown(f"""
                        <div style="background-color: #f3f4f6; padding: 20px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid #4F46E5;">
                            <h3 style="margin-top: 0;">📘 {tutoria['asignatura']}</h3>
                            <p><b>Misión:</b> {tutoria['mision']}</p>
                            <p><small><i>Nivel: {tutoria['complejidad']}</i></small></p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"Entrar a tutoría de {tutoria['asignatura']}", key=tutoria['id'], type="primary"):
                            st.session_state['tutoria_activa'] = tutoria
                            st.session_state['mensajes'] = [{"role": "assistant", "content": f"¡Hola! Soy tu tutor especializado en **{tutoria['asignatura']}**. Hoy tenemos la siguiente misión: *{tutoria['mision']}*. ¿Estás listo para empezar?"}]
                            st.rerun()
        except Exception as e:
            st.error("Error al cargar las tutorías. Pide al profesor que verifique la plataforma.")
            
    # Si el alumno YA SELECCIONÓ una tutoría, mostramos el CHAT EXCLUSIVO
    else:
        tutoria_actual = st.session_state['tutoria_activa']
        
        # Botón para regresar al panel
        if st.button("⬅️ Volver a mis tutorías", use_container_width=False):
            del st.session_state['tutoria_activa']
            if 'resultado_evaluacion' in st.session_state:
                del st.session_state['resultado_evaluacion']
            st.rerun()
            
        st.success(f"🎯 **Asignatura:** {tutoria_actual['asignatura']} | **Misión:** {tutoria_actual['mision']}")

        # Si aún no ha sido evaluado, mostramos el chat
        if 'resultado_evaluacion' not in st.session_state:
            for mensaje in st.session_state.mensajes:
                avatar_icon = "🧑‍🎓" if mensaje["role"] == "user" else URL_LOGO_COLEGIO
                with st.chat_message(mensaje["role"], avatar=avatar_icon):
                    st.markdown(mensaje["content"])

            if pregunta := st.chat_input("Escribe tu mensaje..."):
                with st.chat_message("user", avatar="🧑‍🎓"):
                    st.markdown(pregunta)
                st.session_state.mensajes.append({"role": "user", "content": pregunta})

                with st.chat_message("assistant", avatar=URL_LOGO_COLEGIO):
                    with st.spinner("Escribiendo..."):
                        respuesta = generar_respuesta(perfil_actual, tutoria_actual, pregunta, st.session_state.mensajes)
                        st.markdown(respuesta)
                
                st.session_state.mensajes.append({"role": "assistant", "content": respuesta})
                st.rerun() 

            st.divider()
            if st.button("📤 Entregar Actividad para Evaluar", type="primary", use_container_width=True):
                historial_texto = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.mensajes])
                
                with st.spinner("🧑‍🏫 Evaluando desempeño de manera objetiva..."):
                    try:
                        resultado_json_str = evaluar_actividad(tutoria_actual, historial_texto)
                        datos_evaluacion = json.loads(resultado_json_str) 
                        
                        # 1. Guardar en el historial de evaluaciones
                        supabase.table("evaluaciones").insert({
                            "estudiante_id": perfil_actual['id'],
                            "tarea": tutoria_actual['mision'],
                            "nota": datos_evaluacion['nota'],
                            "feedback": datos_evaluacion['feedback']
                        }).execute()
                        
                        # 2. Marcar la tutoría como completada
                        supabase.table("tutorias").update({"estado": "completada"}).eq("id", tutoria_actual['id']).execute()
                        
                        st.session_state['resultado_evaluacion'] = datos_evaluacion
                        st.rerun()
                    except Exception as e:
                        st.error(f"Hubo un error al generar la evaluación: {e}")
        
        # Mostrar el reporte si ya se evaluó
        else:
            datos = st.session_state['resultado_evaluacion']
            st.markdown("### 📊 Actividad Completada y Evaluada")
            
            color_nota = "green" if datos['nota'] >= 60 else "red"
            st.markdown(f"<h1 style='text-align: center; color: {color_nota}; font-size: 4rem;'>{datos['nota']}/100</h1>", unsafe_allow_html=True)
            
            st.info(f"**🗣️ Comentario:**\n{datos['feedback']}")
            col_buenas, col_mejoras = st.columns(2)
            with col_buenas:
                st.success(f"**✅ Puntos Fuertes:**\n{datos['puntos_fuertes']}")
            with col_mejoras:
                st.warning(f"**📈 Áreas de Mejora:**\n{datos['areas_mejora']}")
            
            if st.button("Regresar al Panel Principal", type="primary"):
                del st.session_state['tutoria_activa']
                del st.session_state['resultado_evaluacion']
                st.rerun()

else:
    st.markdown("""
    <div class="info-card" style="padding: 20px; background-color: #f3f4f6; border-radius: 10px; margin-top: 20px;">
        <h4>🔒 Portal de Acceso Restringido</h4>
        <p>Por favor, usa el <b>panel izquierdo</b> para ingresar tu correo y descubrir tus misiones pendientes.</p>
    </div>
    """, unsafe_allow_html=True)