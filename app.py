from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date
import os

from config import Config
from models import db, User, Livro, RegistroLeitura, SessaoLeitura, Mensagem, MensagemPrivada
from utils import save_upload_image, buscar_livros_google

app = Flask(__name__)
app.config.from_object(Config)

# Inicializar extensões
db.init_app(app)
socketio = SocketIO(
    app,
    async_mode=app.config['SOCKETIO_ASYNC_MODE'],
    cors_allowed_origins="*",
    manage_session=False
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Criar diretórios necessários
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ============= ROTAS DE AUTENTICAÇÃO =============

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        nome_completo = request.form.get('nome_completo', '')

        # Validações
        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado!', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Nome de usuário já existe!', 'error')
            return redirect(url_for('register'))

        user = User(username=username, email=email, nome_completo=nome_completo)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash('Conta criada com sucesso!', 'success')
        return redirect(url_for('login'))

    return render_template('login.html', action='register')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))

        flash('Email ou senha incorretos!', 'error')

    return render_template('login.html', action='login')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ============= ROTAS PRINCIPAIS =============

@app.route('/dashboard')
@login_required
def dashboard():
    livros = current_user.livros.order_by(Livro.created_at.desc()).all()

    # Estatísticas
    stats = {
        'semana': current_user.estatisticas_periodo(7),
        'mes': current_user.estatisticas_periodo(30),
        'ano': current_user.estatisticas_periodo(365)
    }

    return render_template('dashboard.html', livros=livros, stats=stats)


@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == 'POST':
        current_user.nome_completo = request.form.get('nome_completo', '')
        current_user.bio = request.form.get('bio', '')

        # Upload foto de perfil
        if 'foto_perfil' in request.files:
            file = request.files['foto_perfil']
            if file.filename:
                filename = save_upload_image(file, 'perfil')
                if filename:
                    current_user.foto_perfil = filename

        # Upload banner
        if 'banner' in request.files:
            file = request.files['banner']
            if file.filename:
                filename = save_upload_image(file, 'banner')
                if filename:
                    current_user.banner = filename

        db.session.commit()
        flash('Perfil atualizado!', 'success')
        return redirect(url_for('perfil'))

    return render_template('perfil.html')


# ============= API DE LIVROS =============

@app.route('/api/buscar-livros')
@login_required
def api_buscar_livros():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    livros = buscar_livros_google(query)
    return jsonify(livros)


@app.route('/api/adicionar-livro', methods=['POST'])
@login_required
def api_adicionar_livro():
    data = request.json or {}

    titulo = (data.get('titulo') or '').strip()
    if not titulo:
        return jsonify({'error': 'Título é obrigatório'}), 400

    try:
        total_paginas = int(data.get('paginas', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'Número de páginas inválido'}), 400
    if total_paginas <= 0:
        return jsonify({'error': 'Número de páginas deve ser maior que zero'}), 400

    livro = Livro(
        titulo=titulo,
        autor=data.get('autor', ''),
        isbn=data.get('isbn'),
        total_paginas=total_paginas,
        capa_url=data.get('capa_url', ''),
        google_books_id=data.get('google_id'),
        usuario_id=current_user.id,
        iniciado_em=datetime.utcnow()
    )

    db.session.add(livro)
    db.session.commit()

    return jsonify({'success': True, 'livro_id': livro.id})


