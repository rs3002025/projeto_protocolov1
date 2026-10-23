"""Rich text from a validated Delta, never from user-supplied HTML or CSS."""
import json
import re
from urllib.parse import urlsplit
from markupsafe import Markup, escape

MAX_TEXT = 100_000
MAX_DELTA = 1_000_000
FONTS = {'arial': 'Arial, sans-serif', 'times-new-roman': "'Times New Roman', serif",
         'georgia': 'Georgia, serif', 'calibri': 'Calibri, sans-serif', 'monospace': 'monospace'}
SIZES = {'small': '10pt', 'large': '14pt', 'huge': '18pt'}


def normalize_delta(raw):
    if not isinstance(raw, str) or len(raw) > MAX_DELTA:
        raise ValueError('Conteúdo formatado inválido ou muito extenso.')
    try:
        source = json.loads(raw)
    except (ValueError, RecursionError):
        raise ValueError('Conteúdo formatado inválido.') from None
    if not isinstance(source, dict) or not isinstance(source.get('ops'), list) or len(source['ops']) > 10_000:
        raise ValueError('Conteúdo formatado inválido.')
    ops, plain = [], []
    total = 0
    for op in source['ops']:
        if not isinstance(op, dict) or not isinstance(op.get('insert'), str):
            raise ValueError('O despacho aceita texto, sem imagens ou conteúdo incorporado.')
        text = op['insert'].replace('\r\n', '\n').replace('\r', '\n')
        if any(ord(ch) < 32 and ch not in '\n\t' for ch in text):
            raise ValueError('O texto contém caracteres inválidos.')
        total += len(text)
        if total > MAX_TEXT:
            raise ValueError('Informe o despacho, com até 100.000 caracteres.')
        attrs = op.get('attributes', {})
        if not isinstance(attrs, dict):
            raise ValueError('Formatação inválida.')
        safe = {}
        for key, value in attrs.items():
            if key in ('bold', 'italic', 'underline', 'strike', 'blockquote') and value is True:
                safe[key] = True
            elif key == 'font' and isinstance(value, str) and value in FONTS:
                safe[key] = value
            elif key == 'size' and isinstance(value, str) and value in SIZES:
                safe[key] = value
            elif key in ('color', 'background') and isinstance(value, str) and re.fullmatch(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?', value):
                safe[key] = value.lower()
            elif key == 'align' and value in ('left', 'center', 'right', 'justify'):
                safe[key] = value
            elif key == 'header' and type(value) is int and 1 <= value <= 3:
                safe[key] = value
            elif key == 'indent' and type(value) is int and 1 <= value <= 8:
                safe[key] = value
            elif key == 'list' and value in ('ordered', 'bullet'):
                safe[key] = value
            elif key == 'link' and isinstance(value, str) and len(value) <= 2000:
                try:
                    url = urlsplit(value)
                    if (url.scheme.lower() in ('https', 'http') and url.hostname and not url.username
                            and not any(ord(ch) <= 32 for ch in value)):
                        safe[key] = value
                except ValueError:
                    pass
        cleaned = {'insert': text}
        if safe:
            cleaned['attributes'] = safe
        ops.append(cleaned); plain.append(text)
    text = ''.join(plain).strip()
    if not text or len(text) > MAX_TEXT:
        raise ValueError('Informe o texto do despacho.')
    return json.dumps({'ops': ops}, ensure_ascii=False, separators=(',', ':')), text


def inline_html(text, attrs):
    result = str(escape(text))
    for key, tag in (('bold','strong'), ('italic','em'), ('underline','u'), ('strike','s')):
        if attrs.get(key):
            result = f'<{tag}>{result}</{tag}>'
    styles = []
    if attrs.get('font') in FONTS:
        styles.append('font-family:' + FONTS[attrs['font']])
    if attrs.get('size') in SIZES:
        styles.append('font-size:' + SIZES[attrs['size']])
    for key, prop in (('color','color'), ('background','background-color')):
        if key in attrs:
            styles.append(prop + ':' + attrs[key])
    if styles:
        result = '<span style="' + str(escape(';'.join(styles))) + '">' + result + '</span>'
    if attrs.get('link'):
        result = f'<a href="{escape(attrs["link"])}" target="_blank" rel="noopener noreferrer">{result}</a>'
    return result


def render_delta(raw):
    canonical, _ = normalize_delta(raw)
    lines, current = [], []
    for op in json.loads(canonical)['ops']:
        attrs = op.get('attributes', {})
        pieces = op['insert'].split('\n')
        for index, piece in enumerate(pieces):
            if piece:
                current.append(inline_html(piece, attrs))
            if index < len(pieces)-1:
                lines.append((''.join(current) or '<br>', attrs)); current=[]
    if current:
        lines.append((''.join(current), {}))
    result, opened = [], None
    for content, attrs in lines:
        kind = attrs.get('list')
        group = (kind, attrs.get('indent', 0)) if kind else None
        if group != opened:
            if opened:
                result.append('</ol>' if opened[0]=='ordered' else '</ul>')
            if group:
                tag = 'ol' if kind=='ordered' else 'ul'
                result.append(f'<{tag} style="margin-left:{group[1]*1.5:g}em">')
            opened = group
        styles=[]
        if attrs.get('align'):
            styles.append('text-align:'+attrs['align'])
        if not kind and attrs.get('indent'):
            styles.append(f'margin-left:{attrs["indent"]*1.5:g}em')
        tag = 'li' if kind else ('h'+str(attrs['header']) if attrs.get('header') else ('blockquote' if attrs.get('blockquote') else 'p'))
        style = f' style="{";".join(styles)}"' if styles else ''
        result.append(f'<{tag}{style}>{content}</{tag}>')
    if opened:
        result.append('</ol>' if opened[0]=='ordered' else '</ul>')
    return Markup(''.join(result))


def dispatch_body(dispatch):
    raw = getattr(dispatch, 'conteudo_delta', None)
    if raw:
        try:
            return render_delta(raw)
        except ValueError:
            pass  # Legacy/corrupt rich data is never emitted as HTML.
    return Markup('<p>') + escape(dispatch.texto or '').replace('\n', Markup('<br>')) + Markup('</p>')
