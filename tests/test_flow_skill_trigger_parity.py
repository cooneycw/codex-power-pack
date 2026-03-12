from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / ".claude" / "commands" / "flow"
PROMPT_DIR = ROOT / ".codex" / "prompts" / "flow"
SKILLS_DIR = ROOT / ".codex" / "skills"


def _source_commands() -> set[str]:
    return {path.stem for path in SOURCE_DIR.glob("*.md")}


def _target_prompts() -> set[str]:
    return {path.stem for path in PROMPT_DIR.glob("*.md")}


def test_flow_prompt_trigger_parity_with_source_commands() -> None:
    assert _target_prompts() == _source_commands()


def test_every_flow_prompt_has_backing_skill_package() -> None:
    for command in sorted(_source_commands()):
        trigger = f"/flow:{command}"
        skill_name = f"flow-{command}"

        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        agent_yaml = SKILLS_DIR / skill_name / "agents" / "openai.yaml"
        prompt_md = PROMPT_DIR / f"{command}.md"

        assert skill_md.exists(), f"Missing skill file for {trigger}: {skill_md}"
        assert agent_yaml.exists(), f"Missing agents metadata for {trigger}: {agent_yaml}"

        prompt_text = prompt_md.read_text()
        skill_text = skill_md.read_text()

        assert f"Backing skill: `{skill_name}`" in prompt_text
        assert trigger in skill_text
        assert f".codex/prompts/flow/{command}.md" in skill_text
