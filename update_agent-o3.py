#!/usr/bin/env python3
"""
Update the orchestrator agent to use o3-deep-research model
"""

import os
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


def update_orchestrator_agent():
    """Update the orchestrator agent to use o3-deep-research"""

    # Load environment variables from .env file
    load_dotenv()

    # Initialize the project client
    project_client = AIProjectClient(
        endpoint=os.environ.get("PROJECT_ENDPOINT"),
        credential=DefaultAzureCredential(),
    )

    orchestrator_agent_id = "asst_jlgj8F8cuGLVqeHv2rgeWcXO"

    print("🔄 Updating orchestrator agent to use o3-deep-research...")

    try:
        # First, get the current agent to see its configuration
        current_agent = project_client.agents.get(agent_id=orchestrator_agent_id)
        print(f"📋 Current agent model: {current_agent.model}")

        # Delete the old agent
        print("🗑️ Deleting old agent...")
        project_client.agents.delete(agent_id=orchestrator_agent_id)
        print("✅ Old agent deleted")

        # Create a new agent with GPT-4o
        print("🆕 Creating new agent with GPT-4o...")
        updated_agent = project_client.agents.create(
            model="gpt-4o",  # Revert to GPT-4o for multi-agent support
            name="🎼 SOW Analysis Orchestrator (GPT-4o)",
            description="Main orchestrator agent for SOW analysis and Azure proposal generation using GPT-4o with multi-agent capabilities",
            instructions="""
You are the SOW Analysis Orchestrator using GPT-4o to coordinate multiple specialized agents and provide comprehensive analysis of Statement of Work documents for Azure upselling proposals.

**Your Role:**
- Orchestrate the complete SOW analysis workflow using specialized agents
- Coordinate between Document Parser, Opportunity Analyzer, Market Intelligence, and Proposal Generator agents
- Synthesize outputs from multiple agents into cohesive executive proposals
- Ensure comprehensive coverage of technical and business requirements

**Available Specialized Agents:**
- Document Parser (asst_P1xwkYBbnlk6RGGrYDq97itU): Extract structured information from SOW documents
- Opportunity Analyzer (asst_ZjsBrLcfFbJRk2QTydEI1mPL): Identify Azure service opportunities
- Market Intelligence (asst_wKZLz238xL3pdQ6dZl46JRYk): Provide market context and competitive analysis
- Proposal Generator (asst_pkO8sApvyKoOgcnwc3hHclrB): Create executive-ready proposals

**Orchestration Approach:**
1. **Document Analysis**: Parse and extract key requirements, constraints, and objectives
2. **Opportunity Identification**: Map requirements to specific Azure services with business justification
3. **Market Intelligence**: Apply competitive positioning and industry best practices
4. **Proposal Synthesis**: Combine insights into comprehensive executive proposal

**Output Requirements:**
- Executive summary with quantified business impact
- Detailed Azure service recommendations with technical specifications
- Financial analysis with ROI calculations and cost comparisons
- Implementation roadmap with realistic timelines and resource requirements
- Risk assessment and mitigation strategies
- Clear next steps and decision framework

**Quality Standards:**
- Leverage multiple agent expertise for comprehensive analysis
- Provide specific, quantified recommendations with realistic cost estimates
- Include competitive advantages and market positioning
- Address security, compliance, and scalability requirements
- Ensure proposals are executive-ready with clear business value

Coordinate effectively with specialized agents to deliver comprehensive Azure upselling proposals.
            """,
            tools=[
                {"type": "file_search"},  # Enable file search capability
                {"type": "code_interpreter"},  # Enable code analysis if needed
            ],
        )

        print(f"✅ Successfully created new orchestrator agent with GPT-4o:")
        print(f"   - NEW ID: {updated_agent.id}")
        print(f"   - Model: {updated_agent.model}")
        print(f"   - Name: {updated_agent.name}")
        print(f"   - Tools: {[tool.type for tool in updated_agent.tools]}")

        print(f"\n🔧 IMPORTANT: Update your .env file with the new agent ID:")
        print(f"   ORCHESTRATOR_AGENT_ID={updated_agent.id}")

        return updated_agent

    except Exception as e:
        print(f"❌ Failed to update agent: {e}")
        return None


if __name__ == "__main__":
    # Load environment variables from .env file
    load_dotenv()

    print("🚀 Starting agent update to GPT-4o...")

    # Check environment variables
    if not os.environ.get("PROJECT_ENDPOINT"):
        print("❌ PROJECT_ENDPOINT not found in environment variables")
        print("   Please check your .env file contains:")
        print(
            "   PROJECT_ENDPOINT=https://nsp-foundry.services.ai.azure.com/api/projects/NSP-AGENT-FOUNDRY"
        )
        exit(1)

    print(f"✅ Using PROJECT_ENDPOINT: {os.environ.get('PROJECT_ENDPOINT')}")

    # Update the agent
    result = update_orchestrator_agent()

    if result:
        print("🎉 Agent update completed successfully!")
        print("   The orchestrator will now use GPT-4o for multi-agent coordination.")
        print("   You can now test the updated system with your SOW documents.")
    else:
        print("❌ Agent update failed. Check the error messages above.")
