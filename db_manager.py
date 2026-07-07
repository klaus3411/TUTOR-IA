import os
from dotenv import load_dotenv
from supabase import create_client, Client

class TutorDatabaseManager:
    """
    Clase encargada de gestionar todas las conexiones y operaciones 
    con la base de datos del Tutor IA.
    """
    def __init__(self):
        # 1. Cargar las variables de entorno desde el archivo .env
        load_dotenv()
        
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("Faltan credenciales de Supabase en el archivo .env")
        
        # 2. Inicializar el cliente de Supabase
        self.supabase: Client = create_client(url, key)
        print("✅ Conexión establecida con la Base de Datos del Tutor.")

    # --- FUNCIONES DE GESTIÓN DE ESTUDIANTES ---

    def registrar_estudiante(self, nombre: str, correo: str) -> dict:
        """Registra un nuevo estudiante en la base de datos."""
        try:
            data = {
                "nombre": nombre,
                "correo": correo,
                "estilo_aprendizaje": "indefinido",
                "nivel_general": 1
            }
            # Insertar en la tabla 'estudiantes'
            respuesta = self.supabase.table("estudiantes").insert(data).execute()
            print(f"Estudiante {nombre} registrado con éxito.")
            return respuesta.data[0]
        except Exception as e:
            print(f"❌ Error al registrar estudiante: {e}")
            return None

    def obtener_perfil_estudiante(self, correo: str) -> dict:
        """Busca y retorna el perfil de un estudiante por su correo."""
        try:
            respuesta = self.supabase.table("estudiantes").select("*").eq("correo", correo).execute()
            if respuesta.data:
                return respuesta.data[0]
            else:
                print("Estudiante no encontrado.")
                return None
        except Exception as e:
            print(f"❌ Error al buscar estudiante: {e}")
            return None

    # --- FUNCIONES DE HISTORIAL DE APRENDIZAJE ---

    def registrar_interaccion(self, estudiante_id: str, contenido_id: str, exitoso: bool, tiempo_segundos: int, observaciones: str = "") -> bool:
        """
        Guarda cómo le fue al estudiante en una lección específica.
        Esto es lo que la IA leerá luego para adaptarse.
        """
        try:
            data = {
                "estudiante_id": estudiante_id,
                "contenido_id": contenido_id,
                "fue_exitoso": exitoso,
                "tiempo_invertido_segundos": tiempo_segundos,
                "observaciones": observaciones
            }
            self.supabase.table("historial_aprendizaje").insert(data).execute()
            print("Interacción guardada en el historial.")
            return True
        except Exception as e:
            print(f"❌ Error al guardar historial: {e}")
            return False

# ==========================================
# ZONA DE PRUEBAS (Para validar que funciona)
# ==========================================
if __name__ == "__main__":
    # Instanciamos nuestro gestor
    db = TutorDatabaseManager()

    # 1. Prueba: Crear un estudiante de prueba
    estudiante_prueba = db.registrar_estudiante(
        nombre="Carlos Mendoza", 
        correo="carlos.mendoza@ejemplo.com"
    )
    
    # 2. Prueba: Leer los datos del estudiante creado
    if estudiante_prueba:
        perfil = db.obtener_perfil_estudiante("carlos.mendoza@ejemplo.com")
        print("\n--- Datos Recuperados de la BD ---")
        print(f"Nombre: {perfil['nombre']}")
        print(f"Nivel Actual: {perfil['nivel_general']}")
        print(f"ID en Base de datos: {perfil['id']}")