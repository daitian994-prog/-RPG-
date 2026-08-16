const request = async (path, options = {}) => {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options })
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail || '旅途暂时中断')
  return data
}

const streamNdjson = async (path, body, { signal, onMessage }) => {
  const response = await fetch(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal,
  })
  if (!response.ok || !response.body) throw new Error('前方的道路暂时被雾遮住了')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let pending = ''
  while (true) {
    const { value, done } = await reader.read()
    pending += decoder.decode(value || new Uint8Array(), { stream: !done })
    const lines = pending.split('\n')
    pending = lines.pop() || ''
    lines.filter(Boolean).forEach(line => onMessage(JSON.parse(line)))
    if (done) break
  }
  if (pending.trim()) onMessage(JSON.parse(pending))
}

export const api = {
  world: () => request('/api/world'),
  newGame: answers => request('/api/games', { method: 'POST', body: JSON.stringify({ answers }) }),
  travel: (gameId, locationId) => request('/api/travel', { method: 'POST', body: JSON.stringify({ game_id: gameId, location_id: locationId }) }),
  prepareTravel: (gameId, locationId, signal) => request('/api/travel/prepare', { method: 'POST', body: JSON.stringify({ game_id: gameId, location_id: locationId }), signal }),
  streamEvent: (gameId, eventId, options) => streamNdjson('/api/events/narrative-stream', { game_id: gameId, event_id: eventId }, options),
  choose: (gameId, eventId, choiceIndex) => request('/api/choices', { method: 'POST', body: JSON.stringify({ game_id: gameId, event_id: eventId, choice_index: choiceIndex }) }),
  recover: (gameId, method = 'rest') => request('/api/recover', { method: 'POST', body: JSON.stringify({ game_id: gameId, method }) }),
  interveneThread: (gameId, threadId, strategy) => request('/api/world-threads/intervene', { method: 'POST', body: JSON.stringify({ game_id: gameId, thread_id: threadId, strategy }) }),
  focusWorldTopic: (gameId, topicId, focused) => request('/api/world-focus', { method: 'POST', body: JSON.stringify({ game_id: gameId, topic_id: topicId, focused }) }),
  dialogue: (gameId, npcId) => request('/api/dialogue', { method: 'POST', body: JSON.stringify({ game_id: gameId, npc_id: npcId }) })
}
