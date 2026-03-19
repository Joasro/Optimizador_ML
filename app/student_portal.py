import streamlit as st
import pandas as pd
from config.db_connection import get_connection

# ==========================================
# 1. DICCIONARIOS Y LÓGICA ACADÉMICA
# ==========================================
EQUIVALENCIAS = {
    'ISC-101': ['IS-110', 'MM-314'], 'ISC-102': ['IS-210'], 'ISC-103': ['IS-410'],
    'ISC-211': ['IS-310'], 'ISC-321': ['IS-501'], 'ISC-422': ['IS-601'],
    'ISC-341': ['IS-602'], 'ISC-306': ['IS-702'], 'IE-326': ['IS-311', 'IS-510'],
    'ISC-331': ['IS-511'], 'ISC-332': ['IS-611'], 'ISC-333': ['IS-412'],
    'ISC-334': ['IS-512'], 'ISC-552': ['IS-115'], 'ISC-408': ['IS-802'],
    'ISC-414': ['IS-710'], 'ISC-336': ['IS-711'], 'ISC-437': ['IS-603']
}

OPTATIVAS_2021 = ['IS-910', 'IS-911', 'IS-914', 'IS-912', 'IS-913']

MAPA_HORAS_UI = {
    "Cualquiera / Sin preferencia": "Sin preferencia",
    "07:00 AM (Mañana)": "07:00:00", "08:00 AM (Mañana)": "08:00:00",
    "09:00 AM (Mañana)": "09:00:00", "10:00 AM (Mañana)": "10:00:00",
    "11:00 AM (Mañana)": "11:00:00", "12:00 PM (Mediodía)": "12:00:00",
    "01:00 PM (Tarde)": "13:00:00", "02:00 PM (Tarde)": "14:00:00",
    "03:00 PM (Tarde)": "15:00:00", "04:00 PM (Tarde)": "16:00:00",
    "05:00 PM (Noche)": "17:00:00", "06:00 PM (Noche)": "18:00:00",
    "07:00 PM (Noche)": "19:00:00", "08:00 PM (Noche)": "20:00:00"
}

MAPA_INVERSO = {v: k for k, v in MAPA_HORAS_UI.items()}

def es_clase_aprobada_o_equivalente(codigo_nueva, aprobadas):
    if codigo_nueva in aprobadas: return True
    if codigo_nueva in EQUIVALENCIAS:
        if all(old in aprobadas for old in EQUIVALENCIAS[codigo_nueva]): return True
    return False

def cumple_prerrequisitos(prereq_str, aprobadas, uv_actuales):
    if pd.isna(prereq_str) or str(prereq_str).strip().lower() in ['ninguno', 'nan', '']: return True
    prereqs = [p.strip() for p in str(prereq_str).split(',')]
    for p in prereqs:
        if 'UV' in p.upper():
            import re
            nums = re.findall(r'\d+', p)
            if nums and uv_actuales < int(nums[0]): return False
        else:
            if not es_clase_aprobada_o_equivalente(p, aprobadas): return False
    return True

