import hashlib
import random
import sys
import os
from config.db_connection import get_connection

# --- DICCIONARIO DE EQUIVALENCIAS (Plan Viejo -> Plan Nuevo) ---
EQUIVALENCIAS = {
    'ISC-101': ['IS-110', 'MM-314'],
    'ISC-102': ['IS-210'],
    'ISC-103': ['IS-410'],
    'ISC-211': ['IS-310'],
    'ISC-321': ['IS-501'],
    'ISC-422': ['IS-601'],
    'ISC-341': ['IS-602'],
    'ISC-306': ['IS-702'],
    'IE-326':  ['IS-311', 'IS-510'],
    'ISC-331': ['IS-511'],
    'ISC-332': ['IS-611'],
    'ISC-333': ['IS-412'],
    'ISC-334': ['IS-512'],
    'ISC-552': ['IS-115'],
    'ISC-408': ['IS-802'],
    'ISC-414': ['IS-710'],
    'ISC-336': ['IS-711'],
    'ISC-437': ['IS-603']
}

def hash_data(data):
    return hashlib.sha256(str(data).encode()).hexdigest()

def ya_aprobo_equivalencia(codigo_nueva, clases_aprobadas, mapa_codes):
    if codigo_nueva in EQUIVALENCIAS:
        for eq_code in EQUIVALENCIAS[codigo_nueva]:
            eq_ids = mapa_codes.get(eq_code, [])
            # clases_aprobadas ahora es un dict, así que el operador 'in' busca en sus llaves (IDs)
            if any(eq_id in clases_aprobadas for eq_id in eq_ids):
                return True
    return False

def evaluar_prerrequisitos_simulador(req_text, nombre_clase, ids_aprobados, total_uv, mapa_codes):
    req_lower = str(req_text).lower() if req_text else ""
    nombre_lower = str(nombre_clase).lower()
    
    if "seminario" in nombre_lower or "140" in req_lower:
        if total_uv < 140 and "140" in req_lower:
            return False
            
    if req_lower in ['ninguno', 'nan', 'null', '']:
        return True
        
    clases_requeridas = [r.strip().upper() for r in req_text.split(',') if "140" not in r]
    
    for code in clases_requeridas:
        req_ids = mapa_codes.get(code, [])
        aprobado = any(req_id in ids_aprobados for req_id in req_ids)
        
        if not aprobado and code in EQUIVALENCIAS:
            for eq_code in EQUIVALENCIAS[code]:
                eq_ids = mapa_codes.get(eq_code, [])
                if any(eq_id in ids_aprobados for eq_id in eq_ids):
                    aprobado = True
                    break
        
        if not aprobado:
            return False 
            
    return True

# Función auxiliar para comparar períodos (Ej: '2-2025' -> 20252)
def valor_periodo(periodo_str):
    if not periodo_str: return 0
    p, a = map(int, periodo_str.split('-'))
    return a * 10 + p

