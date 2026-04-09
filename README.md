**# 🎓 Optimizador Académico IA (Optimizador_ML)**

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-Framework-FF4B4B)
![Machine Learning](https://img.shields.io/badge/ML-XGBoost-orange)
![Optimization](https://img.shields.io/badge/OR--Tools-CP--SAT-green)

Este repositorio contiene el código fuente del **Sistema de Soporte a Decisiones (DSS)** desarrollado para la optimización de la planificación de la oferta académica. El sistema integra algoritmos de Inteligencia Artificial (Machine Learning) para la predicción de la demanda estudiantil y modelos de Optimización Combinatoria para la generación de horarios académicos libres de colisiones.

**## 🚀 Arquitectura del Sistema**

El proyecto está diseñado bajo una arquitectura de microservicios lógicos y se compone de los siguientes motores:

1. **Motor Predictivo (Machine Learning):** Utiliza `XGBoost` para predecir la demanda exacta de cupos por asignatura, resolviendo el problema de arranque en frío (*Cold Start*) en historiales académicos asimétricos.
2. **Motor Logístico (Programación con Restricciones):** Implementa `Google OR-Tools (CP-SAT)` para orquestar los espacios físicos (aulas) y el personal docente. Aplica un sistema de restricciones duras y blandas, asegurando **0 colisiones operativas**.
3. **Capa de Presentación (Frontend):** Desarrollada nativamente en `Streamlit`, ofreciendo interfaces desacopladas según el rol del usuario (Jefatura, Docente y Estudiante).

---

**## 📂 Estructura del Proyecto**

Optimizador_ML/
├── app/                        # Interfaces gráficas (Frontend - Streamlit)
│   ├── dashboard.py            # Portal de Jefatura (Métricas y XAI)
│   ├── gestion_docentes.py     # Módulo administrativo
│   ├── student_portal.py       # Censo inteligente y matrícula
│   └── teacher_portal.py       # Portal de revisión de carga para docentes
├── config/                     # Configuración global
│   └── db_connection.py        # Conexión cifrada a la base de datos MySQL
├── data/                       # Archivos CSV para ingesta manual (ETL temporal)
├── notebooks/                  # Jupyter Notebooks para experimentación de modelos
├── src/                        # Lógica de Negocio (Backend)
│   ├── logic/                  # Procesamiento de grafos (NetworkX) y datos
│   ├── ml/                     # Modelos de Machine Learning (demand_model.py)
│   └── optimizer/              # Motor CP-SAT logístico (scheduler.py)
├── main.py                     # Punto de entrada de la aplicación web
├── requirements.txt            # Dependencias del proyecto
└── .env                        # Variables de entorno (¡No subir a control de versiones!)

**⚙️ Requisitos Previos**
Python: 3.10 o superior.

**Base de Datos:** Motor MySQL Server en ejecución.

**Git:** Para clonar el repositorio.

**🛠️ Instalación y Despliegue Local**
Sigue estos pasos para replicar el entorno de producción en tu máquina local:

**1. Clonar el repositorio:**
git clone [https://github.com/Joasro/Optimizador_ML.git](https://github.com/Joasro/Optimizador_ML.git)
cd Optimizador_ML

**2. Crear y activar un entorno virtual**
# En Windows:
python -m venv venv
venv\Scripts\activate

# En macOS/Linux:
python3 -m venv venv
source venv/bin/activate

**3. Instalar las dependencias**
pip install -r requirements.txt

**4. Configuración de Variables de Entorno**
Crea un archivo llamado .env en la raíz del proyecto y configura tus credenciales de acceso a la base de datos MySQL basándote en el siguiente esquema:
DB_HOST=localhost
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_NAME=nombre_de_la_base_de_datos

**▶️ Uso del Sistema**
Para levantar la aplicación y acceder a los portales, ejecuta el siguiente comando en la raíz del proyecto:
streamlit run main.py

El servidor local se iniciará y abrirá automáticamente la aplicación en tu navegador predeterminado (por lo general en http://localhost:8501). Desde ahí, el sistema presentará el Login unificado y redireccionará al usuario (Estudiante, Docente o Jefatura) a su módulo correspondiente.
