import io
from flask import send_file, request, jsonify
from . import bp
from ..extensions import db
from ..models import Protocolo
from sqlalchemy import func, text
from datetime import datetime, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font

def get_base_query(filters):
    """Cria uma query base com os filtros comuns."""
    base_filters = []
    if filters.get('dataInicio'):
        base_filters.append(Protocolo.data_solicitacao >= filters['dataInicio'])
    if filters.get('dataFim'):
        base_filters.append(Protocolo.data_solicitacao <= filters['dataFim'])
    if filters.get('status'):
        base_filters.append(Protocolo.status == filters['status'])
    if filters.get('tipo'):
        base_filters.append(Protocolo.tipo_requerimento == filters['tipo'])
    if filters.get('lotacao'):
        base_filters.append(Protocolo.lotacao == filters['lotacao'])
    return Protocolo.query.filter(*base_filters)

@bp.route('/protocolos/dashboard-stats', methods=['GET'])
def dashboard_stats():
    try:
        filters = request.args.to_dict()
        base_query = get_base_query(filters)

        # 1. Cards de Estatísticas
        novos_no_periodo = base_query.count()
        total_finalizados = base_query.filter(Protocolo.status.in_(['Finalizado', 'Concluído'])).count()

        # Pendentes antigos: criados antes do período de início e não finalizados
        quinze_dias_atras = datetime.now() - timedelta(days=15)
        pendentes_antigos = Protocolo.query.filter(
            Protocolo.data_solicitacao < quinze_dias_atras,
            ~Protocolo.status.in_(['Finalizado', 'Concluído'])
        ).count()

        # 2. Gráficos (baseado na query com filtros)
        top_tipos = db.session.query(
            Protocolo.tipo_requerimento, func.count(Protocolo.id).label('total')
        ).select_from(base_query.subquery()).group_by(Protocolo.tipo_requerimento).order_by(func.count(Protocolo.id).desc()).limit(5).all()

        status_protocolos = db.session.query(
            Protocolo.status, func.count(Protocolo.id).label('total')
        ).select_from(base_query.subquery()).group_by(Protocolo.status).all()

        todos_tipos = db.session.query(
             Protocolo.tipo_requerimento, func.count(Protocolo.id).label('total')
        ).select_from(base_query.subquery()).group_by(Protocolo.tipo_requerimento).order_by(Protocolo.tipo_requerimento).all()


        # 3. Gráfico de Evolução (requer query separada para o período de evolução)
        evolucao_periodo = filters.get('evolucaoPeriodo', '30d')
        evolucao_agrupamento = filters.get('evolucaoAgrupamento', 'day')

        evolucao_data_inicio = datetime.now()
        if evolucao_periodo == '7d': evolucao_data_inicio -= timedelta(days=7)
        elif evolucao_periodo == '30d': evolucao_data_inicio -= timedelta(days=30)
        elif evolucao_periodo == 'month': evolucao_data_inicio = evolucao_data_inicio.replace(day=1)
        else: evolucao_data_inicio = Protocolo.query.order_by(Protocolo.data_solicitacao.asc()).first().data_solicitacao if Protocolo.query.count() > 0 else datetime.now()

        date_trunc_str = 'day' if evolucao_agrupamento == 'day' else 'month'

        evolucao_query = db.session.query(
            func.date_trunc(date_trunc_str, Protocolo.data_solicitacao).label('intervalo'),
            func.count(Protocolo.id).label('total')
        ).filter(Protocolo.data_solicitacao >= evolucao_data_inicio).group_by('intervalo').order_by('intervalo')

        evolucao_protocolos = evolucao_query.all()

        return jsonify({
            'novosNoPeriodo': novos_no_periodo,
            'pendentesAntigos': pendentes_antigos,
            'totalFinalizados': total_finalizados,
            'topTipos': [{'tipo_requerimento': r[0], 'total': r[1]} for r in top_tipos],
            'statusProtocolos': [{'status': r[0], 'total': r[1]} for r in status_protocolos],
            'todosTipos': [{'tipo_requerimento': r[0], 'total': r[1]} for r in todos_tipos],
            'evolucaoProtocolos': [{'intervalo': r.intervalo.isoformat(), 'total': r.total} for r in evolucao_protocolos],
        })

    except Exception as e:
        print(f"Erro ao gerar stats do dashboard: {e}")
        return jsonify(msg=f"Erro interno ao gerar estatísticas: {str(e)}"), 500


