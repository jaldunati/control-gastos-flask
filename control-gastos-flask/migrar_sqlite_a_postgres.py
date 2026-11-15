
import os
import sqlite3
import psycopg2

# Base de datos SQLite original
RUTA_SQLITE = os.path.join(
    os.path.dirname(__file__),
    "gastos.db"
)

# Conexión PostgreSQL de Neon
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "No se encontró la variable de entorno DATABASE_URL"
    )

if not os.path.exists(RUTA_SQLITE):
    raise FileNotFoundError(
        f"No se encontró la base SQLite: {RUTA_SQLITE}"
    )

print("Conectando con SQLite...")

sqlite = sqlite3.connect(RUTA_SQLITE)
sqlite.row_factory = sqlite3.Row

usuarios = sqlite.execute(
    "SELECT * FROM usuarios ORDER BY id"
).fetchall()

gastos = sqlite.execute(
    "SELECT * FROM gastos ORDER BY id"
).fetchall()

print(f"Usuarios encontrados: {len(usuarios)}")
print(f"Gastos encontrados: {len(gastos)}")

try:
    print("Conectando con Neon PostgreSQL...")

    postgres = psycopg2.connect(DATABASE_URL)

    with postgres:
        with postgres.cursor() as cursor:

            # Crear tablas si todavía no existen
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id BIGSERIAL PRIMARY KEY,
                    usuario TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gastos (
                    id BIGSERIAL PRIMARY KEY,
                    fecha TEXT NOT NULL,
                    descripcion TEXT NOT NULL,
                    monto DOUBLE PRECISION NOT NULL
                        CHECK (monto > 0)
                )
            """)

            # Migrar usuarios sin sobrescribir registros existentes
            for usuario in usuarios:
                cursor.execute(
                    "SELECT usuario, password_hash "
                    "FROM usuarios WHERE id = %s",
                    (usuario["id"],)
                )
                existente = cursor.fetchone()

                datos = (
                    usuario["usuario"],
                    usuario["password_hash"]
                )

                if existente is None:
                    cursor.execute("""
                        INSERT INTO usuarios
                        (id, usuario, password_hash)
                        VALUES (%s, %s, %s)
                    """, (
                        usuario["id"],
                        usuario["usuario"],
                        usuario["password_hash"]
                    ))
                elif tuple(existente) != datos:
                    raise ValueError(
                        f"Conflicto en usuario ID {usuario['id']}"
                    )

            # Migrar gastos sin sobrescribir registros existentes
            for gasto in gastos:
                cursor.execute(
                    "SELECT fecha, descripcion, monto "
                    "FROM gastos WHERE id = %s",
                    (gasto["id"],)
                )
                existente = cursor.fetchone()

                datos = (
                    gasto["fecha"],
                    gasto["descripcion"],
                    float(gasto["monto"])
                )

                if existente is None:
                    cursor.execute("""
                        INSERT INTO gastos
                        (id, fecha, descripcion, monto)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        gasto["id"],
                        gasto["fecha"],
                        gasto["descripcion"],
                        gasto["monto"]
                    ))
                elif (
                    existente[0] != datos[0]
                    or existente[1] != datos[1]
                    or float(existente[2]) != datos[2]
                ):
                    raise ValueError(
                        f"Conflicto en gasto ID {gasto['id']}"
                    )

            # Actualizar secuencias de IDs
            for tabla in ("usuarios", "gastos"):
                cursor.execute("""
                    SELECT setval(
                        pg_get_serial_sequence(%s, 'id'),
                        COALESCE(
                            (SELECT MAX(id) FROM
                             (SELECT id FROM usuarios
                              WHERE %s = 'usuarios'
                              UNION ALL
                              SELECT id FROM gastos
                              WHERE %s = 'gastos') AS datos),
                            1
                        ),
                        TRUE
                    )
                """, (tabla, tabla, tabla))

            print("Migración completada correctamente.")

    postgres.close()

finally:
    sqlite.close()

print("Base SQLite original conservada.")
