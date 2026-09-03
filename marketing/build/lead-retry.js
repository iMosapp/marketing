/* Lead form resilience: POST /api/demo-requests gets a 20s timeout per try and is retried after 2s and 5s
   on network errors or 5xx (a deploy restart, a flaky connection). 4xx is never retried. */
(function(){
  if(window.__imosLeadRetry)return;window.__imosLeadRetry=true;
  var of=window.fetch;if(!of)return;
  var waits=[0,2000,5000];
  function sleep(ms){return new Promise(function(r){setTimeout(r,ms);});}
  window.fetch=function(input,init){
    var url=typeof input==='string'?input:(input&&input.url)||'';
    var method=((init&&init.method)||(input&&input.method)||'GET').toUpperCase();
    if(url.indexOf('/api/demo-requests')<0||method!=='POST')return of.apply(this,arguments);
    var self=this;
    return (async function(){
      var lastErr=null,lastRes=null;
      for(var i=0;i<waits.length;i++){
        if(waits[i])await sleep(waits[i]);
        var ctl=window.AbortController?new AbortController():null;
        var opts=Object.assign({},init||{});if(ctl)opts.signal=ctl.signal;
        var tm=ctl?setTimeout(function(){ctl.abort();},20000):null;
        try{
          var r=await of.call(self,input,opts);
          if(tm)clearTimeout(tm);
          if(r.ok||(r.status>=400&&r.status<500))return r;
          lastRes=r;
        }catch(e){if(tm)clearTimeout(tm);lastErr=e;}
      }
      if(lastRes)return lastRes;
      throw lastErr||new Error('network');
    })();
  };
})();
