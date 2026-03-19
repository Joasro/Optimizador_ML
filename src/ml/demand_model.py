import pandas as pd
import numpy as np
import os
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

EQUIVALENCIAS_REVERSAS = {
    'IS-110': 'ISC-101', 'MM-314': 'ISC-101', 'IS-210': 'ISC-102', 
    'IS-310': 'ISC-211', 'IS-410': 'ISC-103', 'IS-501': 'ISC-321',
    'IS-601': 'ISC-422', 'IS-602': 'ISC-341', 'IS-702': 'ISC-306', 
    'IS-311': 'IE-326',  'IS-510': 'IE-326',  'IS-511': 'ISC-331',
    'IS-611': 'ISC-332', 'IS-412': 'ISC-333', 'IS-512': 'ISC-334', 
    'IS-115': 'ISC-552', 'IS-802': 'ISC-408'
}
OPTATIVAS_2021 = ['IS-910', 'IS-911', 'IS-914', 'IS-912', 'IS-913']

def extender_aprobadas(aprobadas_base):
    extendidas = set(aprobadas_base)
    for vieja, nueva in EQUIVALENCIAS_REVERSAS.items():
        if vieja in extendidas: extendidas.add(nueva)
    return extendidas

def cumple_prerrequisitos(req_text, aprobadas_set, uv_est):
    if not req_text or str(req_text).lower() in ['ninguno', 'nan', 'null', '']: return True
    if "140" in str(req_text): return uv_est >= 140
    reqs = [r.strip().upper() for r in str(req_text).split(',')]
    return all(r in aprobadas_set for r in reqs)

def calcular_es_egresando(aprobadas_set, plan_estudiante, df_malla):
    malla_carrera = df_malla[(df_malla['Plan_Perteneciente'] == plan_estudiante) & (df_malla['Codigo_Oficial'].str.startswith(('IS', 'ISC', 'IE')))]
    if plan_estudiante == '2021':
        malla_core = malla_carrera[~malla_carrera['Codigo_Oficial'].isin(OPTATIVAS_2021)]
        aprobadas_core = len([c for c in aprobadas_set if c in malla_core['Codigo_Oficial'].values])
        core_faltantes = len(malla_core) - aprobadas_core
        optativas_faltantes = max(0, 3 - len([c for c in aprobadas_set if c in OPTATIVAS_2021]))
        total_faltantes = core_faltantes + optativas_faltantes
    else:
        aprobadas_carrera = len([c for c in aprobadas_set if c in malla_carrera['Codigo_Oficial'].values])
        total_faltantes = len(malla_carrera) - aprobadas_carrera
    return 1 if total_faltantes <= 8 else 0

