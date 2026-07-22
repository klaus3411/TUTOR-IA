import streamlit as st
import os
import json
import base64
import re
from dotenv import load_dotenv
from supabase import create_client, Client
from groq import Groq
from sentence_transformers import SentenceTransformer
import streamlit.components.v1 as components

# --- FONDO DE VIDEOLLAMADA Y AVATARES ---
URL_FONDO_VIDEOLLAMADA = "https://i.pinimg.com/originals/a1/bb/16/a1bb16dc8cda38148b1d624a9cb57b7f.gif" 
URL_AVATAR_SILENCIO = "https://i.postimg.cc/1zWzDD4z/Ilustracio-n-sin-ti-tulo.jpg" 
URL_AVATAR_HABLANDO = "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExb2psM3c5NmNsejJidWRldzd1MzNuMjNlaGpteXlhOThlNWY0aWxrNSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/gSov87k6n2tITSpWgJ/giphy.gif" 

try:
    from pypdf import PdfReader
    PDF_DISPONIBLE = True
except ImportError:
    PDF_DISPONIBLE = False

try:
    from gtts import gTTS
    import io
    VOZ_DISPONIBLE = True
except ImportError:
    VOZ_DISPONIBLE = False

st.set_page_config(page_title="Portal Educativo - Gimnasio Bilingüe Altamar de Cartagena", page_icon="🏫", layout="centered")

st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none !important;}
    [data-testid="collapsedControl"] {display: none !important;}
