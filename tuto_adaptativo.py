import os
from dotenv import load_dotenv
from supabase import create_client, Client
from groq import Groq
from sentence_transformers import SentenceTransformer

# ==========================================
# 1. CONFIGURACIÓN INICIAL
# ==========================================
load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# NOTA: Reemplaza "gsk_..." por tu llave real si el archivo .env sigue fallando
cliente_groq = Groq(api_key=os.environ.get("GROQ_API_KEY")) 
modelo_vectores = SentenceTransformer('all-MiniLM-L6-v2')


# ==========================================
# 2. EL MOTOR DE ADAPTABILIDAD
# ==========================================
def obtener_perfil_y_historial(correo_estudiante: str):
    """Busca al estudiante y calcula su porcentaje de éxito reciente."""
    # A. Buscar perfil
    respuesta_perfil = supabase.table("estudiantes").select("*").eq("correo", correo_estudiante).execute()
    if not respuesta_perfil.data:
        return None, 0
    
    perfil = respuesta_perfil.data[0]
    estudiante_id = perfil['id']

    # B. Analizar historial (Últimas 5 interacciones)
    respuesta_historial = supabase.table("historial_aprendizaje").select("fue_exitoso").eq("estudiante_id", estudiante_id).order("fecha_interaccion", desc=True).limit(5).execute()
    
    if not respuesta_historial.data:
        return perfil, 50 # Si es nuevo, asumimos un éxito medio del 50%
        
    exitos = sum(1 for item in respuesta_historial.data if item['fue_exitoso'])
    total_interacciones = len(respuesta_historial.data)
    porcentaje_exito = (exitos / total_interacciones) * 100
    
    return perfil, porcentaje_exito

def construir_prompt_adaptativo(perfil, porcentaje_exito, texto_oficial, pregunta):
    """Aquí ocurre la magia: Modificamos la personalidad del tutor según el nivel del alumno."""
    
    # 1. Base del comportamiento socrático
    instrucciones_pedagogicas = """
    Eres un tutor de apoyo para estudiantes en un modelo de alternancia.
    Tu objetivo principal NO es dar la respuesta directa, sino guiar al estudiante a entender el concepto por sí mismo.
    Usa el método socrático: hazle una pregunta de vuelta para que él piense.
    """

    # 2. ADAPTABILIDAD SEGÚN EL NIVEL Y RENDIMIENTO
    if porcentaje_exito < 40 or perfil['nivel_general'] == 1:
        # El alumno está teniendo dificultades
        instrucciones_pedagogicas += """
        \nADAPTACIÓN DE NIVEL: El estudiante está teniendo grandes dificultades con este tema.
        ESTRATEGIA: 
        1. Sé extremadamente empático y motivador.
        2. Usa analogías muy simples de la vida cotidiana (ej: deportes, comida, videojuegos).
        3. Explica paso a pasito, como si le hablaras a un niño inteligente de 10 años.
        4. Evita el vocabulario técnico en lo posible.
        """
    elif porcentaje_exito > 80 or perfil['nivel_general'] >= 4:
        # El alumno domina el tema
        instrucciones_pedagogicas += """
        \nADAPTACIÓN DE NIVEL: El estudiante es avanzado y domina el tema.
        ESTRATEGIA:
        1. Usa un lenguaje más técnico y académico.
        2. No te detengas en las bases, ve al grano.
        3. Al final de tu explicación, lánzale un pequeño reto mental o una pregunta difícil relacionada con el tema para llevarlo al siguiente nivel.
        """
    else:
        # El alumno va a un ritmo normal
        instrucciones_pedagogicas += "\nADAPTACIÓN DE NIVEL: El estudiante tiene un nivel intermedio. Explica de forma clara y directa."

    # 3. Ensamblar el Prompt Final
    prompt_final = f"""
    {instrucciones_pedagogicas}
    
    REGLA DE ORO: Solo puedes usar la siguiente información oficial de la clase para responder. Si la respuesta no está ahí, dile cortésmente que lo discuta en la próxima clase presencial.

    INFORMACIÓN DE LA CLASE:
    {texto_oficial}

    PREGUNTA DEL ESTUDIANTE:
    {pregunta}
    """
    return prompt_final


# ==========================================
# 3. LA FUNCIÓN PRINCIPAL
# ==========================================
def tutor_interactivo(correo_estudiante: str, pregunta: str):
    """Función principal que orquesta todo el flujo."""
    print(f"\n--- Iniciando sesión para: {correo_estudiante} ---")
    
    # 1. Obtener datos del alumno
    perfil, porcentaje_exito = obtener_perfil_y_historial(correo_estudiante)
    if not perfil:
        print("❌ Estudiante no encontrado en la base de datos.")
        return
    
    print(f"📊 Análisis: Nivel {perfil['nivel_general']} | Tasa de éxito reciente: {porcentaje_exito}%")
    print("🔍 Buscando en los apuntes de clase...")

    # 2. Buscar en los apuntes (RAG)
    vector_pregunta = modelo_vectores.encode(pregunta).tolist()
    resultados = supabase.rpc("match_contenido_curricular", {
        "query_embedding": vector_pregunta,
        "match_threshold": 0.3, "match_count": 1 
    }).execute()

    if not resultados.data:
        print("🤖 Tutor: Lo siento, ese tema aún no está en mis apuntes. ¿Lo revisamos en presencialidad?")
        return

    texto_oficial = resultados.data[0]["contenido_texto"]
    contenido_id = resultados.data[0]["id"]

    # 3. Generar la respuesta ADAPTATIVA
    print("🧠 Calculando la mejor forma de explicarle a este alumno...")
    prompt_maestro = construir_prompt_adaptativo(perfil, porcentaje_exito, texto_oficial, pregunta)

    respuesta_ia = cliente_groq.chat.completions.create(
        messages=[{"role": "user", "content": prompt_maestro}],
        model="llama-3.1-8b-instant",
        temperature=0.7 # Un poco de creatividad
    )
    
    respuesta_final = respuesta_ia.choices[0].message.content
    print("\n🤖 TUTOR DICE:\n" + "="*50)
    print(respuesta_final)
    print("="*50)

    # 4. Guardar la interacción en el historial (Simulamos que el alumno lo entendió)
    supabase.table("historial_aprendizaje").insert({
        "estudiante_id": perfil['id'],
        "contenido_id": contenido_id,
        "fue_exitoso": True, # En la app real, esto lo marcaría el estudiante
        "observaciones": "Interacción autónoma completada"
    }).execute()
    print("\n✅ Interacción guardada en el historial para futuras adaptaciones.")

# ==========================================
# ZONA DE PRUEBAS
# ==========================================
if __name__ == "__main__":
    # Recuerda que en db_manager.py creamos a "Carlos Mendoza" con correo "carlos.mendoza@ejemplo.com"
    # Al ser nuevo, el sistema asumirá un nivel intermedio.
    
    correo_prueba = "carlos.mendoza@ejemplo.com"
    pregunta_prueba = "¿Para qué sirve exactamente la mitocondria en la célula?"
    
    tutor_interactivo(correo_prueba, pregunta_prueba)