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
| 角色立绘（51张） | 200-400KB | ~15MB |
| 场景背景（7张） | 500KB-1MB | ~5MB |
| UI 元素（11个） | 50-200KB | ~1.5MB |
| 动画效果 | 纯代码，0KB | 0 |
| 音效（13个） | 50-150KB | ~1.5MB |
| BGM（6首，短循环 OGG） | 400-600KB | ~3MB |
| **总计** | | **~26MB** |

---

## 素材文件名清单（完整）

生成素材后按以下文件名放入 `desktop/public/assets/` 目录，前端代码会直接引用这些路径。

### 角色立绘 — `avatars/`

| 座位 | 角色 | 文件名 |
|------|------|--------|
| 1 | 狼人A 头狼 | `wolf_01_normal.png` `wolf_01_speaking.png` `wolf_01_dead.png` `wolf_01_accused.png` |
| 2 | 狼人B 潜伏 | `wolf_02_normal.png` `wolf_02_speaking.png` `wolf_02_dead.png` `wolf_02_accused.png` |
| 3 | 狼人C 暴徒 | `wolf_03_normal.png` `wolf_03_speaking.png` `wolf_03_dead.png` `wolf_03_accused.png` |
| 4 | 狼人D 军师 | `wolf_04_normal.png` `wolf_04_speaking.png` `wolf_04_dead.png` `wolf_04_accused.png` |
| 5 | 预言家 | `seer_normal.png` `seer_speaking.png` `seer_dead.png` `seer_accused.png` |
| 6 | 女巫 | `witch_normal.png` `witch_speaking.png` `witch_antidote.png` `witch_poison.png` `witch_dead.png` |
| 7 | 猎人 | `hunter_normal.png` `hunter_speaking.png` `hunter_shooting.png` `hunter_dead.png` |
| 8 | 白痴 | `idiot_normal.png` `idiot_speaking.png` `idiot_reveal.png` `idiot_dead.png` |
| 9 | 村民A 老村长 | `villager_01_normal.png` `villager_01_speaking.png` `villager_01_dead.png` |
| 10 | 村民B 农夫 | `villager_02_normal.png` `villager_02_speaking.png` `villager_02_dead.png` |
| 11 | 村民C 少女 | `villager_03_normal.png` `villager_03_speaking.png` `villager_03_dead.png` |
| 12 | 村民D 商人 | `villager_04_normal.png` `villager_04_speaking.png` `villager_04_dead.png` |

**总计：51 张**（特殊角色多 1-2 个状态）

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

所有图像素材在提示词前加上以下统一风格前缀：

```
Style: dark gothic fantasy mixed with ancient Chinese aesthetics, semi-realistic digital painting, cinematic lighting, rich detail, game art quality. Color palette: deep midnight blue, dark purple, blood crimson, with gold accents for justice/holy elements. Architecture blends Gothic pointed arches with Chinese curved eaves. Characters are East Asian with fantasy elements.
```

---

## 一、角色立绘（12 个座位，每人 4 个状态）

每个角色需要以下 4 种状态的立绘：
- **Normal** — 默认状态，平静/警惕表情
- **Speaking** — 发言中，张嘴/手势，眼神坚定
- **Dead** — 死亡状态，灰度/闭眼/伤痕
- **Accused** — 被指控时，紧张/愤怒/辩解

尺寸统一：512x768，半身竖版，透明背景

---

### 1.1 狼人 A — 头狼（男，30岁，领袖气质）

**外貌设定：** 高大东亚男性，锐利琥珀色眼睛，鬓角有灰色短鬓，下巴有短胡茬，穿黑色皮毛大衣，内搭暗红衬衫，左耳有银色狼牙耳坠，气场强大但白天伪装得体。

