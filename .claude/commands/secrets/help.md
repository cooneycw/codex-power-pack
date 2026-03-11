# Secrets Commands

Overview of all secrets management commands.

## Instructions

Display the following help information:

```
Secrets Management Commands

  /secrets:get [ID]        Get credentials (masked output)
  /secrets:set KEY VALUE   Set or update a secret value
  /secrets:delete KEY      Delete a secret key (with confirmation)
  /secrets:list            List all secret keys (values masked)
  /secrets:run -- CMD      Run command with secrets injected as env vars
  /secrets:validate        Validate credential configuration
  /secrets:ui              Launch web UI for secrets management
  /secrets:rotate KEY      Rotate a secret value
  /secrets:help            This help message

Tiered Architecture:
  Tier 0: .env in global config (~/.config/codex-power-pack/secrets/)
  Tier 1: Encrypted local store (optional, requires cryptography)
  Tier 2: AWS Secrets Manager (requires boto3 + AWS credentials)

CLI Usage:
  PYTHONPATH="$HOME/Projects/codex-power-pack/lib:$PYTHONPATH"
  python3 -m lib.creds <command> [options]

Configuration:
  Project-level: .codex/secrets.yml
  Audit log:     ~/.config/codex-power-pack/audit.log
  Secret store:  ~/.config/codex-power-pack/secrets/{project_id}/.env
```
