# 素材生成提示词

本文档包含 LycanTUI 桌面端所需的所有素材生成提示词。

---

## 零、素材技术规格总表

### 图片素材

| 类别 | 尺寸（px） | 格式 | 色彩模式 | 备注 |
|------|-----------|------|----------|------|
| 角色立绘 | 512×768 | PNG (RGBA) | sRGB | 透明背景，半身竖版 |
| 场景背景 | 1920×1080 | JPG | sRGB | 质量 90%+，无透明 |
| 圆桌俯视 | 1024×1024 | PNG (RGBA) | sRGB | 圆形外透明 |
| 卡片边框 | 256×384 | PNG (RGBA) | sRGB | 中心透明（放立绘） |
| 警长徽章 | 256×256 | PNG (RGBA) | sRGB | 透明背景 |
| 技能图标 | 128×128 | PNG (RGBA) | sRGB | 透明背景 |
| Loading画面 | 1080×1920 | PNG | sRGB | 竖版全屏 |
| Logo | 1920×480 | PNG (RGBA) | sRGB | 横版透明背景 |

### 动画效果（纯代码实现，无需图片素材）

所有动画效果由 CSS Animation + Framer Motion 在前端代码中实现，60FPS 矢量渲染：

| 效果 | 实现方式 |
|------|----------|
| 狼刀攻击 | 3条红色斜线 CSS clip-path 滑入 + 屏幕微震 |
| 毒药效果 | 紫色径向渐变扩散 + 模糊粒子上升 |
| 解药效果 | 绿色光点粒子螺旋上升 + 暖光脉冲 |
| 预言查验 | 紫色圆环缩放 + 扫描线从左到右 |
| 猎人开枪 | 白色线条射出 + 目标冲击波圆环 |
| 死亡碎裂 | 卡片分裂为多个 clip-path 碎片飞散 + 灰度 |
| 投票飘落 | 多个纸片 div 旋转下落 |
| 胜利庆典 | 多点径向爆炸 + 金色粒子雨 |
| 昼夜切换 | 背景渐变色 2s transition |
| 行动高亮 | 卡片 ring + pulse + scale |

### 音效素材

| 音效 | 时长 | 格式 | 采样率 | 位深 | 声道 |
|------|------|------|--------|------|------|
| 天黑 | 3.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 天亮 | 3.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 狼刀 | 1.5s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 预言查验 | 2.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 解药 | 2.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 毒药 | 2.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 猎人开枪 | 1.5s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 自爆 | 2.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 投票定票 | 1.5s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 放逐宣告 | 2.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 警长当选 | 2.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 好人胜利 | 4.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |
| 狼人胜利 | 4.0s | MP3 / OGG | 44.1kHz | 16bit | Stereo |

音量标准化：-14 LUFS（避免音量跳变）

### 背景音乐

| BGM | 时长 | 格式 | 采样率 | 位深 | BPM | 调性 | 循环 |
|-----|------|------|--------|------|-----|------|------|
| 夜晚 | 30s | OGG 128kbps | 44.1kHz | 16bit | 60 | Dm | 无缝循环 |
| 白天讨论 | 30s | OGG 128kbps | 44.1kHz | 16bit | 90 | Am | 无缝循环 |
| 投票紧张 | 20s | OGG 128kbps | 44.1kHz | 16bit | 110→130 | Em | 无缝循环 |
| 警长竞选 | 30s | OGG 128kbps | 44.1kHz | 16bit | 100 | Gm | 无缝循环 |
| 好人胜利 | 15s | OGG 128kbps | 44.1kHz | 16bit | 120 | D | 自然淡出 |
| 狼人胜利 | 15s | OGG 128kbps | 44.1kHz | 16bit | 80 | Dm | 自然淡出 |

循环点要求：短循环 BGM 首尾衔接必须无缝（同一音高、同一节拍位置），前端用 `loop=true` 自动重复播放。

### 文件大小预算

| 类别 | 单个约 | 总计约 |
|------|--------|--------|
| 角色立绘（6张） | 200-400KB | ~2MB |
| 场景背景（7张） | 500KB-1MB | ~5MB |
| UI 元素（11个） | 50-200KB | ~1.5MB |
| 动画效果 | 纯代码，0KB | 0 |
| 音效（13个） | 50-150KB | ~1.5MB |
| BGM（6首，短循环 OGG） | 400-600KB | ~3MB |
| **总计** | | **~13MB** |

---

## 素材文件名清单（完整）

生成素材后按以下文件名放入 `desktop/public/assets/` 目录，前端代码会直接引用这些路径。

### 角色立绘 — `avatars/`

