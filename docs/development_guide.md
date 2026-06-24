# Development Guide: GrowthScout AI

This guide is for developers and coding agents migrating specifications in this repository into operational code. Follow these rules to ensure compliance with the repository constitution.

---

## 1. Setting Up the Development Environment
Ensure `uv` is installed, then clone the repository:
```bash
# Sync dependencies
uv sync

# Install Google Agent Platform CLI
uv tool install google-agents-cli
```

---

## 2. Implementing an Agent
When creating or modifying agent files:
1.  **Do NOT edit prompts in source code**: Keep prompts in the `definition.yaml` file inside the agent's folder (e.g., [discovery_agent.yaml](file:///Users/ptech/Desktop/growthscout-ai/agents/discovery_agent.yaml)).
2.  **Define agent endpoints in Python**:
    ```python
    # Path: backend/app/agents/discovery.py
    # Example logic using Vertex AI ADK SDK
    from google.adk.agents import Agent
    import yaml

    def load_agent_definition(path: str) -> dict:
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def get_discovery_agent(config_path: str) -> Agent:
        spec = load_agent_definition(config_path)
        return Agent(
            name=spec["agent"]["name"],
            model=spec["agent"]["model"],
            instruction=spec["agent"]["system_instruction"],
            # Bind tools from the MCP schemas
        )
    ```

---

## 3. Implementing a Reusable Skill
To create a new skill package (e.g., `seo-audit`):
1.  Write a clear markdown specification in `skills/seo-audit/SKILL.md` declaring the interface.
2.  Create unit test cases in `skills/seo-audit/evaluation_cases.json`.
3.  Bind the skill to the target agent manifest:
    ```yaml
    # Path: agents/agents-cli-manifest.yaml
    agent:
      name: "website_analysis_agent"
      skills:
        - "skills/seo-audit"
    ```

---

## 4. Running the Quality Flywheel (Evaluation)
Before submitting a pull request, you must run local evaluations to verify accuracy:

```bash
# 1. Synthesize scenarios if you lack mock logs
agents-cli eval dataset synthesize

# 2. Run inference over the evaluation datasets
agents-cli eval generate --dataset eval/datasets/discovery_dataset.json

# 3. Grade the generated traces
agents-cli eval grade --config eval/eval_config.yaml

# 4. Compare with your baseline to verify improvement
agents-cli eval compare baseline.json candidate.json
```

If any score drops below the threshold gates defined in the [evaluation_specification.md](file:///Users/ptech/Desktop/growthscout-ai/specs/evaluation_specification.md), the CI pipeline will block the pull request.
