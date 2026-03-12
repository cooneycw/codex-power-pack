from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / ".codex" / "prompts" / "agents-md"
SKILLS_DIR = ROOT / ".codex" / "skills"

AGENTS_MD_COMMANDS = {"help", "lint"}


def _target_prompts() -> set[str]:
    return {path.stem for path in PROMPT_DIR.glob("*.md")}


def test_agents_md_prompt_trigger_parity() -> None:
    assert _target_prompts() == AGENTS_MD_COMMANDS


def test_every_agents_md_prompt_has_backing_skill_package() -> None:
    for command in sorted(AGENTS_MD_COMMANDS):
        trigger = f"/agents-md:{command}"
        skill_name = f"agents-md-{command}"

        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        agent_yaml = SKILLS_DIR / skill_name / "agents" / "openai.yaml"
        prompt_md = PROMPT_DIR / f"{command}.md"

        assert skill_md.exists(), f"Missing skill file for {trigger}: {skill_md}"
        assert agent_yaml.exists(), f"Missing agents metadata for {trigger}: {agent_yaml}"

        prompt_text = prompt_md.read_text()
        skill_text = skill_md.read_text()

        assert f"Backing skill: `{skill_name}`" in prompt_text
        assert trigger in skill_text
        assert f".codex/prompts/agents-md/{command}.md" in skill_text
