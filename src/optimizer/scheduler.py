import pandas as pd
from ortools.sat.python import cp_model
from sqlalchemy import text

def extraer_hora(valor_tiempo):
    if pd.isna(valor_tiempo): return None
    val_str = str(valor_tiempo).strip()
    if val_str == '00:00:00' or val_str == '0': return None
    if 'days' in val_str: return int(val_str.split('days')[1].split(':')[0].strip())
    return int(val_str.split(':')[0])

def docente_puede_dar_clase(docente, hora_int):
    if pd.notna(docente['Horas_Bloqueadas']) and str(docente['Horas_Bloqueadas']).strip() != "":
        bloqueadas = [int(h.strip()) for h in str(docente['Horas_Bloqueadas']).split(',') if h.strip().isdigit()]
        if hora_int in bloqueadas: return False 
    es_horario_virtual = hora_int >= 17 
    if es_horario_virtual:
        if docente.get('Acepta_Virtualidad', 0) == 0: return False 
        ini_v = extraer_hora(docente['Hora_Inicio_Virtual']) or 17
        fin_v = extraer_hora(docente['Hora_Fin_Virtual']) or 21
        return ini_v <= hora_int < fin_v
    else:
        ini_p = extraer_hora(docente['Hora_Inicio_Turno'])
        fin_p = extraer_hora(docente['Hora_Fin_Turno'])
        if ini_p is None or fin_p is None: return False
        return ini_p <= hora_int < fin_p