# ==========================================
# 2. INTERFAZ PRINCIPAL
# ==========================================
def vista_estudiante():
    hash_usuario = st.session_state.get('user_hash', '')
    nombre_estudiante = st.session_state.get('user_name', 'Estudiante')

    conn = get_connection()
    if not conn:
        st.error("❌ Sin conexión a la base de datos.")
        return

    try:
        # Extraer Perfil
        query_est = "SELECT Plan_Estudio, Ano_Ingreso FROM estudiantes WHERE Hash_Cuenta = %s"
        df_est = pd.read_sql(query_est, conn, params=(hash_usuario,))
        
        if df_est.empty:
            st.error("⚠️ Tu cuenta no está registrada en el padrón de estudiantes.")
            return
            
        plan_estudio = df_est.iloc[0]['Plan_Estudio']
        ano_ingreso = df_est.iloc[0]['Ano_Ingreso']

        # Extraer Historial Completo para la UI
        query_hist_completo = """
            SELECT m.Codigo_Oficial AS 'Código', m.Nombre_Clase AS 'Asignatura', 
                   m.Unidades_Valorativas AS 'UV', h.Periodo_Cursado AS 'Periodo', h.Estado 
            FROM historial_academico h
            JOIN malla_curricular m ON h.ID_Clase = m.ID_Clase
            WHERE h.Hash_Cuenta = %s
        """
        df_historial = pd.read_sql(query_hist_completo, conn, params=(hash_usuario,))
        
        # Filtrar solo aprobadas para la lógica matemática
        df_aprobadas = df_historial[df_historial['Estado'] == 'Aprobado']
        aprobadas_set = set(df_aprobadas['Código'].tolist())
        uv_acumuladas = int(df_aprobadas['UV'].sum()) if not df_aprobadas.empty else 0

        # Extraer Malla
        malla_df = pd.read_sql("SELECT * FROM malla_curricular", conn)
        malla_carrera = malla_df[(malla_df['Plan_Perteneciente'] == plan_estudio) & (malla_df['Codigo_Oficial'].str.startswith(('IS', 'ISC', 'IE')))]

        # Lógica de Egresando
        if plan_estudio == '2021':
            malla_core = malla_carrera[~malla_carrera['Codigo_Oficial'].isin(OPTATIVAS_2021)]
            aprobadas_core = len([c for c in aprobadas_set if c in malla_core['Codigo_Oficial'].values])
            core_faltantes = len(malla_core) - aprobadas_core
            optativas_faltantes = max(0, 3 - len([c for c in aprobadas_set if c in OPTATIVAS_2021]))
            clases_faltantes = core_faltantes + optativas_faltantes
        else:
            aprobadas_carrera = len([c for c in aprobadas_set if c in malla_carrera['Codigo_Oficial'].values])
            clases_faltantes = len(malla_carrera) - aprobadas_carrera
            
        es_egresando = clases_faltantes <= 8

        # ==========================================
        # 🎨 SIDEBAR ACADÉMICO
        # ==========================================
        with st.sidebar:
            st.image("https://cdn-icons-png.flaticon.com/512/2995/2995114.png", width=100)
            st.title("👨‍🎓 Mi Perfil")
            st.markdown(f"**{nombre_estudiante}**")
            st.divider()
            
            st.metric("📖 Plan de Estudio", f"Malla {plan_estudio}")
            st.metric("📅 Año de Ingreso", ano_ingreso)
            st.metric("💎 UV Acumuladas", uv_acumuladas)
            
            st.divider()
            if st.button("🚪 Cerrar Sesión", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        # ==========================================
        # 🌟 ENCABEZADO Y PESTAÑAS
        # ==========================================
        st.markdown(f"# 👋 Hola, {nombre_estudiante.split()[0]}")
        st.markdown("<p style='font-size: 1.1rem; color: gray;'>Bienvenido a tu Portal Académico. Organiza tu futuro y revisa tus calificaciones.</p>", unsafe_allow_html=True)
        
        if es_egresando:
            st.success("🌟 **¡ERES ESTUDIANTE POR EGRESAR!**\n\nEl sistema ha detectado que estás en la recta final de tu carrera. Tus selecciones tendrán **prioridad máxima** en la generación de horarios de la Inteligencia Artificial.")

        st.write("")
        
        # 🔥 CREAMOS LAS DOS PESTAÑAS PRINCIPALES 🔥
        tab_proyeccion, tab_historial = st.tabs(["📝 Proyección de Matrícula", "📚 Mi Historial Académico"])

        # ==========================================
        # PESTAÑA 1: CENSO Y PROYECCIÓN
        # ==========================================
        with tab_proyeccion:
            query_censo = """
                SELECT c.Jornada_Preferencia, m.Codigo_Oficial, m.Nombre_Clase, m.Unidades_Valorativas
                FROM censo_periodo_actual c
                JOIN malla_curricular m ON c.ID_Clase = m.ID_Clase
                WHERE c.Hash_Cuenta = %s
            """
            df_censo = pd.read_sql(query_censo, conn, params=(hash_usuario,))

            if not df_censo.empty:
                with st.container(border=True):
                    st.markdown("### ✅ Censo Académico Registrado")
                    st.info("Ya has completado tu proyección para el próximo periodo. Jefatura tomará en cuenta tus selecciones para la creación de secciones.")
                    
                    df_censo['Hora'] = df_censo['Jornada_Preferencia'].map(MAPA_INVERSO).fillna(df_censo['Jornada_Preferencia'])
                    df_mostrar_censo = df_censo[['Codigo_Oficial', 'Nombre_Clase', 'Unidades_Valorativas', 'Hora']]
                    df_mostrar_censo.columns = ['Código', 'Asignatura', 'UV', 'Hora Preferida']
                    
                    st.dataframe(
                        df_mostrar_censo,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Código": st.column_config.TextColumn("📌 Código", width="small"),
                            "Asignatura": st.column_config.TextColumn("📘 Asignatura", width="large"),
                            "UV": st.column_config.NumberColumn("💎 UV", width="small"),
                            "Hora Preferida": st.column_config.TextColumn("⏰ Preferencia", width="medium")
                        }
                    )
                    st.caption(f"Total de Unidades Valorativas proyectadas: **{df_censo['Unidades_Valorativas'].sum()} UV**")
                    
            else:
                clases_del_plan = malla_df[malla_df['Plan_Perteneciente'] == plan_estudio]
                disponibles = []
                
                for _, c in clases_del_plan.iterrows():
                    if not es_clase_aprobada_o_equivalente(c['Codigo_Oficial'], aprobadas_set):
                        if cumple_prerrequisitos(c['Prerrequisitos'], aprobadas_set, uv_acumuladas):
                            disponibles.append({
                                "ID_Clase": c['ID_Clase'],
                                "Código": c['Codigo_Oficial'],
                                "Asignatura": c['Nombre_Clase'],
                                "UV": c['Unidades_Valorativas'],
                                "✅ Matricular": False,
                                "⏰ Preferencia": "Cualquiera / Sin preferencia"
                            })
                
                if not disponibles:
                    st.balloons()
                    st.success("🎓 **¡FELICIDADES!** Has aprobado todas las clases de tu plan de estudios. Ya no tienes asignaturas pendientes por matricular.")
                else:
                    st.markdown("### 📋 Formulario de Proyección de Matrícula")
                    st.warning("**Instrucciones:** Selecciona las clases que deseas llevar el próximo periodo y elige el horario en el que te gustaría recibirlas.")
                    
                    df_disp = pd.DataFrame(disponibles)
                    edited_df = st.data_editor(
                        df_disp,
                        use_container_width=True,
                        hide_index=True,
                        disabled=["Código", "Asignatura", "UV"],
                        column_config={
                            "ID_Clase": None,
                            "Código": st.column_config.TextColumn("📌 Código", width="small"),
                            "Asignatura": st.column_config.TextColumn("📘 Asignatura", width="large"),
                            "UV": st.column_config.NumberColumn("💎 UV", width="small"),
                            "✅ Matricular": st.column_config.CheckboxColumn("✅ Seleccionar", width="small"),
                            "⏰ Preferencia": st.column_config.SelectboxColumn(
                                "⏰ Horario Preferido",
                                options=list(MAPA_HORAS_UI.keys()),
                                width="medium"
                            )
                        }
                    )
                    
                    st.write("")
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        if st.button("🚀 Confirmar y Enviar mi Censo", type="primary", use_container_width=True):
                            seleccionadas = edited_df[edited_df["✅ Matricular"] == True]
                            if seleccionadas.empty:
                                st.error("⚠️ Debes seleccionar al menos una clase antes de enviar tu proyección.")
                            else:
                                cursor = conn.cursor()
                                try:
                                    prioridad_db = 2 if es_egresando else 1
                                    for _, row in seleccionadas.iterrows():
                                        id_c = int(row["ID_Clase"])
                                        hora_db = MAPA_HORAS_UI[row["⏰ Preferencia"]]
                                        cursor.execute("""
                                            INSERT INTO censo_periodo_actual (Hash_Cuenta, ID_Clase, Jornada_Preferencia, Prioridad_Alumno)
                                            VALUES (%s, %s, %s, %s)
                                        """, (hash_usuario, id_c, hora_db, prioridad_db))
                                    conn.commit()
                                    st.balloons()
                                    st.success("✅ ¡Tu censo ha sido guardado exitosamente!")
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"❌ Ocurrió un error al guardar: {e}")

        # ==========================================
        # PESTAÑA 2: HISTORIAL ACADÉMICO (CORREGIDA)
        # ==========================================
        with tab_historial:
            st.markdown("### 📚 Récord de Calificaciones")
            
            if df_historial.empty:
                st.info("Aún no tienes un historial académico registrado en el sistema.")
            else:
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    # Mostrar métricas sin las reprobadas
                    total_aprobadas = len(df_historial[df_historial['Estado'] == 'Aprobado'])
                    st.metric("✔️ Clases Aprobadas", total_aprobadas)
                
                with col2:
                    # Botón de Descarga CSV
                    csv_data = df_historial.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Descargar Historial (CSV)",
                        data=csv_data,
                        file_name=f"historial_academico_{nombre_estudiante.replace(' ', '_')}.csv",
                        mime='text/csv',
                        use_container_width=True
                    )
                
                st.write("")
                
                # ORDENAMIENTO CRONOLÓGICO: Año (Desc) y luego Periodo (Desc)
                periodos_unicos = sorted(
                    df_historial['Periodo'].unique(), 
                    key=lambda x: (int(x.split('-')[1]), int(x.split('-')[0])), 
                    reverse=True
                )
                
                for per in periodos_unicos:
                    df_per = df_historial[df_historial['Periodo'] == per].drop(columns=['Periodo'])
                    uv_per = df_per[df_per['Estado'] == 'Aprobado']['UV'].sum()
                    
                    with st.expander(f"📅 Periodo: {per} — ({uv_per} UV Aprobadas)", expanded=True):
                        st.dataframe(
                            df_per.style.map(lambda x: 'color: green' if x == 'Aprobado' else 'color: red', subset=['Estado']),
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Código": st.column_config.TextColumn(width="small"),
                                "Asignatura": st.column_config.TextColumn(width="large"),
                                "UV": st.column_config.NumberColumn(width="small"),
                                "Estado": st.column_config.TextColumn(width="small")
                            }
                        )

    except Exception as e:
        st.error(f"Error procesando la vista: {e}")
    finally:
        conn.close()