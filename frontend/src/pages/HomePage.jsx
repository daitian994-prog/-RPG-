import { Feather, Volume2 } from 'lucide-react'
import InkButton from '../components/InkButton'

export default function HomePage({ onStart }) {
  return <main className="home-page page-enter">
    <div className="mountains m1"/><div className="mountains m2"/><div className="sun-disc"/>
    <button className="sound-button" aria-label="声音"><Volume2 size={18}/></button>
    <section className="hero-copy">
      <span className="seal"><Feather size={19}/></span>
      <p className="kicker">RUNETERRA · THE NAMELESS</p>
      <h1>无名者<span>符文之地</span></h1>
      <div className="brush-line"/>
      <p className="intro">在英雄存在的时代，<br/>你将寻找属于自己的道路。</p>
      <InkButton onClick={onStart}>开始人生 <span>→</span></InkButton>
      <p className="whisper">你的名字，尚未写入任何传说</p>
    </section>
  </main>
}

