import { useState } from 'react'
import { ChevronRight, CircleUserRound, Compass, Leaf, LockKeyhole, MapPin, Minus, Plus, Scroll, Shield, Sparkles, Sword, X } from 'lucide-react'
import BottomNav from '../components/BottomNav'
import PlayerHeader from '../components/PlayerHeader'
import { debugMode } from '../debugMode'
import terrainMapUrl from '../../../backend/admin/assets/official/ionia/runeterra-terrain.jpg'

const coreAttributeNames = {martial:'武艺',physique:'体魄',perception:'灵觉',willpower:'心志',agility:'机敏',social:'交涉'}
const personalityNames = {peace:'和平倾向',power:'力量观',freedom:'自由倾向',spirit:'灵性亲和',destiny:'命运态度'}
const fateNames = {guardian:'守护命运',strong:'强者命运',wanderer:'流浪命运',spirit:'灵界命运',breaker:'破局命运'}
const locationIcons = { village: Leaf, forest: Compass, ruins: Sword, temple: Sparkles }

export default function GamePage({ game, world, event, result, tab, busy, eventState, onTab, onTravel, onRecover, onInterveneThread, onFocusWorldTopic, onChoice, onDialogue, onCloseEvent, onRestart }) {
  const location = world.locations.find(x => x.id === game.location)
  const localNpcs = world.npcs.filter(n => n.location === game.location || n.id === 'companion')
  return <main className="game-page page-enter">
    <PlayerHeader game={game} location={location}/>
    <section className="game-content">
      {tab === 'story' && <Story game={game} location={location} result={result} npcs={world.npcs} onMap={() => onTab('map')} onRestart={onRestart}/>}
      {tab === 'map' && <WorldMap locations={world.locations} mapPlaces={world.map_places || []} current={game.location} points={game.action_points} time={game.time} chapterComplete={game.chapter_complete} chapterPhase={game.chapter_phase} bodyCondition={game.player.bodyCondition} busy={busy} onTravel={onTravel} onRecover={onRecover}/>}
      {tab === 'people' && <People npcs={localNpcs} relationships={game.relationships} onDialogue={onDialogue}/>} 
      {tab === 'status' && <Status
        player={game.player} game={game} busy={busy}
        onInterveneThread={onInterveneThread} onFocusWorldTopic={onFocusWorldTopic}
      />}
    </section>
    <BottomNav active={tab} onChange={onTab}/>
    {event && <EventSheet event={event} busy={busy} eventState={eventState} onChoice={onChoice} onClose={onCloseEvent}/>} 
  </main>
}

function Story({ game, location, result, npcs, onMap, onRestart }) {
  const resolution = result && typeof result === 'object' ? result : game.last_resolution
  const latest = resolution?.narrative || result || game.log.at(-1)
  return <div className="story-view">
    <div className="scene-art"><div className="scene-moon"/><div className="scene-ridge"/><span>{location.subtitle}</span></div>
    <div className="chapter-title"><span>{game.chapter_complete ? '第一章 · 完' : `第一章 · ${game.time.total_actions} / ${game.time.chapter_limit}`}</span><h3>{game.chapter_complete ? '血旗落下之后' : '风从帕拉斯吹来'}</h3></div>
    <article><Scroll size={18}/><div className="narrative-copy">{String(latest).split('\n\n').map((p,i) => <p key={i}>{p}</p>)}</div></article>
    <WorldSignals signals={game.latestWorldSignals || []}/>
    {resolution && <ResolutionPanel resolution={resolution} npcs={npcs}/>} 
    {game.demo_complete ? <DemoEnding summary={game.chapter_summary} onRestart={onRestart}/> : game.battle_complete && <div className="milestone"><Shield size={18}/><div><b>旅途印记 · 初战</b><span>你已经历一次真正的战斗。故事仍在继续。</span></div></div>}
    {!game.demo_complete && <button className="next-action" onClick={onMap}><span><Compass size={19}/>{game.time.total_actions >= 12 ? '继续第一章终章' : '选择下一次行动'}</span><ChevronRight/></button>}
  </div>
}