| 角色 | 文件名 | 备注 |
|------|--------|------|
| 狼人 | `wolf.png` | 4狼共用 |
| 预言家 | `seer.png` | |
| 女巫 | `witch.png` | |
| 猎人 | `hunter.png` | |
| 白痴 | `idiot.png` | |
| 村民 | `villager.png` | 4民共用 |

**总计：6 张**

前端状态区分（CSS）：
- 发言中：`scale(1.1)` + 白色 `ring` 光圈 + 上下微浮动画
- 死亡：`grayscale(1)` + `opacity(0.5)` + 💀 叠加
- 被指控：`animate-shake` + 红色 `ring` + `scale(0.95)`
- 行动中：金色 `ring` + `animate-pulse`

### 场景背景 — `backgrounds/`

| 文件名 | 用途 | 触发条件 |
|--------|------|----------|
| `night_village.jpg` | 夜晚默认背景 | phase 包含 `night` |
| `night_wolf_pov.jpg` | 狼人行动特写 | phase = `night_wolf` |
| `day_meeting.jpg` | 白天集会 | phase 包含 `day` 或 `sheriff` |
| `day_execution.jpg` | 投票放逐场 | phase = `day_vote` 或 `day_resolve` |
| `dawn_transition.jpg` | 黎明过渡 | phase = `day_announce` |
| `victory_good.jpg` | 好人胜利 | winner = `good` |
| `victory_wolf.jpg` | 狼人胜利 | winner = `wolf` |

### UI 元素 — `ui/`

| 文件名 | 用途 | 尺寸 |
|--------|------|------|
| `table_top.png` | 圆桌俯视（桌面中央） | 1024×1024 |
| `frame_good.png` | 好人阵营卡片边框 | 256×384 |
| `frame_wolf.png` | 狼人阵营卡片边框 | 256×384 |
| `badge_sheriff.png` | 警长徽章（叠加在卡片上） | 256×256 |
| `loading_card.png` | 加载画面/启动屏 | 1080×1920 |
| `logo.png` | 游戏标题 Logo | 1920×480 |

### 技能图标 — `ui/icons/`

| 文件名 | 对应技能 | 尺寸 |
|--------|----------|------|
| `icon_claw.png` | 狼刀/狼人击杀 | 128×128 |
| `icon_eye.png` | 预言家查验 | 128×128 |
| `icon_antidote.png` | 女巫解药 | 128×128 |
| `icon_poison.png` | 女巫毒药 | 128×128 |
| `icon_bolt.png` | 猎人弩箭 | 128×128 |
| `icon_vote.png` | 投票 | 128×128 |
| `icon_sheriff.png` | 警长竞选/当选 | 128×128 |
| `icon_explode.png` | 狼人自爆 | 128×128 |

### 动画效果 — 纯代码（无素材文件）

所有动画由 CSS + Framer Motion 实现，不需要图片文件。参见「技术规格 - 动画效果」表。

### 音效 — `sfx/`

| 文件名 | 用途 | 时长 |
|--------|------|------|
| `sfx_night_fall.mp3` | 天黑转场 | 3.0s |
| `sfx_dawn.mp3` | 天亮转场 | 3.0s |
| `sfx_wolf_kill.mp3` | 狼刀击杀 | 1.5s |
| `sfx_seer_check.mp3` | 预言家查验 | 2.0s |
| `sfx_antidote.mp3` | 女巫解药 | 2.0s |
| `sfx_poison.mp3` | 女巫毒药 | 2.0s |
| `sfx_hunter_shoot.mp3` | 猎人开枪 | 1.5s |
| `sfx_self_destruct.mp3` | 狼人自爆 | 2.0s |
| `sfx_vote_result.mp3` | 投票定票（锤子） | 1.5s |
| `sfx_exile.mp3` | 放逐宣告 | 2.0s |
| `sfx_sheriff_elected.mp3` | 警长当选 | 2.0s |
| `sfx_victory_good.mp3` | 好人阵营胜利 | 4.0s |
| `sfx_victory_wolf.mp3` | 狼人阵营胜利 | 4.0s |

### 背景音乐 — `bgm/`

| 文件名 | 用途 | 时长 | 循环 | 格式 |
|--------|------|------|------|------|
| `bgm_night.ogg` | 夜晚阶段 | 30s | 无缝循环 | OGG 128kbps |
| `bgm_day.ogg` | 白天讨论 | 30s | 无缝循环 | OGG 128kbps |
| `bgm_vote.ogg` | 投票紧张 | 20s | 无缝循环 | OGG 128kbps |
| `bgm_sheriff.ogg` | 警长竞选 | 30s | 无缝循环 | OGG 128kbps |
| `bgm_victory_good.ogg` | 好人胜利结算 | 15s | 自然淡出 | OGG 128kbps |
| `bgm_victory_wolf.ogg` | 狼人胜利结算 | 15s | 自然淡出 | OGG 128kbps |

