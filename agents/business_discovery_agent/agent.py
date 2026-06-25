import os
import yaml
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from agents.shared.schemas import DiscoveryLeadsSchema

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

# Configure MCP toolset
local_search_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "servers.local_search_server.server"],
        )
    ),
    tool_filter=["local_business_search"]
)

# Instantiate LlmAgent
agent = LlmAgent(
    name=config["name"],
    model=config["model"],
    instruction=system_instruction,
    description=config["description"],
    tools=[local_search_mcp],
    output_schema=DiscoveryLeadsSchema,
    output_key="leads"
)
