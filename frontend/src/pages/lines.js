import {jobs,lines} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {LineOrderStatus,HandoverSide} from '../constants/enums.js';

const canWrite=()=>session.user.role!=='viewer';
const canAdmin=()=>session.user.role==='admin';
const lineStatus=v=>'<span class="line-status '+esc(v)+'">'+esc(LineOrderStatus[v]||v)+'</span>';

function basisText(o){
 const b=o.basis||{};
 return '<p class="basis">依据：<a href="#/results/'+b.job_id+'">'+esc(b.job_name||('任务 #'+b.job_id))+'</a> · '+esc(b.team||o.team)+' 配对 '+esc(b.paired_count??'—')+' 人 · 平均节省 '+esc(b.team_avg_saving??'—')+' 秒 · 参数 '+esc(JSON.stringify(b.params||{}))+'</p><p class="hint">'+esc(b.summary||'')+'</p>';
}

function orderCard(o,detailed=false){
 const hs=o.handovers||[],from=hs.find(h=>h.side==='from'),to=hs.find(h=>h.side==='to');
 const active=o.status==='pending';
 const sides='<div class="handover-sides"><div><span>原线交还 · '+esc(o.from_line)+'</span>'+(from?'<strong>已确认 '+esc(from.actor)+' · '+esc(from.receipt_id)+'</strong><small>'+date(from.recorded_at)+'</small>':'<em>待回执</em>')+'</div><div><span>新线接收 · '+esc(o.to_line)+'</span>'+(to?'<strong>已确认 '+esc(to.actor)+' · '+esc(to.receipt_id)+'</strong><small>'+date(to.recorded_at)+'</small>':'<em>待回执</em>')+'</div></div>';
 const forms=active&&canWrite()?'<div class="handover-forms">'+['from','to'].filter(s=>!(s==='from'?from:to)).map(s=>'<form class="handover-form" data-order="'+o.id+'" data-side="'+s+'"><label>'+esc(HandoverSide[s])+'回执编号<input name="receipt_id" required minlength="8" value="'+esc(receiptSeed(o.id,s))+'"></label><label>经办备注<input name="note" maxlength="300" placeholder="交接位置、现场确认"></label><button type="submit" class="small">确认'+esc(HandoverSide[s])+'</button></form>').join('')+'</div>':'';
 const cancel=(o.status==='pending'||o.status==='effective')&&canAdmin()?'<button class="text-button" data-cancel="'+o.id+'" data-status="'+esc(o.status)+'">'+(o.status==='pending'?'作废换线单':'撤销并走反向交接')+'</button><form class="cancel-form" data-order="'+o.id+'" data-status="'+esc(o.status)+'" hidden><label>撤单原因<input name="reason" required minlength="2" maxlength="300" placeholder="'+(o.status==='pending'?'未生效，直接作废':'已生效，将另开反向交接单')+'"></label><button class="small" type="submit">确认'+(o.status==='pending'?'作废':'反向交接')+'</button></form>':'';
 return '<article class="line-order '+(detailed?'detailed':'')+'"><div class="line-order-head"><div><strong>换线单 #'+o.id+' · '+esc(o.team)+'</strong><p>'+esc(o.from_line)+' → '+esc(o.to_line)+'</p></div>'+lineStatus(o.status)+'</div>'+basisText(o)+(o.note?'<p class="hint">备注：'+esc(o.note)+'</p>':'')+sides+(o.status==='voided'?'<p class="warning">已作废：'+esc(o.cancel_reason||'')+'</p>':'')+(o.status==='reversing'?'<p class="warning">已生效后撤销，待反向单交接完成：'+esc(o.cancel_reason||'')+'</p>':'')+(o.status==='reversed'||o.reverse_of?'<p class="hint">关联单据：'+(o.reverse_of?'原单 #'+o.reverse_of+' · ':'')+(o.reverse_order_id?'反向单 #'+o.reverse_order_id:'')+'</p>':'')+forms+'<div class="line-order-foot">'+cancel+'<a class="text-button" href="#/lines/'+o.id+'">查看交接依据 ↗</a></div></article>';
}

// 回执编号按单据+侧固定生成：页面刷新或断线重试提交同一编号，服务端只记一次。
function receiptSeed(orderId,side){return 'HO-'+orderId+'-'+side.toUpperCase();}