---

## 全局风格统一指令

所有角色卡牌素材在提示词前加上以下统一风格前缀：

```
Style: dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature, oversized head and eyes, cel-shaded flat colors, old parchment background, muted yellow-green glow, sepia brown shadows, dirty paper grain, watercolor stains, black irregular decorative border, bottom blank nameplate, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail
```

---

## 一、角色立绘（6 种角色，每角色 1 张）

狼人共用一个形象，村民共用一个形象。共 **6 张**。
不同状态（发言、死亡、被指控）由前端 CSS 实现（滤镜、缩放、抖动、灰度）。

尺寸统一：512x512，正面全身，透明背景
风格：经典狼人杀卡牌插画，童话绘本风，粗描边，圆润比例，大眼睛，色彩饱和

---

### 1.1 狼人 — `wolf.png`

```
dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature werewolf, a sinister gray wolf with oversized glowing amber eyes, pointed ears, sharp jagged fangs in a wide cunning grin, fluffy wild fur with scratchy ink texture, hunched predatory pose facing viewer, front paws together scheming, bushy tail curled, narrow menacing but charming face, old parchment background, muted blue-purple moonlit glow, sepia brown shadows, dirty paper grain, watercolor stains, cel-shaded flat colors, black irregular decorative border, bottom blank nameplate, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail
```

---

### 1.2 预言家 — `seer.png`

```
dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature fortune teller, oversized head and glowing violet eyes that pierce through darkness, wild flowing white hair, wearing a tall crooked wizard hat covered in star and moon symbols, tattered indigo robes with constellation embroidery, clutching a cracked crystal ball emanating eerie purple light, hunched mysterious pose, knowing unsettling smile, narrow wizened face, old parchment background, muted purple mystic glow, sepia brown shadows, dirty paper grain, watercolor stains, cel-shaded flat colors, black irregular decorative border, bottom blank nameplate, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail
```

---

### 1.3 女巫 — `witch.png`

```
dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature witch, oversized head with heterochromia eyes - one vivid green one deep purple, messy short black bob hair with crooked bangs, wearing a bent pointy witch hat with tiny bat clinging to the brim, tattered emerald dress with stained apron, two potion bottles hanging from rope belt - one bubbling green one smoking purple, mischievous knowing smirk, hunched slightly forward pose, narrow impish face, old parchment background, muted green-purple dual glow, sepia brown shadows, dirty paper grain, watercolor stains, cel-shaded flat colors, black irregular decorative border, bottom blank nameplate, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail
```

---

### 1.4 猎人 — `hunter.png`

```
dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature hunter, oversized head and eyes, narrow face, weary paranoid expression, messy hair and beard, patched medieval leather coat, large double-barrel shotgun pointing toward the viewer, hunched compact pose, old parchment background, muted yellow-green glow, sepia brown shadows, dirty paper grain, watercolor stains, cel-shaded flat colors, black irregular decorative border, bottom blank nameplate, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail
```

---

### 1.5 白痴 — `idiot.png`

```
dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature village idiot, oversized round head with permanently happy vacant curved-moon eyes, gap-toothed dopey grin, wearing a floppy colorful jester cap with tarnished bells, mismatched patched rags in faded colors, clutching a ratty stuffed toy to chest, oblivious carefree slouched pose, drooling slightly, narrow childlike face, old parchment background, muted warm golden glow, sepia brown shadows, dirty paper grain, watercolor stains, cel-shaded flat colors, black irregular decorative border, bottom blank nameplate, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail
```

---

### 1.6 村民 — `villager.png`

```
dark gothic fairy-tale character card, vintage hand-drawn storybook illustration, scratchy ink line art, messy uneven black outlines, grotesque but cute caricature peasant villager, oversized head with big worried earnest eyes, plain round anxious face, wearing a worn straw hat and simple patched brown tunic, holding a flickering lantern nervously in both hands, hunched timid posture, looking over shoulder fearfully, an ordinary frightened everyman, old parchment background, muted warm amber lantern glow, sepia brown shadows, dirty paper grain, watercolor stains, cel-shaded flat colors, black irregular decorative border, bottom blank nameplate, eerie humorous fantasy board game aesthetic, 2D illustration, vertical card layout, high detail
```

---

## 二、场景背景（1920x1080 横版）

### 2.1 夜晚 — 月牙村全景

