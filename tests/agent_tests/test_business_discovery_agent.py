import pytest
from agents.business_discovery_agent.agent import agent
from agents.shared.schemas import DiscoveryLeadsSchema

def test_business_discovery_agent_config():
    assert agent.name == "business_discovery_agent"
    assert agent.model == "gemini-1.5-flash-002"
    assert "Business Discovery Agent" in agent.instruction
    assert "safety policy" in agent.instruction.lower()
    assert "evidence policy" in agent.instruction.lower()
    assert "grounding policy" in agent.instruction.lower()
    assert agent.output_schema == DiscoveryLeadsSchema
    
    # Verify allowed MCP tools: only local_business_search is allowed
    assert len(agent.tools) == 1
    mcp_toolset = agent.tools[0]
    assert "local_business_search" in mcp_toolset.tool_filter
    assert len(mcp_toolset.tool_filter) == 1
