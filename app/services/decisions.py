from __future__ import annotations

from app.domain.actions import ProposedAction, ResolvedAction, ValidatedAction
from app.domain.config import RuntimeConfig
from app.domain.roles import Phase, Role
from app.domain.state import GameState, alive_player_ids, living_wolves
from app.services.llm import TOOL_REGISTRY, enabled_tools


def validate_tool_call(
    *,
    state: GameState,
    runtime: RuntimeConfig,
    actor_id: int,
    role: Role,
    phase: Phase,
    proposed: ProposedAction,
) -> ValidatedAction:
    errors: list[str] = []
    if proposed["tool_name"] not in TOOL_REGISTRY:
        errors.append("unknown tool")
    allowed = {tool["name"] for tool in enabled_tools(runtime, role, phase)}
    if proposed["tool_name"] not in allowed:
        errors.append("tool not enabled for actor/phase")

    args = dict(proposed["raw_args"])
    if "target_id" in args:
        target_id = args["target_id"]
        if target_id is not None:
            try:
                target_id = int(target_id)
                args["target_id"] = target_id
            except (ValueError, TypeError):
                errors.append("target_id is not a valid number")
                target_id = None
        if target_id is not None and target_id not in alive_player_ids(state):
            errors.append("target is not alive")
        if target_id is not None and proposed["tool_name"] == "wolf_kill_proposal" and target_id in living_wolves(state):
            errors.append("wolf cannot target teammate")
        if target_id is not None and proposed["tool_name"] in {"seer_check", "hunter_shoot"} and target_id == actor_id:
            errors.append("self target is not allowed")
        if target_id is not None and proposed["tool_name"] == "vote_target" and phase != Phase.SHERIFF_ELECTION and target_id == actor_id:
            errors.append("self target is not allowed")

    if proposed["tool_name"] == "witch_antidote":
        if args.get("use_antidote") and state["witch_antidote_used"]:
            errors.append("antidote already used")

    if proposed["tool_name"] == "witch_poison":
        poison_target = args.get("target_id")
        if poison_target is not None and state["witch_poison_used"]:
            errors.append("poison already used")
        if poison_target is not None and poison_target not in alive_player_ids(state):
            errors.append("poison target is not alive")
        if poison_target is not None and poison_target == actor_id:
            errors.append("witch cannot poison self")

    if proposed["tool_name"] == "public_speech":
        speech = str(args.get("public_speech", "")).strip()
        lowered = speech.lower()
        max_chars = runtime["prompt_profile"].get("max_public_speech_chars", 180)
        if not speech:
            errors.append("public speech is empty")
        elif len(speech) > max_chars:
            args["public_speech"] = speech[:max_chars]
        if "reasoning_content" in lowered or "internal_thought" in lowered:
            errors.append("public speech contains hidden thought marker")

    return ValidatedAction(
        actor_id=actor_id,
        phase=phase,
        action_type=proposed["tool_name"],
        args=args,
        is_valid=not errors,
        validation_errors=errors,
    )


def resolve_action(validated: ValidatedAction) -> ResolvedAction:
    return ResolvedAction(
        actor_id=validated["actor_id"],
        phase=validated["phase"],
        action_type=validated["action_type"],
        args=dict(validated["args"]),
        effects=[],
    )
