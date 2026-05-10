from app import app
from extensions import db
from sqlalchemy import text

def fix():
    with app.app_context():
        print("Intentando agregar columna assignment_id a la tabla activities...")
        try:
            # 1. Agregar la columna como nullable primero para no romper datos existentes
            db.session.execute(text("ALTER TABLE activities ADD COLUMN assignment_id INTEGER REFERENCES teacher_assignments(id)"))
            db.session.commit()
            print("Columna assignment_id agregada con éxito.")
            
            # 2. Intentar poblar assignment_id basado en teacher_id y el grupo actual de ese maestro
            # Esto es una mejor aproximación para no perder datos históricos
            print("Poblando assignment_id para registros existentes...")
            db.session.execute(text("""
                UPDATE activities a
                SET assignment_id = ta.id
                FROM teacher_assignments ta
                WHERE a.teacher_id = ta.teacher_id
                AND a.assignment_id IS NULL
            """))
            db.session.commit()
            print("Registros existentes actualizados.")
            
        except Exception as e:
            db.session.rollback()
            if "already exists" in str(e):
                print("La columna ya existe.")
            else:
                print(f"Error al reparar la base de datos: {e}")

if __name__ == '__main__':
    fix()
