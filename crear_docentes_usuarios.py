import hashlib
import re
from config.db_connection import get_connection

def hash_data(data):
    return hashlib.sha256(str(data).encode()).hexdigest()

def generar_correo_unah(nombre, id_docente):
    """
    Genera un correo institucional simulado basado en el nombre del docente.
    Ejemplo: 'Ing. Carlos Ramos' -> 'carlosramos2@unah.hn'
    """
    # Quitamos títulos como "Ing.", espacios y caracteres especiales
    clean_name = re.sub(r'[^a-zA-Z]', '', nombre.replace('Ing.', '').replace('Ing', '')).lower()
    return f"{clean_name}{id_docente}@unah.hn"

def crear_cuentas_docentes():
    conn = get_connection()
    if not conn:
        print("❌ Error de conexión a la base de datos.")
        return

    cursor = conn.cursor(dictionary=True)

    print("🔍 Buscando docentes en el catálogo...")
    cursor.execute("SELECT ID_Docente, Nombre FROM docentes_activos")
    docentes = cursor.fetchall()

    if not docentes:
        print("⚠️ No hay docentes registrados en la tabla 'docentes_activos'.")
        conn.close()
        return

    # Contraseña estándar para todos los docentes durante la fase de pruebas
    pass_hash = hash_data('docente123') 
    agregados = 0

    print("🚀 Generando credenciales de acceso...")
    for doc in docentes:
        nombre_exacto = doc['Nombre']
        correo = generar_correo_unah(nombre_exacto, doc['ID_Docente'])
        cuenta_hash = hash_data(correo)

        # Verificar si ya se le creó un usuario previamente
        cursor.execute("SELECT * FROM usuarios WHERE Nombre_Completo = %s", (nombre_exacto,))
        if cursor.fetchone():
            print(f"⏩ {nombre_exacto} ya tiene cuenta de usuario. Saltando...")
            continue

        try:
            # Insertar en la tabla de login con el rol correcto
            cursor.execute("""
                INSERT INTO usuarios (Hash_Cuenta, Nombre_Completo, Correo_Institucional, Contrasena, Rol) 
                VALUES (%s, %s, %s, %s, 'Docente')
            """, (cuenta_hash, nombre_exacto, correo, pass_hash))
            
            agregados += 1
            print(f"✅ Cuenta creada -> Docente: {nombre_exacto} | Correo: {correo}")
        except Exception as e:
            print(f"❌ Error al crear cuenta para {nombre_exacto}: {e}")

    conn.commit()
    conn.close()
    
    print("\n" + "="*50)
    print(f"🎉 Proceso finalizado. Se crearon {agregados} cuentas nuevas para docentes.")
    print("🔑 LA CONTRASEÑA PARA TODOS ES: docente123")
    print("="*50)

if __name__ == '__main__':
    crear_cuentas_docentes()