</style>
""", unsafe_allow_html=True)

URL_LOGO_COLEGIO = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSE3X0xDak4bCBuDN64-J9RuKK8l6BrFgnfPFhrSxTT6uaPc5yEaGm77Su6&s=10" 

MEDALLAS_MAESTRAS = {
    "primera_mision": {"titulo": "Primer Paso", "icono": "🥉", "desc": "Completaste tu primera tutoría con éxito."},
    "mente_brillante": {"titulo": "Mente Brillante", "icono": "🥈", "desc": "Obtuviste una calificación de 85 o más puntos."},
    "perfeccion": {"titulo": "Perfección", "icono": "🥇", "desc": "Alcanzaste la excelencia absoluta de 100/100."},
    "audiofilo": {"titulo": "Audiófilo", "icono": "🎙️", "desc": "Completaste una tutoría interactuando por voz."},
    "investigador": {"titulo": "Investigador", "icono": "📂", "desc": "Sustentaste tus tareas con archivos PDF o imágenes."}
}

@st.cache_resource
def iniciar_sistemas():
    load_dotenv()
    supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
    cliente_groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    modelo_vectores = SentenceTransformer('all-MiniLM-L6-v2')
    return supabase, cliente_groq, modelo_vectores

supabase, cliente_groq, modelo_vectores = iniciar_sistemas()

def obtener_perfil(correo):
    respuesta = supabase.table("estudiantes").select("*").eq("correo", correo).execute()
    return respuesta.data[0] if respuesta.data else None

def transcribir_audio(audio_bytes):
    try:
        respuesta = cliente_groq.audio.transcriptions.create(
            file=("audio.wav", audio_bytes),
            model="whisper-large-v3-turbo",
            response_format="text",
            language="es"
        )
        return respuesta
    except Exception as e:
        return f"[Error al transcribir audio: {e}]"

def otorgar_medalla_logica(estudiante_id, medalla_clave):
    try:
        comprobacion = supabase.table("medallas_ganadas").select("id").eq("estudiante_id", estudiante_id).eq("medalla_clave", medalla_clave).execute()
        if not comprobacion.data:
            supabase.table("medallas_ganadas").insert({
                "estudiante_id": estudiante_id,
                "medalla_clave": medalla_clave
            }).execute()
            return True
    except:
        pass
    return False

def evaluar_actividad(tutoria, historial_mensajes):
    rubrica = tutoria.get('rubrica') or 'Evalúa desde una perspectiva holística: sentir, pensar, actuar y convivir.'
    tarea = tutoria['mision']
    momento_pedagogico = tutoria.get('momento_pedagogico', 'General')
    
    tiene_imagen = any(isinstance(m['content'], list) for m in historial_mensajes)
    modelo_eval = "llama-3.2-11b-vision-preview" if tiene_imagen else "llama-3.1-8b-instant"
    
    prompt_sistema = f"""
    Eres un profesor EVALUADOR EXPERTO EN EL MODELO HOLÍSTICO TRANSFORMADOR (MHT) evaluando la asignatura de {tutoria['asignatura']}.
    Tu enfoque no es solo instructivo; buscas evaluar la madurez integral del ser humano (sentir, pensar, actuar, vivir, convivir y emprender).
    
    TAREA ASIGNADA: {tarea}
    MOMENTO PEDAGÓGICO DE LA TAREA: {momento_pedagogico}
    RÚBRICA ADICIONAL: {rubrica}
    
    INSTRUCCIONES DE CALIFICACIÓN (CUMPLE ESTO ESTRICTAMENTE):
    1. Si el estudiante evadió el proceso holístico o dio respuestas vacías, su nota debe ser menor a 40.
    2. Si la respuesta carece de conexión con la realidad local o no muestra pensamiento crítico, califica entre 40 y 60.
    3. Premia con más de 85 a quienes muestren creatividad, apropiación del "saber hacer" y "saber trascender".
    4. Inicia en 100 y resta puntos justificándolo pedagógicamente.
    
    Genera un reporte en formato JSON exacto:
    {{
        "razonamiento_secreto": "<Justificación pedagógica MHT de la nota>",
        "nota": <entero del 0 al 100>,
        "feedback": "<Retroalimentación constructiva, empática y motivadora, enfocada en la mejora integral>",
        "puntos_fuertes": "<Qué logró en su sentir, pensar o actuar>",
        "areas_mejora": "<En qué dimensión debe profundizar>"
    }}
    """
    
    mensajes_api = [{"role": "system", "content": prompt_sistema}]
    for msg in historial_mensajes:
        mensajes_api.append({"role": msg["role"], "content": msg["content"]})
        
    mensajes_api.append({"role": "user", "content": "Analiza paso a paso y genera la evaluación MHT en formato JSON ahora mismo."})
    
    opciones_api = {
        "messages": mensajes_api,
        "model": modelo_eval,
        "temperature": 0.1 
    }
    
    if not tiene_imagen:
        opciones_api["response_format"] = {"type": "json_object"}
        
    respuesta = cliente_groq.chat.completions.create(**opciones_api)
    contenido = respuesta.choices[0].message.content
    
    match = re.search(r'\{.*\}', contenido, re.DOTALL)
    if match:
        return match.group(0)
    return contenido

def generar_respuesta(perfil, tutoria, pregunta_actual, historial_mensajes):
    texto_busqueda = str(pregunta_actual)
    vector_pregunta = modelo_vectores.encode(texto_busqueda).tolist()
    resultados = supabase.rpc("match_contenido_curricular", {
        "query_embedding": vector_pregunta, "match_threshold": 0.3, "match_count": 1 
    }).execute()

    texto_oficial = "No hay apuntes específicos en la base de datos para esto."
    if resultados.data:
        texto_oficial = resultados.data[0]["contenido_texto"]

    grado = perfil.get('grado', 'un grado escolar')
    curso = perfil.get('curso', 'N/A')
    momento_pedagogico = tutoria.get('momento_pedagogico', 'General / Ciclo Completo')
    modo_voz = tutoria.get('modo_voz', False)

    # ==========================================
    # CEREBRO MHT: PROTOCOLO DE INTERACCIÓN
    # ==========================================
    instrucciones = f"""ROL Y PERFIL DEL ASISTENTE:
