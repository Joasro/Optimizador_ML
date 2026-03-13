import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.student_portal import vista_estudiante

import streamlit as st
import hashlib
import pandas as pd
from config.db_connection import get_connection

st.set_page_config(page_title="Optimizador Académico UNAH", layout="wide", page_icon="🎓")

# ==========================================
# 1. FUNCIONES AUXILIARES
# ==========================================
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

# ==========================================
# 2. SISTEMA DE LOGIN Y SESIÓN
# ==========================================
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
# 3. VISTA: JEFE DE DEPARTAMENTO (ADMIN)
# ==========================================
def vista_jefe_departamento():
    # Importamos el archivo como módulo. (Asegúrate de que no tenga errores de indentación)
    from sqlalchemy import create_engine
    import app.gestion_docentes as gd 
    
    st.sidebar.title(f"👨‍💻 Admin: {st.session_state['user_name']}")
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        cerrar_sesion()

    st.title("🛡️ Panel de Control - Jefe de Departamento")

    # Añadir pestaña de gestión de docentes
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🆕 Registrar Estudiante",
        "📝 Matricular Periodo",
        "✏️ Editar / Corregir Historial",
        "📊 Estadísticas",
        "👨‍🏫 Gestión de Docentes" # Esta es tab5
    ])

 # Inicializar memoria temporal para el historial si no existe
    if 'historial_temporal' not in st.session_state:
        st.session_state['historial_temporal'] = []

    # --- DICCIONARIO DE EQUIVALENCIAS ---
    EQUIVALENCIAS = {
        'ISC-101': ['IS-110', 'MM-314'], 'ISC-102': ['IS-210'], 'ISC-103': ['IS-410'],
        'ISC-211': ['IS-310'], 'ISC-321': ['IS-501'], 'ISC-422': ['IS-601'],
        'ISC-341': ['IS-602'], 'ISC-306': ['IS-702'], 'IE-326': ['IS-311', 'IS-510'],
        'ISC-331': ['IS-511'], 'ISC-332': ['IS-611'], 'ISC-333': ['IS-412'],
        'ISC-334': ['IS-512'], 'ISC-552': ['IS-115'], 'ISC-408': ['IS-802'],
        'ISC-414': ['IS-710'], 'ISC-336': ['IS-711'], 'ISC-437': ['IS-603']
    }

    # --- TAB 1: CREAR ESTUDIANTE ---
    with tab1:
        st.subheader("Paso 1: Datos Básicos del Estudiante")
        
        nombre = st.text_input("Nombre Completo")
        col1, col2 = st.columns(2)
        correo_est = col1.text_input("Correo Institucional")
        pass_est = col2.text_input("Contraseña Temporal", type="password")
        
        ano_ing = st.number_input("Año de Ingreso", 2015, 2030, 2024)
        
        if ano_ing < 2026:
            st.info("💡 Ingreso anterior a 2026: Construiremos su historial visualizando la malla en la que inició.")
            plan_historial = st.radio("Mostrar Malla Base:", ["2021", "2025"], index=0, horizontal=True)
            plan_actual = st.radio("¿A qué plan pertenecerá finalmente (IPAC 2026)?", ["2021", "2025"], index=1, horizontal=True)
        else:
            st.info("💡 Ingreso 2026 o superior: Pertenece 100% al **Plan 2025**.")
            plan_historial = "2025"
            plan_actual = "2025"
            
        st.divider()
        
        st.subheader("Paso 2: Registro Inteligente de Clases")
        st.write("Selecciona el periodo, la clase y si la aprobó o reprobó. El sistema filtrará los prerrequisitos en vivo.")
        
        conn = get_connection()
        malla_df = pd.read_sql(f"SELECT ID_Clase, Codigo_Oficial, Nombre_Clase, Prerrequisitos, Unidades_Valorativas FROM Malla_Curricular WHERE Plan_Perteneciente = '{plan_historial}'", conn)
        conn.close()
        
        if not malla_df.empty:
            aprobadas_actuales = set()
            uv_acumuladas = 0
            
            # Analizar el carrito temporal para ir sumando UV y clases pasadas
            for reg in st.session_state['historial_temporal']:
                if reg['Estado'] == 'Aprobado':
                    aprobadas_actuales.add(reg['Codigo'])
                    uv_val = malla_df.loc[malla_df['Codigo_Oficial'] == reg['Codigo'], 'Unidades_Valorativas']
                    if not uv_val.empty:
                        uv_acumuladas += int(uv_val.values[0])
            
            # Lógica evaluadora
            def cumple_prerrequisitos_ui(prereq_str, aprobadas, uv_actuales):
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
                        if p in aprobadas: continue 
                        equiv_fulfilled = False
                        if p in EQUIVALENCIAS:
                            if all(old_c in aprobadas for old_c in EQUIVALENCIAS[p]):
                                equiv_fulfilled = True
                        if not equiv_fulfilled:
                            return False 
                return True

            # Filtrar solo clases desbloqueadas
            clases_desbloqueadas = []
            for _, row in malla_df.iterrows():
                # No mostrar clases ya aprobadas en la lista de opciones
                if row['Codigo_Oficial'] not in aprobadas_actuales:
                    if cumple_prerrequisitos_ui(row['Prerrequisitos'], aprobadas_actuales, uv_acumuladas):
                        clases_desbloqueadas.append(row.to_dict())
            
            st.markdown(f"**Métricas Actuales:** ✅ Clases Aprobadas: `{len(aprobadas_actuales)}` | 📈 UV Acumuladas: `{uv_acumuladas}`")
            
            if clases_desbloqueadas:
                with st.container(border=True):
                    # Interfaz más limpia y ancha para evitar textos cortados
                    col_per, col_cla, col_est = st.columns([1.5, 3, 1.5])
                    with col_per:
                        periodo_ind = st.text_input("Periodo (Ej: 1-2024)", value=f"1-{ano_ing}")
                    with col_cla:
                        clase_ind = st.selectbox(
                            "Asignatura Desbloqueada",
                            options=[c['ID_Clase'] for c in clases_desbloqueadas],
                            format_func=lambda x: next(f"{c['Codigo_Oficial']} - {c['Nombre_Clase']}" for c in clases_desbloqueadas if c['ID_Clase'] == x)
                        )
                    with col_est:
                        # 🛑 REDUCIDO A SOLO 2 OPCIONES BINARIAS PARA EL ML
                        estado_ind = st.selectbox("Estado final", ["Aprobado", "Reprobado"])
                    
                    if st.button("➕ Agregar al Historial", type="secondary", use_container_width=True):
                        if periodo_ind:
                            nombre_c = next(c['Nombre_Clase'] for c in clases_desbloqueadas if c['ID_Clase'] == clase_ind)
                            codigo_c = next(c['Codigo_Oficial'] for c in clases_desbloqueadas if c['ID_Clase'] == clase_ind)
                            
                            duplicado = any(x['ID_Clase'] == clase_ind and x['Periodo'] == periodo_ind for x in st.session_state['historial_temporal'])
                            if duplicado:
                                st.warning("⚠️ Ya agregaste esta clase en este mismo periodo.")
                            else:
                                st.session_state['historial_temporal'].append({
                                    'ID_Clase': clase_ind,
                                    'Codigo': codigo_c,
                                    'Clase': nombre_c,
                                    'Periodo': periodo_ind,
                                    'Estado': estado_ind
                                })
                                st.rerun() 
                        else:
                            st.warning("⚠️ Debes escribir un Periodo válido.")
            else:
                st.success("🎉 ¡El estudiante ha completado todas las asignaturas mostradas en esta malla!")

        # --- MOSTRAR EL HISTORIAL Y PERMITIR ELIMINAR INDIVIDUALMENTE ---
        if st.session_state['historial_temporal']:
            st.divider()
            st.subheader("📋 Historial a Guardar")
            
            # Usamos columnas para dibujar una tabla interactiva "hecha a mano"
            col_hp, col_hc, col_hn, col_he, col_hx = st.columns([1.5, 1.5, 3, 1.5, 1])
            col_hp.markdown("**Periodo**")
            col_hc.markdown("**Código**")
            col_hn.markdown("**Asignatura**")
            col_he.markdown("**Estado**")
            col_hx.markdown("**Acción**")
            
            # Dibujamos cada clase registrada con su botón de eliminar
            for i, reg in enumerate(st.session_state['historial_temporal']):
                cp, cc, cn, ce, cx = st.columns([1.5, 1.5, 3, 1.5, 1])
                cp.write(reg['Periodo'])
                cc.write(reg['Codigo'])
                cn.write(reg['Clase'])
                
                # Le ponemos color para identificar rápido si la pasó o no
                color = "green" if reg['Estado'] == "Aprobado" else "red"
                ce.markdown(f":{color}[{reg['Estado']}]")
                
                # 🛑 BOTÓN INDIVIDUAL DE ELIMINAR
                if cx.button("❌", key=f"del_{i}", help="Eliminar esta clase"):
                    st.session_state['historial_temporal'].pop(i)
                    st.rerun()
            
            st.write("")
            if st.button("🗑️ Limpiar TODO el historial", type="secondary"):
                st.session_state['historial_temporal'] = []
                st.rerun()

        st.divider()
        
        # --- GUARDAR EN LA BASE DE DATOS ---
        if st.button("💾 Guardar Estudiante e Historial Definitivo", type="primary", use_container_width=True):
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

   # --- TAB 2: GESTIÓN DE HISTORIAL ACADÉMICO ---
    with tab2:
        st.subheader("Paso 3: Matricular Periodo o Actualizar Historial")
        st.write("Selecciona a un estudiante para añadirle nuevas clases a su historial.")
        
        # --- DICCIONARIO DE EQUIVALENCIAS ---
        EQUIVALENCIAS = {
            'ISC-101': ['IS-110', 'MM-314'], 'ISC-102': ['IS-210'], 'ISC-103': ['IS-410'],
            'ISC-211': ['IS-310'], 'ISC-321': ['IS-501'], 'ISC-422': ['IS-601'],
            'ISC-341': ['IS-602'], 'ISC-306': ['IS-702'], 'IE-326': ['IS-311', 'IS-510'],
            'ISC-331': ['IS-511'], 'ISC-332': ['IS-611'], 'ISC-333': ['IS-412'],
            'ISC-334': ['IS-512'], 'ISC-552': ['IS-115'], 'ISC-408': ['IS-802'],
            'ISC-414': ['IS-710'], 'ISC-336': ['IS-711'], 'ISC-437': ['IS-603']
        }

        conn = get_connection()
        estudiantes_df = pd.read_sql("""
            SELECT u.Hash_Cuenta, u.Nombre_Completo, u.Correo_Institucional, e.Plan_Estudio
            FROM Usuarios u
            JOIN Estudiantes e ON u.Hash_Cuenta = e.Hash_Cuenta
        """, conn)
        conn.close()
        
        if estudiantes_df.empty:
            st.info("No hay estudiantes registrados en el sistema.")
        else:
            col1, col2 = st.columns([2, 1])
            with col1:
                estudiante_seleccionado = st.selectbox(
                    "Seleccione un Estudiante",
                    estudiantes_df['Hash_Cuenta'].tolist(),
                    format_func=lambda x: estudiantes_df[estudiantes_df['Hash_Cuenta'] == x]['Nombre_Completo'].values[0]
                )
            
            est_info = estudiantes_df[estudiantes_df['Hash_Cuenta'] == estudiante_seleccionado].iloc[0]
            estudiante_plan = est_info['Plan_Estudio']
            
            with col2:
                st.info(f"🎓 Plan Actual: **{estudiante_plan}**")
            

           # Obtener historial actual de la BD
            conn = get_connection()
            historial_df = pd.read_sql(f"""
                SELECT h.ID_Registro, h.Estado, h.Periodo_Cursado, m.Codigo_Oficial, m.Nombre_Clase, m.Unidades_Valorativas
                FROM Historial_Academico h
                JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
                WHERE h.Hash_Cuenta = '{estudiante_seleccionado}'
            """, conn)
            
            malla_df = pd.read_sql(f"SELECT * FROM Malla_Curricular WHERE Plan_Perteneciente = '{estudiante_plan}'", conn)
            conn.close()
            
            # Calcular métricas base
            aprobadas_set = set(historial_df[historial_df['Estado'] == 'Aprobado']['Codigo_Oficial'].tolist())
            uv_acumuladas = historial_df[historial_df['Estado'] == 'Aprobado']['Unidades_Valorativas'].fillna(0).astype(int).sum()
            
            st.caption(f"📊 **Métricas Actuales del Estudiante:** ✅ Clases Aprobadas: `{len(aprobadas_set)}` | 📈 UV Acumuladas: `{uv_acumuladas}`")
            
            # 🛑 LÓGICA CORE: EVALUADOR DE EQUIVALENCIAS Y PRERREQUISITOS
            def es_clase_aprobada_o_equivalente(codigo_clase, aprobadas):
                # 1. ¿Pasó el código exacto?
                if codigo_clase in aprobadas:
                    return True
                # 2. ¿Es una clase nueva y pasó sus partes viejas (equivalencias)?
                if codigo_clase in EQUIVALENCIAS:
                    if all(old_c in aprobadas for old_c in EQUIVALENCIAS[codigo_clase]):
                        return True
                return False

            def cumple_prerrequisitos(prereq_str, aprobadas, uv_actuales):
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
                        # Comprobar usando la súper función de equivalencias
                        if not es_clase_aprobada_o_equivalente(p, aprobadas):
                            return False
                return True

            # Filtrar malla para obtener SOLO las desbloqueadas
            clases_desbloqueadas = []
            for _, row in malla_df.iterrows():
                codigo_clase = row['Codigo_Oficial']
                # 1. Ocultar la clase si ya la pasó (o si ya pasó sus equivalentes del plan viejo)
                if not es_clase_aprobada_o_equivalente(codigo_clase, aprobadas_set):
                    # 2. Validar que cumpla los prerrequisitos (también lee equivalencias)
                    if cumple_prerrequisitos(row['Prerrequisitos'], aprobadas_set, uv_acumuladas):
                        clases_desbloqueadas.append(row.to_dict())
            
            # --- INTERFAZ PARA MATRICULAR NUEVA CLASE ---
            st.divider()
            st.markdown("### 📝 Añadir Nueva Asignatura al Historial")
            
            if clases_desbloqueadas:
                with st.container(border=True):
                    col_p, col_c, col_e = st.columns([1.5, 3, 1.5])
                    with col_p:
                        nuevo_periodo = st.text_input("Periodo (Ej: 1-2026)")
                    with col_c:
                        nueva_clase_id = st.selectbox(
                            "Asignaturas Desbloqueadas",
                            options=[c['ID_Clase'] for c in clases_desbloqueadas],
                            format_func=lambda x: next(f"{c['Codigo_Oficial']} - {c['Nombre_Clase']}" for c in clases_desbloqueadas if c['ID_Clase'] == x)
                        )
                    with col_e:
                        nuevo_estado = st.selectbox("Estado", ["Aprobado", "Reprobado"])
                    
                    if st.button("➕ Guardar en Historial", type="primary", use_container_width=True):
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
            
            # --- MOSTRAR HISTORIAL ACTUAL Y PERMITIR ELIMINAR ---
            st.divider()
            st.markdown("### 📋 Historial Académico Registrado en BD")
            if not historial_df.empty:
                col_hp, col_hc, col_hn, col_he, col_hx = st.columns([1.5, 1.5, 3, 1.5, 1])
                col_hp.markdown("**Periodo**")
                col_hc.markdown("**Código**")
                col_hn.markdown("**Asignatura**")
                col_he.markdown("**Estado**")
                col_hx.markdown("**Acción**")
                
                for i, row in historial_df.iterrows():
                    cp, cc, cn, ce, cx = st.columns([1.5, 1.5, 3, 1.5, 1])
                    cp.write(row['Periodo_Cursado'])
                    cc.write(row['Codigo_Oficial'])
                    cn.write(row['Nombre_Clase'])
                    color = "green" if row['Estado'] == "Aprobado" else "red"
                    ce.markdown(f":{color}[{row['Estado']}]")
                    
                    # Botón para borrar el registro directo de la Base de Datos
                    if cx.button("❌", key=f"del_bd_{row['ID_Registro']}", help="Eliminar permanentemente de la BD"):
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute(f"DELETE FROM Historial_Academico WHERE ID_Registro = {row['ID_Registro']}")
                        conn.commit()
                        conn.close()
                        st.rerun()
            else:
                st.info("El historial de este estudiante está vacío.")

    # --- TAB 3: EDITAR HISTORIAL ---
    with tab3:
        # ...existing code...
        st.subheader("Edición Rápida de Registros")
        conn = get_connection()
        est_df_edit = pd.read_sql("""
            SELECT u.Hash_Cuenta, u.Nombre_Completo, u.Correo_Institucional, e.Ano_Ingreso, e.Plan_Estudio 
            FROM Usuarios u 
            JOIN Estudiantes e ON u.Hash_Cuenta = e.Hash_Cuenta 
            WHERE u.Rol = 'Estudiante'
        """, conn)
        if not est_df_edit.empty:
            sel_est_edit = st.selectbox("Seleccionar Alumno a Editar", options=est_df_edit['Hash_Cuenta'].tolist(),
                                        format_func=lambda x: est_df_edit[est_df_edit['Hash_Cuenta']==x]['Nombre_Completo'].values[0], key="edit_sel")
            info_edit = est_df_edit[est_df_edit['Hash_Cuenta'] == sel_est_edit].iloc[0]
            correo = info_edit['Correo_Institucional']
            num_cuenta = correo.split('@')[0].replace('estudiante', '') if 'estudiante' in correo else 'No definido'
            st.markdown(f"### 👤 Perfil: {info_edit['Nombre_Completo']}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("📌 Número de Cuenta", num_cuenta)
            c2.metric("🗓️ Año de Ingreso", info_edit['Ano_Ingreso'])
            c3.metric("📚 Plan de Estudio", info_edit['Plan_Estudio'])
            c4.markdown(f"**✉️ Correo:**<br>{correo}", unsafe_allow_html=True)
            st.divider()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT h.ID_Clase, m.Codigo_Oficial, m.Nombre_Clase, h.Periodo_Cursado, h.Estado 
                FROM Historial_Academico h
                JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
                WHERE h.Hash_Cuenta = %s 
            """, (sel_est_edit,))
            hist_edit = cursor.fetchall()
            if not hist_edit:
                st.info("Este estudiante no tiene clases en su historial todavía.")
            else:
                df_hist = pd.DataFrame(hist_edit)
                periodos_unicos = df_hist['Periodo_Cursado'].unique()
                try:
                    periodos_ordenados = sorted(periodos_unicos, key=lambda x: (int(x.split('-')[1]), int(x.split('-')[0])))
                except:
                    periodos_ordenados = periodos_unicos
                st.write("### 📖 Historial por Periodos")
                hubo_cambios = False
                for periodo in periodos_ordenados:
                    st.markdown(f"#### 📅 Periodo: `{periodo}`")
                    df_periodo = df_hist[df_hist['Periodo_Cursado'] == periodo][['ID_Clase', 'Codigo_Oficial', 'Nombre_Clase', 'Estado']]
                    edited_df = st.data_editor(
                        df_periodo,
                        column_config={
                            "ID_Clase": None,
                            "Codigo_Oficial": st.column_config.TextColumn("Código", disabled=True),
                            "Nombre_Clase": st.column_config.TextColumn("Asignatura", disabled=True),
                            "Estado": st.column_config.SelectboxColumn(
                                "Estado",
                                options=["Aprobado", "Reprobado", "🗑️ Eliminar"],
                                required=True
                            )
                        },
                        disabled=["Codigo_Oficial", "Nombre_Clase"],
                        hide_index=True,
                        key=f"editor_{periodo}_{sel_est_edit}",
                        use_container_width=True
                    )
                    for index, row in edited_df.iterrows():
                        orig_row = df_periodo[df_periodo['ID_Clase'] == row['ID_Clase']]
                        if not orig_row.empty:
                            orig_estado = orig_row.iloc[0]['Estado']
                            nuevo_estado = row['Estado']
                            if orig_estado != nuevo_estado:
                                if nuevo_estado == "🗑️ Eliminar":
                                    cursor.execute("DELETE FROM Historial_Academico WHERE Hash_Cuenta = %s AND ID_Clase = %s AND Periodo_Cursado = %s", 
                                                   (sel_est_edit, row['ID_Clase'], periodo))
                                else:
                                    cursor.execute("UPDATE Historial_Academico SET Estado = %s WHERE Hash_Cuenta = %s AND ID_Clase = %s AND Periodo_Cursado = %s", 
                                                   (nuevo_estado, sel_est_edit, row['ID_Clase'], periodo))
                                hubo_cambios = True
                if hubo_cambios:
                    conn.commit()
                    st.toast("✅ Base de datos actualizada.")
                    st.rerun()
        conn.close()

    # --- TAB 4: ESTADÍSTICAS ---
    with tab4:
        st.subheader("📊 Análisis Demográfico y Académico")
        st.markdown("Resumen analítico de la población estudiantil activa en el sistema.")
        
        conn = get_connection()
        try:
            stats_df = pd.read_sql("SELECT Plan_Estudio, COUNT(*) as Total FROM Estudiantes GROUP BY Plan_Estudio", conn)
            
            if stats_df.empty:
                st.info("No hay datos de estudiantes para mostrar.")
            else:
                col_m1, col_m2, col_m3 = st.columns(3)
                total_alumnos = stats_df['Total'].sum()
                
                # Métrica Principal
                col_m1.metric("👥 Población Total Activa", total_alumnos)
                
                # Iteramos sobre los planes para crear métricas dinámicas (Ej. Plan 2021, Plan 2025)
                for i, row in stats_df.iterrows():
                    if i % 2 == 0:
                        col_m2.metric(f"🎓 Estudiantes Plan {row['Plan_Estudio']}", row['Total'])
                    else:
                        col_m3.metric(f"🎓 Estudiantes Plan {row['Plan_Estudio']}", row['Total'])
                
                st.divider()
                
                with st.container(border=True):
                    st.markdown("#### 📈 Distribución Poblacional por Plan de Estudios")
                    # Gráfico de barras nativo y elegante de Streamlit
                    st.bar_chart(stats_df.set_index('Plan_Estudio'), color="#4F8BF9")
                    
        except Exception as e:
            st.error(f"Error al cargar las estadísticas: {e}")
        finally:
            conn.close()
    # --- TAB 5: GESTIÓN DE DOCENTES ---
    with tab5:
        # Aquí creas la conexión a la base de datos que pasaremos a la función
        user = "Joasro"
        password = "Akriila123." 
        host = "localhost"
        db = "dss_academico_unah"
        engine_admin = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}/{db}")
        
        # Invocamos la función del archivo gestion_docentes.py
        gd.mostrar_gestion_docentes(engine_admin)

# ==========================================
# MAIN APP ROUTING
# ==========================================
def main():
    inicializar_sesion()
    
    if not st.session_state['logged_in']:
        st.title("Acceso al Optimizador Académico - UNAH")
        with st.container():
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                with st.form("login_form"):
                    u = st.text_input("Correo Institucional")
                    p = st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Ingresar", use_container_width=True):
                        conn = get_connection()
                        cursor = conn.cursor(dictionary=True)
                        cursor.execute("SELECT * FROM Usuarios WHERE Correo_Institucional = %s AND Contrasena = %s", (u, hash_data(p)))
                        res = cursor.fetchone()
                        if res:
                            st.session_state.update({'logged_in': True, 'user_role': res['Rol'], 'user_name': res['Nombre_Completo'], 'user_hash': res['Hash_Cuenta']})
                            st.rerun()
                        else:
                            st.error("Credenciales incorrectas.")
                        conn.close()
    else:
        if st.session_state['user_role'] == 'Admin':
            vista_jefe_departamento()
        else:
            vista_estudiante()

if __name__ == "__main__":
    main()