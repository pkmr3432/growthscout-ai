import os
import asyncio
import json
from typing import Any
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.genai import types

# Import agents
from agents.business_discovery_agent.agent import agent as discovery_agent
from agents.website_analysis_agent.agent import agent as analysis_agent
from agents.opportunity_agent.agent import agent as opp_agent
from agents.growth_intelligence_agent.agent import agent as growth_agent

# Mock tool callback to bypass live maps/crawling requirements
async def mock_before_tool_callback(tool, args, tool_context):
    print(f"--- Intercepted tool call: {tool.name} with args: {args} ---")
    if tool.name == "local_business_search":
        return {
            "status": "success",
            "results": [
                {
                    "name": "Austin Boiler Experts",
                    "formatted_address": "100 Congress Ave, Austin, TX",
                    "website": "http://austinboilerexperts.com",
                    "rating": 4.5,
                    "user_ratings_total": 45
                }
            ]
        }
    elif tool.name == "web_page_fetcher":
        return {
            "status": 200,
            "content": "<html><h1>Austin Boiler Experts</h1></html>"
        }
    elif tool.name == "tech_footprint_scanner":
        return {
            "cms": "wordpress",
            "load_time_seconds": 1.2,
            "has_booking_widget": False
        }
    elif tool.name == "seo_auditor":
        return {
            "seo_data": {
                "meta_title": "Austin Boiler Experts - Best Boiler Repair in Austin",
                "meta_description": "We offer top quality boiler repair services in Austin, TX.",
                "h1_elements": ["Austin Boiler Experts"],
                "has_schema_markup": False
            }
        }
    return None

# Bind mock callbacks to prevent live API failures during test validation
discovery_agent.before_tool_callback = mock_before_tool_callback
analysis_agent.before_tool_callback = mock_before_tool_callback

# Map Vertex AI model names to AI Studio gemini-2.5-flash for developer validation
discovery_agent.model = "gemini-2.5-flash"
analysis_agent.model = "gemini-2.5-flash"
opp_agent.model = "gemini-2.5-flash"
growth_agent.model = "gemini-2.5-flash"

async def run_agent(agent_instance, prompt: str, app_name: str) -> tuple[str, Any]:
    app = App(name=app_name, root_agent=agent_instance)
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id="validation_user"
    )
    
    result_content = ""
    structured_output = None
    async for event in runner.run_async(
        user_id="validation_user",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    result_content += part.text
        if event.output is not None:
            structured_output = event.output
            print(f"[{agent_instance.name}] Structured Output received: {type(event.output)}")
            
    return result_content, structured_output

async def main():
    print("=== STARTING WORKER AGENT RUNTIME VALIDATION ===")
    
    results = {}
    
    # 1. Validate Discovery Agent
    print("\n--- Validating business_discovery_agent ---")
    discovery_prompt = "Find local plumbing services in Austin, TX."
    text_out, struct_out = await run_agent(discovery_agent, discovery_prompt, "discovery_app")
    results["discovery_agent"] = {
        "text": text_out,
        "structured": struct_out
    }
    print(f"Discovery Result Leads Count: {len(struct_out.leads) if struct_out else 'No output'}")

    # Introduce rate-limiting delay
    print("Waiting 15 seconds to respect rate limits...")
    await asyncio.sleep(15)

    # 2. Validate Website Analysis Agent
    print("\n--- Validating website_analysis_agent ---")
    analysis_prompt = "Perform webpresence analysis on http://austinboilerexperts.com"
    text_out, struct_out = await run_agent(analysis_agent, analysis_prompt, "analysis_app")
    results["analysis_agent"] = {
        "text": text_out,
        "structured": struct_out
    }
    print(f"Analysis Result CMS: {struct_out.audit_results.cms if struct_out else 'No output'}")

    # Introduce rate-limiting delay
    print("Waiting 15 seconds to respect rate limits...")
    await asyncio.sleep(15)

    # 3. Validate Opportunity Agent
    print("\n--- Validating opportunity_agent ---")
    opp_prompt = (
        "Classify and score opportunities for Austin Boiler Experts (website: http://austinboilerexperts.com) "
        "using these crawl results:\n"
        "website_url: http://austinboilerexperts.com\n"
        "http_status_code: 200\n"
        "cms: wordpress\n"
        "load_time_seconds: 1.2\n"
        "has_booking_widget: False\n"
        "seo_data: {'meta_title': 'Austin Boiler Experts', 'meta_description': None, 'h1_elements': [], 'has_schema_markup': False}"
    )
    text_out, struct_out = await run_agent(opp_agent, opp_prompt, "opportunity_app")
    results["opportunity_agent"] = {
        "text": text_out,
        "structured": struct_out
    }
    print(f"Opportunity Result Lead Score: {struct_out.lead_score if struct_out else 'No output'}")

    # Introduce rate-limiting delay
    print("Waiting 15 seconds to respect rate limits...")
    await asyncio.sleep(15)

    # 4. Validate Growth Intelligence Agent
    print("\n--- Validating growth_intelligence_agent ---")
    growth_prompt = (
        "Generate a growth report for Austin Boiler Experts (website: http://austinboilerexperts.com) "
        "with opportunity_scores: {'seo': 15, 'conversion_optimization': 35}, business_impact_analysis: "
        "[{'technical_finding': 'missing_booking_widget', 'business_consequence': 'visitors bounce without booking'}], "
        "and overall lead score: 50."
    )
    text_out, struct_out = await run_agent(growth_agent, growth_prompt, "growth_app")
    results["growth_agent"] = {
        "text": text_out,
        "structured": struct_out
    }
    print(f"Growth Report Length: {len(struct_out.growth_report_markdown) if struct_out else 'No output'}")

    # Save results to a json file
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    output_path = os.path.join(root_dir, "scratch", "validation_results.json")
    serializable = {}
    for agent_name, out in results.items():
        serializable[agent_name] = {
            "text": out["text"],
            "structured": out["structured"].model_dump() if out["structured"] else None
        }
    with open(output_path, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\nSaved runtime validation results to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
