from flask import Flask, render_template, request, jsonify, send_file, session
from config import Config
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from models import db, Novedad, Idea, Usuario
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import cloudinary
import cloudinary.uploader
import os
import io
import urllib.parse

print("Bananin acordate que la base de datos está en Railway y las fotos en Cloudinary")

def crear_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    with app.app_context():
        db.create_all()
        
        if not Usuario.query.filter_by(username='admin').first():
            admin = Usuario(username='admin', rol='admin')
            admin.set_password('cecvencedor')
            db.session.add(admin)
            db.session.commit()

    with app.app_context():
        db.create_all()
    app.secret_key = os.environ.get("SECRET_KEY", "una_clave_muy_secreta_y_unica")
    # Configurar Cloudinary
    cloudinary.config(
        cloud_name='dvu5ol9pi',
        api_key='756223218919971',
        api_secret='T7L1BOjlnGK7X7gDOSQvCCdaWqw'
    )

    
    def get_conn():
        DATABASE_URL = os.environ.get("SQLALCHEMY_DATABASE_URI")  # Railway normalmente lo exporta
        if not DATABASE_URL:
            raise Exception("No se encontró SQLALCHEMY_DATABASE_URI en las variables de entorno")
    
        result = urllib.parse.urlparse(DATABASE_URL)
    
        return psycopg2.connect(
            dbname=result.path[1:],      # eliminar la /
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port,
            sslmode="require"            # casi siempre Railway necesita SSL
        )

    @app.route("/db/tables", methods=["GET"])
    def listar_tablas():
        conn=get_conn(); cur=conn.cursor()
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        tablas=[r[0] for r in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify({"tablas":tablas})
    
    @app.route("/db/table/<nombre>", methods=["GET"])
    def ver_tabla(nombre):
        conn=get_conn(); cur=conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT * FROM {nombre} LIMIT 50")
        registros=cur.fetchall()
        cur.close(); conn.close()
        return jsonify({"registros":registros})
    
    @app.route("/db/tables", methods=["POST"])
    def crear_tabla():
        nombre=request.form["nombre"]
        columnas=request.form["columnas"]
        conn=get_conn(); cur=conn.cursor()
        cur.execute(f"CREATE TABLE {nombre} ({columnas})")
        conn.commit()
        cur.close(); conn.close()
        return jsonify({"msg":"Tabla creada"})
    
    # Borrar un registro por ID
    @app.route("/db/table/<nombre>/row/<int:row_id>", methods=["DELETE"])
    def borrar_fila(nombre, row_id):
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(sql.SQL("DELETE FROM {} WHERE id = %s").format(sql.Identifier(nombre)), [row_id])
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"msg": f"Fila {row_id} borrada de {nombre}"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # Borrar todos los registros de una tabla
    @app.route("/db/table/<nombre>/rows", methods=["DELETE"])
    def borrar_todas_filas(nombre):
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(nombre)))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"msg": f"Todos los registros de {nombre} borrados"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    # ------------------- RUTAS -------------------
    @app.route("/")
    def index():
        user_agent = request.headers.get('User-Agent', '').lower()
        mobile_keywords = ['iphone', 'android', 'blackberry', 'windows phone', 'opera mini', 'mobile']
        template = 'index_movil.html' if any(k in user_agent for k in mobile_keywords) else 'index.html'
        return render_template(template)
    
    @app.route("/movil")
    def index_movil():
        return render_template("index_movil.html")
    
    @app.route("/novedades", methods=["POST"])
    def guardar_novedad():
        asunto = request.form.get("asunto")
        mensaje = request.form.get("mensaje")
        foto = request.files.get("foto")
        imagen_url = ""

        if foto:
            resultado = cloudinary.uploader.upload(foto)
            imagen_url = resultado.get("secure_url", "")

        if asunto and mensaje:
            nueva = Novedad(asunto=asunto, mensaje=mensaje, imagen=imagen_url)
            db.session.add(nueva)
            db.session.commit()

        return "OK"

    @app.route("/ver-novedades")
    def ver_novedades():
        novedades = Novedad.query.order_by(Novedad.id.desc()).all()
        return jsonify({
            "novedades": [
                {"id": n.id, "asunto": n.asunto, "mensaje": n.mensaje, "imagen": n.imagen}
                for n in novedades
            ]
        })
    from flask import session, redirect, url_for

    @app.route("/admin")
    def admin_panel():
        # Solo permitir acceso si usuario logueado y rol admin
        if session.get("user_role") != "admin":
            return redirect(url_for("index"))
        return render_template("admin.html")

    @app.route("/borrar-novedad/<int:id>", methods=["POST"])
    def borrar_novedad(id):
        novedad = Novedad.query.get(id)
        if novedad:
            db.session.delete(novedad)
            db.session.commit()
            return "OK"
        return "Novedad no encontrada", 404

    @app.route("/borrar-todas-novedades", methods=["POST"])
    def borrar_todas_novedades():
        try:
            num = Novedad.query.delete()
            db.session.commit()
            return jsonify({"ok": True, "borradas": num})
        except Exception as e:
            db.session.rollback()
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/ideas", methods=["POST"])
    def guardar_idea():
        nombre = request.form.get("nombre")
        texto = request.form.get("idea")

        if nombre and texto:
            nueva = Idea(nombre=nombre, texto=texto)
            db.session.add(nueva)
            db.session.commit()

        return "OK"


    @app.route("/crear-usuario", methods=["POST"])
    def crear_usuario():
        if session.get("user_role") != "admin":
            return jsonify({"msg": "No autorizado"}), 403
    
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role", "normal")
    
        if not username or not password:
            return jsonify({"msg": "Usuario y contraseña son obligatorios"}), 400
    
        if Usuario.query.filter_by(username=username).first():
            return jsonify({"msg": "El usuario ya existe"}), 400
    
        nuevo = Usuario(username=username, rol=role)
        nuevo.set_password(password)
        db.session.add(nuevo)
        db.session.commit()
    
        return jsonify({"msg": f"Usuario '{username}' creado con éxito"})

    @app.route("/login", methods=["POST"])
    def login():
        user = request.json.get("usuario")
        password = request.json.get("contrasena")
    
        usuario = Usuario.query.filter_by(username=user).first()
        if usuario and usuario.check_password(password):
            session["user_role"] = usuario.rol
            session["username"] = usuario.username
            return jsonify({"ok": True})
        
        return jsonify({"ok": False}), 401

    
    @app.route("/descargar-ideas")
    def descargar_ideas():
        ideas = Idea.query.order_by(Idea.id.asc()).all()

        contenido = ""
        for i in ideas:
            contenido += f"Nombre: {i.nombre}\nIdea: {i.texto}\n\n"

        # Generar archivo en memoria
        archivo = io.BytesIO()
        archivo.write(contenido.encode("utf-8"))
        archivo.seek(0)

        return send_file(
            archivo,
            as_attachment=True,
            download_name="ideas.txt",
            mimetype="text/plain"
        )

    return app

if __name__ == "__main__":
    crear_app().run(host="0.0.0.0", port=5000)






