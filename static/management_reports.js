document.addEventListener('DOMContentLoaded', () => {
  const source = document.getElementById('gestao-series');
  const canvas = document.getElementById('gestao-evolucao');
  if (!source || !canvas || !window.Chart) return;
  const data = JSON.parse(source.textContent);
  new Chart(canvas, {type:'line', data:{labels:data.labels, datasets:[
    {label:'Entradas', data:data.entradas, borderColor:'#176d63', backgroundColor:'#176d631a', tension:.15},
    {label:'Conclusões registradas', data:data.conclusoes, borderColor:'#759bac', backgroundColor:'#759bac1a', tension:.15}
  ]}, options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
    scales:{y:{beginAtZero:true,ticks:{precision:0}}},plugins:{legend:{position:'bottom'}}}});
});
