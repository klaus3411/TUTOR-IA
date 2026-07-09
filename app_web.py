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
            "name": "Portal Educativo IA",
            "short_name": "Portal IA",
            "theme_color": "#1E3A8A",
            "background_color": "#F3F4F6",
            "display": "standalone",
            "orientation": "portrait",
            "scope": "/",
            "start_url": "/",
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
    if not respuesta.data:
        return None, 0
    
    perfil = respuesta.data[0]
    res_historial = supabase.table("historial_aprendizaje").select("fue_exitoso").eq("estudiante_id", perfil['id']).order("fecha_interaccion", desc=True).limit(5).execute()
    
    if not res_historial.data:
        return perfil, 50 
        
    exitos = sum(1 for item in res_historial.data if item['fue_exitoso'])
    porcentaje = (exitos / len(res_historial.data)) * 100
    return perfil, porcentaje

def evaluar_actividad(perfil, historial_chat):
    """Motor de evaluación objetivo y estructurado en JSON."""
    # Extraemos la rúbrica y LA TAREA para dárselas al evaluador
    rubrica = perfil.get('rubrica_evaluacion', 'Evalúa de forma estricta del 0 al 100 qué tanto entendió el estudiante el tema tratado. Revisa si cumplió la actividad asignada, su esfuerzo y la precisión de sus respuestas.')
    tarea_asignada = perfil.get('asignacion_actual', 'No hay una tarea específica asignada. Evalúa la comprensión general del tema.')
    
    prompt_evaluador = f"""
    Eres un profesor estricto, justo y objetivo. Tu tarea NO es hablar con el alumno, sino EVALUAR la interacción completa que acaba de tener con el tutor de IA.
    
    TAREA ASIGNADA AL ESTUDIANTE:
    {tarea_asignada}

    RÚBRICA DE EVALUACIÓN:
    {rubrica}
    
    HISTORIAL DE LA CONVERSACIÓN (Estudiante y Tutor):
    {historial_chat}
    
    Evalúa si el estudiante cumplió con la TAREA ASIGNADA basándote en la RÚBRICA leyendo todo el historial.
    Debes generar tu respuesta ÚNICAMENTE en formato JSON válido con la siguiente estructura exacta:
    {{
        "nota": <número entero del 0 al 100>,
        "feedback": "<Un párrafo corto y directo con la retroalimentación principal sobre su desempeño en la tarea>",
        "puntos_fuertes": "<Qué hizo bien el estudiante>",
        "areas_mejora": "<En qué debe mejorar para la próxima vez>"
    }}
    """
    
    respuesta = cliente_groq.chat.completions.create(
        messages=[{"role": "user", "content": prompt_evaluador}],
        model="llama-3.1-8b-instant",
        response_format={"type": "json_object"},
        temperature=0.1 
    )
    return respuesta.choices[0].message.content

def generar_respuesta(perfil, porcentaje_exito, pregunta, historial_chat):
    """El cerebro del Tutor Adaptativo (RAG + Prompting con Memoria)"""
    vector_pregunta = modelo_vectores.encode(pregunta).tolist()
    resultados = supabase.rpc("match_contenido_curricular", {
        "query_embedding": vector_pregunta, "match_threshold": 0.3, "match_count": 1 
    }).execute()

    texto_oficial = "No hay apuntes específicos en la base de datos para esta pregunta."
    contenido_id = None
    
    if resultados.data:
        texto_oficial = resultados.data[0]["contenido_texto"]
        contenido_id = resultados.data[0]["id"]

    grado_alumno = perfil.get('grado', 'un grado escolar')
    
    instrucciones = f"""Eres un tutor pedagógico excepcionalmente amable y empático. 
    El estudiante está en: {grado_alumno}. Ajusta estrictamente tu vocabulario y ejemplos para que un estudiante de {grado_alumno} lo entienda perfectamente. Usa el método socrático.
    
    REGLAS ESTRICTAS PARA TU COMPORTAMIENTO:
    1. Escribe ÚNICAMENTE tu próximo turno en la conversación.
    2. NO asumas, no simules ni escribas lo que el estudiante va a responder.
    3. NUNCA incluyas notas de guion como "(Espera la respuesta del estudiante)".
    4. Haz UNA SOLA pregunta a la vez y detente. Permite que el estudiante responda.
    5. Sé conciso y directo, simulando una conversación real de WhatsApp."""

    tarea_actual = perfil.get('asignacion_actual')
    complejidad = perfil.get('complejidad_asignacion', 'Intermedio')
    
    if tarea_actual:
        instrucciones += f"""\n\nATENCIÓN: El profesor asignó esta actividad al estudiante: '{tarea_actual}'.
        Complejidad exigida: {complejidad}. Guíalo paso a paso para cumplir esta actividad, sin darle la respuesta completa de golpe."""
    else:
        if not resultados.data:
            return "¡Hola! Esa es una gran pregunta. Sin embargo, ese tema aún no está en mis apuntes oficiales y no tienes una actividad asignada al respecto. ¿Qué te parece si lo anotas para la próxima clase con el profe?"

    mensajes_api = [{"role": "system", "content": f"{instrucciones}\n\nSOLO USA ESTA INFO OFICIAL (Si aplica):\n{texto_oficial}"}]
    
    for msg in historial_chat[-8:]:
        mensajes_api.append({"role": msg["role"], "content": msg["content"]})

    respuesta_ia = cliente_groq.chat.completions.create(
        messages=mensajes_api,
        model="llama-3.1-8b-instant",
        temperature=0.7
    )
    
    if contenido_id:
        supabase.table("historial_aprendizaje").insert({
            "estudiante_id": perfil['id'],
            "contenido_id": contenido_id,
            "fue_exitoso": True, 
            "observaciones": "Consulta web completada"
        }).execute()

    return respuesta_ia.choices[0].message.content

