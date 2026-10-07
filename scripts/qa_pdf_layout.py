"""Gera exemplos sem dados pessoais, usando o mesmo template e motor da aplicação."""
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace as Record
import base64
import io
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
import qrcode

root = Path(__file__).resolve().parents[1]
output = root / 'tmp' / 'pdf-layout-review'
output.mkdir(parents=True, exist_ok=True)
env = Environment(loader=FileSystemLoader(root / 'templates'), autoescape=select_autoescape())
template = env.get_template('pdf_template.html')
buffer = io.BytesIO()
qrcode.make('https://example.org/documento-de-teste').save(buffer, format='PNG')
qr = 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()
envio = Record(id=1, metodo='conta_individual', emitido_em=datetime(2026,10,7,11,0,tzinfo=timezone.utc), codigo_publico='TESTE-ENVIO')
emissao = Record(versao=2, substitui_emissao_id=1, metodo='pin_pessoal', emitido_em=datetime(2026,10,7,11,5,tzinfo=timezone.utc), codigo_publico='TESTE-FINAL', nome_emitente='Responsável de demonstração', login_emitente='teste')
org = Record(nome='Prefeitura de Demonstração', orgao='Prefeitura de Demonstração', municipio='', rodape_documento='')
protocol = Record(numero='TESTE/2026', data_solicitacao=date(2026,10,7), nome='Requerente de demonstração', matricula='TESTE', cpf='000.000.000-00', rg='', endereco='Rua de demonstração, 100', bairro='Centro', municipio='Município de demonstração', cep='00000-000', cargo='Servidor', telefone='(00) 00000-0000', lotacao='Administração', unidade_exercicio='Unidade de atendimento', tipo_requerimento='Solicitação de demonstração', requer_ao='Setor responsável', modalidade_abertura='remota_requerente', envio_requerente=envio, anexos=[])
logo = root / 'static' / 'img' / 'logo.png'
for name, text in [('curto', 'Solicito a análise deste requerimento para fins de demonstração do sistema.'), ('longo', '\n'.join([f'{i+1}. Solicito a análise das informações apresentadas neste requerimento. Este texto é um exemplo de conteúdo extenso para conferir a paginação, a continuidade dos parágrafos e a área das assinaturas.' for i in range(22)]))]:
    protocol.observacoes = text
    rendered = template.render(protocolo=protocol, organizacao=org, emissao=emissao, pdf_logo_url=logo.as_uri(), qr_code_url=qr, qr_validacao_url=qr)
    assert 'REQUERIMENTO RECEBIDO' not in rendered and 'VERSÃO' not in rendered
    HTML(string=rendered, base_url=str(root)).write_pdf(output / f'requerimento-{name}.pdf')
    print(output / f'requerimento-{name}.pdf')
