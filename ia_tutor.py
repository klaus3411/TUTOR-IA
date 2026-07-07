import os
from dotenv import load_dotenv
from supabase import create_client, Client
from groq import Groq
from sentence_transformers import SentenceTransformer

# 1. Cargar configuraciones
load_dotenv()
supabase: Client = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))

# 2. Configurar el Tutor (Llama 3 vía Groq)
cliente_groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# 3. Configurar el "Vectorizador" Local (Se descargará una vez y funcionará offline)
# Usamos un modelo ligero y muy rápido de 384 dimensiones
modelo_vectores = SentenceTransformer('all-MiniLM-L6-v2')

def subir_clase_al_cerebro(tema: str, subtema: str, texto_clase: str, nivel: int):
    print(f"Procesando clase: {tema}...")
    try:
        # A. Crear el vector localmente
        vector_matematico = modelo_vectores.encode(texto_clase).tolist()

        # B. Guardar en Supabase
        data = {
            "tema": tema,
            "subtema": subtema,
            "contenido_texto": texto_clase,
            "nivel_dificultad": nivel,
            "embedding": vector_matematico
        }
        supabase.table("contenido_curricular").insert(data).execute()
        print(f"✅ ¡Clase '{tema}' guardada exitosamente!")
        
    except Exception as e:
        print(f"❌ Error al guardar en base de datos: {e}")

def preguntar_al_tutor(pregunta: str):
    print(f"\nEstudiante pregunta: {pregunta}")
    try:
        # A. Convertir la pregunta a vector localmente
        vector_pregunta = modelo_vectores.encode(pregunta).tolist()

        # B. Buscar en Supabase
        resultados = supabase.rpc(
            "match_contenido_curricular",
            {
                "query_embedding": vector_pregunta,
                "match_threshold": 0.3, 
                "match_count": 1 
            }
        ).execute()

        if not resultados.data:
            print("🤖 Tutor: Lo siento, ese tema aún no está en mis apuntes de clase.")
            return

        texto_oficial = resultados.data[0]["contenido_texto"]

        # C. Diseñar el Prompt
        prompt = f"""
        Eres un tutor de apoyo para estudiantes en alternancia. 
        Tu objetivo NO es dar la respuesta directa, sino guiar al estudiante a entender el concepto.
        
        REGLA DE ORO: Solo puedes usar la siguiente información oficial de la clase para responder.
        Si la respuesta no está aquí, dile que debe consultarlo con el profesor.

        INFORMACIÓN DE LA CLASE:
        {texto_oficial}

        PREGUNTA DEL ESTUDIANTE:
        {pregunta}
        """

        # D. Consultar a Llama-3 a través de Groq
        respuesta_ia = cliente_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": "Eres un tutor pedagógico."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant", # Modelo rapidísimo y excelente para texto
        )
        
        print("\n🤖 Respuesta del Tutor (Llama 3):")
        print(respuesta_ia.choices[0].message.content)
        
    except Exception as e:
        print(f"❌ Error al consultar: {e}")

# ==========================================
# ZONA DE PRUEBAS
# ==========================================
if __name__ == "__main__":
    texto_mitocondria = "La mitocondria es conocida como la central energética de la célula. Su función principal es producir energía en forma de ATP a través de la respiración celular."
    
    # PASO 1: Subimos la clase (Asegúrate de correr el nuevo SQL antes)
    subir_clase_al_cerebro("Biología", "La Célula", texto_mitocondria, 2)

    # PASO 2: Comenta la de arriba y descomenta esta para preguntar
    preguntar_al_tutor("Profe, ¿qué hace exactamente la mitocondria? ¿Me lo explicas fácil?")