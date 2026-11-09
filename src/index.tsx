import {useEffect, useRef, useState} from 'react';
import {ButtonItem, PanelSection, PanelSectionRow, SliderField, ToggleField, DropdownItem,
  ConfirmModal, showModal, Navigation, Router, SidebarNavigation, Focusable} from '@decky/ui';
import {callable, definePlugin, routerHook} from '@decky/api';

const route = '/msi-claw-a8-controller-suite';
const t = (zh: string, en: string) => /^zh(?:[-_]|$)/i.test(navigator.language) ? zh : en;
type Rules = Record<string, string[]>;
type Entry = {name: string; rules: Rules; enabled?: boolean};
type Config = {revision: number; default: Rules; games: Record<string, Entry>};
type State = {config: Config; game: string | null; game_name: string; applied: string | null; apply_error?: string;
  managed: boolean; last_error?: string; call_log?: string[]; consistent?: boolean;
  pid?: number; started?: string;
  rumble_test?: {state: string; code?: string; detail?: string};
  hardware?: {mode: string; left: number; right: number};
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
const buttons = ['M2','M1','A','B','X','Y','LB','RB','LS','RS','Up','Down','Left','Right','Menu','View'];
const keys = ['Space','Enter','Esc','Tab','LeftShift','LeftCtrl','LeftAlt', ...'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'];
const outputs = [...buttons, ...keys.map(k => 'key:Key'+k), 'mouse:Left','mouse:Right','mouse:Middle'];
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const buttonLabel = (key: string) => key==='M2'?t('左 M2','Left M2'):key==='M1'?t('右 M1','Right M1'):key;

function errorText(code?: string): string {
  const messages: Record<string, [string,string]> = {
    not_a8:['未确认是 A8 主机','A8 motherboard was not identified'],
    device_missing:['未找到已确认的内置控制接口','Verified embedded controls were not found'],
    device_ambiguous:['设备不唯一，已停止操作','Ambiguous device; operation blocked'],
    composite_ambiguous:['无法唯一确认内置 InputPlumber 设备','Cannot uniquely identify the embedded InputPlumber device'],
    system_defaults_unavailable:['无法读取本机 A8 系统默认配置，未猜测替代配置；请运行诊断','Installed A8 system defaults are unavailable; run diagnostics'],
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
let rumbleWrite: Promise<void> | undefined;
let writeError = '';
let outstanding = 0;
const stateListeners = new Set<() => void>();
const enqueue = <T,>(action: () => Promise<Result<T>>): Promise<T> => {
  outstanding++;
  // then() hands the previous value to its callback. Never forward it: a
  // zero-argument callable would otherwise reach Python with one extra
  // positional argument and fail before its body runs.
  const next = chain.then(() => action()).then(r => {if (!r.ok) throw new Error(errorText(r.error)); return r.data;}).finally(()=>{outstanding--;});
  chain = next.catch(e => {writeError = String(e);});
  return next;
};
function flushRumble() {
  clearTimeout(rumbleTimer); rumbleTimer = undefined;
  // Await a save already started by the debounce, but forget settled failures:
  // a stale chain/error must not block every later test.
  if (!pending) return rumbleWrite ?? Promise.resolve();
  const [left,right] = pending; pending = undefined;
  writeError = '';
  const write = enqueue(() => setHardware(null,left,right)).then(
    () => {writeError = '';},
    e => {writeError = String(e); throw e;});
  rumbleWrite = write;
  const settled = () => {if (rumbleWrite === write) rumbleWrite = undefined;};
  void write.then(settled, settled);
  return write;
}
function scheduleRumble(left: number, right: number) {
  pending = [left,right]; clearTimeout(rumbleTimer);
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
function Feedback({c,showDisabled=false}: {c: Controller; showDisabled?: boolean}) {
  const s=c.state;
  const disabled=showDisabled && s && !s.managed && !s.apply_error;
  if(s && !c.error && !s.apply_error && !s.hardware_error && !disabled)return null;
  return <PanelSection>
    {c.error&&row(c.error)}
    {!s&&row(t('正在读取…','Reading…'))}
    {disabled&&row(t('管理已停用；修改可保存，启用后生效。','Management disabled; edits can be saved and apply when enabled.'))}
    {s?.apply_error && <>
      {row((s.managed?t('尚未生效：','Not applied: '):t('系统默认尚未恢复：','System defaults not yet restored: '))+errorText(s.apply_error))}
      <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>void c.run(()=>enqueue(()=>manage(s.managed)))}>{t('重试','Retry')}</ButtonItem></PanelSectionRow>
    </>}
    {s?.hardware_error&&row(errorText(s.hardware_error))}
  </PanelSection>;
}
function RumblePanel({c,shared=true}: {c: Controller; shared?: boolean}) {
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
  const result = c.state?.rumble_test;
  return <PanelSection title={shared?t('震动 · 所有游戏共用','Rumble · shared by all games'):t('震动','Rumble')}>
    {[0,1].map(i => <PanelSectionRow key={i}><SliderField label={(i===0?t('左','Left'):t('右','Right'))+` ${values[i]}%`}
      value={values[i]} min={0} max={100} step={5} disabled={!hw || testing || c.busy} onChange={v=>change(i,v)}/></PanelSectionRow>)}
    <PanelSectionRow><ButtonItem disabled={!hw || !c.state?.can_test || testing || c.busy} layout="below" onClick={() => {
      setTesting(true);setError('');
      void (async()=>{
        // Saving the slider value and sending the test are different calls; a
        // failed save must not abort or masquerade as a failed test.
        try {
          await flushRumble();
        } catch(e) {
          setError(t('震动值未保存：','Rumble value not saved: ')+String(e));
          setTesting(false); return;
        }
        try {
          await enqueue(() => testRumble());
        } catch(e) {
          setError(t('测试调用失败：','Test call failed: ')+String(e));
        } finally {setTesting(false);}
        setTimeout(()=>{void c.refresh();},350);
        setTimeout(()=>{void c.refresh();},1100);
      })();
    }}>{testing?t('测试中…','Testing…'):t('测试震动 · 0.5 秒','Test rumble · 0.5 seconds')}</ButtonItem></PanelSectionRow>
    {result?.state==='running'&&row(t('正在发送震动…','Sending the pulse…'))}
    {result?.state==='ok'&&row(t('上次测试：已向内置手柄发送 0.5 秒效果。','Last test: a 0.5 second effect was sent to the embedded controller.'))}
    {result?.state==='error'&&row(t('上次测试失败：','Last test failed: ')
      +(result.code&&result.code!=='operation_failed'?errorText(result.code):(result.detail||result.code||'')))}
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
  {zh:'背键',en:'Back buttons',rows:[['M2','M1']]},
  {zh:'动作键',en:'Face buttons',rows:[['A','B'],['X','Y']]},
  {zh:'方向键',en:'D-pad',rows:[['Up','Down'],['Left','Right']]},
  {zh:'肩键',en:'Shoulder buttons',rows:[['LB','RB']]},
  {zh:'摇杆按下',en:'Stick clicks',rows:[['LS','RS']]},
  {zh:'菜单键',en:'Menu buttons',rows:[['View','Menu']]},
];
// Upstream hardware identifiers stay visible; the Chinese label translates the
// identifier only, because each mode's exact event behaviour is still unverified.
const MODES = [
  {key:'macro', zh:'Macro（宏）', en:'Macro'},
  {key:'combination', zh:'Combination（组合键）', en:'Combination'},
  {key:'disabled', zh:'Disabled（禁用）', en:'Disabled'},
] as const;

function Editor({c,scope,name,onClose}: {c: Controller; scope: string; name: string; onClose: () => void}) {
  const config=c.state!.config;
  const entry = scope==='default'?undefined:config.games[scope];
  const [rules,setRules]=useState<Rules>(()=>clone(entry?.rules ?? config.default));
  const [enabled,setEnabled]=useState(entry?.enabled ?? true);
  const title=name;
  const [dirty,setDirty]=useState(false);
  const [source,setSource]=useState('default');
  const [revision,setRevision]=useState(config.revision);
  const choices=[{data:'default',label:t('默认按键','Default buttons')},
    ...Object.entries(config.games).filter(([id])=>id!==scope).map(([id,e])=>({data:id,label:e.name}))];
  function copySource() {
    const copied=source==='default'?config.default:config.games[source].rules;
    setRules(clone(copied));setDirty(true);
  }
  const close=()=>dirty?confirm(t('放弃未保存修改？','Discard unsaved changes?'),t('已保存的配置保持不变。','Saved configuration stays unchanged.'),onClose):onClose();
  return <Focusable flow-children="column" onCancel={e=>{e.stopPropagation();close();}}>
    <PanelSection title={t('正在编辑：','Editing: ')+(scope==='default'?t('默认按键','Default buttons'):title)}>
      {row(scope==='default'?t('影响使用默认按键的游戏，不影响独立副本。','Affects games using defaults, not independent copies.'):
        c.state?.game===scope?t('仅影响本游戏；保存并启用后应用。','Only this game; applied when saved and enabled.'):
        t('本游戏当前未运行，保存后下次启动生效。','This game is not running; saved changes apply next launch.'))}
      {scope!=='default'&&<PanelSectionRow><ToggleField label={t('使用本游戏专用按键','Use this game’s custom buttons')} checked={enabled}
        onChange={v=>{setEnabled(v);setDirty(true);}}/></PanelSectionRow>}
      <FocusEntry active><PanelSectionRow><DropdownItem label={t('复制来源','Copy from')} selectedOption={source} rgOptions={choices} onChange={(v:{data:string})=>setSource(v.data)}/></PanelSectionRow></FocusEntry>
      <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>confirm(t('替换编辑草稿','Replace draft'),t('复制后互不关联；保存前不改变已有配置。','Copies are independent. Existing settings change only after saving.'),copySource)}>{t('复制到此草稿','Copy into this draft')}</ButtonItem></PanelSectionRow>
    </PanelSection>
    <PanelSection title={t('按键映射','Button mappings')}>
      {mappingGroups.map(group=><div key={group.en} style={{marginBottom:12}}>
        <div style={{fontSize:14,fontWeight:600,margin:'8px 0'}}>{t(group.zh,group.en)}</div>
        {group.rows.map(pair=><Focusable key={pair.join('-')} flow-children="row" style={{display:'flex',gap:12}}>
          {pair.map(b=><div key={b} style={{flex:'1 1 0',minWidth:0}}>
            <DropdownItem layout="below" label={buttonLabel(b)} description={c.state?.inputplumber?.sources.includes(b)?undefined:t('输入待验证','Input unverified')}
              selectedOption={rules[b]?.length===0?'disabled':rules[b]?.[0]??'unchanged'} rgOptions={[{data:'unchanged',label:t('保持基础映射','Keep base mapping')},{data:'disabled',label:t('不输出','No output')},...outputs.map(o=>({data:o,label:buttonLabel(o)}))]}
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
  const top=useRef<HTMLDivElement>(null);
  const frame=useRef(0);
  useEffect(()=>()=>cancelAnimationFrame(frame.current),[]);
  function revealTop() {
    cancelAnimationFrame(frame.current);
    // Run after Steam's focus scrolling, so it cannot leave the status above
    // the viewport. Merely refreshing status must never move focus or scroll.
    frame.current=requestAnimationFrame(()=>{
      frame.current=requestAnimationFrame(()=>top.current?.scrollIntoView({block:'start',behavior:'auto'}));
    });
  }
  const game=s?.game && s.game!=='default'?s.game:undefined;
  const scope=s?.applied;
  const rules=scope==='default'?s?.config.default:scope?s?.config.games[scope]?.rules:undefined;
  const current=!s?.managed?t('管理已停用','Management disabled'):
    scope==='default'?t('默认按键','Default buttons'):
    scope?s?.config.games[scope]?.name??scope:t('尚未生效','Not applied');
  function outputLabel(key:string) {
    const outputs=rules?.[key];
    return outputs===undefined?t('系统默认映射','System default mapping'):
      outputs.length?outputs.map(buttonLabel).join(' + '):t('不输出','No output');
  }
  function open(scope?:string,name?:string) {
    requestedScope=scope?{scope,name:name??''}:undefined;
    Navigation.Navigate(route);Navigation.CloseSideMenus();
  }
  return <><div ref={top}><Feedback c={c}/>{s&&<PanelSection>
    <PanelSectionRow>
      <Focusable tabIndex={0} role="group" aria-label={t('当前按键摘要','Current button summary')}
        onFocus={revealTop} onGamepadFocus={revealTop}
        style={{padding:'10px 4px',lineHeight:1.5,overflowWrap:'anywhere'}}>
        <div style={{fontSize:16,fontWeight:600}}>{t('当前按键：','Current buttons: ')+current}</div>
        {game&&<div style={{fontSize:13,marginTop:4}}>{t('游戏：','Game: ')+(s.game_name||game)}</div>}
        {s.game===null&&<div style={{fontSize:13,marginTop:4}}>{t('正在读取游戏状态，暂不切换配置','Reading game status; keeping the current configuration')}</div>}
        {s.managed&&rules&&<div style={{fontSize:14,marginTop:8}}>
          {['M2','M1'].map(key=><div key={key}>{buttonLabel(key)+' → '+outputLabel(key)}</div>)}
        </div>}
      </Focusable>
    </PanelSectionRow>
    <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>open(game??'default',game?s.game_name:t('默认按键','Default buttons'))}>
      {game?(s.config.games[game]?t('编辑：','Edit: '):t('为本游戏单独设置：','Customize this game: '))+s.game_name:t('编辑默认按键','Edit default buttons')}</ButtonItem></PanelSectionRow>
  </PanelSection>}</div><RumblePanel c={c}/><PanelSection><PanelSectionRow><ButtonItem onClick={()=>open()}>{t('打开设置','Open settings')}</ButtonItem></PanelSectionRow></PanelSection></>;
}

function Settings({page}:{page:'configs'|'hardware'|'about'}) {
  const c=useController();const s=c.state;
  const [editing,setEditing]=useState<{scope:string;name:string}|undefined>(()=>{const req=requestedScope;requestedScope=undefined;return page==='configs'?req:undefined;});
  const returnTo=useRef<string|undefined>(undefined);
  function openEditor(entry:{scope:string;name:string},origin=entry.scope){returnTo.current=origin;setEditing(entry);}
  function closeEditor(){setEditing(undefined);}
  if(!s)return <Feedback c={c}/>;
  if(editing)return <><Feedback c={c} showDisabled/><Editor key={editing.scope} c={c} {...editing} onClose={closeEditor}/></>;
  return <><Feedback c={c} showDisabled={page==='configs'}/>
    {page==='configs'&&<PanelSection>
      <FocusEntry active={returnTo.current==='default'}><PanelSectionRow><ButtonItem onClick={()=>openEditor({scope:'default',name:t('默认按键','Default buttons')})}>{t('编辑默认按键','Edit default buttons')}</ButtonItem></PanelSectionRow></FocusEntry>
      {s.game&&s.game!=='default'&&!s.config.games[s.game]&&<FocusEntry active={returnTo.current===s.game}><PanelSectionRow><ButtonItem onClick={()=>openEditor({scope:s.game!,name:s.game_name})}>{t('为当前游戏创建：','Create for current game: ')+s.game_name}</ButtonItem></PanelSectionRow></FocusEntry>}
      {Object.entries(s.config.games).map(([id,e])=><PanelSection key={id} title={e.name}>
        {row(e.enabled?t('已启用专用配置','Custom configuration enabled'):t('已停用，当前跟随默认','Disabled; uses defaults'))}
        <FocusEntry active={returnTo.current===id}><PanelSectionRow><ButtonItem onClick={()=>openEditor({scope:id,name:e.name})}>{t('编辑','Edit')}</ButtonItem></PanelSectionRow></FocusEntry>
        <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>confirm(t('删除专用配置？','Delete custom configuration?'),e.name,()=>void c.run(()=>enqueue(()=>deleteConfig(id,s.config.revision))))}>{t('删除并使用默认','Delete and use defaults')}</ButtonItem></PanelSectionRow>
      </PanelSection>)}
    </PanelSection>}
    {page==='hardware'&&<>
      <PanelSection>{row(t('本页设置对所有游戏生效','Settings on this page apply to all games'))}</PanelSection>
      <PanelSection title={t('背键硬件模式','Back-button hardware mode')}>
        {MODES.map(mode=><PanelSectionRow key={mode.key}><ButtonItem disabled={c.busy||!s.hardware}
          onClick={()=>void c.run(()=>enqueue(()=>setHardware(mode.key,null,null)))}>{s.hardware?.mode===mode.key?'● ':'○ '}{t(mode.zh,mode.en)}</ButtonItem></PanelSectionRow>)}
        {row(t('两个背键共用一个模式，点选立即写入硬件；不改变按键映射，也不会自动更改。','Both back buttons share one mode. Selecting writes it immediately; button mappings are unchanged and it is never set automatically.'))}
      </PanelSection>
      <RumblePanel c={c} shared={false}/>
    </>}
    {page==='about'&&<>
      <PanelSection title={t('插件管理','Plugin management')}>
        {row(s.managed
          ? t('管理已启用 · Xbox Elite','Management enabled · Xbox Elite')
          : t('管理已停用','Management disabled'))}
        {row(t('仅管理 A8 内置手柄，不影响外接手柄。','Only the embedded A8 controller is managed; external controllers are unaffected.'))}
        {s.inputplumber_error&&row(errorText(s.inputplumber_error))}
        {s.managed&&s.consistent===false&&row(t('检测到手柄的实际输出与套件期望不一致（可能被外部重置）。点“重试”重新应用，不会自动改写。','The controller output differs from what this suite expects, possibly after an external reset. Use Retry to re-apply; nothing is rewritten automatically.'))}
        <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>{
          if(!s.managed){void c.run(()=>enqueue(()=>manage(true)));return;}
          confirm(t('恢复系统默认并停用管理？','Restore system defaults and disable management?'),
            t('内置手柄的输出和按键映射将恢复为本机系统默认，不恢复旧插件的自定义配置。此后保持停用，直到再次启用。背键硬件模式和震动不变。','Restore the installed system defaults, not another plugin’s custom configuration. Management stays disabled until you enable it again. Hardware back-button mode and rumble stay unchanged.'),
            ()=>void c.run(()=>enqueue(()=>manage(false))));
        }}>{s.managed?t('恢复系统默认并停用','Restore system defaults and disable'):t('启用管理','Enable management')}</ButtonItem></PanelSectionRow>
      </PanelSection>
      <PanelSection title={t('安装与维护','Installation and maintenance')}>
        {row('0.1.0-alpha.18 · GPL-3.0-only')}
        {row(t('安装后请重启；持续震动异常可参考 MSI 官方 EC 恢复说明。','Reboot after installation. For persistent rumble issues, consult MSI’s official EC reset guidance.'))}
        {(['install','reinstall','uninstall'] as const).map(action=><PanelSectionRow key={action}><ButtonItem disabled={c.busy} onClick={()=>confirm(
          action==='uninstall'?t('干净卸载插件','Clean uninstall'):action==='reinstall'?t('干净重装当前版本','Clean reinstall current version'):t('修复安装当前版本','Repair current version'),
          t('将短暂重启 Decky。修复保留配置；重装清除按键配置并保留启用选择；卸载先恢复系统默认。硬件震动与背键模式不重置。卸载恢复失败时保留文件。','Decky restarts briefly. Repair keeps settings; reinstall clears mappings and keeps the management choice; uninstall restores system defaults first. Hardware settings stay unchanged. Failed uninstall restoration preserves files.'),
          ()=>void c.run(()=>enqueue(()=>maintenance(action))))}>
          {action==='uninstall'?t('干净卸载','Clean uninstall'):action==='reinstall'?t('干净重装当前版本','Clean reinstall current version'):t('修复安装 · 保留配置','Repair installation · keep configurations')}
        </ButtonItem></PanelSectionRow>)}
      </PanelSection>
      <PanelSection title={t('诊断信息','Diagnostics')}>
        <PanelSectionRow><ButtonItem disabled={c.busy} onClick={()=>void c.run(async()=>{})}>{t('刷新诊断','Refresh diagnostics')}</ButtonItem></PanelSectionRow>
        {s.last_error&&row(t('最近的后端错误：','Last backend error: ')+s.last_error)}
        {row(JSON.stringify({pid:s.pid, started:s.started, managed:s.managed, consistent:s.consistent, hardware:s.hardware, hardware_error:s.hardware_error, inputplumber:s.inputplumber, inputplumber_error:s.inputplumber_error, can_test:s.can_test, rumble_test:s.rumble_test, last_error:s.last_error, call_log:s.call_log},null,2))}
      </PanelSection>
    </>}
  </>;
}

export default definePlugin(()=>{
  let last:string|undefined;let reported:string|undefined;let stable=0;let ticking=false;
  const tick=async()=>{
    if(ticking)return;ticking=true;
    try {
      const app=Router.MainRunningApp;
      const id=app?.appid?String(app.appid):'default';
      // Only a change is worth a backend call. The old periodic re-report fed a
      // 5 s backend poll; both are gone now.
      if(id===reported)return;
      stable=id===last?stable+1:0;last=id;
      if(stable<2)return;
      reported=id;
      await reportGame(id,app?.display_name??'');
      stateListeners.forEach(fn=>fn());
    } catch {await reportGame(null,'').catch(()=>{});} finally {ticking=false;}
  };
  const interval=setInterval(()=>void tick(),1000);
  routerHook.addRoute(route,()=> <SidebarNavigation title="MSI Claw A8 Controller Suite" showTitle pages={[
    {title:t('按键配置','Button configurations'),content:<Settings page="configs"/>,route:route+'/configs'},
    {title:t('手柄设置','Device settings'),content:<Settings page="hardware"/>,route:route+'/hardware'},
    {title:t('维护与关于','Maintenance and about'),content:<Settings page="about"/>,route:route+'/about'},
  ]}/>);
  return {name:'MSI Claw A8 Controller Suite',icon:<span>🎮</span>,content:<QuickPanel/>,onDismount(){
    clearInterval(interval);routerHook.removeRoute(route);void flushRumble().catch(()=>{});
  }};
});
