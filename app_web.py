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

# Intentamos importar pypdf, si no está, avisaremos en la interfaz
try:
    from pypdf import PdfReader
    PDF_DISPONIBLE = True
except ImportError:
    PDF_DISPONIBLE = False

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA WEB
# ==========================================
st.set_page_config(page_title="Portal Educativo - Estudiante", page_icon="🏫", layout="centered")

st.markdown("""
<style>
    [data-testid="stSidebar"] {display: none !important;}
    [data-testid="collapsedControl"] {display: none !important;}
</style>
""", unsafe_allow_html=True)

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
# 3. FUNCIONES DEL TUTOR Y EVALUADOR MULTIMODAL
# ==========================================
def obtener_perfil(correo):
    respuesta = supabase.table("estudiantes").select("*").eq("correo", correo).execute()
    return respuesta.data[0] if respuesta.data else None

def evaluar_actividad(tutoria, historial_mensajes):
    """Motor de evaluación objetivo usando Cadena de Pensamiento para evitar notas repetidas."""
    rubrica = tutoria.get('rubrica') or 'Resta puntos por falta de profundidad, errores técnicos o si la respuesta es muy corta.'
    tarea = tutoria['mision']
    
    # Detectamos si hay alguna imagen en la conversación para cambiar de modelo
    tiene_imagen = any(isinstance(m['content'], list) for m in historial_mensajes)
    modelo_eval = "llama-3.2-11b-vision-preview" if tiene_imagen else "llama-3.1-8b-instant"
    
    prompt_sistema = f"""
    Eres un profesor EVALUADOR ESTRICTO Y ALTAMENTE OBJETIVO de {tutoria['asignatura']}.
    Tu tarea es CALIFICAR la interacción del estudiante basándote ÚNICAMENTE en la evidencia del chat y archivos enviados.
    
    TAREA ASIGNADA: {tarea}
    RÚBRICA DE PENALIZACIÓN: {rubrica}
    
    INSTRUCCIONES DE CALIFICACIÓN (CUMPLE ESTO ESTRICTAMENTE):
    1. NO REGALES NOTA. Si el estudiante solo dijo "hola", no hizo la tarea o la evadió, la nota debe ser menor a 30 (incluso 0).
    2. Si la respuesta es mediocre, copiada o incompleta, la nota debe estar entre 40 y 60.
    3. Solo da más de 85 si el estudiante resolvió PERFECTAMENTE la misión.
    4. Inicia en 100 y RESTA puntos por cada error, falta de análisis o pereza al responder.
    
    Genera un reporte en formato JSON exacto:
    {{
        "razonamiento_secreto": "<Obligatorio: Escribe aquí por qué le vas a poner la nota, qué le faltó y cuántos puntos le restas>",
        "nota": <número entero estricto del 0 al 100 basado en tu razonamiento>,
        "feedback": "<Retroalimentación directa y constructiva para el estudiante>",
        "puntos_fuertes": "<Qué hizo bien (o 'Ninguno' si no hizo nada)>",
        "areas_mejora": "<En qué debe mejorar>"
    }}
    """
    
    mensajes_api = [{"role": "system", "content": prompt_sistema}]
    for msg in historial_mensajes:
        mensajes_api.append({"role": msg["role"], "content": msg["content"]})
        
    mensajes_api.append({"role": "user", "content": "Analiza paso a paso y genera la evaluación en formato JSON ahora mismo."})
    
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
    """Corregido para aceptar los 4 argumentos necesarios."""
    # Extraer el texto para buscar en los apuntes
    vector_pregunta = modelo_vectores.encode(str(pregunta_actual)).tolist()
    resultados = supabase.rpc("match_contenido_curricular", {
        "query_embedding": vector_pregunta, "match_threshold": 0.3, "match_count": 1 
    }).execute()

    texto_oficial = "No hay apuntes específicos en la base de datos para esto."
    if resultados.data:
        texto_oficial = resultados.data[0]["contenido_texto"]

    grado = perfil.get('grado', 'un grado escolar')
    instrucciones = f"""Eres un tutor pedagógico de {tutoria['asignatura']}. El estudiante está en {grado}.
    MISIÓN DEL ALUMNO: {tutoria['mision']}
    COMPLEJIDAD: {tutoria['complejidad']}
    
    REGLAS:
    1. Si el alumno sube una imagen o PDF, analízalo cuidadosamente.
    2. Haz UNA SOLA pregunta a la vez. No simules la respuesta del estudiante.
    """

    tiene_imagen = any(isinstance(m['content'], list) for m in historial_mensajes[-5:])
    modelo_chat = "llama-3.2-11b-vision-preview" if tiene_imagen else "llama-3.1-8b-instant"

    mensajes_api = [{"role": "system", "content": f"{instrucciones}\n\nINFO OFICIAL:\n{texto_oficial}"}]
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
        st.markdown("<p style='text-align: center; color: #4B5563;'>Ingresa para ver tus misiones.</p>", unsafe_allow_html=True)
        
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
    col_saludo, col_salir = st.columns([3, 1])
    with col_saludo:
        st.markdown(f"### 👋 Hola, {perfil_actual['nombre']}")
    with col_salir:
        if st.button("🚪 Salir", use_container_width=True):
            st.session_state.clear()
            st.rerun()
            
    st.divider()
    
    if 'tutoria_activa' not in st.session_state:
        st.subheader("📚 Tus Tutorías Pendientes")
        try:
            res_tutorias = supabase.table("tutorias").select("*").eq("estudiante_id", perfil_actual['id']).eq("estado", "pendiente").execute()
            tutorias_pendientes = res_tutorias.data
            
            if not tutorias_pendientes:
                st.success("¡Felicidades! No tienes tutorías pendientes. Eres libre. 🎉")
            else:
                for tutoria in tutorias_pendientes:
                    with st.container():
                        st.markdown(f"""
                        <div style="background-color: #f3f4f6; padding: 20px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid #4F46E5;">
                            <h3 style="margin-top: 0;">📘 {tutoria['asignatura']}</h3>
                            <p><b>Misión:</b> {tutoria['mision']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"Entrar a tutoría de {tutoria['asignatura']}", key=tutoria['id'], type="primary"):
                            st.session_state['tutoria_activa'] = tutoria
                            st.session_state['mensajes'] = [{"role": "assistant", "content": f"¡Hola! Hoy tenemos la misión: *{tutoria['mision']}*. ¿Empezamos?"}]
                            st.rerun()
        except Exception as e:
            st.error("Error al cargar las tutorías.")
            
    else:
        tutoria_actual = st.session_state['tutoria_activa']
        
        if st.button("⬅️ Volver a mis misiones", use_container_width=False):
            del st.session_state['tutoria_activa']
            if 'resultado_evaluacion' in st.session_state: del st.session_state['resultado_evaluacion']
            st.rerun()
            
        st.success(f"🎯 **{tutoria_actual['asignatura']}:** {tutoria_actual['mision']}")

        if 'resultado_evaluacion' not in st.session_state:
            for mensaje in st.session_state.mensajes:
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
                        st.markdown(mensaje["content"])

            with st.expander("📎 Adjuntar Imagen o Documento PDF para tu tarea"):
                archivo_subido = st.file_uploader("Sube una foto o PDF y escribe en el chat para enviarlo.", type=["pdf", "png", "jpg", "jpeg"])
                if archivo_subido:
                    st.success(f"Archivo listo. Escribe un mensaje abajo y presiona Enter para enviarlo.")

            if pregunta := st.chat_input("Escribe tu mensaje para enviar..."):
                contenido_final = pregunta
                
                if archivo_subido is not None:
                    if archivo_subido.type == "application/pdf":
                        if PDF_DISPONIBLE:
                            try:
                                lector = PdfReader(archivo_subido)
                                texto_pdf = "\n".join([pagina.extract_text() for pagina in lector.pages])
                                contenido_final = f"{pregunta}\n\n[DOCUMENTO PDF ADJUNTO]:\n{texto_pdf}"
                                st.session_state.mensajes.append({"role": "user", "content": contenido_final})
                            except Exception as e:
                                st.error(f"Error al leer PDF: {e}")
                                st.session_state.mensajes.append({"role": "user", "content": pregunta})
                        else:
                            st.session_state.mensajes.append({"role": "user", "content": pregunta})
                    
                    elif archivo_subido.type in ["image/jpeg", "image/png", "image/jpg"]:
                        bytes_data = archivo_subido.getvalue()
                        base64_encoded = base64.b64encode(bytes_data).decode('utf-8')
                        contenido_final = [
                            {"type": "text", "text": pregunta},
                            {"type": "image_url", "image_url": {"url": f"data:{archivo_subido.type};base64,{base64_encoded}"}}
                        ]
                        st.session_state.mensajes.append({"role": "user", "content": contenido_final})
                else:
                    st.session_state.mensajes.append({"role": "user", "content": contenido_final})

                with st.chat_message("user", avatar="🧑‍🎓"):
                    st.markdown(pregunta)

                with st.chat_message("assistant", avatar=URL_LOGO_COLEGIO):
                    with st.spinner("Escribiendo..."):
                        respuesta = generar_respuesta(perfil_actual, tutoria_actual, pregunta, st.session_state.mensajes)
                        st.markdown(respuesta)
                
                st.session_state.mensajes.append({"role": "assistant", "content": respuesta})
                st.rerun() 

            st.divider()
            
            ha_interactuado = len(st.session_state.mensajes) > 1
            if not ha_interactuado:
                st.info("💡 Escribe al menos un mensaje o sube un archivo antes de entregar.")

            col_vacia, col_boton = st.columns([2, 1])
            with col_boton:
                if st.button("📤 Entregar Actividad", type="primary", use_container_width=True, disabled=not ha_interactuado):
                    with st.spinner("🧑‍🏫 Evaluando..."):
                        try:
                            resultado_json_str = evaluar_actividad(tutoria_actual, st.session_state.mensajes)
                            datos_evaluacion = json.loads(resultado_json_str)
                            
                            # NUEVO: Guardamos el historial completo para auditoría
                            historial_completo = json.dumps(st.session_state.mensajes)
                            
                            supabase.table("evaluaciones").insert({
                                "estudiante_id": perfil_actual['id'],
                                "tarea": tutoria_actual['mision'],
                                "nota": datos_evaluacion['nota'],
                                "feedback": datos_evaluacion['feedback'],
                                "historial_evidencia": historial_completo
                            }).execute()
                            
                            supabase.table("tutorias").update({"estado": "completada"}).eq("id", tutoria_actual['id']).execute()
                            st.session_state['resultado_evaluacion'] = datos_evaluacion
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        
        else:
            datos = st.session_state['resultado_evaluacion']
            st.markdown("### 📊 Actividad Completada")
            st.markdown(f"<h1 style='text-align: center; color: green;'>{datos['nota']}/100</h1>", unsafe_allow_html=True)
            st.info(f"**🗣️ Comentario:**\n{datos['feedback']}")
            if st.button("Regresar", type="primary"):
                del st.session_state['tutoria_activa']
                del st.session_state['resultado_evaluacion']
                st.rerun()