@app.route('/api/registrar-leitura', methods=['POST'])
@login_required
def api_registrar_leitura():
    data = request.json or {}

    try:
        livro_id = int(data.get('livro_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'livro_id inválido'}), 400

    livro = Livro.query.get_or_404(livro_id)

    # Verificar permissão
    if livro.usuario_id != current_user.id:
        return jsonify({'error': 'Não autorizado'}), 403

    # Criar registro
    try:
        data_registro = datetime.strptime(data.get('data', ''), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return jsonify({'error': 'Data inválida. Use YYYY-MM-DD'}), 400

    try:
        pagina_inicial = int(data.get('pagina_inicial'))
        pagina_final = int(data.get('pagina_final'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Páginas devem ser números inteiros'}), 400

    if pagina_inicial < 1 or pagina_final < 1:
        return jsonify({'error': 'Páginas devem ser >= 1'}), 400
    if pagina_inicial > pagina_final:
        return jsonify({'error': 'Página inicial não pode ser maior que a final'}), 400
    if pagina_final > livro.total_paginas:
        return jsonify({'error': 'Página final excede o total de páginas do livro'}), 400

    registro = RegistroLeitura(
        livro_id=livro.id,
        data=data_registro,
        pagina_inicial=pagina_inicial,
        pagina_final=pagina_final,
        sessao_id=data.get('sessao_id')
    )

    db.session.add(registro)

    # Atualizar página atual do livro
    livro.pagina_atual = max(livro.pagina_atual or 0, pagina_final)
    if livro.pagina_atual > livro.total_paginas:
        livro.pagina_atual = livro.total_paginas

    # Verificar se concluiu
    if livro.pagina_atual >= livro.total_paginas:
        livro.status = 'concluido'
        livro.concluido_em = datetime.utcnow()

    db.session.commit()

    return jsonify({'success': True})


# ============= CRONÔMETRO E SESSÕES =============

@app.route('/api/iniciar-sessao', methods=['POST'])
@login_required
def api_iniciar_sessao():
    data = request.json or {}
    try:
        livro_id = int(data.get('livro_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'livro_id inválido'}), 400
    livro = Livro.query.get_or_404(livro_id)

    if livro.usuario_id != current_user.id:
        return jsonify({'error': 'Não autorizado'}), 403

    sessao = SessaoLeitura(
        livro_id=livro.id,
        usuario_id=current_user.id,
        inicio=datetime.utcnow(),
        pagina_inicial=livro.pagina_atual
    )

    db.session.add(sessao)
    db.session.commit()

    return jsonify({'success': True, 'sessao_id': sessao.id})


@app.route('/api/finalizar-sessao', methods=['POST'])
@login_required
def api_finalizar_sessao():
    data = request.json
    sessao = SessaoLeitura.query.get_or_404(data['sessao_id'])

    if sessao.usuario_id != current_user.id:
        return jsonify({'error': 'Não autorizado'}), 403

    sessao.fim = datetime.utcnow()
    try:
        pagina_final = int(data.get('pagina_final', sessao.pagina_inicial or 0))
    except (TypeError, ValueError):
        pagina_final = sessao.pagina_inicial or 0
    if pagina_final < (sessao.pagina_inicial or 0):
        pagina_final = sessao.pagina_inicial or 0
    if pagina_final > (sessao.livro.total_paginas or pagina_final):
        pagina_final = sessao.livro.total_paginas
    sessao.pagina_final = pagina_final

    # Calcular duração
    duracao = (sessao.fim - sessao.inicio).total_seconds() / 60
    sessao.duracao_minutos = int(duracao)

    # Criar registro automático
    if sessao.pagina_final and sessao.pagina_final > sessao.pagina_inicial:
        registro = RegistroLeitura(
            livro_id=sessao.livro_id,
            data=date.today(),
            pagina_inicial=sessao.pagina_inicial,
            pagina_final=sessao.pagina_final,
            sessao_id=sessao.id
        )
        db.session.add(registro)

        # Atualizar livro
        sessao.livro.pagina_atual = max(sessao.livro.pagina_atual, sessao.pagina_final)

    db.session.commit()

    return jsonify({'success': True, 'duracao_minutos': sessao.duracao_minutos})


@app.route('/api/historico-sessoes/<int:livro_id>')
@login_required
def api_historico_sessoes(livro_id):
    livro = Livro.query.get_or_404(livro_id)

    if livro.usuario_id != current_user.id:
        return jsonify({'error': 'Não autorizado'}), 403

    sessoes = [{
        'id': s.id,
        'inicio': s.inicio.strftime('%d/%m/%Y %H:%M'),
        'duracao_minutos': s.duracao_minutos,
        'paginas_lidas': s.paginas_lidas,
        'pagina_inicial': s.pagina_inicial,
        'pagina_final': s.pagina_final
    } for s in livro.sessoes.filter(SessaoLeitura.fim.isnot(None)).all()]

    return jsonify(sessoes)


# ============= CHAT EM TEMPO REAL COM SOCKETIO =============

@app.route('/chat')
@login_required
def chat():
    usuarios = User.query.filter(User.id != current_user.id).all()
    mensagens_recentes = Mensagem.query.order_by(Mensagem.timestamp.desc()).limit(50).all()
    mensagens_recentes.reverse()

    return render_template('chat.html', usuarios=usuarios, mensagens=mensagens_recentes)


@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        emit('usuario_conectado', {
            'usuario': current_user.username,
            'foto_perfil': current_user.foto_perfil
        }, broadcast=True)


@socketio.on('enviar_mensagem')
def handle_mensagem(data):
    if not current_user.is_authenticated:
        return

    mensagem = Mensagem(
        usuario_id=current_user.id,
        conteudo=data['conteudo']
    )

    db.session.add(mensagem)
    db.session.commit()

    emit('nova_mensagem', mensagem.to_dict(), broadcast=True)


@socketio.on('entrar_chat_privado')
def handle_entrar_chat_privado(data):
    room = f"chat_{min(current_user.id, data['usuario_id'])}_{max(current_user.id, data['usuario_id'])}"
    join_room(room)

    # Carregar mensagens anteriores
    mensagens = MensagemPrivada.query.filter(
        ((MensagemPrivada.remetente_id == current_user.id) &
         (MensagemPrivada.destinatario_id == data['usuario_id'])) |
        ((MensagemPrivada.remetente_id == data['usuario_id']) &
         (MensagemPrivada.destinatario_id == current_user.id))
    ).order_by(MensagemPrivada.timestamp).limit(50).all()

    emit('historico_mensagens', [m.to_dict() for m in mensagens])


@socketio.on('enviar_mensagem_privada')
def handle_mensagem_privada(data):
    if not current_user.is_authenticated:
        return

    mensagem = MensagemPrivada(
        remetente_id=current_user.id,
        destinatario_id=data['destinatario_id'],
        conteudo=data['conteudo']
    )

    db.session.add(mensagem)
    db.session.commit()

    room = f"chat_{min(current_user.id, data['destinatario_id'])}_{max(current_user.id, data['destinatario_id'])}"
    emit('nova_mensagem_privada', mensagem.to_dict(), room=room)


# ============= INICIALIZAÇÃO =============

@app.cli.command()
def init_db():
    """Inicializa o banco de dados"""
    db.create_all()
    print("Banco de dados criado!")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Para desenvolvimento local
    if os.environ.get('FLASK_ENV') != 'production':
        socketio.run(app, debug=True, host='0.0.0.0', port=5000)
    else:
        # Para produção no Render
        socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
