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
st.set_page_config(page_title="Portal Educativo - Alternancia", page_icon="🏫", layout="centered")

# --- VARIABLE DE BRANDING (Pon aquí el link de tu logo) ---
URL_LOGO_COLEGIO = "https://images.leadconnectorhq.com/image/f_webp/q_80/r_1200/u_https://assets.cdn.filesafe.space/CqwkTEZZmpZXlnX4iVPm/media/7da16945-4101-474d-8992-326abe631293.png" 

# ==========================================
# 1.5 INYECCIÓN PWA (App Instalable para Celulares)
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
            "icons": [
                {
                    "src": "https://cdn-icons-png.flaticon.com/512/167/167707.png",
                    "sizes": "512x512",
                    "type": "image/png"
                }
            ]
        };
        
        const blob = new Blob([JSON.stringify(manifest)], {type: 'application/json'});
        const manifestURL = URL.createObjectURL(blob);
        
        const oldLink = parentDoc.querySelector('link[rel="manifest"]');
        if(oldLink) oldLink.remove();

        parentDoc.head.insertAdjacentHTML('beforeend', `<link rel="manifest" href="${manifestURL}">`);
        parentDoc.head.insertAdjacentHTML('beforeend', `<meta name="theme-color" content="#1E3A8A">`);
        parentDoc.head.insertAdjacentHTML('beforeend', `<link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/167/167707.png">`);

        let installBtn = parentDoc.getElementById('btn-instalar-pwa');
        if (!installBtn) {
            installBtn = parentDoc.createElement('button');
            installBtn.id = 'btn-instalar-pwa';
            installBtn.innerHTML = '📲 Instalar App del Colegio';
            installBtn.style.cssText = 'position: fixed; bottom: 30px; right: 30px; z-index: 999999; background-color: #1E3A8A; color: white; border: none; border-radius: 50px; padding: 14px 24px; font-size: 16px; font-weight: bold; box-shadow: 0 4px 12px rgba(0,0,0,0.3); cursor: pointer; display: none; transition: all 0.3s ease; font-family: sans-serif;';
            
            installBtn.onmouseover = () => installBtn.style.transform = 'scale(1.05)';
            installBtn.onmouseout = () => installBtn.style.transform = 'scale(1)';
            
            parentDoc.body.appendChild(installBtn);
        }

        let deferredPrompt;
        parentWin.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            installBtn.style.display = 'block';
        });

        installBtn.addEventListener('click', async () => {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                if (outcome === 'accepted') {
                    installBtn.style.display = 'none';
                }
                deferredPrompt = null;
            }
        });

        parentWin.addEventListener('appinstalled', () => {
            installBtn.style.display = 'none';
        });

    } catch (e) {
        console.log("Restricción de navegador detectada.");
    }
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
    vector_pregunta = modelo_vectores.encode(pregunta).tolist()
    resultados = supabase.rpc("match_contenido_curricular", {
        "query_embedding": vector_pregunta, "match_threshold": 0.3, "match_count": 1 
    }).execute()

    if not resultados.data:
        return "Lo siento, ese tema aún no está en los apuntes oficiales de la institución. ¿Por qué no lo anotas para discutirlo con el docente en la próxima sesión presencial?"

    texto_oficial = resultados.data[0]["contenido_texto"]
    contenido_id = resultados.data[0]["id"]

    instrucciones = "Eres un tutor pedagógico de apoyo institucional. Usa el método socrático (guía, no des respuestas directas)."
    if porcentaje_exito < 40 or perfil['nivel_general'] == 1:
        instrucciones += " ADAPTACIÓN: El alumno tiene dificultades. Usa analogías simples, lenguaje muy sencillo y sé muy empático."
    elif porcentaje_exito > 80 or perfil['nivel_general'] >= 4:
        instrucciones += " ADAPTACIÓN: El alumno es avanzado. Usa lenguaje académico y lánzale un reto intelectual al final."

    prompt_maestro = f"{instrucciones}\n\nSOLO USA ESTA INFO OFICIAL:\n{texto_oficial}\n\nPREGUNTA DEL ALUMNO:\n{pregunta}"

    respuesta_ia = cliente_groq.chat.completions.create(
        messages=[{"role": "user", "content": prompt_maestro}],
        model="llama-3.1-8b-instant",
        temperature=0.7
    )
    
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

# Encabezado principal institucional
st.title("🏫 Portal Educativo - Tutor IA")
st.markdown("<p style='font-size: 1.1rem; color: #4B5563;'>Bienvenido al entorno virtual de aprendizaje de tu Institución.</p>", unsafe_allow_html=True)
st.divider()

# Panel lateral para iniciar sesión y métricas
with st.sidebar:
    # Usamos la variable del logo aquí
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
            
            st.caption("Rendimiento reciente:")
            st.progress(int(exito) / 100)
            
            st.divider()
            st.caption("🟢 Conectado a la base de datos del colegio")
            
        else:
            st.error("Correo no encontrado en el sistema. Consulta con tu profesor.")
            st.session_state['usuario_valido'] = False

    # ==========================================
    # GUÍA MANUAL DE INSTALACIÓN
    # ==========================================
    st.divider()
    with st.expander("📲 Instalar App del Colegio"):
        st.markdown("""
        **Si tienes Android:**
        1. Toca el botón flotante **"Instalar App del Colegio"** abajo a la derecha. 
        2. *(Si no aparece, toca los 3 puntitos del navegador arriba a la derecha y selecciona "Instalar aplicación")*.
        
        **Si tienes iPhone (Apple):**
        1. Toca el botón **Compartir** (cuadrado con flecha hacia arriba).
        2. Desliza hacia abajo y selecciona ➕ **Agregar a inicio**.
        3. Toca en "Agregar".
        """)

# Sistema de Chat
if st.session_state.get('usuario_valido', False):
    
    if "mensajes" not in st.session_state:
        st.session_state.mensajes = [{"role": "assistant", "content": f"¡Hola {st.session_state['perfil']['nombre']}! Soy el Tutor IA oficial del colegio. ¿Qué tema de nuestra clase te gustaría repasar hoy?"}]

    # Mostrar historial de mensajes
    for mensaje in st.session_state.mensajes:
        # Aquí asignamos el logo del colegio a la IA para que se vea más profesional
        avatar_icon = "🧑‍🎓" if mensaje["role"] == "user" else URL_LOGO_COLEGIO
        with st.chat_message(mensaje["role"], avatar=avatar_icon):
            st.markdown(mensaje["content"])

    if pregunta := st.chat_input("Escribe tu duda aquí (ej: ¿Cuáles son las partes de la célula?)..."):
        
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(pregunta)
        st.session_state.mensajes.append({"role": "user", "content": pregunta})

        # Mostrar "Escribiendo..." con el logo del colegio
        with st.chat_message("assistant", avatar=URL_LOGO_COLEGIO):
            with st.spinner("Revisando los apuntes oficiales..."):
                respuesta = generar_respuesta(st.session_state['perfil'], st.session_state['exito'], pregunta)
                st.markdown(respuesta)
        
        st.session_state.mensajes.append({"role": "assistant", "content": respuesta})

else:
    st.markdown("""
    <div class="info-card">
        <h4>🔒 Portal de Acceso Restringido</h4>
        <p>Por favor, usa el <b>panel izquierdo</b> para ingresar tu correo y desbloquear tus herramientas de estudio.</p>
        <p><i>💡 Tip de prueba: Usa <code>carlos.mendoza@ejemplo.com</code></i></p>
    </div>
    """, unsafe_allow_html=True)