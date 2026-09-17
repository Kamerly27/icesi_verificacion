import os
import sqlite3
import secrets
import qrcode

from datetime import datetime
from flask import Flask, render_template, request, url_for, flash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DB_PATH = os.path.join(BASE_DIR, "instance", "icesi.db")
QR_DIR = os.path.join(BASE_DIR, "static", "qr")

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32)
)

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(QR_DIR, exist_ok=True)


# =========================================================
# BASE DE DATOS
# =========================================================

def db():
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    return conexion


def init_db():

    conexion = db()

    conexion.execute("""
        CREATE TABLE IF NOT EXISTS graduados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            fecha_grado TEXT,
            tipo_id TEXT,
            documento TEXT UNIQUE NOT NULL,
            periodo_ingreso TEXT,
            titulo TEXT,
            numero_diploma TEXT,
            ciudad_documento TEXT,
            periodo_final TEXT,
            acta_grado TEXT,
            certificado_archivo TEXT,
            programa TEXT,
            estado TEXT
        )
    """)

    conexion.execute("""
        CREATE TABLE IF NOT EXISTS consultas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            criterio TEXT NOT NULL,
            resultado TEXT NOT NULL,
            fecha_hora TEXT NOT NULL,
            ip TEXT
        )
    """)

    # Si la base de datos ya existía, agrega las columnas nuevas
    columnas = [
        fila["name"]
        for fila in conexion.execute(
            "PRAGMA table_info(graduados)"
        ).fetchall()
    ]

    if "programa" not in columnas:
        conexion.execute(
            "ALTER TABLE graduados ADD COLUMN programa TEXT"
        )

    if "estado" not in columnas:
        conexion.execute(
            "ALTER TABLE graduados ADD COLUMN estado TEXT"
        )

    conexion.commit()
    conexion.close()


# =========================================================
# CÓDIGO DE VERIFICACIÓN
# =========================================================

def generar_codigo(conexion, documento):

    base = "ICESI-" + "".join(
        caracter
        for caracter in documento.upper()
        if caracter.isalnum()
    )

    codigo = base
    numero = 2

    while conexion.execute(
        "SELECT id FROM graduados WHERE codigo=?",
        (codigo,)
    ).fetchone():

        codigo = f"{base}-{numero}"
        numero += 1

    return codigo


# =========================================================
# CÓDIGO QR
# =========================================================

def generar_qr(codigo):

    enlace = (
        request.host_url.rstrip("/")
        + url_for(
            "index",
            criterio=codigo
        )
    )

    archivo = f"{codigo}.png"

    ruta = os.path.join(
        QR_DIR,
        archivo
    )

    imagen = qrcode.make(enlace)
    imagen.save(ruta)

    return archivo


# =========================================================
# VERIFICACIÓN PÚBLICA
# =========================================================

@app.route("/", methods=["GET", "POST"])
def index():

    graduado = None
    buscado = False

    if request.method == "POST":

        criterio = request.form.get(
            "criterio",
            ""
        ).strip()

    else:

        criterio = request.args.get(
            "criterio",
            ""
        ).strip()


    if criterio:

        buscado = True

        conexion = db()

        graduado = conexion.execute(
            """
            SELECT
                id,
                codigo,
                nombre,
                documento,
                programa,
                titulo,
                periodo_ingreso,
                fecha_grado,
                estado
            FROM graduados
            WHERE documento=?
               OR codigo=?
            LIMIT 1
            """,
            (
                criterio,
                criterio.upper()
            )
        ).fetchone()


        conexion.execute(
            """
            INSERT INTO consultas
            (
                criterio,
                resultado,
                fecha_hora,
                ip
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                criterio,
                "ENCONTRADO"
                if graduado
                else "NO_ENCONTRADO",

                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

                request.headers.get(
                    "X-Forwarded-For",
                    request.remote_addr
                )
            )
        )

        conexion.commit()
        conexion.close()


    return render_template(
        "index.html",
        graduado=graduado,
        buscado=buscado,
        criterio=criterio
    )


# =========================================================
# REGISTRO DE EGRESADO
# =========================================================

@app.route(
    "/registro",
    methods=["GET", "POST"]
)
def registro():

    if request.method == "POST":

        nombres = request.form.get(
            "nombres",
            ""
        ).strip()

        apellidos = request.form.get(
            "apellidos",
            ""
        ).strip()

        documento = request.form.get(
            "documento",
            ""
        ).strip()

        programa = request.form.get(
            "programa",
            ""
        ).strip()

        titulo = request.form.get(
            "titulo",
            ""
        ).strip()

        periodo_ingreso = request.form.get(
            "periodo_ingreso",
            ""
        ).strip()

        fecha_grado = request.form.get(
            "fecha_grado",
            ""
        ).strip()

        acta = request.form.get(
            "acta",
            ""
        ).strip()

        diploma = request.form.get(
            "diploma",
            ""
        ).strip()

        estado = request.form.get(
            "estado",
            "GRADUADO"
        ).strip()


        if not all([
            nombres,
            apellidos,
            documento,
            programa,
            titulo,
            periodo_ingreso,
            fecha_grado,
            acta,
            diploma
        ]):

            flash(
                "Complete todos los campos."
            )

            return render_template(
                "registro.html"
            )


        conexion = db()


        # Documento duplicado

        existe = conexion.execute(
            """
            SELECT id
            FROM graduados
            WHERE documento=?
            """,
            (documento,)
        ).fetchone()


        if existe:

            conexion.close()

            flash(
                "El documento ya está registrado."
            )

            return render_template(
                "registro.html"
            )


        # Código automático

        codigo = generar_codigo(
            conexion,
            documento
        )


        nombre = (
            nombres
            + " "
            + apellidos
        ).upper()


        # Guardar egresado

        conexion.execute(
            """
            INSERT INTO graduados
            (
                codigo,
                nombre,
                fecha_grado,
                tipo_id,
                documento,
                periodo_ingreso,
                titulo,
                numero_diploma,
                ciudad_documento,
                periodo_final,
                acta_grado,
                certificado_archivo,
                programa,
                estado
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                codigo,
                nombre,
                fecha_grado,
                "CC",
                documento,
                periodo_ingreso,
                titulo,
                diploma,
                "",
                "",
                acta,
                None,
                programa,
                estado.upper()
            )
        )


        conexion.commit()
        conexion.close()


        # Generar QR

        qr_archivo = generar_qr(
            codigo
        )


        # Mostrar resultado del registro

        return render_template(
            "registro.html",
            registrado=True,
            codigo=codigo,
            qr_archivo=qr_archivo,
            nombre=nombre
        )


    return render_template(
        "registro.html"
    )


# =========================================================
# INICIO
# =========================================================

init_db()


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=False
    )