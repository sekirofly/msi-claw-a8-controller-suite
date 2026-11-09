import {useEffect, useRef, useState} from 'react';
import {ButtonItem, PanelSection, PanelSectionRow, SliderField, ToggleField, DropdownItem, TextField,
  ConfirmModal, showModal, Navigation, Router, SidebarNavigation, Focusable} from '@decky/ui';
import {callable, definePlugin, routerHook} from '@decky/api';

const route = '/msi-claw-a8-controller-suite';
const t = (zh: string, en: string) => /^zh(?:[-_]|$)/i.test(navigator.language) ? zh : en;
type Rules = Record<string, string[]>;
type Entry = {name: string; rules: Rules; enabled?: boolean};
type Config = {revision: number; default: Rules; games: Record<string, Entry>; templates: Record<string, Entry>};
type State = {config: Config; game: string | null; game_name: string; applied: string | null; apply_error?: string;
  managed: boolean; hardware?: {mode: string; left: number; right: number};
  hardware_error?: string; inputplumber_error?: string; inputplumber?: {sources: string[]; profile: string; targets: string[]}; can_test: boolean};
type Result<T> = {ok: boolean; data: T; error?: string};
const getState = callable<[], Result<State>>('get_state');
const saveConfig = callable<[string, string, Rules, boolean, number], Result<State>>('save_config');
const deleteConfig = callable<[string, number], Result<State>>('delete_config');
const setHardware = callable<[string | null, number | null, number | null], Result<State['hardware']>>('set_hardware');
const testRumble = callable<[], Result<boolean>>('test_rumble');
const manage = callable<[boolean], Result<State>>('set_management');
const maintenance = callable<[string], Result<boolean>>('maintenance');
const reportGame = callable<[string | null, string], Result<unknown>>('report_game');
const buttons = ['M1','M2','A','B','X','Y','LB','RB','LS','RS','Up','Down','Left','Right','Menu','View'];
const keys = ['Space','Enter','Esc','Tab','LeftShift','LeftCtrl','LeftAlt', ...'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'];
const outputs = [...buttons, ...keys.map(k => 'key:Key'+k), 'mouse:Left','mouse:Right','mouse:Middle'];
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

function errorText(code?: string): string {
  const messages: Record<string, [string,string]> = {
    not_a8:['未确认是 A8 主机','A8 motherboard was not identified'],
    device_missing:['未找到已确认的内置控制接口','Verified embedded controls were not found'],
    device_ambiguous:['设备不唯一，已停止操作','Ambiguous device; operation blocked'],
    composite_ambiguous:['无法唯一确认内置 InputPlumber 设备','Cannot uniquely identify the embedded InputPlumber device'],
    interface_unavailable:['接口不可用，请查看诊断','Interface unavailable; check diagnostics'],
    yaml_missing:['需要系统 Python PyYAML','System Python PyYAML is required'],
    external_change:['手柄配置发生变化，请检查冲突后重试','Controller configuration changed. Check for conflicts and retry'],
    management_disabled:['配置尚未应用，请重试','Configuration has not been applied. Retry'],
    stale_edit:['配置已被修改，请重新打开编辑页','Configuration changed; reopen the editor'],
    source_unavailable:['设备未报告该输入，未应用配置','Device does not report this input; configuration not applied'],
    game_unknown:['当前游戏未确认，未切换配置','Current game is unknown; configuration was not switched'],
    rumble_unavailable:['内置手柄未提供可确认的震动测试接口','Verified embedded rumble test interface unavailable'],
    config_corrupt:['配置文件无法读取，未覆盖原文件','Configuration unreadable; original file was not overwritten'],
    test_busy:['测试进行中，请稍候','Test in progress; please wait'],
    readback_failed:['读取结果与请求不符，请检查设备','Read-back mismatch; check the device'],
    maintenance_pending:['维护已安排，Decky 将重启；若未完成请检查维护日志或重新加载 Decky。','Maintenance scheduled; Decky will restart. If it does not complete, check the maintenance journal or reload Decky.'],
    nonstandard_install:['安装位置异常，请使用终端维护命令。','Nonstandard installation; use the terminal maintenance command.'],
  };
  const m = messages[code ?? ''];
  return m ? t(...m) : t('操作失败，请查看日志：','Operation failed; check logs: ') + (code ?? 'unknown');
}

