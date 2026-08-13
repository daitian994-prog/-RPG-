import { ChevronRight, CircleUserRound, Compass, Leaf, LockKeyhole, MapPin, Scroll, Shield, Sparkles, Sword, X } from 'lucide-react'
import BottomNav from '../components/BottomNav'
import PlayerHeader from '../components/PlayerHeader'

const icons = { village: Leaf, forest: Compass, ruins: Sword, temple: Sparkles }
const coreAttributeNames = {martial:'武艺',physique:'体魄',perception:'灵觉',willpower:'心志',agility:'机敏',social:'交涉'}
const personalityNames = {peace:'和平倾向',power:'力量观',freedom:'自由倾向',spirit:'灵性亲和',destiny:'命运态度'}
const fateNames = {guardian:'守护命运',strong:'强者命运',wanderer:'流浪命运',spirit:'灵界命运',breaker:'破局命运'}

export default function GamePage({ game, world, event, result, tab, busy, eventState, onTab, onTravel, onRecover, onChoice, onDialogue, onCloseEvent }) {
  const location = world.locations.find(x => x.id === game.location)
  const localNpcs = world.npcs.filter(n => n.location === game.location || n.id === 'companion')
  return <main className="game-page page-enter">
    <PlayerHeader game={game} location={location}/>
    <section className="game-content">
      {tab === 'story' && <Story game={game} location={location} result={result} npcs={world.npcs} onMap={() => onTab('map')}/>} 
      {tab === 'map' && <WorldMap locations={world.locations} current={game.location} points={game.action_points} time={game.time} chapterComplete={game.chapter_complete} bodyCondition={game.player.bodyCondition} busy={busy} onTravel={onTravel} onRecover={onRecover}/>} 
      {tab === 'people' && <People npcs={localNpcs} relationships={game.relationships} onDialogue={onDialogue}/>} 
      {tab === 'status' && <Status player={game.player} game={game}/>} 
    </section>
    <BottomNav active={tab} onChange={onTab}/>
    {event && <EventSheet event={event} busy={busy} eventState={eventState} onChoice={onChoice} onClose={onCloseEvent}/>} 
  </main>
}

