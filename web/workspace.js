const $=id=>document.getElementById(id);
let current=null,stream=null,poller=null,generation=0,shown=null;
const statuses={queued:'排队中',running:'调查中',completed:'已完成',partial:'部分完成',cancelled:'已取消',failed:'失败',interrupted:'已中断'};
const resumeButton=el('button','继续调查（使用新预算）','secondary');resumeButton.id='resumeTask';resumeButton.hidden=true;$('newTask').parentElement.append(resumeButton);
resumeButton.onclick=async()=>{resumeButton.disabled=true;try{const t=await api('/api/tasks/'+current+'/resume',{method:'POST'});await openTask(t.id)}catch(e){showError(e)}finally{resumeButton.disabled=false}};
const sourceKinds={readme:'README',documentation:'仓库文档',official_page:'官方文档网页',release:'发布说明',issue:'社区 Issue'};
const collectionStates={collected:'已采集',empty:'未发现资料',partial:'部分采集',failed:'采集失败'};
function sourceInfo(s){const m=s.metadata||{};return [s.kind==='issue'?'社区报告，未经独立验证；未含评论':'',m.state?'状态：'+m.state:'',m.updated_at?'更新：'+new Date(m.updated_at).toLocaleString():'',m.published_at?'发布：'+new Date(m.published_at).toLocaleString():'',s.ref?'版本：'+s.ref:''].filter(Boolean).join(' · ')}
const budgetLabel=el('label','本次 Token 预算（预估控制）');budgetLabel.htmlFor='tokenBudget';
const budgetInput=el('input','');budgetInput.id='tokenBudget';budgetInput.type='number';budgetInput.min='12000';budgetInput.max='200000';budgetInput.step='1000';budgetInput.value='60000';
$('mode').parentElement.append(budgetLabel,budgetInput);
const reviewLabel=el('label','');const reviewInput=el('input','');reviewInput.type='checkbox';reviewInput.id='verifyClaims';reviewInput.checked=true;reviewLabel.append(reviewInput,document.createTextNode(' 最终结论模型复核（可能增加一次调用）'));$('mode').parentElement.append(reviewLabel);
const judgments={supported:'支持',unsupported:'不支持',unknown:'未知',conflict:'冲突'};
function el(tag,text,cls){const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n}
async function api(url,options){const r=await fetch(url,options);if(!r.ok){const b=await r.json();throw Error(typeof b.detail==='string'?b.detail:JSON.stringify(b.detail))}return r.json()}
function selectView(name){for(const [key,tab,pane,nav]of [['report','tabReport','report','navReport'],['evidence','tabEvidence','evidencePane','navEvidence'],['sources','tabSources','sourcePane','navSources']]){$(pane).hidden=key!==name;$(tab).classList.toggle('active',key===name);$(tab).setAttribute('aria-selected',String(key===name));$(nav).classList.toggle('active',key===name)}}
for(const [name,tab,nav]of [['report','tabReport','navReport'],['evidence','tabEvidence','navEvidence'],['sources','tabSources','navSources']]){$(tab).onclick=$(nav).onclick=()=>selectView(name)}
function modeNote(){$('modeNote').textContent={demo:'使用三个虚构候选验证证据链；不代表真实模型能力。',github:'采集 README、仓库文档、发布记录与最近 Issues，不调用模型，功能判断保持未知。建议填写候选仓库。',deepseek:'需要本地环境变量中的密钥，调用会产生模型服务费用。'}[$('mode').value]}
$('mode').onchange=modeNote;
$('newTask').onclick=()=>{$('form').hidden=false;$('question').focus()};$('closeForm').onclick=()=>{$('form').hidden=true};
function render(r){shown=r;$('statRepos').textContent=new Set(r.assessments.map(a=>a.repository)).size;$('statEvidence').textContent=r.evidence.length;$('statCalls').textContent=r.metrics.tool_calls;$('resultMode').textContent={demo:'虚构样例 · 规则演示',github:'真实资料 · 未调用模型',deepseek:'真实模型调查'}[r.mode];const root=$('report');root.replaceChildren(el('div',r.summary,'report-summary'));const wrap=el('div','','table-wrap'),table=el('table'),head=el('tr');for(const t of ['候选项目','必须条件','判断','证据'])head.append(el('th',t));table.append(head);const req=Object.fromEntries(r.requirements.map(x=>[x.id,x.text]));for(const a of r.assessments){const row=el('tr'),repo=el('td',a.repository);if(r.excluded.includes(a.repository))repo.append(el('div','不满足硬性条件','note unsupported'));row.append(repo,el('td',req[a.requirement_id]));const status=el('td',judgments[a.status],a.status);status.title=a.explanation;row.append(status);const td=el('td');for(const id of a.evidence_ids){const link=el('a',id+' ');link.href='#'+id;link.onclick=e=>{e.preventDefault();selectView('evidence');const d=$(id);d.open=true;d.scrollIntoView({behavior:'smooth',block:'center'})};td.append(link)}row.append(td);table.append(row)}wrap.append(table);root.append(wrap,el('div',r.limitations.join(' '),'limit-note'));renderResearch(root,r,req);const sources=Object.fromEntries(r.sources.map(s=>[s.id,s]));const ep=$('evidencePane');ep.replaceChildren();for(const e of r.evidence){const s=sources[e.source_id],d=el('details');d.id=e.id;d.open=true;d.append(el('summary',e.id+' · '+s.repository+' · '+req[e.requirement_id]),el('blockquote',e.quote));if(!s.demo){const a=el('a','打开原始来源 ↗');a.href=s.url;a.target='_blank';a.rel='noopener noreferrer';d.append(a)}d.append(el('p',(s.demo?'虚构资料 · ':'')+'ref: '+s.ref+' · '+new Date(s.fetched_at).toLocaleString(),'muted note'));ep.append(d)}if(!r.evidence.length)ep.append(el('p','尚无可引用证据。仅采集资料时不会生成模型判断。','muted'));const sp=$('sourcePane');sp.replaceChildren();for(const s of r.sources){const d=el('details');d.append(el('summary',s.repository+' · '+(sourceKinds[s.kind]||'README')+' · '+(s.title||'README')+(s.demo?' · 虚构':'')+(s.truncated?' · 正文已截断':'')),el('p',sourceInfo(s),'muted note'),el('blockquote',s.text),el('p','SHA / 内容哈希：'+(s.sha||s.hash),'muted note'));if(!s.demo){const a=el('a','打开原始来源 ↗');a.href=s.url;a.target='_blank';a.rel='noopener noreferrer';d.append(a)}sp.append(d)}for(const c of r.collections||[]){sp.append(el('p',c.repository+' · '+(sourceKinds[c.kind]||c.kind)+' · '+(collectionStates[c.status]||c.status)+(c.error?' · '+c.error:''),'muted note'))}}
function trace(event){const labels={phase:'调查阶段',submitted:'报告提交',cache_hit:'复用查询',tool_error:'工具参数纠正',review:'检查证据缺口',followup:'定向补查',collection:'采集覆盖',plan:'规划调查',action:'调用工具',source:'读取资料',evidence:'保存证据',warning:'采集提示',model_usage:'模型调用',model_request:'模型请求',model_retry:'模型重试',cancelled:'任务停止'};const p=event.payload;const item=el('div','','trace-item');item.append(el('strong',labels[event.kind]||event.kind));let desc=p.message||p.tool||p.repository||(p.id+' · '+p.quote);if(event.kind==='model_request')desc='请求 '+p.attempt+' · '+p.elapsed_ms+' ms · 状态 '+(p.status||'连接失败');if(event.kind==='model_usage')desc='第 '+p.call+' 次模型请求';item.append(el('small',desc));const d=el('details');d.append(el('summary','查看记录'),el('pre',JSON.stringify(p,null,2)));item.append(d);$('logs').append(item);$('logs').scrollTop=$('logs').scrollHeight}
async function refresh(token=generation){if(!current)return;const id=current,t=await api('/api/tasks/'+id);if(token!==generation||id!==current)return;$('status').textContent=statuses[t.status]||t.status;const active=['queued','running'].includes(t.status);resumeButton.hidden=!t.resumable;$('cancel').hidden=!active;if(!active){clearInterval(poller);$('start').disabled=false;if(t.error)$('error').textContent=t.error;await history()}if(t.result&&JSON.stringify(t.result)!==JSON.stringify(shown)){render(t.result);for(const [id,format]of [['exportMd','markdown'],['exportJson','json']]){$(id).hidden=false;$(id).href='/api/tasks/'+current+'/export?format='+format}}}
async function openTask(id){const token=++generation;current=id;shown=null;clearInterval(poller);if(stream)stream.close();$('logs').replaceChildren();$('error').textContent='';$('form').hidden=true;$('exportMd').hidden=$('exportJson').hidden=true;$('statRepos').textContent=$('statEvidence').textContent=$('statCalls').textContent='—';selectView('report');$('report').replaceChildren(el('p','正在加载调查…','muted'));$('evidencePane').replaceChildren(el('p','等待证据','muted'));$('sourcePane').replaceChildren(el('p','等待资料','muted'));const t=await api('/api/tasks/'+id);if(token!==generation)return;$('taskTitle').textContent=t.request.question;$('taskSubtitle').textContent='任务 '+id.slice(0,8)+' · '+new Date(t.created).toLocaleString();$('question').value=t.request.question;$('requirements').value=t.request.requirements.map(r=>r.text).join('\n');$('repositories').value=t.request.repositories.join('\n');$('mode').value=t.request.mode;modeNote();const localStream=new EventSource('/api/tasks/'+id+'/events');stream=localStream;localStream.onmessage=e=>{if(token===generation)trace(JSON.parse(e.data))};localStream.addEventListener('finished',()=>{localStream.close();if(token===generation)refresh(token).catch(showError)});poller=setInterval(()=>refresh(token).catch(showError),900);await refresh(token)}
function showError(e){$('error').textContent=e.message}
async function history(){const list=await api('/api/tasks');$('history').replaceChildren();if(!list.length)$('history').append(el('p','还没有调查记录','muted note'));for(const t of list){const b=el('button',new Date(t.created).toLocaleString()+' · '+statuses[t.status]);b.onclick=()=>openTask(t.id).catch(showError);$('history').append(b)}}
$('form').onsubmit=async e=>{e.preventDefault();$('error').textContent='';$('start').disabled=true;try{const requirements=$('requirements').value.split('\n').map(s=>s.trim()).filter(Boolean).map((text,i)=>({id:'R'+(i+1),text,mandatory:true}));const repositories=$('repositories').value.split('\n').map(s=>s.trim()).filter(Boolean);const t=await api('/api/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('question').value,requirements,repositories,mode:$('mode').value,max_tokens:Number(budgetInput.value),verify_claims:reviewInput.checked})});await openTask(t.id)}catch(e){showError(e);$('start').disabled=false}};
$('cancel').onclick=async()=>{try{await api('/api/tasks/'+current+'/cancel',{method:'POST'});await refresh()}catch(e){showError(e)}};history().catch(showError);

function renderResearch(root,report,requirements){
  const metrics=report.metrics||{};
  root.append(el('p',`模型请求 ${metrics.model_requests||0} 次 · Token ${metrics.tokens?.total_tokens??'未记录'} · 查询缓存 ${metrics.cache_hits||0} 次`,'muted note'));
  if(report.completion)root.append(el('p',report.completion.type==='model_submitted'?'已完成最终模型提交':'部分报告：尚无有效最终提交','muted note'));
  if(report.verification?.length){
    const details=el('details');details.append(el('summary','证据检查：原文匹配与结论支持分开核验'));
    for(const check of report.verification){
      details.append(el('p',check.repository+' · '+requirements[check.requirement_id]+'：'+(check.quote_match===true?'摘录匹配原文':'暂无摘录')+'；语义支持待复核'));
      details.append(el('p','适用版本：'+(check.applicable_version||'未声明')+'；条件：'+(check.conditions||'未声明'),'muted note'));
      for(const warning of check.warnings)details.append(el('p',warning,'note'));
    }
    root.append(details);
  }
  if(report.semantic_review){
    const review=report.semantic_review;const labels={completed:'已执行',failed:'执行失败，需人工复核',skipped_budget:'预算不足，未执行'};
    root.append(el('p','模型语义复核：'+(labels[review.status]||review.status)+'（同模型独立提示，不代表事实保证）','muted note'));
    for(const v of review.verdicts||[])root.append(el('p',v.repository+' · '+requirements[v.requirement_id]+'：'+v.reason,'muted note'));
  }
  const research=report.research;
  if(!research)return;
  const section=el('section','','research-section');
  section.append(el('h3','证据缺口与补查'),el('p',`${research.gaps.length} 个待核实条目 · 已补查 ${research.rounds_used} / ${research.rounds_limit} 轮`,'muted'));
  const reasons={missing_evidence:'尚无引用证据',community_only:'只有社区反馈，需官方资料核实',conflict:'证据存在冲突',unresolved:'已有资料尚不足以判定'};
  if(report.mode==='github')section.append(el('p','当前仅采集资料；需模型分析或人工核实后才能更新判断。','muted note'));
  for(const gap of research.gaps){
    const d=el('div','','limit-note');
    d.append(el('strong',gap.repository+' · '+requirements[gap.requirement_id]),el('p',reasons[gap.reason]||gap.reason));
    section.append(d);
  }
  for(const change of research.changes)section.append(el('p',change.repository+' · '+requirements[change.requirement_id]+'：'+judgments[change.before]+' → '+judgments[change.after]+'（'+change.evidence_ids.join(', ')+')'));
  const states={collected:'已获取资料，需核实',empty:'未发现新资料',partial:'部分完成',failed:'读取失败',budget_exhausted:'预算耗尽',running:'进行中'};
  for(const round of research.followups){
    const d=el('details');d.append(el('summary','第 '+round.index+' 轮补查'));
    for(const action of round.actions)d.append(el('p',action.repository+' · '+requirements[action.requirement_id]+' · '+(action.document_path||action.query)+' · '+(states[action.status]||action.status)));
    section.append(d);
  }
  if(!research.gaps.length)section.append(el('p','当前没有结构性证据缺口；引用是否真正支持结论仍需复核。','muted'));
  root.append(section);
}

async function loadModelConfig(){
  try{const c=await api('/api/model/config');$('modelConfig').textContent=(c.configured?'已配置 · ':'未配置 · ')+c.model;$('testModel').disabled=!c.configured}
  catch(e){$('modelConfig').textContent=e.message;$('testModel').disabled=true}
}
$('refreshModel').onclick=()=>{$('modelTestResult').textContent='';loadModelConfig()};
$('testModel').onclick=async()=>{
  $('testModel').disabled=true;$('modelTestResult').textContent='正在检查认证和模型列表…';
  try{const r=await api('/api/model/test',{method:'POST'});$('modelTestResult').textContent=r.message+(r.model_available?'':'；可用模型：'+r.models.join('、'))}
  catch(e){$('modelTestResult').textContent=e.message}
  finally{await loadModelConfig()}
};
loadModelConfig();
