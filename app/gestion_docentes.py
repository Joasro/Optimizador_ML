import streamlit as st
import pandas as pd
from sqlalchemy import text
import datetime

def mostrar_gestion_docentes(engine):
    st.title("👨‍🏫 Gestión de Personal Docente")
    st.markdown("Administra la disponibilidad, días de trabajo y restricciones de los ingenieros.")

    # 1. Cargar datos en vivo desde MySQL (Usando tus columnas reales)
    try:
        df_profes = pd.read_sql("SELECT * FROM docentes_activos", engine)
    except Exception as e:
        st.error(f"Error conectando a la base de datos: {e}")
        return
    
    tab_ver, tab_agregar, tab_editar, tab_eliminar = st.tabs([
        "📋 Lista de Docentes", 
        "➕ Agregar Nuevo", 
        "✏️ Editar Existente", 
        "🗑️ Eliminar Docente"
    ])

    # ---------------------------------------------------------
    # PESTAÑA 1: VER LA TABLA
    # ---------------------------------------------------------
    with tab_ver:
        st.subheader("Estado Actual del Personal")
        # Aquí usamos exactamente 'Nombre' en lugar de 'Nombre_Docente'
        df_mostrar = df_profes[['ID_Docente', 'Nombre', 'Tipo_Docente', 'Dias_Trabajo', 'Hora_Inicio_Turno', 'Hora_Fin_Turno', 'Horas_Bloqueadas', 'Disponible']].copy()
        df_mostrar['Estado'] = df_mostrar['Disponible'].apply(lambda x: "✅ Activo" if x == 1 else "❌ Inactivo")
        
        st.dataframe(
            df_mostrar.drop(columns=['Disponible']), 
            use_container_width=True, 
            height=500,
            hide_index=True 
        )

    # ---------------------------------------------------------
    # PESTAÑA 2: AGREGAR DOCENTE
    # ---------------------------------------------------------
    with tab_agregar:
        st.subheader("➕ Registrar Nuevo Ingeniero")
        with st.form("form_agregar_docente"):
            col1, col2 = st.columns(2)
            with col1:
                nuevo_nombre = st.text_input("Nombre Completo (Ej. Ing. Juan Pérez)")
                nueva_h_inicio = st.time_input("Hora Inicio Turno", datetime.time(7, 0))
                nueva_h_fin = st.time_input("Hora Fin Turno", datetime.time(21, 0))
                
                # Selector de Días de Trabajo
                dias_semana = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sa', 'Do']
                dias_seleccionados = st.multiselect("Días de Trabajo", dias_semana, default=['Lu', 'Ma', 'Mi', 'Ju', 'Vi'])
                str_dias = ",".join(dias_seleccionados)
                
            with col2:
                nuevo_tipo = st.selectbox("Tipo de Contrato", ['Base', 'Emergente', 'Tegucigalpa'])
                horas_bloqueadas = st.text_input("Horas Bloqueadas (Opcional, Ej. 12, 13)", "")
                esta_disponible = st.checkbox("🟢 Docente Activo para este Periodo", value=True)
            
            submit_agregar = st.form_submit_button("Guardar Nuevo Docente")

            if submit_agregar:
                if nuevo_nombre.strip() == "":
                    st.error("El nombre no puede estar vacío.")
                elif not dias_seleccionados:
                    st.error("Debe seleccionar al menos un día de trabajo.")
                else:
                    disp_int = 1 if esta_disponible else 0
                    insert_query = text("""
                        INSERT INTO docentes_activos 
                        (Nombre, Hora_Inicio_Turno, Hora_Fin_Turno, Horas_Bloqueadas, Tipo_Docente, Disponible, Dias_Trabajo) 
                        VALUES (:nom, :h_ini, :h_fin, :bloq, :tipo, :disp, :dias)
                    """)
                    with engine.begin() as conn:
                        conn.execute(insert_query, {
                            'nom': nuevo_nombre,
                            'h_ini': nueva_h_inicio.strftime('%H:%M:%S'),
                            'h_fin': nueva_h_fin.strftime('%H:%M:%S'),
                            'bloq': horas_bloqueadas,
                            'tipo': nuevo_tipo,
                            'disp': disp_int,
                            'dias': str_dias
                        })
                    st.success(f"¡Ing. {nuevo_nombre} agregado con éxito!")
                    st.rerun()

    # ---------------------------------------------------------
    # PESTAÑA 3: EDITAR DOCENTE
    # ---------------------------------------------------------
    with tab_editar:
        st.subheader("✏️ Editar Datos de un Docente")
        
        opciones_editar = {f"{row['ID_Docente']} - {row['Nombre']}": row['ID_Docente'] for idx, row in df_profes.iterrows()}
        seleccion_editar = st.selectbox("Seleccione el docente a editar:", ["Seleccione..."] + list(opciones_editar.keys()))

        if seleccion_editar != "Seleccione...":
            doc_id = opciones_editar[seleccion_editar]
            doc_data = df_profes[df_profes['ID_Docente'] == doc_id].iloc[0]

            with st.form("form_editar_docente"):
                col1, col2 = st.columns(2)
                
                with col1:
                    edit_nombre = st.text_input("Nombre", doc_data['Nombre'])
                    
                    h_ini_str = str(doc_data['Hora_Inicio_Turno']).split()[-1] if pd.notnull(doc_data['Hora_Inicio_Turno']) else "07:00:00"
                    h_fin_str = str(doc_data['Hora_Fin_Turno']).split()[-1] if pd.notnull(doc_data['Hora_Fin_Turno']) else "21:00:00"
                    
                    edit_h_inicio = st.time_input("Hora Inicio Turno", datetime.datetime.strptime(h_ini_str, '%H:%M:%S').time())
                    edit_h_fin = st.time_input("Hora Fin Turno", datetime.datetime.strptime(h_fin_str, '%H:%M:%S').time())

                    # Recuperar y mostrar los días actuales
                    dias_semana = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sa', 'Do']
                    dias_actuales = str(doc_data.get('Dias_Trabajo', 'Lu,Ma,Mi,Ju,Vi')).split(',')
                    dias_actuales = [d.strip() for d in dias_actuales if d.strip() in dias_semana]
                    if not dias_actuales: dias_actuales = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi']
                    
                    edit_dias = st.multiselect("Días de Trabajo", dias_semana, default=dias_actuales)
                    str_edit_dias = ",".join(edit_dias)

                with col2:
                    tipos = ['Base', 'Emergente', 'Tegucigalpa']
                    idx_tipo = tipos.index(doc_data['Tipo_Docente']) if doc_data['Tipo_Docente'] in tipos else 0
                    edit_tipo = st.selectbox("Tipo de Contrato", tipos, index=idx_tipo)
                    
                    edit_bloq = st.text_input("Horas Bloqueadas (Ej. 12, 13)", str(doc_data['Horas_Bloqueadas']) if pd.notnull(doc_data['Horas_Bloqueadas']) else "")
                    edit_disp = st.checkbox("🟢 Docente Disponible para este Periodo", value=bool(doc_data['Disponible']))
                
                submit_editar = st.form_submit_button("Guardar Cambios")

                if submit_editar:
                    update_query = text("""
                        UPDATE docentes_activos 
                        SET Nombre = :nom, Hora_Inicio_Turno = :h_ini, Hora_Fin_Turno = :h_fin, 
                            Horas_Bloqueadas = :bloq, Tipo_Docente = :tipo, Disponible = :disp, Dias_Trabajo = :dias
                        WHERE ID_Docente = :id
                    """)
                    with engine.begin() as conn:
                        conn.execute(update_query, {
                            'nom': edit_nombre, 'h_ini': edit_h_inicio.strftime('%H:%M:%S'),
                            'h_fin': edit_h_fin.strftime('%H:%M:%S'), 'bloq': edit_bloq,
                            'tipo': edit_tipo, 'disp': 1 if edit_disp else 0, 'dias': str_edit_dias, 'id': doc_id
                        })
                    st.success("¡Datos actualizados con éxito!")
                    st.rerun()

    # ---------------------------------------------------------
    # PESTAÑA 4: ELIMINAR DOCENTE
    # ---------------------------------------------------------
    with tab_eliminar:
        st.subheader("🗑️ Eliminar Docente del Sistema")
        st.warning("⚠️ Cuidado: Eliminar a un docente es una acción irreversible.")
        
        seleccion_eliminar = st.selectbox("Seleccione el docente a ELIMINAR:", ["Seleccione..."] + list(opciones_editar.keys()), key="select_del")
        
        if seleccion_eliminar != "Seleccione...":
            doc_id_del = opciones_editar[seleccion_eliminar]
            confirmacion = st.checkbox("Estoy seguro que deseo eliminar a este docente permanentemente.")
            
            if st.button("🚨 Eliminar Docente", type="primary", disabled=not confirmacion):
                try:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM docente_area WHERE ID_Docente = :id"), {'id': doc_id_del})
                        conn.execute(text("DELETE FROM docentes_activos WHERE ID_Docente = :id"), {'id': doc_id_del})
                    st.success("¡Docente eliminado del sistema!")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo eliminar al docente por llaves foráneas. Error: {e}")
                    st.info("💡 Sugerencia: En lugar de eliminarlo, ve a 'Editar Existente' y desactiva la disponibilidad.")