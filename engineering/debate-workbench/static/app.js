import {markdown, escapeHTML as esc} from "./markdown.mjs";
const $ = id => document.getElementById(id);
const show = (id,on=true) => $(id).classList.toggle("hidden",!on);
const phases=["辩题分析","资料整合","立论架构","论据手册","攻防模拟"];
const phaseEnglish=["ANALYZE","RESEARCH","BUILD","SUPPORT","CHALLENGE"];
let current=null, selectedDoc=0, view="document", busy=false, pollTimer=null, config=null, reworkTarget=null;
let navigation=0;
const saved = {
  get(k){try{return localStorage.getItem((config?.workspace||"unassigned")+":"+k);}catch{return null;}},
  set(k,v){try{localStorage.setItem((config?.workspace||"unassigned")+":"+k,v);}catch{}},
  remove(k){try{localStorage.removeItem((config?.workspace||"unassigned")+":"+k);}catch{}}
};
async function api(path,body) {
  let response;
  try {response=await fetch(path,{method:body?"POST":"GET",headers:body?{"Content-Type":"application/json","X-Debate-Client":"workbench","X-CSRF-Token":config?.csrf||""}:{},body:body?JSON.stringify(body):undefined});}
  catch {throw Error("无法连接工作台，请检查网络或服务是否仍在运行。");}
  let data;
  try {data=await response.json();}catch{throw Error("工作台返回了异常响应。");}
  if(!response.ok)throw Error(data.error || (response.status===422?"请检查辩题、持方或输入长度。":"操作失败，请稍后重试。"));
  return data;
}
let toastTimer;
function toast(text){$("toast").textContent=text;show("toast");clearTimeout(toastTimer);toastTimer=setTimeout(()=>show("toast",false),5000);}
function phaseNav() {
  $("phase-nav").innerHTML=phases.map((name,i)=>{
    const done=current?.documents[i].state==="已确认";
    const active=current && current.step.phase===i;
    return '<button class="phase-button '+(active?"active ":"")+(done?"done":"")+'" '+(!current?"disabled":"")+' data-phase="'+i+'"><span class="phase-dot">'+(done?"✓":String(i+1).padStart(2,"0"))+'</span><span>'+name+'<small>'+phaseEnglish[i]+'</small></span></button>';
  }).join("");
  $("phase-nav").querySelectorAll("[data-phase]").forEach(button=>button.onclick=()=>{
    selectedDoc=Number(button.dataset.phase);setTab("document");
    $("workspace").classList.remove("no-preview");$("toggle-preview").textContent="收起文档";
    if(window.innerWidth<=900)$("preview").scrollIntoView({behavior:"smooth"});
  });
}
function setTab(tab) {
  view=tab;
  $("document-tab").classList.toggle("selected",tab==="document");
  $("sources-tab").classList.toggle("selected",tab==="sources");
  show("document-content",tab==="document");show("doc-controls",tab==="document");show("doc-status",tab==="document");show("sources-content",tab==="sources");
  renderPreview();
}
function emptyDocument(title,description){return '<div class="empty-doc"><div class="empty-icon">▤</div><h3>'+esc(title)+'</h3><p>'+esc(description)+'</p></div>';}
function renderPreview() {
  if(!current)return;
  const doc=current.documents[selectedDoc];
  $("document-select").innerHTML=current.documents.map((d,i)=>'<option value="'+i+'">'+esc(d.name)+'</option>').join("");
  $("document-select").value=String(selectedDoc);
  $("doc-status").textContent=doc.state+" · "+(doc.available?doc.content.length.toLocaleString()+" 字符":"讨论结果将自动整理到这里");
  $("document-content").innerHTML=doc.available?markdown(doc.content,current.sources):emptyDocument("思考正在成形","完成本阶段讨论后，这里会出现你的备赛文档。");
  $("download-current").disabled=!doc.available;
  $("rework-button").disabled=busy||current.status==="running"||!current.steps.some((step,i)=>step.phase===selectedDoc&&i<=current.index&&current.nodes[step.key]);
  $("source-count").textContent=String(current.sources.length);
  $("sources-content").innerHTML=current.sources.length?current.sources.map(s=>'<article class="source-card"><small>['+esc(s.id)+'] · '+esc(s.status)+'</small><a href="'+esc(s.url)+'" target="_blank" rel="noopener noreferrer">'+esc(s.title)+'</a><p>'+esc(s.snippet)+'</p><span class="source-domain">'+esc(s.url)+'</span></article>').join(""):emptyDocument("来源，先求证再引用","确认搜索方案后，会在这里列出实际检索的网页与获取状态。");
}
function render() {
  if(!current)return;
  show("home",false);show("workspace");show("export-button");show("toggle-preview");
  $("breadcrumb").textContent="备赛工作台";
  $("session-topic").textContent=current.topic;
  const metadata=[current.side,current.format||"未指定赛制",...(current.date?[current.date]:[]),Math.min(current.index,current.steps.length)+"/"+current.steps.length+" 节点已确认"];
  $("session-meta").innerHTML=metadata.map(v=>"<span>"+esc(v)+"</span>").join("");
  $("step-number").textContent=String(Math.min(current.index+1,current.steps.length)).padStart(2,"0");
  $("step-title").textContent=current.step.title;
  const running=current.status==="running", complete=current.status==="complete";
  $("step-status").textContent=({running:"处理中",waiting:"等待你的判断",error:"需重试",paused:"已暂停",complete:"已完成"})[current.status]||"准备中";
  const conversation=$("timeline");
  const nearBottom=conversation.scrollHeight-conversation.scrollTop-conversation.clientHeight<180;
  // Show current-node conversation; previous chapters remain available in the document pane.
  const history=current.history.filter(h=>h.step===current.step.key);
  $("timeline").innerHTML=history.map(h=>h.role==="event"?'<div class="message event">'+esc(h.text)+'</div>':'<article class="message '+esc(h.role)+'"><div class="message-label">'+(h.role==="assistant"?'<span class="coach-avatar">↗</span> AI 教练 · '+esc(current.step.title):"你")+'</div><div class="message-body '+(h.role==="assistant"?"markdown":"")+'">'+(h.role==="assistant"?markdown(h.text,current.sources):esc(h.text))+'</div></article>').join("");
  if(!history.length&&!complete)$("timeline").innerHTML=emptyDocument(running?"正在打开新的思路":"准备继续本节点","从问题出发，一步一步完善你的立论。");
  show("running-box",running);
  $("running-label").textContent=current.step.search?"正在检索、阅读并整合资料":"AI 教练正在分析与整理";
  show("task-error",Boolean(current.error));$("task-error").textContent=current.error||"";
  show("resume-box",["error","paused"].includes(current.status));
  $("resume-label").textContent=current.status==="paused"?"已暂停。正在发出的 API 请求仍可能计费。":"之前的内容已保存。";
  const node=current.nodes[current.step.key];
  show("plan-box",!!current.step.plan&&!!node?.queries?.length&&!running);
  $("plan-box").innerHTML=node?.queries?.length?"<b>确认后将实际检索</b><ol>"+node.queries.map(q=>"<li>"+esc(q)+"</li>").join("")+"</ol>":"";
  show("confirm-box",current.status==="waiting"&&!!node?.ready);
  $("confirm-button").textContent=current.index===current.steps.length-1?"确认并完成备赛 ✓":"确认并继续 →";
  show("complete-box",complete);show("reply-form",!complete);show("search-form",!complete&&current.step.search);
  $("reply").disabled=running||busy;$("send-button").disabled=running||busy||!$("reply").value.trim();
  $("confirm-button").disabled=busy;$("pause-button").disabled=busy;$("retry-button").disabled=busy;
  $("search-form").querySelectorAll("input,button").forEach(e=>e.disabled=busy||running);
  phaseNav();renderPreview();
  if(nearBottom)requestAnimationFrame(()=>{conversation.scrollTop=conversation.scrollHeight;});
}
function schedulePoll(){
  clearTimeout(pollTimer);
  if(!current)return;
  pollTimer=setTimeout(async()=>{
    const sid=current?.id;
    try {
      const data=await api("/api/sessions/"+sid);
      if(current?.id===sid && data.revision!==current.revision){
        const changed=data.index!==current.index;
        current=data;if(changed)selectedDoc=data.step.phase;render();
      }
    }catch(e){if(current?.id===sid)toast(e.message);}
    schedulePoll();
  },current.status==="running"?1800:6000);
}
async function openSession(sid){
  const request=++navigation;
  try {
    const data=await api("/api/sessions/"+sid);
    if(request!==navigation)return;
    current=data;selectedDoc=data.step.phase;saved.set("debate.current",sid);
    $("reply").value=saved.get("debate.draft."+sid)||"";
    history.replaceState(null,"","#"+sid);render();schedulePoll();
  }catch(e){toast(e.message);}
}
function goHome(){
  navigation++;current=null;clearTimeout(pollTimer);saved.remove("debate.current");
  history.replaceState(null,"",location.pathname);show("home");show("workspace",false);show("export-button",false);show("toggle-preview",false);
  $("breadcrumb").textContent="新建备赛";phaseNav();refreshList();$("topic").focus();
}
async function act(action,text="",target=null){
  if(busy||!current)return false;
  busy=true;render();
  const sid=current.id, revision=current.revision;
  try {
    const data=await api("/api/sessions/"+sid+"/action",{action,revision,text,target});
    if(current?.id===sid){current=data;selectedDoc=data.step.phase;render();schedulePoll();}
    return true;
  }catch(e){
    toast(e.message);
    if(current?.id===sid){try{current=await api("/api/sessions/"+sid);}catch{}}
    return false;
  }finally{busy=false;if(current?.id===sid)render();}
}
async function refreshList(){
  try{
    const list=await api("/api/sessions");$("session-count").textContent=String(list.length);
    $("history-list").innerHTML=list.length?list.map(s=>'<button class="history-item" data-session="'+s.id+'"><span><b>'+esc(s.topic)+'</b><small>'+esc(s.side)+" · "+new Date(s.updated).toLocaleDateString("zh-CN")+" · "+(s.index===16?"已完成":s.index+"/16 节点")+'</small></span><span>↗</span></button>').join(""):emptyDocument("还没有备赛档案","从一个辩题开始，你的每次讨论都会保存在这里。");
    $("history-list").querySelectorAll("[data-session]").forEach(b=>b.onclick=()=>{$("history-dialog").close();openSession(b.dataset.session);});
  }catch(e){toast(e.message);}
}
async function historyDialog(){await refreshList();$("history-dialog").showModal();}
function download(kind){if(current){const link=document.createElement("a");link.href="/api/sessions/"+current.id+"/download/"+kind;link.download="";document.body.append(link);link.click();link.remove();}}
function exportsDialog(){
  if(!current)return;
  $("export-note").textContent=current.status==="complete"?"五份阶段文档、合并总稿与来源记录，随时带到赛场。":"备赛尚未全部完成，下载文件会标明草稿、需更新或待生成状态。";
  $("export-files").innerHTML=current.documents.map((d,i)=>'<button data-download="'+i+'"><span>'+esc(d.name)+'</span><small>'+d.state+' ↓</small></button>').join("");
  $("export-files").querySelectorAll("[data-download]").forEach(b=>b.onclick=()=>download(b.dataset.download));
  $("export-dialog").showModal();
}
$("setup-form").onsubmit=async event=>{
  event.preventDefault();if(busy)return;if(!config?.configured){openSettings();return;}
  busy=true;$("start-button").disabled=true;$("start-button").textContent="正在创建…";show("setup-error",false);
  try{
    const data=await api("/api/sessions",Object.fromEntries(new FormData(event.target)));
    current=data;selectedDoc=0;$("reply").value="";saved.set("debate.current",data.id);history.replaceState(null,"","#"+data.id);
    busy=false;render();schedulePoll();refreshList();
  }catch(e){$("setup-error").textContent=e.message;show("setup-error");}
  finally{busy=false;$("start-button").disabled=false;$("start-button").textContent="开始备赛 ↗";}
};
$("topic").oninput=()=>{$("topic-count").textContent=$("topic").value.length+" / 600";saved.set("debate.topic",$("topic").value);};
$("reply").oninput=()=>{if(current)saved.set("debate.draft."+current.id,$("reply").value);$("send-button").disabled=busy||current?.status==="running"||!$("reply").value.trim();};
$("reply-form").onsubmit=async event=>{
  event.preventDefault();const text=$("reply").value.trim();if(!text)return;
  const sid=current.id;
  if(await act("reply",text)){if(current?.id===sid){$("reply").value="";saved.remove("debate.draft."+sid);render();}}
};
$("reply").onkeydown=e=>{if(e.key==="Enter"&&(e.ctrlKey||e.metaKey)){e.preventDefault();$("reply-form").requestSubmit();}};
$("search-form").onsubmit=async e=>{e.preventDefault();if(await act("search",$("search-query").value))$("search-query").value="";};
$("confirm-button").onclick=()=>act("confirm");$("pause-button").onclick=()=>act("pause");$("retry-button").onclick=()=>act("retry");
$("new-session").onclick=goHome;
document.querySelectorAll(".brand,.mobile-home").forEach(link=>link.onclick=event=>{event.preventDefault();goHome();});
$("history-button").onclick=historyDialog;$("mobile-history").onclick=historyDialog;
$("document-tab").onclick=()=>setTab("document");$("sources-tab").onclick=()=>setTab("sources");
$("document-select").onchange=()=>{selectedDoc=Number($("document-select").value);renderPreview();};
$("toggle-preview").onclick=()=>{const hidden=$("workspace").classList.toggle("no-preview");$("toggle-preview").textContent=hidden?"显示文档":"收起文档";};
$("export-button").onclick=exportsDialog;$("complete-export").onclick=exportsDialog;
$("download-current").onclick=()=>download(selectedDoc);$("download-zip").onclick=()=>download("zip");$("download-merged").onclick=()=>download("merged");
$("rework-button").onclick=()=>{reworkTarget=current.steps.findIndex((s,i)=>s.phase===selectedDoc&&i<=current.index);$("rework-dialog").showModal();};
$("rework-confirm").onclick=async()=>{$("rework-dialog").close();await act("rework","",reworkTarget);};
function connectionState(){
  $("model-name").textContent=config.configured?"模型已连接":"连接你的模型";
  $("connection-status").textContent=config.configured?"已连接 · "+new Date(config.expires*1000).toLocaleTimeString("zh-CN",{hour:"2-digit",minute:"2-digit"})+" 到期":"尚未连接 · 使用你自己的 API";
  $("connection-status").classList.toggle("connected",config.configured);
  show("disconnect-button",config.configured);
  $("mode-label").textContent=config.mode==="remote"?"SHARED":"LOCAL";
  $("storage-title").textContent=config.mode==="remote"?"独立访客空间":"本机工作空间";
  $("storage-note").textContent=config.mode==="remote"?"档案保存在此站点的服务器":"档案保存在这台电脑";
  $("workspace-notice").textContent=(config.mode==="remote"?"档案保存在此站点服务器的独立空间。":"档案保存在这台电脑的独立空间。")+"此版本通过浏览器 Cookie 识别你；清除 Cookie 或更换浏览器后无法找回原空间，请及时下载。";
}
async function openSettings(){
  try{config=await api("/api/config");connectionState();show("connection-error",false);$("settings-dialog").showModal();}
  catch(e){toast(e.message);}
}
$("settings-button").onclick=openSettings;
$("mobile-settings").onclick=openSettings;
let connecting=false;
async function connect(operation){
  if(connecting||!$("connection-form").reportValidity())return;
  connecting=true;show("connection-error",false);
  $("test-connection").disabled=true;$("save-connection").disabled=true;
  $("save-connection").textContent=operation==="connect"?"正在连接…":"正在测试…";
  const payload={protocol:$("api-protocol").value,base:$("api-base").value,model:$("api-model").value,key:$("api-key").value};
  try{
    const result=await api("/api/connection/"+operation,payload);
    Object.assign(config,result);connectionState();toast(result.message);
    if(operation==="connect"){$("api-key").value="";$("settings-dialog").close();show("setup-error",false);}
  }catch(e){$("connection-error").textContent=e.message;show("connection-error");}
  finally{payload.key="";connecting=false;$("test-connection").disabled=false;$("save-connection").disabled=false;$("save-connection").textContent="连接模型 ↗";}
}
$("connection-form").onsubmit=e=>{e.preventDefault();connect("connect");};
$("test-connection").onclick=()=>connect("test");
$("disconnect-button").onclick=async()=>{
  try{Object.assign(config,await api("/api/disconnect",{}));$("api-key").value="";connectionState();if(current)await openSession(current.id);toast("已断开，已保存的档案仍可下载。");}
  catch(e){toast(e.message);}
};
$("settings-dialog").addEventListener("close",()=>{$("api-key").value="";});
let theme;
try{theme=localStorage.getItem("debate.theme");}catch{}
document.documentElement.dataset.theme=theme||"light";
$("theme-button").onclick=()=>{
  const value=document.documentElement.dataset.theme==="dark"?"light":"dark";
  document.documentElement.dataset.theme=value;
  try{localStorage.setItem("debate.theme",value);}catch{}
};
document.querySelectorAll("[data-close]").forEach(b=>b.onclick=()=>$(b.dataset.close).close());
document.querySelectorAll("dialog").forEach(d=>d.addEventListener("click",e=>{if(e.target===d){const rect=d.getBoundingClientRect();if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)d.close();}}));
document.addEventListener("keydown",e=>{if(e.key.toLowerCase()==="n"&&!["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName)&&!document.querySelector("dialog[open]")&&!e.ctrlKey&&!e.metaKey){goHome();}});
window.addEventListener("hashchange",()=>{const sid=location.hash.slice(1);if(/^[a-f0-9]{32}$/.test(sid))openSession(sid);else goHome();});
async function boot(){
  phaseNav();
  try{
    config=await api("/api/config");connectionState();
    $("topic").value=saved.get("debate.topic")||"";$("topic").oninput();
    await refreshList();
    const sid=location.hash.slice(1)||saved.get("debate.current");
    if(sid&&/^[a-f0-9]{32}$/.test(sid))await openSession(sid);
  }catch(e){toast(e.message);}
}
setInterval(async()=>{
  if(document.hidden||connecting)return;
  try{config=await api("/api/config");connectionState();}catch{}
},30000);
boot();
