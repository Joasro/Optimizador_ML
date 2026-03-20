import streamlit as st
import pandas as pd
from sqlalchemy import text
import datetime

# --- Función para limpiar el formato de hora ---
def clean_time_str(time_val):
    if pd.isna(time_val) or time_val == '' or str(time_val).strip() == '00:00:00': return "N/A"
    t_str = str(time_val).strip()
    if 'days' in t_str: t_str = t_str.split('days')[1].strip()
    try:
        parts = t_str.split(':')
        h = int(parts[0])
        m = int(parts[1])
        ampm = "AM" if h < 12 else "PM"
        h_12 = h if h <= 12 else h - 12
        if h_12 == 0: h_12 = 12
        return f"{h_12:02d}:{m:02d} {ampm}"
    except:
        return t_str[:5]

def mostrar_gestion_docentes(engine):
    st.markdown("## 👨‍🏫 Gestión Integral de Personal Docente")
    st.markdown("<p style='font-size: 1.1rem; color: gray;'>Administra el padrón de ingenieros, su disponibilidad de turnos, modalidades y áreas de conocimiento.</p>", unsafe_allow_html=True)
    st.write("")

    DICCIONARIO_HORAS = {
        7: "07:00 AM a 08:00 AM", 8: "08:00 AM a 09:00 AM", 9: "09:00 AM a 10:00 AM",
        10: "10:00 AM a 11:00 AM", 11: "11:00 AM a 12:00 PM", 12: "12:00 PM a 01:00 PM",
        13: "01:00 PM a 02:00 PM", 14: "02:00 PM a 03:00 PM", 15: "03:00 PM a 04:00 PM",
        16: "04:00 PM a 05:00 PM", 17: "05:00 PM a 06:00 PM", 18: "06:00 PM a 07:00 PM",
        19: "07:00 PM a 08:00 PM", 20: "08:00 PM a 09:00 PM"
    }

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
        "🗑️ Zona de Bajas"
    ])

    # =========================================================
    # PESTAÑA 1: DIRECTORIO (TABLA ULTRA ESTILIZADA)
    # =========================================================
    with tab_ver:
        activos = len(df_profes[df_profes['Disponible'] == 1])
        inactivos = len(df_profes[df_profes['Disponible'] == 0])
        
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            col1.metric("👥 Total Registrados", len(df_profes))
            col2.metric("🟢 Docentes Activos", activos)
            col3.metric("🔴 Docentes Inactivos", inactivos)
            
        st.write("")
        st.markdown("### 📊 Padrón Oficial de Personal")
        
        df_mostrar = df_profes.copy()
        
        # 1. Formatear visualmente el texto base
        df_mostrar['Estado'] = df_mostrar['Disponible'].apply(lambda x: "🟢 Activo" if x == 1 else "🔴 Inactivo")
        df_mostrar['Virtual'] = df_mostrar.get('Acepta_Virtualidad', 0).apply(lambda x: "💻 Sí" if x == 1 else "❌ No")
        
        # 2. Limpiar horas y fusionarlas en una sola columna elegante
        df_mostrar['Hora_Inicio_Turno'] = df_mostrar['Hora_Inicio_Turno'].apply(clean_time_str)
        df_mostrar['Hora_Fin_Turno'] = df_mostrar['Hora_Fin_Turno'].apply(clean_time_str)
        df_mostrar['Turno'] = df_mostrar.apply(
            lambda r: f"{r['Hora_Inicio_Turno']} - {r['Hora_Fin_Turno']}" if r['Hora_Inicio_Turno'] != "N/A" else "Solo Virtual / No aplica", axis=1
        )
        
        # 3. 🌟 LA MAGIA: Convertir strings a listas para renderizar "Chips/Etiquetas" redondeadas
        df_mostrar['Areas_List'] = df_mostrar['Areas'].apply(lambda x: [a.strip() for a in str(x).split(',')] if str(x) != 'Sin área asignada' else ['Ninguna'])
        df_mostrar['Dias_List'] = df_mostrar['Dias_Trabajo'].apply(lambda x: [d.strip() for d in str(x).split(',') if d.strip()])
        
        columnas_ver = ['Nombre', 'Areas_List', 'Tipo_Docente', 'Dias_List', 'Turno', 'Virtual', 'Estado']
        
        # 4. Colorización de celdas con Pandas Styler
        def highlight_estado(val):
            if val == "🟢 Activo": return 'background-color: #d4edda; color: #155724; font-weight: bold;'
            if val == "🔴 Inactivo": return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
            return ''

        styled_df = df_mostrar[columnas_ver].style.map(highlight_estado, subset=['Estado'])
        
        # 5. Renderizado Final Inteligente
        st.dataframe(
            styled_df, 
            use_container_width=True, 
            height=450, 
            hide_index=True,
            column_config={
                "Nombre": st.column_config.TextColumn("👨‍🏫 Ingeniero(a)", width="medium"),
                "Areas_List": st.column_config.ListColumn("📚 Áreas Asignadas", width="large", help="Especialidades del docente"),
                "Tipo_Docente": st.column_config.TextColumn("📝 Contrato", width="small"),
                "Dias_List": st.column_config.ListColumn("📅 Días", width="small"),
                "Turno": st.column_config.TextColumn("⏰ Turno Presencial", width="medium"),
                "Virtual": st.column_config.TextColumn("🌐 Virtual", width="small"),
                "Estado": st.column_config.TextColumn("Status", width="small")
            }
        )

    # =========================================================
    # PESTAÑA 2: AGREGAR DOCENTE (FORMULARIO MODERNO)
    # =========================================================
    with tab_agregar:
        st.markdown("### ➕ Registrar Nuevo Ingeniero")
        st.write("Llena el formulario para dar de alta a un nuevo docente en el padrón del departamento.")
        
        with st.container(border=True):
            st.markdown("#### 1. Datos Personales y Contractuales")
            col1, col2 = st.columns(2)
            with col1:
                nuevo_nombre = st.text_input("Nombre Completo (Ej. Ing. Juan Pérez)", key="add_nombre")
                nuevo_tipo = st.selectbox("Tipo de Contrato", ['Base', 'Emergente', 'Tegucigalpa'], key="add_tipo")
            with col2:
                dias_semana = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sa', 'Do']
                dias_seleccionados = st.multiselect("Días de Trabajo en la Semana", dias_semana, default=['Lu', 'Ma', 'Mi', 'Ju', 'Vi'], key="add_dias")
                areas_seleccionadas = st.multiselect("📚 Áreas Académicas a las que pertenece", list(dict_areas.keys()), key="add_areas")
                
            str_dias = ",".join(dias_seleccionados)
            
        with st.container(border=True):
            st.markdown("#### 2. Modalidad y Horarios de Trabajo")
            
            imparte_presencial = st.checkbox("🏫 El docente imparte clases PRESENCIALES", value=True, key="add_chk_pres")
            if imparte_presencial:
                st.info("Configura el turno en el que el docente debe estar físicamente en la universidad.")
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    nueva_h_inicio = st.time_input("Hora Inicio Turno (Presencial)", datetime.time(7, 0), key="add_h_ini_p", step=datetime.timedelta(hours=1))
                with col_p2:
                    nueva_h_fin = st.time_input("Hora Fin Turno (Presencial)", datetime.time(13, 0), key="add_h_fin_p", step=datetime.timedelta(hours=1))
            
            st.write("")
            imparte_virtual = st.checkbox("🌐 El docente imparte clases VIRTUALES (Teledocencia)", value=False, key="add_chk_virt")
            if imparte_virtual:
                st.warning("Configura el bloque de horas en el que el docente está habilitado para dar clases por internet.")
                col_v1, col_v2 = st.columns(2)
                with col_v1:
                    h_inicio_v = st.time_input("Hora Inicio (Virtual)", datetime.time(17, 0), key="add_h_ini_v", step=datetime.timedelta(hours=1))
                with col_v2:
                    h_fin_v = st.time_input("Hora Fin (Virtual)", datetime.time(21, 0), key="add_h_fin_v", step=datetime.timedelta(hours=1))

        with st.container(border=True):
            st.markdown("#### 3. Restricciones Logísticas")
            horas_seleccionadas = st.multiselect(
                "⏳ Bloques de Hora No Disponibles (Horas Bloqueadas)",
                options=list(DICCIONARIO_HORAS.keys()),
                format_func=lambda x: DICCIONARIO_HORAS[x],
                help="La Inteligencia Artificial JAMÁS le asignará una clase en estas horas, sin importar su turno.",
                key="add_bloqueadas"
            )
            str_horas_bloqueadas = ",".join(map(str, horas_seleccionadas))
            
            st.write("") 
            esta_disponible = st.checkbox("🟢 Activar inmediatamente a este docente para la asignación de horarios", value=True, key="add_chk_disp")
            
        st.write("")
        if st.button("💾 Guardar y Registrar Docente", type="primary", use_container_width=True, key="btn_add_docente"):
            if not nuevo_nombre.strip() or not dias_seleccionados or not areas_seleccionadas:
                st.error("⚠️ Faltan datos obligatorios (Nombre, Días o Áreas).")
            elif not imparte_presencial and not imparte_virtual:
                st.error("🚨 El docente debe impartir al menos una modalidad (Presencial o Virtual).")
            else:
                disp_int = 1 if esta_disponible else 0
                h_ini_str = nueva_h_inicio.strftime('%H:%M:%S') if imparte_presencial else "00:00:00"
                h_fin_str = nueva_h_fin.strftime('%H:%M:%S') if imparte_presencial else "00:00:00"
                acc_virt_int = 1 if imparte_virtual else 0
                h_ini_v_str = h_inicio_v.strftime('%H:%M:%S') if imparte_virtual else None
                h_fin_v_str = h_fin_v.strftime('%H:%M:%S') if imparte_virtual else None
                
                insert_query = text("""
                    INSERT INTO docentes_activos 
                    (Nombre, Hora_Inicio_Turno, Hora_Fin_Turno, Horas_Bloqueadas, Tipo_Docente, Disponible, Dias_Trabajo, Acepta_Virtualidad, Hora_Inicio_Virtual, Hora_Fin_Virtual) 
                    VALUES (:nom, :h_ini, :h_fin, :bloq, :tipo, :disp, :dias, :acc_v, :h_ini_v, :h_fin_v)
                """)
                try:
                    with engine.begin() as conn:
                        result = conn.execute(insert_query, {
                            'nom': nuevo_nombre, 'h_ini': h_ini_str, 'h_fin': h_fin_str, 'bloq': str_horas_bloqueadas,
                            'tipo': nuevo_tipo, 'disp': disp_int, 'dias': str_dias,
                            'acc_v': acc_virt_int, 'h_ini_v': h_ini_v_str, 'h_fin_v': h_fin_v_str
                        })
                        doc_id = result.lastrowid
                        for area in areas_seleccionadas:
                            conn.execute(text("INSERT INTO docente_area (ID_Docente, ID_Area) VALUES (:id_doc, :id_area)"),
                                         {'id_doc': doc_id, 'id_area': dict_areas[area]})
                                         
                    st.success(f"✅ ¡Ing. {nuevo_nombre} registrado exitosamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error BD: {e}")

    # =========================================================
    # PESTAÑA 3: EDITAR PERFIL 
    # =========================================================
    with tab_editar:
        st.markdown("### ✏️ Configurar Perfil Operativo")
        
        opciones_editar = {f"{row['ID_Docente']} - {row['Nombre']}": row['ID_Docente'] for idx, row in df_profes.iterrows()}
        seleccion_editar = st.selectbox("🔍 Busque y seleccione un docente para actualizar:", ["Seleccione..."] + list(opciones_editar.keys()), key="edit_selector_docente")

        if seleccion_editar != "Seleccione...":
            doc_id = opciones_editar[seleccion_editar]
            doc_data = df_profes[df_profes['ID_Docente'] == doc_id].iloc[0]
            areas_actuales = doc_data['Areas'].split(', ') if pd.notna(doc_data['Areas']) and doc_data['Areas'] != 'Sin área asignada' else []

            # 🎨 Visualizador rápido del estado actual
            estado_visual = "🟢 ACTIVO" if doc_data['Disponible'] == 1 else "🔴 INACTIVO"
            st.markdown(f"#### Editando Perfil de: **{doc_data['Nombre']}** ({estado_visual})")
            st.write("")

            with st.container(border=True):
                st.markdown("#### 1. Datos Contractuales")
                col1, col2 = st.columns(2)
                with col1:
                    edit_nombre = st.text_input("Nombre", doc_data['Nombre'], key=f"edit_nombre_{doc_id}")
                    tipos = ['Base', 'Emergente', 'Tegucigalpa']
                    idx_tipo = tipos.index(doc_data['Tipo_Docente']) if doc_data['Tipo_Docente'] in tipos else 0
                    edit_tipo = st.selectbox("Tipo de Contrato", tipos, index=idx_tipo, key=f"edit_tipo_{doc_id}")
                with col2:
                    dias_semana = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sa', 'Do']
                    dias_actuales_lista = str(doc_data.get('Dias_Trabajo', 'Lu,Ma,Mi,Ju,Vi')).split(',')
                    dias_actuales_lista = [d.strip() for d in dias_actuales_lista if d.strip() in dias_semana]
                    if not dias_actuales_lista: dias_actuales_lista = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi']
                    edit_dias = st.multiselect("Días de Trabajo", dias_semana, default=dias_actuales_lista, key=f"edit_dias_{doc_id}")
                    str_edit_dias = ",".join(edit_dias)
                    edit_areas = st.multiselect("📚 Áreas Académicas", list(dict_areas.keys()), default=[a for a in areas_actuales if a in dict_areas], key=f"edit_areas_{doc_id}")

            with st.container(border=True):
                st.markdown("#### 2. Modalidad y Horarios de Trabajo")
                
                h_ini_str = str(doc_data['Hora_Inicio_Turno']).split()[-1] if pd.notnull(doc_data['Hora_Inicio_Turno']) else "00:00:00"
                daba_presencial = h_ini_str != "00:00:00"
                
                edit_imparte_presencial = st.checkbox("🏫 El docente imparte clases PRESENCIALES", value=daba_presencial, key=f"edit_chk_pres_{doc_id}")
                if edit_imparte_presencial:
                    col_p1, col_p2 = st.columns(2)
                    h_fin_str = str(doc_data['Hora_Fin_Turno']).split()[-1] if pd.notnull(doc_data['Hora_Fin_Turno']) else "13:00:00"
                    if h_ini_str == "00:00:00": h_ini_str = "07:00:00" 
                    with col_p1:
                        edit_h_inicio = st.time_input("Hora Inicio (Presencial)", datetime.datetime.strptime(h_ini_str, '%H:%M:%S').time(), key=f"edit_h_ini_p_{doc_id}", step=datetime.timedelta(hours=1))
                    with col_p2:
                        edit_h_fin = st.time_input("Hora Fin (Presencial)", datetime.datetime.strptime(h_fin_str, '%H:%M:%S').time(), key=f"edit_h_fin_p_{doc_id}", step=datetime.timedelta(hours=1))
                
                st.write("")
                val_virtual = bool(doc_data.get('Acepta_Virtualidad', 0))
                edit_imparte_virtual = st.checkbox("🌐 El docente imparte clases VIRTUALES", value=val_virtual, key=f"edit_chk_virt_{doc_id}")
                
                if edit_imparte_virtual:
                    hv_ini_str = str(doc_data['Hora_Inicio_Virtual']).split()[-1] if pd.notnull(doc_data.get('Hora_Inicio_Virtual')) else "17:00:00"
                    hv_fin_str = str(doc_data['Hora_Fin_Virtual']).split()[-1] if pd.notnull(doc_data.get('Hora_Fin_Virtual')) else "21:00:00"
                    col_v1, col_v2 = st.columns(2)
                    with col_v1:
                        edit_h_inicio_v = st.time_input("Hora Inicio (Virtual)", datetime.datetime.strptime(hv_ini_str, '%H:%M:%S').time(), key=f"edit_h_ini_v_{doc_id}", step=datetime.timedelta(hours=1))
                    with col_v2:
                        edit_h_fin_v = st.time_input("Hora Fin (Virtual)", datetime.datetime.strptime(hv_fin_str, '%H:%M:%S').time(), key=f"edit_h_fin_v_{doc_id}", step=datetime.timedelta(hours=1))

            with st.container(border=True):
                st.markdown("#### 3. Configuración de IA")
                
                bloq_str = str(doc_data['Horas_Bloqueadas']) if pd.notnull(doc_data['Horas_Bloqueadas']) and doc_data['Horas_Bloqueadas'] != '' else ""
                bloq_actuales_lista = [int(h.strip()) for h in bloq_str.split(',') if h.strip().isdigit() and int(h.strip()) in DICCIONARIO_HORAS]
                
                edit_horas_seleccionadas = st.multiselect(
                    "⏳ Bloques No Disponibles (Horas Bloqueadas para la IA)",
                    options=list(DICCIONARIO_HORAS.keys()),
                    default=bloq_actuales_lista,
                    format_func=lambda x: DICCIONARIO_HORAS[x],
                    key=f"edit_bloqueadas_{doc_id}"
                )
                str_edit_horas_bloqueadas = ",".join(map(str, edit_horas_seleccionadas))
                
                st.write("")
                edit_disp = st.checkbox("🟢 Docente Disponible (Desmárcalo para desactivarlo temporalmente sin borrarlo)", value=bool(doc_data['Disponible']), key=f"edit_chk_disp_{doc_id}")
                
            st.write("")
            if st.button("💾 Sobrescribir Perfil Operativo", type="primary", use_container_width=True, key=f"btn_edit_docente_{doc_id}"):
                if not edit_areas:
                    st.error("⚠️ El docente debe pertenecer a al menos un área.")
                elif not edit_imparte_presencial and not edit_imparte_virtual:
                    st.error("🚨 El docente debe impartir al menos una modalidad (Presencial o Virtual).")
                else:
                    h_ini_str = edit_h_inicio.strftime('%H:%M:%S') if edit_imparte_presencial else "00:00:00"
                    h_fin_str = edit_h_fin.strftime('%H:%M:%S') if edit_imparte_presencial else "00:00:00"
                    acc_virt_int = 1 if edit_imparte_virtual else 0
                    h_ini_v_str = edit_h_inicio_v.strftime('%H:%M:%S') if edit_imparte_virtual else None
                    h_fin_v_str = edit_h_fin_v.strftime('%H:%M:%S') if edit_imparte_virtual else None
                    
                    update_query = text("""
                        UPDATE docentes_activos 
                        SET Nombre = :nom, Hora_Inicio_Turno = :h_ini, Hora_Fin_Turno = :h_fin, 
                            Horas_Bloqueadas = :bloq, Tipo_Docente = :tipo, Disponible = :disp, Dias_Trabajo = :dias,
                            Acepta_Virtualidad = :acc_v, Hora_Inicio_Virtual = :h_ini_v, Hora_Fin_Virtual = :h_fin_v
                        WHERE ID_Docente = :id
                    """)
                    try:
                        with engine.begin() as conn:
                            conn.execute(update_query, {
                                'nom': edit_nombre, 'h_ini': h_ini_str, 'h_fin': h_fin_str, 'bloq': str_edit_horas_bloqueadas,
                                'tipo': edit_tipo, 'disp': 1 if edit_disp else 0, 'dias': str_edit_dias, 
                                'acc_v': acc_virt_int, 'h_ini_v': h_ini_v_str, 'h_fin_v': h_fin_v_str, 'id': doc_id
                            })
                            conn.execute(text("DELETE FROM docente_area WHERE ID_Docente = :id"), {'id': doc_id})
                            for area in edit_areas:
                                conn.execute(text("INSERT INTO docente_area (ID_Docente, ID_Area) VALUES (:id_doc, :id_area)"),
                                             {'id_doc': doc_id, 'id_area': dict_areas[area]})
                        st.success("✅ ¡Perfil actualizado exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al actualizar: {e}")

    # =========================================================
    # PESTAÑA 4: ZONA DE PELIGRO (ELIMINAR DOCENTE)
    # =========================================================
    with tab_eliminar:
        st.markdown("### 🚨 Danger Zone: Baja Definitiva de Personal")
        
        with st.container(border=True):
            st.error("⚠️ **ATENCIÓN:** Eliminar a un docente borrará todo su registro operativo y vínculos con sus áreas. Esta acción destruirá la configuración de la IA para esta persona. Se recomienda **Desactivarlo** en la pestaña 'Configurar Perfil' en lugar de borrarlo.")
            st.write("")
            
            seleccion_eliminar = st.selectbox("🔍 Seleccione el docente a ELIMINAR permanentemente:", ["Seleccione..."] + list(opciones_editar.keys()), key="select_del_docente")
            
            if seleccion_eliminar != "Seleccione...":
                doc_id_del = opciones_editar[seleccion_eliminar]
                st.write("")
                confirmacion = st.checkbox(f"🔴 Comprendo los riesgos. Estoy absolutamente seguro de que deseo eliminar a **{seleccion_eliminar.split('-')[1].strip()}** de la base de datos.", key="chk_confirm_del")
                
                st.write("")
                if st.button("🗑️ Destruir Registro de Docente", type="primary", disabled=not confirmacion, use_container_width=True, key="btn_del_docente"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM docente_area WHERE ID_Docente = :id"), {'id': doc_id_del})
                            conn.execute(text("DELETE FROM docentes_activos WHERE ID_Docente = :id"), {'id': doc_id_del})
                        st.success("✅ ¡Docente eliminado permanentemente del sistema!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error: {e} (Posiblemente el docente ya tiene clases vinculadas en un horario histórico o activo).")