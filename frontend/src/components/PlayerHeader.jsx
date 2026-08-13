import { Footprints, Leaf } from 'lucide-react'

export default function PlayerHeader({ game, location }) {
  return <header className="player-header">
    <span className="game-version">v{game.gameVersion}</span>
    <div><span className="eyebrow">无名者 · {game.player.age}岁</span><h2>{game.player.name}</h2></div>
    <div className="header-meta"><span><Leaf size={13}/>{game.season}</span><span><Footprints size={13}/>{game.action_points} 次行动</span></div>
    <div className="location-line"><i/>此刻 · {location?.name}</div>
  </header>
}