function Story({ game, location, result, npcs, onMap }) {
  const resolution = result && typeof result === 'object' ? result : game.last_resolution
  const latest = resolution?.narrative || result || game.log.at(-1)
  return <div className="story-view">
    <div className="scene-art"><div className="scene-moon"/><div className="scene-ridge"/><span>{location.subtitle}</span></div>
    <div className="chapter-title"><span>{game.chapter_complete ? '第一章 · 完' : `第一章 · ${game.time.total_actions} / ${game.time.chapter_limit}`}</span><h3>{game.chapter_complete ? '血旗落下之后' : '风从帕拉斯吹来'}</h3></div>
    <article><Scroll size={18}/><div className="narrative-copy">{String(latest).split('\n\n').map((p,i) => <p key={i}>{p}</p>)}</div></article>
    {resolution && <ResolutionPanel resolution={resolution} npcs={npcs}/>} 
    {game.chapter_complete ? <div className="milestone chapter-end"><Shield size={18}/><div><b>第一章完成 · 一年之约</b><span>帕拉斯的入侵已经结束，你的名字留在了村庄记忆里。</span></div></div> : game.battle_complete && <div className="milestone"><Shield size={18}/><div><b>旅途印记 · 初战</b><span>你已经历一次真正的战斗。故事仍在继续。</span></div></div>}
    <button className="next-action" onClick={onMap}><span><Compass size={19}/>选择下一次行动</span><ChevronRight/></button>
  </div>
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
    <div className="resolution-title"><Sparkles size={16}/><div><b>{resolution.battle?.is_boss ? '第一章终局结算' : resolution.outcome ? `${resolution.outcome.label} · 事件结算` : '事件结算'}</b><span>收益与代价均已写入人物档案</span></div>{resolution.battle && <em className={resolution.battle.victory ? 'win' : 'lose'}>{resolution.battle.is_boss ? (resolution.battle.victory ? 'BOSS 击破' : 'BOSS 战败') : (resolution.battle.victory ? '战斗胜利' : '负伤脱身')}</em>}</div>
    {resolution.outcome && <div className={`outcome-check ${resolution.outcome.code}`}><div><span>{resolution.outcome.check}</span><b>{resolution.outcome.label}</b></div><p>判定值 {resolution.outcome.roll} · 成功线 {resolution.outcome.final_probability}%</p><small>{resolution.outcome.code === 'failure' ? '未达成原目标，但故事会进入新的困难局面' : resolution.outcome.code === 'partial' ? '完成目标，但必须支付代价' : '检定通过，获得对应收益'}</small><details><summary>判定调试信息</summary><code>基础 {resolution.outcome.base_probability}% · 最终 {resolution.outcome.final_probability}% · Roll {resolution.outcome.roll} · Tier {resolution.outcome.tier} · Seed {resolution.outcome.seed}</code>{resolution.outcome.applied_modifiers.map((modifier,index)=><em key={index}>{modifier.label} {modifier.value>=0?'+':''}{modifier.value}{modifier.mode==='percent'?'%':''}</em>)}</details></div>}
    {groups.map(([title, values, labels]) => <div className="change-group" key={title}><h5>{title}</h5><div>{Object.entries(values).map(([key, value]) => <span className={value >= 0 ? 'up' : 'down'} key={key}>{labels[key] || key}<b>{value >= 0 ? '+' : ''}{value}</b></span>)}</div></div>)}
    {Object.keys(positiveOnly(changes.relations)).length > 0 && <div className="change-group"><h5>人物关系收益</h5><div>{Object.entries(positiveOnly(changes.relations)).map(([id,value]) => <span className="up" key={id}>{npcs.find(n=>n.id===id)?.name || id}<b>+{value}</b></span>)}</div></div>}
    {costGroups.length > 0 && <div className="cost-block"><header>本次代价</header>{costGroups.map(([title, values, labels]) => <div className="change-group" key={title}><h5>{title}</h5><div>{Object.entries(values).map(([key,value]) => <span className="down" key={key}>{labels[key] || key}<b>{value}</b></span>)}</div></div>)}{Object.keys(costs.relations || {}).length > 0 && <div className="change-group"><h5>人物关系损失</h5><div>{Object.entries(costs.relations).map(([id,value]) => <span className="down" key={id}>{npcs.find(n=>n.id===id)?.name || id}<b>{value}</b></span>)}</div></div>}</div>}
    {resolution.items?.map(item => <div className="loot-card" key={item.name}><div><span>获得物品 · {item.rarity}</span><b>{item.name}</b><p>{item.description}</p></div>{item.effects?.length > 0 && <ul>{item.effects.map(effect => <li key={effect}>{effect}</li>)}</ul>}</div>)}
    {resolution.missed_items?.length > 0 && <div className="missed-loot"><span>未能获得</span><b>{resolution.missed_items.join('、')}</b><p>这件物品随失败的机会一同离开，未来或许还有其他取得方式。</p></div>}
  </section>
}