```
Wide establishing shot of Crescent Moon Village at night, full moon with a crescent shadow casting eerie light, Gothic-Chinese fusion architecture - pointed arches with curved eaves, cobblestone village square with an ancient round table under a massive dead tree, misty winding streets, flickering lanterns casting orange pools of light against blue moonlight, a bell tower with both Gothic spire and Chinese pagoda elements in the distance, wolves' shadows barely visible on rooftops, deep blue and purple color palette with warm orange lantern accents, atmospheric fog at ground level, cinematic composition with depth, digital matte painting, 1920x1080
```

### 2.2 夜晚 — 狼人视角

```
Night scene from wolves' perspective on a rooftop overlooking the sleeping village, Crescent Moon Village below with scattered lantern lights, the round table visible in the square, a wolf's claw visible in foreground gripping roof tiles, multiple pairs of amber glowing eyes in the darkness around, blood moon overhead, predatory hunting atmosphere, dark red and black tones with amber eye-light accents, mist curling between buildings below, cinematic wide shot, digital matte painting, 1920x1080
```

### 2.3 白天 — 村庄集会

```
Daytime village square of Crescent Moon Village during a heated meeting, golden morning sunlight streaming through clouds, the ancient round table at center with 12 ornate chairs visible, Gothic-Chinese fusion buildings surrounding the square, cherry blossom trees with some petals drifting, market stalls closed (serious atmosphere despite daylight), long shadows suggesting late afternoon tension, warm amber and green palette but with underlying tension, birds circling overhead, cinematic composition, digital matte painting, 1920x1080
```

### 2.4 白天 — 投票处刑场

```
Village execution platform during exile vote, a raised stone platform with a wooden pillar in the center of the square, village crowd gathered (silhouettes) with torches despite daytime, the accused standing on platform with ropes visible, dramatic cloudy sky with god rays breaking through, Gothic-Chinese architecture framing the scene, tense oppressive atmosphere despite daylight, desaturated warm tones with dramatic shadows, cinematic composition, digital matte painting, 1920x1080
```

### 2.5 黎明 — 天亮过渡

```
Dawn breaking over Crescent Moon Village, sky transitioning from deep midnight blue on left to warm golden orange on right, first sunrays touching the Gothic-Chinese bell tower peak, long dramatic shadows stretching across cobblestone square, mist dissipating in the warming light, the round table in center with evidence of last night's violence (overturned chair, extinguished lantern), birds beginning to fly, hope mixed with dread atmosphere, cinematic panorama, digital matte painting, 1920x1080
```

### 2.6 游戏结束 — 好人胜利

```
Triumphant dawn over Crescent Moon Village after wolves' defeat, brilliant golden sunrise flooding the village square, villagers embracing and celebrating (silhouettes), the dead wolf's shadow dissolving in sunlight, cherry blossoms bursting into full bloom, the round table intact and clean, the seer's crystal glowing warmly on the table, doves flying overhead, warm gold and green celebratory palette, lens flare from sunrise, cinematic composition, digital matte painting, 1920x1080
```

### 2.7 游戏结束 — 狼人胜利

```
Apocalyptic blood moon over ruined Crescent Moon Village after wolves' victory, the village in flames and ruins, the round table shattered, wolf pack silhouettes howling on the bell tower against the blood-red moon, empty streets with claw marks on walls, last torch extinguished with smoke rising, Gothic-Chinese buildings crumbling, red and black apocalyptic palette, ash falling like snow, cinematically desolate composition, digital matte painting, 1920x1080
```

---

## 三、UI 元素

### 3.1 圆桌（俯视图）

```
Top-down view of an ancient ornate circular wooden table, dark aged oak with intricate carved patterns - wolf faces, crescent moons, and vine motifs along the thick raised edge, 12 evenly spaced position markers carved into the rim (subtle rune circles), a single tall melting candle in exact center on an iron holder, wax drips creating patterns, surface worn smooth by centuries of use, dark atmospheric lighting from the central candle only, game UI element, perfectly circular composition, 1024x1024, transparent background outside the table edge
```

### 3.2 角色卡片边框 — 好人阵营

```
Ornate rectangular card border frame for a hero character card, design features intertwined golden vines and silver crescent moon motifs, small protective rune symbols in each corner, subtle holy white-gold inner glow, the center is completely transparent/empty for portrait insertion, aged parchment texture on the frame itself, Gothic-Chinese ornamental fusion style, elegant and righteous feeling, 256x384, PNG with full transparency in center and outside frame
```

### 3.3 角色卡片边框 — 狼人阵营

```
Ornate rectangular card border frame for a villain character card, design features thorny black vines with blood-red berries, wolf claw scratch marks incorporated into the border design, small curse runes in each corner, subtle dark red ominous inner glow, the center is completely transparent/empty for portrait insertion, aged dark leather texture on the frame, Gothic-Chinese ornamental fusion style, menacing and corrupted feeling, 256x384, PNG with full transparency in center and outside frame
```

