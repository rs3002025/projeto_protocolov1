// --- PDF Generation and Modal Functions ---
let protocoloParaGerar = null;

window.fecharModal = function(modalId) {
    const modalEl = document.getElementById(modalId);
    if(modalEl) {
        // Use Bootstrap's Modal API if available, otherwise fallback to style
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) {
            modalInstance.hide();
        } else {
            modalEl.style.display = 'none';
        }
    }
}

window.previsualizarPDF = async function(id = null, isFromForm = false) {
  let protocolo;
  if (isFromForm) {
      // This case is for the creation form
      protocolo = {
          numero: document.getElementById('numeroProtocolo')?.value,
          data_solicitacao: document.getElementById('dataSolicitacao')?.value,
          nome: document.getElementById('nome')?.value,
          matricula: document.getElementById('matricula')?.value,
          cpf: document.getElementById('cpf')?.value,
          rg: document.getElementById('rg')?.value,
          endereco: document.getElementById('endereco')?.value,
          bairro: document.getElementById('bairro')?.value,
          municipio: document.getElementById('municipio')?.value,
          cep: document.getElementById('cep')?.value,
          telefone: document.getElementById('telefone')?.value,
          cargo: document.getElementById('cargo')?.value,
          lotacao: document.getElementById('lotacao')?.value,
          unidade_exercicio: document.getElementById('unidade')?.value,
          tipo_requerimento: document.getElementById('tipo')?.value,
          requer_ao: document.getElementById('requerAo')?.value,
          observacoes: document.getElementById('complemento')?.value
      };
  } else {
      // This case is for existing protocols (from list or detail page)
      if (id === null) {
          alert('ID do protocolo não fornecido.');
          return;
      }
      try {
          const res = await fetch(`/api/protocolo/${id}`);
          if (!res.ok) {
              alert("Erro: Protocolo não encontrado ou falha na comunicação com o servidor.");
              return;
          }
          protocolo = await res.json();
      } catch (err) {
          console.error('Erro ao buscar dados do protocolo:', err);
          alert('Erro de conexão ao buscar dados do protocolo.');
          return;
      }
  }

  protocoloParaGerar = protocolo;
  const pdfContentDiv = document.getElementById('pdfContent');
  const modeloDiv = document.getElementById('modeloProtocolo');
  if (!pdfContentDiv || !modeloDiv) {
      console.error("Elementos do modal (#pdfContent) ou template (#modeloProtocolo) não encontrados no DOM.");
      return;
  }

  const clone = modeloDiv.cloneNode(true);
  clone.style.display = 'block';

  const qrcodeContainer = clone.querySelector('#qrcode-container');
  if (qrcodeContainer && protocolo.numero && protocolo.numero.includes('/')) {
      qrcodeContainer.innerHTML = '';
      const numeroParts = protocolo.numero.split('/');
      if (numeroParts.length === 2) {
          const urlConsulta = `${window.location.origin}/consulta/${numeroParts[1]}/${numeroParts[0]}`;
          try {
            new QRCode(qrcodeContainer, { text: urlConsulta, width: 90, height: 90, correctLevel: QRCode.CorrectLevel.H });
          } catch(e) { console.error("Erro ao gerar QRCode. A biblioteca está carregada?", e); }
      }
  }

  // Populate the template with data
  clone.querySelector('#doc_numero').textContent = protocolo.numero || 'A ser gerado';
  let dataTexto = protocolo.data_solicitacao ? new Date(protocolo.data_solicitacao + 'T00:00:00').toLocaleDateString('pt-BR') : new Date().toLocaleDateString('pt-BR');
  clone.querySelector('#doc_dataSolicitacao').textContent = dataTexto;
  clone.querySelector('#doc_nome').textContent = protocolo.nome || '';
  clone.querySelector('#doc_matricula').textContent = protocolo.matricula || '';
  clone.querySelector('#doc_cpf').textContent = protocolo.cpf || '';
  clone.querySelector('#doc_rg').textContent = protocolo.rg || '';
  clone.querySelector('#doc_endereco').textContent = protocolo.endereco || '';
  clone.querySelector('#doc_bairro').textContent = protocolo.bairro || '';
  clone.querySelector('#doc_municipio').textContent = protocolo.municipio || '';
  clone.querySelector('#doc_cep').textContent = protocolo.cep || '';
  clone.querySelector('#doc_telefone').textContent = protocolo.telefone || '';
  clone.querySelector('#doc_cargo').textContent = protocolo.cargo || '';
  clone.querySelector('#doc_lotacao').textContent = protocolo.lotacao || '';
  clone.querySelector('#doc_unidade').textContent = protocolo.unidade_exercicio || '';
  clone.querySelector('#doc_tipo').textContent = protocolo.tipo_requerimento || '';
  clone.querySelector('#doc_requerAo').textContent = protocolo.requer_ao || '';
  clone.querySelector('#doc_complemento').innerHTML = protocolo.observacoes ? protocolo.observacoes.replace(/\n/g, '<br>') : 'Nenhuma informação adicional.';

  pdfContentDiv.innerHTML = '';
  pdfContentDiv.appendChild(clone.querySelector('.pdf-body'));

  // Show the modal using Bootstrap's API
  const pdfModal = document.getElementById('pdfModal');
  if (pdfModal) {
      const modal = new bootstrap.Modal(pdfModal);
      modal.show();
  }
}

window.gerarPDF = async function() {
  if (!protocoloParaGerar) {
      alert("Nenhum protocolo selecionado para gerar PDF.");
      return;
  }
  const element = document.getElementById('pdfContent').querySelector('.doc-container');
  if (!element) {
      console.error("Elemento .doc-container não encontrado para gerar PDF.");
      return;
  }
  const opt = {
    margin: [0, 0, 0, 0],
    filename: `Protocolo_${(protocoloParaGerar.numero || 'Novo').replace(/[\/\\]/g, '-')}.pdf`,
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, scrollY: 0, useCORS: true },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
  };
  try {
    await html2pdf().set(opt).from(element).save();
    fecharModal('pdfModal');
  } catch (error) {
    console.error("Erro ao gerar PDF com html2pdf:", error);
    alert("Ocorreu um erro ao gerar o PDF.");
  }
}