Eres un "Tutor Pedagógico de IA", experto en el Modelo Holístico Transformador (MHT) desarrollado por Giovanni Marcello Iafrancesco. 
Tu propósito es guiar al estudiante de manera empática, detallada y rigurosa hacia la madurez integral (sentir, pensar, actuar, vivir, convivir y emprender).

DATOS DEL ALUMNO:
- Asignatura: {tutoria['asignatura']}
- Grado: {grado} (Sección {curso})
- Complejidad: {tutoria['complejidad']}
- MISIÓN ASIGNADA HOY: {tutoria['mision']}

ENFOQUE PEDAGÓGICO DE ESTA SESIÓN:
Estás trabajando en el momento de: **{momento_pedagogico}**.

TUS BASES MHT PARA ESTE MOMENTO (Aplica el que corresponda a esta sesión):
1. IDENTIFICACIÓN (Sentir): Movilizar afectiva y cognitivamente. Rescatar saberes previos y emociones.
2. CONTEXTUALIZACIÓN (Pensar): Conectar el saber técnico con el entorno real (histórico, social, local, cotidiano). Explicar el "para qué" sirve.
3. APLICACIÓN (Saber Hacer): Experimentar y ejecutar de forma estructurada. Talleres y resolución guiada.
4. INNOVACIÓN (Saber Trascender): Crear, transformar y proponer soluciones originales e inéditas a problemas reales.

