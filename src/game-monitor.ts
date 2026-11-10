type App = {appid?: number|string; display_name?: string}|undefined;
type Timer = ReturnType<typeof setTimeout>;
export function monitorGame(read:()=>App, report:(id:string|null,name:string)=>Promise<{ok:boolean}>, changed:()=>void,
  subscribe:(notify:()=>void)=>{dispose:()=>void; observed:boolean}) {
  let stopped=false, timer:Timer|undefined, fallback:Timer|undefined, running=false, dirty=false;
  let reported:string|undefined, candidate:string|undefined, failures=0, candidateAt=0, retryAt=0;
  const sample=()=>{
    let app:App;try{app=read();}catch{return {id:null,name:'',key:'unavailable'};}
    const raw=app?.appid?String(app.appid):'';
    const id=!app||(!app.appid&&!app.display_name)?'default':/^[0-9]{1,20}$/.test(raw)&&/[1-9]/.test(raw)?raw:null;
    return {id,name:app?.display_name??'',key:JSON.stringify([id,app?.display_name??''])};
  };
  const schedule=(delay:number)=>{clearTimeout(timer);if(!stopped)timer=setTimeout(()=>void run(),delay);};
  async function run() {
    if(stopped)return;
    if(running){dirty=true;return;}
    running=true;
    try {
      const value=sample();
      if(value.key!==candidate){candidate=value.key;candidateAt=Date.now();failures=0;retryAt=0;}
      if(Date.now()-candidateAt<750){schedule(750-(Date.now()-candidateAt));return;}
      if(Date.now()<retryAt)return;
      if(value.key===reported||failures>=5)return;
      const result=await report(value.id,value.name);
      if(stopped)return;
      if(!result.ok)throw new Error('game report failed');
      reported=value.key;failures=0;changed();
    }catch {
      if(!stopped){failures++;if(failures<5){const delay=[2000,5000,15000,30000][failures-1];retryAt=Date.now()+delay;schedule(delay);}}
    }finally{running=false;if(dirty&&!stopped){dirty=false;schedule(750);}}
  }
  const notify=()=>{if(stopped)return;failures=0;retryAt=0;if(running)dirty=true;else schedule(0);};
  let subscription:{dispose:()=>void;observed:boolean};
  try{subscription=subscribe(notify);}catch{subscription={dispose:()=>{},observed:false};}
  if(!subscription.observed){
    const check=()=>{if(stopped)return;void run();fallback=setTimeout(check,5000);};
    fallback=setTimeout(check,5000);
  }
  schedule(0);
  return ()=>{stopped=true;clearTimeout(timer);clearTimeout(fallback);subscription.dispose();};
}