// One frontend write chain survives panel unmount; backend serializes independently.
let chain: Promise<unknown> = Promise.resolve();
let rumbleTimer: ReturnType<typeof setTimeout> | undefined;
let pending: [number, number] | undefined;
let writeError = '';
let outstanding = 0;
const stateListeners = new Set<() => void>();
const enqueue = <T,>(action: () => Promise<Result<T>>): Promise<T> => {
  outstanding++;
  const next = chain.then(action).then(r => {if (!r.ok) throw new Error(errorText(r.error)); return r.data;}).finally(()=>{outstanding--;});
  chain = next.catch(e => {writeError = String(e);});
  return next;
};
function flushRumble() {
  clearTimeout(rumbleTimer); rumbleTimer = undefined;
  if (pending) {const [left,right] = pending; pending = undefined; return enqueue(() => setHardware(null,left,right));}
  return chain;
}
function scheduleRumble(left: number, right: number) {
  writeError = ''; pending = [left,right]; clearTimeout(rumbleTimer);
  rumbleTimer = setTimeout(() => {void flushRumble().catch(() => {});}, 200);
}

function useController() {
  const [state,setState] = useState<State>();
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  async function refresh() {
    const r = await getState();
    if (r.ok) setState(r.data); else setError(errorText(r.error));
  }
  useEffect(() => {let active = true; const read = async () => {
    try {const r = await getState(); if (active) {if(r.ok) setState(r.data); else setError(errorText(r.error));}}
    catch(e) {if(active) setError(String(e));}
  }; const update=()=>{void read();};stateListeners.add(update);void read(); return () => {active=false;stateListeners.delete(update); void flushRumble().catch(() => {});};}, []);
  async function run(action: () => Promise<unknown>) {
    setBusy(true); setError('');
    try {await flushRumble(); await action(); await refresh();}
    catch(e) {setError(String(e)); await refresh().catch(() => {});}
    finally {setBusy(false);}
  }
  return {state,error,busy,run,refresh};
}
type Controller = ReturnType<typeof useController>;
const row = (text: string) => <PanelSectionRow key={text}><div style={{fontSize:13, overflowWrap:'anywhere'}}>{text}</div></PanelSectionRow>;
function confirm(title: string, description: string, action: () => void) {
  showModal(<ConfirmModal strTitle={title} strDescription={description} strOKButtonText={t('确认','Confirm')}
    strCancelButtonText={t('取消','Cancel')} onOK={action}/>);
}
function Header({c}: {c: Controller}) {
  return <PanelSection title="MSI Claw A8 Controller Suite">
    {row(c.error || (c.state ? t('仅管理 A8 内置手柄','Embedded A8 controller only') : t('正在读取…','Reading…')))}
    {c.state && row(c.state.managed?t('管理已启用','Management enabled'):t('管理已停用','Management disabled'))}
    {c.state?.apply_error && <>
      {row((c.state.managed?t('尚未生效：','Not applied: '):t('原配置尚未恢复：','Original configuration not yet restored: '))+errorText(c.state.apply_error))}
      <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>void c.run(()=>enqueue(()=>manage(c.state!.managed)))}>{t('重试','Retry')}</ButtonItem></PanelSectionRow>
    </>}
    {c.state?.hardware_error && row(errorText(c.state.hardware_error))}
  </PanelSection>;
}
function RumblePanel({c}: {c: Controller}) {
  const hw = c.state?.hardware;
  const [values,setValues] = useState<[number,number]>([50,50]);
  const [testing,setTesting] = useState(false);
  const [error,setError] = useState('');
  const [saving,setSaving] = useState(false);
  useEffect(() => {if(hw && !pending && !outstanding) setValues([hw.left,hw.right]);}, [hw?.left,hw?.right]);
  function change(index: number, value: number) {
    const next: [number,number] = [...values]; next[index] = value; setValues(next);setSaving(true);
    scheduleRumble(...next);
  }
  useEffect(() => {if(!saving) return; const id=setInterval(() => {
    if(!pending) void chain.then(() => {setSaving(false);setError(writeError);if(writeError) void c.refresh();});
  },250);return () => clearInterval(id);},[saving]);
  return <PanelSection title={t('震动 · 所有游戏共用','Rumble · shared by all games')}>
    {[0,1].map(i => <PanelSectionRow key={i}><SliderField label={(i===0?t('左','Left'):t('右','Right'))+` ${values[i]}%`}
      value={values[i]} min={0} max={100} step={5} disabled={!hw || testing || c.busy} onChange={v=>change(i,v)}/></PanelSectionRow>)}
    <PanelSectionRow><ButtonItem disabled={!hw || !c.state?.can_test || testing || c.busy} layout="below" onClick={() => {
      setTesting(true);setError('');void (async()=>{try {await flushRumble(); if(writeError) throw new Error(writeError);
        await enqueue(testRumble);}catch(e){setError(String(e));}finally{setTesting(false);}})();
    }}>{testing?t('测试中…','Testing…'):t('测试震动 · 0.5 秒','Test rumble · 0.5 seconds')}</ButtonItem></PanelSectionRow>
    {row(error || (saving?t('正在保存…','Saving…'):t('滑动自动保存；测试只触发内置手柄。','Sliders save automatically; testing targets only the embedded controller.')))}
    {!c.state?.can_test && row(t('此设备的震动测试接口尚不可用','Rumble test interface is unavailable on this device'))}
  </PanelSection>;
}

