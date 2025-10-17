import os
import requests
from werkzeug.utils import secure_filename
from PIL import Image
from flask import current_app


def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def save_upload_image(file, tipo='perfil'):
    """Salva imagem de perfil ou banner com redimensionamento de forma robusta."""
    if not file or not getattr(file, 'filename', ''):
        return None
    if not allowed_file(file.filename):
        return None

    filename = secure_filename(file.filename)

    # Gerar nome único
    import uuid
    ext = filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{tipo}_{uuid.uuid4().hex}.{ext}"

    upload_dir = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, unique_filename)

    try:
        # Redimensionar imagem
        file.stream.seek(0)
        img = Image.open(file.stream)
        img = img.convert('RGB') if ext in ['jpg', 'jpeg'] else img
        if tipo == 'perfil':
            img.thumbnail((400, 400))
        elif tipo == 'banner':
            img.thumbnail((1200, 400))

        img.save(filepath, quality=85, optimize=True)
        return unique_filename
    except Exception as e:
        # Log simples; em produção, usar logger estruturado
        print(f"Erro ao processar imagem: {e}")
        return None


def buscar_livros_google(query):
    """Busca livros na API do Google Books"""
    try:
        api_key = current_app.config.get('GOOGLE_BOOKS_API_KEY', '')
        url = current_app.config['GOOGLE_BOOKS_API_URL']

        params = {
            'q': query,
            'maxResults': 20,
            'langRestrict': 'pt'
        }

        if api_key:
            params['key'] = api_key

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        livros = []

        for item in data.get('items', []):
            volume_info = item.get('volumeInfo', {})

            livro = {
                'google_id': item.get('id'),
                'titulo': volume_info.get('title', 'Sem título'),
                'autor': ', '.join(volume_info.get('authors', [])) or 'Autor desconhecido',
                'isbn': None,
                'paginas': volume_info.get('pageCount', 0),
                'capa_url': volume_info.get('imageLinks', {}).get('thumbnail', ''),
                'descricao': volume_info.get('description', '')
            }

            # Buscar ISBN
            for identifier in volume_info.get('industryIdentifiers', []):
                if identifier['type'] in ['ISBN_13', 'ISBN_10']:
                    livro['isbn'] = identifier['identifier']
                    break

            livros.append(livro)

        return livros

    except Exception as e:
        print(f"Erro ao buscar livros: {e}")
        return []