def ejecutar():
    conn = get_connection()
    if not conn:
        print("❌ Error de conexión")
        return
    
    cursor = conn.cursor(dictionary=True)
    
    print("🧹 Limpiando base de datos...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("TRUNCATE TABLE Historial_Academico;")
    cursor.execute("TRUNCATE TABLE Estudiantes;")
    cursor.execute("DELETE FROM Usuarios WHERE Rol = 'Estudiante';")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

    print("📖 Analizando Malla Curricular global...")
    cursor.execute("""
        SELECT ID_Clase, Codigo_Oficial, Nombre_Clase, Unidades_Valorativas, 
               Plan_Perteneciente, Prerrequisitos 
        FROM Malla_Curricular
    """)
    malla = cursor.fetchall()

    perfiles = [
        {'plan': '2021', 'n': 10, 'inicio': 2025},
        {'plan': '2021', 'n': 15, 'inicio': 2024},
        {'plan': '2021', 'n': 10, 'inicio': 2023},
        {'plan': '2021', 'n': 18, 'inicio': 2022},
        {'plan': '2021', 'n': 17, 'inicio': 2021} 
    ]

    print("🚀 Simulando trayectorias académicas hasta el actual IPAC 2026...")
    
    pass_hash = hash_data('admin123') 
    est_idx = 1
    
    mapa_codes = {}
    for c in malla:
        codigo = c['Codigo_Oficial'].strip().upper()
        if codigo not in mapa_codes:
            mapa_codes[codigo] = []
        mapa_codes[codigo].append(c['ID_Clase'])
    
    ids_circuitos = mapa_codes.get('IS-311', [])
    ids_poo = mapa_codes.get('IS-410', [])

    for p in perfiles:
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
            
            # ¡AHORA ES UN DICCIONARIO! Guardará el ID de la clase y el período en que la pasó
            clases_aprobadas = {} 
            total_uv_acumuladas = 0
            ano_sim = p['inicio']
            periodo_sim = 1
            plan_actual = p['plan']
            
            while ano_sim < 2026 or (ano_sim == 2026 and periodo_sim <= 1):
                
                # --- REGLA OFICIAL DE TRANSICIÓN: IPAC 2026 ---
                if plan_actual in ['2021', '2024'] and ano_sim == 2026 and periodo_sim == 1:
                    
                    # Obtenemos en qué período pasó Circuitos y POO (si no las pasó, es None)
                    per_circuitos = next((clases_aprobadas[i] for i in ids_circuitos if i in clases_aprobadas), None)
                    per_poo = next((clases_aprobadas[i] for i in ids_poo if i in clases_aprobadas), None)
                    
                    paso_ambas = (per_circuitos is not None) and (per_poo is not None)
                    
                    if not paso_ambas:
                        # Si no pasó alguna, cambio obligatorio al nuevo plan
                        hacer_cambio = True
                    else:
                        # Pasó ambas. ¿Cuándo pasó la última de las dos?
                        val_circ = valor_periodo(per_circuitos)
                        val_poo = valor_periodo(per_poo)
                        max_val = max(val_circ, val_poo)
                        
                        # Si la última de las dos la aprobó en 2025-2 (20252) o 2025-3 (20253):
                        if max_val >= 20252:
                            hacer_cambio = random.random() < 0.30 # Tienen la opción
                        else:
                            # Las aprobó en 2025-1 o antes. Se quedan SI O SI en el viejo.
                            hacer_cambio = False
                        
                    if hacer_cambio:
                        plan_actual = '2025'
                        cursor.execute("""
                            UPDATE Estudiantes SET Plan_Estudio = '2025' WHERE Hash_Cuenta = %s
                        """, (cuenta_hash,))
                
                clases_del_plan = [c for c in malla if c['Plan_Perteneciente'] == plan_actual]
                disponibles = []
                
                for c in clases_del_plan:
                    codigo = c['Codigo_Oficial'].strip().upper()
                    
                    if c['ID_Clase'] in clases_aprobadas:
                        continue
                        
                    if plan_actual == '2025' and ya_aprobo_equivalencia(codigo, clases_aprobadas, mapa_codes):
                        continue
                        
                    if evaluar_prerrequisitos_simulador(c['Prerrequisitos'], c['Nombre_Clase'], clases_aprobadas, total_uv_acumuladas, mapa_codes):
                        disponibles.append(c)
                
                if not disponibles: 
                    break 
                
                is_clases = [c for c in disponibles if c['Codigo_Oficial'].upper().startswith(('IS', 'ISC'))]
                mm_fs_clases = [c for c in disponibles if c['Codigo_Oficial'].upper().startswith(('MM', 'FS'))]
                otras_clases = [c for c in disponibles if not c['Codigo_Oficial'].upper().startswith(('IS', 'ISC', 'MM', 'FS'))]
                
                random.shuffle(is_clases)
                random.shuffle(mm_fs_clases)
                random.shuffle(otras_clases)
                
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
                            # ¡Guardamos el período en el diccionario!
                            clases_aprobadas[c['ID_Clase']] = periodo_str
                            total_uv_acumuladas += c['Unidades_Valorativas']

                periodo_sim += 1
                if periodo_sim > 3:
                    periodo_sim = 1
                    ano_sim += 1
            
            est_idx += 1

    conn.commit()
    conn.close()
    print("✅ Generación completada. Base de datos lista para entrenar el modelo ML.")

if __name__ == '__main__':
    ejecutar()