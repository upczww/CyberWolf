# LycanTUI 素材生成提示词 — 统一暗黑童话手绘卡牌风格 / Copy-Ready 版

> 本文档中的每一条提示词都可以单独复制直接使用，不需要再手动拼接“全局风格前缀”。  
> 统一风格参考：刚才生成的女巫卡牌风格 —— 暗黑哥特童话、复古手绘故事书、粗糙墨线、旧羊皮纸、水彩污渍、怪诞但可爱、幽默恐怖桌游卡牌感。  
> 图片统一避免文字：底部铭牌保持空白，不要出现角色名、Logo、水印或乱码文字。  
> 音效和 BGM 统一服务于“月牙村狼人杀”的场景，不使用现代科幻音色、现代枪械或歌词。

---

## 0. 统一生成规格

### 角色卡
- 推荐生成：1024×1536，2:3 竖版。
- 前端使用：可缩放到 512×768。
- 画面：完整角色卡，带旧羊皮纸背景、黑色不规则装饰边框、底部空白铭牌。
- 禁止：文字、乱码、Logo、水印。

### 场景背景
- 推荐生成：1920×1080，16:9 横版。
- 画面：场景背景，不要卡牌边框，不要铭牌，不要文字。

### UI / 图标
- 图标推荐：128×128 或 256×256，透明背景。
- 风格：暗黑童话、粗糙墨线、厚轮廓、清晰剪影，适合小尺寸识别。

### 音效 / BGM
- SFX：MP3 / OGG，44.1kHz，Stereo，建议 -14 LUFS。
- BGM：OGG 128kbps 或 MP3，44.1kHz，Stereo。
- 循环 BGM：首尾必须处在同一和弦 / 同一节拍位置，适合 loop=true。

---

# 一、角色卡牌提示词

## 1.1 狼人 — `avatars/wolf.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature werewolf, oversized head and glowing amber eyes, sinister gray wolf with pointed ears, jagged white fangs in a wide cunning grin, fluffy wild fur with visible rough ink texture, hunched predatory pose facing the viewer, front paws held together as if scheming, bushy tail curled around the body, narrow menacing but charming face, small patches of moonlight on the fur, old parchment background with dirty paper grain and watercolor stains, muted blue-purple moonlit glow behind the character, sepia brown shadows, cel-shaded flat colors, ornate black irregular decorative border with thorny vines and tiny skull motifs, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

## 1.2 预言家 — `avatars/seer.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature seer and fortune teller, oversized head with large glowing violet eyes that pierce through darkness, narrow wizened face, wild flowing white hair, tall crooked wizard hat covered with tiny moon and star symbols, tattered indigo robes with faded constellation embroidery, bony hands clutching a cracked crystal ball that emits eerie purple light, hunched mysterious pose, knowing unsettling smile, old parchment background with dirty paper grain and watercolor stains, muted purple mystic glow, sepia brown shadows, cel-shaded flat colors, ornate black irregular decorative border with spiderweb corners and occult ornaments, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

## 1.3 女巫 — `avatars/witch.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature witch, oversized head with heterochromia eyes, one vivid green eye and one deep purple eye, messy short black bob hair with crooked bangs, narrow impish face, mischievous knowing smirk, wearing a bent pointy witch hat with a tiny bat clinging to the brim, tattered emerald dress with a stained off-white apron, rope belt holding two potion bottles, one bubbling green potion and one smoking purple potion, hunched slightly forward pose with long bony fingers, old parchment background with dirty paper grain and watercolor stains, muted green-purple dual magical glow, sepia brown shadows, cel-shaded flat colors, ornate black irregular decorative border with curled vines, skulls, spiderwebs and moon ornaments, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

## 1.4 猎人 — `avatars/hunter.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature hunter, oversized head and intense tired eyes, narrow weathered face, weary paranoid expression, messy dark hair and short beard, patched medieval leather coat with worn shoulder straps, carrying a heavy old crossbow instead of a gun, one hand gripping the crossbow and the other holding a silver bolt, compact hunched defensive pose facing the viewer, determined but nervous guardian of the village, old parchment background with dirty paper grain and watercolor stains, muted yellow-green lantern glow mixed with cold moon shadows, sepia brown shadows, cel-shaded flat colors, ornate black irregular decorative border with thorn branches, bolts and tiny wolf-claw ornaments, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