### 3.4 警长徽章

```
Detailed golden sheriff star badge, 6-pointed star design with a wolf's head engraving in the center circle, ornate filigree around the star points, metallic gold material with aged patina, a small crescent moon gem inset at top point, chain attachment at top for wearing, dramatic lighting showing metallic reflections, game UI collectible item, 256x256, PNG transparent background
```

### 3.5 技能图标组（128x128 each，透明背景）

**狼刀：**
```
Game icon: three diagonal wolf claw slash marks glowing blood-red, fresh wound appearance with dark blood droplets spraying, slight motion blur suggesting speed, dark smoky background particles, stylized flat design with 3D depth and glow effects, 128x128, transparent background
```

**预言之眼：**
```
Game icon: a mystical third eye with purple iris and golden sclera, radiating purple divination light rays, celestial rune circle around it, all-seeing magical eye, stylized flat design with magical glow effects, 128x128, transparent background
```

**解药瓶：**
```
Game icon: a round-bottom glass potion flask with glowing emerald green liquid inside, golden cork stopper with wax seal, healing sparkles and small leaf particles rising from the bottle, stylized flat design with magical glow, 128x128, transparent background
```

**毒药瓶：**
```
Game icon: a skull-shaped glass vial with bubbling dark purple-black liquid, cork stopper with purple wax, toxic green vapor and tiny skull shapes rising from the vial, stylized flat design with ominous glow, 128x128, transparent background
```

**弩箭：**
```
Game icon: a single silver crossbow bolt in flight, metallic gleam on the arrowhead, speed motion lines behind, slight red-hot glow at tip, feathered fletching in white, stylized flat design with motion effects, 128x128, transparent background
```

**投票票据：**
```
Game icon: a folded paper ballot being dropped into a wooden ballot box, the paper glowing with golden light of justice, wooden box with iron lock visible, stylized flat design with warm glow, 128x128, transparent background
```

**警徽：**
```
Game icon: a golden six-pointed sheriff star, polished metallic surface with bright reflection, small wolf engraving in center, radiating authority golden light, stylized flat design with metallic sheen, 128x128, transparent background
```

**自爆：**
```
Game icon: a dramatic explosion with wolf silhouette at center being torn apart, red and orange fire burst, debris flying outward, dark smoke ring, destructive violent energy, stylized flat design with particle effects, 128x128, transparent background
```

---

## 四、动画效果（纯代码实现，无需图片素材）

所有游戏内动画由 CSS Animation + Framer Motion 在前端实现，60FPS 矢量渲染，不需要生成任何图片。

| 效果 | 代码实现方式 | 触发时机 | 配合音效 |
|------|-------------|----------|----------|
| 狼刀攻击 | 3 条红色 `clip-path` 斜线依次滑入 + `transform: translate` 屏幕微震 | `wolf_target_selected` | `sfx_wolf_kill.mp3` |
| 毒药效果 | 紫色 `radial-gradient` 从中心扩散 + 多个紫色圆点 div 上升漂浮 | `witch_used_poison` | `sfx_poison.mp3` |
| 解药效果 | 绿色光点粒子（20个 div）螺旋上升 + 中心暖黄 `box-shadow` 脉冲 | `witch_used_antidote` | `sfx_antidote.mp3` |
| 预言查验 | 紫色圆环 `border` 缩放 + 水平扫描线（`linear-gradient` 平移） | `seer_checked` | `sfx_seer_check.mp3` |
| 猎人开枪 | 白色线条从左射向目标 + 目标处圆环 `scale` 冲击波 | `hunter_shot` | `sfx_hunter_shoot.mp3` |
| 死亡碎裂 | 卡片克隆为 6-9 个 `clip-path` 碎片 + 各自随机方向 `translate` + `opacity` 消失 | `player_died` | 无 |
| 投票飘落 | 8-12 个纸片 div 从上方随机位置旋转下落（`rotate` + `translateY`） | `vote_resolved` | `sfx_vote_result.mp3` |
| 胜利庆典 | 多点（5-8个）径向金色爆炸（`scale` + `opacity`）+ 粒子雨下落 | `game_ended` | `sfx_victory_*.mp3` |
| 昼夜切换 | 背景容器 `background` 渐变色 `transition: 2s` | phase 变化 | `sfx_night_fall/dawn.mp3` |
| 行动高亮 | 卡片 `ring-2 ring-yellow-400` + `animate-pulse` + `scale-110` | 当前行动角色 | 无 |

---

## 五、音效素材

### 5.1 阶段转换

