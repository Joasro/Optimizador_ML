import streamlit as st
import pandas as pd
from config.db_connection import get_connection

# --- DICCIONARIOS INTELIGENTES ---
EQUIVALENCIAS = {
    'ISC-101': ['IS-110', 'MM-314'], 'ISC-102': ['IS-210'], 'ISC-103': ['IS-410'],
    'ISC-211': ['IS-310'], 'ISC-321': ['IS-501'], 'ISC-422': ['IS-601'],
    'ISC-341': ['IS-602'], 'ISC-306': ['IS-702'], 'IE-326': ['IS-311', 'IS-510'],
    'ISC-331': ['IS-511'], 'ISC-332': ['IS-611'], 'ISC-333': ['IS-412'],
    'ISC-334': ['IS-512'], 'ISC-552': ['IS-115'], 'ISC-408': ['IS-802'],
    'ISC-414': ['IS-710'], 'ISC-336': ['IS-711'], 'ISC-437': ['IS-603']
}

OPTATIVAS_2021 = ['IS-910', 'IS-911', 'IS-914', 'IS-912', 'IS-913']

# 🛑 NUEVO: DICCIONARIO DE HORAS EXACTAS
HORAS_CENSO = {
    "07:00:00": "07:00 AM - 08:00 AM", "08:00:00": "08:00 AM - 09:00 AM", 
    "09:00:00": "09:00 AM - 10:00 AM", "10:00:00": "10:00 AM - 11:00 AM", 
    "11:00:00": "11:00 AM - 12:00 PM", "12:00:00": "12:00 PM - 01:00 PM",
    "13:00:00": "01:00 PM - 02:00 PM", "14:00:00": "02:00 PM - 03:00 PM", 
    "15:00:00": "03:00 PM - 04:00 PM", "16:00:00": "04:00 PM - 05:00 PM", 
    "17:00:00": "05:00 PM - 06:00 PM", "18:00:00": "06:00 PM - 07:00 PM", 
    "19:00:00": "07:00 PM - 08:00 PM", "20:00:00": "08:00 PM - 09:00 PM"
}

def es_clase_aprobada_o_equivalente(codigo_clase, aprobadas):
    if codigo_clase in aprobadas: return True
    if codigo_clase in EQUIVALENCIAS:
        if all(old_c in aprobadas for old_c in EQUIVALENCIAS[codigo_clase]): return True
    return False

def cumple_prerrequisitos_estudiante(prereq_str, aprobadas, uv_actuales):
    if pd.isna(prereq_str) or str(prereq_str).strip().lower() in ['ninguno', 'nan', '']:
        return True
    prereqs = [p.strip() for p in str(prereq_str).split(',')]
    for p in prereqs:
        if 'UV' in p.upper():
            import re
            nums = re.findall(r'\d+', p)
            if nums and uv_actuales < int(nums[0]):
                return False
        else:
            if not es_clase_aprobada_o_equivalente(p, aprobadas):
                return False
    return True

def calcular_estado_egresando(aprobadas_set, plan, malla_df):
    malla_carrera = malla_df[
        (malla_df['Plan_Perteneciente'] == plan) & 
        (malla_df['Codigo_Oficial'].str.startswith(('IS', 'ISC', 'IE')))
    ]
    aprobadas_optativas = 0
    if plan == '2021':
        malla_core = malla_carrera[~malla_carrera['Codigo_Oficial'].isin(OPTATIVAS_2021)]
        aprobadas_core = len([c for c in aprobadas_set if c in malla_core['Codigo_Oficial'].values])
        core_faltantes = len(malla_core) - aprobadas_core
        aprobadas_optativas = len([c for c in aprobadas_set if c in OPTATIVAS_2021])
        optativas_faltantes = max(0, 3 - aprobadas_optativas)
        total_faltantes = core_faltantes + optativas_faltantes
    else:
        aprobadas_carrera = len([c for c in aprobadas_set if c in malla_carrera['Codigo_Oficial'].values])
        total_faltantes = len(malla_carrera) - aprobadas_carrera
        
    es_egresando = True if total_faltantes <= 8 else False
    return es_egresando, total_faltantes, aprobadas_optativas

