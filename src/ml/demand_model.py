import pandas as pd
import numpy as np
import os
from sklearn.ensemble import RandomForestClassifier  # <-- AGREGADO: El motor de IA

def predecir_demanda_estricta(engine):
    # 1. Extracción de Datos
    df_historial = pd.read_sql("""
        SELECT h.Hash_Cuenta, h.ID_Clase, h.Estado, m.Unidades_Valorativas, m.Codigo_Oficial, m.Plan_Perteneciente
        FROM Historial_Academico h
        JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
    """, engine)
    
    # Solo predecimos para estudiantes activos
    df_estudiantes = pd.read_sql("SELECT Hash_Cuenta, Plan_Estudio FROM Estudiantes", engine)
    df_malla = pd.read_sql("SELECT ID_Clase, Codigo_Oficial, Nombre_Clase, Unidades_Valorativas, Plan_Perteneciente, Prerrequisitos, ID_Area FROM Malla_Curricular", engine)
    df_censo = pd.read_sql("SELECT Hash_Cuenta, ID_Clase, Jornada_Preferencia FROM censo_periodo_actual", engine)

    EQUIVALENCIAS = {
        'ISC-101': ['IS-110', 'MM-314'], 'ISC-102': ['IS-210'], 'ISC-103': ['IS-410'],
        'ISC-211': ['IS-310'], 'ISC-321': ['IS-501'], 'ISC-422': ['IS-601'],
        'ISC-341': ['IS-602'], 'ISC-306': ['IS-702'], 'IE-326': ['IS-311', 'IS-510'],
        'ISC-331': ['IS-511'], 'ISC-332': ['IS-611'], 'ISC-333': ['IS-412'],
        'ISC-334': ['IS-512'], 'ISC-552': ['IS-115'], 'ISC-408': ['IS-802'],
        'ISC-414': ['IS-710'], 'ISC-336': ['IS-711'], 'ISC-437': ['IS-603']
    }

    def es_clase_aprobada(codigo, aprobadas):
        if codigo in aprobadas: return True
        if codigo in EQUIVALENCIAS and all(c in aprobadas for c in EQUIVALENCIAS[codigo]): return True
        return False

    def cumple_prerrequisitos(prereq, aprobadas, uv_actuales):
        if pd.isna(prereq) or str(prereq).strip().lower() in ['ninguno', 'nan', '']: return True
        for p in [x.strip() for x in str(prereq).split(',')]:
            if 'UV' in p.upper():
                import re
                nums = re.findall(r'\d+', p)
                if nums and uv_actuales < int(nums[0]): return False
            elif not es_clase_aprobada(p, aprobadas): return False
        return True

    print("🧠 Motor 1 (Predictivo) Iniciado: Entrenando modelo Random Forest...")
    
    # ==========================================
    # NUEVO: ENTRENAMIENTO DEL MODELO MACHINE LEARNING
    # ==========================================
    # 1. Feature Engineering (Métricas de la vida real)
    dificultad_clase = df_historial.groupby('ID_Clase')['Estado'].apply(lambda x: (x == 'Aprobado').mean()).to_dict()
    rendimiento_alumno = df_historial.groupby('Hash_Cuenta')['Estado'].apply(lambda x: (x == 'Aprobado').mean()).to_dict()

    # 2. Generación de Set de Entrenamiento (Simulando el "Sesgo de Optimismo" del censo)
    X_train = []
    y_train = []
    
    for _ in range(1000):
        rend_sim = np.random.uniform(0.2, 1.0)
        dif_sim = np.random.uniform(0.3, 0.9)
        censo_sim = np.random.choice([0, 1])
        
        prob_real = 0.3
        if censo_sim == 1:
            # Si la pidió, calculamos si realmente la va a llevar basada en su rendimiento
            prob_real = 0.95 * rend_sim * (1.2 - dif_sim) 
        else:
            prob_real = 0.40 * rend_sim
            
        prob_real = min(1.0, max(0.0, prob_real))
        
        X_train.append([rend_sim, dif_sim, censo_sim])
        y_train.append(1 if np.random.random() < prob_real else 0)

    # 3. Entrenamiento del Clasificador
    modelo_ml = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    modelo_ml.fit(X_train, y_train)
    print("✅ Modelo entrenado. Calculando probabilidades dinámicas por estudiante...")
    # ==========================================
    
    # 2. Análisis Predictivo (El corazón de tu ML)
    prediccion_actual = []
    aprobadas_totales = df_historial[df_historial['Estado'] == 'Aprobado'].groupby('Hash_Cuenta')['Codigo_Oficial'].apply(set).to_dict()

    for _, est in df_estudiantes.iterrows():
        hash_est = est['Hash_Cuenta']
        plan = est['Plan_Estudio']
        aprobadas = aprobadas_totales.get(hash_est, set())
        
        perfil_alumno = rendimiento_alumno.get(hash_est, 0.70) # <-- Le pasamos el perfil a la IA
        uv_actuales = df_historial[(df_historial['Hash_Cuenta'] == hash_est) & (df_historial['Estado'] == 'Aprobado')]['Unidades_Valorativas'].sum()
        clases_plan = df_malla[(df_malla['Plan_Perteneciente'] == plan) & (df_malla['Codigo_Oficial'].str.startswith(('IS', 'ISC', 'IE')))]
        
        for _, clase in clases_plan.iterrows():
            if es_clase_aprobada(clase['Codigo_Oficial'], aprobadas): continue
            
            # Si cumple prerrequisitos, entra al modelo predictivo
            if cumple_prerrequisitos(clase['Prerrequisitos'], aprobadas, uv_actuales):
                # Validar si el alumno la pidió en el censo
                en_censo = 1 if not df_censo[(df_censo['Hash_Cuenta'] == hash_est) & (df_censo['ID_Clase'] == clase['ID_Clase'])].empty else 0
                
                perfil_clase = dificultad_clase.get(clase['ID_Clase'], 0.60) # <-- Le pasamos el perfil a la IA
                
                # ==========================================
                # LA MAGIA DEL MOTOR 1 (Random Forest en acción)
                # ==========================================
                # Le pasamos las 3 variables al modelo: Rendimiento, Dificultad, ¿Llenó el censo?
                caracteristicas = np.array([[perfil_alumno, perfil_clase, en_censo]])
                
                # La IA nos devuelve un porcentaje exacto (Ej: 0.82) en lugar de un número estático
                prob_ml = modelo_ml.predict_proba(caracteristicas)[0][1] 
                # ==========================================
                
                prediccion_actual.append({
                    'ID_Clase': clase['ID_Clase'],
                    'Codigo_Oficial': clase['Codigo_Oficial'],
                    'Nombre_Clase': clase['Nombre_Clase'],
                    'ID_Area': clase['ID_Area'],
                    'Probabilidad_Final': prob_ml
                })

    if not prediccion_actual:
        return pd.DataFrame()

    df_ipac = pd.DataFrame(prediccion_actual)
    
   # Sumamos las probabilidades para obtener la demanda real
    demanda_final = df_ipac.groupby(['ID_Clase', 'Codigo_Oficial', 'Nombre_Clase', 'ID_Area'])['Probabilidad_Final'].sum().reset_index()
    demanda_final['Cupos_Estimados'] = np.ceil(demanda_final['Probabilidad_Final']).astype(int)
    
    # ==========================================
    # 🛑 REGLA DE NEGOCIO: MÍNIMO DE ALUMNOS Y SECCIONES ÚNICAS
    # ==========================================
    MINIMO_ALUMNOS = 5 
    SECCIONES_UNICAS = ['IS-115', 'IS-906', 'IS-802']
    
    condicion_unica = (demanda_final['Codigo_Oficial'].isin(SECCIONES_UNICAS)) & (demanda_final['Cupos_Estimados'] > 0)
    condicion_normal = (~demanda_final['Codigo_Oficial'].isin(SECCIONES_UNICAS)) & (demanda_final['Cupos_Estimados'] >= MINIMO_ALUMNOS)
    
    demanda_final = demanda_final[condicion_unica | condicion_normal]
    
    # 3. Extracción de la hora ideal del censo (Si existe)
    if not df_censo.empty and 'Jornada_Preferencia' in df_censo.columns:
        horas_censo = df_censo.groupby(['ID_Clase', 'Jornada_Preferencia'], as_index=False).size()
        horas_censo.rename(columns={'size': 'Votos'}, inplace=True)
        top_horas = horas_censo.sort_values('Votos', ascending=False).drop_duplicates(subset=['ID_Clase'])
        top_horas.rename(columns={'Jornada_Preferencia': 'Hora_Sugerida'}, inplace=True)
        demanda_final = demanda_final.merge(top_horas[['ID_Clase', 'Hora_Sugerida']], on='ID_Clase', how='left')
        demanda_final['Hora_Sugerida'] = demanda_final['Hora_Sugerida'].fillna('Sin preferencia')
    else:
        demanda_final['Hora_Sugerida'] = 'Sin preferencia'

    os.makedirs('data', exist_ok=True)
    demanda_final.to_csv('data/demanda_proyectada_2026.csv', index=False)
    return demanda_final