**天黑（夜晚开始）— 3秒**
```
Atmospheric sound design: distant lone wolf howl echoing across mountains, crickets chirping fading out, heavy wooden door creaking shut, ominous deep bass drone fading in, wind through bare tree branches, 3 seconds, dark horror game ambience, high quality stereo, 44.1kHz
```

**天亮（白天开始）— 3秒**
```
Atmospheric sound design: rooster crowing at dawn, multiple birds beginning to chirp, gentle morning breeze, church bell (single toll) in distance, warm hopeful undertone but with lingering tension, wood fire crackling softly, 3 seconds, medieval village morning, high quality stereo, 44.1kHz
```

### 5.2 技能音效

**狼刀 — 1.5秒**
```
Sound effect: violent triple slash - three rapid swooshing cuts through air followed by wet flesh impact, wolf snarl/growl underlying, dark reverb tail, visceral and terrifying, 1.5 seconds, horror game combat SFX, high quality
```

**预言家查验 — 2秒**
```
Sound effect: mystical divination reveal - ethereal glass wind chime ascending, crystal ball resonance humming, magical whoosh of revealing light, then either warm angelic chord (good) or dissonant dark chord (wolf), 2 seconds, fantasy magic SFX, high quality
```

**女巫解药 — 2秒**
```
Sound effect: healing potion usage - glass cork pop, liquid pouring with magical shimmer, ascending warm bell tones, sparkle particles sound like tiny chimes, breath of life gasp at end, warm and relieving, 2 seconds, fantasy healing SFX, high quality
```

**女巫毒药 — 2秒**
```
Sound effect: poison application - glass cork pop (darker tone), thick liquid bubbling, hissing toxic gas release, victim choking gasp, descending dissonant tones, sinister and fatal, 2 seconds, dark fantasy SFX, high quality
```

**猎人开枪 — 1.5秒**
```
Sound effect: crossbow firing - taut string release twang, bolt whistling through air at high speed, solid impact thud into target, wood splintering, brief echo in village square, dramatic and final, 1.5 seconds, medieval ranged weapon SFX, high quality
```

**狼人自爆 — 2秒**
```
Sound effect: werewolf self-destruction - building wolf growl into full howl, transformation cracking bones, explosive burst of dark energy, shattering glass, deep boom with long reverb, scattered debris falling, shocking and violent, 2 seconds, dark fantasy explosion SFX, high quality
```

**投票定票 — 1.5秒**
```
Sound effect: decisive vote result - crowd murmuring building, papers shuffling, then silence, heavy wooden gavel strike (single), crowd gasping reaction, tense resonant echo, 1.5 seconds, courtroom drama SFX, high quality
```

**放逐宣告 — 2秒**
```
Sound effect: exile pronouncement - dramatic orchestral hit, heavy iron chains rattling, crowd jeering briefly, massive wooden gate slamming shut, final gong reverberating into silence, 2 seconds, epic drama SFX, high quality
```

**警长当选 — 2秒**
```
Sound effect: sheriff election fanfare - brief triumphant brass fanfare (3 notes ascending), metallic badge pinning click, crowd brief polite applause, authority drum roll ending in single snare hit, 2 seconds, ceremony SFX, high quality
```

### 5.3 结果音效

**好人胜利 — 4秒**
```
Sound effect: heroes victory - triumphant full orchestral fanfare in major key, French horns leading, strings swelling, crowd cheering and clapping, church bells ringing joyfully, ascending to brilliant climax, hopeful and relieving, 4 seconds, epic game victory SFX, cinematic quality
```

**狼人胜利 — 4秒**
```
Sound effect: wolves victory - ominous orchestral hit in minor key, multiple wolves howling in harmony, thunder crack, low brass doom chords, sinister string tremolo, wind howling through ruins, descending into dark silence, dreadful and final, 4 seconds, dark epic game victory SFX, cinematic quality
```

---

## 六、背景音乐 BGM（循环）

### 6.1 夜晚阶段 — 30秒无缝循环

```
Dark ambient background music, 30 seconds seamless loop, tempo 60 BPM, key of D minor. Instruments: low cello drone, sparse haunting piano notes (high register), one distant wolf howl at 15s mark, subtle heartbeat bass drum (pp), ethereal female voice humming. Must start and end on same note/chord for perfect loop. Mysterious dangerous suspenseful mood. Cinematic game soundtrack, orchestral + ambient hybrid.
```

### 6.2 白天讨论 — 30秒无缝循环

```
Tense discussion background music, 30 seconds seamless loop, tempo 90 BPM, key of A minor. Instruments: pizzicato strings repeating motif, light frame drum, guzheng sparse melodic fragments, low clarinet. Suspicious analytical mood, medieval tavern meets courtroom. Must loop seamlessly - same beat position at start and end. Cinematic game soundtrack.
```