function DemoEnding({ summary, onRestart }) {
  const safe = summary || {title:'第一章 · 血旗落下之后',result:'这一年的旅途已经告一段落。',playerLegacy:'无名者',lines:[],nextChapterHook:'故事仍会继续。'}
  return <section className="demo-ending">
    <span>试玩 Demo 完成</span><h3>{safe.title}</h3><p>{safe.result}</p><div className="ending-legacy"><Shield size={18}/><div><small>本章留下的名字</small><b>{safe.playerLegacy}</b></div></div>
    <div className="ending-lines">{safe.lines.map(line=><article key={line.id}><span>本章收束</span><h4>{line.title}</h4><b>{line.closure}</b><p>{line.detail}</p><small>后续伏笔 · {line.hook}</small></article>)}</div>
    <blockquote>{safe.nextChapterHook}</blockquote><button className="restart-demo" onClick={onRestart}>重新开始试玩</button>
  </section>
}

function ResolutionPanel({ resolution, npcs }) {
  const changes = resolution.changes || {attributes:{},personality:{},fate:{},relations:{}}
  const costs = resolution.costs || {attributes:{},personality:{},fate:{},relations:{}}
  const positiveOnly = values => Object.fromEntries(Object.entries(values || {}).filter(([,value]) => value > 0))
  const groups = [
    ['人格成长', positiveOnly(changes.personality), personalityNames],
    ['命运倾向', positiveOnly(changes.fate), fateNames],
  ].filter(([, values]) => Object.keys(values).length)
  const costGroups = [
    ['人格取舍', costs.personality || {}, personalityNames],
    ['命运代价', costs.fate || {}, fateNames],
  ].filter(([, values]) => Object.keys(values).length)
  return <section className="resolution-panel">
    <div className="resolution-title"><Sparkles size={16}/><div><b>{resolution.battle?.is_boss ? '第一章终局结算' : resolution.outcome ? `${resolution.outcome.label} · 现场结果` : '现场结果'}</b><span>{resolution.sceneEnded === false ? '眼前的事情还没有结束' : '这次现场已经告一段落'}</span></div>{resolution.battle && <em className={resolution.battle.victory ? 'win' : 'lose'}>{resolution.battle.is_boss ? (resolution.battle.victory ? 'BOSS 击破' : 'BOSS 战败') : (resolution.battle.victory ? '战斗占优' : '陷入劣势')}</em>}</div>
    {resolution.outcome && <div className={`outcome-check ${resolution.outcome.code}`}><div><span>{resolution.outcome.check}</span><b>{resolution.outcome.label}</b></div><p>{resolution.outcome.requires_check === false ? '这项行动结果明确，没有进行能力检定' : `成功率 ${resolution.outcome.final_probability}%`}</p><small>{resolution.outcome.code === 'failure' ? '未达成原目标，但故事会进入新的困难局面' : resolution.outcome.code === 'partial' ? '完成目标，但必须支付代价' : resolution.outcome.requires_check === false ? '你主动选择了承担这项行动的明确后果' : '检定通过，获得对应收益'}</small>{resolution.outcome.requires_check !== false && <details><summary>查看成功率构成</summary><code>基础成功率 {resolution.outcome.base_probability}% · 最终成功率 {resolution.outcome.final_probability}%</code>{resolution.outcome.applied_modifiers?.map((modifier,index)=><em key={index}>{modifier.label} {modifier.value>=0?'+':''}{modifier.value}{modifier.mode==='percent'?'%':''}</em>)}</details>}{debugMode && <details><summary>开发信息</summary><pre>{JSON.stringify(resolution.outcome, null, 2)}</pre></details>}</div>}
    {groups.map(([title, values, labels]) => <div className="change-group" key={title}><h5>{title}</h5><div>{Object.entries(values).map(([key, value]) => <span className={value >= 0 ? 'up' : 'down'} key={key}>{labels[key] || key}<b>{value >= 0 ? '+' : ''}{value}</b></span>)}</div></div>)}
    {Object.keys(positiveOnly(changes.relations)).length > 0 && <div className="change-group"><h5>人物关系收益</h5><div>{Object.entries(positiveOnly(changes.relations)).map(([id,value]) => <span className="up" key={id}>{npcs.find(n=>n.id===id)?.name || id}<b>+{value}</b></span>)}</div></div>}
    {costGroups.length > 0 && <div className="cost-block"><header>本次代价</header>{costGroups.map(([title, values, labels]) => <div className="change-group" key={title}><h5>{title}</h5><div>{Object.entries(values).map(([key,value]) => <span className="down" key={key}>{labels[key] || key}<b>{value}</b></span>)}</div></div>)}{Object.keys(costs.relations || {}).length > 0 && <div className="change-group"><h5>人物关系损失</h5><div>{Object.entries(costs.relations).map(([id,value]) => <span className="down" key={id}>{npcs.find(n=>n.id===id)?.name || id}<b>{value}</b></span>)}</div></div>}</div>}
    {resolution.items?.map(item => <div className="loot-card" key={item.name}><div><span>获得物品 · {item.rarity}</span><b>{item.name}</b><p>{item.description}</p></div>{item.effects?.length > 0 && <ul>{item.effects.map(effect => <li key={effect}>{effect}</li>)}</ul>}</div>)}
    {resolution.missed_items?.length > 0 && <div className="missed-loot"><span>未能获得</span><b>{resolution.missed_items.join('、')}</b><p>这件物品随失败的机会一同离开，未来或许还有其他取得方式。</p></div>}
    {resolution.worldFeedback?.worldChanged && <div className="world-feedback"><span>这件事改变了附近正在发展的局势</span>{resolution.worldFeedback.newPlayableSituation && <p>{resolution.worldFeedback.newPlayableSituation}</p>}</div>}
    {resolution.worldFeedback?.heroChanged && <div className="world-feedback"><span>这次相逢改变了对方对你的看法</span></div>}
    {debugMode && resolution.worldFeedback?.thread && <div className="world-feedback"><span>开发信息</span><pre>{JSON.stringify(resolution.worldFeedback, null, 2)}</pre></div>}
  </section>
}

