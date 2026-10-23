(() => {
  const form = document.getElementById('dispatch-form');
  const plain = document.getElementById('dispatch-plain');
  const delta = document.getElementById('dispatch-delta');
  const wrapper = document.getElementById('dispatch-rich-wrapper');
  if (!form || !window.Quill) return; // Plain textarea remains usable if the editor cannot load.
  let editor;
  let dirty = false;
  let submitted = false;
  try {
    const Font = Quill.import('formats/font');
    Font.whitelist = ['arial', 'times-new-roman', 'georgia', 'calibri', 'monospace'];
    Quill.register(Font, true);
    editor = new Quill('#dispatch-rich', {
      theme: 'snow', placeholder: 'Escreva o texto do despacho…',
      formats: ['header','font','size','bold','italic','underline','strike','color','background','align','list','indent','blockquote','link'],
      modules: { toolbar: {container:'#dispatch-toolbar', handlers: {
        undo() { this.quill.history.undo(); }, redo() { this.quill.history.redo(); },
        expand() { wrapper.classList.toggle('dispatch-expanded'); }
      }}, history: {userOnly:true} }
    });
    if (delta.value) editor.setContents(JSON.parse(delta.value));
    else if (plain.value) editor.setText(plain.value);
    editor.history.clear();
    editor.root.setAttribute('aria-labelledby','dispatch-body-label');
    editor.root.setAttribute('aria-describedby','dispatch-help');
    editor.root.setAttribute('spellcheck','true');
    editor.root.setAttribute('lang','pt-BR');
    wrapper.hidden = false;
    plain.hidden = true;
    plain.required = false;
    delta.disabled = false;
  } catch (error) { wrapper.hidden = true; return; }
  const synchronize = () => {
    plain.value = editor.getText();
    delta.value = JSON.stringify(editor.getContents());
  };
  editor.on('text-change', () => { dirty = true; synchronize(); });
  document.getElementById('dispatch-subject').addEventListener('input', () => { dirty = true; });
  form.addEventListener('submit', event => {
    synchronize();
    const error = document.getElementById('dispatch-error');
    if (!plain.value.trim() || plain.value.length > 100000) {
      event.preventDefault(); error.hidden = false;
      error.textContent = 'Informe o texto do despacho, com até 100.000 caracteres.';
      editor.focus(); return;
    }
    submitted = true;
  });
  window.addEventListener('beforeunload', event => {
    if (dirty && !submitted) { event.preventDefault(); event.returnValue = ''; }
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') wrapper.classList.remove('dispatch-expanded'); });
})();
