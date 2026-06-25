import os
import yaml
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from agents.shared.schemas import AuditResultsSchema

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
web_analyzer_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "servers.web_analyzer_server.server"],
            env={
                "GOOGLE_MAPS_API_KEY": os.environ.get("GOOGLE_MAPS_API_KEY", ""),
                "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": os.environ.get("PYTHONPATH", "") or ".",
            }
        )
    ),
    tool_filter=["web_page_fetcher", "tech_footprint_scanner", "seo_auditor"]
)

# Instantiate LlmAgent
agent = LlmAgent(
    name=config["name"],
    model=config["model"],
    instruction=system_instruction,
    description=config["description"],
    tools=[web_analyzer_mcp],
    output_schema=AuditResultsSchema,
    output_key="audit_results"
)
