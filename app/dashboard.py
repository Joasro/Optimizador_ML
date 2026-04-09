import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import streamlit.components.v1 as components
import datetime
import streamlit as st
import hashlib
import pandas as pd
from config.db_connection import get_connection
from app.student_portal import vista_estudiante
from app.teacher_portal import vista_docente

st.set_page_config(page_title="Optimizador Académico UNAH", layout="wide", page_icon="🎓")

# ----------------------
# Funciones varias
# ----------------------
def hash_data(data):
    return hashlib.sha256(str(data).encode()).hexdigest()

def sugerir_siguiente_periodo(ultimo_periodo, ano_ingreso):
    if not ultimo_periodo:
        return f"1-{ano_ingreso}"
    try:
        p, a = map(int, ultimo_periodo.split('-'))
        if p >= 3:
            return f"1-{a + 1}"
        else:
            return f"{p + 1}-{a}"
    except:
        return f"1-{ano_ingreso}"

def evaluar_prerrequisitos(req_text, ids_aprobados, total_uv, mapa_codes):
    if not req_text or str(req_text).lower() in ['ninguno', 'nan', 'null', '']:
        return True
    if "140 uv" in str(req_text).lower():
        return total_uv >= 140
    req_codes = [r.strip().upper() for r in str(req_text).split(',')]
    for code in req_codes:
        req_id = mapa_codes.get(code)
        if req_id and req_id not in ids_aprobados:
            return False
    return True

# ----------------------
# Login y sesión
# ----------------------
def inicializar_sesion():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['user_role'] = None
        st.session_state['user_name'] = None
        st.session_state['user_hash'] = None

