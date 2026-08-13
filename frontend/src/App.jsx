import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import BirthPage from './pages/BirthPage'
import GamePage from './pages/GamePage'
import HomePage from './pages/HomePage'
import PersonalityPage from './pages/PersonalityPage'

export default function App() {
  const [screen, setScreen] = useState('home')
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState([])
  const [game, setGame] = useState(null)
  const [world, setWorld] = useState(null)
  const [event, setEvent] = useState(null)
  const [result, setResult] = useState('')
  const [tab, setTab] = useState('story')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [eventState, setEventState] = useState('IDLE')
  const [transition, setTransition] = useState(null)
  const requestRef = useRef({ id: 0, controller: null })

  useEffect(() => () => requestRef.current.controller?.abort(), [])

  useEffect(() => { api.world().then(setWorld).catch(e => setError(e.message)) }, [])

  const answer = async value => {
    const next = [...answers, value]
    setAnswers(next)
    if (step < 5) return setStep(step + 1)
    setBusy(true)
    try { const data = await api.newGame(next); setGame(data.game); setScreen('birth') }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const travel = async locationId => {
    if (eventState !== 'IDLE' && eventState !== 'COMPLETE' && eventState !== 'CHOICES_AVAILABLE') return
    requestRef.current.controller?.abort()
    const controller = new AbortController()
    const requestId = requestRef.current.id + 1
    requestRef.current = { id: requestId, controller }
    const destination = world.locations.find(location => location.id === locationId)
    const scene = transitionFor(destination)
    setBusy(true); setResult(''); setError(''); setEvent(null)
    setEventState('PLAYER_ACTION'); setTransition(scene)
    requestAnimationFrame(() => setEventState('TRANSITION'))
    try {
      const data = await api.prepareTravel(game.id, locationId, controller.signal)
      if (requestRef.current.id !== requestId) return
      const skeleton = { ...data.event, text: '', paragraphs: [], streaming: true }
      setGame(data.game); setEvent(skeleton); setTransition(null); setTab('story'); setEventState('STREAMING'); setBusy(false)
      await api.streamEvent(game.id, data.event.id, {
        signal: controller.signal,
        onMessage: message => {
          if (requestRef.current.id !== requestId) return
          if (message.type === 'paragraph') {
            setEvent(current => current ? { ...current, paragraphs: [...(current.paragraphs || []), message.text], text: [...(current.paragraphs || []), message.text].join('\n\n') } : current)
            setEventState(data.event.lockChoicesUntilComplete ? 'STREAMING' : 'CHOICES_AVAILABLE')
          }
          if (message.type === 'complete') {
            setEvent(current => current ? { ...current, text: message.text, streaming: false } : current)
            setEventState('CHOICES_AVAILABLE')
          }
          if (message.type === 'error') throw new Error(message.message)
        },
      })
    } catch (e) {
      if (e.name === 'AbortError' || requestRef.current.id !== requestId) return
      console.error('Travel stream failed', e)
      setError('你停下脚步，周围暂时没有新的发现。')
      setEventState('COMPLETE')
    } finally {
      if (requestRef.current.id === requestId) { setBusy(false); setTransition(null) }
    }
  }

  const choose = async index => {
    if (busy) return
    requestRef.current.controller?.abort()
    requestRef.current = { id: requestRef.current.id + 1, controller: null }
    setBusy(true)
    try { setEventState('EVENT_RESOLVE'); const data = await api.choose(game.id, event.id, index); setGame(data.game); setResult(data.resolution); setEvent(null); setTab('story'); setEventState('COMPLETE') }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const dialogue = async npcId => {
    if (busy) return
    setBusy(true)
    try { const data = await api.dialogue(game.id, npcId); setGame(data.game); setResult(data.message); setTab('story') }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const recover = async () => {
    if (busy) return
    setBusy(true); setError('')
    try { const data = await api.recover(game.id); setGame(data.game); setResult(data.message); setTab('story') }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return <div className="app-shell">
    {screen === 'home' && <HomePage onStart={() => setScreen('questions')}/>} 
    {screen === 'questions' && <PersonalityPage step={step} onAnswer={answer} onBack={() => step ? setStep(step-1) : setScreen('home')}/>} 
    {screen === 'birth' && game && <BirthPage game={game} onContinue={() => setScreen('game')}/>} 
    {screen === 'game' && game && world && <GamePage game={game} world={world} event={event} result={result} tab={tab} busy={busy} eventState={eventState} onTab={setTab} onTravel={travel} onRecover={recover} onChoice={choose} onDialogue={dialogue} onCloseEvent={() => { requestRef.current.controller?.abort(); setEvent(null); setBusy(false); setEventState('IDLE') }}/>} 
    {transition && <WorldTransition scene={transition}/>} 
    {error && <button className="error-toast" onClick={() => setError('')}>{error}<span>×</span></button>}
  </div>
}

const transitionFor = location => {
  const scenes = {
    windbreak: ['深入断风森林……', '风吹过层叠树冠。', '远处似乎传来脚步声。'],
    war_ruins: ['调查战争遗迹……', '灰尘从残破石柱落下。', '附近残留着微弱的魔法痕迹。'],
    mountain_temple: ['沿石阶向山寺前行……', '云气漫过檐角。', '暮钟的余韵停在山谷里。'],
    pallas: ['返回帕拉斯……', '道路逐渐变得热闹。', '远处已经能看见村中的灯火。'],
  }
  return { title: location?.name || '前方', lines: scenes[location?.id] || ['你离开主路，向前方走去。', '四周逐渐安静下来。', '你察觉到了什么。'] }
}

function WorldTransition({ scene }) {
  return <div className="world-transition" role="status" aria-live="polite"><div className="transition-rings"/><p>{scene.title}</p>{scene.lines.map((line, index) => <span key={line} style={{ animationDelay: `${index * .65}s` }}>{line}</span>)}</div>
}