**Normal:**
```
Half-body portrait of a werewolf pack leader in human disguise, tall East Asian male age 30, sharp amber eyes with vertical pupils barely visible, gray-streaked temples, short stubble on jaw, wearing a black fur-lined leather coat over dark red shirt, silver wolf-fang earring on left ear, arms crossed confidently, composed predatory expression, moonlit from upper left, dark smoky background, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a werewolf pack leader giving a speech during village meeting, tall East Asian male age 30, sharp amber eyes intense and focused, gray-streaked temples, short stubble, black fur-lined coat over dark red shirt, silver wolf-fang earring, right hand raised in persuasive gesture, mouth open mid-speech, confident commanding expression, warm candlelight from left, village hall background blurred, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead werewolf leader, tall East Asian male age 30, eyes closed peacefully, gray-streaked temples, face partially transformed showing wolf features - elongated canines visible, fur patches on cheekbones, black coat torn revealing claw wounds on chest, silver wolf-fang earring now tarnished, desaturated cold blue color grading, moonlight from above, mist rising, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Accused:**
```
Half-body portrait of a werewolf leader being accused in village meeting, tall East Asian male age 30, amber eyes flashing with barely contained fury, jaw clenched, gray-streaked temples, short stubble, black fur-lined coat, silver wolf-fang earring, fists clenched at sides, defensive aggressive posture, shadow of wolf ears flickering behind him, dramatic torchlight from below creating harsh shadows, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

### 1.2 狼人 B — 潜伏者（女，25岁，伪装无辜）

**外貌设定：** 娇小东亚女性，圆脸大眼看似无害，长黑发用红色发带束起，穿暗红色传统改良旗袍，袖口有暗纹狼爪图案，笑起来时犬齿微微尖锐。

**Normal:**
```
Half-body portrait of a disguised female werewolf, petite East Asian woman age 25, round face with large seemingly innocent eyes, long black hair tied with a crimson ribbon, wearing a dark red modified qipao with subtle wolf-claw embroidery on sleeve cuffs, slightly pointed canines visible in a small closed-mouth smile, hands folded demurely in front, soft moonlight from right, dark background with faint red mist, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a disguised female werewolf speaking at village gathering, petite East Asian woman age 25, large eyes wide with feigned concern, long black hair with crimson ribbon, dark red qipao, one hand touching her chest in a "who me?" gesture, mouth open with slightly visible pointed canines, worried innocent expression that's subtly too perfect, warm interior candlelight, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead female werewolf with true form partially revealed, petite East Asian woman age 25, eyes half-open with amber glow fading, hair loose and wild revealing wolf-like ears, dark red qipao torn at shoulders showing fur patches, crimson ribbon fallen around neck like a wound, one clawed hand visible, desaturated blue-gray tones, cold moonlight, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Accused:**
```
Half-body portrait of a female werewolf being accused and dropping her innocent act, petite East Asian woman age 25, eyes narrowed with predatory glint breaking through the innocent facade, lips pulled back slightly showing pointed canines, hair partially loose from crimson ribbon, dark red qipao, one hand gripping the table edge with slightly elongated nails, dramatic split lighting - warm torch from left cold moon from right, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

### 1.3 狼人 C — 暴徒（男，35岁，肌肉型）

**外貌设定：** 魁梧东亚男性，光头，脸上有三道平行旧疤（像爪痕），穿破旧黑色皮甲，露出布满伤疤的手臂，血红色瞳孔，性格暴躁易怒。

