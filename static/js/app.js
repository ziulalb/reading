// ============= GERENCIAMENTO DE TABS =============
function switchTab(tabId) {
    // Esconder todas as tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Remover active de todos os botões
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Ativar tab selecionada
    document.getElementById(tabId).classList.add('active');
    event.target.classList.add('active');
}

// ============= BUSCA DE LIVROS GOOGLE BOOKS =============
async function buscarLivros() {
    const query = document.getElementById('busca-input').value.trim();
    const resultados = document.getElementById('resultados-busca');

    if (!query) {
        alert('Digite algo para buscar!');
        return;
    }

    resultados.innerHTML = '<p style="text-align: center;">🔍 Buscando...</p>';

    try {
        const response = await fetch(`/api/buscar-livros?q=${encodeURIComponent(query)}`);
        const livros = await response.json();

        if (livros.length === 0) {
            resultados.innerHTML = '<p style="text-align: center;">Nenhum livro encontrado.</p>';
            return;
        }

        resultados.innerHTML = '';
        livros.forEach(livro => {
            const card = document.createElement('div');
            card.className = 'resultado-card';
            card.innerHTML = `
                <div class="resultado-capa">
                    ${livro.capa_url ? `<img src="${livro.capa_url}" alt="${livro.titulo}">` : '📖'}
                </div>
                <div class="resultado-info">
                    <h4>${livro.titulo}</h4>
                    <p>${livro.autor}</p>
                    <small>${livro.paginas} páginas</small>
                </div>
                <button onclick='adicionarLivroAPI(${JSON.stringify(livro)})' class="btn btn-primary btn-small">
                    ➕ Adicionar
                </button>
            `;
            resultados.appendChild(card);
        });
    } catch (error) {
        console.error('Erro:', error);
        resultados.innerHTML = '<p style="color: red;">Erro ao buscar livros.</p>';
    }
}

async function adicionarLivroAPI(livro) {
    try {
        const response = await fetch('/api/adicionar-livro', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                titulo: livro.titulo,
                autor: livro.autor,
                isbn: livro.isbn,
                paginas: livro.paginas,
                capa_url: livro.capa_url,
                google_id: livro.google_id
            })
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Livro adicionado com sucesso!');
            location.reload();
        }
    } catch (error) {
        alert('❌ Erro ao adicionar livro.');
    }
}

// Adicionar livro manualmente
document.getElementById('form-adicionar-manual')?.addEventListener('submit', async function(e) {
    e.preventDefault();

    const formData = new FormData(e.target);
    const dados = {
        titulo: formData.get('titulo'),
        autor: formData.get('autor') || '',
        isbn: formData.get('isbn') || null,
        paginas: parseInt(formData.get('paginas'))
    };

    try {
        const response = await fetch('/api/adicionar-livro', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(dados)
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Livro adicionado!');
            location.reload();
        }
    } catch (error) {
        alert('❌ Erro ao adicionar.');
    }
});

// ============= REGISTRAR LEITURA =============
function atualizarUltimaPagina() {
    const select = document.getElementById('select-livro');
    const option = select.options[select.selectedIndex];

    if (option && option.value) {
        const ultima = parseInt(option.dataset.ultima) || 0;
        document.getElementById('pag-inicial').value = ultima + 1;
    }
}

document.getElementById('form-registrar-leitura')?.addEventListener('submit', async function(e) {
    e.preventDefault();

    const formData = new FormData(e.target);
    const dados = {
        livro_id: parseInt(formData.get('livro_id')),
        data: formData.get('data'),
        pagina_inicial: parseInt(formData.get('pagina_inicial')),
        pagina_final: parseInt(formData.get('pagina_final'))
    };

    if (dados.pagina_final <= dados.pagina_inicial) {
        alert('A página final deve ser maior que a inicial!');
        return;
    }

    try {
        const response = await fetch('/api/registrar-leitura', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(dados)
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Leitura registrada!');
            e.target.reset();
            const hoje = new Date().toISOString().split('T')[0];
            document.querySelector('input[name="data"]').value = hoje;
        }
    } catch (error) {
        alert('❌ Erro ao registrar.');
    }
});

// ============= CRONÔMETRO =============
let cronoIntervalo = null;
let cronoSegundos = 0;
let cronoRodando = false;
let sessaoAtualId = null;

