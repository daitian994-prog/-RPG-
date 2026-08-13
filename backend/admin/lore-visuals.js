const LoreVisuals = (() => {
  const ns = 'http://www.w3.org/2000/svg';
  const knownNames = {riven:'锐雯',taliyah:'塔莉垭',swain:'斯维因',singed:'辛吉德',souma:'素马长老',kusho:'苦说大师',kai:'凯',valmar:'瓦尔茂',darha:'达尔哈',kalan:'康根',ionia:'艾欧尼亚',vastayashai_rei:'瓦斯塔亚霞瑞',vastaya:'瓦斯塔亚诸族',pallas_guardians:'帕拉斯守卫',god_willow:'神柳',noxian_invasion:'诺克萨斯远征军',ionian_resistance:'艾欧尼亚抵抗力量',dragon_spirit:'龙之灵',wuju_villagers:'无极村民与门人',ionian_factions:'艾欧尼亚诸派系',noxian_remnants:'诺克萨斯残余驻军',aion_erna:'艾恩·厄娜',noxian_reinforcements:'诺克萨斯增援部队'};
  const knownCharacters = new Set(['riven','taliyah','swain','singed','souma','kusho','kai','valmar','darha','kalan']);
  const safeUrl = value => /^\/admin\/assets\/official\/[a-zA-Z0-9_./-]+$/.test(value||'') ? value : '';
  const safeOfficial = value => /^https:\/\/(universe\.leagueoflegends\.com|map\.leagueoflegends\.com|developer\.riotgames\.com|ddragon\.leagueoflegends\.com)\//.test(value||'') ? value : '';
  const actionButtons = (record, protectedRecord=false, hasOfficial=false) => `${hasOfficial?`<button class="official-lore" data-id="${record.id}">中文官网原文</button>`:''}<button class="ghost edit-lore" data-id="${record.id}">查看 / 编辑</button>${protectedRecord?'':`<button class="danger delete-lore" data-id="${record.id}">删除</button>`}`;
  const entityName = (id,catalog) => catalog[id]?.name||knownNames[id]||id.replaceAll('_',' ');
  function associationMarkup(ids,catalog,escape) {
    const unique=[...new Set((ids||[]).filter(Boolean))];
    const groups={region:[],faction:[],character:[]};
    for(const id of unique){const category=catalog[id]?.category;if(category==='places'||category==='region')groups.region.push(id);else if(category==='factions')groups.faction.push(id);else if(category==='champions'||knownCharacters.has(id))groups.character.push(id);}
    const labels={region:'相关地区',faction:'相关派系',character:'相关角色'};
    return `<div class="association-groups">${Object.entries(groups).map(([type,items])=>`<div><b>${labels[type]}</b><span>${items.length?items.map(id=>`<i>${escape(entityName(id,catalog))}</i>`).join(''):'<em>暂无明确记录</em>'}</span></div>`).join('')}</div>`;
  }

  function wireActions(mount, records, onEdit, onDelete, onOfficial=()=>{}) {
    const index=Object.fromEntries(records.map(record=>[record.id,record]));
    mount.querySelectorAll('.edit-lore').forEach(button=>button.onclick=()=>onEdit(index[button.dataset.id]));
    mount.querySelectorAll('.delete-lore').forEach(button=>button.onclick=()=>onDelete(index[button.dataset.id]));
    mount.querySelectorAll('.official-lore').forEach(button=>button.onclick=()=>onOfficial(index[button.dataset.id]));
  }

  function renderCards({mount,category,records,escape,excerpt,meta,onEdit,onDelete,onOfficial,officialIds=new Set()}) {
    mount.className='lore-grid';
    mount.innerHTML=records.map(record=>{const tags=meta(record).filter(Boolean).slice(0,3);const image=safeUrl(record.data.image_url),source=safeOfficial(record.data.image_source_url);const protectedRecord=['metadata','region'].includes(category),hasOfficial=officialIds.has(record.id);return `<article class="lore-card media-card">${image?`<div class="lore-media" style="background-image:url('${image}')">${source?`<a href="${source}" target="_blank" rel="noreferrer">官方来源 ↗</a>`:''}<span>${escape(record.data.image_credit||'Riot Games 官方素材')}</span></div>`:''}<div class="lore-card-body"><div class="lore-card-top"><span>${escape(category)}${hasOfficial?' · 中文官网已同步':''}</span><code>${escape(record.id)}</code></div><h3>${escape(record.title)}</h3><p>${escape(excerpt(record.data))}</p><div class="lore-tags">${tags.map(item=>`<span>${escape(item)}</span>`).join('')}</div><div class="lore-card-actions"><small>更新于 ${escape(record.updated_at)}</small><div>${actionButtons(record,protectedRecord,hasOfficial)}</div></div></div></article>`}).join('');
    wireActions(mount,records,onEdit,onDelete,onOfficial);
  }

  function renderTimeline({mount,records,catalog,escape,onEdit,onDelete}) {
    mount.className='timeline-shell';
    mount.innerHTML=`<div class="visual-heading"><div><span>CHRONICLE</span><h3>艾欧尼亚历史时间轴</h3></div><p>点击节点展开背景、经过、结果与历史影响</p></div><div class="timeline-track">${records.map((record,index)=>{const d=record.data,image=safeUrl(d.image_url),links=[...(d.entities||[]),...(d.related_regions||[]),...(d.related_factions||[]),...(d.related_characters||[])],sections=[['事件背景',d.background],['详细经过',d.process],['直接结果',d.outcome],['历史影响',d.historical_impact]],participants=(d.participants||[]);return `<article class="timeline-event ${index%2?'right':'left'}"><button class="timeline-node" aria-label="展开 ${escape(record.title)}"></button><div class="timeline-card">${image?`<div class="timeline-image" style="background-image:url('${image}')"></div>`:''}<div class="timeline-copy"><div class="timeline-era"><b>${escape(d.era||'年代未知')}</b><span>#${escape(d.order||index+1)}</span></div><h3>${escape(record.title)}</h3><p>${escape(d.summary||'')}</p><small>${escape(d.precision||'')}</small>${associationMarkup(links,catalog,escape)}<button class="timeline-expand" type="button">查看完整事件资料</button><div class="timeline-details">${sections.filter(item=>item[1]).map(([title,text])=>`<section><b>${title}</b><p>${escape(text)}</p></section>`).join('')}${participants.length?`<section><b>参与者与立场</b><ul>${participants.map(item=>`<li><strong>${escape(entityName(item.id,catalog))}</strong><span>${escape(item.role)}</span></li>`).join('')}</ul></section>`:''}${d.uncertainty?`<section class="timeline-uncertainty"><b>时间与资料说明</b><p>${escape(d.uncertainty)}</p></section>`:''}</div><div class="timeline-actions">${actionButtons(record)}</div></div></div></article>`}).join('')}</div>`;
    mount.querySelectorAll('.timeline-node,.timeline-expand').forEach(node=>node.onclick=()=>{const event=node.closest('.timeline-event');event.classList.toggle('expanded');const button=event.querySelector('.timeline-expand');if(button)button.textContent=event.classList.contains('expanded')?'收起完整资料':'查看完整事件资料';});
    wireActions(mount,records,onEdit,onDelete);
  }

  function renderPlaces({mount,records,catalog,escape,onEdit,onDelete}) {
    const official=records.filter(record=>record.data.map_position?.mode==='point'&&Number.isFinite(record.data.map_position.x)&&Number.isFinite(record.data.map_position.y));
    const estimated=records.filter(record=>record.data.map_position?.mode?.startsWith('estimated_')&&Number.isFinite(record.data.map_position.x)&&Number.isFinite(record.data.map_position.y));
    const mapped=[...official,...estimated],unlocated=records.filter(record=>!mapped.includes(record));
    mount.className='place-visual';
    mount.innerHTML=`<div class="visual-heading"><div><span>OFFICIAL + INFERRED MAP</span><h3>艾欧尼亚地点地图</h3></div><p>底图与全部标点统一使用 Riot 2048 × 2048 原生坐标；金色为官方锚点，青色虚线为故事关系推定范围</p></div><div class="map-layout"><div class="map-stage"><svg class="map-world" viewBox="1180 480 760 700" preserveAspectRatio="xMidYMid slice" role="img" aria-label="官方锚点与剧情推定地点组成的艾欧尼亚地图"><image href="/admin/assets/official/ionia/runeterra-terrain.jpg" x="0" y="0" width="2048" height="2048"></image>${mapped.map(record=>{const p=record.data.map_position,isEstimate=p.mode.startsWith('estimated_');return `<g class="map-pin ${isEstimate?'estimated':'official'} confidence-${p.confidence||'official'}" transform="translate(${p.x} ${p.y})" data-id="${record.id}" role="button" tabindex="0" aria-label="${escape(record.title)}${isEstimate?`，推定位置，可信度${escape(p.confidence_label||'未知')}`:'，Riot 官方锚点'}">${isEstimate?`<circle class="estimate-range" r="${p.radius||40}"></circle>`:''}<circle class="anchor" r="${isEstimate?7:9}"></circle><text y="28">${escape(record.title)}</text></g>`}).join('')}</svg>${unlocated.length?`<div class="map-unlocated"><b>尚无法合理推定 · ${unlocated.length}</b><div>${unlocated.map(record=>`<button data-id="${record.id}">${escape(record.title)}</button>`).join('')}</div></div>`:''}<div class="map-coordinate-legend"><span><i></i>Riot 官方锚点 · ${official.length}</span><span><i></i>剧情推定范围 · ${estimated.length}</span></div><a class="map-source" href="https://map.leagueoflegends.com/" target="_blank" rel="noreferrer">Riot 官方地图 ↗</a></div><aside class="map-detail"></aside></div><div class="map-place-strip">${records.map(record=>`<button data-id="${record.id}">${escape(record.title)}</button>`).join('')}</div>`;
    const detail=mount.querySelector('.map-detail');
    const show=id=>{const record=records.find(item=>item.id===id)||records[0];if(!record)return;mount.querySelectorAll('[data-id]').forEach(el=>el.classList.toggle('active',el.dataset.id===record.id));const image=safeUrl(record.data.image_url),position=record.data.map_position||{},related=[record.id,...(record.data.related_regions||[]),...(record.data.related_factions||[]),...(record.data.champions||[])];detail.innerHTML=`${image?`<div class="map-detail-image" style="background-image:url('${image}')"></div>`:''}<span>${escape(record.data.type||'地点')}</span><h3>${escape(record.title)}</h3><p>${escape(record.data.summary||'')}</p><small>${escape(position.precision||'')}</small>${position.basis?`<div class="estimate-evidence"><b>推定依据</b><p>${escape(position.basis)}</p></div>`:''}${associationMarkup(related,catalog,escape)}<div class="map-detail-actions">${actionButtons(record)}</div>`;wireActions(detail,records,onEdit,onDelete);};
    mount.querySelectorAll('.map-pin,.map-place-strip button,.map-unlocated button').forEach(button=>{button.onclick=()=>show(button.dataset.id);button.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();show(button.dataset.id);}};});show(records[0]?.id);
  }

  function graphLayout(records) {
    const ids=[...new Set(records.flatMap(r=>[r.data.source,r.data.target]))];
    const nodes=ids.map((id,index)=>({id,x:550+Math.cos(index/ids.length*Math.PI*2)*250,y:320+Math.sin(index/ids.length*Math.PI*2)*230,vx:0,vy:0}));
    const index=Object.fromEntries(nodes.map(node=>[node.id,node]));
    for(let step=0;step<180;step++){
      for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){const a=nodes[i],b=nodes[j],dx=a.x-b.x,dy=a.y-b.y,d2=Math.max(dx*dx+dy*dy,80),f=900/d2;a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f;}
      for(const record of records){const a=index[record.data.source],b=index[record.data.target],dx=b.x-a.x,dy=b.y-a.y,d=Math.max(Math.hypot(dx,dy),1),f=(d-175)*.0025;a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f;}
      for(const node of nodes){node.vx+=(550-node.x)*.0008;node.vy+=(320-node.y)*.0008;node.vx*=.82;node.vy*=.82;node.x=Math.max(55,Math.min(1045,node.x+node.vx));node.y=Math.max(45,Math.min(595,node.y+node.vy));}
    }
    return {nodes,index};
  }

  function renderRelationships({mount,records,catalog,escape,onEdit,onDelete}) {
    mount.className='relationship-visual';const {nodes,index}=graphLayout(records);const name=id=>catalog[id]?.name||knownNames[id]||id.replaceAll('_',' ');const degree=id=>records.filter(r=>r.data.source===id||r.data.target===id).length;
    const edges=records.map(record=>{const a=index[record.data.source],b=index[record.data.target];return `<line data-edge="${record.id}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" style="stroke-width:${1+(record.data.strength||2)*.55}"><title>${escape(name(record.data.source))} → ${escape(name(record.data.target))} · ${escape(record.data.type)}</title></line>`}).join('');
    const nodeMarkup=nodes.map(node=>{const image=safeUrl(catalog[node.id]?.image_url);return `<g class="graph-node" data-node="${node.id}" transform="translate(${node.x} ${node.y})"><circle r="${22+Math.min(degree(node.id),5)*2}"></circle>${image?`<clipPath id="clip-${node.id}"><circle r="19"></circle></clipPath><image href="${image}" x="-19" y="-19" width="38" height="38" preserveAspectRatio="xMidYMid slice" clip-path="url(#clip-${node.id})"></image>`:''}<text y="39">${escape(name(node.id))}</text></g>`}).join('');
    mount.innerHTML=`<div class="visual-heading"><div><span>RELATIONSHIP GRAPH</span><h3>人物与势力关系网络</h3></div><p>${nodes.length} 个节点 · ${records.length} 条关系 · 节点大小代表连接数量</p></div><div class="graph-layout"><div class="graph-canvas"><svg viewBox="0 0 1100 640" role="img" aria-label="艾欧尼亚人物关系网"><g class="graph-edges">${edges}</g><g>${nodeMarkup}</g></svg><div class="graph-legend"><span><i></i>关系强度</span><span>点击节点查看关联</span></div></div><aside class="graph-detail"></aside></div>`;
    const detail=mount.querySelector('.graph-detail');
    const show=id=>{mount.querySelectorAll('.graph-node').forEach(node=>node.classList.toggle('active',node.dataset.node===id));const related=records.filter(record=>record.data.source===id||record.data.target===id);detail.innerHTML=`<span>关系节点</span><h3>${escape(name(id))}</h3><p>${related.length} 条直接关系</p><div class="relation-list">${related.map(record=>{const other=record.data.source===id?record.data.target:record.data.source;return `<article><b>${escape(name(other))}</b><span>${escape(record.data.type)}</span><p>${escape(record.data.summary||'')}</p><div>${actionButtons(record)}</div></article>`}).join('')}</div>`;wireActions(detail,records,onEdit,onDelete);};
    mount.querySelectorAll('.graph-node').forEach(node=>node.onclick=()=>show(node.dataset.node));show(nodes.sort((a,b)=>degree(b.id)-degree(a.id))[0]?.id);
  }

  function render(options) {
    options.mount.innerHTML='';
    if(!options.records.length){options.mount.className='lore-grid';return;}
    if(options.category==='timeline')return renderTimeline(options);
    if(options.category==='places')return renderPlaces(options);
    if(options.category==='relationships')return renderRelationships(options);
    return renderCards(options);
  }
  return {render};
})();
