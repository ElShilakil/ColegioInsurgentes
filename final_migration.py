from app import app
from extensions import db
from sqlalchemy import text

def migrate():
    with app.app_context():
        print("Iniciando migración estructural...")
        try:
            # 1. Eliminar dependencias y tablas antiguas
            db.session.execute(text("ALTER TABLE activities DROP CONSTRAINT IF EXISTS activities_period_id_fkey"))
            db.session.execute(text("DROP TABLE IF EXISTS school_periods CASCADE"))
            db.session.execute(text("DROP TABLE IF EXISTS ciclos_escolares CASCADE"))
            
            # 2. Crear nuevas tablas (db.create_all lo hará basado en los nuevos modelos)
            db.create_all()
            print("Tablas creados con el nuevo esquema.")
            
            # 3. Asegurar que activities tiene la columna trimestre_id
            # Si ya existe por db.create_all, el try lo manejará
            try:
                db.session.execute(text("ALTER TABLE activities ADD COLUMN trimestre_id INTEGER REFERENCES trimestres(id)"))
            except Exception:
                print("Columna trimestre_id ya existe.")
            
            db.session.commit()
            print("Migración finalizada con éxito.")
        except Exception as e:
            db.session.rollback()
            print(f"Error en migración: {e}")

if __name__ == "__main__":
    migrate()