function selecionarLivroCrono() {
    const select = document.getElementById('livro-cronometro');
    const option = select.options[select.selectedIndex];

    if (option && option.value) {
        const ultima = parseInt(option.dataset.ultima) || 0;
        document.getElementById('ultima-pag-crono').value = ultima;
        carregarHistoricoSessoes(option.value);
    }
}

function iniciarCrono() {
    const livroId = document.getElementById('livro-cronometro').value;

    if (!livroId) {
        alert('Selecione um livro primeiro!');
        return;
    }

    cronoRodando = true;
    document.getElementById('btn-iniciar').style.display = 'none';
    document.getElementById('btn-pausar').style.display = 'inline-block';
    document.getElementById('tempo-status').textContent = '⏱️ Em andamento...';

    // Iniciar sessão no backend
    fetch('/api/iniciar-sessao', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({livro_id: parseInt(livroId)})
    })
    .then(r => r.json())
    .then(data => {
        sessaoAtualId = data.sessao_id;
    });

    cronoIntervalo = setInterval(() => {
        cronoSegundos++;
        atualizarDisplayCrono();
    }, 1000);
}

function pausarCrono() {
    cronoRodando = false;
    clearInterval(cronoIntervalo);
    document.getElementById('btn-iniciar').style.display = 'inline-block';
    document.getElementById('btn-pausar').style.display = 'none';
    document.getElementById('tempo-status').textContent = '⏸️ Pausado';
}

function resetarCrono() {
    pausarCrono();
    cronoSegundos = 0;
    sessaoAtualId = null;
    atualizarDisplayCrono();
    document.getElementById('tempo-status').textContent = 'Parado';
}

function atualizarDisplayCrono() {
    const horas = Math.floor(cronoSegundos / 3600);
    const minutos = Math.floor((cronoSegundos % 3600) / 60);
    const segundos = cronoSegundos % 60;

    document.getElementById('tempo-display').textContent =
        `${String(horas).padStart(2, '0')}:${String(minutos).padStart(2, '0')}:${String(segundos).padStart(2, '0')}`;
}

async function salvarSessaoCrono() {
    if (!sessaoAtualId) {
        alert('Inicie o cronômetro primeiro!');
        return;
    }

    const pagFinal = document.getElementById('crono-pag-final').value;

    if (!pagFinal) {
        alert('Digite a página final!');
        return;
    }

    pausarCrono();

    try {
        const response = await fetch('/api/finalizar-sessao', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                sessao_id: sessaoAtualId,
                pagina_final: parseInt(pagFinal)
            })
        });

        const data = await response.json();

        if (data.success) {
            alert(`✅ Sessão salva! Duração: ${data.duracao_minutos} minutos`);
            resetarCrono();
            document.getElementById('crono-pag-final').value = '';
            location.reload();
        }
    } catch (error) {
        alert('❌ Erro ao salvar sessão.');
    }
}

async function carregarHistoricoSessoes(livroId) {
    try {
        const response = await fetch(`/api/historico-sessoes/${livroId}`);
        const sessoes = await response.json();

        const container = document.getElementById('lista-sessoes');

        if (sessoes.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #7f8c8d;">Nenhuma sessão registrada ainda.</p>';
            return;
        }

        container.innerHTML = '<table class="sessoes-table"><thead><tr><th>Data/Hora</th><th>Duração</th><th>Páginas</th></tr></thead><tbody>';

        sessoes.forEach(s => {
            container.innerHTML += `
                <tr>
                    <td>${s.inicio}</td>
                    <td>${s.duracao_minutos} min</td>
                    <td>${s.pagina_inicial} - ${s.pagina_final} (${s.paginas_lidas} págs)</td>
                </tr>
            `;
        });

        container.innerHTML += '</tbody></table>';
    } catch (error) {
        console.error('Erro ao carregar sessões:', error);
    }
}

// ============= MODAIS E HISTÓRICO =============
function verHistorico(livroId) {
    // Implementar modal com histórico de registros
    alert('Funcionalidade de histórico em desenvolvimento');
}

function verSessoes(livroId) {
    // Abrir modal com histórico de sessões
    carregarHistoricoSessoes(livroId);
}

function fecharModal() {
    document.getElementById('modal-historico').style.display = 'none';
}

// Fechar modal ao clicar fora
window.onclick = function(event) {
    const modal = document.getElementById('modal-historico');
    if (event.target == modal) {
        modal.style.display = 'none';
    }
}
