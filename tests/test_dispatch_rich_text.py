import json
import pytest
from types import SimpleNamespace
from dispatch_rich_text import dispatch_body, normalize_delta, render_delta

def delta(*ops):
    return json.dumps({'ops':list(ops)})

def test_safe_rich_formatting_and_lists():
    raw=delta({'insert':'Decisão','attributes':{'bold':True,'color':'#123abc','font':'georgia'}},
              {'insert':'\n','attributes':{'header':2,'align':'center'}},
              {'insert':'Primeiro item'}, {'insert':'\n','attributes':{'list':'ordered'}},
              {'insert':'Segundo item'}, {'insert':'\n','attributes':{'list':'ordered'}},
              {'insert':'Fim\n'})
    normalized,text=normalize_delta(raw)
    assert text=='Decisão\nPrimeiro item\nSegundo item\nFim'
    html=str(render_delta(normalized))
    assert '<h2 style="text-align:center">' in html and '<strong>Decisão</strong>' in html
    assert 'color:#123abc' in html and html.count('<ol ')==1 and html.count('<li>')==2
    assert '<p>Fim</p>' in html

def test_never_accepts_html_css_scripts_embeds_or_unsafe_links():
    raw=delta({'insert':'<script>alert(1)</script><img src=x onerror=alert(1)>',
               'attributes':{'link':'javascript:alert(1)','color':'url(https://evil.invalid)',
                             'font':'x; background:url(https://evil.invalid)','onerror':'alert(1)',
                             'style':'position:fixed','bold':True}}, {'insert':'\n'})
    normalized,_=normalize_delta(raw)
    html=str(render_delta(normalized))
    assert '<script' not in html and '<img' not in html and 'javascript:' not in html
    assert 'url(' not in html and '<strong>&lt;script&gt;' in html
    for url in ('data:text/html,evil','//evil.invalid','https://user:secret@evil.invalid','https://example.com/\nmalicious'):
        assert 'href=' not in render_delta(delta({'insert':'Link','attributes':{'link':url}}))
    assert 'rel="noopener noreferrer"' in render_delta(delta({'insert':'Link','attributes':{'link':'https://example.com/?a=1&b=2'}}))
    for raw in (delta({'insert':{'image':'https://evil.invalid'}}),delta({'insert':'x','attributes':[]}),'{bad',delta({'insert':'x\x00'}),delta({'insert':'x'*100001}),delta({'insert':' \n'})):
        with pytest.raises(ValueError): normalize_delta(raw)

def test_legacy_and_invalid_rich_data_are_escaped():
    d=SimpleNamespace(texto='<b>Legado</b>\nLinha 2',conteudo_delta=None)
    assert '&lt;b&gt;Legado&lt;/b&gt;<br>Linha 2' in dispatch_body(d)
    d.conteudo_delta='invalid'
    assert '<b>' not in dispatch_body(d)

