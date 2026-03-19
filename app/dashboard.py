import sys
import os
import streamlit.components.v1 as components
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.student_portal import vista_estudiante
from app.teacher_portal import vista_docente
import datetime
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


    # Añadir pestaña de IA y arreglar el orden
   # Añadir pestaña de IA y arreglar el orden
    tab1, tab2, tab_edit, tab_ia, tab4, tab5, tab6, tab_historial_clases = st.tabs([
        "👥 Registrar Estudiante",
        "📚 Matricular Clases",
        "✏️ Editar Historial",
        "📅 Generar Horarios (IA)",
        "📊 Estadísticas",
        "👨‍🏫 Gestión Docente",
        "📡 Censo en Vivo",
        "📜 Historial de Clases" # NUEVA PESTAÑA
    ])

 # Inicializar memoria temporal para el historial si no existe
    if 'historial_temporal' not in st.session_state:
        st.session_state['historial_temporal'] = []

    # --- DICCIONARIO DE EQUIVALENCIAS ---
    EQUIVALENCIAS = {
        'ISC-101': ['IS-110'], 'ISC-102': ['IS-210'], 'ISC-103': ['IS-410'],
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
    with tab_edit:
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

        # --- TAB IA: GENERAR HORARIOS Y MATRIZ CONDENSADA ---
    # --- TAB IA: GENERAR HORARIOS Y MATRIZ CONDENSADA ---
    # --- TAB IA: GENERAR HORARIOS Y MATRIZ CONDENSADA ---
    with tab_ia:
        st.subheader("🧠 Motor de IA: Planificación Condensada")
        st.markdown("Ejecuta el cruce de variables complejas (Censo, Prerrequisitos, Aulas y Disponibilidad Docente) para generar el horario óptimo.")
        
        from sqlalchemy import create_engine, text
        user = "Joasro"
        password = "Akriila123." 
        host = "localhost"
        db = "dss_academico_unah"
        engine_ia = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}/{db}")
                
        if st.button("🚀 Ejecutar Optimizador Logístico", type="primary", use_container_width=True):
            with st.spinner("⏳ 1/2 Analizando expedientes, prerrequisitos y censo de estudiantes..."):
                from src.ml.demand_model import predecir_demanda_estricta
                df_demanda = predecir_demanda_estricta(engine_ia)
                
            if df_demanda.empty:
                st.error("⚠️ No hay suficientes datos de demanda en el censo para generar un horario.")
            else:
                with st.spinner("⚙️ 2/2 Ejecutando Google OR-Tools para optimización física de aulas y docentes..."):
                    from src.optimizer.scheduler import ejecutar_optimizador
                    exito, alertas = ejecutar_optimizador(engine_ia)
                    
                if exito:
                    st.success("✅ ¡Matriz Generada y Guardada en Base de Datos Temporal!")
                    if alertas:
                        for alerta in alertas:
                            st.warning(f"🚨 {alerta}")
                else:
                    st.error(f"❌ Error en el motor: {alertas[0]}")
                    
        st.divider()
        st.markdown("### 📊 Vista Previa: Planificación Condensada ISC")
        
        # Agregamos ID_Seccion, ID_Docente y ID_Espacio para poder editarlos
        query_matriz = """
            SELECT 
                o.ID_Seccion, o.Hora_Inicio, o.Hora_Fin, 
                e.Nombre_Espacio as Aula, e.ID_Espacio,
                m.Codigo_Oficial, m.Nombre_Clase, m.Unidades_Valorativas,
                d.Nombre as Docente, d.ID_Docente, o.Dias, o.Cupos_Maximos,
                d.Acepta_Virtualidad, d.Hora_Inicio_Virtual, d.Hora_Fin_Virtual
            FROM oferta_academica_generada o
            JOIN Malla_Curricular m ON o.ID_Clase = m.ID_Clase
            JOIN espacios_fisicos e ON o.ID_Espacio = e.ID_Espacio
            JOIN docentes_activos d ON o.ID_Docente = d.ID_Docente
        """
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

            # ==========================================
            # LÓGICA DE COLORES DINÁMICOS POR DOCENTE
            # ==========================================
            docentes_unicos = df_oferta['Docente'].unique()
            paleta_colores = ['#4F8BF9', '#28a745', '#dc3545', '#ffc107', '#6f42c1', '#fd7e14', '#17a2b8', '#e83e8c', '#20c997', '#6c757d']
            mapa_colores = {doc: paleta_colores[i % len(paleta_colores)] for i, doc in enumerate(docentes_unicos)}
            df_oferta['Color_Docente'] = df_oferta['Docente'].map(mapa_colores)

            # ==========================================
            # LÓGICA DE MODALIDAD PROFUNDA (Corregida y a prueba de fallos)
            # ==========================================
            def extraer_hora_segura(valor_tiempo):
                """Limpia el formato raro de tiempo de Pandas/MySQL y saca solo la hora en entero"""
                if pd.isna(valor_tiempo): return None
                val_str = str(valor_tiempo).strip()
                if val_str == '00:00:00' or val_str == '0' or val_str == 'None': return None
                if 'days' in val_str:
                    return int(val_str.split('days')[1].split(':')[0].strip())
                return int(val_str.split(':')[0])

            def determinar_modalidad_real(row):
                try:
                    # 1. Sacamos a qué hora se asignó la clase
                    h_clase = extraer_hora_segura(row['Hora_Inicio'])
                    if h_clase is None: return "🏫 Presencial"

                    # 2. Nos aseguramos de que Acepta_Virtualidad sea evaluado como un número entero (1 o 0)
                    acepta_virt = 0
                    if pd.notna(row['Acepta_Virtualidad']):
                        acepta_virt = int(row['Acepta_Virtualidad'])

                    # 3. Si el ingeniero acepta Teledocencia, evaluamos sus horas
                    if acepta_virt == 1:
                        ini_v = extraer_hora_segura(row['Hora_Inicio_Virtual'])
                        fin_v = extraer_hora_segura(row['Hora_Fin_Virtual'])
                        
                        # Verificamos que tenga configuradas horas válidas
                        if ini_v is not None and fin_v is not None:
                            # Si la clase cae dentro de las horas que él configuró para teledocencia:
                            if ini_v <= h_clase < fin_v:
                                return "📡 Teledocencia"
                                
                    # Si no se cumple lo de teledocencia, es su turno físico
                    return "🏫 Presencial"
                except Exception as e:
                    # Si algo rarísimo pasa con los datos, lo mandamos a presencial
                    return "🏫 Presencial" 

            # Ejecutamos la función sobre todo el Dataframe fila por fila
            df_oferta['Modalidad_Texto'] = df_oferta.apply(determinar_modalidad_real, axis=1)

            # ==========================================
            # Celda HTML Modificada (Diseño exacto solicitado)
            # ==========================================
            df_oferta['Info_Celda'] = (
                "<div style='padding:8px; border-radius:5px; background-color:#f8f9fa; border-left:8px solid " + df_oferta['Color_Docente'] + "; margin-bottom:4px; font-size:12px; color:#333;'>"
                "<b style='color:#004085;'>" + df_oferta['Codigo_Oficial'] + "</b> - " + df_oferta['Nombre_Clase'] + "<br>"
                "👨‍🏫 <i>" + df_oferta['Docente'] + "</i><br>"
                "⚡ " + df_oferta['Unidades_Valorativas'].astype(str) + " UV | 📅 <b>" + df_oferta['Dias'] + "</b><br>"
                "<span style='color:#28a745; font-weight:bold;'>👥 Cupos: " + df_oferta['Cupos_Maximos'].astype(str) + "</span><br>"
                "<span style='font-weight:bold; color:#495057;'>" + df_oferta['Modalidad_Texto'] + "</span>"
                "</div>"
            )

            # ==========================================
            # 3. Pivot Table Inmune a Crasheos
            # ==========================================
            matriz = df_oferta.pivot_table(
                index='Hora_Rango', 
                columns='Aula', 
                values='Info_Celda', 
                aggfunc=lambda x: "".join(x)
            ).fillna("")
            
            matriz = matriz.sort_index()
            matriz.index.name = "⌚ Hora / Aula 🏫"
            matriz.columns.name = ""
            
            # ==========================================
            # 4. Renderizado a Prueba de Streamlit
            # ==========================================
            html_raw = matriz.to_html(escape=False)
            
            # 🛑 LA MAGIA: Borramos todos los saltos de línea (\n)
            html_limpio = html_raw.replace("\n", "")
            
            css_tabla = """
            <style>
                table.dataframe { width: 100%; border-collapse: collapse; font-family: sans-serif; background-color: white; margin-top: 15px; }
                table.dataframe thead th { background-color: #004085 !important; color: white !important; padding: 12px; text-align: center; border: 1px solid #dee2e6; }
                table.dataframe tbody th { background-color: #e9ecef !important; color: #333 !important; font-weight: bold; text-align: center; border: 1px solid #dee2e6; padding: 10px; width: 130px; }
                table.dataframe tbody td { border: 1px solid #dee2e6; padding: 8px; vertical-align: top; }
            </style>
            """.replace("\n", "")
            
            # Imprimimos en pantalla de forma 100% segura
            st.markdown(css_tabla + html_limpio, unsafe_allow_html=True)
            
            st.divider()
            
            # ==========================================
            # 🛑 EDITOR MANUAL DE CARGA
            # ==========================================
            st.markdown("### 🛠️ Editor Manual de Carga Académica")
            st.write("¿La IA cometió un error o quieres hacer un ajuste fino? Selecciona una sección para modificarla o borrarla.")
            
            opciones_sec = {f"{row['Codigo_Oficial']} - {row['Nombre_Clase']} ({row['Hora_Inicio_Limpia']} en {row['Aula']})": row['ID_Seccion'] for _, row in df_oferta.iterrows()}
            sec_seleccionada = st.selectbox("🔍 Buscar Sección:", ["Seleccione..."] + list(opciones_sec.keys()))
            
            if sec_seleccionada != "Seleccione...":
                id_sec_edit = opciones_sec[sec_seleccionada]
                sec_actual = df_oferta[df_oferta['ID_Seccion'] == id_sec_edit].iloc[0]
                
                df_docs = pd.read_sql("SELECT ID_Docente, Nombre FROM docentes_activos", engine_ia)
                dict_docs = dict(zip(df_docs['Nombre'], df_docs['ID_Docente']))
                
                df_esp = pd.read_sql("SELECT ID_Espacio, Nombre_Espacio FROM espacios_fisicos", engine_ia)
                dict_esp = dict(zip(df_esp['Nombre_Espacio'], df_esp['ID_Espacio']))
                
                with st.container(border=True):
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        idx_doc = list(dict_docs.values()).index(sec_actual['ID_Docente']) if sec_actual['ID_Docente'] in dict_docs.values() else 0
                        nuevo_doc = st.selectbox("👨‍🏫 Reasignar Docente", list(dict_docs.keys()), index=idx_doc)
                        
                        idx_esp = list(dict_esp.values()).index(sec_actual['ID_Espacio']) if sec_actual['ID_Espacio'] in dict_esp.values() else 0
                        nueva_aula = st.selectbox("🏫 Reasignar Aula", list(dict_esp.keys()), index=idx_esp)
                        
                    with col_e2:
                        st.write(" ")
                        st.write(" ")
                        if st.button("💾 Guardar Cambios", use_container_width=True):
                            with engine_ia.begin() as con:
                                con.execute(text("UPDATE oferta_academica_generada SET ID_Docente = :d, ID_Espacio = :e WHERE ID_Seccion = :s"), 
                                            {"d": dict_docs[nuevo_doc], "e": dict_esp[nueva_aula], "s": id_sec_edit})
                            st.success("¡Sección modificada!")
                            st.rerun()
                            
                        if st.button("🗑️ Eliminar Sección", type="primary", use_container_width=True):
                            with engine_ia.begin() as con:
                                con.execute(text("DELETE FROM oferta_academica_generada WHERE ID_Seccion = :s"), {"s": id_sec_edit})
                            st.warning("Sección eliminada de la oferta.")
                            st.rerun()
                            
            st.divider()
            
            # ==========================================
            # BOTÓN DE APROBACIÓN FINAL
            # ==========================================
            st.markdown("#### ¿Satisfecho con la propuesta del sistema?")
            col_a, col_b, col_c = st.columns([1,2,1])
            with col_b:
                if st.button("✅ APROBAR Y PUBLICAR OFERTA PARA ESTUDIANTES", type="primary", use_container_width=True):
                    with engine_ia.begin() as con:
                        con.execute(text("UPDATE oferta_academica_generada SET Aprobado_Por_Jefatura = 1"))
                    st.success("🎉 ¡Oferta Académica Publicada Oficialmente! Los estudiantes ya pueden matricularse en el portal.")
                    st.balloons()
        else:
            st.info("No hay una oferta académica generada actualmente. Ejecuta el optimizador arriba.")
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

    # --- TAB 6: MONITOR DEL CENSO EN VIVO ---
    with tab6:
        st.subheader("📡 Monitor del Censo de Matrícula (Tiempo Real)")
        st.write("Analiza las intenciones de matrícula de los estudiantes agrupadas por asignatura. Se resalta automáticamente a los estudiantes por egresar.")
        
        conn = get_connection()
        try:
            # 1. Traer datos del censo cruzados con la información del estudiante
            query_censo = """
                SELECT c.Jornada_Preferencia, m.Codigo_Oficial, m.Nombre_Clase, u.Nombre_Completo, c.Hash_Cuenta, e.Plan_Estudio
                FROM censo_periodo_actual c
                JOIN Malla_Curricular m ON c.ID_Clase = m.ID_Clase
                JOIN Usuarios u ON c.Hash_Cuenta = u.Hash_Cuenta
                JOIN Estudiantes e ON c.Hash_Cuenta = e.Hash_Cuenta
            """
            censo_df = pd.read_sql(query_censo, conn)

            if censo_df.empty:
                st.info("Aún no hay respuestas registradas en el censo para este periodo.")
            else:
                # 2. Traer el historial de todos los estudiantes para calcular si son Egresandos
                historial_df = pd.read_sql("""
                    SELECT h.Hash_Cuenta, m.Codigo_Oficial
                    FROM Historial_Academico h
                    JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
                    WHERE h.Estado = 'Aprobado'
                """, conn)
                
                malla_df = pd.read_sql("SELECT Codigo_Oficial, Plan_Perteneciente FROM Malla_Curricular", conn)
                
                # Diccionario temporal para guardar quién es egresando y optimizar la velocidad
                dict_egresando = {}
                OPTATIVAS_2021 = ['IS-910', 'IS-911', 'IS-914', 'IS-912', 'IS-913']
                
                for hash_c in censo_df['Hash_Cuenta'].unique():
                    plan_est = censo_df[censo_df['Hash_Cuenta'] == hash_c].iloc[0]['Plan_Estudio']
                    aprobadas_set = set(historial_df[historial_df['Hash_Cuenta'] == hash_c]['Codigo_Oficial'].tolist())
                    
                    malla_carrera = malla_df[(malla_df['Plan_Perteneciente'] == plan_est) & (malla_df['Codigo_Oficial'].str.startswith(('IS', 'ISC', 'IE')))]
                    
                    if plan_est == '2021':
                        malla_core = malla_carrera[~malla_carrera['Codigo_Oficial'].isin(OPTATIVAS_2021)]
                        aprobadas_core = len([c for c in aprobadas_set if c in malla_core['Codigo_Oficial'].values])
                        core_faltantes = len(malla_core) - aprobadas_core
                        aprobadas_optativas = len([c for c in aprobadas_set if c in OPTATIVAS_2021])
                        optativas_faltantes = max(0, 3 - aprobadas_optativas)
                        total_faltantes = core_faltantes + optativas_faltantes
                    else:
                        aprobadas_carrera = len([c for c in aprobadas_set if c in malla_carrera['Codigo_Oficial'].values])
                        total_faltantes = len(malla_carrera) - aprobadas_carrera
                        
                    dict_egresando[hash_c] = total_faltantes <= 8

                # 3. Aplicamos la etiqueta de Egresando al Dataframe del Censo
                censo_df['Es_Egresando'] = censo_df['Hash_Cuenta'].map(dict_egresando)

                # 4. Agrupamos por Asignatura para ver cuáles son las más demandadas
                resumen_clases = censo_df.groupby(['Codigo_Oficial', 'Nombre_Clase']).size().reset_index(name='Total_Solicitudes')
                resumen_clases = resumen_clases.sort_values(by='Total_Solicitudes', ascending=False)
                
                # --- UI: DICCIONARIO DE HORAS ---
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
                st.markdown("### 🏆 Top Asignaturas Solicitadas")
                st.caption("Despliega cada asignatura para ver el detalle de los estudiantes y la hora exacta que necesitan.")
                
                # 5. Generar un bloque desplegable (Expander) por cada clase
                for _, row in resumen_clases.iterrows():
                    cod = row['Codigo_Oficial']
                    nom = row['Nombre_Clase']
                    total = row['Total_Solicitudes']
                    
                    estudiantes_clase = censo_df[censo_df['Codigo_Oficial'] == cod]
                    num_egresandos = estudiantes_clase['Es_Egresando'].sum()
                    
                    # Alerta visual si hay alumnos por egresar pidiendo esta clase
                    alerta_egresando = f" | 🚨 {num_egresandos} por egresar" if num_egresandos > 0 else ""
                    
                    with st.expander(f"📚 {cod} - {nom} | 👥 {total} solicitudes {alerta_egresando}"):
                        
                        detail_df = estudiantes_clase[['Nombre_Completo', 'Jornada_Preferencia', 'Es_Egresando']].copy()
                        
                        # Formato amigable de horas y estado
                        detail_df['Hora Solicitada'] = detail_df['Jornada_Preferencia'].apply(lambda x: HORAS_CENSO.get(x, x))
                        detail_df['Estado'] = detail_df['Es_Egresando'].apply(lambda x: "Por Egresar" if x else "Regular")
                        
                        # Ordenamos para que los de "Por Egresar" salgan de primeros en la tabla
                        detail_df = detail_df.sort_values(by='Es_Egresando', ascending=False)
                        
                        detail_df = detail_df[['Nombre_Completo', 'Hora Solicitada', 'Estado']]
                        detail_df.rename(columns={'Nombre_Completo': 'Estudiante'}, inplace=True)
                        
                   
                        # Pintar de amarillo con texto oscuro para garantizar lectura en modo claro/oscuro
                        def color_egresando(row):
                            if row['Estado'] == 'Por Egresar':
                                # Usamos amarillo suave de fondo y gris/negro muy oscuro para las letras
                                return ['background-color: #FFF3CD; color: #212529; font-weight: bold' for _ in row]
                            else:
                                return ['' for _ in row]
                        
                        st.dataframe(
                            detail_df.style.apply(color_egresando, axis=1), 
                            use_container_width=True, 
                            hide_index=True
                        )
        except Exception as e:
            st.error(f"Error al cargar los datos del censo: {e}")
        finally:
            conn.close()   

    # --- TAB 7: HISTORIAL HISTÓRICO DE CLASES ---
    with tab_historial_clases:
        st.subheader("📜 Carga de Historial de Clases (Últimos Periodos)")
        st.write("Registra cómo se impartieron las asignaturas en periodos anteriores para que la Inteligencia Artificial aprenda las preferencias de horarios, docentes y aulas.")

        conn = get_connection()
        try:
            # Traer catálogos para los selectbox
            df_clases = pd.read_sql("SELECT ID_Clase, Codigo_Oficial, Nombre_Clase FROM Malla_Curricular WHERE Codigo_Oficial LIKE 'IS%' OR Codigo_Oficial LIKE 'ISC%' OR Codigo_Oficial LIKE 'IE%'", conn)
            df_docentes = pd.read_sql("SELECT ID_Docente, Nombre FROM docentes_activos", conn)
            df_espacios = pd.read_sql("SELECT ID_Espacio, Nombre_Espacio FROM espacios_fisicos", conn)

            with st.container(border=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    per_hist_input = st.text_input("Periodo Académico", placeholder="Ej: 3-2024")
                    
                    # Selectbox de clases con formato amigable
                    opciones_clases = df_clases['ID_Clase'].tolist()
                    formato_clase = lambda x: f"{df_clases[df_clases['ID_Clase'] == x]['Codigo_Oficial'].values[0]} - {df_clases[df_clases['ID_Clase'] == x]['Nombre_Clase'].values[0]}"
                    clase_hist_sel = st.selectbox("Asignatura", options=opciones_clases, format_func=formato_clase)
                    
                    # Selectbox de docentes
                    opciones_docentes = [None] + df_docentes['ID_Docente'].tolist()
                    formato_docente = lambda x: "Sin asignar / No aplica" if x is None else df_docentes[df_docentes['ID_Docente'] == x]['Nombre'].values[0]
                    docente_hist_sel = st.selectbox("Docente que la impartió", options=opciones_docentes, format_func=formato_docente)

                with col2:
                    # Selectbox de espacios/aulas
                    opciones_espacios = [None] + df_espacios['ID_Espacio'].tolist()
                    formato_espacio = lambda x: "Sin asignar / Virtual" if x is None else df_espacios[df_espacios['ID_Espacio'] == x]['Nombre_Espacio'].values[0]
                    espacio_hist_sel = st.selectbox("Aula donde se impartió", options=opciones_espacios, format_func=formato_espacio)
                    
                    st.write("Horario Impartido:")
                    c_h1, c_h2 = st.columns(2)

                    
                    # Forzamos saltos de 1 hora (step=3600 segundos) y ponemos 07:00 por defecto
                    hora_in_hist = c_h1.time_input("Hora de Inicio", 
                                                   value=datetime.time(7, 0), 
                                                   step=datetime.timedelta(hours=1))
                                                   
                    hora_out_hist = c_h2.time_input("Hora de Fin", 
                                                    value=datetime.time(8, 0), 
                                                    step=datetime.timedelta(hours=1))
                if st.button("💾 Guardar Registro Histórico", type="primary", use_container_width=True):
                    if per_hist_input and hora_in_hist and hora_out_hist:
                        cursor = conn.cursor()
                        # Query actualizada sin el campo "Dias"
                        cursor.execute("""
                            INSERT INTO historial_oferta_academica 
                            (Periodo_Academico, ID_Clase, ID_Docente, ID_Espacio, Hora_Inicio, Hora_Fin) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (per_hist_input, clase_hist_sel, docente_hist_sel, espacio_hist_sel, hora_in_hist.strftime('%H:%M:%S'), hora_out_hist.strftime('%H:%M:%S')))
                        conn.commit()
                        st.success("✅ ¡Registro histórico guardado! La IA ahora tiene un patrón más para analizar.")
                        st.rerun()
                    else:
                        st.warning("⚠️ Debes ingresar al menos el Periodo y las Horas de Inicio y Fin.")

            st.divider()
            st.markdown("### 📋 Registros Actuales en la Base de Conocimiento")
            
            # Query actualizada para no llamar al campo "Dias"
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
                st.dataframe(df_historial_conocimiento, use_container_width=True, hide_index=True)
            else:
                st.info("La tabla de conocimiento histórico está vacía. ¡Agrega el primer registro arriba!")
            # Mostrar tabla con los datos actuales
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
                st.dataframe(df_historial_conocimiento, use_container_width=True, hide_index=True)
                
                # ==========================================
                # 🛑 EDITOR INDIVIDUAL DE HISTORIAL
                # ==========================================
                st.divider()
                st.markdown("### ✏️ Editar o Eliminar Registro")
                
                # Crear diccionario visual para el buscador
                dic_registros = {f"[{row['Periodo_Academico']}] {row['Codigo_Oficial']} - {row['Hora_Inicio']} en {row['Aula']}": row['ID_Historial'] for _, row in df_historial_conocimiento.iterrows()}
                sel_registro = st.selectbox("🔍 Buscar registro histórico para modificar:", ["Seleccione..."] + list(dic_registros.keys()))
                
                if sel_registro != "Seleccione...":
                    id_edit = dic_registros[sel_registro]
                    # Obtener los datos crudos del registro seleccionado
                    df_actual = pd.read_sql(f"SELECT * FROM historial_oferta_academica WHERE ID_Historial = {id_edit}", conn)
                    datos_actuales = df_actual.iloc[0]
                    
                    with st.container(border=True):
                        st.write(f"**Modificando ID:** {id_edit}")
                        col_e1, col_e2 = st.columns(2)
                        
                        with col_e1:
                            edit_per = st.text_input("📝 Editar Periodo", value=datos_actuales['Periodo_Academico'])
                            
                            # Mantener el docente actual seleccionado
                            id_docente_actual = datos_actuales['ID_Docente']
                            idx_doc = opciones_docentes.index(id_docente_actual) if id_docente_actual in opciones_docentes else 0
                            edit_docente = st.selectbox("👨‍🏫 Cambiar Docente", options=opciones_docentes, format_func=formato_docente, index=idx_doc, key="ed_doc")
                            
                        with col_e2:
                            # Mantener el aula actual seleccionada
                            id_espacio_actual = datos_actuales['ID_Espacio']
                            idx_esp = opciones_espacios.index(id_espacio_actual) if id_espacio_actual in opciones_espacios else 0
                            edit_espacio = st.selectbox("🏫 Cambiar Aula", options=opciones_espacios, format_func=formato_espacio, index=idx_esp, key="ed_esp")
                            
                            st.write(" ")
                            st.write(" ")
                            c_btn1, c_btn2 = st.columns(2)
                            
                            # Botón para Actualizar
                            if c_btn1.button("💾 Actualizar", use_container_width=True):
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE historial_oferta_academica 
                                    SET Periodo_Academico = %s, ID_Docente = %s, ID_Espacio = %s
                                    WHERE ID_Historial = %s
                                """, (edit_per, edit_docente, edit_espacio, id_edit))
                                conn.commit()
                                st.success("✅ ¡Registro actualizado correctamente!")
                                st.rerun()
                                
                            # Botón para Eliminar
                            if c_btn2.button("🗑️ Borrar", type="primary", use_container_width=True):
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM historial_oferta_academica WHERE ID_Historial = %s", (id_edit,))
                                conn.commit()
                                st.warning("🚨 ¡Registro eliminado del historial!")
                                st.rerun()

            else:
                st.info("La tabla de conocimiento histórico está vacía. ¡Agrega el primer registro arriba!")

        except Exception as e:
            st.error(f"Error al cargar la interfaz de historial: {e}")
        finally:
            conn.close()
        

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
        elif st.session_state['user_role'] == 'Docente':
            vista_docente() # <--- LA NUEVA RUTA
        else:
            vista_estudiante()

if __name__ == "__main__":
    main()