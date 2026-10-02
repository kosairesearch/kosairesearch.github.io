/* 리포트 본문 문단 자르기 — 글자 수(한글 170자 · 영문 320자) 예산, 문장 중간에서는 자르지 않는다(CLAUDE.md '리포트 본문 문단 자르는 방식').
   원래 실사이트 stock.html 에 손으로 쓴 함수 셋이었다. 2026-10-03 실사이트를 새 디자인으로 옮기며 stock.html 도 생성기 결과가 되어,
   그 원본을 이 파일로 옮겼다(글자 하나 바꾸지 않았다). scripts/build_stock_staging.py 가 실사이트 · 스테이징 stock.html 에 똑같이 넣고,
   staging/tests/same-paragraphs.test.mjs 가 두 페이지가 같은지 · 세 문장 방식으로 돌아가지 않았는지 본다. */
function splitSentences(p){
    // 문장 끝('다.'/'요.' 등 또는 .!?) + 공백 뒤에 구분자 삽입 후 분리.
    // 소수점(13.5)은 뒤에 공백이 없어 분리되지 않음.
    var SEP='⁣';
    var m=String(p)
      .replace(/([다요죠음함됨임]\.)\s+/g, '$1'+SEP)
      .replace(/([.!?])\s+(?=[A-Z가-힣"'(])/g, '$1'+SEP);
    return m.split(SEP).map(function(s){return s.trim();}).filter(Boolean);
  }
var PARA_KO=170, PARA_EN=320;
function chunkPara(p){
    var s=splitSentences(p);
    if(s.length<2) return [p];
    var budget=/[가-힣]/.test(p)?PARA_KO:PARA_EN;
    var out=[],cur='',i,nx;
    for(i=0;i<s.length;i++){
      nx = cur ? cur+' '+s[i] : s[i];
      if(cur && nx.length>budget){ out.push(cur); cur=s[i]; }
      else cur=nx;
    }
    if(cur) out.push(cur);
    // 마지막 조각이 한 줄짜리 외톨이로 남으면 앞 문단에 붙인다.
    if(out.length>1 && out[out.length-1].length < budget*0.35){
      out[out.length-2] += ' '+out.pop();
    }
    return out;
  }
function ps(t){
    t=String(t==null?'':t);
    if(!t.trim()) return '';
    var out=[];
    t.split(/\n\n+/).forEach(function(x){ chunkPara(x.trim()).forEach(function(c){ if(c)out.push(c); }); });
    return out.map(function(c){ return '<p>'+esc(c)+'</p>'; }).join('');
  }
