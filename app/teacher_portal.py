import streamlit as st
import pandas as pd
from config.db_connection import get_connection

def clean_time(time_val):
    """Limpia la aberración de '0 days 07:00:00' y lo convierte a '07:00 AM' elegantes"""
    if pd.isna(time_val): return "N/A"
    t_str = str(time_val)
    if 'days' in t_str:
        t_str = t_str.split('days')[1].strip()
    
    try:
        # Extraemos solo Horas y Minutos
        parts = t_str.split(':')
        h = int(parts[0])
        m = parts[1]
        ampm = "AM" if h < 12 else "PM"
        h_12 = h if h <= 12 else h - 12
        if h_12 == 0: h_12 = 12
        return f"{h_12:02d}:{m} {ampm}"
    except:
        return t_str[:5]

def vista_docente():
    nombre_docente = st.session_state.get('user_name', '')
    
    # ==========================================
    # 🎨 SIDEBAR RENOVADO
    # ==========================================
    with st.sidebar:
        # Un pequeño avatar para darle vida
        st.image("https://cdn-icons-png.flaticon.com/512/2784/2784403.png", width=120)
        st.title(f"👨‍🏫 {nombre_docente}")
        st.caption("Panel de Control Docente")
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # ==========================================
    # 🌟 ENCABEZADO PRINCIPAL
    # ==========================================
    st.markdown(f"# 👋 Bienvenido, {nombre_docente.split()[0] if nombre_docente else 'Docente'}")
    st.markdown("<p style='font-size: 1.1rem; color: gray;'>Revisa tu perfil operativo y la planificación académica asignada por Jefatura.</p>", unsafe_allow_html=True)
    st.write("")

    conn = get_connection()
    if not conn:
        st.error("❌ Error fatal: No se pudo conectar a la base de datos.")
        return

    try:
        # Obtener el perfil del docente
        query_perfil = """
            SELECT ID_Docente, Hora_Inicio_Turno, Hora_Fin_Turno, Tipo_Docente, 
                   Dias_Trabajo, Acepta_Virtualidad, Hora_Inicio_Virtual, Hora_Fin_Virtual
            FROM docentes_activos 
            WHERE Nombre = %s
        """
        df_perfil = pd.read_sql(query_perfil, conn, params=(nombre_docente,))

        if df_perfil.empty:
            st.error("⚠️ Tu cuenta no está enlazada al catálogo del departamento. Contacta a Jefatura.")
            return

        perfil = df_perfil.iloc[0]
        id_docente = int(perfil['ID_Docente'])

        # ==========================================
        # 🃏 SECCIÓN 1: TARJETAS DE CONTRATO (ADIÓS MÉTRICAS FEAS)
        # ==========================================
        with st.container(border=True):
            st.markdown("#### ⚙️ Configuración Operativa de tu Contrato")
            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.info(f"**📝 Tipo de Contrato**\n\n### {perfil['Tipo_Docente']}")
            with c2:
                h_ini_p = clean_time(perfil['Hora_Inicio_Turno'])
                h_fin_p = clean_time(perfil['Hora_Fin_Turno'])
                st.success(f"**🏢 Turno Presencial**\n\n### {h_ini_p} a {h_fin_p}")
            with c3:
                if perfil['Acepta_Virtualidad'] == 1:
                    h_ini_v = clean_time(perfil['Hora_Inicio_Virtual'])
                    h_fin_v = clean_time(perfil['Hora_Fin_Virtual'])
                    st.warning(f"**💻 Turno Virtual**\n\n### {h_ini_v} a {h_fin_v}")
                else:
                    st.error("**💻 Turno Virtual**\n\n### No habilitada")

        st.write("")
        st.write("")

        # ==========================================
        # 📅 SECCIÓN 2: CARGA ACADÉMICA
        # ==========================================
        query_clases = """
            SELECT 
                m.Codigo_Oficial AS 'Código',
                m.Nombre_Clase AS 'Asignatura',
                o.Dias AS 'Días',
                o.Hora_Inicio AS 'Hora Inicio',
                o.Hora_Fin AS 'Hora Fin',
                e.Nombre_Espacio AS 'Aula',
                o.Cupos_Maximos AS 'Cupos',
                o.Aprobado_Por_Jefatura
            FROM oferta_academica_generada o
            JOIN malla_curricular m ON o.ID_Clase = m.ID_Clase
            JOIN espacios_fisicos e ON o.ID_Espacio = e.ID_Espacio
            WHERE o.ID_Docente = %s
            ORDER BY o.Hora_Inicio ASC
        """
        df_clases = pd.read_sql(query_clases, conn, params=(id_docente,))

        if df_clases.empty:
            st.info("📭 **Aún no tienes carga asignada.** El motor de Inteligencia Artificial o Jefatura aún no han generado los horarios para el próximo periodo.")
        else:
            aprobado = df_clases['Aprobado_Por_Jefatura'].iloc[0] == 1
            
            # --- BANNERS GIGANTES DE ESTADO ---
            if aprobado:
                st.success("## ✅ CARGA ACADÉMICA OFICIAL\n**Esta planificación ha sido aprobada por Jefatura y es definitiva.**")
            else:
                st.warning("## ⚠️ PROPUESTA EN REVISIÓN (BORRADOR)\n**Esta es la propuesta matemática de la IA. Podría sufrir modificaciones por Jefatura antes de su publicación.**")
            
            st.write("")
            st.markdown(f"#### 📚 Tu Horario Programado ({len(df_clases)} secciones)")

            # --- LIMPIEZA DE DATOS PARA LA TABLA ---
            df_mostrar = df_clases.drop(columns=['Aprobado_Por_Jefatura'])
            df_mostrar['Hora Inicio'] = df_mostrar['Hora Inicio'].apply(clean_time)
            df_mostrar['Hora Fin'] = df_mostrar['Hora Fin'].apply(clean_time)

            # --- TABLA INTERACTIVA (ST.DATAFRAME) ---
            st.dataframe(
                df_mostrar,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Código": st.column_config.TextColumn("📌 Código", width="small"),
                    "Asignatura": st.column_config.TextColumn("📘 Asignatura", width="large"),
                    "Días": st.column_config.TextColumn("🗓️ Días", width="small"),
                    "Hora Inicio": st.column_config.TextColumn("⏰ Inicio", width="small"),
                    "Hora Fin": st.column_config.TextColumn("⌛ Fin", width="small"),
                    "Aula": st.column_config.TextColumn("🏫 Medio/Aula", width="medium"),
                    "Cupos": st.column_config.ProgressColumn(
                        "👥 Cupos",
                        help="Capacidad máxima reservada para esta sección",
                        format="%d alumnos",
                        min_value=0,
                        max_value=60 # Límite visual de la barra
                    )
                }
            )
            
    except Exception as e:
        st.error(f"Error procesando la vista: {e}")
    finally:
        conn.close()