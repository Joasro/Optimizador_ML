import hashlib
import random
import sys
import os
from config.db_connection import get_connection

def hash_data(data):
    return hashlib.sha256(str(data).encode()).hexdigest()

def evaluar_prerrequisitos_simulador(req_text, nombre_clase, ids_aprobados, total_uv, mapa_codes):
    """Evalúa estrictamente si el estudiante virtual puede llevar una materia."""
    req_lower = str(req_text).lower() if req_text else ""
    nombre_lower = str(nombre_clase).lower()
    
    # Candado de Seminario (140 UV)
    if "seminario" in nombre_lower or "140" in req_lower:
        if total_uv < 140:
            return False
            
    if req_lower in ['ninguno', 'nan', 'null', '']:
        return True
        
    clases_requeridas = [r.strip().upper() for r in req_text.split(',') if "140" not in r]
    
    for code in clases_requeridas:
        req_id = mapa_codes.get(code)
        if req_id and req_id not in ids_aprobados:
            return False 
            
    return True

def ejecutar():
    conn = get_connection()
    if not conn:
        print("❌ Error de conexión")
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("🧹 Limpiando base de datos (protegiendo cuentas de Admin)...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("TRUNCATE TABLE Historial_Academico;")
    cursor.execute("TRUNCATE TABLE Estudiantes;")
    cursor.execute("DELETE FROM Usuarios WHERE Rol = 'Estudiante';")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    print("📖 Analizando Malla Curricular...")
    cursor.execute("""
        SELECT ID_Clase, Codigo_Oficial, Nombre_Clase, Unidades_Valorativas, 
               Plan_Perteneciente, Prerrequisitos 
        FROM Malla_Curricular
    """)
    malla = cursor.fetchall()

    perfiles = [
        {'plan': '2024', 'n': 10, 'inicio': 2025},
        {'plan': '2024', 'n': 15, 'inicio': 2024},
        {'plan': '2024', 'n': 10, 'inicio': 2023},
        {'plan': '2021', 'n': 17, 'inicio': 2022},
        {'plan': '2021', 'n': 15, 'inicio': 2021} 
    ]

    print("🚀 Simulando trayectorias académicas con prioridad en clases IS...")
    
    pass_hash = hash_data('admin123') 
    est_idx = 1

    for p in perfiles:
        clases_del_plan = [c for c in malla if c['Plan_Perteneciente'] == p['plan']]
        
        mapa_codes = {c['Codigo_Oficial'].strip().upper(): c['ID_Clase'] for c in clases_del_plan}
        
        for _ in range(p['n']):
            num_cuenta = (p['inicio'] * 100000) + est_idx
            correo_est = f"estudiante{num_cuenta}@unah.hn"
            nombre_est = f"Estudiante {est_idx}"
            cuenta_hash = hash_data(correo_est) 
            
            cursor.execute("""
                INSERT INTO Usuarios (Hash_Cuenta, Nombre_Completo, Correo_Institucional, Contrasena, Rol) 
                VALUES (%s, %s, %s, %s, 'Estudiante')
            """, (cuenta_hash, nombre_est, correo_est, pass_hash))
            
            cursor.execute("""
                INSERT INTO Estudiantes (Hash_Cuenta, Plan_Estudio, Ano_Ingreso) 
                VALUES (%s, %s, %s)
            """, (cuenta_hash, p['plan'], p['inicio']))
            
            clases_aprobadas = set() 
            total_uv_acumuladas = 0
            ano_sim = p['inicio']
            periodo_sim = 1
            
            while ano_sim < 2026 or (ano_sim == 2026 and periodo_sim <= 1):
                disponibles = []
                
                for c in clases_del_plan:
                    if c['ID_Clase'] not in clases_aprobadas:
                        if evaluar_prerrequisitos_simulador(c['Prerrequisitos'], c['Nombre_Clase'], clases_aprobadas, total_uv_acumuladas, mapa_codes):
                            disponibles.append(c)
                
                if not disponibles: 
                    break
                
                # --- SISTEMA DE PRIORIDAD DE MATRÍCULA ---
                is_clases = [c for c in disponibles if c['Codigo_Oficial'].upper().startswith('IS')]
                mm_fs_clases = [c for c in disponibles if c['Codigo_Oficial'].upper().startswith(('MM', 'FS'))]
                otras_clases = [c for c in disponibles if not c['Codigo_Oficial'].upper().startswith(('IS', 'MM', 'FS'))]
                
                # Se baraja dentro de cada grupo para dar un toque de aleatoriedad realista
                random.shuffle(is_clases)
                random.shuffle(mm_fs_clases)
                random.shuffle(otras_clases)
                
                # Se concatenan en orden de importancia
                disponibles_priorizados = is_clases + mm_fs_clases + otras_clases
                
                carga_periodo = []
                uv_periodo = 0
                max_clases_periodo = random.randint(3, 4)
                
                for d in disponibles_priorizados:
                    if uv_periodo + d['Unidades_Valorativas'] <= 18:
                        carga_periodo.append(d)
                        uv_periodo += d['Unidades_Valorativas']
                    if len(carga_periodo) >= max_clases_periodo: 
                        break
                
                if carga_periodo:
                    periodo_str = f"{periodo_sim}-{ano_sim}"
                    for c in carga_periodo:
                        exito = random.random() < 0.82
                        estado = 'Aprobado' if exito else 'Reprobado'
                        
                        cursor.execute("""
                            INSERT INTO Historial_Academico (Hash_Cuenta, ID_Clase, Estado, Periodo_Cursado) 
                            VALUES (%s, %s, %s, %s)
                        """, (cuenta_hash, c['ID_Clase'], estado, periodo_str))
                        
                        if estado == 'Aprobado':
                            clases_aprobadas.add(c['ID_Clase'])
                            total_uv_acumuladas += c['Unidades_Valorativas']

                periodo_sim += 1
                if periodo_sim > 3:
                    periodo_sim = 1
                    ano_sim += 1
            
            est_idx += 1

    conn.commit()
    conn.close()
    print("✅ Generación completada. Historiales realistas construidos con prioridad en IS.")

if __name__ == '__main__':
    ejecutar()