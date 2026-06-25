import os
import yaml
from google.adk.agents import LlmAgent
from agents.shared.schemas import OpportunityAnalysisSchema

# Resolve directories
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))

# Load config
config_path = os.path.join(current_dir, "definition.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)["agent"]

# Load policies from shared location
policy_dir = os.path.join(root_dir, "agents", "shared", "policies")
policies = []
for policy_file in ["safety_policy.md", "evidence_policy.md", "grounding_policy.md"]:
    p_path = os.path.join(policy_dir, policy_file)
    if os.path.exists(p_path):
        with open(p_path, "r") as pf:
            policies.append(pf.read())
policy_text = "\n\n".join(policies)

system_instruction = f"{config['system_instruction']}\n\n=== SHARED POLICIES ===\n{policy_text}"

# Instantiate LlmAgent
agent = LlmAgent(
    name=config["name"],
    model=config["model"],
    instruction=system_instruction,
    description=config["description"],
    tools=[],  # Pure reasoning agent, no external tool access
    output_schema=OpportunityAnalysisSchema,
    output_key="opportunities"
)