## 1.5 白痴 — `avatars/idiot.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature village fool, oversized round head with permanently happy vacant crescent-moon eyes, gap-toothed dopey grin, floppy faded jester cap with tarnished bells, mismatched patched rags in faded red, yellow and green, clutching a ratty stuffed toy to the chest, oblivious carefree slouched pose, slightly drooling but sweet and harmless, narrow childlike face, old parchment background with dirty paper grain and watercolor stains, muted warm golden glow with faint spooky green edges, sepia brown shadows, cel-shaded flat colors, ornate black irregular decorative border with playful crooked bells, tiny stars and thorny vines, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

## 1.6 村民 — `avatars/villager.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature peasant villager, oversized head with big worried earnest eyes, plain anxious face, worn straw hat, simple patched brown tunic and rough cloth scarf, holding a flickering lantern nervously in both hands, hunched timid posture, looking over one shoulder fearfully, ordinary frightened everyman of Crescent Moon Village, old parchment background with dirty paper grain and watercolor stains, muted warm amber lantern glow surrounded by cool blue village shadows, sepia brown shadows, cel-shaded flat colors, ornate black irregular decorative border with lanterns, vines, small crescent moons and cracked wood ornaments, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

---

# 二、场景背景提示词

## 2.1 夜晚村庄全景 — `backgrounds/night_village.jpg`

```text
Dark gothic fairy-tale cinematic background, vintage hand-drawn storybook matte painting with scratchy ink outlines, watercolor stains and subtle dirty parchment texture, wide establishing shot of Crescent Moon Village at night, a full moon partly covered by a crescent-shaped shadow casting eerie light, Gothic-Chinese fusion architecture with pointed arches, curved tiled eaves, wooden balconies and red lanterns, cobblestone village square at center with an ancient round table beneath a massive dead tree, misty winding streets, flickering orange lanterns contrasting against deep blue moonlight, distant bell tower combining Gothic spire and Chinese pagoda silhouette, faint wolf shadows barely visible on rooftops, atmospheric fog at ground level, dark blue and purple palette with warm amber accents, eerie humorous board game fantasy atmosphere, cinematic depth, 16:9 aspect ratio, 1920x1080, no text, no watermark, no logo
```

## 2.2 狼人视角 — `backgrounds/night_wolf_pov.jpg`

```text
Dark gothic fairy-tale cinematic background, vintage hand-drawn storybook matte painting with scratchy ink outlines, watercolor stains and subtle dirty parchment texture, night scene from the wolves' perspective on a rooftop overlooking sleeping Crescent Moon Village, curved roof tiles in the foreground, one large wolf claw gripping the edge of the roof, village square far below with the ancient round table faintly visible, scattered lantern lights glowing in mist, several pairs of amber wolf eyes hidden in the surrounding darkness, blood moon behind thin clouds, Gothic-Chinese rooftops, twisted eaves and narrow alleys, predatory hunting atmosphere, dark red, black and midnight blue palette with amber eye-light accents, cinematic wide shot, 16:9 aspect ratio, 1920x1080, no text, no watermark, no logo
```

## 2.3 白天村庄集会 — `backgrounds/day_meeting.jpg`

```text
Dark gothic fairy-tale cinematic background, vintage hand-drawn storybook matte painting with scratchy ink outlines, watercolor stains and subtle dirty parchment texture, daytime village square of Crescent Moon Village during a heated meeting, golden morning sunlight breaking through heavy clouds, ancient round table at center with 12 ornate chairs visible, villagers shown only as expressive silhouettes and small groups arguing, Gothic-Chinese fusion buildings surrounding the square with pointed arches and curved eaves, cherry blossom trees with petals drifting in the air, closed market stalls creating a serious atmosphere despite daylight, long shadows, warm amber and desaturated green palette with underlying tension, birds circling overhead, eerie humorous board game fantasy mood, cinematic composition, 16:9 aspect ratio, 1920x1080, no text, no watermark, no logo
```

## 2.4 投票放逐处刑场 — `backgrounds/day_execution.jpg`

```text
Dark gothic fairy-tale cinematic background, vintage hand-drawn storybook matte painting with scratchy ink outlines, watercolor stains and subtle dirty parchment texture, village execution platform during an exile vote, raised stone platform in the center of Crescent Moon Village square, crooked wooden pillar with ropes, crowd of villagers gathered as dark silhouettes holding papers and torches even in daylight, dramatic cloudy sky with god rays breaking through, Gothic-Chinese architecture framing the scene, ancient round table partially visible in the background, oppressive tense atmosphere, desaturated warm tones with harsh shadows, eerie humorous fantasy board game style, cinematic composition, 16:9 aspect ratio, 1920x1080, no text, no watermark, no logo
```

