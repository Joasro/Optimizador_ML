import mysql.connector
import os
from dotenv import load_dotenv

# Asegura que busque el .env en la raíz del proyecto
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
load_dotenv(os.path.join(basedir, '.env'))

def get_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            user=os.getenv("DB_USER", "Joasro"),
            password=os.getenv("DB_PASSWORD", "Akriila123."),
            database=os.getenv("DB_NAME", "dss_academico_unah"),
            port=3306,
            use_pure=True
        )
        if conn.is_connected():
            return conn
    except mysql.connector.Error as e:
        print(f"❌ Error al conectar a MySQL: {e}")
        return None

if __name__ == "__main__":
    test = get_connection()
    if test:
        print("✅ ¡CONECTADO!")
        test.close()