const pallasLocalPositions = {
  pallas: [50, 50],
  windbreak: [29, 27],
  war_ruins: [25, 72],
  mountain_temple: [76, 27],
}

function WorldMap({ locations, mapPlaces, current, points, time, chapterComplete, chapterPhase, bodyCondition, busy, onTravel, onRecover }) {
  const [mapLevel, setMapLevel] = useState('ionia')
  const remaining = Math.max(0, time.chapter_limit - time.total_actions)
  const overviewPlaces = mapPlaces.filter(place => place.id !== 'ionian_archipelago')
  const openPallas = () => setMapLevel('pallas')
  const inFinale = !chapterComplete && time.total_actions >= 12
  const finaleNext = {12:['mountain_temple','终章一 · 前往山寺平息灵界异象'],13:['war_ruins','终章二 · 赴战争遗迹与亚索会合'],14:['pallas','终章三 · 返回帕拉斯布置防线'],15:['pallas','终章四 · 迎战血旗督军']}[time.total_actions]
  const handleLocalKey = (event, locationId) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    if (!busy && locationId !== current) onTravel(locationId)
  }
  return <div className="map-view">
    <div className="section-heading"><p>艾欧尼亚 · 东部</p><h3>{inFinale ? '第一章终章' : '选择去处'}</h3><span>{chapterComplete ? '试玩已经结束' : inFinale ? '最后四幕将依次推进' : `${points} 次行动可用${points === 0 ? ' · 下一次行动进入新季节' : ''}`}</span><div className="chapter-countdown"><i><span style={{width:`${Math.min(100,time.total_actions / time.chapter_limit * 100)}%`}}/></i><b>{chapterComplete ? '第一章已经结束' : `一年之期 · 还剩 ${remaining} 次行动`}</b></div></div>
    {inFinale && finaleNext && <section className="finale-next"><span>固定终章 · {time.total_actions - 11} / 4</span><b>{finaleNext[1]}</b><p>终章已经开始，调查、休息和自由旅行暂时关闭。完成这一幕后才会进入下一段收尾。</p><button disabled={busy} onClick={()=>onTravel(finaleNext[0])}>继续终章</button></section>}
    <div className={`map-canvas map-level-${mapLevel}`}>
      <div className="map-window-label"><b>{mapLevel === 'ionia' ? '艾欧尼亚大陆' : '帕拉斯地区'}</b><span>{mapLevel === 'ionia' ? '灰色地点暂未开放' : '四个章节探索地点'}</span></div>
      <div className="map-zoom-controls" aria-label="地图窗口缩放"><button disabled={mapLevel === 'ionia'} onClick={() => setMapLevel('ionia')} aria-label="缩小至艾欧尼亚全境"><Minus size={13}/>全境</button><button disabled={mapLevel === 'pallas'} onClick={openPallas} aria-label="放大至帕拉斯地区"><Plus size={13}/>帕拉斯</button></div>
      {mapLevel === 'ionia' ? <svg className="official-game-map overview-map" viewBox="1180 480 760 700" preserveAspectRatio="xMidYMid meet" role="img" aria-label="艾欧尼亚大陆与数据库地点">
        <image href={terrainMapUrl} x="0" y="0" width="2048" height="2048"/>
        <text className="ionia-continent-label" x="1535" y="645">艾欧尼亚大陆</text>
        {overviewPlaces.map(place => { const p=place.map_position; const isPallas=place.id==='pallas'; const estimated=p.mode==='estimated_area'; return <g key={place.id} className={`world-map-pin ${isPallas?'pallas-open':'locked'} ${estimated?'estimated':''}`} transform={`translate(${p.x} ${p.y})`} role={isPallas?'button':'img'} tabIndex={isPallas?0:undefined} aria-label={isPallas?'帕拉斯，点击放大':'暂未开放，'+place.name} onClick={isPallas?openPallas:undefined} onKeyDown={isPallas ? event => { if(event.key==='Enter'||event.key===' '){event.preventDefault();openPallas()} } : undefined}>{estimated && <circle className="estimate-range" r={p.radius || 45}/>}<circle className="anchor" r={isPallas?10:7}/><text y="24">{place.name}</text>{isPallas && <text className="pin-status" y="41">点击进入</text>}</g> })}
      </svg> : <svg className="official-game-map pallas-detail-map" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" role="img" aria-label="帕拉斯的四个章节地点">
        <image href={terrainMapUrl} x="0" y="0" width="100" height="100" preserveAspectRatio="xMidYMid slice"/>
        <path className="local-route" d="M50 50 L29 27 M50 50 L25 72 M50 50 L76 27"/>
        {locations.map(loc => { const [x,y]=pallasLocalPositions[loc.id]; const active=loc.id===current; const isPallas=loc.id==='pallas'; return <g key={loc.id} className={`local-map-pin ${active?'current':''} ${isPallas?'hub':''}`} transform={`translate(${x} ${y})`} role="button" tabIndex="0" aria-label={`${loc.name}${active?'，当前位置':'，前往需要一次行动'}`} onClick={() => !busy && !active && onTravel(loc.id)} onKeyDown={event => handleLocalKey(event,loc.id)}><circle r={isPallas?4:3}/><text y="8">{loc.name}</text><text className="pin-status" y="13">{active?'当前位置':isPallas?'返回 · 1':'前往 · 1'}</text></g> })}
      </svg>}
      <div className="map-wash wash-a"/><div className="map-wash wash-b"/>
    </div>
    <div className="map-note"><span><MapPin size={14}/>{mapLevel === 'ionia' ? '点击帕拉斯，在地图窗口内放大' : '使用窗口右上角按钮返回全境'}</span></div>
    {!inFinale && current === 'pallas' && <section className="recovery-card"><div><span>安全地点 · 稳定恢复</span><b>在帕拉斯休息</b><p>解除疲惫和紧张，使伤势改善一级。消耗 1 次行动，时间成本 1。</p></div><button disabled={busy || points <= 0 || bodyCondition?.state === 'healthy'} onClick={onRecover}>休息 / 治疗</button></section>}
    {!inFinale && <section className="travel-list"><header><div><span>周边行程</span><b>章节探索地点</b></div><small>帕拉斯地区内的四个可探索地点</small></header>{locations.map(loc => { const Icon=locationIcons[loc.icon]; const active=loc.id===current; return <button disabled={busy||active||chapterComplete} key={loc.id} onClick={() => onTravel(loc.id)} className={active?'current':''}><i><Icon size={17}/></i><div><b>{loc.name}</b><small>{loc.description}</small></div><em>{active?'当前位置':'前往 · 1'}</em></button> })}</section>}
  </div>
}

