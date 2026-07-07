import os
from dotenv import load_dotenv
from google import genai

# Forzamos a que lea el archivo .env
load_dotenv()

llave = os.environ.get("GEMINI_API_KEY")

print(f"1. La llave que Python está leyendo empieza con: {llave[:10]}...")
print(f"2. La llave tiene un largo de: {len(llave)} caracteres.")

if not llave or " " in llave or '"' in llave:
    print("❌ ERROR VISUAL: Tu llave tiene espacios en blanco o comillas. Por favor quítalos del archivo .env.")
else:
    print("3. Intentando conectar a Google...")
    try:
        cliente = genai.Client(api_key=llave)
        respuesta = cliente.models.generate_content(
            model='gemini-2.5-flash',
            contents='Di "Hola, tu llave funciona perfecto".'
        )
        print(f"✅ CONEXIÓN EXITOSA: {respuesta.text}")
    except Exception as e:
        print(f"❌ FALLO LA CONEXIÓN A GOOGLE: {e}")