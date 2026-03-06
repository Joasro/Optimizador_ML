from config.db_connection import get_connection

def limpiar_todo():
    conn = get_connection()
    if not conn:
        print("❌ Error de conexión")
        return
    
    cursor = conn.cursor()
    
    print("⚠️  Iniciando limpieza profunda...")
    
    # Desactivamos llaves foráneas para evitar conflictos de integridad temporalmente
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    # 1. ELIMINAR ESTUDIANTES Y SUS REGISTROS
    print("👥 Eliminando registros de estudiantes (Historial, Censo, Perfiles)...")
    cursor.execute("TRUNCATE TABLE Historial_Academico;")
    cursor.execute("TRUNCATE TABLE Censo_Periodo_Actual;")
    cursor.execute("TRUNCATE TABLE Estudiantes;")
    # Solo borramos usuarios con rol Estudiante para proteger tu Admin
    cursor.execute("DELETE FROM Usuarios WHERE Rol = 'Estudiante';")
    
    # 2. ELIMINAR CLASES DEL PLAN NUEVO
    # Ajusta '2024' si el plan que quieres borrar tiene otro nombre en tu tabla
    plan_erroneo = '2024' 
    print(f"📚 Eliminando clases de la malla del plan: {plan_erroneo}...")
    cursor.execute("DELETE FROM Malla_Curricular WHERE Plan_Perteneciente = %s", (plan_erroneo,))
    
    # 3. OPCIONAL: Limpiar oferta generada si ya habías hecho pruebas
    cursor.execute("TRUNCATE TABLE Oferta_Academica_Generada;")
    
    # Reactivamos las restricciones
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    
    conn.commit()
    conn.close()
    print("✅ ¡Listo! La base de datos ha sido purgada de estudiantes y de la malla errónea.")

if __name__ == '__main__':
    confirmacion = input("¿Estás seguro de que deseas eliminar TODOS los estudiantes y las clases del plan nuevo? (s/n): ")
    if confirmacion.lower() == 's':
        limpiar_todo()
    else:
        print("Operación cancelada.")