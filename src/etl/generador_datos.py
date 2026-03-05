import sys
import os
import hashlib
import random

# Configuración de rutas para encontrar 'config'
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from config.db_connection import get_connection

def hash_data(data):
    return hashlib.sha256(str(data).encode()).hexdigest()

def ejecutar():
    conn = get_connection()
    if not conn:
        print("❌ Error de conexión")
        return
    
    cursor = conn.cursor(dictionary=True)
    
    # Limpieza total
    print("🧹 Limpiando tablas...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("TRUNCATE TABLE Historial_Academico;")
    cursor.execute("TRUNCATE TABLE Usuarios;")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    cursor.execute("SELECT ID_Clase, Plan_Perteneciente FROM Malla_Curricular")
    malla = cursor.fetchall()
    c21 = [c['ID_Clase'] for c in malla if c['Plan_Perteneciente'] == '2021']
    c24 = [c['ID_Clase'] for c in malla if c['Plan_Perteneciente'] == '2024']

    # Distribución de los 67 estudiantes
    perfiles = [
        {'plan': '2024', 'n': 15, 'clases': (3, 10)},
        {'plan': '2024', 'n': 15, 'clases': (12, 25)},
        {'plan': '2021', 'n': 27, 'clases': (25, 40)},
        {'plan': '2021', 'n': 10, 'clases': (45, 53)}
    ]

    print("🚀 Generando 67 estudiantes...")
    pass_hash = hash_data('unah123')
    
    idx = 1
    for p in perfiles:
        pool = c24 if p['plan'] == '2024' else c21
        for _ in range(p['n']):
            cuenta = 20201000000 + idx
            h_cuenta = hash_data(cuenta)
            
            # Insertar Usuario
            cursor.execute("INSERT INTO Usuarios (Hash_Cuenta, Rol, Plan_Estudio_Inferido, Nombre_Completo, Password_Hashed) VALUES (%s, %s, %s, %s, %s)", 
                           (h_cuenta, 'Estudiante', p['plan'], f"Estudiante {idx}", pass_hash))
            
            # Insertar Historial
            n_clases = random.randint(p['clases'][0], p['clases'][1])
            seleccion = random.sample(pool, min(n_clases, len(pool)))
            for id_c in seleccion:
                estado = 'Aprobado' if random.random() < 0.85 else 'Reprobado'
                cursor.execute("INSERT INTO Historial_Academico (Hash_Cuenta, ID_Clase, Estado) VALUES (%s, %s, %s)", 
                               (h_cuenta, id_c, estado))
            idx += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ Éxito total: 67 estudiantes creados.")

if __name__ == "__main__":
    ejecutar()