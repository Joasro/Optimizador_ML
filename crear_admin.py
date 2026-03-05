import hashlib
import sys
import os
# Añadir la ruta para encontrar la conexión
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from config.db_connection import get_connection

def crear():
    print("🛡️ Configuración de Super Administrador")
    nombre = input("Tu nombre completo: ")
    correo = input("Tu correo (ej: joaquin@unah.hn): ")
    password = input("Tu contraseña: ")
    
    # El sistema hace la encriptación automáticamente
    h_pass = hashlib.sha256(password.encode()).hexdigest()
    # Para el admin, usaremos el hash del correo como ID de cuenta único
    h_cuenta = hashlib.sha256(correo.encode()).hexdigest()

    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        try:
            sql = """INSERT INTO Usuarios (Hash_Cuenta, Nombre_Completo, Correo_Institucional, Contrasena, Rol) 
                     VALUES (%s, %s, %s, %s, 'Admin')"""
            cursor.execute(sql, (h_cuenta, nombre, correo, h_pass))
            conn.commit()
            print(f"\n✅ ¡Éxito! Usuario '{nombre}' creado como Admin.")
            print(f"Ya puedes entrar a la web con el correo: {correo}")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    crear()