// Transfer focus only on an explicit view transition, never on status refreshes.
function FocusEntry({active,children}: {active:boolean;children:React.ReactNode}) {
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!active)return;
    let frame=0;
    frame=requestAnimationFrame(()=>{frame=requestAnimationFrame(()=>{
      const root=ref.current;
      const target=root?.querySelector<HTMLElement>('button:not(:disabled), [role="button"]:not([aria-disabled="true"])')
        ?? root?.querySelector<HTMLElement>('select:not(:disabled), input:not(:disabled)')
        ?? root?.querySelector<HTMLElement>('[tabindex="0"]');
      target?.focus();
    });});
    return ()=>cancelAnimationFrame(frame);
  },[active]);
  return <Focusable ref={ref} flow-children="column" preferredFocus={active} noFocusRing>{children}</Focusable>;
}
const mappingGroups = [
  {zh:'背键',en:'Back buttons',rows:[['M1','M2']]},
  {zh:'动作键',en:'Face buttons',rows:[['A','B'],['X','Y']]},
  {zh:'方向键',en:'D-pad',rows:[['Up','Down'],['Left','Right']]},
  {zh:'肩键',en:'Shoulder buttons',rows:[['LB','RB']]},
  {zh:'摇杆按下',en:'Stick clicks',rows:[['LS','RS']]},
  {zh:'菜单键',en:'Menu buttons',rows:[['View','Menu']]},
];

