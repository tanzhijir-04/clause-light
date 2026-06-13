# -*- coding: utf-8 -*-
import json, os

base = r'C:\Users\20300\Desktop\clause-light\designs\contract-annotated-view'
data = json.load(open(os.path.join(base, 'data.json'), 'r', encoding='utf-8'))

contract_json = json.dumps(data, ensure_ascii=False)

html = '''<!DOCTYPE html>
<html lang="zh" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>\u5408\u540c\u539f\u6587\u6807\u6ce8\u89c6\u56fe</title>
<style>
:root,[data-theme="light"]{--bg-app:#fff;--bg-sidebar:#f7f7f5;--bg-surface:#fff;--bg-surface-hover:#f7f7f5;--bg-muted:#f1f1ef;--text-primary:#1a1a1a;--text-secondary:#6b6b6b;--text-tertiary:#9b9b9b;--border-default:#e8e8e5;--border-strong:#d4d4d0;--border-subtle:#f0f0ee;--accent:#2383e2;--accent-subtle:#e8f0fe;--risk-red:#e53e3e;--risk-red-bg:#fff5f5;--risk-red-text:#c53030;--risk-red-border:#fed7d7;--risk-yellow:#d69e2e;--risk-yellow-bg:#fffff0;--risk-yellow-text:#b7791f;--risk-yellow-border:#fefcbf;--risk-green:#38a169;--risk-green-bg:#f0fff4;--risk-green-text:#276749;--risk-green-border:#c6f6d5;--shadow-sm:0 1px 3px rgba(0,0,0,.06);--shadow-lg:0 10px 15px rgba(0,0,0,.06);--sp-2:8px;--sp-3:12px;--sp-4:16px;--sp-5:20px;--sp-6:24px;--sp-8:32px;--radius-sm:4px;--radius-md:6px;--radius-lg:8px;--radius-full:9999px;--font-sans:Inter,-apple-system,SF Pro Text,PingFang SC,Noto Sans SC,system-ui,sans-serif;--text-xs:11px;--text-sm:13px;--text-base:14px;--text-md:15px;--text-lg:18px;--text-xl:24px;--text-2xl:30px}
[data-theme="dark"]{--bg-app:#191919;--bg-sidebar:#202020;--bg-surface:#232323;--bg-surface-hover:#2a2a2a;--bg-muted:#2a2a2a;--text-primary:#ebebeb;--text-secondary:#999;--text-tertiary:#666;--border-default:#333;--border-strong:#444;--border-subtle:#2a2a2a;--accent:#529cca;--accent-subtle:#1a2a35;--risk-red:#fc8181;--risk-red-bg:#2d1b1b;--risk-red-text:#feb2b2;--risk-red-border:#5c3030;--risk-yellow:#f6e05e;--risk-yellow-bg:#2d2b1b;--risk-yellow-text:#faf089;--risk-yellow-border:#5c5530;--risk-green:#68d391;--risk-green-bg:#1b2d1f;--risk-green-text:#9ae6b4;--risk-green-border:#305c3a;--shadow-sm:0 1px 3px rgba(0,0,0,.3);--shadow-lg:0 10px 15px rgba(0,0,0,.4)}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden}
body{font-family:var(--font-sans);font-size:var(--text-base);line-height:1.6;color:var(--text-primary);background:var(--bg-app);-webkit-font-smoothing:antialiased}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--border-strong);border-radius:3px}
button{font-family:inherit;border:none;background:none;cursor:pointer;color:inherit;outline:none}
.app{display:flex;height:100vh;overflow:hidden}
.sidebar{width:240px;min-width:240px;height:100vh;display:flex;flex-direction:column;background:var(--bg-sidebar);border-right:1px solid var(--border-default);flex-shrink:0}
.sidebar-header{display:flex;align-items:center;gap:12px;padding:20px}
.sidebar-logo{width:32px;height:32px;border-radius:6px;background:linear-gradient(135deg,#38a169,#2383e2);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:#fff}
.sidebar-title{font-size:15px;font-weight:600}
.sidebar-nav{flex:1;padding:0 8px}
.sidebar-nav-item{display:flex;align-items:center;gap:12px;padding:8px 12px;border-radius:6px;color:var(--text-secondary);font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.sidebar-nav-item:hover{background:rgba(0,0,0,.04);color:var(--text-primary)}
.sidebar-nav-item.active{background:rgba(35,131,226,.08);color:var(--text-primary)}
.sidebar-section-label{padding:8px 12px;font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0}
.topbar{padding:20px 24px 12px;flex-shrink:0;border-bottom:1px solid var(--border-subtle)}
.topbar-row{display:flex;align-items:center;justify-content:space-between;gap:16px}
.topbar-title{font-size:24px;font-weight:700;letter-spacing:-.03em}
.topbar-subtitle{font-size:13px;color:var(--text-secondary);margin-top:2px}
.view-tabs{display:flex;border-bottom:1px solid var(--border-default);margin-top:16px}
.view-tab{padding:12px 16px;font-size:13px;font-weight:500;color:var(--text-secondary);cursor:pointer;border-bottom:2px solid transparent;transition:all .15s;margin-bottom:-1px;user-select:none;display:flex;align-items:center;gap:8px}
.view-tab:hover{color:var(--text-primary)}.view-tab.active{color:var(--text-primary);border-bottom-color:var(--accent)}
.risk-dist{display:flex;height:6px;border-radius:3px;overflow:hidden;gap:2px;cursor:pointer}
.risk-dist-seg{height:100%;border-radius:3px;transition:opacity .15s}
.risk-dist-seg.red{background:var(--risk-red)}.risk-dist-seg.yellow{background:var(--risk-yellow)}.risk-dist-seg.green{background:var(--risk-green)}
.risk-dist-seg:hover{opacity:.8}.risk-dist-seg.dim{opacity:.3}
.risk-nav{display:flex;align-items:center;gap:8px}
.risk-nav-btn{display:flex;align-items:center;gap:4px;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:500;border:1px solid var(--border-default);background:var(--bg-surface);color:var(--text-secondary);transition:all .15s}
.risk-nav-btn:hover:not(:disabled){background:var(--bg-surface-hover);color:var(--text-primary);border-color:var(--border-strong)}
.risk-nav-btn:disabled{opacity:.4;cursor:not-allowed}
.risk-nav-count{font-size:11px;color:var(--text-tertiary);min-width:60px;text-align:center}
.content-area{flex:1;display:flex;overflow:hidden;position:relative}
.original-text{flex:1;overflow-y:auto;padding:24px 32px;font-size:15px;line-height:1.9;scroll-behavior:smooth;white-space:pre-wrap}
.clause-mark{position:relative;cursor:pointer;transition:all .15s;border-left:3px solid transparent;padding-left:12px;margin-left:-3px;border-radius:0 4px 4px 0;display:inline}
.clause-mark.red{background:rgba(229,62,62,.12);border-left-color:var(--risk-red)}
.clause-mark.yellow{background:rgba(214,158,46,.10);border-left-color:var(--risk-yellow)}
.clause-mark:hover{filter:brightness(.95)}
.clause-mark.active{box-shadow:0 0 0 2px var(--accent);z-index:1;position:relative}
.clause-mark .clause-label{position:absolute;top:-10px;right:8px;font-size:10px;font-weight:600;padding:1px 6px;border-radius:9999px;opacity:0;transition:opacity .15s;pointer-events:none}
.clause-mark:hover .clause-label,.clause-mark.active .clause-label{opacity:1}
.clause-mark.red .clause-label{background:var(--risk-red);color:#fff}
.clause-mark.yellow .clause-label{background:var(--risk-yellow);color:#fff}
.annotation-panel{width:400px;min-width:400px;border-left:1px solid var(--border-default);background:var(--bg-surface);display:flex;flex-direction:column;overflow:hidden;transition:width .25s ease,min-width .25s ease,opacity .2s ease}
.annotation-panel.collapsed{width:0;min-width:0;opacity:0;border-left:none}
.anno-header{padding:16px 20px;border-bottom:1px solid var(--border-subtle);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;gap:8px}
.anno-close{width:28px;height:28px;display:flex;align-items:center;justify-content:center;border-radius:6px;color:var(--text-tertiary);transition:all .15s;font-size:16px}
.anno-close:hover{background:var(--bg-surface-hover);color:var(--text-primary)}
.anno-risk-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:600}
.anno-risk-badge.red{background:var(--risk-red-bg);color:var(--risk-red-text);border:1px solid var(--risk-red-border)}
.anno-risk-badge.yellow{background:var(--risk-yellow-bg);color:var(--risk-yellow-text);border:1px solid var(--risk-yellow-border)}
.anno-risk-badge.green{background:var(--risk-green-bg);color:var(--risk-green-text);border:1px solid var(--risk-green-border)}
.anno-body{flex:1;overflow-y:auto;padding:20px}
.anno-section{margin-bottom:20px}
.anno-section-title{font-size:11px;font-weight:600;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}
.anno-section-content{font-size:13px;line-height:1.7;color:var(--text-primary);white-space:pre-wrap}
.anno-section-content.legal{color:var(--text-secondary);font-style:italic}
.anno-section-content.suggest{color:var(--accent);background:var(--accent-subtle);padding:12px;border-radius:6px;border-left:3px solid var(--accent)}
.severity-bar{display:flex;align-items:center;gap:8px;margin-top:8px}
.severity-blocks{display:flex;gap:2px}
.severity-block{width:16px;height:8px;border-radius:2px;background:var(--border-default)}
.severity-text{font-size:11px;color:var(--text-tertiary);margin-left:8px}
.clause-list-view{flex:1;overflow-y:auto;padding:24px 32px}
.clause-card{border-left:3px solid var(--border-default);padding:16px 20px;margin-bottom:12px;background:var(--bg-surface);border-radius:0 6px 6px 0;border-top:1px solid var(--border-subtle);border-right:1px solid var(--border-subtle);border-bottom:1px solid var(--border-subtle);cursor:pointer;transition:all .15s}
.clause-card:hover{background:var(--bg-surface-hover);box-shadow:var(--shadow-sm)}
.clause-card.red{border-left-color:var(--risk-red)}.clause-card.yellow{border-left-color:var(--risk-yellow)}.clause-card.green{border-left-color:var(--risk-green)}
.clause-card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.clause-card-num{font-weight:600;font-size:15px}
.clause-card-title{font-size:13px;color:var(--text-secondary);margin-bottom:8px}
.clause-card-summary{font-size:13px}
@media(max-width:1024px){.sidebar{display:none}.annotation-panel{width:100%!important;min-width:100%!important;position:absolute;bottom:0;left:0;right:0;height:50%;border-left:none;border-top:1px solid var(--border-default);border-radius:8px 8px 0 0;z-index:10;box-shadow:var(--shadow-lg)}.annotation-panel.collapsed{height:0;width:100%!important;min-width:100%!important}.original-text{padding:16px}}
@media(max-width:768px){.topbar{padding:12px 16px 8px}.topbar-title{font-size:18px}.annotation-panel{height:60%}.original-text{padding:12px;font-size:14px}}
@keyframes slideUp{from{transform:translateY(20px);opacity:0}to{transform:translateY(0);opacity:1}}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}.animate-in{animation:fadeIn .2s ease-out}
</style>
</head>
<body>
<div id="root"></div>
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" crossorigin="anonymous"></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" crossorigin="anonymous"></script>
<script type="text/babel">
const{useState,useEffect,useRef,useCallback}=React;
const C=''' + contract_json + ''';
function rl(l){return l==='red'?'\\u9ad8\\u98ce\\u9669':l==='yellow'?'\\u4e2d\\u98ce\\u9669':'\\u4f4e\\u98ce\\u9669'}
function Sidebar(){
  const nav=[['dashboard','\\u4eea\\u8868\\u76d8'],['contracts','\\u5408\\u540c\\u7ba1\\u7406'],['knowledge','\\u77e5\\u8bc6\\u5e93'],['sync','\\u540c\\u6b65\\u7ba1\\u7406'],['settings','\\u8bbe\\u7f6e'],['models','\\u6a21\\u578b\\u7ba1\\u7406']];
  return React.createElement('div',{className:'sidebar'},
    React.createElement('div',{className:'sidebar-header'},React.createElement('div',{className:'sidebar-logo'},'CL'),React.createElement('div',{className:'sidebar-title'},'\\u5408\\u540c\\u7ea2\\u7eff\\u706f')),
    React.createElement('div',{className:'sidebar-nav'},
      React.createElement('div',{className:'sidebar-section-label'},'\\u5bfc\\u822a'),
      ...nav.map(([id,label])=>React.createElement('div',{key:id,className:'sidebar-nav-item'+(id==='contracts'?' active':'')},React.createElement('span',{className:'nav-icon',style:{width:18,height:18}},id==='contracts'?'\\ud83d\\udcc4':id==='dashboard'?'\\ud83d\\udcca':id==='knowledge'?'\\ud83d\\udcda':id==='sync'?'\\ud83d\\udd04':id==='settings'?'\\u2699\\ufe0f':'\\ud83d\\udce6'),React.createElement('span',null,label)))
    ),
    React.createElement('div',{style:{padding:'16px 20px',borderTop:'1px solid var(--border-default)',fontSize:'11px',color:'var(--text-tertiary)',display:'flex',alignItems:'center',gap:8}},React.createElement('span',{style:{width:7,height:7,borderRadius:'50%',background:'var(--risk-green)'}}),'\\u670d\\u52a1\\u8fd0\\u884c\\u4e2d')
  );
}
function RiskDist({red,yellow,green,filter,onFilter}){
  const t=red+yellow+green;
  return React.createElement('div',{style:{display:'flex',alignItems:'center',gap:'var(--sp-3)'}},
    React.createElement('div',{className:'risk-dist',style:{flex:1}},
      red>0&&React.createElement('div',{className:'risk-dist-seg red'+(filter&&filter!=='red'?' dim':''),style:{width:(red/t)*100+'%'},onClick:()=>onFilter(filter==='red'?null:'red')}),
      yellow>0&&React.createElement('div',{className:'risk-dist-seg yellow'+(filter&&filter!=='yellow'?' dim':''),style:{width:(yellow/t)*100+'%'},onClick:()=>onFilter(filter==='yellow'?null:'yellow')}),
      green>0&&React.createElement('div',{className:'risk-dist-seg green'+(filter&&filter!=='green'?' dim':''),style:{width:(green/t)*100+'%'},onClick:()=>onFilter(filter==='green'?null:'green')})
    ),
    React.createElement('div',{style:{display:'flex',gap:12,fontSize:'11px',color:'var(--text-secondary)',whiteSpace:'nowrap'}},
      React.createElement('span',{style:{color:'var(--risk-red)',fontWeight:filter==='red'?700:400,cursor:'pointer'},onClick:()=>onFilter(filter==='red'?null:'red')},'\\u7ea2 '+red),
      React.createElement('span',{style:{color:'var(--risk-yellow)',fontWeight:filter==='yellow'?700:400,cursor:'pointer'},onClick:()=>onFilter(filter==='yellow'?null:'yellow')},'\\u9ec4 '+yellow),
      React.createElement('span',{style:{color:'var(--risk-green)',fontWeight:filter==='green'?700:400,cursor:'pointer'},onClick:()=>onFilter(filter==='green'?null:'green')},'\\u7eff '+green)
    )
  );
}
function AnnoPanel({clause,onClose}){
  if(!clause)return React.createElement('div',{className:'annotation-panel collapsed'});
  const sv=clause.severityScore||0;const svc=sv>=7?'var(--risk-red)':sv>=4?'var(--risk-yellow)':'var(--risk-green)';
  return React.createElement('div',{className:'annotation-panel',style:{animation:'slideUp .2s ease-out'}},
    React.createElement('div',{className:'anno-header'},
      React.createElement('div',{style:{display:'flex',alignItems:'center',gap:8,minWidth:0}},
        React.createElement('span',{className:'anno-risk-badge '+clause.riskLevel},clause.riskLevel==='red'?'\\ud83d\\udd34':clause.riskLevel==='yellow'?'\\ud83d\\udfe1':'\\ud83d\\udfe2',rl(clause.riskLevel)),
        React.createElement('span',{style:{fontSize:'13px',fontWeight:600,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}},clause.clauseTitle)
      ),
      React.createElement('button',{className:'anno-close',onClick:onClose},'\\u2715')
    ),
    React.createElement('div',{className:'anno-body'},
      clause.riskSummary&&React.createElement('div',{className:'anno-section'},React.createElement('div',{className:'anno-section-title'},'\\u95ee\\u9898\\u63cf\\u8ff0'),React.createElement('div',{className:'anno-section-content'},clause.riskSummary)),
      clause.plainExplanation&&React.createElement('div',{className:'anno-section'},React.createElement('div',{className:'anno-section-title'},'\\u901a\\u4fd7\\u89e3\\u91ca'),React.createElement('div',{className:'anno-section-content'},clause.plainExplanation)),
      clause.legalBasis&&React.createElement('div',{className:'anno-section'},React.createElement('div',{className:'anno-section-title'},'\\u6cd5\\u5f8b\\u4f9d\\u636e'),React.createElement('div',{className:'anno-section-content legal'},clause.legalBasis)),
      clause.suggestedClause&&React.createElement('div',{className:'anno-section'},React.createElement('div',{className:'anno-section-title'},'\\u4fee\\u6539\\u5efa\\u8bae'),React.createElement('div',{className:'anno-section-content suggest'},clause.suggestedClause)),
      React.createElement('div',{className:'anno-section'},React.createElement('div',{className:'anno-section-title'},'\\u4e25\\u91cd\\u5ea6'),
        React.createElement('div',{className:'severity-bar'},
          React.createElement('div',{className:'severity-blocks'},...Array.from({length:10}).map((_,i)=>React.createElement('div',{key:i,className:'severity-block',style:i<sv?{background:svc}:{}}))),
          React.createElement('span',{className:'severity-text'},sv+'/10')
        )
      ),
      clause.riskLevel!=='green'&&React.createElement('div',{className:'anno-section',style:{display:'flex',gap:8}},
        React.createElement('button',{style:{padding:'4px 12px',borderRadius:'6px',fontSize:'11px',fontWeight:500,border:'1px solid var(--border-default)',background:'var(--bg-surface)',color:'var(--text-secondary)',cursor:'pointer'}},'\\u2713 \\u6807\\u6ce8\\u51c6\\u786e'),
        React.createElement('button',{style:{padding:'4px 12px',borderRadius:'6px',fontSize:'11px',fontWeight:500,border:'1px solid var(--border-default)',background:'var(--bg-surface)',color:'var(--text-secondary)',cursor:'pointer'}},'\\u2717 \\u6807\\u6ce8\\u4e0d\\u51c6\\u786e')
      )
    )
  );
}
function AnnotatedView({contract,onSelect,activeId}){
  const ref=useRef(null);
  useEffect(()=>{if(!ref.current)return;const el=ref.current.querySelector('.clause-mark.red');if(el)setTimeout(()=>el.scrollIntoView({behavior:'smooth',block:'center'}),300)},[]);
  if(!contract)return null;const text=contract.fullText;const clauses=contract.clauses||[];
  let segs=[];clauses.forEach(c=>{const ct=c.clauseContent;if(!ct)return;const parts=ct.split('\\n').filter(p=>p.trim().length>10);
    for(const p of parts){const t=p.trim();const idx=text.indexOf(t);if(idx!==-1){const last=parts[parts.length-1].trim();const li=text.lastIndexOf(last);segs.push({start:idx,end:li!==-1?li+last.length:idx+t.length,clause:c});break}}});
  segs.sort((a,b)=>a.start-b.start);const els=[];let cur=0;
  segs.forEach((s,i)=>{if(s.start>cur)els.push(React.createElement('span',{key:'t'+i},text.slice(cur,s.start)));
    if(s.start>=cur){els.push(React.createElement('span',{key:'c'+i,className:'clause-mark '+s.clause.riskLevel+(activeId===s.clause.id?' active':''),onClick:()=>onSelect(s.clause)},React.createElement('span',{className:'clause-label'},s.clause.clauseNumber),text.slice(s.start,s.end)));cur=s.end}});
  if(cur<text.length)els.push(React.createElement('span',{key:'tail'},text.slice(cur)));
  return React.createElement('div',{className:'original-text',ref,lang:'zh'},...els);
}
function ListView({contract,onSelect}){
  if(!contract)return null;
  return React.createElement('div',{className:'clause-list-view animate-in'},
    ...contract.clauses.map(c=>React.createElement('div',{key:c.id,className:'clause-card '+c.riskLevel,onClick:()=>onSelect(c)},
      React.createElement('div',{className:'clause-card-header'},React.createElement('span',{className:'clause-card-num'},c.clauseNumber),React.createElement('span',{className:'anno-risk-badge '+c.riskLevel},rl(c.riskLevel))),
      React.createElement('div',{className:'clause-card-title'},c.clauseTitle),
      React.createElement('div',{className:'clause-card-summary'},c.riskSummary),
      c.suggestedClause&&React.createElement('div',{style:{fontSize:'13px',color:'var(--accent)',background:'var(--accent-subtle)',padding:8,borderRadius:'6px',marginTop:8}},'\\u4fee\\u6539\\u5efa\\u8bae\\uff1a'+c.suggestedClause.slice(0,80)+'...'),
      c.legalBasis&&React.createElement('div',{style:{fontSize:'11px',color:'var(--text-tertiary)',marginTop:8}},'\\u6cd5\\u5f8b\\u4f9d\\u636e\\uff1a'+c.legalBasis.slice(0,60)+'...')
    ))
  );
}
function App(){
  const[view,setView]=useState('annotated');const[active,setActive]=useState(null);const[filter,setFilter]=useState(null);const[theme,setTheme]=useState('light');
  const ct=C;const rc=ct.clauses.filter(c=>c.riskLevel==='red'||c.riskLevel==='yellow');const idx=active?rc.findIndex(c=>c.id===active.id):-1;
  const sel=useCallback(c=>{setActive(c);setView('annotated')},[]);
  const sc=ct.score>=70?'var(--risk-green)':ct.score>=50?'var(--risk-yellow)':'var(--risk-red)';
  return React.createElement('div',{className:'app'},
    React.createElement(Sidebar,null),
    React.createElement('div',{className:'main'},
      React.createElement('div',{className:'topbar'},
        React.createElement('div',{className:'topbar-row'},
          React.createElement('div',{style:{display:'flex',alignItems:'center',gap:12}},React.createElement('button',{style:{display:'flex',alignItems:'center',gap:4,padding:'4px 8px',borderRadius:'6px',fontSize:'13px',color:'var(--text-secondary)',cursor:'pointer'}},'\\u2190 \\u8fd4\\u56de')),
          React.createElement('div',{style:{display:'flex',alignItems:'center',gap:12}},
            React.createElement('div',{className:'risk-nav'},
              React.createElement('button',{className:'risk-nav-btn',onClick:()=>{if(idx>0)setActive(rc[idx-1])},disabled:idx<=0},'\\u25b2 \\u4e0a\\u4e00\\u6761'),
              React.createElement('span',{className:'risk-nav-count'},active?(idx+1)+' / '+rc.length:rc.length+' \\u6761\\u98ce\\u9669'),
              React.createElement('button',{className:'risk-nav-btn',onClick:()=>{if(idx<rc.length-1)setActive(rc[idx+1])},disabled:idx>=rc.length-1},'\\u4e0b\\u4e00\\u6761 \\u25bc')
            ),
            React.createElement('button',{onClick:()=>{const n=theme==='light'?'dark':'light';setTheme(n);document.documentElement.setAttribute('data-theme',n)},style:{width:32,height:32,display:'flex',alignItems:'center',justifyContent:'center',borderRadius:'6px',border:'1px solid var(--border-default)',background:'var(--bg-surface)',color:'var(--text-secondary)',cursor:'pointer'}},theme==='light'?'\\ud83c\\udf19':'\\u2600\\ufe0f')
          )
        ),
        React.createElement('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'flex-end',marginTop:8}},
          React.createElement('div',null,React.createElement('div',{className:'topbar-title'},ct.title),React.createElement('div',{className:'topbar-subtitle'},ct.type+' \\u00b7 '+ct.createdAt)),
          React.createElement('div',{style:{display:'flex',alignItems:'center',gap:16}},React.createElement('span',{className:'anno-risk-badge '+ct.riskLevel},rl(ct.riskLevel)),React.createElement('span',{style:{fontSize:'30px',fontWeight:700,color:sc,letterSpacing:'-.03em'}},ct.score))
        ),
        React.createElement('div',{style:{marginTop:12}},React.createElement(RiskDist,{red:ct.redCount,yellow:ct.yellowCount,green:ct.greenCount,filter,onFilter:setFilter})),
        React.createElement('div',{className:'view-tabs'},
          React.createElement('div',{className:'view-tab'+(view==='list'?' active':''),onClick:()=>setView('list')},'\\u2630 \\u6761\\u6b3e\\u5217\\u8868'),
          React.createElement('div',{className:'view-tab'+(view==='annotated'?' active':''),onClick:()=>setView('annotated')},'\\ud83d\\udcdd \\u539f\\u6587\\u6807\\u6ce8')
        )
      ),
      React.createElement('div',{className:'content-area'},
        view==='annotated'
          ?React.createElement(React.Fragment,null,React.createElement(AnnotatedView,{contract:ct,onSelect:sel,activeId:active?active.id:null}),React.createElement(AnnoPanel,{clause:active,onClose:()=>setActive(null)}))
          :React.createElement(React.Fragment,null,React.createElement(ListView,{contract:ct,onSelect:sel}),React.createElement(AnnoPanel,{clause:active,onClose:()=>setActive(null)}))
      )
    )
  );
}
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));
</script>
</body>
</html>'''

out_path = os.path.join(base, 'annotated-view.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print('Written', os.path.getsize(out_path), 'bytes to', out_path)
