const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const Module=require('node:module');
const ts=require('typescript');
const React=require('react');
const {create,act}=require('react-test-renderer');
global.IS_REACT_ACT_ENVIRONMENT=true;
global.requestAnimationFrame=fn=>setTimeout(fn,0);
global.cancelAnimationFrame=clearTimeout;
// Focus transfer runs after two animation frames; poll instead of assuming a
// fixed delay, which made this assertion flaky on loaded machines.
const waitFor=async(check,timeout=1000)=>{const start=Date.now();
  while(!check()){if(Date.now()-start>timeout)return;
    await act(async()=>{await new Promise(r=>setTimeout(r,10))});}};

for(const language of ['zh-CN','en-US']) test(`quick panel scope and rumble ordering: ${language}`,async()=>{
  Object.defineProperty(global,'navigator',{value:{language},configurable:true});
  const calls=[];let factory;let release;let failSave=false;
  const hardware={mode:'macro',left:50,right:50};
  const state={config:{revision:0,default:{M2:['B'],M1:[]},games:{}},game:'1',game_name:'Game One',
    applied:'default',managed:true,paused:false,hardware,can_test:true,inputplumber:{sources:['M1','M2']}};
  const ui={Router:{MainRunningApp:{appid:1,display_name:'Game One'}},Navigation:{Navigate(){},CloseSideMenus(){}},showModal(el){el?.props?.onOK?.()}};
  for(const n of ['ButtonItem','PanelSection','PanelSectionRow','SliderField','ToggleField','DropdownItem','TextField','ConfirmModal','SidebarNavigation','Focusable','DialogButton'])
    ui[n]=props=>React.createElement(n,props,props.children);
  const api={definePlugin:f=>f,routerHook:{addRoute:(_,f)=>{factory=f},removeRoute(){}},callable:name=>async(...args)=>{
    calls.push([name,...args]);
    if(name==='set_hardware') {await new Promise(r=>{release=r});if(failSave)return {ok:false,error:'readback_failed'};hardware.left=args[1];hardware.right=args[2];return {ok:true,data:hardware};}
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
    assert.match(json,language==='zh-CN'?/当前按键：默认按键/:/Current buttons: Default buttons/);
    assert.match(json,language==='zh-CN'?/左 M2 → B/:/Left M2 → B/);
    assert.match(json,language==='zh-CN'?/右 M1 → 不输出/:/Right M1 → No output/);
    assert.doesNotMatch(json,/未运行游戏 \/ 尚未确认|基础映射 \/ 未确认/);
    // The summary action is the only button that ends with the chevron.
    const summaryButtons=()=>rendered.root.findAllByType('ButtonItem').filter(x=>String(x.props.children).includes('›'));
    const summary=summaryButtons()[0];
    assert.ok(summary,'summary participates in focus navigation');
    assert.equal(summaryButtons().length,1,'one summary action, not one per line');
    let defaultEditor;
    try{
      await act(async()=>{summary.props.onClick();defaultEditor=create(factory().props.pages[0].content)});
      assert.ok(defaultEditor.root.findAllByType('PanelSection').some(x=>x.props.title===(language==='zh-CN'?'正在编辑：默认按键':'Editing: Default buttons')),
        'running game using defaults opens the displayed default configuration');
    }finally{await act(async()=>defaultEditor?.unmount());}

    const panelText=JSON.stringify(rendered.toJSON());
    const infoLabel=language==='zh-CN'?'当前按键：':'Current buttons: ';
    assert.ok(panelText.indexOf(infoLabel)<panelText.indexOf('\u203a'),'context precedes the action on screen');
    assert.equal(summary.findAllByType('Focusable').length,0,'summary has no nested focus stops');
    const elementText=node=>typeof node==='string'?node:Array.isArray(node)?node.map(elementText).join(''):
      node&&node.props?elementText(node.props.children):'';
    assert.doesNotMatch(elementText(summary.props.children),/游戏：|M2|M1/,'information rows stay outside the action row');
    assert.doesNotMatch(json,/MSI Claw A8 Controller Suite|仅管理 A8|Embedded A8 controller only/);
    assert.match(json,language==='zh-CN'?/游戏：/:/Game: /,'game status is plain information, not a second focus stop');
    assert.equal(summary.props.onGamepadFocus,undefined,'the action row needs no focus hook');
    const saved=JSON.parse(JSON.stringify(state));
    for(const scenario of [
      {game:null,managed:true,applied:'default',expected:language==='zh-CN'?'游戏：正在读取…':'Game: Reading…'},
      {game:'default',managed:true,applied:'default',expected:language==='zh-CN'?'当前按键：默认按键':'Current buttons: Default buttons'},
      {game:'1',managed:true,applied:'1',expected:language==='zh-CN'?'当前按键：Custom':'Current buttons: Custom'},
      {game:'default',managed:false,applied:null,expected:language==='zh-CN'?'管理已停用':'Management disabled'},
      {game:'default',managed:true,applied:null,expected:language==='zh-CN'?'尚未生效':'Not applied'},
    ]){
      Object.assign(state,scenario);
      state.config.games={'1':{name:'Custom',enabled:true,rules:{M2:['M1']}}};
      let preview;
      try{
        await act(async()=>{preview=create(plugin.content)});
        const content=JSON.stringify(preview.toJSON());
        assert.ok(content.includes(scenario.expected));
        if(scenario.game==='default')assert.ok(content.includes(language==='zh-CN'?'游戏：未运行':'Game: Not running'));
        if(scenario.game==='1')assert.ok(content.includes(language==='zh-CN'?'游戏：Game One':'Game: Game One'));
        if(!scenario.applied)assert.doesNotMatch(content,/→/);
        if(scenario.applied==='1')assert.ok(content.includes(language==='zh-CN'?'左 M2 → 右 M1':'Left M2 → Right M1'));
      }finally{await act(async()=>preview?.unmount());}
    }
    Object.assign(state,saved);

    await act(async()=>{rendered.root.findAllByType('SliderField')[0].props.onChange(75)});
    const testButton=rendered.root.findAllByType('ButtonItem').find(x=>String(x.props.children).includes('0.5'));
    await act(async()=>{testButton.props.onClick();await Promise.resolve()});
    assert.equal(calls.filter(x=>x[0]==='test_rumble').length,0);
    assert.equal(calls.filter(x=>x[0]==='set_hardware').length,1);
    await act(async()=>{release();await new Promise(r=>setTimeout(r,10))});
    // A zero-argument callable must reach the backend with no arguments:
    // an extra positional value makes Python raise before the body runs.
    assert.deepEqual(calls.filter(x=>x[0]==='test_rumble'),[['test_rumble']]);
    // The debounce has already consumed pending values, but the device write
    // is still running. Testing must await its result, including failure.
    await act(async()=>{rendered.root.findAllByType('SliderField')[0].props.onChange(80)});
    await waitFor(()=>calls.filter(x=>x[0]==='set_hardware').length===2);
    failSave=true;
    await act(async()=>{testButton.props.onClick();await Promise.resolve()});
    await act(async()=>{release();await new Promise(r=>setTimeout(r,10))});
    assert.equal(calls.filter(x=>x[0]==='test_rumble').length,1);
    assert.match(JSON.stringify(rendered.toJSON()),language==='zh-CN'?/震动值未保存/:/Rumble value not saved/);
    // A completed, historic failure must not permanently block later tests.
    failSave=false;
    await act(async()=>{testButton.props.onClick();await new Promise(r=>setTimeout(r,10))});
    assert.equal(calls.filter(x=>x[0]==='test_rumble').length,2);
    assert.ok(factory);
    // An enabled-but-not-applied preference has a retry action, not a restore prerequisite.
    state.apply_error='external_change';state.applied=null;
    let navigation,settings;
    try {
      await act(async()=>{navigation=create(factory())});
      const hardwarePage=navigation.root.findByType('SidebarNavigation').props.pages[2].content;
      await act(async()=>{settings=create(hardwarePage)});
      const text=JSON.stringify(settings.toJSON());
      assert.doesNotMatch(text,/MSI Claw A8 Controller Suite/,'outer navigation owns the plugin title');
      assert.doesNotMatch(text,/请恢复后重新启用|Restore before enabling again/);
      assert.match(text,language==='zh-CN'?/尚未生效/:/Not applied/);
      const retry=settings.root.findAllByType('ButtonItem').find(x=>['重试','Retry'].includes(x.props.children));
      await act(async()=>{await retry.props.onClick();await new Promise(r=>setTimeout(r,10))});
      assert.deepEqual(calls.filter(x=>x[0]==='set_management').at(-1),['set_management',true]);
      const disable=settings.root.findAllByType('ButtonItem').find(x=>String(x.props.children).includes(language==='zh-CN'?'恢复系统默认':'Restore system defaults'));
      await act(async()=>{await disable.props.onClick();await new Promise(r=>setTimeout(r,10))});
      assert.deepEqual(calls.filter(x=>x[0]==='set_management').at(-1),['set_management',false]);
      assert.match(JSON.stringify(settings.toJSON()),language==='zh-CN'?/启用管理/:/Enable management/);
      // Management moved to maintenance; the device page keeps only hardware controls.
      const pages=navigation.root.findByType('SidebarNavigation').props.pages;
      assert.equal(pages.length,3);
      let device;
      try {
        await act(async()=>{device=create(pages[1].content)});
        const deviceText=JSON.stringify(device.toJSON());
        assert.match(deviceText,language==='zh-CN'?/背键硬件模式/:/Back-button hardware mode/);
        assert.doesNotMatch(deviceText,/MSI Claw A8 Controller Suite|当前：|Current: /);
        assert.ok(device.root.findAllByType('PanelSection').some(x=>x.props.title===(language==='zh-CN'?'震动':'Rumble')));
        assert.ok(deviceText.includes(language==='zh-CN'?'本页设置对所有游戏生效':'Settings on this page apply to all games'));
        assert.equal(device.root.findAllByType('Focusable').filter(x=>x.props.tabIndex===0).length,0);
        assert.doesNotMatch(deviceText,language==='zh-CN'?/恢复系统默认/:/Restore system defaults/);
      } finally {await act(async()=>{device?.unmount()});}
      for(const pageIndex of [0]) {
        let editor;const focused=[];
        try {
          const page=navigation.root.findByType('SidebarNavigation').props.pages[pageIndex].content;
          await act(async()=>{editor=create(page,{createNodeMock:element=>element.type==='Focusable'?{
            querySelector:()=>({focus:()=>focused.push('control')})
          }:null})});
          const configText=JSON.stringify(editor.toJSON());
          assert.doesNotMatch(configText,/MSI Claw A8 Controller Suite/);
          assert.ok(configText.includes(language==='zh-CN'?'管理已停用；修改可保存':'Management disabled; edits can be saved'));
          assert.equal(editor.root.findAllByType('PanelSection').filter(x=>x.props.title===(language==='zh-CN'?'按键配置':'Button configurations')).length,0);
          const label=language==='zh-CN'?'编辑':'Edit';
          const open=()=>editor.root.findAllByType('DialogButton').find(x=>x.props.children===label);
          await act(async()=>{open().props.onClick()});
          await waitFor(()=>focused.length===1);
          assert.equal(focused.length,1,'entering editor transfers focus');
          const pairs=editor.root.findAllByType('Focusable').filter(x=>x.props['flow-children']==='row');
          assert.equal(pairs.length,8);
          assert.ok(pairs.every(x=>x.findAllByType('DropdownItem').length===2));
          const labels=pairs.flatMap(x=>x.findAllByType('DropdownItem').map(d=>d.props.label));
          assert.equal(new Set(labels).size,16);
          assert.deepEqual(labels.slice(0,2),language==='zh-CN'?['左 M2','右 M1']:['Left M2','Right M1']);
          const backKeys=pairs[0].findAllByType('DropdownItem');
          assert.equal(backKeys[1].props.selectedOption,'disabled');
          const target=backKeys[0].props.rgOptions.find(o=>o.data==='M1');
          assert.equal(target.label,language==='zh-CN'?'右 M1':'Right M1');
          await act(async()=>{backKeys[0].props.onChange({data:'M1'})});
          assert.equal(pairs[0].findAllByType('DropdownItem')[0].props.selectedOption,'M1','labels never change stored identifiers');
          const back=editor.root.findAllByType('ButtonItem').find(x=>['返回','Back'].includes(x.props.children));
          await act(async()=>{back.props.onClick()});
          await waitFor(()=>focused.length===2);
          assert.equal(focused.length,2,'return restores focus to the entry button');
          assert.ok(open());
        } finally {await act(async()=>editor?.unmount());}
      }
    } finally {await act(async()=>{settings?.unmount();navigation?.unmount()});}
  } finally {await act(async()=>rendered?.unmount());plugin.onDismount();}
});

for(const language of ['zh-CN','en-US']) test(`cards, copy dialog and duplicate game IDs: ${language}`,async()=>{
  Object.defineProperty(global,'navigator',{value:{language},configurable:true});
  const zh=language==='zh-CN';const text=node=>typeof node==='string'?node:node.children.map(text).join('');
  const state={config:{revision:0,default:{M2:['A']},games:{
    '1':{name:'Same',enabled:true,rules:{M2:['B']}},
    '2':{name:'Same',enabled:true,rules:{M2:['X']}},
    '3':{name:'Unique',enabled:true,rules:{M2:['Y']}}
  }},game:'1',game_name:'Same',applied:'1',managed:true,can_test:false,inputplumber:{sources:['M1','M2']}};
  const calls=[],focus=[];let factory,modal,modalHandle;
  const ui={Router:{},Navigation:{Navigate(){},CloseSideMenus(){}},showModal(element,parent,options){
    let closed=false;
    modal=create(element,{createNodeMock:e=>e.type==='Focusable'?{querySelector:()=>({focus:()=>focus.push('modal')})}:null});
    const handle={Close(){if(closed)return;closed=true;modal.unmount();options?.fnOnClose?.();}};
    modalHandle=handle;return handle;
  }};
  for(const n of ['ButtonItem','DialogButton','PanelSection','PanelSectionRow','SliderField','ToggleField','DropdownItem','ConfirmModal','ModalRoot','SidebarNavigation','Focusable'])
    ui[n]=props=>React.createElement(n,props,props.children);
  const api={definePlugin:f=>f,routerHook:{addRoute:(_,f)=>{factory=f},removeRoute(){}},callable:name=>async(...args)=>{
    calls.push([name,...args]);
    if(name==='save_config'){
      const [id,title,rules,enabled]=args;
      if(id==='default')state.config.default=rules;else state.config.games[id]={name:title,rules,enabled};
      state.config.revision++;
    }
    if(name==='delete_config'){delete state.config.games[args[0]];state.config.revision++;}
    return {ok:true,data:JSON.parse(JSON.stringify(state))};
  }};
  const filename=path.resolve('src/index.tsx');
  const compiled=ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020}}).outputText;
  const mod=new Module(filename,module);mod.filename=filename;mod.paths=Module._nodeModulePaths(path.dirname(filename));
  const original=mod.require.bind(mod);mod.require=n=>n==='@decky/ui'?ui:n==='@decky/api'?api:original(n);mod._compile(compiled,filename);
  const plugin=mod.exports.default();let quick,nav,page;
  try{
    await act(async()=>{quick=create(plugin.content);nav=create(factory())});
    const card=quick.root.findAllByType('ButtonItem').find(x=>String(x.props.children).includes('›'));
    assert.ok(JSON.stringify(quick.toJSON()).includes((zh?'当前按键：':'Current buttons: ')+'Same · ID 1'),'scope is plain information');
    assert.equal(card.findAllByType('Focusable').length,0);
    assert.equal(quick.root.findAllByType('ButtonItem').filter(x=>String(x.props.children).includes('›')).length,1);
    await act(async()=>{page=create(nav.root.findByType('SidebarNavigation').props.pages[0].content,
      {createNodeMock:e=>e.type==='Focusable'?{querySelector:()=>({focus:()=>focus.push('page')})}:null})});
    const section=label=>page.root.findAllByType('PanelSection').find(x=>x.props.title===label);
    assert.ok(section('Same · ID 1'));assert.ok(section('Same · ID 2'));assert.ok(section('Unique'));
    const defaults=section(zh?'默认按键':'Default buttons');
    assert.equal(defaults.findAllByType('DialogButton').length,1,'default has Edit but no Delete');
    assert.equal(section('Same · ID 1').findAllByType('DialogButton').length,2);
    await act(async()=>{section('Same · ID 1').findAllByType('DialogButton')[0].props.onClick()});
    await waitFor(()=>focus.length>0);
    assert.ok(section((zh?'正在编辑：':'Editing: ')+'Same · ID 1'));
    assert.equal(page.root.findAllByType('DropdownItem').length,16,'copy source is not on the editing page');
    await act(async()=>{page.root.findByType('ToggleField').props.onChange(false)});
    const copyButton=()=>page.root.findAllByType('ButtonItem').find(x=>x.props.children===(zh?'从其他方案复制…':'Copy from another configuration…'));
    await act(async()=>{copyButton().props.onClick()});
    await waitFor(()=>focus.includes('modal'));
    const options=modal.root.findByType('DropdownItem').props.rgOptions;
    assert.equal(options.find(o=>o.data==='2').label,'Same · ID 2');
    assert.equal(options.find(o=>o.data==='3').label,'Unique');
    assert.ok(!options.some(o=>o.data==='1'),'cannot copy from the same editing configuration');
    await act(async()=>{modal.root.findByType('DropdownItem').props.onChange({data:'2'})});
    const before=focus.length;
    await act(async()=>{modal.root.findByType('ConfirmModal').props.onOK()});
    await waitFor(()=>focus.length>before);
    assert.equal(focus.at(-1),'page','return focus to copy entry');
    const mapping=()=>page.root.findAllByType('DropdownItem').find(x=>x.props.label===(zh?'左 M2':'Left M2'));
    assert.equal(mapping().props.selectedOption,'X');
    assert.equal(page.root.findByType('ToggleField').props.checked,false,'copy must not enable custom configuration');
    assert.equal(calls.filter(c=>c[0]==='save_config').length,0,'copy only changes local edits');
    await act(async()=>{copyButton().props.onClick()});
    await act(async()=>{modal.root.findByType('DropdownItem').props.onChange({data:'3'})});
    await act(async()=>{modal.root.findByType('ConfirmModal').props.onCancel()});
    assert.equal(mapping().props.selectedOption,'X','cancel leaves draft unchanged');
    await act(async()=>{await page.root.findAllByType('ButtonItem').find(x=>String(x.props.children).startsWith(zh?'保存到：':'Save to: ')).props.onClick()});
    await waitFor(()=>!!section('Same · ID 1'));
    const save=calls.find(c=>c[0]==='save_config');
    assert.equal(save[1],'1');assert.equal(save[2],'Same','ID suffix is presentation only');
    assert.deepEqual(save[3],{M2:['X']});assert.equal(save[4],false);
    assert.deepEqual(state.config.games['2'].rules,{M2:['X']},'source unchanged');
    // Deletion opens a destructive dialog whose first, focused action is Cancel:
    // a reflex A press must keep the configuration.
    await act(async()=>{section('Same · ID 2').findAllByType('DialogButton')[1].props.onClick()});
    const danger=()=>modal.root.findByType('ModalRoot');
    assert.match(text(danger()),/Same · ID 2/);
    const dangerButtons=danger().findAllByType('DialogButton');
    assert.equal(dangerButtons.length,2);
    assert.equal(String(dangerButtons[0].props.children),zh?'取消':'Cancel','cancel is the first action');
    await act(async()=>{dangerButtons[0].props.onClick()});
    assert.ok(!calls.some(c=>c[0]==='delete_config'),'cancel deletes nothing');
    assert.ok(state.config.games['2'],'cancel keeps the configuration');
    await act(async()=>{section('Same · ID 2').findAllByType('DialogButton')[1].props.onClick()});
    await act(async()=>{danger().findAllByType('DialogButton')[1].props.onClick()});
    await waitFor(()=>calls.some(c=>c[0]==='delete_config'));
    assert.equal(calls.find(c=>c[0]==='delete_config')[1],'2');
    assert.ok(state.config.games['1']);assert.equal(state.config.games['2'],undefined);
    // A lost game ID retains the applied mapping but cannot create/edit a
    // configuration using the previous game as if it were still current.
    state.game_known=false;
    let unknown;
    try{
      await act(async()=>{unknown=create(plugin.content)});
      const unknownCard=unknown.root.findAllByType('ButtonItem')
        .find(x=>String(x.props.children).includes('›'));
      assert.ok(JSON.stringify(unknown.toJSON()).includes(zh?'无法识别，保持当前配置':'Unrecognized; keeping current configuration'));
      await act(async()=>{unknownCard.props.onClick()});
      let fallback;
      try{
        await act(async()=>{fallback=create(factory().props.pages[0].content)});
        assert.ok(fallback.root.findAllByType('PanelSection').some(x=>x.props.title===(zh?'正在编辑：Same':'Editing: Same')));
        assert.equal(fallback.root.findAllByType('ToggleField').length,1);
      }finally{await act(async()=>fallback?.unmount());}
    }finally{await act(async()=>unknown?.unmount());}
    state.game_known=true;
    // The game card opens the current game's editor, retaining its raw ID/name.
    await act(async()=>{card.props.onClick()});
    let opened;
    try{
      await act(async()=>{opened=create(factory().props.pages[0].content)});
      assert.ok(opened.root.findAllByType('PanelSection').some(x=>x.props.title===(zh?'正在编辑：':'Editing: ')+'Same'));
    }finally{await act(async()=>opened?.unmount());}
  }finally{
    await act(async()=>{modalHandle?.Close();page?.unmount();nav?.unmount();quick?.unmount()});plugin.onDismount();
  }
});