## 2.5 黎明过渡 — `backgrounds/dawn_transition.jpg`

```text
Dark gothic fairy-tale cinematic background, vintage hand-drawn storybook matte painting with scratchy ink outlines, watercolor stains and subtle dirty parchment texture, dawn breaking over Crescent Moon Village, sky transitioning from deep midnight blue on the left to warm golden orange on the right, first sunrays touching the Gothic-Chinese bell tower peak, long dramatic shadows stretching across the cobblestone square, night mist slowly dissipating in the warming light, ancient round table in the center with evidence of last night's violence, overturned chair, extinguished lantern, scattered feathers and claw marks, small birds beginning to fly, hope mixed with dread atmosphere, cinematic panorama, 16:9 aspect ratio, 1920x1080, no text, no watermark, no logo
```

## 2.6 好人胜利 — `backgrounds/victory_good.jpg`

```text
Dark gothic fairy-tale cinematic background, vintage hand-drawn storybook matte painting with scratchy ink outlines, watercolor stains and subtle dirty parchment texture, triumphant dawn over Crescent Moon Village after the wolves' defeat, brilliant golden sunrise flooding the village square, villagers celebrating as joyful silhouettes, cherry blossoms blooming brightly, the ancient round table restored and clean, the seer's crystal ball glowing warmly on the table, a dissolving wolf shadow fading into sunlight, doves flying overhead, Gothic-Chinese buildings bathed in warm gold and soft green light, hopeful heroic relief after a nightmare, whimsical but gothic board game atmosphere, cinematic composition, 16:9 aspect ratio, 1920x1080, no text, no watermark, no logo
```

## 2.7 狼人胜利 — `backgrounds/victory_wolf.jpg`

```text
Dark gothic fairy-tale cinematic background, vintage hand-drawn storybook matte painting with scratchy ink outlines, watercolor stains and subtle dirty parchment texture, apocalyptic blood moon over ruined Crescent Moon Village after the wolves' victory, village square in flames and smoke, ancient round table shattered into pieces, wolf pack silhouettes howling on the bell tower against the blood-red moon, empty streets with claw marks on walls, last lantern extinguished with smoke rising, Gothic-Chinese buildings crumbling, ash falling like black snow, red and black apocalyptic palette with deep purple shadows, dreadful final mood, eerie fantasy board game atmosphere, cinematic desolate composition, 16:9 aspect ratio, 1920x1080, no text, no watermark, no logo
```

---

# 三、UI 元素提示词

## 3.1 圆桌俯视图 — `ui/table_top.png`

```text
Dark gothic fairy-tale game UI element, vintage hand-drawn storybook illustration with scratchy ink outlines and cel-shaded flat colors, top-down view of an ancient ornate circular wooden table, dark aged oak with intricate carved patterns of wolf faces, crescent moons, thorn vines and Chinese cloud scroll motifs along the thick raised edge, 12 evenly spaced position markers carved into the rim as subtle rune circles, a single tall melting candle in the exact center on a black iron holder, wax drips forming mysterious patterns, surface worn smooth by centuries of use, moody candlelight, perfectly circular composition, transparent background outside the table edge, high detail, 1024x1024, no text, no watermark, no logo
```

## 3.2 好人阵营卡片边框 — `ui/frame_good.png`

```text
Dark gothic fairy-tale game UI card frame, vintage hand-drawn storybook ornament with scratchy black ink outlines, ornate rectangular border frame for a hero character card, intertwined antique golden vines, silver crescent moon motifs, tiny protective rune symbols in each corner, subtle holy white-gold inner glow, faint Chinese cloud scroll patterns blended with Gothic arches, aged parchment texture on the frame itself, elegant righteous feeling, center area completely transparent and empty for portrait insertion, outside of the frame completely transparent, 2:3 vertical card frame, 256x384, no text, no watermark, no logo
```

## 3.3 狼人阵营卡片边框 — `ui/frame_wolf.png`

```text
Dark gothic fairy-tale game UI card frame, vintage hand-drawn storybook ornament with scratchy black ink outlines, ornate rectangular border frame for a villain werewolf character card, thorny black vines, dark red berries, wolf claw scratch marks integrated into the border design, tiny curse rune symbols in each corner, subtle blood-red ominous inner glow, faint Chinese cloud scroll patterns corrupted by Gothic thorn shapes, aged dark leather and stained parchment texture on the frame, menacing corrupted feeling, center area completely transparent and empty for portrait insertion, outside of the frame completely transparent, 2:3 vertical card frame, 256x384, no text, no watermark, no logo
```

