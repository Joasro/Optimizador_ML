import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine

# Configuración del estilo visual (mismo estilo para mantener coherencia en la tesis)
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("Blues_d")

def generar_grafico_planes():
    print("📊 Generando gráfico de distribución por Plan de Estudio...")
    
    try:
        # 1. Conexión a tu BD
        user = "Joasro"
        password = "Akriila123." 
        host = "localhost"
        db = "dss_academico_unah"
        
        engine = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}/{db}")
        
        # 2. CONSULTA DIRECTA (A la tabla estudiantes para sacar el plan)
        query = """
            SELECT plan_estudio as Plan_Estudio
            FROM estudiantes
        """
        df = pd.read_sql(query, engine)
        print(f"✅ Se extrajeron datos de {len(df)} estudiantes desde MySQL.")
        
    except Exception as e:
        print(f"⚠️ Error de conexión o consulta: {e}")
        return 

    # 3. Agrupación y conteo
    # Se cuenta cuántos estudiantes hay por cada plan de estudio
    conteo_planes = df['Plan_Estudio'].value_counts().reset_index()
    conteo_planes.columns = ['Plan de Estudio', 'Cantidad de Estudiantes']

    # 4. Creación de la figura
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Crear el gráfico de barras
    bars = sns.barplot(
        data=conteo_planes, 
        x='Plan de Estudio', 
        y='Cantidad de Estudiantes', 
        hue='Plan de Estudio',
        palette='Blues_d', 
        ax=ax,
        edgecolor='#2c3e50',
        linewidth=1.5,
        legend=False
    )
    
    # Personalización
    ax.set_title('Distribución Demográfica por Plan de Estudio\n(Población Activa - Piloto UNAH-Comayagua)', 
                 fontsize=15, fontweight='bold', pad=20, color='#2c3e50')
    ax.set_xlabel('Plan de Estudio Vigente', fontsize=12, fontweight='bold', labelpad=10)
    ax.set_ylabel('Cantidad de Estudiantes Matriculados', fontsize=12, fontweight='bold', labelpad=10)
    
    # Etiquetas sobre las barras
    for p in bars.patches:
        height = p.get_height()
        if height > 0: 
            ax.annotate(f'{int(height)}', 
                        xy=(p.get_x() + p.get_width() / 2, height),
                        xytext=(0, 6),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=12, fontweight='bold', color='#1a252f')
    
    # Configuración de márgenes
    ax.set_ylim(0, conteo_planes['Cantidad de Estudiantes'].max() * 1.2)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()
    
    # Guardar la imagen
    nombre_archivo = '00_distribucion_planes.png'
    plt.savefig(nombre_archivo, dpi=300, bbox_inches='tight')
    print(f"🎉 ¡Éxito! Gráfico guardado como: '{nombre_archivo}'")
    plt.close()

if __name__ == '__main__':
    generar_grafico_planes()