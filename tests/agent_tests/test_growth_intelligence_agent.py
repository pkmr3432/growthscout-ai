import pytest
from agents.growth_intelligence_agent.agent import agent
from agents.shared.schemas import GrowthReportsSchema

def test_growth_intelligence_agent_config():
    assert agent.name == "growth_intelligence_agent"
    assert agent.model == "gemini-1.5-pro-002"
    assert "Growth Intelligence Agent" in agent.instruction
    assert "safety policy" in agent.instruction.lower()
    assert "evidence policy" in agent.instruction.lower()
    assert "grounding policy" in agent.instruction.lower()
    assert agent.output_schema == GrowthReportsSchema
    
    # Growth intelligence agent is pure reasoning and must have no tools
    assert len(agent.tools) == 0
