import { Backpack, Map, ScrollText, Users } from 'lucide-react'

const tabs = [
  ['story', ScrollText, '旅记'], ['map', Map, '地图'], ['people', Users, '人物'], ['status', Backpack, '行囊']
]

export default function BottomNav({ active, onChange }) {
  return <nav className="bottom-nav">{tabs.map(([id, Icon, label]) => <button key={id} onClick={() => onChange(id)} className={active === id ? 'active' : ''}><Icon size={20}/><span>{label}</span></button>)}</nav>
}