def cerrar_sesion():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ==========================================
# Vista principal admin
# ----------------------
def vista_jefe_departamento():
    from sqlalchemy import create_engine
    import app.gestion_docentes as gd 
    
    # Sidebar
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2942/2942813.png", width=100)
        st.title(f"👨‍💻 Jefatura")
        st.markdown(f"**{st.session_state['user_name']}**")
        st.caption("Administrador del Sistema")
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            cerrar_sesion()

    # Encabezado
    st.markdown("# 🛡️ Panel de Control Principal")
    st.markdown("<p style='font-size: 1.1rem; color: gray;'>Gestión integral del departamento de Ingeniería en Sistemas, inteligencia artificial y logística académica.</p>", unsafe_allow_html=True)
    st.write("")

 
    tab_ia, tab4, tab5, tab6, tab_historial_clases = st.tabs([
        "📅 Generar Horarios (IA)",
        "📊 Estadísticas",
        "👨‍🏫 Gestión Docente",
        "📡 Censo en Vivo",
        "📜 Historial de Clases"
    ])

    if 'historial_temporal' not in st.session_state:
        st.session_state['historial_temporal'] = []

    EQUIVALENCIAS = {
        'ISC-101': ['IS-110'], 'ISC-102': ['IS-210'], 'ISC-103': ['IS-410'],
        'ISC-211': ['IS-310'], 'ISC-321': ['IS-501'], 'ISC-422': ['IS-601'],
        'ISC-341': ['IS-602'], 'ISC-306': ['IS-702'], 'IE-326': ['IS-311', 'IS-510'],
        'ISC-331': ['IS-511'], 'ISC-332': ['IS-611'], 'ISC-333': ['IS-412'],
        'ISC-334': ['IS-512'], 'ISC-552': ['IS-115'], 'ISC-408': ['IS-802'],
        'ISC-414': ['IS-710'], 'ISC-336': ['IS-711'], 'ISC-437': ['IS-603']
    }

    # Tab 1: Crear estudiante
    if False: # Módulo oculto. Antes era: with tab1:
        st.markdown("### 📝 Creación de Nuevo Expediente")
        
        with st.container(border=True):
            st.markdown("#### 1. Datos Personales y Académicos")
            nombre = st.text_input("Nombre Completo")
            col1, col2 = st.columns(2)
            correo_est = col1.text_input("Correo Institucional")
            pass_est = col2.text_input("Contraseña Temporal", type="password")
            
            ano_ing = st.number_input("Año de Ingreso", 2015, 2030, 2024)
            
            if ano_ing < 2026:
                st.info("💡 **Transición de Malla:** Alumno de reingreso. Especifica cómo visualizar su historial base.")
                c_rad1, c_rad2 = st.columns(2)
                plan_historial = c_rad1.radio("Mostrar Malla Base:", ["2021", "2025"], index=0, horizontal=True)
                plan_actual = c_rad2.radio("Plan Oficial Vigente (IPAC 2026):", ["2021", "2025"], index=1, horizontal=True)
            else:
                st.success("💡 **Nuevo Ingreso:** Pertenece automáticamente y al 100% al Plan 2025.")
                plan_historial = "2025"
                plan_actual = "2025"
            
        st.write("")
        st.markdown("#### 2. Reconstrucción de Historial (Carrito de Clases)")
        
        conn = get_connection()
        malla_df = pd.read_sql(f"SELECT ID_Clase, Codigo_Oficial, Nombre_Clase, Prerrequisitos, Unidades_Valorativas FROM Malla_Curricular WHERE Plan_Perteneciente = '{plan_historial}'", conn)
        conn.close()
        
        if not malla_df.empty:
            aprobadas_actuales = set()
            uv_acumuladas = 0
            
            for reg in st.session_state['historial_temporal']:
                if reg['Estado'] == 'Aprobado':
                    aprobadas_actuales.add(reg['Codigo'])
                    uv_val = malla_df.loc[malla_df['Codigo_Oficial'] == reg['Codigo'], 'Unidades_Valorativas']
                    if not uv_val.empty:
                        uv_acumuladas += int(uv_val.values[0])
            
            def cumple_prerrequisitos_ui(prereq_str, aprobadas, uv_actuales):
                if pd.isna(prereq_str) or str(prereq_str).strip().lower() in ['ninguno', 'nan', '']: return True
                prereqs = [p.strip() for p in str(prereq_str).split(',')]
                for p in prereqs:
                    if 'UV' in p.upper():
                        import re
                        nums = re.findall(r'\d+', p)
                        if nums and uv_actuales < int(nums[0]): return False 
                    else:
                        if p in aprobadas: continue 
                        equiv_fulfilled = False
                        if p in EQUIVALENCIAS:
                            if all(old_c in aprobadas for old_c in EQUIVALENCIAS[p]): equiv_fulfilled = True
                        if not equiv_fulfilled: return False 
                return True

            clases_desbloqueadas = []
            for _, row in malla_df.iterrows():
                if row['Codigo_Oficial'] not in aprobadas_actuales:
                    if cumple_prerrequisitos_ui(row['Prerrequisitos'], aprobadas_actuales, uv_acumuladas):
                        clases_desbloqueadas.append(row.to_dict())
            
            # Métricas
            c_met1, c_met2 = st.columns(2)
            c_met1.metric("✔️ Clases Aprobadas en Carrito", len(aprobadas_actuales))
            c_met2.metric("💎 UV Proyectadas", uv_acumuladas)
            
            if clases_desbloqueadas:
                with st.container(border=True):
                    col_per, col_cla, col_est = st.columns([1.5, 3, 1.5])
                    with col_per:
                        periodo_ind = st.text_input("Periodo (Ej: 1-2024)", value=f"1-{ano_ing}")
                    with col_cla:
                        clase_ind = st.selectbox("Asignatura Desbloqueada", options=[c['ID_Clase'] for c in clases_desbloqueadas], format_func=lambda x: next(f"{c['Codigo_Oficial']} - {c['Nombre_Clase']}" for c in clases_desbloqueadas if c['ID_Clase'] == x))
                    with col_est:
                        estado_ind = st.selectbox("Estado final", ["Aprobado", "Reprobado"])
                    
                    if st.button("➕ Agregar al Historial", type="secondary", use_container_width=True):
                        if periodo_ind:
                            nombre_c = next(c['Nombre_Clase'] for c in clases_desbloqueadas if c['ID_Clase'] == clase_ind)
                            codigo_c = next(c['Codigo_Oficial'] for c in clases_desbloqueadas if c['ID_Clase'] == clase_ind)
                            duplicado = any(x['ID_Clase'] == clase_ind and x['Periodo'] == periodo_ind for x in st.session_state['historial_temporal'])
                            if duplicado:
                                st.warning("⚠️ Ya agregaste esta clase en este mismo periodo.")
                            else:
                                st.session_state['historial_temporal'].append({'ID_Clase': clase_ind, 'Codigo': codigo_c, 'Clase': nombre_c, 'Periodo': periodo_ind, 'Estado': estado_ind})
                                st.rerun() 
                        else:
                            st.warning("⚠️ Debes escribir un Periodo válido.")
            else:
                st.success("🎉 ¡El estudiante ha completado todas las asignaturas mostradas en esta malla!")

        if st.session_state['historial_temporal']:
            st.markdown("#### 🛒 Clases Listas para Guardar")
            with st.container(border=True):
                col_hp, col_hc, col_hn, col_he, col_hx = st.columns([1.5, 1.5, 3, 1.5, 1])
                col_hp.markdown("**Periodo**"); col_hc.markdown("**Código**"); col_hn.markdown("**Asignatura**"); col_he.markdown("**Estado**"); col_hx.markdown("**Acción**")
                
                for i, reg in enumerate(st.session_state['historial_temporal']):
                    cp, cc, cn, ce, cx = st.columns([1.5, 1.5, 3, 1.5, 1])
                    cp.write(reg['Periodo'])
                    cc.write(reg['Codigo'])
                    cn.write(reg['Clase'])
                    color = "green" if reg['Estado'] == "Aprobado" else "red"
                    ce.markdown(f":{color}[{reg['Estado']}]")
                    if cx.button("❌", key=f"del_{i}", help="Eliminar esta clase"):
                        st.session_state['historial_temporal'].pop(i)
                        st.rerun()
                
            if st.button("🗑️ Vaciar Carrito", type="secondary"):
                st.session_state['historial_temporal'] = []
                st.rerun()

        st.write("")
        if st.button("💾 Crear Expediente y Guardar Historial", type="primary", use_container_width=True):
            if not (nombre and correo_est and pass_est) or not st.session_state['historial_temporal']:
                st.error("⚠️ Faltan datos básicos o el historial está vacío.")
            else:
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    hash_user = hash_data(correo_est)
                    cursor.execute("INSERT INTO Usuarios (Hash_Cuenta, Nombre_Completo, Correo_Institucional, Contrasena, Rol) VALUES (%s, %s, %s, %s, 'Estudiante')", 
                                   (hash_user, nombre, correo_est, hash_data(pass_est)))
                    cursor.execute("INSERT INTO Estudiantes (Hash_Cuenta, Plan_Estudio, Ano_Ingreso) VALUES (%s, %s, %s)", 
                                   (hash_user, plan_actual, ano_ing))
                    for reg in st.session_state['historial_temporal']:
                        cursor.execute("INSERT INTO Historial_Academico (Hash_Cuenta, ID_Clase, Estado, Periodo_Cursado) VALUES (%s, %s, %s, %s)",
                                       (hash_user, reg['ID_Clase'], reg['Estado'], reg['Periodo']))
                    conn.commit()
                    st.success(f"✅ ¡Éxito! Estudiante guardado correctamente.")
                    st.session_state['historial_temporal'] = [] 
                except Exception as e:
                    st.error(f"❌ Error BD: {e}")
                finally:
                    conn.close()

    # Tab 2: Matricular clases
    if False: # Módulo oculto. Antes era: with tab2:
        st.markdown("### 📚 Matricular Nuevo Periodo")
        
        conn = get_connection()
        estudiantes_df = pd.read_sql("""
            SELECT u.Hash_Cuenta, u.Nombre_Completo, u.Correo_Institucional, e.Plan_Estudio
            FROM Usuarios u JOIN Estudiantes e ON u.Hash_Cuenta = e.Hash_Cuenta
        """, conn)
        conn.close()
        
        if estudiantes_df.empty:
            st.info("No hay estudiantes registrados en el sistema.")
        else:
            with st.container(border=True):
                estudiante_seleccionado = st.selectbox(
                    "🔍 Buscar Estudiante:",
                    estudiantes_df['Hash_Cuenta'].tolist(),
                    format_func=lambda x: estudiantes_df[estudiantes_df['Hash_Cuenta'] == x]['Nombre_Completo'].values[0]
                )
            
            est_info = estudiantes_df[estudiantes_df['Hash_Cuenta'] == estudiante_seleccionado].iloc[0]
            estudiante_plan = est_info['Plan_Estudio']
            
            conn = get_connection()
            historial_df = pd.read_sql(f"""
                SELECT h.ID_Registro, h.Estado, h.Periodo_Cursado, m.Codigo_Oficial, m.Nombre_Clase, m.Unidades_Valorativas
                FROM Historial_Academico h JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
                WHERE h.Hash_Cuenta = '{estudiante_seleccionado}'
            """, conn)
            malla_df = pd.read_sql(f"SELECT * FROM Malla_Curricular WHERE Plan_Perteneciente = '{estudiante_plan}'", conn)
            conn.close()
            
            aprobadas_set = set(historial_df[historial_df['Estado'] == 'Aprobado']['Codigo_Oficial'].tolist())
            uv_acumuladas = historial_df[historial_df['Estado'] == 'Aprobado']['Unidades_Valorativas'].fillna(0).astype(int).sum()
            
            # Métricas
            c_info1, c_info2, c_info3 = st.columns(3)
            c_info1.metric("📖 Plan Vigente", estudiante_plan)
            c_info2.metric("✔️ Clases Aprobadas", len(aprobadas_set))
            c_info3.metric("💎 UV Oficiales", uv_acumuladas)
            
            def es_clase_aprobada_o_equivalente(codigo_clase, aprobadas):
                if codigo_clase in aprobadas: return True
                if codigo_clase in EQUIVALENCIAS:
                    if all(old_c in aprobadas for old_c in EQUIVALENCIAS[codigo_clase]): return True
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

            clases_desbloqueadas = []
            for _, row in malla_df.iterrows():
                if not es_clase_aprobada_o_equivalente(row['Codigo_Oficial'], aprobadas_set):
                    if cumple_prerrequisitos(row['Prerrequisitos'], aprobadas_set, uv_acumuladas):
                        clases_desbloqueadas.append(row.to_dict())
            
            st.write("")
            st.markdown("#### ➕ Registrar Nueva Calificación")
            if clases_desbloqueadas:
                with st.container(border=True):
                    col_p, col_c, col_e = st.columns([1.5, 3, 1.5])
                    with col_p:
                        nuevo_periodo = st.text_input("Periodo (Ej: 1-2026)")
                    with col_c:
                        nueva_clase_id = st.selectbox("Asignaturas Desbloqueadas", options=[c['ID_Clase'] for c in clases_desbloqueadas], format_func=lambda x: next(f"{c['Codigo_Oficial']} - {c['Nombre_Clase']}" for c in clases_desbloqueadas if c['ID_Clase'] == x))
                    with col_e:
                        nuevo_estado = st.selectbox("Estado", ["Aprobado", "Reprobado"])
                    
                    if st.button("💾 Guardar en Base de Datos", type="primary", use_container_width=True):
                        if nuevo_periodo:
                            conn = get_connection()
                            cursor = conn.cursor()
                            try:
                                cursor.execute("INSERT INTO Historial_Academico (Hash_Cuenta, ID_Clase, Estado, Periodo_Cursado) VALUES (%s, %s, %s, %s)",
                                            (estudiante_seleccionado, nueva_clase_id, nuevo_estado, nuevo_periodo))
                                conn.commit()
                                st.success("✅ Clase agregada al historial exitosamente.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error BD: {e}")
                            finally:
                                conn.close()
                        else:
                            st.warning("⚠️ Debes especificar el Periodo.")
            else:
                st.success("🎉 Este estudiante ya completó todas las asignaturas de su plan actual.")
            
            st.write("")
            st.markdown("#### 📋 Historial Oficial Registrado")
            if not historial_df.empty:
                with st.container(border=True):
                    for i, row in historial_df.iterrows():
                        cp, cc, cn, ce, cx = st.columns([1.5, 1.5, 3, 1.5, 1])
                        cp.write(row['Periodo_Cursado'])
                        cc.write(row['Codigo_Oficial'])
                        cn.write(row['Nombre_Clase'])
                        color = "green" if row['Estado'] == "Aprobado" else "red"
                        ce.markdown(f":{color}[{row['Estado']}]")
                        if cx.button("❌", key=f"del_bd_{row['ID_Registro']}", help="Eliminar permanentemente"):
                            conn = get_connection()
                            cursor = conn.cursor()
                            cursor.execute(f"DELETE FROM Historial_Academico WHERE ID_Registro = {row['ID_Registro']}")
                            conn.commit()
                            conn.close()
                            st.rerun()
            else:
                st.info("El historial de este estudiante está vacío.")

    # Tab 3: Editar historial
    if False: # Módulo oculto. Antes era: with tab_edit:
        st.markdown("### ✏️ Editor Masivo de Expediente")
        conn = get_connection()
        est_df_edit = pd.read_sql("""
            SELECT u.Hash_Cuenta, u.Nombre_Completo, u.Correo_Institucional, e.Ano_Ingreso, e.Plan_Estudio 
            FROM Usuarios u JOIN Estudiantes e ON u.Hash_Cuenta = e.Hash_Cuenta 
            WHERE u.Rol = 'Estudiante'
        """, conn)
        if not est_df_edit.empty:
            with st.container(border=True):
                sel_est_edit = st.selectbox("🔍 Buscar Estudiante:", options=est_df_edit['Hash_Cuenta'].tolist(),
                                            format_func=lambda x: est_df_edit[est_df_edit['Hash_Cuenta']==x]['Nombre_Completo'].values[0], key="edit_sel")
            info_edit = est_df_edit[est_df_edit['Hash_Cuenta'] == sel_est_edit].iloc[0]
            correo = info_edit['Correo_Institucional']
            num_cuenta = correo.split('@')[0].replace('estudiante', '') if 'estudiante' in correo else 'No definido'
            
            st.write("")
            # Perfil
            with st.container(border=True):
                st.markdown(f"#### 👤 {info_edit['Nombre_Completo']}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("📌 Cuenta", num_cuenta)
                c2.metric("🗓️ Ingreso", info_edit['Ano_Ingreso'])
                c3.metric("📚 Plan", info_edit['Plan_Estudio'])
                c4.markdown(f"**✉️ Correo:**<br><span style='font-size:14px'>{correo}</span>", unsafe_allow_html=True)
            
            st.write("")
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT h.ID_Clase, m.Codigo_Oficial, m.Nombre_Clase, h.Periodo_Cursado, h.Estado 
                FROM Historial_Academico h JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
                WHERE h.Hash_Cuenta = %s 
            """, (sel_est_edit,))
            hist_edit = cursor.fetchall()
            
            if not hist_edit:
                st.info("Este estudiante no tiene clases en su historial todavía.")
            else:
                df_hist = pd.DataFrame(hist_edit)
                periodos_unicos = df_hist['Periodo_Cursado'].unique()
                try:
                    periodos_ordenados = sorted(periodos_unicos, key=lambda x: (int(x.split('-')[1]), int(x.split('-')[0])), reverse=True)
                except:
                    periodos_ordenados = periodos_unicos
                
                st.markdown("#### 📖 Edición por Periodos")
                hubo_cambios = False
                for periodo in periodos_ordenados:
                    with st.expander(f"📅 Periodo: {periodo}", expanded=True):
                        df_periodo = df_hist[df_hist['Periodo_Cursado'] == periodo][['ID_Clase', 'Codigo_Oficial', 'Nombre_Clase', 'Estado']]
                        edited_df = st.data_editor(
                            df_periodo,
                            column_config={
                                "ID_Clase": None,
                                "Codigo_Oficial": st.column_config.TextColumn("Código", disabled=True),
                                "Nombre_Clase": st.column_config.TextColumn("Asignatura", disabled=True),
                                "Estado": st.column_config.SelectboxColumn("Estado", options=["Aprobado", "Reprobado", "🗑️ Eliminar"], required=True)
                            },
                            disabled=["Codigo_Oficial", "Nombre_Clase"], hide_index=True, key=f"editor_{periodo}_{sel_est_edit}", use_container_width=True
                        )
                        for index, row in edited_df.iterrows():
                            orig_row = df_periodo[df_periodo['ID_Clase'] == row['ID_Clase']]
                            if not orig_row.empty:
                                orig_estado = orig_row.iloc[0]['Estado']
                                nuevo_estado = row['Estado']
                                if orig_estado != nuevo_estado:
                                    if nuevo_estado == "🗑️ Eliminar":
                                        cursor.execute("DELETE FROM Historial_Academico WHERE Hash_Cuenta = %s AND ID_Clase = %s AND Periodo_Cursado = %s", (sel_est_edit, row['ID_Clase'], periodo))
                                    else:
                                        cursor.execute("UPDATE Historial_Academico SET Estado = %s WHERE Hash_Cuenta = %s AND ID_Clase = %s AND Periodo_Cursado = %s", (nuevo_estado, sel_est_edit, row['ID_Clase'], periodo))
                                    hubo_cambios = True
                if hubo_cambios:
                    conn.commit()
                    st.toast("✅ Base de datos actualizada exitosamente.")
                    st.rerun()
        conn.close()

    # Tab IA: Generar horarios y matriz
    with tab_ia:
        st.markdown("### Motor de horarios")
        st.write("Genera la planificación.")
        
        # Inicializar memoria
        if 'ia_exito' not in st.session_state:
            st.session_state['ia_exito'] = False
        if 'ia_alertas' not in st.session_state:
            st.session_state['ia_alertas'] = []
        
        from sqlalchemy import create_engine, text
        user = "Joasro"
        password = "Akriila123." 
        host = "localhost"
        db = "dss_academico_unah"
        engine_ia = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}/{db}")
        
        st.write("")
        if st.button("🚀 INICIAR OPTIMIZACIÓN LOGÍSTICA", type="primary", use_container_width=True):
            with st.spinner("⏳ 1/2 Analizando expedientes, modelo XGBoost y censo estudiantil..."):
                from src.ml.demand_model import predecir_demanda_estricta
                df_demanda = predecir_demanda_estricta(engine_ia)
                
            if df_demanda.empty:
                st.error("⚠️ No hay suficientes datos de demanda para generar un horario.")
            else:
                with st.spinner("⚙️ 2/2 Ejecutando Google OR-Tools para asignación física de aulas y docentes..."):
                    from src.optimizer.scheduler import ejecutar_optimizador
                    exito, alertas = ejecutar_optimizador(engine_ia)
                    
                if exito:
                    # Guardar y recargar
                    st.session_state['ia_exito'] = True
                    st.session_state['ia_alertas'] = alertas
                    st.rerun() # Esto fuerza la recarga para mostrar las alertas de inmediato
                else:
                    st.error(f"❌ Error en el motor: {alertas[0]}")
                    
        # Mostrar alertas
        if st.session_state.get('ia_exito', False):
            st.success("✅ ¡Matriz Generada y Guardada en Base de Datos Temporal!")
            
            if st.session_state.get('ia_alertas'):
                # Mostrar alertas en expander
                with st.expander("🚨 Alertas Logísticas: Análisis de Brechas (Gap Analysis)", expanded=True):
                    st.markdown("**El sistema detectó que la demanda superó la capacidad física de la infraestructura:**")
                    for alerta in st.session_state['ia_alertas']:
                        st.warning(alerta)
                    
        st.divider()
        st.markdown("### 📊 Propuesta Condensada de la IA")
        
        query_matriz = """
            SELECT o.ID_Seccion, o.Hora_Inicio, o.Hora_Fin, e.Nombre_Espacio as Aula, e.ID_Espacio,
                   m.Codigo_Oficial, m.Nombre_Clase, m.Unidades_Valorativas, d.Nombre as Docente, 
                   d.ID_Docente, o.Dias, o.Cupos_Maximos, d.Acepta_Virtualidad, d.Hora_Inicio_Virtual, d.Hora_Fin_Virtual
            FROM oferta_academica_generada o
            JOIN Malla_Curricular m ON o.ID_Clase = m.ID_Clase
            JOIN espacios_fisicos e ON o.ID_Espacio = e.ID_Espacio
            JOIN docentes_activos d ON o.ID_Docente = d.ID_Docente
        """
        # Mostrar tabla
        
        try:
            df_oferta = pd.read_sql(query_matriz, engine_ia)
        except:
            df_oferta = pd.DataFrame()
        
        if not df_oferta.empty:
            def limpiar_hora_visual(h):
                h_str = str(h).strip()
                if 'days' in h_str: return h_str.split('days')[1].strip()[:5]
                return h_str[:5]

            df_oferta['Hora_Inicio_Limpia'] = df_oferta['Hora_Inicio'].apply(limpiar_hora_visual)
            df_oferta['Hora_Fin_Limpia'] = df_oferta['Hora_Fin'].apply(limpiar_hora_visual)
            df_oferta['Hora_Rango'] = df_oferta['Hora_Inicio_Limpia'] + " - " + df_oferta['Hora_Fin_Limpia']

            docentes_unicos = df_oferta['Docente'].unique()
            paleta_colores = ['#4F8BF9', '#28a745', '#dc3545', '#ffc107', '#6f42c1', '#fd7e14', '#17a2b8', '#e83e8c', '#20c997', '#6c757d']
            mapa_colores = {doc: paleta_colores[i % len(paleta_colores)] for i, doc in enumerate(docentes_unicos)}
            df_oferta['Color_Docente'] = df_oferta['Docente'].map(mapa_colores)

            def extraer_hora_segura(valor_tiempo):
                if pd.isna(valor_tiempo): return None
                val_str = str(valor_tiempo).strip()
                if val_str in ['00:00:00', '0', 'None']: return None
                if 'days' in val_str: return int(val_str.split('days')[1].split(':')[0].strip())
                return int(val_str.split(':')[0])

            def determinar_modalidad_real(row):
                try:
                    h_clase = extraer_hora_segura(row['Hora_Inicio'])
                    if h_clase is None: return "🏫 Presencial"
                    acepta_virt = int(row['Acepta_Virtualidad']) if pd.notna(row['Acepta_Virtualidad']) else 0
                    if acepta_virt == 1:
                        ini_v = extraer_hora_segura(row['Hora_Inicio_Virtual'])
                        fin_v = extraer_hora_segura(row['Hora_Fin_Virtual'])
                        if ini_v is not None and fin_v is not None:
                            if ini_v <= h_clase < fin_v: return "📡 Teledocencia"
                    return "🏫 Presencial"
                except:
                    return "🏫 Presencial" 

            df_oferta['Modalidad_Texto'] = df_oferta.apply(determinar_modalidad_real, axis=1)

            df_oferta['Info_Celda'] = (
                "<div style='padding:8px; border-radius:5px; background-color:#f8f9fa; border-left:8px solid " + df_oferta['Color_Docente'] + "; margin-bottom:4px; font-size:12px; color:#333;'>"
                "<b style='color:#004085;'>" + df_oferta['Codigo_Oficial'] + "</b> - " + df_oferta['Nombre_Clase'] + "<br>"
                "👨‍🏫 <i>" + df_oferta['Docente'] + "</i><br>"
                "⚡ " + df_oferta['Unidades_Valorativas'].astype(str) + " UV | 📅 <b>" + df_oferta['Dias'] + "</b><br>"
                "<span style='color:#28a745; font-weight:bold;'>👥 Cupos: " + df_oferta['Cupos_Maximos'].astype(str) + "</span><br>"
                "<span style='font-weight:bold; color:#495057;'>" + df_oferta['Modalidad_Texto'] + "</span></div>"
            )

            matriz = df_oferta.pivot_table(index='Hora_Rango', columns='Aula', values='Info_Celda', aggfunc=lambda x: "".join(x)).fillna("")
            matriz = matriz.sort_index()
            matriz.index.name = "⌚ Hora / Aula 🏫"
            matriz.columns.name = ""
            
            html_raw = matriz.to_html(escape=False)
            html_limpio = html_raw.replace("\n", "")
            
            css_tabla = """
            <style>
                table.dataframe { width: 100%; border-collapse: collapse; font-family: sans-serif; background-color: white; margin-top: 15px; }
                table.dataframe thead th { background-color: #004085 !important; color: white !important; padding: 12px; text-align: center; border: 1px solid #dee2e6; }
                table.dataframe tbody th { background-color: #e9ecef !important; color: #333 !important; font-weight: bold; text-align: center; border: 1px solid #dee2e6; padding: 10px; width: 130px; }
                table.dataframe tbody td { border: 1px solid #dee2e6; padding: 8px; vertical-align: top; }
            </style>
            """.replace("\n", "")
            
            st.markdown(css_tabla + html_limpio, unsafe_allow_html=True)
            st.divider()
            
            st.divider()
            st.markdown("### 🛠️ Ajuste Manual de Secciones")
            st.markdown("<p style='color: gray; font-size: 15px;'>Modifica o elimina secciones generadas por la IA. Selecciona una sección para habilitar el panel de edición detallada.</p>", unsafe_allow_html=True)
            
            # 1. Selector de Sección a Editar
            opciones_sec = {f"{row['Codigo_Oficial']} - {row['Nombre_Clase']} ({row['Hora_Inicio_Limpia']} en {row['Aula']})": row['ID_Seccion'] for _, row in df_oferta.iterrows()}
            sec_seleccionada = st.selectbox("🔍 Buscar Sección en el periodo actual:", ["Seleccione..."] + list(opciones_sec.keys()))
            
            if sec_seleccionada != "Seleccione...":
                id_sec_edit = opciones_sec[sec_seleccionada]
                sec_actual = df_oferta[df_oferta['ID_Seccion'] == id_sec_edit].iloc[0]
                
                # Cargar catálogos
                df_docs = pd.read_sql("SELECT ID_Docente, Nombre FROM docentes_activos", engine_ia)
                dict_docs = dict(zip(df_docs['Nombre'], df_docs['ID_Docente']))
                df_esp = pd.read_sql("SELECT ID_Espacio, Nombre_Espacio FROM espacios_fisicos", engine_ia)
                dict_esp = dict(zip(df_esp['Nombre_Espacio'], df_esp['ID_Espacio']))
                
                # Función para limpiar y convertir la hora SQL a un objeto datetime.time compatible con Streamlit
                def parse_time_for_ui(time_obj):
                    if pd.isna(time_obj): return datetime.time(7, 0)
                    t_str = str(time_obj).split('days ')[-1].strip() if 'days' in str(time_obj) else str(time_obj).strip()
                    try:
                        parts = t_str.split(':')
                        return datetime.time(int(parts[0]), int(parts[1]))
                    except:
                        return datetime.time(7, 0)

                hora_i_actual = parse_time_for_ui(sec_actual['Hora_Inicio'])
                hora_f_actual = parse_time_for_ui(sec_actual['Hora_Fin'])
                
                # 2. PANEL DE EDICIÓN AVANZADO (Tarjeta Visual)
                with st.container(border=True):
                    # Cabecera de la tarjeta
                    st.markdown(f"#### 📝 Editando: <span style='color:#004085;'>{sec_actual['Codigo_Oficial']} - {sec_actual['Nombre_Clase']}</span>", unsafe_allow_html=True)
                    st.caption(f"**ID de Sección:** {id_sec_edit} | **Capacidad:** {sec_actual['Cupos_Maximos']} estudiantes")
                    st.write("")
                    
                    # División en dos columnas lógicas
                    col_edit1, col_edit2 = st.columns(2)
                    
                    with col_edit1:
                        st.markdown("**1. Recursos Físicos y Humanos**")
                        idx_doc = list(dict_docs.values()).index(sec_actual['ID_Docente']) if sec_actual['ID_Docente'] in dict_docs.values() else 0
                        nuevo_doc = st.selectbox("👨‍🏫 Ingeniero / Docente", list(dict_docs.keys()), index=idx_doc)
                        
                        idx_esp = list(dict_esp.values()).index(sec_actual['ID_Espacio']) if sec_actual['ID_Espacio'] in dict_esp.values() else 0
                        nueva_aula = st.selectbox("🏫 Aula / Laboratorio", list(dict_esp.keys()), index=idx_esp)
                        
                    with col_edit2:
                        st.markdown("**2. Programación Horaria**")
                        nuevo_dia = st.text_input("📅 Días de clase", value=sec_actual['Dias'])
                        
                        c_h1, c_h2 = st.columns(2)
                        nueva_hora_ini = c_h1.time_input("⏰ Hora Inicio", value=hora_i_actual, step=datetime.timedelta(minutes=30))
                        nueva_hora_fin = c_h2.time_input("⌛ Hora Fin", value=hora_f_actual, step=datetime.timedelta(minutes=30))
                        
                    st.write("")
                    st.divider()
                    
                    # 3. BOTONES DE ACCIÓN (Con UX mejorada)
                    col_btn1, col_btn2 = st.columns([1.5, 1])
                    
                    with col_btn1:
                        if st.button("💾 Guardar Ajustes en esta Sección", type="primary", use_container_width=True):
                            with engine_ia.begin() as con:
                                con.execute(text("""
                                    UPDATE oferta_academica_generada 
                                    SET ID_Docente = :d, 
                                        ID_Espacio = :e,
                                        Dias = :dias,
                                        Hora_Inicio = :hi,
                                        Hora_Fin = :hf
                                    WHERE ID_Seccion = :s
                                """), {
                                    "d": dict_docs[nuevo_doc], 
                                    "e": dict_esp[nueva_aula], 
                                    "dias": nuevo_dia,
                                    "hi": nueva_hora_ini.strftime('%H:%M:%S'),
                                    "hf": nueva_hora_fin.strftime('%H:%M:%S'),
                                    "s": id_sec_edit
                                })
                            st.success("✅ ¡Sección modificada y optimizada con éxito!")
                            st.rerun()
                            
                    with col_btn2:
                        # Expander de seguridad para eliminar (Previene desastres operativos)
                        with st.expander("⚠️ Eliminar", expanded=False):
                            st.markdown("¿Borrar sección del periodo?")
                            if st.button("🗑️ Confirmar", type="primary", use_container_width=True):
                                with engine_ia.begin() as con:
                                    con.execute(text("DELETE FROM oferta_academica_generada WHERE ID_Seccion = :s"), {"s": id_sec_edit})
                                st.warning("🚨 Sección eliminada.")
                                st.rerun()
            with st.container(border=True):
                st.markdown("<h3 style='text-align: center;'>Publicación Oficial</h3>", unsafe_allow_html=True)
                if st.button("✅ APROBAR Y PUBLICAR HORARIO", type="primary", use_container_width=True):
                    with engine_ia.begin() as con:
                        con.execute(text("UPDATE oferta_academica_generada SET Aprobado_Por_Jefatura = 1"))
                    st.success("🎉 ¡Oferta Académica Publicada! Visible para estudiantes y docentes.")
                    st.balloons()
        else:
            st.info("Aún no se ha generado la matriz. Haz clic en 'Iniciar Optimización Logística'.")

    # Tab 4: Estadísticas
    with tab4:
        st.markdown("### 📊 Inteligencia Demográfica")
        conn = get_connection()
        try:
            stats_df = pd.read_sql("SELECT Plan_Estudio, COUNT(*) as Total FROM Estudiantes GROUP BY Plan_Estudio", conn)
            if stats_df.empty:
                st.info("No hay datos suficientes para graficar.")
            else:
                total_alumnos = stats_df['Total'].sum()
                c1, c2, c3 = st.columns(3)
                c1.metric("👥 Población Total", total_alumnos)
                for i, row in stats_df.iterrows():
                    (c2 if i % 2 == 0 else c3).metric(f"🎓 Plan {row['Plan_Estudio']}", row['Total'])
                
                st.divider()
                with st.container(border=True):
                    st.markdown("#### Distribución por Plan de Estudios")
                    st.bar_chart(stats_df.set_index('Plan_Estudio'), color="#4F8BF9")
        except Exception as e:
            st.error(f"Error estadístico: {e}")
        finally:
            conn.close()

    # Tab 5: Gestión docente
    with tab5:
        user = "Joasro"; password = "Akriila123."; host = "localhost"; db = "dss_academico_unah"
        engine_admin = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}/{db}")
        gd.mostrar_gestion_docentes(engine_admin)

    # Tab 6: Censo en vivo
    with tab6:
        st.markdown("### 📡 Radar de Demanda (Tiempo Real)")
        st.write("Analiza las intenciones de matrícula de los estudiantes agrupadas por asignatura. Los estudiantes por egresar están marcados en amarillo para prioridad logística.")
        
        conn = get_connection()
        try:
            query_censo = """
                SELECT c.Jornada_Preferencia, m.Codigo_Oficial, m.Nombre_Clase, u.Nombre_Completo, c.Hash_Cuenta, e.Plan_Estudio
                FROM censo_periodo_actual c JOIN Malla_Curricular m ON c.ID_Clase = m.ID_Clase
                JOIN Usuarios u ON c.Hash_Cuenta = u.Hash_Cuenta JOIN Estudiantes e ON c.Hash_Cuenta = e.Hash_Cuenta
            """
            censo_df = pd.read_sql(query_censo, conn)

            if censo_df.empty:
                st.info("El radar no detecta respuestas en el censo actualmente.")
            else:
                historial_df = pd.read_sql("SELECT h.Hash_Cuenta, m.Codigo_Oficial FROM Historial_Academico h JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase WHERE h.Estado = 'Aprobado'", conn)
                malla_df = pd.read_sql("SELECT Codigo_Oficial, Plan_Perteneciente FROM Malla_Curricular", conn)
                dict_egresando = {}
                OPTATIVAS_2021 = ['IS-910', 'IS-911', 'IS-914', 'IS-912', 'IS-913']
                
                for hash_c in censo_df['Hash_Cuenta'].unique():
                    plan_est = censo_df[censo_df['Hash_Cuenta'] == hash_c].iloc[0]['Plan_Estudio']
                    aprobadas_set = set(historial_df[historial_df['Hash_Cuenta'] == hash_c]['Codigo_Oficial'].tolist())
                    malla_carrera = malla_df[(malla_df['Plan_Perteneciente'] == plan_est) & (malla_df['Codigo_Oficial'].str.startswith(('IS', 'ISC', 'IE')))]
                    
                    if plan_est == '2021':
                        malla_core = malla_carrera[~malla_carrera['Codigo_Oficial'].isin(OPTATIVAS_2021)]
                        core_faltantes = len(malla_core) - len([c for c in aprobadas_set if c in malla_core['Codigo_Oficial'].values])
                        optativas_faltantes = max(0, 3 - len([c for c in aprobadas_set if c in OPTATIVAS_2021]))
                        total_faltantes = core_faltantes + optativas_faltantes
                    else:
                        total_faltantes = len(malla_carrera) - len([c for c in aprobadas_set if c in malla_carrera['Codigo_Oficial'].values])
                        
                    dict_egresando[hash_c] = total_faltantes <= 8

                censo_df['Es_Egresando'] = censo_df['Hash_Cuenta'].map(dict_egresando)
                resumen_clases = censo_df.groupby(['Codigo_Oficial', 'Nombre_Clase']).size().reset_index(name='Total_Solicitudes').sort_values(by='Total_Solicitudes', ascending=False)
                
                HORAS_CENSO = {
                    "07:00:00": "07:00 AM - 08:00 AM", "08:00:00": "08:00 AM - 09:00 AM", 
                    "09:00:00": "09:00 AM - 10:00 AM", "10:00:00": "10:00 AM - 11:00 AM", 
                    "11:00:00": "11:00 AM - 12:00 PM", "12:00:00": "12:00 PM - 01:00 PM",
                    "13:00:00": "01:00 PM - 02:00 PM", "14:00:00": "02:00 PM - 03:00 PM", 
                    "15:00:00": "03:00 PM - 04:00 PM", "16:00:00": "04:00 PM - 05:00 PM", 
                    "17:00:00": "05:00 PM - 06:00 PM", "18:00:00": "06:00 PM - 07:00 PM", 
                    "19:00:00": "07:00 PM - 08:00 PM", "20:00:00": "08:00 PM - 09:00 PM"
                }

                st.divider()
                for _, row in resumen_clases.iterrows():
                    cod, nom, total = row['Codigo_Oficial'], row['Nombre_Clase'], row['Total_Solicitudes']
                    estudiantes_clase = censo_df[censo_df['Codigo_Oficial'] == cod]
                    num_egresandos = estudiantes_clase['Es_Egresando'].sum()
                    alerta = f" | 🚨 {num_egresandos} por egresar" if num_egresandos > 0 else ""
                    
                    with st.expander(f"📚 {cod} - {nom} | 👥 {total} solicitudes {alerta}"):
                        detail_df = estudiantes_clase[['Nombre_Completo', 'Jornada_Preferencia', 'Es_Egresando']].copy()
                        detail_df['Hora Solicitada'] = detail_df['Jornada_Preferencia'].apply(lambda x: HORAS_CENSO.get(x, x))
                        detail_df['Estado'] = detail_df['Es_Egresando'].apply(lambda x: "Por Egresar" if x else "Regular")
                        detail_df = detail_df.sort_values(by='Es_Egresando', ascending=False)[['Nombre_Completo', 'Hora Solicitada', 'Estado']]
                        detail_df.rename(columns={'Nombre_Completo': 'Estudiante'}, inplace=True)
                        
                        def color_egresando(row):
                            if row['Estado'] == 'Por Egresar': return ['background-color: #FFF3CD; color: #212529; font-weight: bold' for _ in row]
                            return ['' for _ in row]
                        
                        st.dataframe(detail_df.style.apply(color_egresando, axis=1), use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error de radar: {e}")
        finally:
            conn.close()   

    # Tab 7: Historial de clases
    with tab_historial_clases:
        st.markdown("### Base de conocimiento")
        st.write("Registra cómo se impartieron las asignaturas antes.")

        conn = get_connection()
        try:
            df_clases = pd.read_sql("SELECT ID_Clase, Codigo_Oficial, Nombre_Clase FROM Malla_Curricular WHERE Codigo_Oficial LIKE 'IS%' OR Codigo_Oficial LIKE 'ISC%' OR Codigo_Oficial LIKE 'IE%'", conn)
            df_docentes = pd.read_sql("SELECT ID_Docente, Nombre FROM docentes_activos", conn)
            df_espacios = pd.read_sql("SELECT ID_Espacio, Nombre_Espacio FROM espacios_fisicos", conn)

            with st.container(border=True):
                st.markdown("#### ➕ Nuevo Registro Histórico")
                col1, col2 = st.columns(2)
                
                with col1:
                    per_hist_input = st.text_input("Periodo Académico", placeholder="Ej: 3-2024")
                    opciones_clases = df_clases['ID_Clase'].tolist()
                    formato_clase = lambda x: f"{df_clases[df_clases['ID_Clase'] == x]['Codigo_Oficial'].values[0]} - {df_clases[df_clases['ID_Clase'] == x]['Nombre_Clase'].values[0]}"
                    clase_hist_sel = st.selectbox("Asignatura", options=opciones_clases, format_func=formato_clase)
                    
                    opciones_docentes = [None] + df_docentes['ID_Docente'].tolist()
                    formato_docente = lambda x: "Sin asignar / No aplica" if x is None else df_docentes[df_docentes['ID_Docente'] == x]['Nombre'].values[0]
                    docente_hist_sel = st.selectbox("Ingeniero(a) que la impartió", options=opciones_docentes, format_func=formato_docente)

                with col2:
                    opciones_espacios = [None] + df_espacios['ID_Espacio'].tolist()
                    formato_espacio = lambda x: "Sin asignar / Virtual" if x is None else df_espacios[df_espacios['ID_Espacio'] == x]['Nombre_Espacio'].values[0]
                    espacio_hist_sel = st.selectbox("Laboratorio/Aula donde se impartió", options=opciones_espacios, format_func=formato_espacio)
                    
                    st.write("Horario Impartido:")
                    c_h1, c_h2 = st.columns(2)
                    hora_in_hist = c_h1.time_input("Hora de Inicio", value=datetime.time(7, 0), step=datetime.timedelta(hours=1))
                    hora_out_hist = c_h2.time_input("Hora de Fin", value=datetime.time(8, 0), step=datetime.timedelta(hours=1))
                
                st.write("")
                if st.button("💾 Guardar y Entrenar Memoria de IA", type="primary", use_container_width=True):
                    if per_hist_input and hora_in_hist and hora_out_hist:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO historial_oferta_academica (Periodo_Academico, ID_Clase, ID_Docente, ID_Espacio, Hora_Inicio, Hora_Fin) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (per_hist_input, clase_hist_sel, docente_hist_sel, espacio_hist_sel, hora_in_hist.strftime('%H:%M:%S'), hora_out_hist.strftime('%H:%M:%S')))
                        conn.commit()
                        st.success("✅ ¡Registro histórico guardado en el núcleo de la IA!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Faltan datos críticos para registrar.")

            st.divider()
            
            # Corrección de duplicados
            st.markdown("### 📋 Conocimiento Histórico Consolidado")
            
            df_historial_conocimiento = pd.read_sql("""
                SELECT h.ID_Historial, h.Periodo_Academico, m.Codigo_Oficial, d.Nombre as Docente, 
                       e.Nombre_Espacio as Aula, h.Hora_Inicio, h.Hora_Fin
                FROM historial_oferta_academica h
                LEFT JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
                LEFT JOIN docentes_activos d ON h.ID_Docente = d.ID_Docente
                LEFT JOIN espacios_fisicos e ON h.ID_Espacio = e.ID_Espacio
                ORDER BY h.Periodo_Academico DESC, m.Codigo_Oficial ASC
            """, conn)
            
            if not df_historial_conocimiento.empty:
                
                # --- 🛠️ CORRECCIÓN DE FORMATO DE HORA (NANO-SEGUNDOS Y TIMEDELTAS) ---
                # --- 🛠️ CORRECCIÓN DEFINITIVA DE FORMATO DE HORA ---
                def limpiar_hora_historial(val):
                    import re
                    import datetime
                    
                    if pd.isna(val) or val == "": 
                        return "N/A"
                    
                    # 1. Si es un objeto de tiempo nativo de Python/Pandas
                    if isinstance(val, (pd.Timedelta, datetime.timedelta)):
                        segundos = val.total_seconds()
                        h = int(segundos // 3600)
                        m = int((segundos % 3600) // 60)
                        ampm = "AM" if h < 12 else "PM"
                        h12 = h if h <= 12 else h - 12
                        if h12 == 0: h12 = 12
                        return f"{h12:02d}:{m:02d} {ampm}"
                    
                    val_str = str(val).strip()
                    
                    # 2. Extractor de Regex (Captura directamente "08:00" ignorando el "0 days")
                    match = re.search(r'(\d+):(\d+)', val_str)
                    if match:
                        h = int(match.group(1))
                        m = int(match.group(2))
                        ampm = "AM" if h < 12 else "PM"
                        h12 = h if h <= 12 else h - 12
                        if h12 == 0: h12 = 12
                        return f"{h12:02d}:{m:02d} {ampm}"
                        
                    # 3. Si viene como nanosegundos (ej. 46800000000000)
                    try:
                        ns = float(val_str)
                        if ns > 1000000:
                            segundos = ns / 1e9
                            h = int(segundos // 3600)
                            m = int((segundos % 3600) // 60)
                            ampm = "AM" if h < 12 else "PM"
                            h12 = h if h <= 12 else h - 12
                            if h12 == 0: h12 = 12
                            return f"{h12:02d}:{m:02d} {ampm}"
                    except ValueError:
                        pass
                        
                    # 4. Si dice "8 hours"
                    if 'hour' in val_str.lower():
                        nums = re.findall(r'\d+', val_str)
                        if nums:
                            h = int(nums[0])
                            ampm = "AM" if h < 12 else "PM"
                            h12 = h if h <= 12 else h - 12
                            if h12 == 0: h12 = 12
                            return f"{h12:02d}:00 {ampm}"
                            
                    return val_str[:5]

                # Aplicamos la limpieza a las horas
                df_historial_conocimiento['Hora_Inicio'] = df_historial_conocimiento['Hora_Inicio'].apply(limpiar_hora_historial)
                df_historial_conocimiento['Hora_Fin'] = df_historial_conocimiento['Hora_Fin'].apply(limpiar_hora_historial)

                # ==========================================
                # AGRUPACIÓN VISUAL POR PERIODO ACADÉMICO
                # ==========================================
                periodos_unicos = df_historial_conocimiento['Periodo_Academico'].unique()
                
                for per in periodos_unicos:
                    # Filtramos los datos para este periodo específico
                    df_per = df_historial_conocimiento[df_historial_conocimiento['Periodo_Academico'] == per]
                    
                    # Creamos un acordeón (expander) por cada periodo
                    with st.expander(f"📅 Periodo Académico: {per} — ({len(df_per)} secciones registradas)", expanded=True):
                        # Mostramos la tabla ocultando la columna de Periodo para no ser redundantes
                        st.dataframe(
                            df_per.drop(columns=['Periodo_Academico']), 
                            use_container_width=True, 
                            hide_index=True,
                            column_config={
                                "ID_Historial": st.column_config.NumberColumn("ID", width="small"),
                                "Codigo_Oficial": st.column_config.TextColumn("Código", width="small"),
                                "Docente": st.column_config.TextColumn("👨‍🏫 Docente", width="large"),
                                "Aula": st.column_config.TextColumn("🏫 Aula", width="medium"),
                                "Hora_Inicio": st.column_config.TextColumn("⏰ Inicio", width="small"),
                                "Hora_Fin": st.column_config.TextColumn("⌛ Fin", width="small")
                            }
                        )
                
                st.write("") # Espaciado
                
                with st.container(border=True):
                    st.markdown("#### ✏️ Edición Fina de Registros")
                    dic_registros = {f"[{row['Periodo_Academico']}] {row['Codigo_Oficial']} - {row['Hora_Inicio']} en {row['Aula']}": row['ID_Historial'] for _, row in df_historial_conocimiento.iterrows()}
                    sel_registro = st.selectbox("🔍 Buscar registro histórico a corregir:", ["Seleccione..."] + list(dic_registros.keys()))
                    
                    if sel_registro != "Seleccione...":
                        id_edit = dic_registros[sel_registro]
                        df_actual = pd.read_sql(f"SELECT * FROM historial_oferta_academica WHERE ID_Historial = {id_edit}", conn)
                        datos_actuales = df_actual.iloc[0]
                        
                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            edit_per = st.text_input("📝 Editar Periodo", value=datos_actuales['Periodo_Academico'])
                            id_docente_actual = datos_actuales['ID_Docente']
                            idx_doc = opciones_docentes.index(id_docente_actual) if id_docente_actual in opciones_docentes else 0
                            edit_docente = st.selectbox("👨‍🏫 Cambiar Docente", options=opciones_docentes, format_func=formato_docente, index=idx_doc, key="ed_doc")
                            
                        with col_e2:
                            id_espacio_actual = datos_actuales['ID_Espacio']
                            idx_esp = opciones_espacios.index(id_espacio_actual) if id_espacio_actual in opciones_espacios else 0
                            edit_espacio = st.selectbox("🏫 Cambiar Aula", options=opciones_espacios, format_func=formato_espacio, index=idx_esp, key="ed_esp")
                            
                            st.write(" "); st.write(" ")
                            c_btn1, c_btn2 = st.columns(2)
                            if c_btn1.button("💾 Sobrescribir", use_container_width=True):
                                cursor = conn.cursor()
                                cursor.execute("UPDATE historial_oferta_academica SET Periodo_Academico = %s, ID_Docente = %s, ID_Espacio = %s WHERE ID_Historial = %s", (edit_per, edit_docente, edit_espacio, id_edit))
                                conn.commit()
                                st.success("✅ Registro actualizado.")
                                st.rerun()
                            if c_btn2.button("🗑️ Borrar Dato", type="primary", use_container_width=True):
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM historial_oferta_academica WHERE ID_Historial = %s", (id_edit,))
                                conn.commit()
                                st.rerun()
            else:
                st.info("La tabla de conocimiento histórico está vacía.")
        except Exception as e:
            st.error(f"Error al cargar la interfaz de historial: {e}")
        finally:
            conn.close()

# ----------------------
# Main app routing
# ----------------------

# ----------------------
# Estilos visuales login
# ----------------------
def apply_login_styles():
    st.markdown(
        """
        <style>
        /* Contenedor central del login (AHORA TRANSPARENTE Y LIMPIO) */
        .login-container {
            background-color: transparent; 
            padding: 10px 0px;
            text-align: center;
            margin-bottom: 5px;
        }

        /* Estilo para los títulos */
        .login-title {
            color: #003366; /* Azul Institucional UNAH */
            font-weight: 900;
            font-size: 32px;
            margin-bottom: 0px;
            padding-bottom: 0px;
        }
        
        .login-subtitle {
            color: #555555;
            font-size: 16px;
            font-weight: 500;
            margin-top: 5px;
            margin-bottom: 15px;
        }

        /* Estilo para el botón de Ingresar */
        div.stButton > button:first-child {
            background-color: #F9D003; /* Oro UNAH */
            color: #003366; 
            font-weight: 700;
            font-size: 16px;
            border: none;
            border-radius: 8px;
            transition: all 0.3s ease;
            margin-top: 10px;
        }
        
        div.stButton > button:first-child:hover {
            background-color: #e5be02; 
            color: #003366;
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(249, 208, 3, 0.4);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def main():
    inicializar_sesion()

    if not st.session_state['logged_in']:
        # Aplicamos los estilos UNAH
        apply_login_styles()
        
        # Centramos el formulario
        st.write("")
        st.write("")
        col1, col2, col3 = st.columns([1, 1.5, 1])
        
        with col2:
            # Tarjeta de Título
            st.markdown(
                """
                <div class="login-container">
                    <h1 class="login-title">Sistema de Soporte a Decisiones</h1>
                    <p class="login-subtitle">Universidad Nacional Autónoma de Honduras</p>
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            # Formulario
            with st.form("login_form"):
                u = st.text_input("✉️ Correo Institucional", placeholder="ejemplo@unah.hn")
                p = st.text_input("🔒 Contraseña", type="password", placeholder="••••••••")
                
                st.write("") # Espaciado
                
                if st.form_submit_button("Ingresar al Sistema", use_container_width=True):
                    # Tu lógica de backend original intocable
                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT * FROM Usuarios WHERE Correo_Institucional = %s AND Contrasena = %s", (u, hash_data(p)))
                    res = cursor.fetchone()
                    if res:
                        st.session_state.update({
                            'logged_in': True, 
                            'user_role': res['Rol'], 
                            'user_name': res['Nombre_Completo'], 
                            'user_hash': res['Hash_Cuenta']
                        })
                        st.rerun()
                    else:
                        st.error("❌ Credenciales incorrectas. Verifique su correo o contraseña.")
                    conn.close()
    else:
        if st.session_state['user_role'] == 'Admin':
            vista_jefe_departamento()
        elif st.session_state['user_role'] == 'Docente':
            vista_docente() 
        else:
            vista_estudiante()

if __name__ == "__main__":
    main()