## 3.4 警长徽章 — `ui/badge_sheriff.png`

```text
Dark gothic fairy-tale game UI collectible item, vintage hand-drawn storybook illustration with scratchy ink outlines and cel-shaded metallic shading, detailed golden sheriff star badge, six-pointed star design, small wolf head engraving in the center circle, ornate filigree around the star points, aged metallic gold with patina and small scratches, tiny crescent moon gem inset at the top point, chain attachment loop at the top, dramatic warm light reflections, clean readable silhouette for game UI, transparent background, 256x256, no text, no watermark, no logo
```

## 3.5 Loading 画面 — `ui/loading_card.png`

```text
Dark gothic fairy-tale loading screen for a werewolf board game, vintage hand-drawn storybook tarot card back design, scratchy black ink line art, messy uneven outlines, aged parchment texture, centered composition featuring a howling wolf silhouette against a crescent moon, intricate circle of 12 rune symbols representing player seats, ornate border with intertwining Gothic thorn vines and Chinese cloud scroll patterns, four corner symbols: crystal ball, potion bottle, crossbow bolt, sheriff star, deep midnight blue background with antique gold linework and tiny blood-red accent dots, mystical and foreboding atmosphere, high detail, vertical full-screen layout, 1080x1920, no readable text, no watermark, no logo
```

## 3.6 游戏 Logo — `ui/logo.png`

```text
Game logo design for the title LycanTUI, dark gothic fairy-tale werewolf game style, stylized fantasy wordmark where the letter L subtly transforms into a wolf claw reaching upward, the letter y includes a crescent moon shape, TUI rendered in bold Gothic-Chinese fusion calligraphy, metallic dark iron texture on the main letters, blood-red accent on the claw, subtle antique golden glow around TUI, faint full moon circle behind the wordmark, elegant clean silhouette suitable for game title screen, horizontal layout, transparent background, 1920x480, high detail, no extra words, no watermark, no additional logo
```

---

# 四、技能图标提示词

## 4.1 狼刀 — `ui/icons/claw_slash.png`

```text
Dark gothic fairy-tale game skill icon, vintage hand-drawn storybook style with scratchy black ink outline and cel-shaded flat colors, three diagonal wolf claw slash marks glowing blood-red, fresh wound-like cuts with a few dark blood droplets spraying, slight motion blur suggesting speed, smoky black particles around the slashes, strong readable silhouette for 128x128 UI, dramatic red glow, transparent background, high contrast, no text, no watermark, no logo
```

## 4.2 预言之眼 — `ui/icons/seer_eye.png`

```text
Dark gothic fairy-tale game skill icon, vintage hand-drawn storybook style with scratchy black ink outline and cel-shaded flat colors, mystical third eye with deep purple iris and antique golden sclera, radiating violet divination light rays, thin celestial rune circle surrounding the eye, tiny moon and star particles, all-seeing magical feeling, strong readable silhouette for 128x128 UI, transparent background, high contrast, no text, no watermark, no logo
```

## 4.3 解药瓶 — `ui/icons/antidote.png`

```text
Dark gothic fairy-tale game skill icon, vintage hand-drawn storybook style with scratchy black ink outline and cel-shaded flat colors, round-bottom glass potion flask filled with glowing emerald green liquid, cork stopper sealed with aged golden wax, healing sparkles and tiny leaf particles rising from the bottle, warm life-restoring magical glow, strong readable silhouette for 128x128 UI, transparent background, high contrast, no text, no watermark, no logo
```

## 4.4 毒药瓶 — `ui/icons/poison.png`

```text
Dark gothic fairy-tale game skill icon, vintage hand-drawn storybook style with scratchy black ink outline and cel-shaded flat colors, skull-shaped glass vial filled with bubbling dark purple-black poison, cork stopper sealed with purple wax, toxic green vapor curling upward with tiny skull-shaped smoke puffs, ominous magical glow, strong readable silhouette for 128x128 UI, transparent background, high contrast, no text, no watermark, no logo
```

## 4.5 猎人弩箭 — `ui/icons/crossbow_bolt.png`

```text
Dark gothic fairy-tale game skill icon, vintage hand-drawn storybook style with scratchy black ink outline and cel-shaded flat colors, single silver crossbow bolt flying diagonally through the air, sharp metallic arrowhead gleaming, white feather fletching, speed motion lines behind it, slight red-hot glow at the tip, dramatic final-shot feeling, strong readable silhouette for 128x128 UI, transparent background, high contrast, no text, no watermark, no logo
```