def predecir_demanda_estricta(engine):
    print("🧠 Motor Inteligente: Extrayendo datos frescos y entrenando XGBoost...")
    
    df_historial = pd.read_sql("SELECT h.Hash_Cuenta, h.ID_Clase, h.Estado, h.Periodo_Cursado, m.Unidades_Valorativas, m.Codigo_Oficial, m.Plan_Perteneciente FROM Historial_Academico h JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase", engine)
    df_estudiantes = pd.read_sql("SELECT Hash_Cuenta, Plan_Estudio, Ano_Ingreso FROM Estudiantes", engine)
    df_malla = pd.read_sql("SELECT ID_Clase, Codigo_Oficial, Nombre_Clase, Unidades_Valorativas, Plan_Perteneciente, Prerrequisitos, ID_Area FROM Malla_Curricular", engine)
    df_censo = pd.read_sql("SELECT Hash_Cuenta, ID_Clase, Jornada_Preferencia FROM censo_periodo_actual", engine)

    periodos = sorted(df_historial['Periodo_Cursado'].unique(), key=lambda x: (int(x.split('-')[1]), int(x.split('-')[0])))
    dict_estudiantes = df_estudiantes.set_index('Hash_Cuenta').to_dict('index')
    training_data = []

    for i in range(1, len(periodos)):
        periodo_actual = periodos[i]
        historia_previa = df_historial[df_historial['Periodo_Cursado'].apply(lambda x: periodos.index(x) < i)]
        matriculas_actuales = df_historial[df_historial['Periodo_Cursado'] == periodo_actual]

        for hash_est, info in dict_estudiantes.items():
            plan = info['Plan_Estudio']
            hist_estudiante = historia_previa[historia_previa['Hash_Cuenta'] == hash_est]
            if hist_estudiante.empty: continue 
            
            aprobadas_antes = extender_aprobadas(set(hist_estudiante[hist_estudiante['Estado'] == 'Aprobado']['Codigo_Oficial']))
            uv_antes = hist_estudiante[hist_estudiante['Estado'] == 'Aprobado']['Unidades_Valorativas'].sum()
            clases_matriculadas = set(matriculas_actuales[matriculas_actuales['Hash_Cuenta'] == hash_est]['Codigo_Oficial'])
            clases_plan = df_malla[(df_malla['Plan_Perteneciente'] == plan) & (df_malla['Codigo_Oficial'].str.startswith(('IS', 'ISC', 'IE')))]
            
            for _, clase in clases_plan.iterrows():
                cod = clase['Codigo_Oficial']
                if cod in aprobadas_antes: continue 
                if cumple_prerrequisitos(clase['Prerrequisitos'], aprobadas_antes, uv_antes):
                    training_data.append({
                        'UV_Acumuladas': uv_antes, 'Es_Egresando': calcular_es_egresando(aprobadas_antes, plan, df_malla),
                        'Plan_n': 1 if plan == '2025' else 0, 'Matriculo_Real': 1 if cod in clases_matriculadas else 0 
                    })

    df_train = pd.DataFrame(training_data)
    modelo_base = xgb.XGBClassifier(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=42, eval_metric='logloss')
    if not df_train.empty:
        X_train = df_train[['UV_Acumuladas', 'Es_Egresando', 'Plan_n']]
        y_train = df_train['Matriculo_Real']
        modelo_base.fit(X_train, y_train)

    prediccion_actual = []
    aprobadas_totales = df_historial[df_historial['Estado'] == 'Aprobado'].groupby('Hash_Cuenta')['Codigo_Oficial'].apply(set).to_dict()

    for hash_est, info in dict_estudiantes.items():
        plan = info['Plan_Estudio']
        aprobadas = extender_aprobadas(aprobadas_totales.get(hash_est, set()))
        uv_actuales = sum([df_malla[df_malla['Codigo_Oficial'] == c]['Unidades_Valorativas'].values[0] for c in aprobadas if c in df_malla['Codigo_Oficial'].values])
        es_egresando = calcular_es_egresando(aprobadas, plan, df_malla)
        clases_plan = df_malla[(df_malla['Plan_Perteneciente'] == plan) & (df_malla['Codigo_Oficial'].str.startswith(('IS', 'ISC', 'IE')))]
        
        for _, clase in clases_plan.iterrows():
            cod, id_clase = clase['Codigo_Oficial'], clase['ID_Clase']
            if cod in aprobadas: continue
            if cumple_prerrequisitos(clase['Prerrequisitos'], aprobadas, uv_actuales):
                en_censo = 1 if ((df_censo['Hash_Cuenta'] == hash_est) & (df_censo['ID_Clase'] == id_clase)).any() else 0
                prediccion_actual.append({
                    'ID_Clase': id_clase, 'Codigo_Oficial': cod, 'Nombre_Clase': clase['Nombre_Clase'], 'ID_Area': clase['ID_Area'],
                    'UV_Acumuladas': uv_actuales, 'Es_Egresando': es_egresando, 'Plan_n': 1 if plan == '2025' else 0, 'En_Censo': en_censo
                })

    if not prediccion_actual: return pd.DataFrame()

    df_ipac2026 = pd.DataFrame(prediccion_actual)
    if not df_train.empty:
        X_ipac = df_ipac2026[['UV_Acumuladas', 'Es_Egresando', 'Plan_n']]
        df_ipac2026['Probabilidad_ML'] = modelo_base.predict_proba(X_ipac)[:, 1]
    else:
        df_ipac2026['Probabilidad_ML'] = 0.5
        
    df_ipac2026['Probabilidad_Final'] = np.clip(df_ipac2026['Probabilidad_ML'] + (df_ipac2026['En_Censo'] * 0.35), 0, 1)
    df_ipac2026.loc[df_ipac2026['Es_Egresando'] == 1, 'Probabilidad_Final'] = 1.0 # 🌟 Prioridad absoluta egresandos

    demanda_final = df_ipac2026.groupby(['ID_Clase', 'Codigo_Oficial', 'Nombre_Clase', 'ID_Area'])['Probabilidad_Final'].sum().reset_index()
    demanda_final['Cupos_Estimados'] = np.ceil(demanda_final['Probabilidad_Final']).astype(int)
    
    MINIMO_ALUMNOS = 3
    SECCIONES_UNICAS = ['IS-115', 'IS-906', 'IS-802']
    condicion_unica = (demanda_final['Codigo_Oficial'].isin(SECCIONES_UNICAS)) & (demanda_final['Cupos_Estimados'] > 0)
    condicion_normal = (~demanda_final['Codigo_Oficial'].isin(SECCIONES_UNICAS)) & (demanda_final['Cupos_Estimados'] >= MINIMO_ALUMNOS)
    demanda_final = demanda_final[condicion_unica | condicion_normal]

    if not df_censo.empty and 'Jornada_Preferencia' in df_censo.columns:
        horas_censo = df_censo.groupby(['ID_Clase', 'Jornada_Preferencia'], as_index=False).size().rename(columns={'size': 'Votos'})
        top_horas = horas_censo.sort_values('Votos', ascending=False).drop_duplicates(subset=['ID_Clase']).rename(columns={'Jornada_Preferencia': 'Hora_Sugerida'})
        demanda_final = demanda_final.merge(top_horas[['ID_Clase', 'Hora_Sugerida']], on='ID_Clase', how='left')
        demanda_final['Hora_Sugerida'] = demanda_final['Hora_Sugerida'].fillna('Sin preferencia')
    else:
        demanda_final['Hora_Sugerida'] = 'Sin preferencia'

    # ==========================================
    # 🌟 INYECCIÓN EXÓGENA (Primer Ingreso: ISC-101)
    # ==========================================
    try:
        ruta_csv = 'data/historial_ingresos.csv'
        if not os.path.exists(ruta_csv): ruta_csv = '../data/historial_ingresos.csv'
        df_hist = pd.read_csv(ruta_csv)
        col_name = 'Primer Ingreso' if 'Primer Ingreso' in df_hist.columns else 'Primer_Ingreso'
        if col_name not in df_hist.columns:
            df_hist = pd.read_csv(ruta_csv, skiprows=1)
            col_name = 'Primer Ingreso' if 'Primer Ingreso' in df_hist.columns else 'Primer_Ingreso'
            
        df_hist[col_name] = pd.to_numeric(df_hist[col_name], errors='coerce')
        df_validos = df_hist.dropna(subset=[col_name])
        df_validos = df_validos[df_validos[col_name] > 0]
        
        ultimos = df_validos[col_name].tail(3).values
        novatos_brutos = int(np.ceil((ultimos[2]*0.5) + (ultimos[1]*0.3) + (ultimos[0]*0.2))) if len(ultimos)==3 else 35
        
        df_mod = df_estudiantes[df_estudiantes['Ano_Ingreso'] >= 2023]
        hashes_str = tuple(df_mod['Hash_Cuenta'].tolist())
        q = f"SELECT COUNT(DISTINCT h.Hash_Cuenta) as t FROM Historial_Academico h JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase WHERE m.Codigo_Oficial='ISC-101' AND h.Hash_Cuenta IN {hashes_str}"
        res = pd.read_sql(q, engine)
        tasa = min(max(res['t'].iloc[0] / len(df_mod), 0.50), 1.0)
        
        cupos_intro = int(np.ceil(novatos_brutos * tasa))
        
        info_clase = df_malla[df_malla['Codigo_Oficial'] == 'ISC-101'].iloc[0]
        if 'ISC-101' in demanda_final['Codigo_Oficial'].values:
            idx = demanda_final.index[demanda_final['Codigo_Oficial'] == 'ISC-101'][0]
            demanda_final.at[idx, 'Cupos_Estimados'] += cupos_intro
        else:
            nueva_seccion = pd.DataFrame([{
                'ID_Clase': info_clase['ID_Clase'], 'Codigo_Oficial': 'ISC-101', 'Nombre_Clase': info_clase['Nombre_Clase'], 
                'ID_Area': info_clase['ID_Area'], 'Cupos_Estimados': cupos_intro, 'Hora_Sugerida': 'Sin preferencia'
            }])
            demanda_final = pd.concat([demanda_final, nueva_seccion], ignore_index=True)
            
    except Exception as e:
        print(f"⚠️ Aviso Exógeno: {e}")

    os.makedirs('data', exist_ok=True)
    demanda_final.to_csv('data/demanda_proyectada_2026.csv', index=False)
    return demanda_final