function Editor({c,scope,name,onClose}: {c: Controller; scope: string; name: string; onClose: () => void}) {
  const config=c.state!.config;
  const entry = scope==='default'?undefined:scope.startsWith('template:')?config.templates[scope.slice(9)]:config.games[scope];
  const [rules,setRules]=useState<Rules>(()=>clone(entry?.rules ?? config.default));
  const [enabled,setEnabled]=useState(entry?.enabled ?? true);
  const [title,setTitle]=useState(name);
  const [dirty,setDirty]=useState(false);
  const [source,setSource]=useState('default');
  const [revision,setRevision]=useState(config.revision);
  const template=scope.startsWith('template:');
  const choices=[{data:'default',label:t('默认按键','Default buttons')},
    ...Object.entries(config.games).filter(([id])=>id!==scope).map(([id,e])=>({data:id,label:e.name})),
    ...Object.entries(config.templates).filter(([id])=>'template:'+id!==scope).map(([id,e])=>({data:'template:'+id,label:e.name}))];
  function copySource() {
    const copied=source==='default'?config.default:source.startsWith('template:')?config.templates[source.slice(9)].rules:config.games[source].rules;
    setRules(clone(copied));setDirty(true);
  }
  const close=()=>dirty?confirm(t('放弃未保存修改？','Discard unsaved changes?'),t('已保存的配置保持不变。','Saved configuration stays unchanged.'),onClose):onClose();
  return <Focusable flow-children="column" onCancel={e=>{e.stopPropagation();close();}}>
    <PanelSection title={t('正在编辑：','Editing: ')+(scope==='default'?t('默认按键','Default buttons'):title)}>
      {row(scope==='default'?t('影响使用默认按键的游戏，不影响独立副本。','Affects games using defaults, not independent copies.'):
        template?t('模板修改不会影响已有游戏配置。','Template edits do not change existing game configurations.'):
        c.state?.game===scope?t('仅影响本游戏；保存并启用后应用。','Only this game; applied when saved and enabled.'):
        t('本游戏当前未运行，保存后下次启动生效。','This game is not running; saved changes apply next launch.'))}
      {template&&<PanelSectionRow><TextField label={t('模板名称','Template name')} value={title} onChange={e=>{setTitle(e.target.value);setDirty(true);}}/></PanelSectionRow>}
      {scope!=='default'&&!template&&<PanelSectionRow><ToggleField label={t('使用本游戏专用按键','Use this game’s custom buttons')} checked={enabled}
        onChange={v=>{setEnabled(v);setDirty(true);}}/></PanelSectionRow>}
      <FocusEntry active><PanelSectionRow><DropdownItem label={t('复制来源','Copy from')} selectedOption={source} rgOptions={choices} onChange={(v:{data:string})=>setSource(v.data)}/></PanelSectionRow></FocusEntry>
      <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>confirm(t('替换编辑草稿','Replace draft'),t('复制后互不关联；保存前不改变已有配置。','Copies are independent. Existing settings change only after saving.'),copySource)}>{t('复制到此草稿','Copy into this draft')}</ButtonItem></PanelSectionRow>
    </PanelSection>
    <PanelSection title={t('按键映射','Button mappings')}>
      {mappingGroups.map(group=><div key={group.en} style={{marginBottom:12}}>
        <div style={{fontSize:14,fontWeight:600,margin:'8px 0'}}>{t(group.zh,group.en)}</div>
        {group.rows.map(pair=><Focusable key={pair.join('-')} flow-children="row" style={{display:'flex',gap:12}}>
          {pair.map(b=><div key={b} style={{flex:'1 1 0',minWidth:0}}>
            <DropdownItem layout="below" label={b} description={c.state?.inputplumber?.sources.includes(b)?undefined:t('输入待验证','Input unverified')}
              selectedOption={rules[b]?.[0]??'unchanged'} rgOptions={[{data:'unchanged',label:t('保持基础映射','Keep base mapping')},{data:'disabled',label:t('不输出','No output')},...outputs.map(o=>({data:o,label:o}))]}
              onChange={(v:{data:string})=>{const next=clone(rules);if(v.data==='unchanged')delete next[b];else next[b]=v.data==='disabled'?[]:[v.data];setRules(next);setDirty(true);}}/>
          </div>)}
        </Focusable>)}
      </div>)}
      {row(t('Guide/QAM 入口受保护。摇杆和扳机轴保持原始行为。','Guide/QAM are protected. Stick and trigger axes keep their original behavior.'))}
    </PanelSection>
    <PanelSection>
      <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>void c.run(async()=>{
        const r=await enqueue(()=>saveConfig(scope,title,rules,enabled,revision));
        setRevision(r.config.revision);setDirty(false);
        if(r.apply_error) throw new Error(t('已保存，未生效：','Saved, not applied: ')+errorText(r.apply_error));
        setDirty(false);onClose();
      })}>{scope==='default'?t('保存默认按键','Save default buttons'):t('保存到：','Save to: ')+title}</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem disabled={c.busy} onClick={close}>{t('返回','Back')}</ButtonItem></PanelSectionRow>
    </PanelSection>
  </Focusable>;
}

let requestedScope: {scope:string;name:string}|undefined;
function QuickPanel() {
  const c=useController(); const s=c.state;
  const game=s?.game && s.game!=='default'?s.game:undefined;
  const scope=s?.applied;
  const rules=scope==='default'?s?.config.default:scope?s?.config.games[scope]?.rules:undefined;
  function open(scope?:string,name?:string) {
    requestedScope=scope?{scope,name:name??''}:undefined;
    Navigation.Navigate(route);Navigation.CloseSideMenus();
  }
  return <><Header c={c}/>{s&&<PanelSection title={t('当前按键','Current buttons')}>
    {row(game?s.game_name:t('未运行游戏 / 尚未确认','No running game / not yet confirmed'))}
    {row(!s.managed?t('按键管理未启用','Mapping management is not enabled'):scope==='default'?t('默认按键','Default buttons'):scope?s.config.games[scope]?.name??scope:t('尚未确认生效','Not confirmed applied'))}
    {['M1','M2'].map(b=>row(`${b} → ${rules?.[b]?.join(' + ') || t('基础映射 / 未确认','Base mapping / unconfirmed')}`))}
    <PanelSectionRow><ButtonItem disabled={c.busy||s.game===null} onClick={()=>open(game??'default',game?s.game_name:t('默认按键','Default buttons'))}>
      {game?(s.config.games[game]?t('编辑：','Edit: '):t('为本游戏单独设置：','Customize this game: '))+s.game_name:t('编辑默认按键','Edit default buttons')}</ButtonItem></PanelSectionRow>
  </PanelSection>}<RumblePanel c={c}/><PanelSection><PanelSectionRow><ButtonItem onClick={()=>open()}>{t('打开设置','Open settings')}</ButtonItem></PanelSectionRow></PanelSection></>;
}

