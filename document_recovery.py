"""Recuperação administrativa de bytes originais comprovados por hash."""
import hashlib,hmac,re
from flask import abort,flash,redirect,render_template,request,url_for
from sqlalchemy.orm import defer


def register_recovery_routes(app,db):
    from app import permission_required,tenant_query,read_attachment_bytes,_admin_audit
    from models import Anexo,Protocolo,EmissaoEletronica

    @app.get('/admin/recuperar-documento')
    @permission_required('manage')
    def recuperar_documento():
        number=(request.args.get('numero') or '').strip()
        protocol=tenant_query(Protocolo).filter_by(numero=number).first() if number else None
        documents=tenant_query(Anexo).filter_by(protocolo_id=protocol.id).options(defer(Anexo.file_data)).order_by(
            Anexo.id.desc()).all() if protocol else []
        return render_template('recuperar_documento.html',title='Recuperar documento original',
                               numero=number,protocolo=protocol,documentos=documents)

    @app.post('/admin/recuperar-documento/<int:anexo_id>')
    @permission_required('manage')
    def restaurar_documento_original(anexo_id):
        item=tenant_query(Anexo).filter_by(id=anexo_id).with_for_update().first_or_404()
        protocol=tenant_query(Protocolo).filter_by(id=item.protocolo_id).first_or_404()
        expected=item.file_hash or ''
        if not re.fullmatch(r'[0-9a-fA-F]{64}',expected):
            abort(409,description='O cadastro não possui um hash de integridade. É necessária conferência especializada da fonte original.')
        source=request.files.get('original')
        if not source: abort(400,description='Selecione o arquivo original.')
        data=source.read(min(item.file_size,30*1024*1024)+1)
        digest=hashlib.sha256(data).hexdigest()
        if len(data)!=item.file_size or not hmac.compare_digest(digest,expected.lower()):
            abort(400,description='O arquivo não corresponde ao original registrado. Nenhuma alteração foi realizada.')
        emission=tenant_query(EmissaoEletronica).filter_by(pdf_anexo_id=item.id).first()
        if emission and not hmac.compare_digest(digest,emission.pdf_sha256):
            abort(409,description='O arquivo não corresponde à evidência de emissão preservada.')
        try:
            read_attachment_bytes(item)
        except Exception:
            pass
        else:
            abort(409,description='O original já está disponível e íntegro. Nenhuma substituição foi realizada.')
        # Preserva o objeto anterior no armazenamento e todos os metadados.
        # Uma cópia validada no banco restaura a leitura sem sobrescrever a fonte.
        item.file_data=data; item.storage_backend='database'
        _admin_audit('ARQUIVO_ORIGINAL_RECUPERADO',f'Anexo {item.id} do protocolo {protocol.numero} recuperado com tamanho e hash originais confirmados.')
        db.session.commit()
        flash('Arquivo original recuperado. Conteúdo, versão e evidências de emissão foram preservados.','success')
        return redirect(url_for('detalhe_protocolo',protocolo_id=protocol.id,_anchor='documentos'))