INSTRUCCIONES DE COMPORTAMIENTO:
1. RUTA DE ACCIÓN: Empieza saludando empáticamente. Nunca des la respuesta directa; usa la mayéutica. Guía al estudiante basándote estrictamente en el "Momento Pedagógico" actual asignado a esta sesión.
2. FORMATO DE CLASE: Si el usuario te pide una explicación detallada o una guía, estructúrala de forma impecable usando la "Plantilla Estándar de Respuesta MHT" (Título, Propósito, y los 4 momentos detallando: Objetivo, Actividad, Pregunta Detonante).
3. TONO: Motivador, empático y orientado a que descubra el "porqué" de las cosas.
4. LÍMITES MULTIMODALES: Si el alumno sube una imagen o [DOCUMENTO PDF ADJUNTO], analízalo detalladamente usando los lentes del MHT. IMPORTANTE: Si no hay archivos, NUNCA asumas que los hay.
"""

    if modo_voz:
        instrucciones += "\n5. ALERTA MODO VOZ ACTIVADO: Tus respuestas serán leídas en voz alta. Por favor, IGNORA la regla de crear guías o plantillas largas. Debes ser MUY BREVE (máximo 2 o 3 oraciones cortas), conversacional y actuar como si estuvieras en una videollamada. Haz una sola pregunta reflexiva corta a la vez."
    else:
        instrucciones += "\n5. MODO TEXTO ACTIVADO: Tus respuestas deben ser detalladas, estructuradas de forma impecable y ricas en pedagogía holística."

    tiene_imagen = any(isinstance(m['content'], list) for m in historial_mensajes[-5:])
    modelo_chat = "llama-3.2-11b-vision-preview" if tiene_imagen else "llama-3.1-8b-instant"

    mensajes_api = [{"role": "system", "content": f"{instrucciones}\n\nMATERIAL DE APOYO OFICIAL:\n{texto_oficial}"}]
    
    if not historial_mensajes:
        mensajes_api.append({"role": "system", "content": "Genera el saludo inicial aplicando el MHT."})
    else:
        for msg in historial_mensajes[-8:]: 
            mensajes_api.append({"role": msg["role"], "content": msg["content"]})

    respuesta_ia = cliente_groq.chat.completions.create(
        messages=mensajes_api,
        model=modelo_chat,
        temperature=0.7
    )
    return respuesta_ia.choices[0].message.content

# ==========================================
# 4. INTERFAZ GRÁFICA (UI)
# ==========================================
if not st.session_state.get('usuario_valido', False):
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"<div style='text-align: center;'><img src='{URL_LOGO_COLEGIO}' width='150' style='border-radius: 50%;'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>Portal Educativo</h2>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            correo_input = st.text_input("✉️ Correo Institucional:")
            if st.form_submit_button("Ingresar", type="primary", use_container_width=True):
                if correo_input:
                    perfil = obtener_perfil(correo_input.strip().lower())
                    if perfil:
                        st.session_state['usuario_valido'] = True
                        st.session_state['perfil'] = perfil
                        st.rerun()
                    else:
                        st.error("Correo no encontrado en el sistema.")
                else:
                    st.warning("Ingresa tu correo.")
                    
        st.markdown("<br><p style='text-align: center;'><a href='/tablero_profesor' target='_self' style='color: #9CA3AF; text-decoration: none; font-size: 0.8rem;'>👨‍🏫 Acceso Docente</a></p>", unsafe_allow_html=True)

else:
    perfil_actual = st.session_state['perfil']
    
    if 'tutoria_activa' not in st.session_state:
        col_saludo, col_salir = st.columns([3, 1])
        with col_saludo:
            st.markdown(f"### 👋 Hola, {perfil_actual['nombre']}")
        with col_salir:
            if st.button("🚪 Salir", use_container_width=True):
                st.session_state.clear()
                st.rerun()
                
        st.divider()
        tab_misiones, tab_rendimiento = st.tabs(["🎮 Mis Misiones", "📊 Mi Rendimiento"])
        
        with tab_misiones:
            try:
                res_med_db = supabase.table("medallas_ganadas").select("medalla_clave").eq("estudiante_id", perfil_actual['id']).execute()
                claves_ganadas = [registro['medalla_clave'] for registro in res_med_db.data] if res_med_db.data else []
                
                st.markdown("#### 🏆 Tus Logros Académicos")
                columnas_medallas = st.columns(len(MEDALLAS_MAESTRAS))
                for index, (clave, metadatos) in enumerate(MEDALLAS_MAESTRAS.items()):
                    with columnas_medallas[index]:
                        if clave in claves_ganadas:
                            st.markdown(f"""
                            <div style="text-align: center; background-color: #f0fdf4; border: 2px solid #22c55e; padding: 12px; border-radius: 12px; min-height: 140px;">
                                <span style="font-size: 2.2rem;">{metadatos['icono']}</span><br>
                                <b style="font-size: 0.8rem; color: #166534; display: block; margin-top: 5px;">{metadatos['titulo']}</b>
                                <p style="font-size: 0.65rem; color: #15803d; margin: 5px 0 0 0; line-height: 1.1;">{metadatos['desc']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style="text-align: center; background-color: #f8fafc; border: 2px dashed #cbd5e1; padding: 12px; border-radius: 12px; min-height: 140px; opacity: 0.45;">
                                <span style="font-size: 2.2rem; filter: grayscale(100%);">🔒</span><br>
                                <b style="font-size: 0.8rem; color: #64748b; display: block; margin-top: 5px;">Bloqueado</b>
                                <p style="font-size: 0.65rem; color: #94a3b8; margin: 5px 0 0 0; line-height: 1.1;">{metadatos['desc']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                st.write("")
            except:
                pass

            st.subheader("📚 Tus Tutorías Pendientes")
            try:
                res_tutorias = supabase.table("tutorias").select("*").eq("estudiante_id", perfil_actual['id']).eq("estado", "pendiente").execute()
                tutorias_pendientes = res_tutorias.data
                
                if not tutorias_pendientes:
                    st.success("¡Felicidades! No tienes tutorías pendientes. Eres libre. 🎉")
                else:
                    for tutoria in tutorias_pendientes:
                        with st.container():
                            icono_voz = " 🎙️ (Misión con Voz)" if tutoria.get('modo_voz', False) else ""
                            momento_badge = f"<span style='background:#e0e7ff; color:#3730a3; padding:3px 8px; border-radius:12px; font-size:0.7rem;'>Fase: {tutoria.get('momento_pedagogico', 'General')}</span>"
                            
                            st.markdown(f"""
                            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid #4F46E5;">
                                <h3 style="margin-top: 0;">📘 {tutoria['asignatura']}{icono_voz}</h3>
                                {momento_badge}
                                <p style="margin-top:10px;"><b>Misión:</b> {tutoria['mision']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button(f"Entrar a tutoría de {tutoria['asignatura']}", key=tutoria['id'], type="primary"):
                                st.session_state['tutoria_activa'] = tutoria
                                primer_msg = f"¡Hola, {perfil_actual['nombre']}! Soy tu Tutor. Hoy trabajaremos en la fase de **{tutoria.get('momento_pedagogico', 'General')}**. Tu misión es: *{tutoria['mision']}*. ¿Comenzamos?"
                                st.session_state['mensajes'] = [{"role": "assistant", "content": primer_msg}]
                                st.rerun()
            except Exception as e:
                st.error("Error al cargar las tutorías.")

        with tab_rendimiento:
            st.markdown("#### 📈 Resumen de tu Desempeño Holístico")
            try:
                res_eval = supabase.table("evaluaciones").select("*").eq("estudiante_id", perfil_actual['id']).order("created_at", desc=True).execute()
                historial_evaluaciones = res_eval.data
                
                if not historial_evaluaciones:
                    st.info("Aún no tienes calificaciones registradas. ¡Completa tu primera misión para ver tus notas aquí!")
                else:
                    total_misiones = len(historial_evaluaciones)
                    promedio = sum(item['nota'] for item in historial_evaluaciones) / total_misiones
                    
                    col_prom, col_total = st.columns(2)
                    with col_prom:
                        st.markdown(f"""
                        <div style="text-align: center; background-color: #eff6ff; padding: 15px; border-radius: 10px; border: 1px solid #bfdbfe;">
                            <p style="color: #1e3a8a; font-weight: bold; margin: 0;">Desempeño Integral</p>
                            <h2 style="color: #2563eb; margin: 0;">{promedio:.1f} <span style="font-size: 1rem; color: #60a5fa;">/100</span></h2>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_total:
                        st.markdown(f"""
                        <div style="text-align: center; background-color: #fef2f2; padding: 15px; border-radius: 10px; border: 1px solid #fecaca;">
                            <p style="color: #7f1d1d; font-weight: bold; margin: 0;">Retos Completados</p>
                            <h2 style="color: #dc2626; margin: 0;">{total_misiones}</h2>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    st.divider()
                    st.markdown("#### 📖 Historial de Retroalimentaciones")
                    
                    for evaluacion in historial_evaluaciones:
                        fecha_corta = evaluacion['created_at'][:10]
                        nota = evaluacion['nota']
                        color_nota = "🟢" if nota >= 85 else "🟡" if nota >= 60 else "🔴"
                        with st.expander(f"{color_nota} {fecha_corta} | {evaluacion['tarea']} - Nota: {nota}/100"):
                            st.markdown(f"**🗣️ Guía Pedagógica del Tutor:**")
                            st.info(evaluacion['feedback'])
            except Exception as e:
                st.error("No se pudo cargar tu historial.")

    # ------------------------------------------
    # PANTALLA DE TUTORÍA ACTIVA
    # ------------------------------------------
    else:
        tutoria_actual = st.session_state['tutoria_activa']
        modo_voz_activado = tutoria_actual.get('modo_voz', False)
        
        if modo_voz_activado:
            st.markdown(f"""
            <style>
                @keyframes pulse-red {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} 100% {{ opacity: 1; }} }}
                @keyframes float-window {{ 0% {{ transform: translateY(0px); }} 50% {{ transform: translateY(-8px); }} 100% {{ transform: translateY(0px); }} }}
                .floating-pip {{ position: fixed; top: 80px; right: 20px; width: 130px; height: 180px; border-radius: 16px; box-shadow: 0px 10px 30px rgba(0,0,0,0.3); border: 3px solid #4F46E5; z-index: 999999; overflow: hidden; background-color: #000; animation: float-window 4s ease-in-out infinite; }}
                .floating-pip img {{ width: 100%; height: 100%; object-fit: cover; }}
                .live-badge {{ position: absolute; top: 8px; right: 8px; background-color: #ef4444; color: white; font-size: 0.6rem; font-weight: bold; padding: 3px 8px; border-radius: 12px; z-index: 2; animation: pulse-red 1.5s infinite; box-shadow: 0px 2px 5px rgba(0,0,0,0.5); display: none; }}
            </style>
            <div class="floating-pip" id="pip-container">
                <div class="live-badge" id="live-badge-ui">🔴 LIVE</div>
                <img id="tutor-avatar-ui" src="{URL_AVATAR_SILENCIO}">
            </div>
            """, unsafe_allow_html=True)

        col_back, col_title = st.columns([1, 4])
        with col_back:
            if st.button("⬅️ Salir", use_container_width=True):
                del st.session_state['tutoria_activa']
                if 'resultado_evaluacion' in st.session_state: del st.session_state['resultado_evaluacion']
                st.rerun()
        with col_title:
            st.success(f"🎯 **{tutoria_actual['asignatura']} | Fase: {tutoria_actual.get('momento_pedagogico', 'General')}**")

        if 'resultado_evaluacion' not in st.session_state:
            for index, mensaje in enumerate(st.session_state.mensajes):
                avatar_icon = "🧑‍🎓" if mensaje["role"] == "user" else URL_LOGO_COLEGIO
                with st.chat_message(mensaje["role"], avatar=avatar_icon):
                    if isinstance(mensaje["content"], list):
                        for item in mensaje["content"]:
                            if item["type"] == "text":
                                st.markdown(item["text"])
                            elif item["type"] == "image_url":
                                b64_img = item["image_url"]["url"].split(",")[1]
                                st.image(base64.b64decode(b64_img), width=350)
                    else:
                        if "[DOCUMENTO PDF ADJUNTO]:" in mensaje["content"]:
                            partes = mensaje["content"].split("[DOCUMENTO PDF ADJUNTO]:")
                            st.markdown(partes[0].strip())
                            with st.expander("📄 Documento PDF Adjunto (Texto Extraído)"):
                                st.text(partes[1].strip())
                        else:
                            st.markdown(mensaje["content"])
                            
                    if mensaje.get("audio_bytes"):
                        es_el_ultimo = (index == len(st.session_state.mensajes) - 1)
                        b64_audio = base64.b64encode(mensaje["audio_bytes"]).decode()
                        codigo_reproductor_inteligente = f"""
                        <audio id="audio-{index}" controls {"autoplay" if es_el_ultimo else ""} style="width: 100%; height: 45px; outline: none; border-radius: 10px;">
                            <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
                        </audio>
                        <script>
                            (function() {{
                                const audio = document.getElementById('audio-{index}');
                                const parentDoc = window.parent.document;
                                const avatar = parentDoc.getElementById('tutor-avatar-ui');
                                const badge = parentDoc.getElementById('live-badge-ui');
                                if (avatar && audio) {{
                                    audio.onplay = () => {{ avatar.src = "{URL_AVATAR_HABLANDO}"; if (badge) badge.style.display = 'block'; }};
                                    audio.onended = () => {{ avatar.src = "{URL_AVATAR_SILENCIO}"; if (badge) badge.style.display = 'none'; }};
                                    audio.onpause = audio.onended;
                                }}
                            }})();
                        </script>
                        """
                        components.html(codigo_reproductor_inteligente, height=60)

            col_doc, col_voz = st.columns([1, 1])
            with col_doc:
                with st.expander("📎 Adjuntar PDF / Imagen"):
                    archivo_subido = st.file_uploader("Sube y escribe abajo para enviar.", type=["pdf", "png", "jpg", "jpeg", "webp"], label_visibility="collapsed")
                    if archivo_subido:
                        st.success("Archivo listo.")
            
            with col_voz:
                with st.expander("🎙️ Enviar nota de voz"):
                    if VOZ_DISPONIBLE:
                        st.markdown(f"<p style='font-size:0.8rem; text-align:center;'>Usa la grabadora a continuación para hablar.</p>", unsafe_allow_html=True)
                        grabacion = st.audio_input("Graba tu mensaje", label_visibility="collapsed")
                        if grabacion is not None:
                            audio_bytes = grabacion.getvalue()
                            if audio_bytes != st.session_state.get('ultimo_audio'):
                                st.session_state['ultimo_audio'] = audio_bytes
                                st.markdown(f"<p style='text-align:center;'>⏳ Escuchando tu nota de voz...</p>", unsafe_allow_html=True)
                                texto_voz = transcribir_audio(audio_bytes)
                                st.session_state['mensaje_voz_pendiente'] = texto_voz
                                st.rerun() 
                    else:
                        st.warning("⚠️ La librería gTTS no está instalada.")

            pregunta_escrita = st.chat_input("Escribe tu mensaje para enviar...")
            pregunta_voz = st.session_state.get('mensaje_voz_pendiente')
            pregunta = pregunta_escrita or pregunta_voz

            if pregunta:
                if pregunta_voz: del st.session_state['mensaje_voz_pendiente']
                contenido_final = pregunta
                texto_pdf_extraido = ""
                
                if archivo_subido is not None:
                    st.session_state['evidencia_adjuntada_en_mision'] = True
                    if archivo_subido.type == "application/pdf":
                        if PDF_DISPONIBLE:
                            try:
                                lector = PdfReader(archivo_subido)
                                texto_pdf_extraido = "\n".join([pagina.extract_text() for pagina in lector.pages])
                                contenido_final = f"{pregunta}\n\n[DOCUMENTO PDF ADJUNTO]:\n{texto_pdf_extraido}"
                                st.session_state.mensajes.append({"role": "user", "content": contenido_final})
                            except Exception as e:
                                st.error(f"Error al leer PDF: {e}")
                                st.session_state.mensajes.append({"role": "user", "content": pregunta})
                    elif archivo_subido.type.startswith("image/"):
                        bytes_data = archivo_subido.getvalue()
                        base64_encoded = base64.b64encode(bytes_data).decode('utf-8')
                        contenido_final = [
                            {"type": "text", "text": pregunta},
                            {"type": "image_url", "image_url": {"url": f"data:{archivo_subido.type};base64,{base64_encoded}"}}
                        ]
                        st.session_state.mensajes.append({"role": "user", "content": contenido_final})
                else:
                    st.session_state.mensajes.append({"role": "user", "content": contenido_final})

                if pregunta_voz:
                    st.session_state['voz_utilizada_en_mision'] = True

                with st.chat_message("assistant", avatar=URL_LOGO_COLEGIO):
                    st.markdown(f"<p>Pensando...</p>", unsafe_allow_html=True)
                    
                    respuesta = generar_respuesta(perfil_actual, tutoria_actual, pregunta, st.session_state.mensajes)
                    audio_generado = None
                    if VOZ_DISPONIBLE and modo_voz_activado:
                        try:
                            tts = gTTS(respuesta, lang='es', tld='com.mx')
                            fp = io.BytesIO()
                            tts.write_to_fp(fp)
                            audio_generado = fp.getvalue()
                        except:
                            pass 
                
                st.session_state.mensajes.append({
                    "role": "assistant", 
                    "content": respuesta,
                    "audio_bytes": audio_generado 
                })
                st.rerun() 

            st.divider()
            ha_interactuado = len(st.session_state.mensajes) > 1
            if not ha_interactuado:
                st.info("💡 Escribe al menos un mensaje o sube un archivo antes de entregar.")

            col_vacia, col_boton = st.columns([2, 1])
            with col_boton:
                if st.button("📤 Entregar Actividad", type="primary", use_container_width=True, disabled=not ha_interactuado):
                    with st.spinner("🧑‍🏫 Evaluando de forma Holística..."):
                        try:
                            resultado_json_str = evaluar_actividad(tutoria_actual, st.session_state.mensajes)
                            datos_evaluacion = json.loads(resultado_json_str)
                            
                            historial_limpio_para_db = []
                            for m in st.session_state.mensajes:
                                mensaje_copia = {"role": m["role"], "content": m["content"]}
                                historial_limpio_para_db.append(mensaje_copia)
                                
                            historial_completo = json.dumps(historial_limpio_para_db, ensure_ascii=False, indent=4)
                            
                            supabase.table("evaluaciones").insert({
                                "estudiante_id": perfil_actual['id'],
                                "tarea": tutoria_actual['mision'],
                                "nota": datos_evaluacion['nota'],
                                "feedback": datos_evaluacion['feedback'],
                                "historial_evidencia": historial_completo
                            }).execute()
                            
                            supabase.table("tutorias").update({"estado": "completada"}).eq("id", tutoria_actual['id']).execute()
                            
                            # GAMIFICACIÓN
                            medallas_desbloqueadas_ahora = []
                            if otorgar_medalla_logica(perfil_actual['id'], "primera_mision"): medallas_desbloqueadas_ahora.append("primera_mision")
                            if datos_evaluacion['nota'] >= 85: 
                                if otorgar_medalla_logica(perfil_actual['id'], "mente_brillante"): medallas_desbloqueadas_ahora.append("mente_brillante")
                            if datos_evaluacion['nota'] == 100:
                                if otorgar_medalla_logica(perfil_actual['id'], "perfeccion"): medallas_desbloqueadas_ahora.append("perfeccion")
                            if st.session_state.get('voz_utilizada_en_mision', False) or modo_voz_activado:
                                if otorgar_medalla_logica(perfil_actual['id'], "audiofilo"): medallas_desbloqueadas_ahora.append("audiofilo")
                            if st.session_state.get('evidencia_adjuntada_en_mision', False):
                                if otorgar_medalla_logica(perfil_actual['id'], "investigador"): medallas_desbloqueadas_ahora.append("investigador")
                            
                            if medallas_desbloqueadas_ahora: st.session_state['nuevas_medallas'] = medallas_desbloqueadas_ahora
                            st.session_state['resultado_evaluacion'] = datos_evaluacion
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        
        else:
            datos = st.session_state['resultado_evaluacion']
            st.markdown("### 📊 Actividad Completada")
            st.markdown(f"<h1 style='text-align: center; color: green;'>{datos['nota']}/100</h1>", unsafe_allow_html=True)
            st.info(f"**🗣️ Comentario del Tutor:**\n{datos['feedback']}")
            
            if 'nuevas_medallas' in st.session_state:
                st.balloons() 
                st.markdown("#### 🎉 ¡Has desbloqueado nuevos logros integrales en esta misión!")
                for clave_m in st.session_state['nuevas_medallas']:
                    meta = MEDALLAS_MAESTRAS[clave_m]
                    st.success(f"**{meta['icono']} {meta['titulo']}:** {meta['desc']}")
            
            if st.button("Regresar a Misiones", type="primary"):
                del st.session_state['tutoria_activa']
                del st.session_state['resultado_evaluacion']
                if 'nuevas_medallas' in st.session_state: del st.session_state['nuevas_medallas']
                if 'voz_utilizada_en_mision' in st.session_state: del st.session_state['voz_utilizada_en_mision']
                if 'evidencia_adjuntada_en_mision' in st.session_state: del st.session_state['evidencia_adjuntada_en_mision']
                st.rerun()