## 4.6 投票票据 — `ui/icons/ballot_vote.png`

```text
Dark gothic fairy-tale game skill icon, vintage hand-drawn storybook style with scratchy black ink outline and cel-shaded flat colors, folded parchment ballot being dropped into an old wooden ballot box with iron lock, ballot glowing with warm golden light of justice, tiny paper scraps and dust particles, tense village vote atmosphere, strong readable silhouette for 128x128 UI, transparent background, high contrast, no text, no watermark, no logo
```

## 4.7 警长竞选 — `ui/icons/sheriff_star.png`

```text
Dark gothic fairy-tale game skill icon, vintage hand-drawn storybook style with scratchy black ink outline and cel-shaded flat colors, golden six-pointed sheriff star badge, polished but aged metallic surface, tiny wolf engraving in the center, crescent moon jewel at the top, radiating authority with warm golden light, strong readable silhouette for 128x128 UI, transparent background, high contrast, no text, no watermark, no logo
```

## 4.8 狼人自爆 — `ui/icons/self_destruct.png`

```text
Dark gothic fairy-tale game skill icon, vintage hand-drawn storybook style with scratchy black ink outline and cel-shaded flat colors, dramatic dark magic explosion with a black wolf silhouette at the center, red and orange fire burst mixed with purple shadow energy, debris flying outward, smoky circular shockwave, destructive violent energy but stylized for board game UI, strong readable silhouette for 128x128 UI, transparent background, high contrast, no text, no watermark, no logo
```

---

# 五、音效 SFX 提示词

## 5.1 天黑转场 — `sfx/phase_night.mp3` — 3.0s

```text
Generate a 3.0-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: night falls over Crescent Moon Village. Start with faint evening crickets and a distant wooden village bell, then lantern flames dim and wind passes through bare branches and curved roof eaves. Add one lonely wolf howl far away in the mountains, followed by a soft ominous low bass drone fading in. Mood: eerie, suspenseful, magical village horror, not modern, not sci-fi. High quality game SFX, 44.1kHz stereo, clean fade out, no dialogue, no lyrics.
```

## 5.2 天亮转场 — `sfx/phase_dawn.mp3` — 3.0s

```text
Generate a 3.0-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: dawn returns to Crescent Moon Village after a dangerous night. Begin with the last trace of cold night wind fading away, then a rooster crows softly, small birds begin chirping, a distant village bell tolls once, and a warm morning breeze moves through paper lanterns and wooden eaves. Mood: hopeful but still tense, relief mixed with dread. High quality medieval fantasy village SFX, 44.1kHz stereo, natural fade out, no dialogue, no lyrics.
```

## 5.3 狼刀击杀 — `sfx/skill_wolf_kill.mp3` — 1.5s

```text
Generate a 1.5-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: the werewolves choose a victim at night. Use three rapid claw slashes cutting through the air from left to right, a low wolf growl underneath, a short sharp impact, and a dark reverb tail that fades into silence. Make it visceral and frightening but stylized, suitable for a board game UI, not excessively gory. High quality horror fantasy combat SFX, 44.1kHz stereo, no dialogue, no lyrics.
```

## 5.4 预言家查验 — `sfx/skill_seer_check.mp3` — 2.0s

```text
Generate a 2.0-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: the seer uses a crystal ball to inspect a player. Begin with a soft glass chime, then a swirling magical hum, faint paper talisman rustle, tiny star-like sparkles, and a short mystical reveal shimmer at the end. Use purple divination energy, ancient village magic, and subtle choir-like air without vocals. Mood: mysterious, focused, supernatural. High quality fantasy magic SFX, 44.1kHz stereo, no dialogue, no lyrics.
```

## 5.5 女巫解药 — `sfx/skill_antidote.mp3` — 2.0s

```text
Generate a 2.0-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: the witch uses a green antidote potion to save someone from death. Start with a small cork pop from a glass bottle, then shimmering liquid pouring, warm rising bell tones, tiny sparkling particles, and a soft breath-of-life swell at the end. Mood: healing, magical, relieved, but still gothic and eerie. High quality fantasy potion SFX, 44.1kHz stereo, no dialogue, no lyrics.
```

## 5.6 女巫毒药 — `sfx/skill_poison.mp3` — 2.0s

```text
Generate a 2.0-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: the witch uses a purple poison potion. Start with a darker cork pop, thick liquid bubbling in glass, toxic vapor hissing, tiny skull-like smoke wisps, then a descending dissonant magical tone and a short fatal shadow impact. Mood: sinister, poisonous, magical, tense. High quality dark fantasy potion SFX, 44.1kHz stereo, no dialogue, no lyrics.
```

