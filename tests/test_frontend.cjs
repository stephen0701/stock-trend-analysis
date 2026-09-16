const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'app/index.html'), 'utf8');
const code = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
function run(value, bad = true) {
 const elements = {};
 const context = {window:{}, document:{getElementById:id=>elements[id] ||= {textContent:'',innerHTML:''},querySelectorAll:()=>[]}, localStorage:{getItem:()=>JSON.stringify([{ticker:'NVDA',shares:2,price:100}])}};
 vm.createContext(context);
 vm.runInContext(fs.readFileSync(path.join(root,'app/data.js'),'utf8'),context);
 if(bad) for(const s of Object.values(context.window.APP_DATA.stocks)) {s.close[s.close.length-1]=value; s.dayHigh=value;}
 vm.runInContext(code, context);
 assert(!/NaN|非數值|Infinity/.test(elements.screen.innerHTML));
 if(bad) assert(elements.screen.innerHTML.includes('暫不判定趨勢'));
 if(bad) {vm.runInContext("renderDetail('NVDA')",context); assert(elements.screen.innerHTML.includes('暫不判定趨勢'));}
 vm.runInContext('renderPortfolio()',context);
 assert(!/NaN|非數值|Infinity/.test(elements.screen.innerHTML));
 if(bad) assert(elements.screen.innerHTML.includes('總市值與總損益暫不計算'));
}
run(null, false); run(NaN); run(Infinity); run(null); run("bad");
console.log('Frontend valid and invalid quote rendering: PASS');
