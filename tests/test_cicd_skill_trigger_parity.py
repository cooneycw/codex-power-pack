from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT / ".codex" / "prompts" / "cicd"
SKILLS_DIR = ROOT / ".codex" / "skills"

CICD_COMMANDS = {
    "check",
    "container",
    "health",
    "help",
    "infra-discover",
    "infra-init",
    "infra-pipeline",
    "init",
    "pipeline",
    "smoke",
}

def _target_prompts() -> set[str]:
    return {path.stem for path in PROMPT_DIR.glob("*.md")}


def test_cicd_prompt_trigger_parity_with_source_commands() -> None:
    assert _target_prompts() == CICD_COMMANDS


def test_every_cicd_prompt_has_backing_skill_package() -> None:
    for command in sorted(CICD_COMMANDS):
        trigger = f"/cicd:{command}"
        skill_name = f"cicd-{command}"

        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        agent_yaml = SKILLS_DIR / skill_name / "agents" / "openai.yaml"
        prompt_md = PROMPT_DIR / f"{command}.md"

        assert skill_md.exists(), f"Missing skill file for {trigger}: {skill_md}"
        assert agent_yaml.exists(), f"Missing agents metadata for {trigger}: {agent_yaml}"

        prompt_text = prompt_md.read_text()
        skill_text = skill_md.read_text()

        assert f"Backing skill: `{skill_name}`" in prompt_text
        assert trigger in skill_text
        assert f".codex/prompts/cicd/{command}.md" in skill_text
