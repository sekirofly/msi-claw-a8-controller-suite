const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const Module=require('node:module');
const ts=require('typescript');
const React=require('react');
const {create,act}=require('react-test-renderer');
global.IS_REACT_ACT_ENVIRONMENT=true;

for(const language of ['zh-CN','en-US']) test(`quick panel scope and rumble ordering: ${language}`,async()=>{
  Object.defineProperty(global,'navigator',{value:{language},configurable:true});
  const calls=[];let factory;let release;
  const hardware={mode:'macro',left:50,right:50};
  const state={config:{revision:0,default:{},games:{},templates:{}},game:'1',game_name:'Game One',
    applied:'default',managed:true,paused:false,hardware,can_test:true,inputplumber:{sources:['M1','M2']}};
  const ui={Router:{MainRunningApp:{appid:1,display_name:'Game One'}},Navigation:{Navigate(){},CloseSideMenus(){}},showModal(){}};
  for(const n of ['ButtonItem','PanelSection','PanelSectionRow','SliderField','ToggleField','DropdownItem','TextField','ConfirmModal','SidebarNavigation'])
    ui[n]=props=>React.createElement(n,props,props.children);
  const api={definePlugin:f=>f,routerHook:{addRoute:(_,f)=>{factory=f},removeRoute(){}},callable:name=>async(...args)=>{
    calls.push([name,...args]);
    if(name==='set_hardware') {await new Promise(r=>{release=r});hardware.left=args[1];hardware.right=args[2];return {ok:true,data:hardware};}
    if(name==='get_state')return {ok:true,data:JSON.parse(JSON.stringify(state))};
    if(name==='set_management') {state.managed=args[0];state.apply_error=null;return {ok:true,data:state};}
    return {ok:true,data:true};
  }};
  const filename=path.resolve('src/index.tsx');
  const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
  const mod=new Module(filename,module);mod.filename=filename;mod.paths=Module._nodeModulePaths(path.dirname(filename));
  const original=mod.require.bind(mod);mod.require=n=>n==='@decky/ui'?ui:n==='@decky/api'?api:original(n);mod._compile(compiled,filename);
  const plugin=mod.exports.default();let rendered;
  try {
    await act(async()=>{rendered=create(plugin.content)});
    const json=JSON.stringify(rendered.toJSON());
    assert.doesNotMatch(json,/Combination|背键硬件模式/);
    if(language==='en-US')assert.doesNotMatch(json,/[\u3400-\u9fff]/);
    assert.deepEqual(calls,[['get_state']]);
    await act(async()=>{rendered.root.findAllByType('SliderField')[0].props.onChange(75)});
    const testButton=rendered.root.findAllByType('ButtonItem').find(x=>String(x.props.children).includes('0.5'));
    await act(async()=>{testButton.props.onClick();await Promise.resolve()});
    assert.equal(calls.filter(x=>x[0]==='test_rumble').length,0);
    assert.equal(calls.filter(x=>x[0]==='set_hardware').length,1);
    await act(async()=>{release();await new Promise(r=>setTimeout(r,10))});
    assert.equal(calls.filter(x=>x[0]==='test_rumble').length,1);
    assert.ok(factory);
    // An enabled-but-not-applied preference has a retry action, not a restore prerequisite.
    state.apply_error='external_change';state.applied=null;
    let navigation,settings;
    try {
      await act(async()=>{navigation=create(factory())});
      const hardwarePage=navigation.root.findByType('SidebarNavigation').props.pages[2].content;
      await act(async()=>{settings=create(hardwarePage)});
      const text=JSON.stringify(settings.toJSON());
      assert.doesNotMatch(text,/请恢复后重新启用|Restore before enabling again/);
      assert.match(text,language==='zh-CN'?/尚未生效/:/Not applied/);
      const retry=settings.root.findAllByType('ButtonItem').find(x=>['重试','Retry'].includes(x.props.children));
      await act(async()=>{await retry.props.onClick();await new Promise(r=>setTimeout(r,10))});
      assert.deepEqual(calls.filter(x=>x[0]==='set_management').at(-1),['set_management',true]);
      const disable=settings.root.findAllByType('ButtonItem').find(x=>String(x.props.children).includes(language==='zh-CN'?'恢复原配置':'Restore original'));
      await act(async()=>{await disable.props.onClick();await new Promise(r=>setTimeout(r,10))});
      assert.deepEqual(calls.filter(x=>x[0]==='set_management').at(-1),['set_management',false]);
      assert.match(JSON.stringify(settings.toJSON()),language==='zh-CN'?/启用管理/:/Enable management/);
    } finally {await act(async()=>{settings?.unmount();navigation?.unmount()});}
  } finally {await act(async()=>rendered?.unmount());plugin.onDismount();}
});
