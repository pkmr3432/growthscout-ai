import pytest
from agents.website_analysis_agent.agent import agent
from agents.shared.schemas import AuditResultsSchema

def test_website_analysis_agent_config():
    assert agent.name == "website_analysis_agent"
    assert agent.model == "gemini-1.5-flash-002"
    assert "Website Analysis Agent" in agent.instruction
    assert "safety policy" in agent.instruction.lower()
    assert "evidence policy" in agent.instruction.lower()
    assert "grounding policy" in agent.instruction.lower()
    assert agent.output_schema == AuditResultsSchema
    
    # Verify allowed MCP tools: web_page_fetcher, tech_footprint_scanner, seo_auditor
    assert len(agent.tools) == 1
    mcp_toolset = agent.tools[0]
    assert set(mcp_toolset.tool_filter) == {"web_page_fetcher", "tech_footprint_scanner", "seo_auditor"}
