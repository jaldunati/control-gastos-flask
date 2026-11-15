import os, sqlite3
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-practica-cambiar-en-produccion")
DB = os.path.join(os.path.dirname(__file__), "gastos.db")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    conn = g.pop("db", None)
    if conn: conn.close()

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS usuarios(id INTEGER PRIMARY KEY, usuario TEXT UNIQUE, password_hash TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS gastos(id INTEGER PRIMARY KEY, fecha TEXT NOT NULL, descripcion TEXT NOT NULL, monto REAL NOT NULL CHECK(monto > 0))")
    if not conn.execute("SELECT id FROM usuarios WHERE usuario='admin'").fetchone():
        conn.execute("INSERT INTO usuarios(usuario,password_hash) VALUES(?,?)", ("admin", generate_password_hash("123")))
    conn.commit(); conn.close()

def requiere_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session: return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u=request.form.get("usuario","").strip(); p=request.form.get("clave","")
        user=db().execute("SELECT * FROM usuarios WHERE usuario=?", (u,)).fetchone()
        if user and check_password_hash(user["password_hash"],p):
            session.clear(); session["usuario_id"]=user["id"]; session["usuario"]=user["usuario"]
            return redirect(url_for("inicio"))
        flash("Usuario o contraseña incorrectos.","error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/")
@requiere_login
def inicio():
    conn=db()
    total=conn.execute("SELECT COUNT(*) FROM gastos").fetchone()[0]
    suma=conn.execute("SELECT COALESCE(SUM(monto),0) FROM gastos").fetchone()[0]
    recientes=conn.execute("SELECT * FROM gastos ORDER BY fecha DESC,id DESC LIMIT 5").fetchall()
    return render_template("index.html", total=total, suma=suma, recientes=recientes)

@app.route("/gastos")
@requiere_login
def gastos():
    rows=db().execute("SELECT * FROM gastos ORDER BY fecha DESC,id DESC").fetchall()
    return render_template("gastos.html", gastos=rows)

@app.route("/gastos/nuevo", methods=["GET","POST"])
@requiere_login
def nuevo():
    if request.method=="POST":
        fecha=request.form.get("fecha","").strip()
        descripcion=request.form.get("descripcion","").strip()
        try: monto=float(request.form.get("monto",""))
        except ValueError: monto=0
        try: date.fromisoformat(fecha)
        except ValueError: fecha=""
        if not fecha or not descripcion or monto<=0:
            flash("Completa los campos e ingresa una fecha válida y un monto mayor que cero.","error")
            return render_template("form.html", gasto=None, hoy=date.today().isoformat()),400
        db().execute("INSERT INTO gastos(fecha,descripcion,monto) VALUES(?,?,?)",(fecha,descripcion,monto)); db().commit()
        flash("Gasto registrado correctamente.","success"); return redirect(url_for("gastos"))
    return render_template("form.html", gasto=None, hoy=date.today().isoformat())

@app.route("/gastos/editar/<int:id>", methods=["GET","POST"])
@requiere_login
def editar(id):
    conn=db(); gasto=conn.execute("SELECT * FROM gastos WHERE id=?",(id,)).fetchone()
    if not gasto: return render_template("404.html"),404
    if request.method=="POST":
        fecha=request.form.get("fecha","").strip(); desc=request.form.get("descripcion","").strip()
        try: monto=float(request.form.get("monto","")); date.fromisoformat(fecha)
        except ValueError: monto=0
        if not fecha or not desc or monto<=0:
            flash("Verifica los datos ingresados.","error"); return render_template("form.html",gasto=gasto,hoy=date.today().isoformat()),400
        conn.execute("UPDATE gastos SET fecha=?,descripcion=?,monto=? WHERE id=?",(fecha,desc,monto,id)); conn.commit()
        flash("Gasto actualizado.","success"); return redirect(url_for("gastos"))
    return render_template("form.html",gasto=gasto,hoy=date.today().isoformat())

@app.route("/gastos/eliminar/<int:id>",methods=["POST"])
@requiere_login
def eliminar(id):
    db().execute("DELETE FROM gastos WHERE id=?",(id,)); db().commit()
    flash("Gasto eliminado.","success"); return redirect(url_for("gastos"))

@app.route("/reporte")
@requiere_login
def reporte():
    desde=request.args.get("desde","").strip(); hasta=request.args.get("hasta","").strip()
    sql="SELECT * FROM gastos WHERE 1=1"; args=[]
    if desde: sql+=" AND fecha>=?"; args.append(desde)
    if hasta: sql+=" AND fecha<=?"; args.append(hasta)
    rows=db().execute(sql+" ORDER BY fecha DESC,id DESC",args).fetchall()
    return render_template("reporte.html",gastos=rows,total=sum(r["monto"] for r in rows),desde=desde,hasta=hasta)

@app.errorhandler(404)
def no_encontrado(error): return render_template("404.html"),404

if __name__=="__main__":
    init_db()
    app.run(debug=True)
