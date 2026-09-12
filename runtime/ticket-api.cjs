const crypto=require('node:crypto');
const users=new Map(),emails=new Map(),sessions=new Map();
const errorText='无效凭据';
function reply(res,status,value,headers={}){res.writeHead(status,{'Content-Type':'application/json',...headers});res.end(JSON.stringify(value));return true;}
function sid(req){const found=(req.headers.cookie||'').split(';').map(x=>x.trim()).find(x=>x.startsWith('audit_sid='));return found?found.slice(10):'';}
function login(res,user){const token=crypto.randomBytes(24).toString('hex');sessions.set(token,user.username.toLowerCase());return reply(res,200,{username:user.username},{'Set-Cookie':'audit_sid='+token+'; HttpOnly; SameSite=Lax; Path=/'});}
async function body(req){let text='';for await(const chunk of req){text+=chunk;if(text.length>16384)throw new Error('BodyLimit');}return JSON.parse(text||'{}');}
module.exports=async(req,res)=>{
 const url=new URL(req.url,'http://localhost');if(!url.pathname.startsWith('/api/'))return false;
 const current=users.get(sessions.get(sid(req)));
 if(req.method==='GET'&&url.pathname==='/api/session')return reply(res,200,{username:current?.username||null});
 if(req.method==='POST'&&url.pathname==='/api/logout'){sessions.delete(sid(req));return reply(res,200,{ok:true},{'Set-Cookie':'audit_sid=; Max-Age=0; HttpOnly; SameSite=Lax; Path=/'});}
 if(req.method!=='POST')return reply(res,404,{error:'Not found'});
 let data;try{data=await body(req);}catch{return reply(res,400,{error:'请求格式错误'});}
 if(url.pathname==='/api/register'){
  const username=String(data.username||'').trim(),email=String(data.email||'').trim(),password=String(data.password||'');
  const usernameKey=username.toLowerCase(),emailKey=email.toLowerCase();
  if(users.has(usernameKey))return reply(res,409,{error:'用户名已存在'});
  if(emails.has(emailKey))return reply(res,409,{error:'邮箱已存在'});
  if(!/^[A-Za-z0-9_-]{6,64}$/.test(username))return reply(res,400,{error:'用户名格式不正确'});
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))return reply(res,400,{error:'邮箱格式不正确'});
  if(password.length<8||!/[A-Z]/.test(password)||!/[a-z]/.test(password)||!/[0-9]/.test(password)||! /[^A-Za-z0-9]/.test(password))return reply(res,400,{error:'登录密码需包含大小写字母、数字及特殊字符，至少八位'});
  if(password!==String(data.confirmPassword||''))return reply(res,400,{error:'确认密码必须与登录密码一致'});
  if(!data.terms)return reply(res,400,{error:'请同意服务条款及隐私政策'});
  if(!String(data.documentNumber||'').trim())return reply(res,400,{error:'证件号码必填'});
  if(!data.name||!data.documentType||!data.discountType||!data.countryCode||!data.mobileNumber)return reply(res,400,{error:'请填写完整账户信息'});
  const salt=crypto.randomBytes(16).toString('hex'),hash=crypto.scryptSync(password,salt,32);
  const user={username,email,salt,hash};users.set(usernameKey,user);emails.set(emailKey,usernameKey);return login(res,user);
 }
 if(url.pathname==='/api/login'){
  const identifier=String(data.identifier||'').trim().toLowerCase(),password=String(data.password||'');
  const user=users.get(emails.get(identifier)||identifier);
  if(!user||!password)return reply(res,401,{error:errorText});
  const hash=crypto.scryptSync(password,user.salt,32);
  if(!crypto.timingSafeEqual(hash,user.hash))return reply(res,401,{error:errorText});
  return login(res,user);
 }
 return reply(res,404,{error:'Not found'});
};
