import streamlit as st
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from groq import Groq
from sentence_transformers import SentenceTransformer
import streamlit.components.v1 as components

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA WEB
# ==========================================
st.set_page_config(page_title="Tutor IA - Alternancia", page_icon="🎓", layout="centered")

# ==========================================
# 1.5 INYECCIÓN PWA (App Instalable para Celulares)
# ==========================================
# Este script invisible engaña al celular para que crea que es una App Nativa
components.html("""
<script>
    const manifest = {
        "name": "Tutor IA - Colegio",
        "short_name": "Tutor IA",
        "theme_color": "#4F46E5",
        "background_color": "#F9FAFB",
        "display": "standalone",
        "orientation": "portrait",
        "scope": "/",
        "start_url": "/",
        "icons": [
            {
                "src": "https://cdn-icons-png.flaticon.com/512/3135/3135810.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    };
    const stringManifest = JSON.stringify(manifest);
    const blob = new Blob([stringManifest], {type: 'application/json'});
    const manifestURL = URL.createObjectURL(blob);
    
    const head = document.querySelector('head');
    head.insertAdjacentHTML('beforeend', `<link rel="manifest" href="${manifestURL}">`);
    head.insertAdjacentHTML('beforeend', `<meta name="theme-color" content="#4F46E5">`);
    head.insertAdjacentHTML('beforeend', `<link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/3135/3135810.png">`);
</script>
""", height=0)

# ==========================================
# 2. CARGA DE SISTEMAS EN MEMORIA (CACHE)
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
# 3. FUNCIONES DEL TUTOR (Adaptadas para Web)
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

def generar_respuesta(perfil, porcentaje_exito, pregunta):
    # 1. Buscar en los apuntes
    vector_pregunta = modelo_vectores.encode(pregunta).tolist()
    resultados = supabase.rpc("match_contenido_curricular", {
        "query_embedding": vector_pregunta, "match_threshold": 0.3, "match_count": 1 
    }).execute()

    if not resultados.data:
        return "Lo siento, ese tema aún no está en mis apuntes de clase. ¿Por qué no lo anotas para discutirlo en nuestra próxima sesión presencial?"

    texto_oficial = resultados.data[0]["contenido_texto"]
    contenido_id = resultados.data[0]["id"]

    # 2. Adaptar la personalidad
    instrucciones = "Eres un tutor pedagógico de apoyo. Usa el método socrático (guía, no des respuestas directas)."
    if porcentaje_exito < 40 or perfil['nivel_general'] == 1:
        instrucciones += " ADAPTACIÓN: El alumno tiene dificultades. Usa analogías simples, lenguaje muy sencillo y sé muy empático."
    elif porcentaje_exito > 80 or perfil['nivel_general'] >= 4:
        instrucciones += " ADAPTACIÓN: El alumno es avanzado. Usa lenguaje académico y lánzale un reto intelectual al final."

    prompt_maestro = f"{instrucciones}\n\nSOLO USA ESTA INFO OFICIAL:\n{texto_oficial}\n\nPREGUNTA DEL ALUMNO:\n{pregunta}"

    # 3. Consultar a la IA
    respuesta_ia = cliente_groq.chat.completions.create(
        messages=[{"role": "user", "content": prompt_maestro}],
        model="llama-3.1-8b-instant",
        temperature=0.7
    )
    
    # 4. Guardar interacción
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

# Encabezado principal
st.title("🦉 Tutor Inteligente")
st.markdown("<p style='font-size: 1.1rem; color: #4B5563;'>Tu acompañante para el modelo de alternancia.</p>", unsafe_allow_html=True)
st.divider()

# Panel lateral para iniciar sesión y métricas
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4200/4200465.png", width=80) # Icono decorativo
    st.header("Identificación")
    correo_input = st.text_input("Ingresa tu correo estudiantil:")
    
    if correo_input:
        perfil, exito = obtener_perfil(correo_input)
        if perfil:
            st.session_state['usuario_valido'] = True
            st.session_state['perfil'] = perfil
            st.session_state['exito'] = exito
            
            # Tarjeta de bienvenida
            st.markdown(f"### 👋 Hola, {perfil['nombre']}")
            
            # Métricas en columnas para que se vean como un "Dashboard"
            col1, col2 = st.columns(2)
            col1.metric("Nivel", f"Lvl {perfil['nivel_general']}")
            col2.metric("Aciertos", f"{int(exito)}%")
            
            # Barra de progreso visual del rendimiento
            st.caption("Rendimiento reciente:")
            st.progress(int(exito) / 100)
            
            st.divider()
            st.caption("🟢 Conectado al entorno de aprendizaje")
            
        else:
            st.error("Correo no encontrado. Consulta con el profesor.")
            st.session_state['usuario_valido'] = False

# Sistema de Chat
if st.session_state.get('usuario_valido', False):
    
    # Mensaje de bienvenida inicial en el chat
    if "mensajes" not in st.session_state:
        st.session_state.mensajes = [{"role": "assistant", "content": f"¡Hola {st.session_state['perfil']['nombre']}! ¿Qué tema de la clase te gustaría repasar hoy?"}]

    # Mostrar historial de mensajes con AVATARES
    for mensaje in st.session_state.mensajes:
        # Asignamos un icono según quién hable
        avatar_icon = "🧑‍🎓" if mensaje["role"] == "user" else "🦉"
        with st.chat_message(mensaje["role"], avatar=avatar_icon):
            st.markdown(mensaje["content"])

    # Caja de texto flotante en la parte inferior
    if pregunta := st.chat_input("Escribe tu duda aquí (ej: ¿Qué es la mitocondria?)..."):
        
        # Mostrar mensaje del usuario
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(pregunta)
        st.session_state.mensajes.append({"role": "user", "content": pregunta})

        # Mostrar "Escribiendo..." y generar respuesta
        with st.chat_message("assistant", avatar="🦉"):
            with st.spinner("Revisando los apuntes de la clase..."):
                respuesta = generar_respuesta(st.session_state['perfil'], st.session_state['exito'], pregunta)
                st.markdown(respuesta)
        
        # Guardar respuesta
        st.session_state.mensajes.append({"role": "assistant", "content": respuesta})

else:
    # Pantalla de espera cuando no ha iniciado sesión
    st.markdown("""
    <div class="info-card">
        <h4>🔒 Acceso Restringido</h4>
        <p>Por favor, usa el <b>panel izquierdo</b> para ingresar tu correo estudiantil y desbloquear el tutor.</p>
        <p><i>💡 Tip de prueba: Usa <code>carlos.mendoza@ejemplo.com</code></i></p>
    </div>
    """, unsafe_allow_html=True)