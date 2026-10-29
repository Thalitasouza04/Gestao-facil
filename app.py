import os
import sqlite3
from functools import wraps
from decimal import Decimal, InvalidOperation
from flask import Flask, g, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-antes-de-publicar")
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(app.instance_path, "gestao_facil.db"))
os.makedirs(os.path.dirname(DATABASE), exist_ok=True)

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS usuario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        senha_hash TEXT NOT NULL,
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS produto (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
        nome TEXT NOT NULL,
        descricao TEXT DEFAULT '',
        preco_centavos INTEGER NOT NULL CHECK(preco_centavos >= 0),
        estoque INTEGER NOT NULL DEFAULT 0 CHECK(estoque >= 0),
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS cliente (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
        nome TEXT NOT NULL,
        email TEXT DEFAULT '',
        telefone TEXT DEFAULT '',
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS venda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
        cliente_id INTEGER REFERENCES cliente(id) ON DELETE SET NULL,
        total_centavos INTEGER NOT NULL CHECK(total_centavos >= 0),
        status TEXT NOT NULL DEFAULT 'concluida',
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS item_venda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        venda_id INTEGER NOT NULL REFERENCES venda(id) ON DELETE CASCADE,
        produto_id INTEGER REFERENCES produto(id) ON DELETE SET NULL,
        nome_produto TEXT NOT NULL,
        quantidade INTEGER NOT NULL CHECK(quantidade > 0),
        preco_unitario_centavos INTEGER NOT NULL CHECK(preco_unitario_centavos >= 0),
        subtotal_centavos INTEGER NOT NULL CHECK(subtotal_centavos >= 0)
    );
    CREATE INDEX IF NOT EXISTS idx_produto_usuario ON produto(usuario_id);
    CREATE INDEX IF NOT EXISTS idx_cliente_usuario ON cliente(usuario_id);
    CREATE INDEX IF NOT EXISTS idx_venda_usuario ON venda(usuario_id);
    """)
    db.commit()

@app.before_request
def ensure_db():
    init_db()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def money(cents):
    return f"R$ {cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

@app.context_processor
def inject_helpers():
    return {"money": money}

@app.route("/")
def index():
    if session.get("usuario_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        if not nome or not email or len(senha) < 8:
            flash("Preencha todos os campos. A senha deve ter pelo menos 8 caracteres.", "erro")
            return render_template("cadastro.html")
        db = get_db()
        try:
            db.execute("INSERT INTO usuario(nome,email,senha_hash) VALUES(?,?,?)",
                       (nome, email, generate_password_hash(senha)))
            db.commit()
        except sqlite3.IntegrityError:
            flash("Este e-mail já está cadastrado.", "erro")
            return render_template("cadastro.html")
        flash("Conta criada! Entre com seu e-mail e senha.", "sucesso")
        return redirect(url_for("login"))
    return render_template("cadastro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        user = get_db().execute("SELECT * FROM usuario WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["senha_hash"], senha):
            session.clear()
            session["usuario_id"] = user["id"]
            session["usuario_nome"] = user["nome"]
            return redirect(url_for("dashboard"))
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("login.html")

@app.route("/sair")
def sair():
    session.clear()
    flash("Você saiu do sistema.", "sucesso")
    return redirect(url_for("login"))

@app.route("/painel")
@login_required
def dashboard():
    db, uid = get_db(), session["usuario_id"]
    produtos = db.execute("SELECT COUNT(*) n FROM produto WHERE usuario_id=?", (uid,)).fetchone()["n"]
    clientes = db.execute("SELECT COUNT(*) n FROM cliente WHERE usuario_id=?", (uid,)).fetchone()["n"]
    vendas = db.execute("SELECT COUNT(*) n FROM venda WHERE usuario_id=? AND status='concluida'", (uid,)).fetchone()["n"]
    receita = db.execute("SELECT COALESCE(SUM(total_centavos),0) n FROM venda WHERE usuario_id=? AND status='concluida'", (uid,)).fetchone()["n"]
    estoque_baixo = db.execute("SELECT * FROM produto WHERE usuario_id=? AND estoque <= 5 ORDER BY estoque, nome LIMIT 5", (uid,)).fetchall()
    ultimas = db.execute("SELECT v.*, c.nome cliente_nome FROM venda v LEFT JOIN cliente c ON c.id=v.cliente_id WHERE v.usuario_id=? ORDER BY v.id DESC LIMIT 5", (uid,)).fetchall()
    return render_template("dashboard.html", produtos=produtos, clientes=clientes, vendas=vendas,
                           receita=receita, estoque_baixo=estoque_baixo, ultimas=ultimas)

def parse_price(raw):
    raw = (raw or "").strip().replace("R$", "").replace(" ", "")
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        value = Decimal(raw)
        if value < 0:
            return None
        return int((value * 100).quantize(Decimal("1")))
    except (InvalidOperation, ValueError):
        return None

@app.route("/produtos", methods=["GET", "POST"])
@login_required
def produtos():
    db, uid = get_db(), session["usuario_id"]
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        descricao = request.form.get("descricao", "").strip()
        preco = parse_price(request.form.get("preco"))
        try:
            estoque = int(request.form.get("estoque", "0"))
        except ValueError:
            estoque = -1
        if not nome or preco is None or estoque < 0:
            flash("Informe nome, preço válido e estoque igual ou maior que zero.", "erro")
        else:
            db.execute("INSERT INTO produto(usuario_id,nome,descricao,preco_centavos,estoque) VALUES(?,?,?,?,?)",
                       (uid, nome, descricao, preco, estoque))
            db.commit()
            flash("Produto cadastrado.", "sucesso")
            return redirect(url_for("produtos"))
    rows = db.execute("SELECT * FROM produto WHERE usuario_id=? ORDER BY nome", (uid,)).fetchall()
    return render_template("produtos.html", produtos=rows)

@app.route("/produtos/<int:produto_id>/excluir", methods=["POST"])
@login_required
def excluir_produto(produto_id):
    db, uid = get_db(), session["usuario_id"]
    db.execute("DELETE FROM produto WHERE id=? AND usuario_id=?", (produto_id, uid))
    db.commit()
    flash("Produto excluído, se pertencia à sua conta.", "sucesso")
    return redirect(url_for("produtos"))

@app.route("/clientes", methods=["GET", "POST"])
@login_required
def clientes():
    db, uid = get_db(), session["usuario_id"]
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip()
        telefone = request.form.get("telefone", "").strip()
        if not nome:
            flash("O nome do cliente é obrigatório.", "erro")
        else:
            db.execute("INSERT INTO cliente(usuario_id,nome,email,telefone) VALUES(?,?,?,?)",
                       (uid, nome, email, telefone))
            db.commit()
            flash("Cliente cadastrado.", "sucesso")
            return redirect(url_for("clientes"))
    rows = db.execute("SELECT * FROM cliente WHERE usuario_id=? ORDER BY nome", (uid,)).fetchall()
    return render_template("clientes.html", clientes=rows)

@app.route("/clientes/<int:cliente_id>/excluir", methods=["POST"])
@login_required
def excluir_cliente(cliente_id):
    db = get_db()
    db.execute("DELETE FROM cliente WHERE id=? AND usuario_id=?", (cliente_id, session["usuario_id"]))
    db.commit()
    flash("Cliente excluído, se pertencia à sua conta.", "sucesso")
    return redirect(url_for("clientes"))

@app.route("/vendas", methods=["GET", "POST"])
@login_required
def vendas():
    db, uid = get_db(), session["usuario_id"]
    if request.method == "POST":
        try:
            produto_id = int(request.form.get("produto_id", ""))
            quantidade = int(request.form.get("quantidade", ""))
            cliente_raw = request.form.get("cliente_id", "").strip()
            cliente_id = int(cliente_raw) if cliente_raw else None
        except ValueError:
            flash("Selecione um produto e informe uma quantidade válida.", "erro")
            return redirect(url_for("vendas"))
        if quantidade <= 0:
            flash("A quantidade deve ser maior que zero.", "erro")
            return redirect(url_for("vendas"))
        produto = db.execute("SELECT * FROM produto WHERE id=? AND usuario_id=?", (produto_id, uid)).fetchone()
        if not produto:
            flash("Produto não encontrado na sua conta.", "erro")
            return redirect(url_for("vendas"))
        cliente = None
        if cliente_id is not None:
            cliente = db.execute("SELECT * FROM cliente WHERE id=? AND usuario_id=?", (cliente_id, uid)).fetchone()
            if not cliente:
                flash("Cliente inválido.", "erro")
                return redirect(url_for("vendas"))
        if produto["estoque"] < quantidade:
            flash("Estoque insuficiente para esta venda.", "erro")
            return redirect(url_for("vendas"))
        subtotal = produto["preco_centavos"] * quantidade
        try:
            db.execute("BEGIN")
            cur = db.execute("INSERT INTO venda(usuario_id,cliente_id,total_centavos) VALUES(?,?,?)",
                             (uid, cliente_id, subtotal))
            venda_id = cur.lastrowid
            db.execute("""INSERT INTO item_venda(venda_id,produto_id,nome_produto,quantidade,preco_unitario_centavos,subtotal_centavos)
                          VALUES(?,?,?,?,?,?)""",
                       (venda_id, produto["id"], produto["nome"], quantidade, produto["preco_centavos"], subtotal))
            db.execute("UPDATE produto SET estoque=estoque-? WHERE id=? AND usuario_id=? AND estoque>=?",
                       (quantidade, produto_id, uid, quantidade))
            db.commit()
            flash("Venda registrada e estoque atualizado.", "sucesso")
        except sqlite3.Error:
            db.rollback()
            flash("Não foi possível concluir a venda. Tente novamente.", "erro")
        return redirect(url_for("vendas"))
    products = db.execute("SELECT * FROM produto WHERE usuario_id=? ORDER BY nome", (uid,)).fetchall()
    clients = db.execute("SELECT * FROM cliente WHERE usuario_id=? ORDER BY nome", (uid,)).fetchall()
    sales = db.execute("""SELECT v.*, c.nome cliente_nome,
                          (SELECT GROUP_CONCAT(iv.nome_produto || ' × ' || iv.quantidade, ', ')
                           FROM item_venda iv WHERE iv.venda_id=v.id) itens
                          FROM venda v LEFT JOIN cliente c ON c.id=v.cliente_id
                          WHERE v.usuario_id=? ORDER BY v.id DESC LIMIT 50""", (uid,)).fetchall()
    return render_template("vendas.html", produtos=products, clientes=clients, vendas=sales)

@app.route("/vendas/<int:venda_id>/cancelar", methods=["POST"])
@login_required
def cancelar_venda(venda_id):
    db, uid = get_db(), session["usuario_id"]
    sale = db.execute("SELECT * FROM venda WHERE id=? AND usuario_id=? AND status='concluida'", (venda_id, uid)).fetchone()
    if not sale:
        flash("Venda não encontrada ou já cancelada.", "erro")
        return redirect(url_for("vendas"))
    items = db.execute("SELECT * FROM item_venda WHERE venda_id=?", (venda_id,)).fetchall()
    try:
        db.execute("BEGIN")
        for item in items:
            if item["produto_id"] is not None:
                db.execute("UPDATE produto SET estoque=estoque+? WHERE id=? AND usuario_id=?",
                           (item["quantidade"], item["produto_id"], uid))
        db.execute("UPDATE venda SET status='cancelada' WHERE id=? AND usuario_id=?", (venda_id, uid))
        db.commit()
        flash("Venda cancelada e estoque devolvido.", "sucesso")
    except sqlite3.Error:
        db.rollback()
        flash("Não foi possível cancelar a venda.", "erro")
    return redirect(url_for("vendas"))

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
