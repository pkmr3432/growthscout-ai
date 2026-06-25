import pytest
from agents.opportunity_agent.agent import agent
from agents.shared.schemas import OpportunityAnalysisSchema

def test_opportunity_agent_config():
    assert agent.name == "opportunity_agent"
    assert agent.model == "gemini-1.5-flash-002"
    assert "Opportunity Agent" in agent.instruction
    assert "safety policy" in agent.instruction.lower()
    assert "evidence policy" in agent.instruction.lower()
    assert "grounding policy" in agent.instruction.lower()
    assert agent.output_schema == OpportunityAnalysisSchema
    
    # Opportunity agent is pure reasoning and must have no tools
    assert len(agent.tools) == 0