function People({ npcs, relationships, onDialogue }) {
  return <div className="people-view"><div className="section-heading"><p>相逢并非偶然</p><h3>旅途中认识的人</h3></div><div className="npc-list">{npcs.map(npc => { const rel = relationships[npc.id]; return <button key={npc.id} onClick={() => onDialogue(npc.id)}><span className="npc-avatar"><CircleUserRound/></span><div><b>{npc.name}</b><small>{npc.job} · {npc.personality}</small><em>{rel.memories.length ? rel.memories.at(-1) : '你们尚未留下共同记忆'}</em></div><i>{rel.score > 10 ? '信任' : rel.score > 0 ? '相识' : '陌生'} · {rel.score}</i></button> })}</div></div>
}

function Status({ player, game, busy, onInterveneThread, onFocusWorldTopic }) {
  return <div className="status-view"><div className="section-heading"><p>普通人的传说</p><h3>{player.name}的人物档案</h3></div>
    <div className="profile-card"><span>{player.age}</span><div><b>{player.family}</b><small>{player.birthplace}</small></div></div>
    <h4>第一章时间轴 <small>一年 · 四季 · 每季4次行动</small></h4><SeasonTimeline time={game.time} complete={game.chapter_complete}/>
    <h4>角色状态</h4><section className={`body-condition ${player.bodyCondition.state}`}><header><span>身体状况</span><b>{player.bodyCondition.label}</b></header><p>{player.bodyCondition.description}</p>{debugMode && <div>{Object.entries(player.bodyCondition.modifiers || {}).map(([key,value])=><em key={key}>{coreAttributeNames[key]} {value}%</em>)}</div>}</section>
    <div className="effect-list">{player.statuses?.length ? player.statuses.map(item=><span key={item.id || item.name}>状态 · {item.name} · {item.duration ?? '条件解除'}</span>) : <small>没有临时状态</small>}{player.traits?.map(item=><span key={item.id}>特质 · {item.name} Lv.{item.level}</span>)}</div>
    <h4>核心能力 <small>决定你能不能做到</small></h4><div className="core-stat-grid">{Object.entries(player.coreAbilities || {}).map(([key,value])=><div key={key}><span>{coreAttributeNames[key]}</span><b>{value}</b></div>)}</div>
    <h4>已知线索</h4><div className="effect-list">{player.clues?.length ? player.clues.map(item=><span key={item.name}>{item.name}</span>) : <small>尚未掌握可靠线索</small>}</div>
    <WorldThreads game={game} busy={busy} onInterveneThread={onInterveneThread} onFocusWorldTopic={onFocusWorldTopic}/>
    <h4>人格倾向 <small>描述你倾向怎么做</small></h4><div className="value-bars">{Object.entries(player.personality).map(([key,value]) => <ValueBar key={key} label={personalityNames[key]} value={value}/>)}</div>
    <h4>命运倾向 <small>影响你更容易与哪些类型的故事发生联系</small></h4><div className="value-bars fate-bars">{Object.entries(player.fateAffinities).map(([key,value]) => <ValueBar key={key} label={fateNames[key]} value={value}/>)}</div>
    <h4>行囊 <small>旅途中真正携带的东西</small></h4><div className="inventory-cards">{player.inventory.map(item => <div key={item.name}><header><b>{item.name}</b><span>{item.type || item.rarity}</span></header><p>{item.description}</p>{item.effects?.length > 0 && <footer>{item.effects.map(effect => <em key={effect}>{effect}</em>)}</footer>}</div>)}</div>
    <h4>旅途印记</h4><div className="memory-count"><Scroll/><div><b>{player.memories.length} 段经历</b><span>去过 {game.visited.length} 个地方 · 遇见 {game.completed_events.length} 次选择</span></div></div>
  </div>
}

