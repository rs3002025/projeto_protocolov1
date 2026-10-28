const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/script.js', 'utf8');
const helper = source.slice(source.indexOf('async function readJsonResponse'), source.indexOf("document.addEventListener('DOMContentLoaded'"));
const context = vm.createContext({});
vm.runInContext(helper, context);
const read = context.readJsonResponse;
test('JSON válido preserva o contrato de sucesso', async () => {
  assert.equal((await read(new Response('{"sucesso":true}', {headers:{'content-type':'application/json'}}))).sucesso,true);
});
for (const [code, body, type] of [[500,'<!doctype html>erro','text/html'],[400,'{"mensagem":"Confira os dados"}','application/json'],[401,'{"mensagem":"Sessão expirada"}','application/json'],[200,'invalid','application/json']]) {
  test(`resposta ${code}/${type} gera mensagem legível`, async () => {
    await assert.rejects(read(new Response(body,{status:code,headers:{'content-type':type}})), e=>!e.message.includes('Unexpected token') && e.message.length>5);
  });
}
test('redirecionamento para login não é interpretado como JSON', async()=>{
  await assert.rejects(read({redirected:true,status:200,headers:new Headers({'content-type':'text/html'})}),/sessão expirou/);
});

function loginFixture(fetch) {
  let submit, destination;
  const classes = new Set();
  const button = {disabled:false, classList:{add:c=>classes.add(c),remove:c=>classes.delete(c)},
    setAttribute(){},removeAttribute(){}};
  const feedback = {hidden:true, textContent:'',focus(){}};
  const form = {action:'https://dev.example/login',querySelector:s=>s.includes('feedback')?feedback:button,
    addEventListener:(_,fn)=>{submit=fn}};
  const scope = vm.createContext({fetch, FormData:class {},AbortController,URL,setTimeout:()=>1,clearTimeout(){},
    document:{querySelector:()=>form},
    DOMParser:class {parseFromString(html){return {querySelector:()=>html.includes('senha incorreta')?{textContent:'Login ou senha incorreta.'}:null}}},
    window:{location:{href:form.action,origin:'https://dev.example',assign:url=>{destination=url}}}});
  vm.runInContext(helper,scope); scope.initializeLoginForm();
  return {button,feedback,classes,run:()=>submit({preventDefault(){}}),destination:()=>destination};
}
test('senha incorreta mostra erro e encerra carregamento sem redirecionar', async()=>{
  const f=loginFixture(async()=>new Response('senha incorreta',{status:200}));
  await f.run();
  assert.match(f.feedback.textContent,/senha incorreta/);
  assert.equal(f.feedback.hidden,false); assert.equal(f.button.disabled,false);
  assert.equal(f.classes.size,0); assert.equal(f.destination(),undefined);
});
test('falha ou demora da rede encerra carregamento e permite nova tentativa',async()=>{
  for(const error of [new Error('Conexão indisponível'),Object.assign(new Error('timeout'),{name:'AbortError'})]){
    const f=loginFixture(async()=>{throw error}); await f.run();
    assert.equal(f.button.disabled,false); assert.equal(f.classes.size,0); assert.equal(f.feedback.hidden,false);
  }
});
test('login correto segue o redirecionamento do servidor',async()=>{
  const f=loginFixture(async()=>({redirected:true,ok:true,url:'https://dev.example/plataforma'}));
  await f.run(); assert.equal(f.destination(),'https://dev.example/plataforma');
});
test('consulta de matrícula não apaga dados por ausência, falha ou resposta atrasada',async()=>{
  const fields={matricula:{value:'QA'},nome:{value:'Digitado manualmente'}};
  let resolveFetch, fills=0;
  const scope=vm.createContext({console:{error(){}},document:{getElementById:id=>fields[id]},
    fetch:()=>new Promise(resolve=>{resolveFetch=resolve}),readJsonResponse:async r=>r.json(),
    preencherCamposServidor:()=>{fills++}});
  vm.runInContext(source.slice(source.indexOf('let matriculaRequestSerial'),source.indexOf('async function fetchCep()')),scope);
  let task=scope.fetchServidorByMatricula(); resolveFetch({status:404}); await task; assert.equal(fills,0);
  task=scope.fetchServidorByMatricula(); fields.nome.value='Corrigido durante a consulta';
  resolveFetch({status:200,json:async()=>({nome:'Nome da consulta'})}); await task; assert.equal(fills,0);
  task=scope.fetchServidorByMatricula(); fields.matricula.value='OUTRA';
  resolveFetch({status:200,json:async()=>({nome:'Nome da consulta'})}); await task; assert.equal(fills,0);
  task=scope.fetchServidorByMatricula(); resolveFetch({status:200,json:async()=>({nome:'Nome confirmado'})});
  await task; assert.equal(fills,1);
});
