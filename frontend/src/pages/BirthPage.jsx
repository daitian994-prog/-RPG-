import { MapPin, Sparkles } from 'lucide-react'
import InkButton from '../components/InkButton'

export default function BirthPage({ game, onContinue }) {
  const p = game.player
  return <main className="birth-page page-enter">
    <div className="birth-art"><div className="sun-disc"/><div className="ink-tree"/></div>
    <section>
      <p className="kicker">你的故事，由此开始</p>
      <h1>{p.name}</h1>
      <div className="birth-meta"><span>{p.age} 岁</span><span><MapPin size={13}/>{p.birthplace}</span></div>
      <div className="story-scroll"><Sparkles size={18}/><p>{p.story}</p></div>
      <div className="tag-row">{p.tags.map(t => <span key={t}>· {t} ·</span>)}</div>
      <InkButton onClick={onContinue}>踏入世界 <span>→</span></InkButton>
    </section>
  </main>
}