def ejecutar_optimizador(engine):
    # 1. Cargar Docentes
    df_docentes = pd.read_sql("""
        SELECT d.ID_Docente, d.Nombre, d.Hora_Inicio_Turno, d.Hora_Fin_Turno, d.Horas_Bloqueadas,
               d.Acepta_Virtualidad, d.Hora_Inicio_Virtual, d.Hora_Fin_Virtual,
               GROUP_CONCAT(a.ID_Area) as Areas
        FROM docentes_activos d
        LEFT JOIN docente_area da ON d.ID_Docente = da.ID_Docente
        LEFT JOIN areas_academicas a ON da.ID_Area = a.ID_Area
        WHERE d.Disponible = 1 GROUP BY d.ID_Docente
    """, engine)
    docentes = df_docentes.to_dict('records')
    for d in docentes: d['Areas'] = [int(x) for x in str(d['Areas']).split(',')] if pd.notna(d['Areas']) else []

    # 2. Cargar Aulas
    df_espacios = pd.read_sql("SELECT ID_Espacio, Nombre_Espacio, Capacidad_Maxima as Capacidad FROM espacios_fisicos", engine)
    espacios = df_espacios.to_dict('records')

    # 3. Cargar Demanda (Desde tu CSV original)
    try:
        df_demanda = pd.read_csv('data/demanda_proyectada_2026.csv')
    except:
        return False, ["No hay demanda generada. Asegúrese de que haya datos en el censo (CSV no encontrado)."]
    clases = df_demanda.to_dict('records')
    
    # 4. NUEVO: CARGAR HISTORIAL DE LA BASE DE DATOS
    # 4. NUEVO: CARGAR HISTORIAL DE LA BASE DE DATOS
    try:
        df_hist = pd.read_sql("SELECT ID_Clase, ID_Docente, ID_Espacio, Hora_Inicio FROM historial_oferta_academica", engine)
        hist_stats = {}
        docente_aula_pref = {} # 👈 NUEVO: Diccionario para las aulas de los docentes
        
        if not df_hist.empty:
            df_hist['Hora_Int'] = df_hist['Hora_Inicio'].apply(lambda x: extraer_hora(x))
            
            # 1. Sacar la moda por CLASE (Lo que ya tenías)
            for c_id, group in df_hist.groupby('ID_Clase'):
                h_mod = group['Hora_Int'].mode()[0] if not group['Hora_Int'].mode().empty else -1
                r_mod = group['ID_Espacio'].mode()[0] if not group['ID_Espacio'].mode().empty else -1
                d_mod = group['ID_Docente'].mode()[0] if not group['ID_Docente'].mode().empty else -1
                hist_stats[c_id] = {'h': h_mod, 'r': r_mod, 'd': d_mod}
                
            # 2. 👈 NUEVO: Sacar la moda de aula por DOCENTE
            for d_id, group in df_hist.groupby('ID_Docente'):
                if not group['ID_Espacio'].mode().empty:
                    docente_aula_pref[d_id] = group['ID_Espacio'].mode()[0]
                    
    except Exception as e:
        print(f"Aviso: No se pudo cargar historial ({e}). Se usará optimización pura.")
        hist_stats = {}
        docente_aula_pref = {}

    model = cp_model.CpModel()
    asignaciones = {}
    horas_disponibles = list(range(7, 21))

    # Variables
    for c in clases:
        c_id = int(c['ID_Clase'])
        for h in horas_disponibles:
            for d in docentes:
                if int(c['ID_Area']) in d['Areas'] and docente_puede_dar_clase(d, h):
                    for r in espacios:
                        var_name = f'A_c{c_id}_d{d["ID_Docente"]}_r{r["ID_Espacio"]}_h{h}'
                        asignaciones[(c_id, d['ID_Docente'], r['ID_Espacio'], h)] = model.NewBoolVar(var_name)

    # Restricciones Duras
    for d in docentes:
        for h in horas_disponibles:
            model.AddAtMostOne([asignaciones[k] for k in asignaciones if k[1] == d['ID_Docente'] and k[3] == h])
    for r in espacios:
        for h in horas_disponibles:
            model.AddAtMostOne([asignaciones[k] for k in asignaciones if k[2] == r['ID_Espacio'] and k[3] == h])

    costos = []
    
    # Restricción de Cupos (Slack)
    for c in clases:
        c_id = int(c['ID_Clase'])
        vars_clase = [asignaciones[k] for k in asignaciones if k[0] == c_id]
        if vars_clase:
            slack = model.NewIntVar(0, int(c['Cupos_Estimados']), f'slack_{c_id}')
            model.Add(sum(
                int(float(next(esp['Capacidad'] for esp in espacios if esp['ID_Espacio'] == k[2])) * 1.2) * asignaciones[k]
                for k in asignaciones if k[0] == c_id
            ) + slack >= int(c['Cupos_Estimados']))
            costos.append(slack * 5000)

    # NUEVO: LÓGICA DE COSTOS Y RECOMPENSAS HISTÓRICAS
    for k, var in asignaciones.items():
        c_id, d_id, r_id, h = k
        c_info = next(c for c in clases if int(c['ID_Clase']) == c_id)
        
        hora_ideal = -1
        if str(c_info.get('Hora_Sugerida', 'Sin preferencia')) != 'Sin preferencia':
            try: hora_ideal = int(str(c_info['Hora_Sugerida']).split(':')[0])
            except: pass

        # Costo base por asignar una clase
        # Costo base por asignar una clase
        costo_asignacion = 100 
        
        # 🚨 NUEVO: PENALIZACIÓN POR USAR LAS 7:00 AM
        # Como es rarísimo abrir clases a esta hora, le cobramos una multa altísima al motor.
        if h == 7:
            costo_asignacion += 300  # Evitará las 7 AM como si fuera fuego.
        
        # Recompensa por cumplir la hora del Censo Estudiantil
        if h == hora_ideal: 
            costo_asignacion -= 30 
            
        # Recompensas por respetar la HISTORIA DE LA CLASE
        if c_id in hist_stats:
            if h == hist_stats[c_id]['h']:
                costo_asignacion -= 60  # Mayor recompensa por respetar la HORA
            if r_id == hist_stats[c_id]['r']:
                costo_asignacion -= 20  # Recompensa media por respetar el AULA de la clase
            if d_id == hist_stats[c_id]['d']:
                costo_asignacion -= 10  # Recompensa baja por respetar al DOCENTE

        # 👈 NUEVO: Recompensa por darle al DOCENTE su aula favorita general
        if d_id in docente_aula_pref and r_id == docente_aula_pref[d_id]:
            costo_asignacion -= 25 # Un premio jugoso por hacer sentir al ingeniero como en casa

        # Evitamos que el costo sea negativo para no romper el minimizador matemático
        costo_asignacion = max(1, costo_asignacion)
        costos.append(costo_asignacion * var)

    model.Minimize(sum(costos))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60.0
    status = solver.Solve(model)

    alertas = []
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        horarios_generados = []
        for k, variable in asignaciones.items():
            if solver.Value(variable) == 1:
                c_id, d_id, r_id, h = k
                c_info = next(c for c in clases if int(c['ID_Clase']) == c_id)
                r_info = next(r for r in espacios if r['ID_Espacio'] == r_id)
                
                demanda_real = int(c_info['Cupos_Estimados'])
                cap_fisica = int(float(r_info['Capacidad']))
                cupos_a_habilitar = demanda_real + 5 if demanda_real <= cap_fisica else int(cap_fisica * 1.2)
                
                horarios_generados.append({
                    'ID_Clase': c_id, 'ID_Docente': d_id, 'ID_Espacio': r_id,
                    'Hora_Inicio': f"{h:02d}:00:00", 'Hora_Fin': f"{(h+1):02d}:00:00",
                    'Cupos': cupos_a_habilitar
                })

        for c in clases:
            c_id = int(c['ID_Clase'])
            cupos_logrados = sum([int(float(next(esp['Capacidad'] for esp in espacios if esp['ID_Espacio'] == k[2])) * 1.2) 
                                  for k in asignaciones if k[0] == c_id and solver.Value(asignaciones[k]) == 1])
            if cupos_logrados < int(c['Cupos_Estimados']):
                alertas.append(f"Déficit en {c['Codigo_Oficial']} - {c['Nombre_Clase']}: Faltan {int(c['Cupos_Estimados']) - cupos_logrados} cupos físicos.")

        if horarios_generados:
            with engine.begin() as conn:
                conn.execute(text("TRUNCATE TABLE oferta_academica_generada"))
                for h in horarios_generados:
                    dias_asig = "Lu,Ma,Mi,Ju,Vi" if int(h['Hora_Inicio'][:2]) >= 17 else "Lu,Ma,Mi,Ju"
                    conn.execute(text("""
                        INSERT INTO oferta_academica_generada 
                        (Periodo_Academico, ID_Clase, ID_Docente, ID_Espacio, Dias, Hora_Inicio, Hora_Fin, Cupos_Maximos, Aprobado_Por_Jefatura)
                        VALUES ('1-2026', :clase, :doc, :esp, :dias, :h_ini, :h_fin, :cupos, 0)
                    """), {'clase': h['ID_Clase'], 'doc': h['ID_Docente'], 'esp': h['ID_Espacio'], 'dias': dias_asig, 'h_ini': h['Hora_Inicio'], 'h_fin': h['Hora_Fin'], 'cupos': h['Cupos']})
        return True, alertas
    else:
        return False, ["Caos logístico: Imposible resolver con los recursos y docentes actuales."]