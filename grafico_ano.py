import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine

# Configuración del estilo visual
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("Blues_d")

def generar_grafico_distribucion():
    print("📊 Generando gráfico de distribución demográfica...")
    
    try:
        # 1. Conexión a tu BD
        user = "Joasro"
        password = "Akriila123." 
        host = "localhost"
        db = "dss_academico_unah"
        
        engine = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}/{db}")
        
        # 2. CONSULTA DIRECTA (Solo a la tabla estudiantes, sin joins ni censo)
        query = """
            SELECT ano_ingreso as Ano_Ingreso
            FROM estudiantes
        """
        df = pd.read_sql(query, engine)
        print(f"✅ Se extrajeron datos de {len(df)} estudiantes desde MySQL.")
        
    except Exception as e:
        print(f"⚠️ Error de conexión o consulta: {e}")
        return 

    # 3. Agrupación y conteo
    conteo_anos = df['Ano_Ingreso'].value_counts().reset_index()
    conteo_anos.columns = ['Año de Ingreso', 'Cantidad de Estudiantes']
    conteo_anos = conteo_anos.sort_values('Año de Ingreso')

    # 4. Creación de la figura
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Crear el gráfico de barras
    bars = sns.barplot(
        data=conteo_anos, 
        x='Año de Ingreso', 
        y='Cantidad de Estudiantes', 
        hue='Año de Ingreso',
        palette='Blues_d', 
        ax=ax,
        edgecolor='#2c3e50',
        linewidth=1.5,
        legend=False
    )
    
    # Personalización
    ax.set_title('Distribución Demográfica de Estudiantes por Año de Ingreso\n(Población Activa - Piloto UNAH-Comayagua)', 
                 fontsize=15, fontweight='bold', pad=20, color='#2c3e50')
    ax.set_xlabel('Año de Ingreso Institucional', fontsize=12, fontweight='bold', labelpad=10)
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
    
    # Línea de tendencia
    ax.plot(range(len(conteo_anos)), conteo_anos['Cantidad de Estudiantes'], 
            color='#e74c3c', marker='o', linestyle='-', linewidth=2.5, markersize=8,
            label='Curva de Densidad Poblacional')
    
    ax.set_ylim(0, conteo_anos['Cantidad de Estudiantes'].max() * 1.2)
    ax.legend(loc='upper left', frameon=True, shadow=True)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()
    
    # Guardar
    nombre_archivo = '00_distribucion_anos.png'
    plt.savefig(nombre_archivo, dpi=300, bbox_inches='tight')
    print(f"🎉 ¡Éxito! Gráfico guardado como: '{nombre_archivo}'")
    plt.close()

if __name__ == '__main__':
    generar_grafico_distribucion()