## 5.7 猎人射击 — `sfx/skill_hunter_shoot.mp3` — 1.5s

```text
Generate a 1.5-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: the hunter fires an old crossbow in the village square. Use a tight crossbow string release twang, a silver bolt whistling through the air, a fast whoosh, then a solid wooden target impact with a short echo between stone houses. Mood: dramatic, final, heroic but grim. Medieval fantasy weapon SFX, not a gunshot, not modern firearm. High quality 44.1kHz stereo, no dialogue, no lyrics.
```

## 5.8 狼人自爆 — `sfx/skill_self_destruct.mp3` — 2.0s

```text
Generate a 2.0-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: a werewolf reveals itself and self-destructs in dark magic. Begin with a rising wolf growl turning into a sharp howl, add cracking cursed bones and tearing shadow energy, then a compact magical explosion with glass shatter, stone dust, and a deep boom with dark reverb. Mood: shocking, violent, supernatural, board-game stylized. High quality dark fantasy SFX, 44.1kHz stereo, no dialogue, no lyrics.
```

## 5.9 投票定票 — `sfx/vote_result.mp3` — 1.5s

```text
Generate a 1.5-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: the village vote is finalized. Start with quick parchment ballots shuffling and anxious crowd murmurs, then sudden silence, followed by one heavy wooden gavel strike on the ancient round table and a short crowd gasp. Mood: tense, decisive, ritualistic village justice. High quality courtroom-meets-medieval-village SFX, 44.1kHz stereo, no dialogue, no lyrics.
```

## 5.10 放逐宣告 — `sfx/exile.mp3` — 2.0s

```text
Generate a 2.0-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: a player is exiled from Crescent Moon Village. Use a dramatic low orchestral hit, iron chains rattling, heavy wooden gate creaking and slamming shut, faint crowd reaction, and one final distant gong fading into silence. Mood: grim, ceremonial, tragic village justice. High quality dark fantasy drama SFX, 44.1kHz stereo, no dialogue, no lyrics.
```

## 5.11 警长当选 — `sfx/sheriff_elected.mp3` — 2.0s

```text
Generate a 2.0-second stereo sound effect for a dark gothic fairy-tale werewolf board game. Scene: the village sheriff is elected. Use a brief three-note brass fanfare with medieval character, a metallic badge pinning click, a short polite crowd applause, and a final small snare hit. Mood: authoritative, ceremonial, hopeful but tense. Avoid modern political sound, keep it gothic village fantasy. High quality ceremony SFX, 44.1kHz stereo, no dialogue, no lyrics.
```

## 5.12 好人胜利音效 — `sfx/victory_good.mp3` — 4.0s

```text
Generate a 4.0-second stereo victory sound effect for a dark gothic fairy-tale werewolf board game. Scene: villagers defeat the wolves at dawn. Use a triumphant short orchestral fanfare in a major key, French horns and warm strings, church bells ringing joyfully in the distance, crowd cheering softly, birds lifting into the sunrise, and a bright final shimmer. Mood: heroic relief after nightmare, warm golden dawn, cinematic but compact. High quality game victory SFX, 44.1kHz stereo, clean fade out, no dialogue, no lyrics.
```

## 5.13 狼人胜利音效 — `sfx/victory_wolf.mp3` — 4.0s

```text
Generate a 4.0-second stereo victory sound effect for a dark gothic fairy-tale werewolf board game. Scene: the wolves win and Crescent Moon Village falls under the blood moon. Use an ominous orchestral hit in a minor key, several wolves howling in harmony, thunder cracking far away, low brass doom chords, sinister string tremolo, wind through burning ruins, and a final lone wolf howl fading into darkness. Mood: dreadful, powerful, final. High quality dark epic game victory SFX, 44.1kHz stereo, no dialogue, no lyrics.
```

---

# 六、背景音乐 BGM 提示词

## 6.1 夜晚阶段循环 — `bgm/night_loop.ogg` — 30s

```text
Create a 30-second seamless loop background music track for a dark gothic fairy-tale werewolf board game night phase. Tempo 60 BPM, key of D minor. Scene: Crescent Moon Village under moonlight while werewolves hunt. Instruments: low cello drone, sparse high-register haunted piano notes, subtle heartbeat bass drum very soft, bowed cymbal texture, distant wooden bell, faint ethereal female choir-like humming without lyrics, one distant wolf howl around the middle of the loop. Mood: mysterious, dangerous, suspenseful, ancient village horror. The first and last beat must connect perfectly on the same chord and same rhythmic position for seamless looping. Cinematic orchestral + dark ambient hybrid, 44.1kHz stereo, no lyrics, no spoken words.
```

