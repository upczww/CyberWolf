# Wolf Game Art Asset Manifest

Supplemental art resources added for the gothic storybook werewolf game.

## Avatars

- `avatars/variants/villager_01.png`
- `avatars/variants/villager_02.png`
- `avatars/variants/villager_03.png`
- `avatars/variants/wolf_01.png`
- `avatars/variants/wolf_02.png`

All avatar variants are `1024x1536` character cards with the same bottom nameplate alignment as the existing avatar cards.

## UI Status

Small transparent player-state overlays, all `256x256`:

- `ui/status/dead.png`
- `ui/status/exiled.png`
- `ui/status/poisoned.png`
- `ui/status/saved.png`
- `ui/status/selected.png`
- `ui/status/speaking.png`
- `ui/status/targeted.png`
- `ui/status/voted.png`
- `ui/status/waiting.png`

## Cards And Panels

- `ui/cards/button_parchment.png` - parchment button base, `520x180`
- `ui/cards/panel_parchment.png` - modal/panel base, `1024x640`
- `ui/cards/role_card_back.png` - hidden role card back, `1024x1536`
- `ui/cards/system_banner.png` - narrator/system banner, `1200x260`
- `ui/cards/unknown_avatar.png` - hidden identity avatar, `1024x1536`

## Seer Results

Transparent symbolic result stamps, both `640x420`:

- `ui/results/seer_result_good.png`
- `ui/results/seer_result_wolf.png`

## Vote

Transparent voting UI pieces, all `512x512`:

- `ui/vote/abstain_mark.png`
- `ui/vote/exile_stamp.png`
- `ui/vote/tie_mark.png`
- `ui/vote/vote_arrow.png`
- `ui/vote/vote_count_token.png`

## Action Effects

Transparent overlays, all `1024x1024`:

- `ui/effects/antidote_glow_overlay.png`
- `ui/effects/hunter_bolt_trail_overlay.png`
- `ui/effects/poison_smoke_overlay.png`
- `ui/effects/seer_eye_glow_overlay.png`
- `ui/effects/wolf_claw_overlay.png`

## Phase Banners

Blank phase banner backgrounds for app-rendered localized text, all `1400x360`:

- `ui/phases/phase_dawn.png`
- `ui/phases/phase_day_discussion.png`
- `ui/phases/phase_endgame.png`
- `ui/phases/phase_last_words.png`
- `ui/phases/phase_night.png`
- `ui/phases/phase_vote.png`

## Endgame

- `ui/endgame/alive_mark.png` - transparent alive mark, `640x640`
- `ui/endgame/dead_mark.png` - transparent dead mark, `640x640`
- `ui/endgame/defeat_overlay.png` - semi-transparent full-screen defeat overlay, `1920x1080`
- `ui/endgame/good_victory_badge.png` - transparent good team badge, `640x640`
- `ui/endgame/wolf_victory_badge.png` - transparent wolf team badge, `640x640`

## Audio

Procedural gothic storybook audio generated from `desktop/prompts_copy_ready_gothic_storybook_audio.md`.
The prompt file requests MP3/OGG, but the local environment has no ffmpeg encoder, so these are shipped as browser-playable `44.1kHz` stereo WAV files.

### SFX

- `sfx/phase_night.wav`
- `sfx/phase_dawn.wav`
- `sfx/skill_wolf_kill.wav`
- `sfx/skill_seer_check.wav`
- `sfx/skill_antidote.wav`
- `sfx/skill_poison.wav`
- `sfx/skill_hunter_shoot.wav`
- `sfx/skill_self_destruct.wav`
- `sfx/vote_result.wav`
- `sfx/exile.wav`
- `sfx/sheriff_elected.wav`
- `sfx/victory_good.wav`
- `sfx/victory_wolf.wav`

### BGM

- `bgm/night_loop.wav`
- `bgm/day_discussion.wav`
- `bgm/vote_tension.wav`
- `bgm/sheriff_campaign.wav`
- `bgm/victory_good.wav`
- `bgm/victory_wolf.wav`

## Previews

Preview contact sheets are outside the shipped asset tree:

- `C:\Work\wolf\previews\avatar_variants.jpg`
- `C:\Work\wolf\previews\new_ui_assets.jpg`
