import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

    # --- TAB 1: CREAR ESTUDIANTE ---
    with tab1:
        # ...existing code...
        nombre = st.text_input("Nombre Completo")
        col1, col2 = st.columns(2)
        correo_est = col1.text_input("Correo Institucional")
        pass_est = col2.text_input("Contraseña Temporal", type="password")
        ano_ing = st.number_input("Año de Ingreso", 2015, 2030, 2024)
        if ano_ing >= 2024:
            st.info("Ingreso 2024 o superior: Se asigna Plan 2024 automáticamente.")
            plan_final = "2024"
        else:
            plan_final = st.radio("¿Con qué plan inicia su registro?", ["2021", "2024"])
        if st.form("form_nuevo_estudiante").form_submit_button("Guardar Estudiante"):
            if not (nombre and correo_est and pass_est):
                st.error("Faltan datos obligatorios.")
            else:
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO Usuarios (Hash_Cuenta, Nombre_Completo, Correo_Institucional, Contrasena, Rol) VALUES (%s, %s, %s, %s, 'Estudiante')", 
                                   (hash_data(correo_est), nombre, correo_est, hash_data(pass_est)))
                    cursor.execute("INSERT INTO Estudiantes (Hash_Cuenta, Plan_Estudio, Ano_Ingreso) VALUES (%s, %s, %s)", 
                                   (hash_data(correo_est), plan_final, ano_ing))
                    conn.commit()
                    st.success(f"✅ Estudiante {nombre} registrado exitosamente.")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
                finally:
                    conn.close()

    # --- TAB 2: GESTIONAR HISTORIALES Y PRERREQUISITOS ---
    with tab2:
        # ...existing code...
        st.subheader("Agregar Nuevo Periodo")
        conn = get_connection()
        est_df = pd.read_sql("SELECT u.Hash_Cuenta, u.Nombre_Completo, e.Plan_Estudio, e.Ano_Ingreso FROM Usuarios u JOIN Estudiantes e ON u.Hash_Cuenta = e.Hash_Cuenta", conn)
        if est_df.empty:
            st.warning("No hay estudiantes registrados.")
        else:
            sel_est = st.selectbox("Seleccionar Estudiante", options=est_df['Hash_Cuenta'].tolist(),
                                   format_func=lambda x: est_df[est_df['Hash_Cuenta']==x]['Nombre_Completo'].values[0])
            info = est_df[est_df['Hash_Cuenta'] == sel_est].iloc[0]
            col_acc1, col_acc2 = st.columns(2)
            with col_acc1:
                st.info(f"**Plan Actual:** {info['Plan_Estudio']}")
                if info['Plan_Estudio'] == '2021':
                    if st.button("🔄 Migrar estudiante al Plan 2024"):
                        cursor = conn.cursor()
                        cursor.execute("UPDATE Estudiantes SET Plan_Estudio = '2024' WHERE Hash_Cuenta = %s", (sel_est,))
                        conn.commit()
                        st.success("¡Plan actualizado!")
                        st.rerun()
            with col_acc2:
                with st.expander("⚠️ Eliminar Perfil Completo"):
                    if st.checkbox(f"Entiendo, quiero eliminar a {info['Nombre_Completo']}"):
                        if st.button("🗑️ Eliminar Definitivamente", type="primary"):
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM Usuarios WHERE Hash_Cuenta = %s", (sel_est,))
                            conn.commit()
                            st.success("Estudiante eliminado.")
                            st.rerun()
            st.divider()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT h.ID_Clase, h.Estado, m.Unidades_Valorativas, h.Periodo_Cursado, m.Nombre_Clase, m.Codigo_Oficial 
                FROM Historial_Academico h
                JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
                WHERE h.Hash_Cuenta = %s ORDER BY h.Periodo_Cursado
            """, (sel_est,))
            historial = cursor.fetchall()
            clases_aprobadas_ids = {r['ID_Clase'] for r in historial if r['Estado'] == 'Aprobado'}
            total_uv = sum(r['Unidades_Valorativas'] for r in historial if r['Estado'] == 'Aprobado')
            cursor.execute("SELECT ID_Clase, Codigo_Oficial, Nombre_Clase, Prerrequisitos FROM Malla_Curricular WHERE Plan_Perteneciente = %s", (info['Plan_Estudio'],))
            malla = cursor.fetchall()
            mapa_codes = {c['Codigo_Oficial'].strip().upper(): c['ID_Clase'] for c in malla}
            clases_disponibles = [c for c in malla if c['ID_Clase'] not in clases_aprobadas_ids and evaluar_prerrequisitos(c['Prerrequisitos'], clases_aprobadas_ids, total_uv, mapa_codes)]
            ultimo_per = historial[-1]['Periodo_Cursado'] if historial else None
            periodo_reg = st.text_input("Periodo Académico (Ej: 1-2024)", value=sugerir_siguiente_periodo(ultimo_per, info['Ano_Ingreso']))
            clases_sel = st.multiselect(
                "Clases Desbloqueadas (Incluye repitencias):", 
                options=[c['ID_Clase'] for c in clases_disponibles],
                format_func=lambda x: next(f"{c['Codigo_Oficial']} - {c['Nombre_Clase']}" for c in clases_disponibles if c['ID_Clase'] == x)
            )
            if clases_sel:
                st.write("#### Resultados:")
                resultados = {}
                for cid in clases_sel:
                    nom_c = next(c['Nombre_Clase'] for c in clases_disponibles if c['ID_Clase'] == cid)
                    resultados[cid] = st.radio(f"Estado de {nom_c}:", ["Aprobado", "Reprobado"], horizontal=True, key=f"c_{cid}")
                if st.button("Guardar Periodo", type="primary"):
                    for cid in clases_sel:
                        cursor.execute("INSERT INTO Historial_Academico (Hash_Cuenta, ID_Clase, Estado, Periodo_Cursado) VALUES (%s, %s, %s, %s)", 
                                       (sel_est, cid, resultados[cid], periodo_reg))
                    conn.commit()
                    st.success("Guardado.")
                    st.rerun()
        conn.close()

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
        # ...existing code...
        st.subheader("Resumen de Estudiantes por Plan de Estudio")
        conn = get_connection()
        try:
            stats_df = pd.read_sql("SELECT Plan_Estudio, COUNT(*) as Total FROM Estudiantes GROUP BY Plan_Estudio", conn)
            if stats_df.empty:
                st.info("No hay datos de estudiantes para mostrar.")
            else:
                col_m1, col_m2 = st.columns(2)
                for i, row in stats_df.iterrows():
                    with (col_m1 if i % 2 == 0 else col_m2):
                        st.metric(label=f"Plan {row['Plan_Estudio']}", value=f"{row['Total']} Estudiantes")
                st.divider()
                st.write("### Distribución por Plan")
                st.bar_chart(stats_df.set_index('Plan_Estudio'))
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
# 4. VISTA: ESTUDIANTE
# ==========================================
def vista_estudiante():
    st.sidebar.title(f"🎓 Estudiante: {st.session_state['user_name']}")
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        cerrar_sesion()
        
    st.title("Mi Historial Académico")
    
    conn = get_connection()
    df = pd.read_sql(f"""
        SELECT h.Periodo_Cursado, m.Codigo_Oficial, m.Nombre_Clase, m.Unidades_Valorativas, h.Estado 
        FROM Historial_Academico h JOIN Malla_Curricular m ON h.ID_Clase = m.ID_Clase
        WHERE h.Hash_Cuenta = '{st.session_state['user_hash']}' ORDER BY h.Periodo_Cursado ASC
    """, conn)
    conn.close()
    
    if df.empty:
        st.info("Aún no tienes clases registradas.")
    else:
        col_header1, col_header2 = st.columns([3, 1])
        with col_header1:
            uv_totales = df[df['Estado'] == 'Aprobado']['Unidades_Valorativas'].sum()
            st.metric("Total de Unidades Valorativas Aprobadas", int(uv_totales))
        with col_header2:
            csv_completo = df.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Descargar Historial Completo", data=csv_completo, file_name="mi_historial.csv", mime="text/csv", type="primary", use_container_width=True)
            
        st.divider()

        periodos_unicos = df['Periodo_Cursado'].unique()
        try:
            periodos_ordenados = sorted(periodos_unicos, key=lambda x: (int(x.split('-')[1]), int(x.split('-')[0])))
        except:
            periodos_ordenados = periodos_unicos
        
        for periodo in periodos_ordenados:
            st.markdown(f"### 📅 Periodo Académico: `{periodo}`")
            df_periodo = df[df['Periodo_Cursado'] == periodo][['Codigo_Oficial', 'Nombre_Clase', 'Unidades_Valorativas', 'Estado']]
            df_periodo.index = range(1, len(df_periodo) + 1)
            
            def color_estado(val):
                return 'color: green' if val == 'Aprobado' else 'color: red; font-weight: bold'
            
            st.dataframe(df_periodo.style.applymap(color_estado, subset=['Estado']), use_container_width=True)
            st.write("---")

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