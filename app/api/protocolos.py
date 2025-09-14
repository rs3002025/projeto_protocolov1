from flask import jsonify
from . import bp
from ..models import Servidor

@bp.route('/protocolos/servidor/<string:matricula>', methods=['GET'])
def get_servidor_by_matricula(matricula):
    """
    Busca um servidor pela matrícula para preenchimento automático do formulário.
    """
    servidor = Servidor.query.filter_by(matricula=matricula).first()
    if not servidor:
        return jsonify(msg="Servidor não encontrado."), 404

    servidor_data = {
        'matricula': servidor.matricula,
        'nome': servidor.nome,
        'lotacao': servidor.lotacao,
        'cargo': servidor.cargo,
        'unidade_de_exercicio': servidor.unidade_de_exercicio
    }
    return jsonify(servidor_data)

from flask import request
from sqlalchemy import text
from ..extensions import db
from ..models import Protocolo, HistoricoProtocolo

@bp.route('/protocolos/ultimoNumero/<int:ano>', methods=['GET'])
def get_ultimo_numero_protocolo(ano):
    """
    Obtém o último número de protocolo usado em um determinado ano.
    """
    # A consulta SQL é mais eficiente para esta operação específica.
    sql = text("""
        SELECT MAX(CAST(SPLIT_PART(numero, '/', 1) AS INTEGER))
        FROM protocolos
        WHERE numero LIKE :pattern
    """)

    # O schema do tenant já está definido pelo before_request_handler
    result = db.session.execute(sql, {'pattern': f'%/{ano}'}).scalar_one_or_none()

    ultimo_numero = result if result is not None else 0

    return jsonify(ultimo=ultimo_numero)

from flask_jwt_extended import get_jwt_identity, get_jwt

@bp.route('/protocolos', methods=['POST'])
def create_protocolo():
    """
    Cria um novo protocolo.
    """
    data = request.get_json()
    if not data:
        return jsonify(msg="Dados da requisição ausentes."), 400

    # Validação básica
    numero_protocolo = data.get('numero')
    if not numero_protocolo:
        return jsonify(msg="Número do protocolo é obrigatório."), 400

    # Verificar se o número do protocolo já existe no schema do tenant
    existing_protocol = Protocolo.query.filter_by(numero=numero_protocolo).first()
    if existing_protocol:
        return jsonify(msg="O número deste protocolo já foi usado."), 409 # 409 Conflict

    try:
        new_protocolo = Protocolo(
            numero=numero_protocolo,
            nome=data.get('nome'),
            matricula=data.get('matricula'),
            endereco=data.get('endereco'),
            municipio=data.get('municipio'),
            bairro=data.get('bairro'),
            cep=data.get('cep'),
            telefone=data.get('telefone'),
            cpf=data.get('cpf'),
            rg=data.get('rg'),
            cargo=data.get('cargo'),
            lotacao=data.get('lotacao'),
            unidade_exercicio=data.get('unidade'), # 'unidade' no JS
            tipo_requerimento=data.get('tipo'), # 'tipo' no JS
            requer_ao=data.get('requerAo'), # 'requerAo' no JS
            data_solicitacao=data.get('dataSolicitacao'), # 'dataSolicitacao' no JS
            observacoes=data.get('complemento'), # 'complemento' no JS
            status=data.get('status', 'PROTOCOLO GERADO'),
            responsavel=data.get('responsavel', get_jwt_identity())
        )
        db.session.add(new_protocolo)

        # É crucial dar um flush para obter o ID do new_protocolo antes de criar o histórico
        db.session.flush()

        # Criar o primeiro registro de histórico
        historico_inicial = HistoricoProtocolo(
            protocolo_id=new_protocolo.id,
            status=new_protocolo.status,
            responsavel=new_protocolo.responsavel,
            observacao="Protocolo criado no sistema."
        )
        db.session.add(historico_inicial)

        db.session.commit()

        return jsonify(sucesso=True, id=new_protocolo.id), 201

    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Erro interno ao criar protocolo: {str(e)}"), 500