function WorldSignals({ signals }) {
  const visible = signals.filter(signal => signal.observed || signal.forcedOpportunity)
  if (!visible.length) return null
  return <section className="world-signals"><header>世界征兆</header>{visible.map((signal,index)=><div className={signal.level} key={`${signal.threadId}-${index}`}><b>{signal.level === 'urgent' ? '紧迫变化' : '你注意到'}</b><p>{signal.text}</p></div>)}</section>
}

function WorldThreads({ game, busy, onInterveneThread, onFocusWorldTopic }) {
  const worldState = game.worldState
  const directorState = game.directorState
  const known = game.knownWorldThreads || worldState?.activeThreads?.filter(thread => thread.awareness >= 20 || thread.resolved).map(thread => ({...thread, statusLabel: thread.resolved ? '已形成世界结果' : thread.awareness < 40 ? '模糊传闻' : thread.awareness < 60 ? '确认存在' : thread.awareness < 80 ? '了解危机' : '迫在眉睫', knownText: thread.resolved ? thread.resolvedOutcome.label : thread.awarenessSignals.filter(item=>item.stage<=thread.stage).at(-1)?.text, canInvestigate: thread.interventionWindow !== 'CLOSED', canIntervene: thread.awareness >= 40 && thread.interventionWindow !== 'CLOSED'})) || []
  const focusedTopics = game.focusedWorldTopics || directorState?.focus || []
  return <>
    <h4>世界动态 <small>远方的变化也会传到你的耳边</small></h4>
    <div className="world-thread-list">{known.length ? known.map(thread=>{ const focused=focusedTopics.includes(thread.id); return <article className={thread.interventionWindow.toLowerCase()} key={thread.id}><header><div><span>{thread.statusLabel}</span><b>{thread.title}</b></div><em>{thread.interventionWindow === 'OPEN' ? '仍可介入' : thread.interventionWindow === 'CLOSING' ? '机会缩小' : '主要结果已定'}</em></header><p>{thread.knownText || '你只听到一些尚无法确认的说法。'}</p><footer className="thread-actions"><button className={focused?'focused':''} disabled={busy} onClick={()=>onFocusWorldTopic(thread.id,!focused)}>{focused?'取消关注':'关注此事'}</button>{!thread.resolved && <><button disabled={busy || !thread.canInvestigate} onClick={()=>onInterveneThread(thread.id,'investigate')}>调查线索 · 1</button><button disabled={busy || !thread.canIntervene} onClick={()=>onInterveneThread(thread.id,'intervene')}>主动介入 · 1</button></>}</footer></article>}) : <small>尚未察觉足以辨认的世界动向</small>}</div>
    <h4>旅途日志 <small>记录沿途听闻与亲历</small></h4><div className="journey-log">{known.map(thread=><div key={thread.id}><b>{thread.title}</b><span>{thread.knownText || '尚未确认的传闻'}</span>{thread.worldEffects?.map(effect=><em key={effect}>世界余波 · {effect}</em>)}{focusedTopics.includes(thread.id) && <em>你正在留意这件事</em>}</div>)}</div>
    {debugMode && <><h4>开发信息 <small>完整状态链</small></h4><details className="world-thread-debug"><summary>展开最近一次内部状态</summary><div><pre>{JSON.stringify({scene:game.scene,worldState,directorState,lastResolution:game.last_resolution,ai:game.aiNarratorDebug,stateChangeLog:game.stateChangeLog?.slice(-8)}, null, 2)}</pre></div></details><details className="world-thread-debug"><summary>亚索 Hero Actor 运行时与事件权重</summary><div><pre>{JSON.stringify({runtime:game.heroActors?.yasuo,encounter:game.heroEncounter,actionLog:game.heroActionLog?.slice(-8)}, null, 2)}</pre></div></details></>}
  </>
}