export async function linePage(id){
 const [board,orders,allJobs]=await Promise.all([lines.board(),lines.list(),jobs.list()]);
 workspace.lineBoard=board;workspace.lineOrders=orders;
 const approved=allJobs.filter(j=>j.approved&&j.status==='completed');
 const detail=id&&/^\d+$/.test(String(id))?await lines.get(id):null;
 const teams=board.map(b=>b.team);
 const createForm='<section class="panel"><div class="section-title"><h2>开班组换线单</h2><span>依据已批准复测结论</span></div><form id="line-form"><div class="parameter-grid"><label>试点小组<select name="team" required>'+teams.map(t=>'<option>'+esc(t)+'</option>').join('')+'</select></label><label>换至新线<input name="to_line" required maxlength="40" placeholder="例如：新线 B"></label></div><label>复测结论（已完成且获批准）<select name="job_id" required>'+approved.map(j=>'<option value="'+j.id+'">'+esc(j.name)+' · '+esc(j.params?.team||'')+'</option>').join('')+'</select></label><label>换线备注<input name="note" maxlength="300" placeholder="现场条件、交接窗口"></label><button type="submit" class="primary" '+(canWrite()&&approved.length?'':'disabled')+'>保存待交接单</button><p class="hint">同组同时只能有一张待交接单；相反指令由先开单占用，后者须等前单完成或作废。原线在新线接收、原线交还都确认前继续执行。</p></form></section>';
 const boardRows=board.map(b=>{const p=b.pending_order;return '<article class="board-row"><div><strong>'+esc(b.team)+'</strong><p>当前路线：'+esc(b.current_line)+'</p><small>'+(b.updated_at?'更新 '+date(b.updated_at):'尚未换线，沿用原线')+'</small></div><div>'+(p?'<span class="line-status pending">待交接 #'+p.id+' → '+esc(p.to_line)+'</span>':'<span class="line-status effective">无待交接</span>')+(b.effective_order?'<small>最近生效 #'+b.effective_order.id+' · '+date(b.effective_order.effective_at)+'</small>':'')+'</div><a class="text-button" href="#/lines'+(p?'/'+p.id:'')+'">'+(p?'去交接 ↗':'查依据 ↗')+'</a></article>';}).join('');
 return heading('05 / LINE HANDOVER','班组换线与交接','按已批准复测结论开单。原线交还与新线接收都确认后才切换路线，之前仍走原线。','<button class="button" id="refresh-lines">刷新路线 ↻</button>')+
  '<section class="panel board"><div class="section-title"><h2>当前路线与待交接</h2><span>'+board.length+' 个试点小组</span></div><div class="board-list">'+boardRows+'</div></section>'+
  (detail?'<section class="panel detail"><div class="section-title"><h2>交接依据 · 换线单 #'+detail.id+'</h2><span>当前路线 '+esc(detail.current_line)+'</span></div>'+orderCard({...detail,handovers:detail.handovers},true)+'<div class="section-title"><h2>交接回执</h2><span>同一回执重试只生效一次</span></div>'+(detail.handovers.length?'<div class="table-wrap"><table><thead><tr><th>侧</th><th>回执编号</th><th>路线</th><th>经办</th><th>备注</th><th>登记时间</th></tr></thead><tbody>'+detail.handovers.map(h=>'<tr><td>'+esc(HandoverSide[h.side])+'</td><td>'+esc(h.receipt_id)+'</td><td>'+esc(h.line)+'</td><td>'+esc(h.actor)+'</td><td>'+esc(h.note||'—')+'</td><td>'+date(h.recorded_at)+'</td></tr>').join('')+'</tbody></table></div>':'<p class="empty">尚未收到交接回执。</p>')+'<div class="section-title"><h2>单据链</h2><span>原单与反向单</span></div>'+detail.chain.map(o=>'<article class="chain-row"><strong>#'+o.id+' '+esc(o.team)+'</strong><span>'+esc(o.from_line)+' → '+esc(o.to_line)+'</span>'+lineStatus(o.status)+'</article>').join(''):'')+
  '<div class="line-grid">'+createForm+'<section><div class="section-title"><h2>换线单记录</h2><span>'+orders.length+' 张</span></div><div class="line-orders">'+(orders.length?orders.map(o=>orderCard(o)).join(''):'<p class="empty">尚无换线单。选择已批准结论开单后在此交接。</p>')+'</div></section></div>';
}

export function bindLines(refresh){
 document.querySelector('#refresh-lines').onclick=refresh;
 const form=document.querySelector('#line-form');
 if(form)submit(form,async f=>{const o=await lines.create({team:f.get('team'),to_line:f.get('to_line'),job_id:Number(f.get('job_id')),note:f.get('note')||''});notify('已生成待交接换线单 #'+o.id+'，原线继续执行');location.hash='#/lines/'+o.id;});
 document.querySelectorAll('.handover-form').forEach(el=>submit(el,async f=>{const out=await lines.handover(Number(el.dataset.order),{side:el.dataset.side,receipt_id:f.get('receipt_id'),note:f.get('note')||''});notify(out.idempotent?'该回执此前已生效，未重复交接':(out.switched?'两侧交接完成，班组已切换至「'+out.to_line+'」':'回执已登记，尚需另一侧确认'));await refresh();}));
 document.querySelectorAll('[data-cancel]').forEach(b=>b.onclick=()=>{const form=document.querySelector('.cancel-form[data-order="'+b.dataset.cancel+'"]');form.hidden=!form.hidden;if(!form.hidden)form.querySelector('input').focus();});
 document.querySelectorAll('.cancel-form').forEach(el=>submit(el,async f=>{const effective=el.dataset.status==='effective';try{const out=await lines.cancel(Number(el.dataset.order),{reason:String(f.get('reason')).trim()});notify(out.cancel_mode==='reverse'?'已生效，已生成反向交接单 #'+out.reverse_order_id:'未生效，换线单已作废');await refresh();}catch(e){notify(e.message,true);}}));
}
