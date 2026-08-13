param([switch]$Force)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$assetRoot = Join-Path $projectRoot 'backend\admin\assets\official'
$championRoot = Join-Path $assetRoot 'champions'
$ioniaRoot = Join-Path $assetRoot 'ionia'
New-Item -ItemType Directory -Force -Path $championRoot, $ioniaRoot | Out-Null

function Save-OfficialAsset([string]$Url, [string]$Path) {
    if ((Test-Path -LiteralPath $Path) -and -not $Force) { return }
    Invoke-WebRequest -Uri $Url -OutFile $Path -UseBasicParsing
}

$champions = [ordered]@{
    ahri='Ahri'; akali='Akali'; hwei='Hwei'; irelia='Irelia'; ivern='Ivern'; jhin='Jhin'
    karma='Karma'; kayn='Kayn'; kennen='Kennen'; lee_sin='LeeSin'; lillia='Lillia'
    master_yi='MasterYi'; rakan='Rakan'; sett='Sett'; shen='Shen'; syndra='Syndra'
    varus='Varus'; wukong='MonkeyKing'; xayah='Xayah'; yasuo='Yasuo'; yone='Yone'
    yunara='Yunara'; zed='Zed'
}
foreach ($entry in $champions.GetEnumerator()) {
    $url = "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/$($entry.Value)_0.jpg"
    Save-OfficialAsset $url (Join-Path $championRoot "$($entry.Key).jpg")
}

$ioniaAssets = [ordered]@{
    'runeterra-terrain.jpg'='https://map.leagueoflegends.com/assets/images/tiles/terrain_z1.jpg'
    'ionia-emblem.png'='https://map.leagueoflegends.com/assets/images/regions/ionia.png'
    'placidium-landmark.png'='https://map.leagueoflegends.com/assets/obj/landmarks/placidium.png'
    'first-lands.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/e8a24e6e60fe602dae0b9211b58465ec689a8d03-1920x737.jpg?accountingTag=LoL'
    'great-monasteries.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/72ad1322d9a8b12047f23f9f7d344de6735e54fc-1920x1079.jpg?accountingTag=LoL'
    'placidium.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/5b2f763df14096727e8b38405392126034ab9899-1920x888.jpg?accountingTag=LoL'
    'great-stand.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/2ac800dc33ba35196a61cddb5c6cf8ecae24b155-1189x755.jpg?accountingTag=LoL'
    'vastaya.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/436d62b38f970160b1cd9a67709f6855cd501b00-1920x849.jpg?accountingTag=LoL'
    'village-market.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/2e007fb236af9f3b91af54a8d8cc642d8e515299-1920x1080.jpg?accountingTag=LoL'
    'coastal-region.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/7167be57432556be8170a582c09dae87c0e0251e-1920x1080.jpg?accountingTag=LoL'
    'ionian-farm.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/be226cc46fc8c540058cc7dd22265327106fbc83-1832x837.jpg?accountingTag=LoL'
    'forest-market.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/32e13bdc6ee2c23376d5643c0810b9235b2cd8b0-832x1080.jpg?accountingTag=LoL'
    'kinkou.jpg'='https://cmsassets.rgpub.io/sanity/images/dsfx7636/universe_live/6e96758b6430e1d21bc160e829931e62f9e6dca2-2585x736.jpg?accountingTag=LoL'
}
foreach ($entry in $ioniaAssets.GetEnumerator()) {
    Save-OfficialAsset $entry.Value (Join-Path $ioniaRoot $entry.Key)
}

Write-Host "Official lore assets ready: $assetRoot"
