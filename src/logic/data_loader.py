import sys
import os
import pandas as pd

# Asegurar que encuentre la configuración de BD
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config.db_connection import get_connection

class DataLoader:
    def __init__(self):
        self.conn = get_connection()

    def obtener_demanda_agrupada(self):
        """
        Lee el censo y agrupa cuántos estudiantes necesitan cada clase por jornada.
        (Aquí aplicaremos luego los pesos si están por egresar).
        """
        query = """
            SELECT c.ID_Clase, m.Codigo_Oficial, m.Nombre_Clase, m.ID_Area, 
                   c.Jornada_Preferencia, SUM(c.Prioridad_Alumno) as Prioridad_Total, 
                   COUNT(c.Hash_Cuenta) as Total_Alumnos
            FROM censo_periodo_actual c
            JOIN malla_curricular m ON c.ID_Clase = m.ID_Clase
            GROUP BY c.ID_Clase, m.Codigo_Oficial, m.Nombre_Clase, m.ID_Area, c.Jornada_Preferencia
            ORDER BY Prioridad_Total DESC
        """
        return pd.read_sql(query, self.conn)

    def obtener_docentes_disponibles(self):
        """
        Extrae los docentes, sus horarios, su tipo (Base, Emergente) y las áreas que dominan.
        """
        query = """
            SELECT d.ID_Docente, d.Nombre, d.Hora_Inicio_Turno, d.Hora_Fin_Turno, 
                   d.Horas_Bloqueadas, d.Tipo_Docente, GROUP_CONCAT(da.ID_Area) as Areas_Habilitadas
            FROM docentes_activos d
            LEFT JOIN docente_area da ON d.ID_Docente = da.ID_Docente
            GROUP BY d.ID_Docente
        """
        df_docentes = pd.read_sql(query, self.conn)
        
        # Convertir el string de áreas separadas por coma en una lista de enteros
        df_docentes['Areas_Habilitadas'] = df_docentes['Areas_Habilitadas'].apply(
            lambda x: [int(i) for i in str(x).split(',')] if pd.notna(x) else []
        )
        return df_docentes

    def obtener_aulas(self):
        """
        Lista los espacios físicos, su capacidad y su tipo (Laboratorio o Aula).
        """
        query = "SELECT ID_Espacio, Nombre_Espacio, Tipo_Espacio, Capacidad_Maxima FROM espacios_fisicos"
        return pd.read_sql(query, self.conn)

    def obtener_malla(self):
        """
        Información de las clases y a qué área pertenecen.
        """
        query = "SELECT ID_Clase, Codigo_Oficial, Nombre_Clase, ID_Area FROM malla_curricular"
        return pd.read_sql(query, self.conn)

    def cerrar_conexion(self):
        if self.conn:
            self.conn.close()

# Bloque de prueba
if __name__ == "__main__":
    loader = DataLoader()
    
    print("📥 Cargando datos desde MySQL para el Optimizador...\n")
    
    aulas = loader.obtener_aulas()
    print(f"✅ Aulas cargadas: {len(aulas)}")
    
    docentes = loader.obtener_docentes_disponibles()
    print(f"✅ Docentes activos cargados: {len(docentes)}")
    
    demanda = loader.obtener_demanda_agrupada()
    print(f"✅ Requerimientos de clases agrupados: {len(demanda)}")
    
    loader.cerrar_conexion()
    print("\n🚀 Datos listos para ser inyectados en el Algoritmo Genético.")