## 6.2 白天讨论循环 — `bgm/day_discussion.ogg` — 30s

```text
Create a 30-second seamless loop background music track for a dark gothic fairy-tale werewolf board game daytime discussion phase. Tempo 90 BPM, key of A minor. Scene: villagers argue around the ancient round table in Crescent Moon Village. Instruments: pizzicato strings repeating a suspicious motif, light frame drum, sparse guzheng plucks, low clarinet, muted hand percussion, soft wooden creaks. Mood: analytical, suspicious, tense but not action-heavy, medieval tavern mixed with village courtroom. The first and last beat must connect perfectly on the same chord and same rhythmic position for seamless looping. Cinematic game soundtrack, 44.1kHz stereo, no lyrics, no spoken words.
```

## 6.3 投票紧张循环 — `bgm/vote_tension.ogg` — 20s

```text
Create a 20-second seamless loop background music track for a dark gothic fairy-tale werewolf board game voting countdown. Tempo 120 BPM, key of E minor. Scene: villagers cast final votes while someone may be exiled. Instruments: driving low string ostinato, ticking wooden clock percussion, short brass staccato stabs, snare drum pattern, heartbeat-like bass pulse, faint paper ballot rustle used rhythmically. Mood: urgent, life-or-death, tense, ritualistic. The first and last beat must connect perfectly on the same chord and same rhythmic position for seamless looping. Cinematic game soundtrack, 44.1kHz stereo, no lyrics, no spoken words.
```

## 6.4 警长竞选循环 — `bgm/sheriff_campaign.ogg` — 30s

```text
Create a 30-second seamless loop background music track for a dark gothic fairy-tale werewolf board game sheriff election phase. Tempo 100 BPM, key of G minor. Scene: players compete for authority in Crescent Moon Village. Instruments: bold but restrained brass authority theme, military snare played softly, competitive string runs, low drum pulses, Chinese erhu melodic fragments for Eastern flavor, occasional metallic badge chime. Mood: political, competitive, ceremonial, tense, slightly theatrical. The first and last beat must connect perfectly on the same chord and same rhythmic position for seamless looping. Cinematic game soundtrack, 44.1kHz stereo, no lyrics, no spoken words.
```

## 6.5 好人胜利结算 — `bgm/victory_good.ogg` — 15s

```text
Create a 15-second non-looping victory music cue for a dark gothic fairy-tale werewolf board game. Tempo 120 BPM, key of D major. Scene: dawn breaks after the villagers defeat the wolves. Structure: 0-5 seconds explosive triumphant brass and strings climax, 5-10 seconds warm hopeful solo violin melody, 10-15 seconds gentle fade with flute, soft bells and birds. Mood: heroic relief, golden sunrise after nightmare, cinematic fantasy victory. Clean natural fade out, 44.1kHz stereo, no lyrics, no spoken words.
```

## 6.6 狼人胜利结算 — `bgm/victory_wolf.ogg` — 15s

```text
Create a 15-second non-looping dark victory music cue for a dark gothic fairy-tale werewolf board game. Tempo 80 BPM, key of D minor. Scene: the wolf pack wins and Crescent Moon Village is ruined under a blood moon. Structure: 0-5 seconds ominous orchestral hit with a huge wolf howl, 5-10 seconds sinister low brass march with deep drums and string tremolo, 10-15 seconds fade into wind through ruins and one lone wolf howl in silence. Mood: dreadful, powerful, final, apocalyptic fantasy. Clean natural fade out, 44.1kHz stereo, no lyrics, no spoken words.
```

---

# 七、可选状态卡提示词

## 7.1 女巫使用解药 — `avatars/witch_antidote.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature witch using an antidote potion, oversized head with heterochromia eyes, one vivid green eye and one deep purple eye, messy short black bob hair, bent pointy witch hat with a tiny bat on the brim, tattered emerald dress and stained apron, holding a glowing emerald green potion bottle high in one bony hand, warm healing light spilling over her mischievous face, green sparkles and leaf-shaped magic particles rising around her, old parchment background with dirty paper grain and watercolor stains, muted green magical glow, sepia brown shadows, cel-shaded flat colors, ornate black irregular decorative border, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D vertical card, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