const gameActionUnavailable = thread => thread.interventionWindow === 'CLOSED'

function ValueBar({ label, value }) { return <div className="value-bar"><header><span>{label}</span><b>{value}</b></header><i><span style={{width:`${Math.min(100,value)}%`}}/></i></div> }
function SeasonTimeline({ time, complete }) { const seasons=['春','夏','秋','冬']; const perSeason=time.actions_per_season || 4; const current=Math.min(3,Math.floor(Math.min(time.total_actions,time.chapter_limit-1)/perSeason)); return <div className="season-timeline">{seasons.map((season,i)=><div key={i} className={`${time.total_actions >= (i+1)*perSeason || complete ? 'done' : ''} ${!complete && i===current ? 'current' : ''}`}><span>第一年</span><b>{season}</b><small>{Math.min(perSeason,Math.max(0,time.total_actions-i*perSeason))} / {perSeason}</small></div>)}</div> }

function EventSheet({ event, busy, eventState, onChoice, onClose }) {
  const typeIcon = event.type === '战斗' ? Sword : event.type === '命运' ? Sparkles : Compass
  const Icon = typeIcon
  const intensityLabel = {low:'低张力',medium:'中张力',high:'高张力',climax:'高潮'}
  return <div className="sheet-backdrop"><section className={`event-sheet ${event.type === '战斗' ? 'battle' : ''}`}>
    <div className="sheet-handle"/>{!event.sceneActive && !event.finale_stage && !event.chapter_finale && <button className="sheet-close" onClick={onClose}><X size={18}/></button>}
    <span className="event-type"><Icon size={15}/>{event.type}事件{event.round ? ` · 第 ${event.round} 轮` : ''}</span><h2>{event.title}</h2>
    {debugMode && event.director && <div className="director-badge"><span>事件编排 · {event.director.categoryLabel}</span><b>{event.director.intentLabel} · {intensityLabel[event.director.intensity] || event.director.intensity}</b></div>}
    {debugMode && event.actionDebug && <details className="dynamic-components"><summary>行动候选信息</summary><pre>{JSON.stringify(event.actionDebug, null, 2)}</pre></details>}
    {debugMode && event.narrativeAuthorityDebug && <details className="dynamic-components"><summary>叙事信封、AI提案与拒绝记录</summary><pre>{JSON.stringify(event.narrativeAuthorityDebug, null, 2)}</pre></details>}
    {debugMode && event.sceneDebug && <details className="dynamic-components"><summary>SceneState · 当前现场</summary><pre>{JSON.stringify(event.sceneDebug, null, 2)}</pre></details>}
    {event.boss && <div className="boss-card"><span>{event.boss.title}</span><h3>{event.boss.name}</h3><p>{event.boss.description}</p><div><b>威胁 · 致命</b><b>终章 · 第 4 幕</b></div></div>}
    <div className={`event-copy ${event.streaming ? 'is-streaming' : ''}`} aria-live="polite">{(event.paragraphs?.length ? event.paragraphs : event.text ? event.text.split('\n\n') : []).map((p,i) => <p className="stream-paragraph" key={`${i}-${p.slice(0,12)}`}>{p}</p>)}{!event.text && <div className="world-whisper"><i/><span>{event.type === '战斗' ? '敌人正在逼近。你调整呼吸，四周逐渐安静下来。' : '风从近处掠过。某种变化正在显露轮廓。'}</span></div>}</div>
    {event.type === '战斗' && <div className="battle-warning"><Sword size={17}/><span>{event.chapter_finale ? '这是第一章终章的最后一次关键检定；本次选择决定帕拉斯的结局。' : '战斗会随现场结果自然继续或结束；本次选择决定眼前局势。'}</span></div>}
    <div className={`event-choices ${eventState === 'CHOICES_AVAILABLE' ? 'available' : ''}`}>{event.choices.map((choice, index) => { const noCheck=choice.assessment?.requires_check === false || choice.requiresCheck === false; return <button style={{animationDelay:`${index * .08}s`}} disabled={busy || eventState !== 'CHOICES_AVAILABLE'} onClick={() => onChoice(index)} key={choice.text}><span>{String.fromCharCode(65+index)}</span><div className="choice-copy"><b>{choice.text}</b><small>{choice.hint}</small><div className="choice-assessment"><em className={`risk-${choice.assessment?.risk || choice.risk}`}>风险 · {choice.assessment?.risk || choice.risk}</em><em>{noCheck ? '无需检定 · 结果明确' : `${choice.assessment.attribute_label} · 成功率 ${choice.assessment.final_probability}%`}</em>{choice.lethal && <em className="risk-致命">失败后果 · 可能死亡</em>}{choice.assessment?.applied_modifiers?.map((modifier,i)=><em key={i}>{modifier.label} {modifier.value>=0?'+':''}{modifier.value}{modifier.mode==='percent'?'%':''}</em>)}</div></div><ChevronRight size={18}/></button> })}</div>
    <p className="fate-note"><LockKeyhole size={12}/>{event.sceneActive ? '每次选择都会产生具体后果；若问题尚未解决，现场将继续' : '选择后将显示这次行动造成的变化'}</p>
  </section></div>
}