function Settings({page}:{page:'configs'|'templates'|'hardware'|'about'}) {
  const c=useController();const s=c.state;
  const [editing,setEditing]=useState<{scope:string;name:string}|undefined>(()=>{const req=requestedScope;requestedScope=undefined;return page==='configs'?req:undefined;});
  const returnTo=useRef<string|undefined>(undefined);
  function openEditor(entry:{scope:string;name:string},origin=entry.scope){returnTo.current=origin;setEditing(entry);}
  function closeEditor(){setEditing(undefined);}
  if(!s)return <Header c={c}/>;
  if(editing)return <><Header c={c}/><Editor key={editing.scope} c={c} {...editing} onClose={closeEditor}/></>;
  return <><Header c={c}/>
    {page==='configs'&&<PanelSection title={t('按键配置','Button configurations')}>
      <FocusEntry active={returnTo.current==='default'}><PanelSectionRow><ButtonItem onClick={()=>openEditor({scope:'default',name:t('默认按键','Default buttons')})}>{t('编辑默认按键','Edit default buttons')}</ButtonItem></PanelSectionRow></FocusEntry>
      {s.game&&s.game!=='default'&&!s.config.games[s.game]&&<FocusEntry active={returnTo.current===s.game}><PanelSectionRow><ButtonItem onClick={()=>openEditor({scope:s.game!,name:s.game_name})}>{t('为当前游戏创建：','Create for current game: ')+s.game_name}</ButtonItem></PanelSectionRow></FocusEntry>}
      {Object.entries(s.config.games).map(([id,e])=><PanelSection key={id} title={e.name}>
        {row(e.enabled?t('已启用专用配置','Custom configuration enabled'):t('已停用，当前跟随默认','Disabled; uses defaults'))}
        <FocusEntry active={returnTo.current===id}><PanelSectionRow><ButtonItem onClick={()=>openEditor({scope:id,name:e.name})}>{t('编辑','Edit')}</ButtonItem></PanelSectionRow></FocusEntry>
        <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>confirm(t('删除专用配置？','Delete custom configuration?'),e.name,()=>void c.run(()=>enqueue(()=>deleteConfig(id,s.config.revision))))}>{t('删除并使用默认','Delete and use defaults')}</ButtonItem></PanelSectionRow>
      </PanelSection>)}
    </PanelSection>}
    {page==='templates'&&<PanelSection title={t('模板库 · 复制后互不关联','Templates · copies remain independent')}>
      <FocusEntry active={returnTo.current==='new-template'}><PanelSectionRow><ButtonItem onClick={()=>openEditor({scope:'template:'+Date.now().toString(),name:t('新模板','New template')},'new-template')}>{t('新建模板','New template')}</ButtonItem></PanelSectionRow></FocusEntry>
      {Object.entries(s.config.templates).map(([id,e])=><PanelSection key={id} title={e.name}>
        <FocusEntry active={returnTo.current==='template:'+id}><PanelSectionRow><ButtonItem onClick={()=>openEditor({scope:'template:'+id,name:e.name})}>{t('编辑','Edit')}</ButtonItem></PanelSectionRow></FocusEntry>
        <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>confirm(t('删除模板？','Delete template?'),t('已复制到游戏的配置不受影响。','Existing game copies are unaffected.'),()=>void c.run(()=>enqueue(()=>deleteConfig('template:'+id,s.config.revision))))}>{t('删除','Delete')}</ButtonItem></PanelSectionRow>
      </PanelSection>)}
    </PanelSection>}
    {page==='hardware'&&<><PanelSection title={t('手柄设置 · 所有游戏共用','Device settings · shared by all games')}>
      {s.inputplumber_error&&row(errorText(s.inputplumber_error))}
      <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>void c.run(()=>enqueue(()=>manage(!s.managed)))}>
        {s.managed?t('恢复原配置并停用','Restore original configuration and disable'):t('启用管理','Enable management')}
      </ButtonItem></PanelSectionRow>
      {['macro','combination','disabled'].map(mode=><PanelSectionRow key={mode}><ButtonItem disabled={c.busy||!s.hardware}
        onClick={()=>void c.run(()=>enqueue(()=>setHardware(mode,null,null)))}>{s.hardware?.mode===mode?'● ':'○ '}{mode}</ButtonItem></PanelSectionRow>)}
      {row(t('背键硬件模式可能影响独立 M1/M2 事件；不会自动更改。','Hardware back-button mode can affect independent M1/M2 events; it is never changed automatically.'))}
    </PanelSection><RumblePanel c={c}/></>}
    {page==='about'&&<PanelSection title={t('维护与诊断','Maintenance and diagnostics')}>
      {row('0.1.0-alpha.5 · GPL-3.0-only')}
      {row(t('安装后请重启；持续震动异常可参考 MSI 官方 EC 恢复说明。','Reboot after installation. For persistent rumble issues, consult MSI’s official EC reset guidance.'))}
      {row(t('恢复：先到手柄设置停用管理。终端恢复和卸载方法见 README。','Recovery: disable management in device settings first. See README for terminal recovery and removal.'))}
      {(['install','reinstall','uninstall'] as const).map(action=><PanelSectionRow key={action}><ButtonItem disabled={c.busy} onClick={()=>confirm(
        action==='uninstall'?t('干净卸载插件','Clean uninstall'):action==='reinstall'?t('干净重装当前版本','Clean reinstall current version'):t('修复安装当前版本','Repair current version'),
        t('将短暂重启 Decky，并先恢复接管前的输入配置。修复保留按键配置；干净卸载/重装会清除它们。硬件震动与背键模式不重置。恢复失败时保留文件。','Decky restarts briefly. Original input state is restored first. Repair keeps button configurations; clean reinstall/uninstall clears them. Hardware settings are not reset. Files are preserved if restoration fails.'),
        ()=>void c.run(()=>enqueue(()=>maintenance(action))))}>
        {action==='uninstall'?t('干净卸载','Clean uninstall'):action==='reinstall'?t('干净重装当前版本','Clean reinstall current version'):t('修复安装 · 保留配置','Repair installation · keep configurations')}
      </ButtonItem></PanelSectionRow>)}
      <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>void c.run(async()=>{})}>{t('刷新诊断','Refresh diagnostics')}</ButtonItem></PanelSectionRow>
      {row(JSON.stringify({hardware:s.hardware, hardware_error:s.hardware_error, inputplumber:s.inputplumber,inputplumber_error:s.inputplumber_error,can_test:s.can_test},null,2))}
    </PanelSection>}
  </>;
}

