import { useState } from 'react'
import { ChevronDown, ChevronUp, Compass, Footprints, Leaf, MapPin, Sparkles, Sword } from 'lucide-react'
import pallasImage from '../assets/locations/pallas.png'
import windbreakImage from '../assets/locations/windbreak-forest.png'
import warRuinsImage from '../assets/locations/war-ruins.png'
import templeImage from '../assets/locations/mountain-temple.png'
import './LocationSelectionPage.css'

const locationImages = { pallas: pallasImage, windbreak: windbreakImage, war_ruins: warRuinsImage, mountain_temple: templeImage }
const locationIcons = { village: Leaf, forest: Compass, ruins: Sword, temple: Sparkles }
const riskClass = { 低: 'low', 中: 'medium', 高: 'high', 致命: 'deadly' }

export default function LocationSelectionPage({ locations, journal, current, points, time, chapterComplete, bodyCondition, busy, onTravel, onRecover }) {
  const remaining = Math.max(0, time.chapter_limit - time.total_actions)
  const inFinale = !chapterComplete && time.total_actions >= 12
  const finaleNext = {12:['mountain_temple','终章一 · 前往山寺平息灵界异象'],13:['war_ruins','终章二 · 赴战争遗迹与亚索会合'],14:['pallas','终章三 · 返回帕拉斯布置防线'],15:['pallas','终章四 · 迎战血旗督军']}[time.total_actions]
  const leadsFor = locationId => journal.filter(item => item.trackable && item.status === 'active' && item.relatedLocations?.includes(locationId))
  return <div className="location-selection-page">
    <header className="location-selection-heading"><div><span>周边行程</span><h3>{inFinale ? '第一章终章' : '选择你为什么前往'}</h3><p>地点有稳定倾向，具体现场仍会动态发生</p></div><aside><b>{points}</b><span>次行动</span></aside><div className="journey-progress"><i><span style={{width:`${Math.min(100,time.total_actions / time.chapter_limit * 100)}%`}}/></i><em>{chapterComplete ? '第一章已经结束' : `一年之期 · 还剩 ${remaining} 次行动`}</em></div></header>
    {inFinale && finaleNext ? <section className="finale-next"><span>固定终章 · {time.total_actions - 11} / 4</span><b>{finaleNext[1]}</b><p>终章已经开始，自由行程暂时关闭。完成这一幕后才会进入下一段收尾。</p><button disabled={busy} onClick={()=>onTravel(finaleNext[0])}>继续终章</button></section> : <div className="location-card-list">{locations.map(location => <LocationCard key={location.id} location={location} leads={leadsFor(location.id)} current={location.id === current} disabled={busy || chapterComplete} onTravel={onTravel}/>)}</div>}
    {!inFinale && current === 'pallas' && <section className="location-recovery"><div><span>安全地点 · 稳定恢复</span><b>在帕拉斯休息</b><p>解除疲惫和紧张，使伤势改善一级。消耗 1 次行动。</p></div><button disabled={busy || points <= 0 || bodyCondition?.state === 'healthy'} onClick={onRecover}>休息 / 治疗</button></section>}
  </div>
}

function LocationCard({ location, leads, current, disabled, onTravel }) {
  const [expanded, setExpanded] = useState(false)
  const primaryLead = leads[0]
  const extraLeads = leads.slice(1)
  const enter = () => !disabled && onTravel(location.id, primaryLead?.id || null)
  return <article className={`location-choice-card ${current?'is-current':''} ${primaryLead?.isNew?'has-new-lead':''}`}>
    <button className="location-card-main" disabled={disabled} onClick={enter} aria-label={`${primaryLead?'追踪 '+primaryLead.title+'，前往':'自由探索'}${location.name}`}>
      <LocationVisualHeader location={location} current={current}/>
      <LocationInfoBody location={location}/>
    </button>
    <LocationLeadPanel location={location} leads={leads} expanded={expanded} onExpand={()=>setExpanded(value=>!value)} disabled={disabled} onTrack={leadId=>onTravel(location.id,leadId)}/>
    <LocationActionFooter location={location} current={current} hasLead={Boolean(primaryLead)} disabled={disabled} onPrimary={enter} onFreeExplore={()=>onTravel(location.id,null)}/>
  </article>
}

function LocationVisualHeader({ location, current }) {
  const Icon = locationIcons[location.icon] || MapPin
  return <div className="location-visual-header"><img src={locationImages[location.imageKey || location.id]} alt=""/><div className="location-visual-shade"/><span className="location-emblem"><Icon size={19}/></span><RiskBadge risk={location.risk}/>{current && <em className="current-location"><MapPin size={12}/>当前位置</em>}<div className="location-visual-title"><small>{location.subtitle}</small><h4>{location.name}</h4></div></div>
}

function LocationInfoBody({ location }) { return <div className="location-info-body"><LocationTagList tags={location.subtitleTags || location.playstyle?.split(' · ') || []}/><p>{location.expectation || location.description}</p><span>更可能获得</span><b>{(location.rewards || location.feedbackTypes || []).join(' / ')}</b></div> }

function LocationLeadPanel({ location, leads, expanded, onExpand, disabled, onTrack }) {
  if (!leads.length) return <div className="location-no-lead">目前没有明确线索，你仍然可以自由探索。</div>
  const visible = expanded ? leads : leads.slice(0,1)
  return <section className="location-lead-panel"><header><Footprints size={14}/><span>当前可追踪事项</span></header>{visible.map(lead=><button key={lead.id} disabled={disabled} onClick={()=>onTrack(lead.id)}><em>{lead.isNew?'NEW · 当前可追踪':'继续追踪'}</em><b>{lead.title}</b><p>{lead.summary}</p></button>)}{leads.length > 1 && <button className="expand-leads" disabled={disabled} onClick={onExpand}>{expanded?<><ChevronUp size={13}/>收起其他线索</>:<><ChevronDown size={13}/>还有 {leads.length-1} 条可追踪事项 · 展开更多</>}</button>}</section>
}

function LocationActionFooter({ location, current, hasLead, disabled, onPrimary, onFreeExplore }) { return <footer className="location-action-footer"><button className="primary-location-action" disabled={disabled} onClick={onPrimary}>{hasLead?'沿当前线索前往':'自由探索'} · 1 次行动</button>{hasLead && <button className="secondary-location-action" disabled={disabled} onClick={onFreeExplore}>不追线索，自由探索</button>}{current && <span>你现在就在{location.name}</span>}</footer> }
function RiskBadge({ risk }) { return <span className={`risk-badge ${riskClass[risk] || 'medium'}`}>风险 · {risk}</span> }
function LocationTagList({ tags }) { return <div className="location-tag-list">{tags.map(tag=><span key={tag}>{tag}</span>)}</div> }