function WorldMap({ locations, current, points, time, chapterComplete, bodyCondition, busy, onTravel, onRecover }) {
  const remaining = Math.max(0, time.chapter_limit - time.total_actions)
  const mapped = locations.filter(loc => loc.map_position?.mode === 'point')
  return <div className="map-view">
    <div className="section-heading"><p>艾欧尼亚 · 东部</p><h3>选择去处</h3><span>{points} 次行动可用{points === 0 ? ' · 下一次行动进入新季节' : ''}</span><div className="chapter-countdown"><i><span style={{width:`${Math.min(100,time.total_actions / time.chapter_limit * 100)}%`}}/></i><b>{chapterComplete ? '第一章已经结束' : `一年之期 · 还剩 ${remaining} 次行动`}</b></div></div>
    <div className="map-canvas">
      <svg className="official-game-map" viewBox="1180 480 760 700" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Riot 官方地图上的帕拉斯位置">
        <image href="/admin/assets/official/ionia/runeterra-terrain.jpg" x="0" y="0" width="2048" height="2048"/>
        {mapped.map(loc => { const p=loc.map_position; const active=loc.id===current; return <g key={loc.id} className={`official-map-pin ${active?'current':''}`} transform={`translate(${p.x} ${p.y})`} role="button" tabIndex="0" aria-label={`${loc.name}${active?'，你在这里':'，前往'}`} onClick={() => !busy && onTravel(loc.id)} onKeyDown={event => { if(!busy && (event.key==='Enter'||event.key===' ')){event.preventDefault();onTravel(loc.id)} }}><circle r="10"/><text y="29">{loc.name}</text><text className="pin-status" y="48">{active?'你在这里':'前往 · 1'}</text></g> })}
      </svg>
      <div className="map-wash wash-a"/><div className="map-wash wash-b"/>
    </div>
    <p className="map-note"><MapPin size={14}/>帕拉斯采用 Riot 官方互动地图精确锚点</p>
    {current === 'pallas' && <section className="recovery-card"><div><span>安全地点 · 稳定恢复</span><b>在帕拉斯休息</b><p>解除疲惫和紧张，使伤势改善一级。消耗 1 次行动，时间成本 1。</p></div><button disabled={busy || points <= 0 || bodyCondition?.state === 'healthy'} onClick={onRecover}>休息 / 治疗</button></section>}
    <section className="travel-list"><header><div><span>周边行程</span><b>章节探索地点</b></div><small>以下地点没有官方精确坐标，不在地图上制造伪标点</small></header>{locations.map(loc => { const Icon=icons[loc.icon]; const active=loc.id===current; return <button disabled={busy||active} key={loc.id} onClick={() => onTravel(loc.id)} className={active?'current':''}><i><Icon size={17}/></i><div><b>{loc.name}</b><small>{loc.description}</small></div><em>{active?'当前位置':'前往 · 1'}</em></button> })}</section>
  </div>
}

function People({ npcs, relationships, onDialogue }) {
  return <div className="people-view"><div className="section-heading"><p>相逢并非偶然</p><h3>旅途中认识的人</h3></div><div className="npc-list">{npcs.map(npc => { const rel = relationships[npc.id]; return <button key={npc.id} onClick={() => onDialogue(npc.id)}><span className="npc-avatar"><CircleUserRound/></span><div><b>{npc.name}</b><small>{npc.job} · {npc.personality}</small><em>{rel.memories.length ? rel.memories.at(-1) : '你们尚未留下共同记忆'}</em></div><i>{rel.score > 10 ? '信任' : rel.score > 0 ? '相识' : '陌生'} · {rel.score}</i></button> })}</div></div>
}

function Status({ player, game }) {
  return <div className="status-view"><div className="section-heading"><p>普通人的传说</p><h3>{player.name}的人物档案</h3></div>
    <div className="profile-card"><span>{player.age}</span><div><b>{player.family}</b><small>{player.birthplace}</small></div></div>
    <h4>第一章时间轴 <small>一年 · 四季 · 每季3次行动</small></h4><SeasonTimeline time={game.time} complete={game.chapter_complete}/>
    <h4>角色状态</h4><section className={`body-condition ${player.bodyCondition.state}`}><header><span>身体状况</span><b>{player.bodyCondition.label}</b></header><p>{player.bodyCondition.description}</p><div>{Object.entries(player.bodyCondition.modifiers).map(([key,value])=><em key={key}>{coreAttributeNames[key]} {value}%</em>)}</div></section>
    <div className="effect-list">{player.statuses?.length ? player.statuses.map(item=><span key={item.id || item.name}>状态 · {item.name} · {item.duration ?? '条件解除'}</span>) : <small>没有临时状态</small>}{player.traits?.map(item=><span key={item.id}>特质 · {item.name} Lv.{item.level}</span>)}</div>
    <h4>核心能力 <small>决定你能不能做到</small></h4><div className="core-stat-grid">{Object.entries(player.coreAbilities || {}).map(([key,value])=><div key={key}><span>{coreAttributeNames[key]}</span><b>{value}</b></div>)}</div>
    <h4>线索</h4><div className="effect-list">{player.clues?.length ? player.clues.map(item=><span key={item.name}>{item.name}</span>) : <small>尚未掌握可用于检定的线索</small>}</div>
    <h4>人格倾向 <small>描述你倾向怎么做</small></h4><div className="value-bars">{Object.entries(player.personality).map(([key,value]) => <ValueBar key={key} label={personalityNames[key]} value={value}/>)}</div>
    <h4>命运倾向 <small>影响你更容易与哪些类型的故事发生联系</small></h4><div className="value-bars fate-bars">{Object.entries(player.fateAffinities).map(([key,value]) => <ValueBar key={key} label={fateNames[key]} value={value}/>)}</div>
    <h4>持有物 <small>在适用情境中提供帮助</small></h4><div className="inventory-cards">{player.inventory.map(item => <div key={item.name}><header><b>{item.name}</b><span>{item.rarity}</span></header><p>{item.description}</p>{item.effects?.length > 0 && <footer>{item.effects.map(effect => <em key={effect}>{effect}</em>)}</footer>}</div>)}</div>
    <h4>旅途印记</h4><div className="memory-count"><Scroll/><div><b>{player.memories.length} 段经历</b><span>去过 {game.visited.length} 个地方 · 遇见 {game.completed_events.length} 次选择</span></div></div>
  </div>
}

