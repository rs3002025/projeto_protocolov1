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
