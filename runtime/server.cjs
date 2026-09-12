const http=require('node:http'),fs=require('node:fs/promises'),path=require('node:path');
const api=require('./api.cjs'),base=path.resolve(__dirname,'../frontend/dist');
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'};
async function handle(req,res){
  try{
    if(await api(req,res)||res.writableEnded)return;
    const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    let file=path.resolve(base,'.'+pathname);
    if(file!==base&&!file.startsWith(base+path.sep)){res.writeHead(403);res.end();return;}
    if(file===base)file=path.join(base,'index.html');
    let body;
    try{body=await fs.readFile(file);}catch(error){
      if(path.extname(file)||pathname.startsWith('/api/')){res.writeHead(404);res.end();return;}
      file=path.join(base,'index.html');body=await fs.readFile(file);
    }
    res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream'});res.end(body);
  }catch(error){res.writeHead(500);res.end('Server error');console.error(error.name);}
}
const primary=Number(process.env.PORT||3000),secondary=Number(process.env.AUDIT_SECONDARY_PORT||3301);
const ports=primary===secondary?[primary]:[primary,secondary];
for(const port of ports){
  const server=http.createServer(handle);
  server.on('error',error=>{console.error(error.code);process.exit(1);});
  server.listen(port,process.env.AUDIT_BIND_ADDRESS||'0.0.0.0',()=>console.log(JSON.stringify({listening:server.address().port})));
}