### 6.3 投票紧张 — 20秒无缝循环

```
Intense countdown background music, 20 seconds seamless loop, tempo 110 BPM steady, key of E minor. Instruments: driving string ostinato, ticking clock percussion, brass staccato stabs, snare drum pattern, heartbeat bass. Time pressure life-or-death mood. Short tight loop, same rhythmic position at start and end. Cinematic game soundtrack.
```

### 6.4 警长竞选 — 30秒无缝循环

```
Dramatic campaign background music, 30 seconds seamless loop, tempo 100 BPM, key of G minor. Instruments: bold brass authority theme, military snare, competitive string runs, Chinese erhu Eastern flavor. Competitive political dramatic mood. Must loop seamlessly. Cinematic game soundtrack.
```

### 6.5 好人胜利 — 15秒（带淡出）

```
Short victory fanfare, 15 seconds with fade out, tempo 120 BPM, key of D major. Structure: 0-5s explosive triumphant brass and strings climax, 5-10s warm hopeful melody (solo violin), 10-15s gentle fade with flute and birds. Heroic relieving dawn-breaks mood. Cinematic quality.
```

### 6.6 狼人胜利 — 15秒（带淡出）

```
Short dark victory sting, 15 seconds with fade out, tempo 80 BPM, key of D minor. Structure: 0-5s ominous orchestral hit with wolf howl, 5-10s sinister low brass march, 10-15s fade to lone wolf howl in silence. Dreadful powerful final mood. Cinematic quality.
```

---

## 七、游戏世界观（生成素材时的上下文参考）

### 世界观文档

```
世界观："月牙村"——一个融合中世纪欧洲哥特风格与中国古代乡村的架空村庄。

地理：位于群山环绕的月牙形山谷中，因此得名。村庄中央是一棵百年古树下的圆形石桌，是村民集会的场所。

历史：三百年前，一位旅行的术士带来了狼人诅咒。每逢满月，被诅咒者会在夜间化为狼形猎杀同胞，白天恢复人形混迹于村民之中。

守护者：
- 预言家：古树的守护者，通过水晶球感知狼人的气息
- 女巫：山中隐居的药师，掌握解药（逆转死亡）和毒药（结束生命）
- 猎人：前朝退伍军人，誓死保卫村庄，以弩为武器
- 白痴：天真的傻子，因为太过无害甚至狼人都不屑于吃他（翻牌免死）

规则：村民必须在白天集会中通过投票放逐狼人。如果所有神职死亡（屠神）或所有平民死亡（屠民），狼人获胜。如果所有狼人被放逐或击杀，好人获胜。

美术风格关键词：暗黑哥特, 中国古风, 满月, 迷雾, 灯笼, 圆桌, 飞檐, 尖顶, 血月, 水墨元素, 烛光, 星辰, 暗色调为主辅以金色正义光芒
```

### Loading 画面

```
A mysterious ornate tarot card back design for a werewolf game loading screen: centered composition featuring a howling wolf silhouette against a crescent moon, surrounded by an intricate circle of 12 rune symbols representing each player seat, ornate border with intertwining Gothic thorny vines and Chinese cloud scroll patterns, four corner elements - crystal ball (top-left), potion bottle (top-right), crossbow bolt (bottom-left), sheriff star (bottom-right), color scheme of deep midnight blue background with antique gold linework and blood-red accent dots, aged parchment texture, mystical and foreboding atmosphere, vertical orientation, game card back design, 1080x1920
```

### 游戏 Logo

```
Game logo design for "LycanTUI" (werewolf AI game): stylized text where the "L" transforms into a wolf's claw reaching upward, the "y" has a crescent moon as its descender dot, "TUI" in bold Gothic-Chinese fusion calligraphy, metallic dark iron texture for main letters with blood-red accent on the claw, subtle golden glow around "TUI" letters, a faint full moon circle behind the entire wordmark, clean design suitable for game title screen, horizontal layout, 1920x480, transparent background
```

---

## 八、文件组织结构