**Normal:**
```
Half-body portrait of a brutal werewolf enforcer in human form, burly East Asian male age 35, shaved head, three parallel old scars across left cheek like claw marks, blood-red irises, wearing worn black leather vest over bare scarred muscular arms, heavy jaw set in a perpetual scowl, thick neck with a leather cord necklace bearing a wolf tooth, intimidating posture, harsh moonlight from above casting deep shadows, dark background, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a brutal werewolf enforcer arguing loudly at village meeting, burly East Asian male age 35, shaved head, three claw scars on cheek, blood-red eyes wide with anger, mouth open shouting, veins visible on neck and temple, black leather vest, scarred arms with one fist raised threateningly, pointing aggressively at someone off-screen, dramatic warm torchlight from below, dust particles in air, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead brutal werewolf, burly East Asian male age 35, shaved head, claw scars on cheek, eyes open and glazed with fading red glow, mouth slightly open showing elongated fangs, black leather vest with crossbow bolt embedded in chest, arms limp with claws partially emerged, pool of dark blood reflection below, cold blue desaturated tones, overhead moonlight, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Accused:**
```
Half-body portrait of a brutal werewolf being cornered and accused, burly East Asian male age 35, shaved head, claw scars on cheek, blood-red eyes blazing with rage, baring teeth showing sharp canines, black leather vest, scarred arms tense with veins popping, crouched slightly like about to lunge, shadow on wall behind him shows monstrous wolf silhouette, red-tinted dramatic lighting, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

### 1.4 狼人 D — 军师（男，40岁，书生型）

**外貌设定：** 瘦高东亚男性，戴圆框眼镜，梳理整齐的黑发，穿深色学者长袍（类似明代文人服），手持折扇，表情冷静从容，狼性隐藏在温文尔雅之下。

**Normal:**
```
Half-body portrait of a cunning werewolf strategist in human form, thin tall East Asian male age 40, round wire-frame glasses, neatly combed black hair in a traditional topknot, wearing dark navy scholar's changshan robe with subtle silver thread patterns, holding a folded black fan in right hand, calm calculating half-smile, one eyebrow slightly raised, composed intellectual demeanor, soft candlelight from left side, study room with bookshelves blurred in background, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a werewolf strategist delivering a logical argument at village meeting, thin tall East Asian male age 40, round glasses reflecting firelight, neat topknot, dark navy scholar's robe, fan held open in left hand used for emphasis, right hand index finger raised making a point, mouth open in articulate speech, confident knowing expression, eyes sharp behind glasses, warm study lamp lighting from below-left, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead werewolf strategist, thin tall East Asian male age 40, round glasses cracked and askew on face, hair fallen loose from topknot, dark navy robe with spreading bloodstain on chest, folded fan fallen nearby, eyes closed with a final knowing smirk frozen on face, subtle wolf shadow dissolving behind him, cool blue-gray desaturated tones, overhead dim light, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Accused:**
```
Half-body portrait of a werewolf strategist calmly facing accusation, thin tall East Asian male age 40, round glasses pushed up on nose, neat topknot slightly loosened, dark navy scholar's robe, fan snapped shut held like a weapon, eyes cold and calculating behind glasses, thin smile that doesn't reach eyes, perfectly composed exterior but shadow behind him warps into wolf shape, dramatic side lighting creating sharp contrasts, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

### 1.5 预言家（女，60岁，神秘老妇）

**外貌设定：** 年迈东亚女性，花白长发披散，深邃紫色瞳孔（通灵之眼），额头有第三只眼纹身（半睁状），穿靛蓝色星辰纹道袍，手持水晶球，周身有淡紫色灵光。

