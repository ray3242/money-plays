// Real protocol client for tests: node bot.js <mcport> <httpport> <version> [name]
// HTTP: /chat?m=<text>  -> send chat/command ; /events -> JSON of chat lines + particle counts since last call
const mineflayer=require('mineflayer'),http=require('http'),url=require('url')
const [mcport,hport,version,name='Bot']=process.argv.slice(2)
const bot=mineflayer.createBot({host:'127.0.0.1',port:+mcport,username:name,version,auth:'offline'})
let raw=[],chat=[],particles={},pp=[],ready=false,sounds=[]
bot.on('spawn',()=>{ready=true})
bot.on('message',(m,pos)=>{raw.push(JSON.stringify(m.json))});bot.on('message',(m,pos)=>chat.push((pos==='game_info'?'[actionbar] ':'')+m.toString()))
for(const n of ['action_bar','set_action_bar_text'])bot._client.on(n,p=>chat.push('[actionbar] '+JSON.stringify(p.text??p)))
bot._client.on('world_particles',p=>{const k=JSON.stringify(p.particle?.type??p.particleId)+(p.particle?.data?JSON.stringify(p.particle.data):'');particles[k]=(particles[k]||0)+1;if(pp.length<4000)pp.push([k,+p.x.toFixed(2),+p.y.toFixed(2),+p.z.toFixed(2)])})
bot._client.on('sound_effect',p=>sounds.push(p.soundId??p.soundEvent))
bot.on('kicked',r=>{console.log('kicked',r);process.exit(1)});bot.on('error',e=>console.log('err',e.message))
http.createServer((q,r)=>{const u=url.parse(q.url,true)
 if(u.pathname==='/chat'){bot.chat(u.query.m);r.end('ok')}
 else if(u.pathname==='/events'){const p=bot.entity?.position;r.end(JSON.stringify({ready,pos:p&&[p.x,p.y,p.z],dim:bot.game?.dimension,chat,raw,particles,sounds,pp:u.query.pp?pp:undefined}));chat=[];raw=[];particles={};pp=[];sounds=[]}
 else r.end('?')}).listen(+hport,'127.0.0.1')
