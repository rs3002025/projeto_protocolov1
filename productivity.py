"""Preferências pessoais e modelos do cliente, sem ampliar acesso a protocolos."""
import json
from datetime import datetime, timezone
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from dispatch_rich_text import normalize_delta

SEARCH_FIELDS = ('numero','nome','status','data_inicio','data_fim','tipo','prazo','setor_atual','tipo_exato')


def saved_searches():
    from app import tenant_query
    from models import PesquisaSalva
    result=[]
    for item in tenant_query(PesquisaSalva).filter_by(usuario_id=current_user.id,ativo=True).order_by(PesquisaSalva.nome).all():
        try:
            filters=json.loads(item.filtros)
            if not isinstance(filters,dict): continue
            filters={key:str(value) for key,value in filters.items() if key in SEARCH_FIELDS}
        except (ValueError,TypeError): continue
        result.append(dict(id=item.id,nome=item.nome,url=url_for('relatorios',**filters)))
    return result


def alert_preference():
    from app import tenant_query
    from models import PreferenciaAlerta
    item=tenant_query(PreferenciaAlerta).filter_by(usuario_id=current_user.id).first()
    return dict(ativo=item.ativo if item else True,dias=item.antecedencia_dias if item else 3)


def register_productivity_routes(app,db):
    from app import (permission_required,tenant_query,current_tenant_id,accessible_protocols_query,
                     apply_protocol_filters,_admin_audit)
    from models import PesquisaSalva,PreferenciaAlerta,ModeloDespacho,Usuario,Organizacao

    @app.post('/relatorios/pesquisas')
    @permission_required('reports')
    def salvar_pesquisa():
        name=(request.form.get('nome_pesquisa') or '').strip()
        if not name or len(name)>80 or any(ord(c)<32 for c in name): abort(400)
        filters={key:request.form.get(key,'').strip() for key in SEARCH_FIELDS if request.form.get(key,'').strip()}
        if any(len(value)>400 for value in filters.values()): abort(400)
        apply_protocol_filters(accessible_protocols_query(),filters)
        # Serializa alterações por usuário, inclusive com duas réplicas.
        db.session.query(Usuario.id).filter(Usuario.id==current_user.id).with_for_update().one()
        item=tenant_query(PesquisaSalva).filter_by(usuario_id=current_user.id,nome=name).first()
        if (not item or not item.ativo) and tenant_query(PesquisaSalva).filter_by(usuario_id=current_user.id,ativo=True).count()>=20:
            abort(400,description='Você pode manter até 20 pesquisas salvas.')
        if not item:
            item=PesquisaSalva(tenant_id=current_tenant_id(),usuario_id=current_user.id,nome=name)
            db.session.add(item)
        item.filtros=json.dumps(filters,ensure_ascii=False); item.ativo=True
        db.session.commit(); flash('Pesquisa salva para seu usuário.','success')
        return redirect(url_for('relatorios',**filters))

    @app.post('/relatorios/pesquisas/<int:pesquisa_id>/remover')
    @permission_required('reports')
    def remover_pesquisa(pesquisa_id):
        item=tenant_query(PesquisaSalva).filter_by(id=pesquisa_id,usuario_id=current_user.id).first_or_404()
        item.ativo=False; db.session.commit()
        return redirect(url_for('relatorios'))

    @app.post('/painel/alertas')
    @permission_required('view')
    def configurar_alertas():
        raw=request.form.get('antecedencia_dias','3')
        if raw not in ('0','1','3','7'): abort(400)
        db.session.query(Usuario.id).filter(Usuario.id==current_user.id).with_for_update().one()
        item=tenant_query(PreferenciaAlerta).filter_by(usuario_id=current_user.id).first()
        if not item:
            item=PreferenciaAlerta(tenant_id=current_tenant_id(),usuario_id=current_user.id)
            db.session.add(item)
        item.ativo=request.form.get('ativo')=='1'; item.antecedencia_dias=int(raw)
        db.session.commit(); flash('Preferências de alerta atualizadas.','success')
        scope=request.form.get('escopo','')
        if scope not in ('equipe','meu','acompanhando'): scope=None
        return redirect(url_for('home',**({'escopo':scope} if scope else {})))

    @app.get('/modelos-despacho')
    @permission_required('view')
    def modelos_despacho():
        query=tenant_query(ModeloDespacho)
        if current_user.tipo!='admin': query=query.filter_by(ativo=True)
        return render_template('modelos_despacho.html',title='Modelos de despacho',modelos=query.order_by(ModeloDespacho.nome).all())

    @app.get('/modelos-despacho/editar')
    @app.get('/modelos-despacho/<int:modelo_id>/editar')
    @permission_required('manage')
    def editar_modelo_despacho(modelo_id=None):
        item=tenant_query(ModeloDespacho).filter_by(id=modelo_id).first_or_404() if modelo_id else None
        return render_template('despacho_editor.html',title='Modelo de despacho',modelo_editor=True,modelo=item,
            assunto=item.assunto if item else '',texto=item.texto if item else '',
            conteudo_delta=item.conteudo_delta or '' if item else '',envio_token='',falha=False)

    @app.post('/modelos-despacho/salvar')
    @permission_required('manage')
    def salvar_modelo_despacho():
        identifier=request.form.get('modelo_id','')
        if identifier and not identifier.isdecimal(): abort(400)
        item=tenant_query(ModeloDespacho).filter_by(id=int(identifier)).first_or_404() if identifier else None
        name=(request.form.get('nome_modelo') or '').strip(); subject=(request.form.get('assunto') or '').strip()
        text=(request.form.get('texto') or '').strip(); delta=request.form.get('conteudo_delta') or ''
        if not name or len(name)>100 or not subject or len(subject)>250 or any(ord(c)<32 for c in name+subject): abort(400)
        if delta:
            try: delta,text=normalize_delta(delta)
            except ValueError as exc: abort(400,description=str(exc))
        if not text or len(text)>100000 or '\x00' in text: abort(400)
        db.session.query(Organizacao.id).filter_by(id=current_tenant_id()).with_for_update().one()
        if not item:
            if tenant_query(ModeloDespacho).count()>=100: abort(400,description='Limite de 100 modelos por cliente.')
            item=ModeloDespacho(tenant_id=current_tenant_id()); db.session.add(item)
        item.nome,item.assunto,item.texto,item.conteudo_delta=name,subject,text,delta or None
        item.atualizado_por_id=current_user.id; item.atualizado_em=datetime.now(timezone.utc)
        _admin_audit('MODELO_DESPACHO_ATUALIZADO',f'Modelo de despacho {name} atualizado.')
        db.session.commit(); flash('Modelo salvo. Ele deve ser revisado antes de registrar cada despacho.','success')
        return redirect(url_for('modelos_despacho'))

    @app.post('/modelos-despacho/<int:modelo_id>/situacao')
    @permission_required('manage')
    def situacao_modelo_despacho(modelo_id):
        item=tenant_query(ModeloDespacho).filter_by(id=modelo_id).first_or_404()
        item.ativo=request.form.get('ativo')=='1'
        _admin_audit('MODELO_DESPACHO_SITUACAO',f'Modelo de despacho {item.id}: ativo={item.ativo}.')
        db.session.commit(); return redirect(url_for('modelos_despacho'))