**Normal:**
```
Half-body portrait of a village seer / fortune teller, elderly East Asian woman age 60, long silver-white hair flowing freely, deep violet glowing eyes that seem to look through reality, a half-open third eye tattoo on forehead in indigo ink, wearing flowing indigo Taoist robes embroidered with constellation patterns in silver thread, holding a palm-sized crystal orb emanating soft purple light between both hands, serene knowing expression with slight sadness, purple mystical aura around shoulders, moonlight from behind creating silver rim lighting, dark starfield background, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking (revealing truth):**
```
Half-body portrait of a village seer revealing her divination results, elderly East Asian woman age 60, silver-white hair blowing in supernatural wind, violet eyes blazing with inner light, third eye tattoo on forehead now fully open and glowing bright purple, indigo constellation robes billowing, crystal orb held high in right hand emanating beam of revealing light, left hand pointing forward accusingly, mouth open declaring truth with authority, dramatic purple and white lighting radiating from the crystal, shocked villagers' shadows in background, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead village seer, elderly East Asian woman age 60, silver-white hair spread around her like a halo, violet eyes dimmed to gray and half-closed, third eye tattoo faded and cracked, indigo constellation robes with wolf claw tears across chest, crystal orb fallen and cracked beside her with last purple spark fading, peaceful accepting expression, surrounded by dissipating constellation particles, cold silver-blue lighting from above, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Accused (defending truth):**
```
Half-body portrait of a village seer being doubted and passionately defending her divination, elderly East Asian woman age 60, silver-white hair wild and crackling with static energy, violet eyes intense and unwavering, third eye tattoo pulsing with light, indigo robes swirling, crystal orb clutched protectively to chest with both hands, expression of righteous determination mixed with frustration, purple energy arcing around her like lightning, dramatic underlighting from the orb, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

### 1.6 女巫（女，28岁，神秘药师）

**外貌设定：** 东亚年轻女性，异色瞳（左眼翠绿=解药，右眼暗紫=毒药），黑色短发斜刘海遮住右眼，穿深翠色药师长袍，腰间挂着两个小瓶（绿色解药+紫色毒药），周身有药草和烟雾环绕。

**Normal:**
```
Half-body portrait of a village witch / alchemist, East Asian young woman age 28, heterochromia eyes - left eye vivid emerald green right eye deep amethyst purple, black short asymmetrical hair with side-swept bangs partially covering right eye, wearing deep emerald apothecary robes with leather belt, two small potion bottles hanging from belt - one glowing green one glowing purple, dried herbs tucked in belt pouch, mysterious slight smile, surrounded by wisps of herbal smoke, soft green-purple dual lighting from the potions, dark laboratory background with shelves of bottles, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a witch speaking carefully at village meeting, East Asian young woman age 28, heterochromia eyes both visible - green left scanning the crowd purple right narrowed, black asymmetrical hair pushed back, emerald robes, holding the green antidote bottle up in demonstration, mouth open explaining with measured words, cautious guarded expression, warm candlelight mixing with green potion glow on her face, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Using Antidote:**
```
Half-body portrait of a witch using her antidote to save someone, East Asian young woman age 28, green left eye glowing intensely, black hair blown back by magical wind, emerald robes billowing, both hands holding the uncorked green potion bottle above a dying patient (implied below frame), golden-green healing light pouring from bottle, expression of fierce determination and compassion, sparkling particles rising, warm green magical lighting, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Using Poison:**
```
Half-body portrait of a witch using her poison on a target, East Asian young woman age 28, purple right eye glowing ominously, left eye hidden behind black bangs, emerald robes in shadow, holding the uncorked purple poison vial tilted and dripping, sinister satisfied expression, purple-black toxic smoke curling from the vial, toxic bubbles and skull-shaped vapor, cold purple backlighting, dark ominous atmosphere, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead witch, East Asian young woman age 28, both heterochromia eyes dimmed and half-closed, black hair fallen over face, emerald robes with claw marks, both potion bottles shattered at her belt with green and purple liquids mixing and evaporating, expression of quiet regret, green and purple particles dissipating around her, cold desaturated tones, dim overhead light, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

### 1.7 猎人（男，45岁，退伍老兵）

**外貌设定：** 中年东亚男性，方脸，左眼有眼罩（战斗旧伤），粗犷短发花白，穿棕色猎装背心+皮护臂，背上斜挎弩弓，脖子上戴银弹项链，浑身散发战场老兵的气息。