@bp.route('/protocolos', methods=['GET'])
def list_protocolos():
    """
    Lista todos os protocolos com paginação.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Ordenar por ID decrescente para mostrar os mais recentes primeiro
    pagination = Protocolo.query.order_by(Protocolo.id.desc()).paginate(page=page, per_page=per_page, error_out=False)

    protocolos = pagination.items
    protocolos_data = [
        {
            'id': p.id,
            'numero': p.numero,
            'matricula': p.matricula,
            'nome': p.nome,
            'tipo_requerimento': p.tipo_requerimento,
            'status': p.status,
            'responsavel': p.responsavel,
            'data_solicitacao': p.data_solicitacao.isoformat()
        } for p in protocolos
    ]

    return jsonify({
        'protocolos': protocolos_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })

@bp.route('/protocolos/<int:protocolo_id>', methods=['GET'])
def get_protocolo(protocolo_id):
    """
    Retorna os detalhes de um único protocolo.
    """
    protocolo = Protocolo.query.get_or_404(protocolo_id)
    # Serializar todos os campos necessários para o formulário de edição
    protocolo_data = {
        'id': protocolo.id,
        'numero': protocolo.numero,
        'nome': protocolo.nome,
        'matricula': protocolo.matricula,
        'endereco': protocolo.endereco,
        'municipio': protocolo.municipio,
        'bairro': protocolo.bairro,
        'cep': protocolo.cep,
        'telefone': protocolo.telefone,
        'cpf': protocolo.cpf,
        'rg': protocolo.rg,
        'cargo': protocolo.cargo,
        'lotacao': protocolo.lotacao,
        'unidade_exercicio': protocolo.unidade_exercicio,
        'tipo_requerimento': protocolo.tipo_requerimento,
        'requer_ao': protocolo.requer_ao,
        'data_solicitacao': protocolo.data_solicitacao.isoformat() if protocolo.data_solicitacao else None,
        'observacoes': protocolo.observacoes,
        'status': protocolo.status,
        'responsavel': protocolo.responsavel
    }
    return jsonify(protocolo=protocolo_data)

@bp.route('/protocolos/<int:protocolo_id>', methods=['PUT'])
def update_protocolo(protocolo_id):
    """
    Atualiza um protocolo existente. Apenas para admin/padrão.
    """
    claims = get_jwt()
    if claims.get('role') not in ['admin', 'padrao']:
        return jsonify(msg="Acesso não autorizado."), 403

    protocolo = Protocolo.query.get_or_404(protocolo_id)
    data = request.get_json()

    # Atualizar campos
    for key, value in data.items():
        # Mapeia os nomes do JS para os nomes do modelo
        key_map = {
            'unidade': 'unidade_exercicio',
            'tipo': 'tipo_requerimento',
            'requerAo': 'requer_ao',
            'dataSolicitacao': 'data_solicitacao',
            'complemento': 'observacoes'
        }
        model_key = key_map.get(key, key)
        if hasattr(protocolo, model_key):
            setattr(protocolo, model_key, value)

    db.session.commit()
    return jsonify(sucesso=True, mensagem="Protocolo atualizado com sucesso.")

@bp.route('/protocolos/<int:protocolo_id>', methods=['DELETE'])
def delete_protocolo(protocolo_id):
    """
    Exclui um protocolo. Apenas para admin/padrão.
    """
    claims = get_jwt()
    if claims.get('role') not in ['admin', 'padrao']:
        return jsonify(msg="Acesso não autorizado."), 403

    protocolo = Protocolo.query.get_or_404(protocolo_id)

    db.session.delete(protocolo)
    db.session.commit()

    return jsonify(sucesso=True, mensagem="Protocolo excluído com sucesso.")

@bp.route('/protocolos/historico/<int:protocolo_id>', methods=['GET'])
def get_protocolo_historico(protocolo_id):
    """
    Retorna o histórico de movimentações de um protocolo.
    """
    # Garante que o protocolo existe antes de buscar o histórico
    Protocolo.query.get_or_404(protocolo_id)

    historico = HistoricoProtocolo.query.filter_by(protocolo_id=protocolo_id).order_by(HistoricoProtocolo.data_movimentacao.asc()).all()

    historico_data = [
        {
            'status': h.status,
            'responsavel': h.responsavel,
            'observacao': h.observacao,
            'data_movimentacao': h.data_movimentacao.isoformat()
        } for h in historico
    ]
    return jsonify(historico=historico_data)

@bp.route('/protocolos/atualizar', methods=['POST'])
def atualizar_status_protocolo():
    """
    Atualiza o status e/ou responsável de um protocolo e registra no histórico.
    """
    data = request.get_json()
    protocolo_id = data.get('protocoloId')
    novo_status = data.get('novoStatus')
    novo_responsavel = data.get('novoResponsavel')
    observacao = data.get('observacao')

    if not protocolo_id:
        return jsonify(msg="ID do protocolo é obrigatório."), 400

    protocolo = Protocolo.query.get_or_404(protocolo_id)

    try:
        if novo_status:
            protocolo.status = novo_status

        if novo_responsavel:
            protocolo.responsavel = novo_responsavel

        # Criar o registro de histórico para a alteração
        claims = get_jwt()
        ator_da_mudanca = claims.get('login', 'sistema') # Quem está fazendo a alteração

        historico_entry = HistoricoProtocolo(
            protocolo_id=protocolo.id,
            status=protocolo.status,
            responsavel=protocolo.responsavel,
            observacao=f"({ator_da_mudanca}) {observacao or 'Status atualizado.'}"
        )
        db.session.add(historico_entry)
        db.session.commit()
        return jsonify(sucesso=True, mensagem="Protocolo atualizado com sucesso.")
    except Exception as e:
        db.session.rollback()
        return jsonify(msg=f"Erro ao atualizar protocolo: {str(e)}"), 500

@bp.route('/protocolos/servidores/search', methods=['GET'])
def search_servidores():
    """
    Busca servidores pelo nome.
    """
    search_term = request.args.get('nome', '').strip()
    if len(search_term) < 3:
        return jsonify([]) # Retorna lista vazia se o termo for muito curto

    servidores = Servidor.query.filter(Servidor.nome.ilike(f'%{search_term}%')).limit(20).all()

    servidores_data = [
        {
            'matricula': s.matricula,
            'nome': s.nome,
            'lotacao': s.lotacao,
            'cargo': s.cargo,
            'unidade_de_exercicio': s.unidade_de_exercicio
        } for s in servidores
    ]
    return jsonify(servidores_data)

@bp.route('/protocolos/meus', methods=['GET'])
def list_meus_protocolos():
    """
    Lista os protocolos do usuário logado, com paginação.
    A identidade do usuário é obtida de forma segura a partir do token JWT.
    """
    claims = get_jwt()
    user_login = claims.get('login')

    if not user_login:
        return jsonify(msg="Token inválido: 'login' ausente nas claims."), 401

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    query = Protocolo.query.filter_by(responsavel=user_login).order_by(Protocolo.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    protocolos = pagination.items
    protocolos_data = [
        {
            'id': p.id,
            'numero': p.numero,
            'nome': p.nome,
            'status': p.status,
            'responsavel': p.responsavel,
            'data_solicitacao': p.data_solicitacao.isoformat()
        } for p in protocolos
    ]

    return jsonify({
        'protocolos': protocolos_data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page,
        'has_next': pagination.has_next,
        'has_prev': pagination.has_prev
    })
