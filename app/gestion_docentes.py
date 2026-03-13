import streamlit as st
import pandas as pd
from sqlalchemy import text
import datetime

def mostrar_gestion_docentes(engine):
    st.markdown("## 👨‍🏫 Gestión Integral de Personal Docente")
    st.markdown("Administra el padrón de docentes, su disponibilidad, horarios, y las **áreas de conocimiento** a las que pertenecen.")

    # --- DICCIONARIO DE HORAS AMIGABLES (UI/UX) ---
    DICCIONARIO_HORAS = {
        7: "07:00 AM a 08:00 AM", 8: "08:00 AM a 09:00 AM", 9: "09:00 AM a 10:00 AM",
        10: "10:00 AM a 11:00 AM", 11: "11:00 AM a 12:00 PM", 12: "12:00 PM a 01:00 PM",
        13: "01:00 PM a 02:00 PM", 14: "02:00 PM a 03:00 PM", 15: "03:00 PM a 04:00 PM",
        16: "04:00 PM a 05:00 PM", 17: "05:00 PM a 06:00 PM", 18: "06:00 PM a 07:00 PM",
        19: "07:00 PM a 08:00 PM", 20: "08:00 PM a 09:00 PM"
    }

    # 1. Cargar datos cruzados (JOIN) desde MySQL
    try:
        query_docentes = """
            SELECT d.*, IFNULL(GROUP_CONCAT(a.Nombre_Area SEPARATOR ', '), 'Sin área asignada') as Areas
            FROM docentes_activos d
            LEFT JOIN docente_area da ON d.ID_Docente = da.ID_Docente
            LEFT JOIN areas_academicas a ON da.ID_Area = a.ID_Area
            GROUP BY d.ID_Docente
        """
        df_profes = pd.read_sql(query_docentes, engine)
        
        df_areas = pd.read_sql("SELECT ID_Area, Nombre_Area FROM areas_academicas", engine)
        dict_areas = dict(zip(df_areas['Nombre_Area'], df_areas['ID_Area']))
    except Exception as e:
        st.error(f"❌ Error conectando a la base de datos: {e}")
        return
    
    tab_ver, tab_agregar, tab_editar, tab_eliminar = st.tabs([
        "📋 Directorio de Docentes", 
        "➕ Registrar Nuevo", 
        "✏️ Configurar Perfiles", 
        "🗑️ Bajas"
    ])

    # ---------------------------------------------------------
    # PESTAÑA 1: VER LA TABLA
    # ---------------------------------------------------------
    with tab_ver:
        st.markdown("### 📊 Estado Actual del Personal")
        
        activos = len(df_profes[df_profes['Disponible'] == 1])
        inactivos = len(df_profes[df_profes['Disponible'] == 0])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Registrados", len(df_profes))
        with col2:
            st.metric("Docentes Activos 🟢", activos)
        with col3:
            st.metric("Docentes Inactivos 🔴", inactivos)
            
        st.divider()
        
        df_mostrar = df_profes[['ID_Docente', 'Nombre', 'Areas', 'Tipo_Docente', 'Dias_Trabajo', 'Hora_Inicio_Turno', 'Hora_Fin_Turno', 'Horas_Bloqueadas', 'Disponible']].copy()
        df_mostrar['Estado'] = df_mostrar['Disponible'].apply(lambda x: "🟢 Activo" if x == 1 else "🔴 Inactivo")
        
        st.dataframe(df_mostrar.drop(columns=['Disponible']), use_container_width=True, height=400, hide_index=True)

    # ---------------------------------------------------------
    # PESTAÑA 2: AGREGAR DOCENTE
    # ---------------------------------------------------------
    with tab_agregar:
        st.markdown("### ➕ Registrar Nuevo Ingeniero")
        with st.form("form_agregar_docente", border=True):
            st.markdown("#### 👤 Datos Personales y Contractuales")
            col1, col2 = st.columns(2)
            with col1:
                nuevo_nombre = st.text_input("Nombre Completo (Ej. Ing. Juan Pérez)")
                nuevo_tipo = st.selectbox("Tipo de Contrato", ['Base', 'Emergente', 'Tegucigalpa'])
                areas_seleccionadas = st.multiselect("📚 Áreas Académicas", list(dict_areas.keys()), help="Selecciona las áreas de especialidad del docente.")
                
            with col2:
                nueva_h_inicio = st.time_input("Hora Inicio Turno", datetime.time(7, 0))
                nueva_h_fin = st.time_input("Hora Fin Turno", datetime.time(21, 0))
                
                dias_semana = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sa', 'Do']
                dias_seleccionados = st.multiselect("Días de Trabajo", dias_semana, default=['Lu', 'Ma', 'Mi', 'Ju', 'Vi'])
                str_dias = ",".join(dias_seleccionados)
                
            st.divider()
            st.markdown("#### ⚙️ Disponibilidad y Restricciones")
            
            # 🛑 NUEVA UX PARA HORAS BLOQUEADAS
            horas_seleccionadas = st.multiselect(
                "⏳ Bloques de Hora No Disponibles (Horas Bloqueadas)",
                options=list(DICCIONARIO_HORAS.keys()),
                format_func=lambda x: DICCIONARIO_HORAS[x],
                help="Selecciona las horas en las que el docente NO puede impartir clases (ej. reuniones administrativas, hora de almuerzo)."
            )
            # Convierte la lista [12, 13] al string "12,13" para la BD
            str_horas_bloqueadas = ",".join(map(str, horas_seleccionadas))
            
            st.write("") 
            esta_disponible = st.checkbox("🟢 Docente Activo para asignación de clases", value=True)
            
            st.write("")
            submit_agregar = st.form_submit_button("💾 Guardar Nuevo Docente", type="primary", use_container_width=True)

            if submit_agregar:
                if not nuevo_nombre.strip() or not dias_seleccionados or not areas_seleccionadas:
                    st.error("⚠️ Faltan datos obligatorios (Nombre, Días o Áreas).")
                else:
                    disp_int = 1 if esta_disponible else 0
                    insert_query = text("""
                        INSERT INTO docentes_activos 
                        (Nombre, Hora_Inicio_Turno, Hora_Fin_Turno, Horas_Bloqueadas, Tipo_Docente, Disponible, Dias_Trabajo) 
                        VALUES (:nom, :h_ini, :h_fin, :bloq, :tipo, :disp, :dias)
                    """)
                    try:
                        with engine.begin() as conn:
                            result = conn.execute(insert_query, {
                                'nom': nuevo_nombre, 'h_ini': nueva_h_inicio.strftime('%H:%M:%S'),
                                'h_fin': nueva_h_fin.strftime('%H:%M:%S'), 'bloq': str_horas_bloqueadas,
                                'tipo': nuevo_tipo, 'disp': disp_int, 'dias': str_dias
                            })
                            doc_id = result.lastrowid
                            
                            for area in areas_seleccionadas:
                                conn.execute(text("INSERT INTO docente_area (ID_Docente, ID_Area) VALUES (:id_doc, :id_area)"),
                                             {'id_doc': doc_id, 'id_area': dict_areas[area]})
                                             
                        st.success(f"✅ ¡Ing. {nuevo_nombre} registrado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error BD: {e}")

    # ---------------------------------------------------------
    # PESTAÑA 3: EDITAR DOCENTE
    # ---------------------------------------------------------
    with tab_editar:
        st.markdown("### ✏️ Configurar Perfil del Docente")
        
        opciones_editar = {f"{row['ID_Docente']} - {row['Nombre']}": row['ID_Docente'] for idx, row in df_profes.iterrows()}
        seleccion_editar = st.selectbox("🔍 Busque y seleccione un docente:", ["Seleccione..."] + list(opciones_editar.keys()))

        if seleccion_editar != "Seleccione...":
            doc_id = opciones_editar[seleccion_editar]
            doc_data = df_profes[df_profes['ID_Docente'] == doc_id].iloc[0]
            
            areas_actuales = doc_data['Areas'].split(', ') if pd.notna(doc_data['Areas']) and doc_data['Areas'] != 'Sin área asignada' else []

            with st.form("form_editar_docente", border=True):
                st.markdown("#### 👤 Datos Personales y Contractuales")
                col1, col2 = st.columns(2)
                
                with col1:
                    edit_nombre = st.text_input("Nombre", doc_data['Nombre'])
                    tipos = ['Base', 'Emergente', 'Tegucigalpa']
                    idx_tipo = tipos.index(doc_data['Tipo_Docente']) if doc_data['Tipo_Docente'] in tipos else 0
                    edit_tipo = st.selectbox("Tipo de Contrato", tipos, index=idx_tipo)
                    edit_areas = st.multiselect("📚 Áreas Académicas", list(dict_areas.keys()), default=[a for a in areas_actuales if a in dict_areas])

                with col2:
                    h_ini_str = str(doc_data['Hora_Inicio_Turno']).split()[-1] if pd.notnull(doc_data['Hora_Inicio_Turno']) else "07:00:00"
                    h_fin_str = str(doc_data['Hora_Fin_Turno']).split()[-1] if pd.notnull(doc_data['Hora_Fin_Turno']) else "21:00:00"
                    edit_h_inicio = st.time_input("Hora Inicio Turno", datetime.datetime.strptime(h_ini_str, '%H:%M:%S').time())
                    edit_h_fin = st.time_input("Hora Fin Turno", datetime.datetime.strptime(h_fin_str, '%H:%M:%S').time())

                    dias_semana = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sa', 'Do']
                    dias_actuales_lista = str(doc_data.get('Dias_Trabajo', 'Lu,Ma,Mi,Ju,Vi')).split(',')
                    dias_actuales_lista = [d.strip() for d in dias_actuales_lista if d.strip() in dias_semana]
                    if not dias_actuales_lista: dias_actuales_lista = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi']
                    
                    edit_dias = st.multiselect("Días de Trabajo", dias_semana, default=dias_actuales_lista)
                    str_edit_dias = ",".join(edit_dias)

                st.divider()
                st.markdown("#### ⚙️ Disponibilidad y Restricciones")
                
                # 🛑 LÓGICA INVERSA PARA EDITAR (De string BD a lista visual)
                bloq_str = str(doc_data['Horas_Bloqueadas']) if pd.notnull(doc_data['Horas_Bloqueadas']) and doc_data['Horas_Bloqueadas'] != '' else ""
                bloq_actuales_lista = [int(h.strip()) for h in bloq_str.split(',') if h.strip().isdigit() and int(h.strip()) in DICCIONARIO_HORAS]
                
                edit_horas_seleccionadas = st.multiselect(
                    "⏳ Bloques de Hora No Disponibles (Horas Bloqueadas)",
                    options=list(DICCIONARIO_HORAS.keys()),
                    default=bloq_actuales_lista,
                    format_func=lambda x: DICCIONARIO_HORAS[x]
                )
                str_edit_horas_bloqueadas = ",".join(map(str, edit_horas_seleccionadas))
                
                st.write("")
                edit_disp = st.checkbox("🟢 Docente Disponible para asignación", value=bool(doc_data['Disponible']))
                
                st.write("")
                submit_editar = st.form_submit_button("💾 Actualizar Perfil", type="primary", use_container_width=True)

                if submit_editar:
                    if not edit_areas:
                        st.error("⚠️ El docente debe pertenecer a al menos un área.")
                    else:
                        update_query = text("""
                            UPDATE docentes_activos 
                            SET Nombre = :nom, Hora_Inicio_Turno = :h_ini, Hora_Fin_Turno = :h_fin, 
                                Horas_Bloqueadas = :bloq, Tipo_Docente = :tipo, Disponible = :disp, Dias_Trabajo = :dias
                            WHERE ID_Docente = :id
                        """)
                        try:
                            with engine.begin() as conn:
                                conn.execute(update_query, {
                                    'nom': edit_nombre, 'h_ini': edit_h_inicio.strftime('%H:%M:%S'),
                                    'h_fin': edit_h_fin.strftime('%H:%M:%S'), 'bloq': str_edit_horas_bloqueadas,
                                    'tipo': edit_tipo, 'disp': 1 if edit_disp else 0, 'dias': str_edit_dias, 'id': doc_id
                                })
                                conn.execute(text("DELETE FROM docente_area WHERE ID_Docente = :id"), {'id': doc_id})
                                for area in edit_areas:
                                    conn.execute(text("INSERT INTO docente_area (ID_Docente, ID_Area) VALUES (:id_doc, :id_area)"),
                                                 {'id_doc': doc_id, 'id_area': dict_areas[area]})
                            st.success("✅ ¡Perfil actualizado exitosamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al actualizar: {e}")

    # ---------------------------------------------------------
    # PESTAÑA 4: ELIMINAR DOCENTE
    # ---------------------------------------------------------
    with tab_eliminar:
        st.markdown("### 🗑️ Baja de Personal")
        st.warning("⚠️ **ATENCIÓN:** Eliminar a un docente es una acción irreversible. Se recomienda encarecidamente **Desactivarlo** en la pestaña 'Editar' en lugar de borrarlo para mantener el registro de las clases que impartió en el pasado.")
        
        with st.container(border=True):
            seleccion_eliminar = st.selectbox("🔍 Seleccione el docente a ELIMINAR permanentemente:", ["Seleccione..."] + list(opciones_editar.keys()), key="select_del")
            
            if seleccion_eliminar != "Seleccione...":
                doc_id_del = opciones_editar[seleccion_eliminar]
                confirmacion = st.checkbox(f"Estoy absolutamente seguro de que deseo eliminar a {seleccion_eliminar.split('-')[1].strip()} del sistema.")
                
                st.write("")
                if st.button("🚨 Eliminar Docente Definitivamente", type="primary", disabled=not confirmacion, use_container_width=True):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM docente_area WHERE ID_Docente = :id"), {'id': doc_id_del})
                            conn.execute(text("DELETE FROM docentes_activos WHERE ID_Docente = :id"), {'id': doc_id_del})
                        st.success("✅ ¡Docente eliminado del sistema!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ No se pudo eliminar. Probablemente esté asignado a una oferta académica pasada. Error: {e}")