```
desktop/public/assets/
├── avatars/                        # 角色立绘（每人4状态）
│   ├── wolf_01_normal.png
│   ├── wolf_01_speaking.png
│   ├── wolf_01_dead.png
│   ├── wolf_01_accused.png
│   ├── wolf_02_normal.png ~ wolf_02_accused.png
│   ├── wolf_03_normal.png ~ wolf_03_accused.png
│   ├── wolf_04_normal.png ~ wolf_04_accused.png
│   ├── seer_normal.png
│   ├── seer_speaking.png
│   ├── seer_dead.png
│   ├── seer_accused.png
│   ├── witch_normal.png
│   ├── witch_speaking.png
│   ├── witch_antidote.png          # 使用解药特写
│   ├── witch_poison.png            # 使用毒药特写
│   ├── witch_dead.png
│   ├── hunter_normal.png
│   ├── hunter_speaking.png
│   ├── hunter_shooting.png         # 开枪特写
│   ├── hunter_dead.png
│   ├── idiot_normal.png
│   ├── idiot_speaking.png
│   ├── idiot_reveal.png            # 翻牌特写
│   ├── idiot_dead.png
│   ├── villager_01_normal.png ~ villager_01_dead.png
│   ├── villager_02_normal.png ~ villager_02_dead.png
│   ├── villager_03_normal.png ~ villager_03_dead.png
│   └── villager_04_normal.png ~ villager_04_dead.png
├── backgrounds/                    # 场景背景（1920x1080）
│   ├── night_village.jpg           # 夜晚村庄全景
│   ├── night_wolf_view.jpg         # 狼人视角
│   ├── day_meeting.jpg             # 白天集会
│   ├── day_execution.jpg           # 投票处刑场
│   ├── dawn_transition.jpg         # 黎明过渡
│   ├── victory_good.jpg            # 好人胜利终景
│   └── victory_wolf.jpg            # 狼人胜利终景
├── ui/                             # UI 元素
│   ├── table_top.png               # 圆桌俯视
│   ├── frame_good.png              # 好人卡片边框
│   ├── frame_wolf.png              # 狼人卡片边框
│   ├── badge_sheriff.png           # 警长徽章
│   ├── loading_card.png            # Loading 画面
│   ├── logo.png                    # 游戏 Logo
│   └── icons/                      # 技能图标
│       ├── claw_slash.png
│       ├── seer_eye.png
│       ├── antidote.png
│       ├── poison.png
│       ├── crossbow_bolt.png
│       ├── ballot_vote.png
│       ├── sheriff_star.png
│       └── self_destruct.png
│   # 动画效果由代码实现，无需图片文件
├── sfx/                            # 音效
│   ├── phase_night.mp3             # 天黑 3s
│   ├── phase_dawn.mp3              # 天亮 3s
│   ├── skill_wolf_kill.mp3         # 狼刀 1.5s
│   ├── skill_seer_check.mp3        # 查验 2s
│   ├── skill_antidote.mp3          # 解药 2s
│   ├── skill_poison.mp3            # 毒药 2s
│   ├── skill_hunter_shoot.mp3      # 开枪 1.5s
│   ├── skill_self_destruct.mp3     # 自爆 2s
│   ├── vote_result.mp3             # 投票定票 1.5s
│   ├── exile.mp3                   # 放逐 2s
│   ├── sheriff_elected.mp3         # 警长当选 2s
│   ├── victory_good.mp3            # 好人胜利 4s
│   └── victory_wolf.mp3            # 狼人胜利 4s
└── bgm/                            # 背景音乐
    ├── night_loop.mp3              # 夜晚 120s 循环
    ├── day_discussion.mp3          # 讨论 120s 循环
    ├── vote_tension.mp3            # 投票 60s 循环
    ├── sheriff_campaign.mp3        # 竞选 90s 循环
    ├── victory_good.mp3            # 好人胜利 30s
    └── victory_wolf.mp3            # 狼人胜利 30s
```

---

## 九、生成工具推荐

| 素材类型 | 推荐工具 | 参数建议 |
|----------|----------|----------|
| 角色立绘 | Midjourney v6 | `--style raw --ar 2:3 --s 250` |
| 角色立绘（一致性） | Midjourney + `--cref` | 用第一张 Normal 作为 character reference |
| 背景图 | Midjourney v6 | `--ar 16:9 --s 500 --quality 2` |
| UI 图标 | DALL-E 3 / Midjourney | 方形 `--ar 1:1`，后用 Rembg 去背 |
| Sprite Sheet | Stable Diffusion + ControlNet | AnimateDiff 插件生成帧序列 |
| 音效 | ElevenLabs SFX / Stable Audio | 指定精确时长 |
| BGM | Suno v4 / Udio | 指定 BPM、调性、循环点 |
| 去背/抠图 | Rembg / Remove.bg | 批量处理角色立绘 |
| 放大/超分 | Real-ESRGAN | 4x 放大后裁切 |

### Midjourney 批量生成技巧

```
1. 先生成一个角色的 Normal 状态
2. 用 --cref [Normal图片URL] 保持角色一致性
3. 修改提示词中的表情/动作/光线生成其他状态
4. 使用 --seed 固定随机种子确保同批次风格统一
```
