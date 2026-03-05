import mysql.connector
import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '../.env'))

def get_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=3306,
            use_pure=True 
        )
        if conn.is_connected():
            return conn
    except mysql.connector.Error as e:
        print(f"Error al conectar a MySQL: {e}")
        return None

if __name__ == "__main__":
    test = get_connection()
    if test:
        print("¡CONECTADO! Ya podemos seguir, Joaquin.")
        test.close()