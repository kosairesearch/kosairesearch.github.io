/* ============================================================
   KOS ai — lightweight in-place i18n (KO ⇄ EN)
   Text-node level translation: dictionary keyed by visible
   Korean text (whitespace-normalized). No reload, reversible.
   - Injects a KO/EN toggle to the left of #themeBtn
   - localStorage('kos-lang')
   - Pages: KOSi18n.register(dict, onChange)
   - Dynamic (JS-rendered) regions: mark container [data-i18n-skip]
     and re-render with KOSi18n.t() inside the onChange callback.
   - Placeholders: add attribute data-i18n-ph to the input.
   ============================================================ */
(function(){
  const KEY='kos-lang';
  const dict={};                 // normalized KO -> EN
  const listeners=[];
  const txtOrig=new WeakMap();   // textNode -> original nodeValue
  const phOrig=new WeakMap();    // element  -> original placeholder
  const blockOrig=new WeakMap(); // element  -> {html, key}
  let lang='ko';

  function getLang(){ try{ return localStorage.getItem(KEY)||'ko'; }catch(e){ return 'ko'; } }
  function norm(s){ return s.replace(/\s+/g,' ').trim(); }

  function translateText(orig){
    const m=orig.match(/^(\s*)([\s\S]*?)(\s*)$/);
    const lead=m[1], core=norm(m[2]), trail=m[3];
    if(!core) return orig;
    const en=dict[core];
    return (en!=null)? (lead+en+trail) : orig;
  }

  function walk(node){
    if(node.nodeType===1){ // element
      const tag=node.tagName;
      if(tag==='SCRIPT'||tag==='STYLE'||tag==='NOSCRIPT') return;
      if(node.hasAttribute('data-i18n-skip')) return;
      if(node.hasAttribute('data-i18n-ph')){
        if(!phOrig.has(node)) phOrig.set(node, node.getAttribute('placeholder')||'');
        const ko=phOrig.get(node);
        node.setAttribute('placeholder', lang==='en' ? (dict[norm(ko)]||ko) : ko);
      }
      if(node.hasAttribute('data-i18n-block')){
        if(!blockOrig.has(node)) blockOrig.set(node, {html:node.innerHTML, key:norm(node.textContent||'')});
        const rec=blockOrig.get(node);
        if(lang==='en'){
          let en=dict[rec.key];
          if(en==null){
            // try with leading bull/bear marker stripped ("▲ X" / "▼ X" → "X")
            const stripped=rec.key.replace(/^[▲▼]\s*/,'');
            if(stripped!==rec.key && dict[stripped]!=null){
              const mk=rec.key.slice(0,1);
              en=mk+' '+dict[stripped];
            }
          }
          if(en!=null) node.textContent=en;
          else node.innerHTML=rec.html;
        } else {
          node.innerHTML=rec.html;
        }
        return;
      }
      for(let c=node.firstChild;c;c=c.nextSibling) walk(c);
    }else if(node.nodeType===3){ // text
      const v=node.nodeValue;
      if(!v || !v.trim()) return;
      if(!txtOrig.has(node)) txtOrig.set(node, v);
      const orig=txtOrig.get(node);
      node.nodeValue = (lang==='en') ? translateText(orig) : orig;
    }
  }

  function apply(){
    document.documentElement.setAttribute('lang', lang);
    if(document.body) walk(document.body);
    updateToggle();
  }

  function setLang(l){
    lang=l;
    try{ localStorage.setItem(KEY,l); }catch(e){}
    listeners.forEach(fn=>{ try{ fn(lang); }catch(e){} });  // let pages re-render dynamic parts first
    apply();
  }

  function t(ko){ return lang==='en' ? (dict[norm(ko)]!=null?dict[norm(ko)]:ko) : ko; }

  function register(d, onChange){
    if(d){ for(const k in d){ dict[norm(k)]=d[k]; } }
    if(onChange){ listeners.push(onChange); try{ onChange(lang); }catch(e){} }
    apply();
  }

  /* ---- toggle UI ---- */
  function buildToggle(){
    const theme=document.getElementById('themeBtn');
    if(!theme || document.getElementById('langToggle')) return;
    const wrap=document.createElement('div');
    wrap.id='langToggle';
    wrap.setAttribute('role','group');
    wrap.setAttribute('aria-label','Language');
    wrap.innerHTML='<button type="button" data-l="ko">KO</button><button type="button" data-l="en">EN</button>';
    theme.parentNode.insertBefore(wrap, theme);
    wrap.addEventListener('click',e=>{ const b=e.target.closest('button'); if(b) setLang(b.dataset.l); });
    if(!document.getElementById('langToggleStyle')){
      const st=document.createElement('style'); st.id='langToggleStyle';
      st.textContent=`
        #langToggle{display:inline-flex;gap:2px;padding:3px;border-radius:9999px;
          background:rgba(0,0,0,.05);margin-right:2px}
        :root[data-theme="dark"] #langToggle{background:rgba(255,255,255,.08)}
        #langToggle button{border:0;background:transparent;cursor:pointer;
          font:700 12px/1 var(--font-sans,"Pretendard",sans-serif);letter-spacing:.02em;
          color:var(--fg-3);padding:7px 10px;border-radius:9999px;transition:background .15s,color .15s}
        #langToggle button:hover{color:var(--fg-1)}
        #langToggle button.on{background:#000;color:#fff}
        :root[data-theme="dark"] #langToggle button.on{background:#fff;color:#000}`;
      document.head.appendChild(st);
    }
  }
  function updateToggle(){
    const wrap=document.getElementById('langToggle'); if(!wrap) return;
    wrap.querySelectorAll('button').forEach(b=>b.classList.toggle('on', b.dataset.l===lang));
  }

  function autoMarkBlocks(){
    // Treat each visually-distinct prose unit as a single translation block,
    // so inline <b>/<strong>/<span> highlights don't split text into pieces
    // the dictionary can't match.
    const sel='.prose p,.factor p,.tldr p,.kpoints li,.risk .body,.wrapup p,.lead,.desc,.sec-lead';
    document.querySelectorAll(sel).forEach(el=>{
      if(!el.hasAttribute('data-i18n-block')) el.setAttribute('data-i18n-block','');
    });
  }

  function init(){ lang=getLang(); buildToggle(); autoMarkBlocks(); listeners.forEach(fn=>{ try{ fn(lang); }catch(e){} }); apply(); }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
  else init();

  window.KOSi18n={ register, t, setLang, get lang(){return lang;}, apply };
})();