# ==========================================
# 4. INTERFAZ GRÁFICA (UI)
# ==========================================
st.title("🏫 Portal Educativo - Tutor IA")
st.markdown("<p style='font-size: 1.1rem; color: #4B5563;'>Entorno virtual de aprendizaje institucional.</p>", unsafe_allow_html=True)
st.divider()

with st.sidebar:
    st.image(URL_LOGO_COLEGIO, width=120) 
    st.header("Identificación Estudiantil")
    correo_input = st.text_input("Ingresa tu correo institucional:")
    
    if correo_input:
        perfil, exito = obtener_perfil(correo_input)
        if perfil:
            st.session_state['usuario_valido'] = True
            st.session_state['perfil'] = perfil
            st.session_state['exito'] = exito
            
            st.markdown(f"### 👋 Hola, {perfil['nombre']}")
            col1, col2 = st.columns(2)
            col1.metric("Nivel", f"Lvl {perfil['nivel_general']}")
            col2.metric("Aciertos", f"{int(exito)}%")
            st.caption("🟢 Conectado a la base de datos")
        else:
            st.error("Correo no encontrado. Consulta con tu profesor.")
            st.session_state['usuario_valido'] = False

# ==========================================
# ÁREA PRINCIPAL DEL CHAT Y EVALUACIÓN
# ==========================================
if st.session_state.get('usuario_valido', False):
    
    tarea_actual = st.session_state['perfil'].get('asignacion_actual')
    if tarea_actual:
        st.success(f"🎯 **Tu Misión Actual:** {tarea_actual}")
    
    if "mensajes" not in st.session_state:
        st.session_state.mensajes = [{"role": "assistant", "content": f"¡Hola {st.session_state['perfil']['nombre']}! Estoy aquí para ayudarte a completar tu actividad. ¿Por dónde empezamos?"}]

    for mensaje in st.session_state.mensajes:
        avatar_icon = "🧑‍🎓" if mensaje["role"] == "user" else URL_LOGO_COLEGIO
        with st.chat_message(mensaje["role"], avatar=avatar_icon):
            st.markdown(mensaje["content"])

    if pregunta := st.chat_input("Escribe tu duda aquí..."):
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(pregunta)
        st.session_state.mensajes.append({"role": "user", "content": pregunta})

        with st.chat_message("assistant", avatar=URL_LOGO_COLEGIO):
            with st.spinner("Pensando respuesta..."):
                respuesta = generar_respuesta(st.session_state['perfil'], st.session_state['exito'], pregunta, st.session_state.mensajes)
                st.markdown(respuesta)
        
        st.session_state.mensajes.append({"role": "assistant", "content": respuesta})
        st.rerun() 

    st.divider()
    col_vacia, col_boton = st.columns([2, 1])
    with col_boton:
        if st.button("📤 Entregar Actividad para Evaluar", type="primary", use_container_width=True):
            historial_texto = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.mensajes])
            
            with st.spinner("🧑‍🏫 Evaluando desempeño de manera objetiva..."):
                try:
                    resultado_json_str = evaluar_actividad(st.session_state['perfil'], historial_texto)
                    datos_evaluacion = json.loads(resultado_json_str) 
                    st.session_state['resultado_evaluacion'] = datos_evaluacion
                except Exception as e:
                    st.error(f"Hubo un error al generar la evaluación: {e}")
    
    if 'resultado_evaluacion' in st.session_state:
        datos = st.session_state['resultado_evaluacion']
        st.markdown("### 📊 Reporte de Evaluación")
        
        color_nota = "green" if datos['nota'] >= 60 else "red"
        st.markdown(f"<h1 style='text-align: center; color: {color_nota}; font-size: 4rem;'>{datos['nota']}/100</h1>", unsafe_allow_html=True)
        
        st.info(f"**🗣️ Comentario General:**\n{datos['feedback']}")
        
        col_buenas, col_mejoras = st.columns(2)
        with col_buenas:
            st.success(f"**✅ Puntos Fuertes:**\n{datos['puntos_fuertes']}")
        with col_mejoras:
            st.warning(f"**📈 Áreas de Mejora:**\n{datos['areas_mejora']}")
        
else:
    st.markdown("""
    <div class="info-card" style="padding: 20px; background-color: #f3f4f6; border-radius: 10px; margin-top: 20px;">
        <h4>🔒 Portal de Acceso Restringido</h4>
        <p>Por favor, usa el <b>panel izquierdo</b> para ingresar tu correo y desbloquear tus herramientas de estudio.</p>
    </div>
    """, unsafe_allow_html=True)