**Normal:**
```
Half-body portrait of a village hunter / veteran marksman, weathered East Asian male age 45, square jaw, leather eyepatch over left eye with scar extending above and below, grizzled short salt-and-pepper hair, wearing brown leather hunting vest with metal buckles over dark green tunic, leather arm guards on both forearms, crossbow strapped diagonally on back visible over right shoulder, silver bullet necklace on a leather cord, one good eye scanning alertly, veteran's calm confident posture, forest moonlight atmosphere, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a hunter veteran giving testimony at village meeting, weathered East Asian male age 45, eyepatch, square jaw set firm, grizzled hair, brown hunting vest, right hand slammed flat on table for emphasis, one good eye burning with conviction, mouth open speaking bluntly, crossbow on back, silver bullet necklace catching firelight, direct no-nonsense expression, warm torchlight from side, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Shooting (last stand):**
```
Half-body portrait of a hunter firing his crossbow as his final act, weathered East Asian male age 45, eyepatch, grizzled hair blown back by force, brown hunting vest with fresh wounds, crossbow in both hands aimed forward with bolt just released - motion blur on bolt, muzzle flash and smoke, one good eye locked on target with grim determination, silver bullet necklace flying from the recoil, dramatic action pose, speed lines and dust, warm-to-cold lighting transition, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead hunter veteran, weathered East Asian male age 45, eyepatch still on, one good eye closed peacefully, grizzled hair matted, brown hunting vest with wolf claw tears, crossbow fallen beside him with one last bolt still loaded, silver bullet necklace broken with bullets scattered, a final defiant expression frozen on face, cold blue desaturated tones, ground-level perspective, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

### 1.8 白痴（男，20岁，天真少年）

**外貌设定：** 年轻东亚男性，圆脸娃娃脸，乱蓬蓬的棕色头发上插着一朵野花，穿打了彩色补丁的简陋衣服，手里抱着一个木头小人偶，笑容纯真无忧，眼神有些呆萌。

**Normal:**
```
Half-body portrait of a village idiot / innocent fool, young East Asian male age 20, round baby face with rosy cheeks, messy brown hair with a small wildflower tucked behind ear, wearing simple patched clothes with mismatched colorful fabric patches - blue green yellow, hugging a small hand-carved wooden puppet doll to his chest, wide innocent smile showing slight gap in front teeth, slightly unfocused cheerful eyes, warm soft candlelight, simple cottage background blurred, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking (confused):**
```
Half-body portrait of a village idiot trying to speak at meeting but confused, young East Asian male age 20, round baby face, messy brown hair with wildflower, patched colorful clothes, wooden puppet held in one hand while other hand scratches head, mouth open in confused "uh" expression, eyes looking up trying to think, tilted head, innocent bewilderment, warm candlelight, villagers' blurred silhouettes around, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Revealing (flipping card):**
```
Half-body portrait of a village idiot triumphantly revealing his identity to survive exile, young East Asian male age 20, round face with a rare moment of clever grin, messy brown hair wildflower bouncing, patched clothes, holding up his "fool's card" identity token proudly in both hands above his head, wooden puppet tucked under arm, expression of childlike triumph and relief, golden light emanating from the revealed card, surprised gasps implied around him, dramatic reveal lighting, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead village idiot, young East Asian male age 20, round face now peaceful in eternal sleep, messy brown hair with wildflower wilting, patched colorful clothes now torn, wooden puppet fallen from limp hand, slight smile still on face as if dreaming, the innocence preserved even in death, warm but fading golden light from above like a farewell, desaturating to cool tones at edges, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

### 1.9 ~ 1.12 村民（4人，各有特点）

**村民 A — 老村长（男，70岁）**

外貌：白须长者，拄拐杖，穿素色麻布长衫，慈祥但忧虑。

**Normal:**
```
Half-body portrait of a village elder, East Asian elderly man age 70, long white beard and mustache, kind worried eyes with deep wrinkles, wearing plain beige hemp changshan robe, leaning on a gnarled wooden walking stick with both hands, slightly hunched posture of age but dignity intact, a jade pendant at neck, grandfatherly concerned expression, warm candlelight from a nearby hearth, simple village home background, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a village elder speaking with wisdom at meeting, East Asian elderly man age 70, white beard, one wrinkled hand raised palm-out in calming gesture, other hand on walking stick, eyes kind but firm, mouth open offering measured counsel, jade pendant glowing faintly, respected authority posture, warm interior lighting, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead village elder, East Asian elderly man age 70, white beard peaceful, eyes closed as if sleeping, hemp robe with minimal visible wound, walking stick fallen beside him, jade pendant cracked, a single tear dried on weathered cheek, expression of sorrow for his village, cold moonlight through window, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

