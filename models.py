from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Perfil configurável
    nome_completo = db.Column(db.String(200))
    bio = db.Column(db.Text)
    foto_perfil = db.Column(db.String(255), default='default.jpg')
    banner = db.Column(db.String(255), default='default_banner.jpg')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relacionamentos
    livros = db.relationship('Livro', backref='usuario', lazy='dynamic', cascade='all, delete-orphan')
    sessoes = db.relationship('SessaoLeitura', backref='usuario', lazy='dynamic', cascade='all, delete-orphan')
    mensagens = db.relationship('Mensagem', backref='autor', lazy='dynamic', cascade='all, delete-orphan')
    mensagens_privadas_enviadas = db.relationship('MensagemPrivada',
                                                  foreign_keys='MensagemPrivada.remetente_id',
                                                  backref='remetente', lazy='dynamic')
    mensagens_privadas_recebidas = db.relationship('MensagemPrivada',
                                                   foreign_keys='MensagemPrivada.destinatario_id',
                                                   backref='destinatario', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def estatisticas_periodo(self, dias=7):
        """Retorna estatísticas de leitura para um período"""
        data_inicio = datetime.utcnow() - timedelta(days=dias)

        sessoes = self.sessoes.filter(SessaoLeitura.inicio >= data_inicio).all()

        total_minutos = sum(s.duracao_minutos or 0 for s in sessoes)
        total_paginas = sum(s.paginas_lidas for s in sessoes)

        return {
            'total_minutos': total_minutos,
            'total_paginas': total_paginas,
            'total_sessoes': len(sessoes),
            'media_minutos_dia': round(total_minutos / dias, 1) if dias > 0 else 0,
            'media_paginas_dia': round(total_paginas / dias, 1) if dias > 0 else 0
        }

    def __repr__(self):
        return f'<User {self.username}>'


class Livro(db.Model):
    __tablename__ = 'livros'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(300), nullable=False)
    autor = db.Column(db.String(200))
    isbn = db.Column(db.String(20))
    total_paginas = db.Column(db.Integer, nullable=False)
    capa_url = db.Column(db.String(500))
    google_books_id = db.Column(db.String(100))

    # Status
    status = db.Column(db.String(20), default='lendo')
    pagina_atual = db.Column(db.Integer, default=0)

    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    iniciado_em = db.Column(db.DateTime)
    concluido_em = db.Column(db.DateTime)

    # Relacionamentos
    registros = db.relationship('RegistroLeitura', backref='livro', lazy='dynamic',
                                cascade='all, delete-orphan', order_by='RegistroLeitura.data')
    sessoes = db.relationship('SessaoLeitura', backref='livro', lazy='dynamic',
                              cascade='all, delete-orphan', order_by='SessaoLeitura.inicio.desc()')

    @property
    def progresso_percentual(self):
        if self.total_paginas == 0:
            return 0
        return round((self.pagina_atual / self.total_paginas) * 100, 1)

    @property
    def total_tempo_leitura(self):
        return sum(sessao.duracao_minutos or 0 for sessao in self.sessoes)

    @property
    def media_tempo_sessao(self):
        sessoes = [s for s in self.sessoes if s.duracao_minutos]
        if not sessoes:
            return 0
        return round(sum(s.duracao_minutos for s in sessoes) / len(sessoes), 1)

    def __repr__(self):
        return f'<Livro {self.titulo}>'


class RegistroLeitura(db.Model):
    __tablename__ = 'registros_leitura'

    id = db.Column(db.Integer, primary_key=True)
    livro_id = db.Column(db.Integer, db.ForeignKey('livros.id'), nullable=False)
    data = db.Column(db.Date, nullable=False, index=True)
    pagina_inicial = db.Column(db.Integer, nullable=False)
    pagina_final = db.Column(db.Integer, nullable=False)
    sessao_id = db.Column(db.Integer, db.ForeignKey('sessoes_leitura.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def paginas_lidas(self):
        return self.pagina_final - self.pagina_inicial + 1

    def __repr__(self):
        return f'<Registro {self.livro.titulo} - {self.data}>'


class SessaoLeitura(db.Model):
    __tablename__ = 'sessoes_leitura'

    id = db.Column(db.Integer, primary_key=True)
    livro_id = db.Column(db.Integer, db.ForeignKey('livros.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    inicio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fim = db.Column(db.DateTime)
    duracao_minutos = db.Column(db.Integer)

    pagina_inicial = db.Column(db.Integer)
    pagina_final = db.Column(db.Integer)

    @property
    def paginas_lidas(self):
        if self.pagina_inicial and self.pagina_final:
            return self.pagina_final - self.pagina_inicial + 1
        return 0

    @property
    def duracao_formatada(self):
        if not self.duracao_minutos:
            return '0 min'
        horas = self.duracao_minutos // 60
        mins = self.duracao_minutos % 60
        if horas > 0:
            return f'{horas}h {mins}min'
        return f'{mins}min'

    def __repr__(self):
        return f'<Sessao {self.livro.titulo} - {self.duracao_minutos}min>'


class Mensagem(db.Model):
    __tablename__ = 'mensagens'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'usuario': self.autor.username,
            'usuario_id': self.usuario_id,
            'foto_perfil': self.autor.foto_perfil,
            'conteudo': self.conteudo,
            'timestamp': self.timestamp.strftime('%H:%M')
        }

    def __repr__(self):
        return f'<Mensagem {self.autor.username}>'


class MensagemPrivada(db.Model):
    __tablename__ = 'mensagens_privadas'

    id = db.Column(db.Integer, primary_key=True)
    remetente_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    lida = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'remetente': self.remetente.username,
            'remetente_id': self.remetente_id,
            'destinatario': self.destinatario.username,
            'destinatario_id': self.destinatario_id,
            'foto_perfil_remetente': self.remetente.foto_perfil,
            'conteudo': self.conteudo,
            'lida': self.lida,
            'timestamp': self.timestamp.strftime('%H:%M - %d/%m/%Y')
        }

    def __repr__(self):
        return f'<MensagemPrivada {self.remetente.username} -> {self.destinatario.username}>'