@bp.route('/protocolos/backup', methods=['GET'])
def export_excel_report():
    """
    Gera um relatório em Excel com base nos filtros fornecidos
    e o retorna para download.
    """
    try:
        # Coletar filtros da query string
        filters = []
        if request.args.get('numero'):
            filters.append(Protocolo.numero.ilike(f"%{request.args.get('numero')}%"))
        if request.args.get('nome'):
            filters.append(Protocolo.nome.ilike(f"%{request.args.get('nome')}%"))
        if request.args.get('status'):
            filters.append(Protocolo.status == request.args.get('status'))
        if request.args.get('tipo'):
            filters.append(Protocolo.tipo_requerimento == request.args.get('tipo'))
        if request.args.get('lotacao'):
            filters.append(Protocolo.lotacao == request.args.get('lotacao'))
        if request.args.get('dataInicio'):
            filters.append(Protocolo.data_solicitacao >= request.args.get('dataInicio'))
        if request.args.get('dataFim'):
            filters.append(Protocolo.data_solicitacao <= request.args.get('dataFim'))

        # Query no banco de dados
        query = Protocolo.query.filter(*filters).order_by(Protocolo.data_solicitacao.desc())
        protocolos = query.all()

        # Criar o workbook e a worksheet do Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "Relatório de Protocolos"

        # Cabeçalhos
        headers = [
            "Número", "Data Solicitação", "Nome Requerente", "Matrícula", "CPF",
            "Tipo de Requerimento", "Status", "Responsável Atual", "Lotação"
        ]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)

        # Preencher com os dados
        for p in protocolos:
            ws.append([
                p.numero,
                p.data_solicitacao.strftime('%d/%m/%Y') if p.data_solicitacao else '',
                p.nome,
                p.matricula,
                p.cpf,
                p.tipo_requerimento,
                p.status,
                p.responsavel,
                p.lotacao
            ])

        # Salvar em um stream de bytes na memória
        mem_stream = io.BytesIO()
        wb.save(mem_stream)
        mem_stream.seek(0)

        return send_file(
            mem_stream,
            as_attachment=True,
            download_name='relatorio_protocolos.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print(f"Erro ao gerar relatório Excel: {e}")
        return jsonify(msg="Erro interno ao gerar relatório."), 500

@bp.route('/protocolos/pesquisa', methods=['GET'])
def search_protocolos():
    """
    Realiza uma busca avançada em protocolos, com paginação.
    """
    try:
        filters = []
        if request.args.get('numero'):
            filters.append(Protocolo.numero.ilike(f"%{request.args.get('numero')}%"))
        if request.args.get('nome'):
            filters.append(Protocolo.nome.ilike(f"%{request.args.get('nome')}%"))
        if request.args.get('status'):
            filters.append(Protocolo.status == request.args.get('status'))
        if request.args.get('tipo'):
            filters.append(Protocolo.tipo_requerimento == request.args.get('tipo'))
        if request.args.get('lotacao'):
            filters.append(Protocolo.lotacao == request.args.get('lotacao'))
        if request.args.get('dataInicio'):
            filters.append(Protocolo.data_solicitacao >= request.args.get('dataInicio'))
        if request.args.get('dataFim'):
            filters.append(Protocolo.data_solicitacao <= request.args.get('dataFim'))

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        query = Protocolo.query.filter(*filters).order_by(Protocolo.data_solicitacao.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        protocolos = pagination.items
        protocolos_data = [
            {
                'id': p.id, 'numero': p.numero, 'nome': p.nome, 'matricula': p.matricula,
                'tipo_requerimento': p.tipo_requerimento,
                'data_solicitacao': p.data_solicitacao.isoformat() if p.data_solicitacao else None,
                'status': p.status, 'responsavel': p.responsavel
            } for p in protocolos
        ]

        return jsonify({
            'protocolos': protocolos_data,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': pagination.page
        })

    except Exception as e:
        print(f"Erro ao pesquisar protocolos: {e}")
        return jsonify(msg="Erro interno ao pesquisar protocolos."), 500
