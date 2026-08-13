import { ArrowLeft, Feather } from 'lucide-react'
import { questions } from '../data/questions'

export default function PersonalityPage({ step, onAnswer, onBack }) {
  const q = questions[step]
  return <main className="question-page page-enter">
    <header><button onClick={onBack}><ArrowLeft size={19}/></button><div><span>倾听内心</span><b>{String(step + 1).padStart(2,'0')} / 06</b></div></header>
    <div className="progress"><i style={{width:`${(step + 1) / 6 * 100}%`}}/></div>
    <section className="question-card">
      <div className="chapter-mark"><Feather size={17}/><span>第 {['一','二','三','四','五','六'][step]} 问</span></div>
      <h2>{q.scene}</h2>
      <div className="answer-list">{q.options.map((option, i) => <button key={option.text} onClick={() => onAnswer(option.value)}><span>{String.fromCharCode(65+i)}</span><p>{option.text}</p><i>›</i></button>)}</div>
    </section>
    <p className="question-foot">没有正确的答案，只有你愿意承担的选择</p>
  </main>
}

