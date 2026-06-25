import pytest
from agents.business_discovery_agent.agent import agent as discovery_agent
from agents.website_analysis_agent.agent import agent as analysis_agent
from agents.opportunity_agent.agent import agent as opp_agent
from agents.growth_intelligence_agent.agent import agent as growth_agent

def test_agent_permission_boundaries():
    # 1. Discovery Agent Boundaries
    assert len(discovery_agent.tools) == 1
    discovery_toolset = discovery_agent.tools[0]
    # Authorized tools
    assert "local_business_search" in discovery_toolset.tool_filter
    # Unauthorized tools
    assert "web_page_fetcher" not in discovery_toolset.tool_filter
    assert "tech_footprint_scanner" not in discovery_toolset.tool_filter
    assert "seo_auditor" not in discovery_toolset.tool_filter

    # 2. Analysis Agent Boundaries
    assert len(analysis_agent.tools) == 1
    analysis_toolset = analysis_agent.tools[0]
    # Authorized tools
    assert "web_page_fetcher" in analysis_toolset.tool_filter
    assert "tech_footprint_scanner" in analysis_toolset.tool_filter
    assert "seo_auditor" in analysis_toolset.tool_filter
    # Unauthorized tools
    assert "local_business_search" not in analysis_toolset.tool_filter

    # 3. Opportunity Agent Boundaries (Pure reasoning - no tools allowed)
    assert len(opp_agent.tools) == 0

    # 4. Growth Intelligence Agent Boundaries (Pure reasoning - no tools allowed)
    assert len(growth_agent.tools) == 0