## 7.2 女巫使用毒药 — `avatars/witch_poison.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature witch using a poison potion, oversized head with heterochromia eyes, one vivid green eye and one deep purple eye, messy short black bob hair, bent pointy witch hat with a tiny bat on the brim, tattered emerald dress and stained apron, holding a smoking purple poison bottle close to her sly grin, toxic violet smoke curling into tiny skull shapes, green-purple sinister glow across her face, old parchment background with dirty paper grain and watercolor stains, sepia brown shadows, cel-shaded flat colors, ornate black irregular decorative border, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D vertical card, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

## 7.3 猎人射击 — `avatars/hunter_shooting.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature hunter firing an old crossbow, oversized head and intense tired eyes, patched medieval leather coat, hunched compact pose, heavy crossbow aimed toward the viewer with a silver bolt just released, dramatic motion lines and warm lantern glow, determined grim expression, old parchment background with dirty paper grain and watercolor stains, muted yellow-green glow and sepia brown shadows, cel-shaded flat colors, ornate black irregular decorative border with bolts and thorn vines, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D vertical card, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

## 7.4 白痴翻牌 — `avatars/idiot_reveal.png`

```text
Dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature village fool revealing himself, oversized round head with happy vacant crescent-moon eyes, gap-toothed grin, floppy jester cap with tarnished bells, mismatched patched rags, holding up a blank wooden sign proudly with no text on it, villagers' shocked silhouettes in the parchment background, warm silly golden glow mixed with eerie green shadows, dirty paper grain and watercolor stains, cel-shaded flat colors, ornate black irregular decorative border, empty blank parchment nameplate at the bottom with no text, standardized fixed nameplate height matching every character card, eerie humorous fantasy board game aesthetic, 2D vertical card, high detail, 2:3 aspect ratio, no words, no letters, no watermark, no logo
```

---

# 八、文件组织建议

```text
desktop/public/assets/
├── avatars/
│   ├── wolf.png
│   ├── seer.png
│   ├── witch.png
│   ├── hunter.png
│   ├── idiot.png
│   ├── villager.png
│   ├── witch_antidote.png
│   ├── witch_poison.png
│   ├── hunter_shooting.png
│   └── idiot_reveal.png
├── backgrounds/
│   ├── night_village.jpg
│   ├── night_wolf_pov.jpg
│   ├── day_meeting.jpg
│   ├── day_execution.jpg
│   ├── dawn_transition.jpg
│   ├── victory_good.jpg
│   └── victory_wolf.jpg
├── ui/
│   ├── table_top.png
│   ├── frame_good.png
│   ├── frame_wolf.png
│   ├── badge_sheriff.png
│   ├── loading_card.png
│   ├── logo.png
│   └── icons/
│       ├── claw_slash.png
│       ├── seer_eye.png
│       ├── antidote.png
│       ├── poison.png
│       ├── crossbow_bolt.png
│       ├── ballot_vote.png
│       ├── sheriff_star.png
│       └── self_destruct.png
├── sfx/
│   ├── phase_night.mp3
│   ├── phase_dawn.mp3
│   ├── skill_wolf_kill.mp3
│   ├── skill_seer_check.mp3
│   ├── skill_antidote.mp3
│   ├── skill_poison.mp3
│   ├── skill_hunter_shoot.mp3
│   ├── skill_self_destruct.mp3
│   ├── vote_result.mp3
│   ├── exile.mp3
│   ├── sheriff_elected.mp3
│   ├── victory_good.mp3
│   └── victory_wolf.mp3
└── bgm/
    ├── night_loop.ogg
    ├── day_discussion.ogg
    ├── vote_tension.ogg
    ├── sheriff_campaign.ogg
    ├── victory_good.ogg
    └── victory_wolf.ogg
```

---

# 九、批量一致性建议

## 9.1 图片一致性复制提示

```text
Use the same seed or reference image for all character cards. Keep the same dark gothic fairy-tale storybook card frame, parchment texture, scratchy ink line art, grotesque but cute proportions, and bottom blank nameplate. Do not generate readable text. Keep characters centered, full body or three-quarter full body, with oversized heads and expressive eyes.
```

## 9.2 音频一致性复制提示

```text
Keep all audio assets in the same sonic world: dark gothic fairy-tale werewolf village, medieval instruments, subtle Chinese folk texture, old wood, bells, parchment, lantern flame, wolves, wind, stone square, and ritual tension. Avoid modern guns, electronic EDM, modern city sounds, lyrics, spoken dialogue, and sci-fi effects.
```
