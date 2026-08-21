import { Compass, MapPin, Scroll } from 'lucide-react'

export default function OpeningPage({ opening, journal, busy, onContinue }) {
  const lead = journal.find(item => item.trackable)
  return <main className="opening-page page-enter">
    <div className="opening-art"><div className="opening-lantern"/><span>帕拉斯 · 初夜</span></div>
    <section>
      <p className="kicker">你先听见了什么</p>
      <h1>{opening?.title || '风带来的消息'}</h1>
      <p className="opening-intro">{opening?.intro}</p>
      <div className="opening-signals">{opening?.signals?.map((signal, index) => <article key={signal}><span>0{index + 1}</span><p>{signal}</p></article>)}</div>
      <p className="opening-closing">{opening?.closing}</p>
      {lead && <div className="opening-lead"><Scroll size={18}/><div><small>现在值得继续留意</small><b>{lead.title}</b><p>{lead.summary}</p><em><MapPin size={12}/>{lead.relatedLocations?.includes('windbreak') ? '断风森林' : '相关地点'}</em></div></div>}
      <button className="ink-button" disabled={busy} onClick={onContinue}><Compass size={17}/>{busy ? '正在展开地图…' : '带着这些消息打开地图'}</button>
    </section>
  </main>
}
