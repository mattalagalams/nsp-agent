# sow_service.py
import os
import asyncio
import tempfile
from typing import Dict, Any
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import (
    FileSearchToolDefinition,
    DeepResearchToolDefinition,
    ConnectedAgentTool,
)
from azure.identity import DefaultAzureCredential
from datetime import datetime
import json


class SOWProposalService:
    def __init__(self):
        """Initialize the SOW Analysis service with Azure AI Foundry"""
        self.project_client = AIProjectClient(
            endpoint=os.environ.get("PROJECT_ENDPOINT"),
            credential=DefaultAzureCredential(),
        )

        # Use the real orchestrator agent ID
        self.orchestrator_agent_id = os.environ.get("ORCHESTRATOR_AGENT_ID")

        # Switch to real agent processing (no longer using simple/mock)
        self.use_simple_agent = False  # Always use orchestrator now

    async def process_sow_document(
        self, file_content: bytes, filename: str
    ) -> Dict[str, Any]:
        """
        Process SOW document and generate Azure upselling proposal

        Args:
            file_content: Binary content of the uploaded file
            filename: Name of the uploaded file

        Returns:
            Dictionary with processing results
        """
        try:
            # Always use orchestrator agent now
            return await self._process_with_orchestrator(file_content, filename)

        except Exception as e:
            return {
                "status": "error",
                "error": f"Processing failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }

    async def _process_with_single_agent(
        self, file_content: bytes, filename: str
    ) -> Dict[str, Any]:
        """Simplified processing with a single agent for testing"""
        try:
            # Create a simple agent for SOW analysis
            agent = await self._create_or_get_sow_agent()

            # Create thread for this processing session
            thread = self.project_client.agents.create_thread()

            # Save file temporarily and upload
            with tempfile.NamedTemporaryFile(
                suffix=f"_{filename}", delete=False
            ) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            try:
                # Upload file to the agent
                uploaded_file = self.project_client.agents.upload_file(
                    file_path=temp_file_path, purpose="assistants"
                )

                # Create message with comprehensive SOW analysis prompt
                analysis_prompt = self._create_comprehensive_analysis_prompt(filename)

                message = self.project_client.agents.create_message(
                    thread_id=thread.id,
                    role="user",
                    content=analysis_prompt,
                    file_ids=[uploaded_file.id],
                )

                # Run the agent
                run = self.project_client.agents.create_run(
                    thread_id=thread.id, agent_id=agent.id
                )

                # Poll for completion
                max_wait_time = 300  # 5 minutes max
                wait_time = 0

                while (
                    run.status in ["queued", "in_progress"]
                    and wait_time < max_wait_time
                ):
                    await asyncio.sleep(5)
                    wait_time += 5
                    run = self.project_client.agents.get_run(
                        thread_id=thread.id, run_id=run.id
                    )

                if run.status == "completed":
                    # Get the proposal
                    messages = self.project_client.agents.list_messages(
                        thread_id=thread.id
                    )
                    proposal_message = next(
                        msg for msg in messages if msg.role == "assistant"
                    )

                    proposal_text = proposal_message.content[0].text.value

                    return {
                        "status": "success",
                        "proposal": proposal_text,
                        "thread_id": thread.id,
                        "file_id": uploaded_file.id,
                        "processing_time": wait_time,
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    return {
                        "status": "error",
                        "error": f"Agent processing failed with status: {run.status}",
                        "details": (
                            run.last_error
                            if hasattr(run, "last_error")
                            else "No additional details"
                        ),
                    }

            finally:
                # Clean up temp file
                os.unlink(temp_file_path)

        except Exception as e:
            return {
                "status": "error",
                "error": f"Single agent processing failed: {str(e)}",
            }

    async def _create_or_get_sow_agent(self):
        """Create or retrieve the SOW analysis agent"""
        try:
            # Try to get existing agent first
            if hasattr(self, "_sow_agent"):
                return self._sow_agent

            # Create new agent with comprehensive instructions
            agent = self.project_client.agents.create_agent(
                model=os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
                name="SOW Analysis Agent",
                instructions=self._get_comprehensive_agent_instructions(),
                tools=[
                    FileSearchToolDefinition(),
                    # Add Deep Research if available
                    *(
                        [
                            DeepResearchToolDefinition(
                                deep_research={
                                    "bing_grounding_connection_id": os.environ.get(
                                        "AZURE_BING_CONNECTION_ID"
                                    ),
                                    "model_deployment_name": os.environ.get(
                                        "DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME"
                                    ),
                                }
                            )
                        ]
                        if os.environ.get("AZURE_BING_CONNECTION_ID")
                        else []
                    ),
                ],
            )

            self._sow_agent = agent
            return agent

        except Exception as e:
            print(f"Error creating agent: {e}")
            raise

    def _get_comprehensive_agent_instructions(self) -> str:
        """Get comprehensive instructions for SOW analysis"""
        return """
You are an expert Azure Solutions Architect and Sales Engineer specializing in analyzing Scope of Work (SOW) documents to identify Azure upselling opportunities.

YOUR EXPERTISE:
- Azure architecture and service portfolio
- Cost optimization and ROI analysis  
- Enterprise solution design
- Competitive positioning vs AWS/GCP
- Implementation planning and risk assessment

ANALYSIS WORKFLOW:

1. DOCUMENT PARSING & UNDERSTANDING
   - Extract project objectives, timeline, and budget
   - Identify current technology stack and infrastructure
   - Note technical requirements and constraints
   - Flag compliance, security, and performance needs
   - Document team size, skills, and organizational context

2. OPPORTUNITY IDENTIFICATION
   Focus on these Azure service categories:
   
   INFRASTRUCTURE & COMPUTE:
   - Azure Virtual Machines, App Service, Container Instances
   - Azure Kubernetes Service (AKS)
   - Azure Functions for serverless computing
   - Azure Spring Apps for Java workloads
   
   DATA & ANALYTICS:
   - Azure SQL Database, Cosmos DB, PostgreSQL
   - Azure Synapse Analytics for data warehousing
   - Azure Data Factory for ETL/ELT
   - Power BI for business intelligence
   
   AI & MACHINE LEARNING:
   - Azure Cognitive Services (Vision, Language, Speech)
   - Azure Machine Learning platform
   - Azure Bot Service for conversational AI
   - Azure Form Recognizer for document processing
   
   SECURITY & IDENTITY:
   - Microsoft Entra ID (Azure AD)
   - Azure Security Center & Microsoft Sentinel
   - Azure Key Vault for secrets management
   - Azure DDoS Protection
   
   INTEGRATION & AUTOMATION:
   - Azure Logic Apps for workflow automation
   - Azure API Management
   - Azure Service Bus for messaging
   - Azure DevOps for CI/CD

3. BUSINESS CASE DEVELOPMENT
   For each recommended service:
   - Quantify business impact (cost savings, performance gains, risk reduction)
   - Estimate implementation effort and timeline
   - Calculate ROI and payback period
   - Address potential objections and risks

4. COMPETITIVE POSITIONING
   - Highlight Azure's unique advantages
   - Compare pricing with AWS/GCP where relevant
   - Emphasize Microsoft ecosystem integration benefits
   - Reference relevant customer success stories

OUTPUT FORMAT:
Generate a professional "Next Step Proposal" with these sections:

📋 EXECUTIVE SUMMARY
- 3-4 key opportunity highlights
- Total estimated value/savings
- Recommended engagement approach

🔍 SOW ANALYSIS FINDINGS
- Project overview and key requirements
- Current state assessment
- Identified gaps and opportunities

🚀 RECOMMENDED AZURE SERVICES
For each service (limit to top 5):
- Service name and key capabilities
- Business justification and expected impact
- Implementation complexity (Low/Medium/High)
- Estimated monthly cost
- Timeline to value

💰 FINANCIAL IMPACT
- Total investment required
- Expected cost savings/revenue increase
- ROI calculation and payback period
- Comparison with alternative solutions

📅 IMPLEMENTATION ROADMAP
- Phase 1: Quick wins (30-90 days)
- Phase 2: Core migrations (3-6 months)  
- Phase 3: Advanced optimization (6-12 months)
- Key milestones and success metrics

🎯 NEXT STEPS
- Immediate actions required
- Recommended engagement model
- Decision timeline and stakeholders
- Proposed follow-up activities

⚠️ RISK MITIGATION
- Technical implementation risks
- Change management considerations
- Recommended mitigation strategies

Always include specific Azure pricing references, relevant case studies, and cite current Azure capabilities. Focus on measurable business outcomes over technical features.

If you have access to Deep Research tool, use it to:
- Verify current Azure service pricing and capabilities
- Research competitor positioning and recent developments
- Find relevant customer case studies and ROI data
- Validate market trends and adoption patterns

Maintain a consultative, professional tone focused on business value and strategic outcomes.
        """

    def _create_comprehensive_analysis_prompt(self, filename: str) -> str:
        """Create comprehensive analysis prompt for the uploaded SOW"""
        return f"""
Please analyze the uploaded SOW document ({filename}) and generate a comprehensive "Next Step Proposal" focusing on Azure upselling opportunities.

ANALYSIS REQUIREMENTS:

1. DOCUMENT UNDERSTANDING
   - Extract and summarize key project requirements
   - Identify current technology stack and infrastructure mentioned
   - Note budget constraints, timeline, and success criteria
   - Flag any specific compliance, security, or performance requirements

2. AZURE OPPORTUNITY ASSESSMENT
   - Identify specific Azure services that align with project needs
   - Prioritize opportunities by business impact and implementation feasibility
   - Consider both immediate needs and future expansion possibilities
   - Focus on services where Azure has competitive advantages

3. BUSINESS VALUE QUANTIFICATION
   - Estimate cost savings, performance improvements, or revenue opportunities
   - Provide realistic ROI calculations with supporting assumptions
   - Include both hard and soft benefits (cost, risk reduction, agility, etc.)
   - Compare with current state or alternative solutions

4. IMPLEMENTATION STRATEGY
   - Propose phased approach starting with highest-value, lowest-risk opportunities
   - Provide realistic timelines and resource requirements
   - Address potential technical and organizational challenges
   - Recommend specific next steps and engagement models

5. MARKET CONTEXT
   If you have access to research capabilities, include:
   - Current Azure pricing for recommended services
   - Recent feature updates or service improvements
   - Relevant customer success stories or case studies
   - Competitive positioning insights

Generate a professional, executive-ready proposal that demonstrates clear business value and provides actionable next steps for Azure adoption.
        """

    async def _process_with_orchestrator(
        self, file_content: bytes, filename: str
    ) -> Dict[str, Any]:
        """Process using the orchestrator agent"""
        try:
            # Create thread for this processing session
            thread = self.project_client.agents.create_thread()

            # Save file temporarily and upload
            with tempfile.NamedTemporaryFile(
                suffix=f"_{filename}", delete=False
            ) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            try:
                # Upload file to the agent
                uploaded_file = self.project_client.agents.upload_file(
                    file_path=temp_file_path, purpose="assistants"
                )

                # Create comprehensive SOW analysis message
                analysis_message = f"""
Please analyze the uploaded SOW document ({filename}) and generate a comprehensive "Next Step Proposal" with Azure upselling opportunities.

Execute the complete workflow:

1. **Document Analysis**: Extract and structure all key information from the SOW
2. **Opportunity Identification**: Identify prioritized Azure service opportunities  
3. **Market Intelligence**: Apply Azure competitive advantages and best practices
4. **Proposal Generation**: Create executive-ready proposal with ROI analysis

Focus on:
- Clear business value and ROI quantification
- Realistic implementation timelines
- Azure's competitive advantages
- Executive-level recommendations with concrete next steps

Deliver a complete "Next Step Proposal" ready for executive review.
                """

                message = self.project_client.agents.create_message(
                    thread_id=thread.id,
                    role="user",
                    content=analysis_message,
                    file_ids=[uploaded_file.id],
                )

                # Run the orchestrator agent
                run = self.project_client.agents.create_run(
                    thread_id=thread.id, agent_id=self.orchestrator_agent_id
                )

                # Poll for completion with extended timeout for complex analysis
                max_wait_time = 600  # 10 minutes for comprehensive analysis
                wait_time = 0

                while (
                    run.status in ["queued", "in_progress"]
                    and wait_time < max_wait_time
                ):
                    await asyncio.sleep(10)  # Check every 10 seconds
                    wait_time += 10
                    run = self.project_client.agents.get_run(
                        thread_id=thread.id, run_id=run.id
                    )

                    # Log progress for debugging
                    if wait_time % 60 == 0:  # Every minute
                        print(
                            f"Processing SOW... {wait_time//60} minutes elapsed, status: {run.status}"
                        )

                if run.status == "completed":
                    # Get the proposal
                    messages = self.project_client.agents.list_messages(
                        thread_id=thread.id
                    )
                    proposal_message = next(
                        msg for msg in messages if msg.role == "assistant"
                    )

                    proposal_text = proposal_message.content[0].text.value

                    return {
                        "status": "success",
                        "proposal": proposal_text,
                        "thread_id": thread.id,
                        "file_id": uploaded_file.id,
                        "processing_time": wait_time,
                        "timestamp": datetime.now().isoformat(),
                        "agent_used": "orchestrator",
                    }
                else:
                    # Handle timeout or failure
                    error_msg = f"Processing failed with status: {run.status}"
                    if hasattr(run, "last_error") and run.last_error:
                        error_msg += f" - {run.last_error}"
                    elif wait_time >= max_wait_time:
                        error_msg += " - Processing timeout (10 minutes exceeded)"

                    return {
                        "status": "error",
                        "error": error_msg,
                        "processing_time": wait_time,
                    }

            finally:
                # Clean up temp file
                os.unlink(temp_file_path)

        except Exception as e:
            return {
                "status": "error",
                "error": f"Orchestrator processing failed: {str(e)}",
            }


# Mock service for initial testing without Azure setup
class MockSOWService:
    async def process_sow_document(
        self, file_content: bytes, filename: str
    ) -> Dict[str, Any]:
        """Mock service that returns sample proposal for testing"""

        # Simulate processing time
        await asyncio.sleep(3)

        return {
            "status": "success",
            "proposal": f"""📋 NEXT STEP PROPOSAL - AZURE UPSELLING OPPORTUNITIES

Document Analyzed: {filename}
Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

📋 EXECUTIVE SUMMARY
Based on analysis of {filename}, we've identified 4 high-impact Azure opportunities with potential annual savings of $180,000 and improved operational efficiency of 40%.

Key Recommendations:
• Migrate current infrastructure to Azure App Service - 35% cost reduction
• Implement Azure SQL Database with automatic tuning - 50% performance improvement  
• Deploy Azure AI Document Intelligence - 60% faster document processing
• Add Azure DevOps for CI/CD pipeline - 80% faster deployment cycles

🔍 SOW ANALYSIS FINDINGS

Project Overview:
- Web application modernization project
- Current hosting on legacy on-premises servers
- Microsoft SQL Server 2016 database
- Manual deployment processes
- Document-heavy workflows requiring processing

Current State Challenges:
- High infrastructure maintenance costs ($15,000/month)
- Performance bottlenecks during peak usage
- Manual document processing taking 2-3 hours per document
- Deployment cycles taking 2-3 weeks
- Limited disaster recovery capabilities

🚀 RECOMMENDED AZURE SERVICES

1. AZURE APP SERVICE
   Business Impact: Reduce infrastructure costs by 35% ($5,250/month savings)
   Technical Benefits: Auto-scaling, built-in load balancing, SSL certificates
   Implementation: Medium complexity
   Monthly Cost: $2,800 (vs current $8,000)
   Timeline: 6-8 weeks migration

2. AZURE SQL DATABASE
   Business Impact: 50% faster query performance, 99.99% uptime SLA
   Technical Benefits: Automatic tuning, built-in intelligence, point-in-time restore
   Implementation: Medium complexity  
   Monthly Cost: $1,200
   Timeline: 4-6 weeks migration

3. AZURE AI DOCUMENT INTELLIGENCE
   Business Impact: 60% reduction in document processing time (saves 40 hours/week)
   Technical Benefits: OCR, form recognition, table extraction, custom models
   Implementation: Low-Medium complexity
   Monthly Cost: $800
   Timeline: 3-4 weeks integration

4. AZURE DEVOPS
   Business Impact: 80% faster deployments, reduced human error risk
   Technical Benefits: CI/CD pipelines, automated testing, release management
   Implementation: Low complexity
   Monthly Cost: $300 (for team of 10)
   Timeline: 2-3 weeks setup

5. AZURE BACKUP & SITE RECOVERY
   Business Impact: Comprehensive disaster recovery, meet RTO/RPO requirements
   Technical Benefits: Automated backups, cross-region replication
   Implementation: Low complexity
   Monthly Cost: $400
   Timeline: 2 weeks setup

💰 FINANCIAL IMPACT

Total Monthly Investment: $5,500
Current Monthly Costs: $15,000+
Monthly Savings: $9,500
Annual Savings: $114,000

Additional Value:
- Productivity gains from faster document processing: $50,000/year
- Reduced deployment errors and downtime: $16,000/year
- Improved disaster recovery posture: Risk mitigation valued at $25,000/year

Total Annual Value: $180,000+
ROI: 327% in first year
Payback Period: 4 months

📅 IMPLEMENTATION ROADMAP

PHASE 1: FOUNDATION (Months 1-2)
- Set up Azure subscription and governance
- Deploy Azure DevOps and establish CI/CD pipeline
- Implement Azure Backup for existing systems
- Quick win: Immediate deployment automation

PHASE 2: CORE MIGRATION (Months 2-4)  
- Migrate application to Azure App Service
- Database migration to Azure SQL Database
- Performance testing and optimization
- Staff training on new platform

PHASE 3: AI ENHANCEMENT (Months 4-5)
- Deploy Azure AI Document Intelligence
- Integrate with existing document workflows
- Build custom models for specific document types
- User acceptance testing

PHASE 4: OPTIMIZATION (Months 5-6)
- Performance tuning and cost optimization
- Advanced monitoring and alerting setup
- Disaster recovery testing
- Knowledge transfer and documentation

🎯 NEXT STEPS

IMMEDIATE ACTIONS (Next 2 weeks):
1. Schedule Azure architecture review session (2 hours)
2. Conduct proof-of-concept for document processing (1 week)
3. Prepare detailed migration plan for priority applications
4. Set up Azure subscriptions and basic governance

RECOMMENDED ENGAGEMENT:
- Azure Migration Assessment Workshop (2 days)
- Dedicated Azure Solutions Architect for 3 months
- Training program for development and operations teams
- Ongoing Azure optimization review (quarterly)

DECISION TIMELINE:
- Week 1-2: Technical validation and stakeholder alignment
- Week 3-4: Contract negotiation and project planning  
- Week 5: Project kickoff and Phase 1 initiation

⚠️ RISK MITIGATION

Technical Risks:
- Application compatibility: Recommended compatibility assessment before migration
- Data migration complexity: Plan for gradual migration with rollback procedures
- Performance validation: Extensive testing in Azure staging environment

Organizational Risks:
- Change management: Comprehensive training program and gradual rollout
- Skills gap: Partner with Azure experts for knowledge transfer
- Business continuity: Maintain parallel systems during critical migration phases

Success Factors:
- Executive sponsorship and clear communication
- Dedicated migration team with protected time
- Partnership with experienced Azure implementation partner
- Phased approach with clear milestones and success metrics

COMPETITIVE ADVANTAGES OF AZURE:
- Seamless integration with existing Microsoft technologies
- Industry-leading compliance certifications (SOC 2, ISO 27001, HIPAA)
- Global presence with 60+ regions
- Cost optimization tools and reserved instance pricing
- 99.95% SLA on critical services

This proposal is based on initial analysis of your SOW document. We recommend scheduling a detailed technical review to validate assumptions and refine recommendations based on your specific requirements and constraints.
            """,
            "thread_id": "mock-123",
            "file_id": "mock-file-456",
            "processing_time": 3,
            "timestamp": datetime.now().isoformat(),
        }