function ValueBar({ label, value }) { return <div className="value-bar"><header><span>{label}</span><b>{value}</b></header><i><span style={{width:`${Math.min(100,value)}%`}}/></i></div> }
function SeasonTimeline({ time, complete }) { const seasons=['春','夏','秋','冬']; const current=Math.min(3,time.season_index); return <div className="season-timeline">{seasons.map((season,i)=><div key={i} className={`${time.total_actions >= (i+1)*3 || complete ? 'done' : ''} ${!complete && i===current ? 'current' : ''}`}><span>第一年</span><b>{season}</b><small>{Math.min(3,Math.max(0,time.total_actions-i*3))} / 3</small></div>)}</div> }

function EventSheet({ event, busy, eventState, onChoice, onClose }) {
  const typeIcon = event.type === '战斗' ? Sword : event.type === '命运' ? Sparkles : Compass
  const Icon = typeIcon
  return <div className="sheet-backdrop"><section className={`event-sheet ${event.type === '战斗' ? 'battle' : ''}`}>
    <div className="sheet-handle"/><button className="sheet-close" onClick={onClose}><X size={18}/></button>
    <span className="event-type"><Icon size={15}/>{event.type}事件</span><h2>{event.title}</h2>
    {event.boss && <div className="boss-card"><span>{event.boss.title}</span><h3>{event.boss.name}</h3><p>{event.boss.description}</p><div><b>威胁 · 致命</b><b>关键检定 · 4 个节点</b></div></div>}
    <div className={`event-copy ${event.streaming ? 'is-streaming' : ''}`} aria-live="polite">{(event.paragraphs?.length ? event.paragraphs : event.text ? event.text.split('\n\n') : []).map((p,i) => <p className="stream-paragraph" key={`${i}-${p.slice(0,12)}`}>{p}</p>)}{!event.text && <div className="world-whisper"><i/><span>{event.type === '战斗' ? '敌人正在逼近。你调整呼吸，四周逐渐安静下来。' : '风从近处掠过。某种变化正在显露轮廓。'}</span></div>}</div>
    {event.type === '战斗' && <div className="battle-warning"><Sword size={17}/><span>战斗将作为 {event.chapter_finale ? '4 个' : '2 个'}关键检定节点处理；本次选择决定当前节点局势。</span></div>}
    <div className={`event-choices ${eventState === 'CHOICES_AVAILABLE' ? 'available' : ''}`}>{event.choices.map((choice, index) => <button style={{animationDelay:`${index * .08}s`}} disabled={busy || eventState !== 'CHOICES_AVAILABLE'} onClick={() => onChoice(index)} key={choice.text}><span>{String.fromCharCode(65+index)}</span><div className="choice-copy"><b>[{choice.assessment.attribute_label}] {choice.text}</b><small>{choice.hint}</small><div className="choice-assessment"><em className={`risk-${choice.assessment.risk}`}>风险 · {choice.assessment.risk}</em><em>成功率 · {choice.assessment.final_probability}%</em>{choice.lethal && <em className="risk-致命">失败后果 · 可能死亡</em>}{choice.assessment.applied_modifiers.map((modifier,i)=><em key={i}>{modifier.label} {modifier.value>=0?'+':''}{modifier.value}{modifier.mode==='percent'?'%':''}</em>)}</div></div><ChevronRight size={18}/></button>)}</div>
    <p className="fate-note"><LockKeyhole size={12}/>选择后将显示属性、命运、关系与物品的完整变化</p>
  </section></div>
}