# ==========================================
# VISTA PRINCIPAL DEL ESTUDIANTE
# ==========================================
def vista_estudiante():
    st.sidebar.title(f"🎓 Estudiante: {st.session_state['user_name']}")
    
    hash_usuario = st.session_state['user_hash']
    conn = get_connection()
    
    est_df = pd.read_sql(f"SELECT Plan_Estudio FROM Estudiantes WHERE Hash_Cuenta = '{hash_usuario}'", conn)
    if est_df.empty:
        st.error("No se encontró tu información en la base de datos.")
        conn.close()
        return
    plan_actual = est_df.iloc[0]['Plan_Estudio']

    historial_df = pd.read_sql(f"""
        SELECT h.Periodo_Cursado, m.Codigo_Oficial, m.Nombre_Clase, m.Unidades_Valorativas, h.Estado 
        FROM Historial_Academico h 
        JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
        WHERE h.Hash_Cuenta = '{hash_usuario}' 
        ORDER BY h.Periodo_Cursado ASC
    """, conn)
    
    malla_df = pd.read_sql(f"SELECT ID_Clase, Codigo_Oficial, Nombre_Clase, Prerrequisitos, Unidades_Valorativas, Plan_Perteneciente FROM Malla_Curricular WHERE Plan_Perteneciente = '{plan_actual}'", conn)

    if not historial_df.empty:
        aprobadas_set = set(historial_df[historial_df['Estado'] == 'Aprobado']['Codigo_Oficial'].tolist())
        uv_totales = historial_df[historial_df['Estado'] == 'Aprobado']['Unidades_Valorativas'].sum()
    else:
        aprobadas_set = set()
        uv_totales = 0

    es_egresando, clases_faltantes, opt_aprobadas = calcular_estado_egresando(aprobadas_set, plan_actual, malla_df)

    if es_egresando:
        st.sidebar.success("🌟 **¡Estudiante por Egresar!**")
        st.sidebar.caption(f"Solo te faltan **{clases_faltantes}** clases para finalizar.")
    else:
        st.sidebar.info("📚 Estatus: Estudiante Regular")
        st.sidebar.caption(f"Clases de carrera faltantes: **{clases_faltantes}**")

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    tab_historial, tab_censo = st.tabs(["📋 Mi Historial Académico", "🚀 Planificar mi Próximo Periodo"])
    
    # --- PESTAÑA 1: HISTORIAL ---
    with tab_historial:
        st.title("Mi Historial Académico")
        if historial_df.empty:
            st.info("Aún no tienes clases registradas.")
        else:
            col_header1, col_header2 = st.columns([3, 1])
            with col_header1:
                st.metric("Total de Unidades Valorativas Aprobadas", int(uv_totales))
            with col_header2:
                csv_completo = historial_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar CSV", data=csv_completo, file_name="mi_historial.csv", mime="text/csv", type="primary", use_container_width=True)
                
            st.divider()
            periodos_unicos = historial_df['Periodo_Cursado'].unique()
            try:
                periodos_ordenados = sorted(periodos_unicos, key=lambda x: (int(x.split('-')[1]), int(x.split('-')[0])))
            except:
                periodos_ordenados = periodos_unicos
            
            for periodo in periodos_ordenados:
                st.markdown(f"### 📅 Periodo Académico: `{periodo}`")
                df_periodo = historial_df[historial_df['Periodo_Cursado'] == periodo][['Codigo_Oficial', 'Nombre_Clase', 'Unidades_Valorativas', 'Estado']]
                df_periodo.index = range(1, len(df_periodo) + 1)
                def color_estado(val):
                    return 'color: green' if val == 'Aprobado' else 'color: red; font-weight: bold'
                st.dataframe(df_periodo.style.applymap(color_estado, subset=['Estado']), use_container_width=True)
                st.write("---")

    # --- PESTAÑA 2: CENSO POR HORA EXACTA ---
    with tab_censo:
        st.title("Censo de Matrícula (Hora Exacta)")
        
        censo_df = pd.read_sql(f"""
            SELECT c.Jornada_Preferencia, m.Codigo_Oficial, m.Nombre_Clase, m.Unidades_Valorativas 
            FROM censo_periodo_actual c 
            JOIN Malla_Curricular m ON c.ID_Clase = m.ID_Clase 
            WHERE c.Hash_Cuenta = '{hash_usuario}'
        """, conn)
        
        if not censo_df.empty:
            st.success("✅ ¡Censo completado! Tu planificación exacta ha sido enviada al Optimizador.")
            st.markdown("### 📋 Resumen de tu Horario Planeado:")
            
            for _, row in censo_df.iterrows():
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1.5])
                    with col1:
                        st.markdown(f"**{row['Codigo_Oficial']}** - {row['Nombre_Clase']}")
                        st.caption(f"Valor: {row['Unidades_Valorativas']} UV")
                    with col2:
                        # Convertimos la hora de la BD al texto amigable para mostrarlo
                        hora_bd = row['Jornada_Preferencia']
                        hora_texto = HORAS_CENSO.get(hora_bd, hora_bd)
                        st.info(f"🕒 **{hora_texto}**")
            
            st.caption("Nota: Si deseas modificar tu censo, comunícate con la Jefatura del Departamento.")
        else:
            st.markdown("Diseña tu horario ideal. Selecciona la **hora exacta** en la que necesitas llevar cada clase para poder trabajar o realizar tus otras actividades.")
            st.write("")
            
            if plan_actual == '2021':
                if opt_aprobadas >= 3:
                    st.success(f"🎉 ¡Felicidades! Ya aprobaste {opt_aprobadas} optativas. Las demás han sido ocultadas.")
                elif opt_aprobadas > 0:
                    st.info(f"💡 Has aprobado {opt_aprobadas} de las 3 optativas requeridas.")
            
            clases_desbloqueadas = []
            for _, row in malla_df.iterrows():
                cod = row['Codigo_Oficial']
                if plan_actual == '2021' and cod in OPTATIVAS_2021 and opt_aprobadas >= 3:
                    continue 
                if not es_clase_aprobada_o_equivalente(cod, aprobadas_set):
                    if cumple_prerrequisitos_estudiante(row['Prerrequisitos'], aprobadas_set, int(uv_totales)):
                        clases_desbloqueadas.append(row.to_dict())
            
            if not clases_desbloqueadas:
                st.balloons()
                st.success("🎉 ¡Felicidades! Has completado todas las clases de tu plan de estudios.")
            else:
                st.markdown("### 1️⃣ Paso 1: Elige tus asignaturas")
                opciones_mostrar = {c['ID_Clase']: f"{c['Codigo_Oficial']} - {c['Nombre_Clase']} ({c['Unidades_Valorativas']} UV)" for c in clases_desbloqueadas}
                
                clases_seleccionadas = st.multiselect(
                    "Selecciona las clases que tienes planeado matricular:",
                    options=list(opciones_mostrar.keys()),
                    format_func=lambda x: opciones_mostrar[x],
                    placeholder="Haz clic aquí para ver las clases disponibles..."
                )
                
                if clases_seleccionadas:
                    st.divider()
                    st.markdown("### 2️⃣ Paso 2: Asigna la hora exacta")
                    
                    uv_planeadas = sum([c['Unidades_Valorativas'] for c in clases_desbloqueadas if c['ID_Clase'] in clases_seleccionadas])
                    
                    if uv_planeadas > 25:
                        st.error(f"🚨 Estás intentando planificar **{uv_planeadas} UV**. El límite máximo permitido por las Normas Académicas es de 25 UV por periodo.")
                    else:
                        st.info(f"📊 Carga académica planificada: **{uv_planeadas} UV** (Límite máximo: 25 UV).")
                    
                    st.write("Indícanos a qué hora prefieres llevar cada clase:")
                    
                    preferencias_hora = {}
                    for id_c in clases_seleccionadas:
                        clase_info = next(c for c in clases_desbloqueadas if c['ID_Clase'] == id_c)
                        with st.container(border=True):
                            col_info, col_hora = st.columns([2, 1.5])
                            with col_info:
                                st.markdown(f"**{clase_info['Codigo_Oficial']}** - {clase_info['Nombre_Clase']}")
                            with col_hora:
                                # 🛑 EL NUEVO SELECTOR DE HORA EXACTA
                                preferencias_hora[id_c] = st.selectbox(
                                    "Hora Preferida", 
                                    options=list(HORAS_CENSO.keys()),
                                    format_func=lambda x: HORAS_CENSO[x],
                                    key=f"hora_{id_c}",
                                    label_visibility="collapsed"
                                )
                    
                    st.write("")
                    if st.button("🚀 Confirmar y Enviar mi Planificación", type="primary", use_container_width=True):
                        cursor = conn.cursor()
                        try:
                            for id_c, hora_elegida in preferencias_hora.items():
                                cursor.execute("""
                                    INSERT INTO censo_periodo_actual (Hash_Cuenta, ID_Clase, Jornada_Preferencia, Prioridad_Alumno)
                                    VALUES (%s, %s, %s, 1)
                                """, (hash_usuario, id_c, hora_elegida))
                            conn.commit()
                            st.success("✅ ¡Censo guardado exitosamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar: {e}. ¿Ejecutaste el comando ALTER TABLE en tu base de datos?")
                                
    conn.close()