export default definePlugin(()=>{
  let last:string|undefined;let stable=0;let ticking=false;let count=0;
  const tick=async()=>{
    if(ticking)return;ticking=true;
    try {
      const app=Router.MainRunningApp;
      const id=app?.appid?String(app.appid):'default';
      stable=id===last?stable+1:0;last=id;
      if(stable>=2 && (++count%5===1)) {await reportGame(id,app?.display_name??'');stateListeners.forEach(fn=>fn());}
    } catch {await reportGame(null,'').catch(()=>{});} finally {ticking=false;}
  };
  const interval=setInterval(()=>void tick(),1000);
  routerHook.addRoute(route,()=> <SidebarNavigation title="MSI Claw A8 Controller Suite" showTitle pages={[
    {title:t('按键配置','Button configurations'),content:<Settings page="configs"/>,route:route+'/configs'},
    {title:t('模板库','Templates'),content:<Settings page="templates"/>,route:route+'/templates'},
    {title:t('手柄设置','Device settings'),content:<Settings page="hardware"/>,route:route+'/hardware'},
    {title:t('维护与关于','Maintenance and about'),content:<Settings page="about"/>,route:route+'/about'},
  ]}/>);
  return {name:'MSI Claw A8 Controller Suite',icon:<span>🎮</span>,content:<QuickPanel/>,onDismount(){
    clearInterval(interval);routerHook.removeRoute(route);void flushRumble().catch(()=>{});
  }};
});