**村民 B — 农夫（男，32岁）**

外貌：壮实庄稼汉，古铜肤色，穿粗布短褂，戴草帽（挂在背后），手上有老茧。

**Normal:**
```
Half-body portrait of a young farmer villager, sturdy East Asian male age 32, tanned bronze skin, honest open face, wearing rough cotton short jacket in earth brown, straw hat hanging on back by chin cord, calloused strong hands resting at sides, simple hemp belt with a small sickle tucked in, earnest straightforward expression, golden wheat-field sunset light, rural farm background blurred, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a farmer speaking earnestly at village meeting, sturdy East Asian male age 32, tanned face animated with honest passion, straw hat pushed back, rough cotton jacket, one calloused hand gesturing openly, mouth open speaking plainly from the heart, no guile in expression, warm torchlight, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead farmer, sturdy East Asian male age 32, tanned face now pale, eyes closed, rough cotton jacket with bloodstain on chest, straw hat fallen nearby, one calloused hand still clutching earth, sickle at belt unused, cold blue-gray morning light, dew on ground around him, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

**村民 C — 少女（女，18岁）**

外貌：温婉东亚少女，编了两条辫子，穿浅蓝色汉服衫裙，手提小灯笼，胆小但善良。

**Normal:**
```
Half-body portrait of a village girl, gentle East Asian young woman age 18, two braided pigtails tied with pale blue ribbons, soft kind face with worried doe eyes, wearing light blue simplified hanfu - cross-collar top and flowing skirt, holding a small paper lantern in both hands close to chest for comfort, shy timid posture with slight hunch of shoulders, warm lantern glow illuminating her face from below, misty evening village street background, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a village girl nervously speaking at meeting, gentle East Asian young woman age 18, braided pigtails, blue hanfu, lantern set on table, both hands fidgeting in her lap, mouth open speaking softly with visible nervousness, eyes darting between listeners, slight blush of embarrassment, trying to be brave despite fear, warm interior candlelight, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead village girl, gentle East Asian young woman age 18, braids loose and ribbons undone, blue hanfu with tear marks, paper lantern fallen and extinguished nearby, eyes closed with dried tear tracks on cheeks, peaceful innocent expression preserved, a single blue ribbon caught on the wind, cold moonlight with warm lantern afterglow fading, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

---

**村民 D — 商人（男，50岁）**

外貌：圆胖中年人，精明面相，穿锦缎商服，腰间挂算盘和钱袋，圆滑但胆小。

**Normal:**
```
Half-body portrait of a village merchant, plump East Asian middle-aged man age 50, round shrewd face with small calculating eyes, thin mustache, wearing brocade merchant robes in dark green and gold trim, a small abacus hanging from sash belt next to a money pouch, hands rubbing together nervously, trying to appear friendly but clearly self-interested, warm lamp-lit shop atmosphere, shelves with goods blurred behind, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Speaking:**
```
Half-body portrait of a merchant arguing to save himself at village meeting, plump East Asian male age 50, round face sweating, small eyes darting nervously, thin mustache twitching, brocade robes, one hand clutching money pouch protectively other hand waving dismissively, mouth open in rapid persuasion, self-preservation clear in expression, warm torchlight making his sweat glisten, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
```

**Dead:**
```
Half-body portrait of a dead merchant, plump East Asian male age 50, round face frozen in surprise, small eyes wide open, thin mustache, brocade robes disheveled, money pouch spilled with coins scattered around him, abacus broken, expression of disbelief that his wealth couldn't save him, cold harsh overhead light, semi-realistic digital painting, gothic-Chinese fantasy style, 512x768, transparent background
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
