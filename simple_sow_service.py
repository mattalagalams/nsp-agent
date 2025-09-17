# simple_sow_service.py
"""
Updated SOW Analysis Service with o3-deep-research and proper file processing
"""

import os
import asyncio
import tempfile
from typing import Dict, Any
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from datetime import datetime


class SOWProposalService:
    def __init__(self):
        """Initialize the SOW Analysis service with Azure AI Foundry"""
        self.project_client = AIProjectClient(
            endpoint=os.environ.get("PROJECT_ENDPOINT"),
            credential=DefaultAzureCredential(),
        )

        # Use the orchestrator agent ID
        self.orchestrator_agent_id = os.environ.get("ORCHESTRATOR_AGENT_ID")

        if not self.orchestrator_agent_id:
            raise ValueError("ORCHESTRATOR_AGENT_ID not found in environment variables")

    async def process_sow_document(
        self, file_content: bytes, filename: str
    ) -> Dict[str, Any]:
        """
        Process SOW document and generate Azure upselling proposal
        """
        try:
            return await self._process_with_orchestrator(file_content, filename)

        except Exception as e:
            return {
                "status": "error",
                "error": f"Processing failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }

    async def _extract_text_content(self, file_content: bytes, filename: str) -> str:
        """Extract text content from the uploaded file"""
        try:
            # Try to decode as text first
            if filename.lower().endswith(".txt"):
                return file_content.decode("utf-8", errors="ignore")

            # For other file types, try basic text extraction
            text_content = file_content.decode("utf-8", errors="ignore")

            # Clean up common file format artifacts
            if filename.lower().endswith((".doc", ".docx")):
                # Basic cleanup for Word docs decoded as text
                import re

                text_content = re.sub(r"[^\x20-\x7E\n\r\t]", " ", text_content)
                text_content = re.sub(r"\s+", " ", text_content).strip()

            return text_content[:10000]  # Limit to first 10k characters for processing

        except Exception as e:
            print(f"⚠️ Text extraction failed: {e}")
            return f"Content from {filename} (text extraction encountered issues, please provide key details manually)"

    async def _process_with_orchestrator(
        self, file_content: bytes, filename: str
    ) -> Dict[str, Any]:
        """Process using the orchestrator agent with enhanced file handling"""
        try:
            print(f"🔄 Starting SOW analysis for: {filename}")

            # Extract text content from the file
            document_text = await self._extract_text_content(file_content, filename)

            # Create thread for this processing session
            thread = self.project_client.agents.threads.create()
            print(f"📋 Created thread: {thread.id}")

            # Enhanced analysis message with extracted content
            analysis_message = f"""
I need you to analyze this SOW document and generate a comprehensive Azure upselling proposal.

DOCUMENT: {filename}
EXTRACTED CONTENT:
{document_text}

Please execute the complete workflow:

1. **Document Analysis**: Extract and structure key information:
   - Project objectives and business requirements
   - Current technology stack and infrastructure
   - Timeline, budget, and resource constraints
   - Technical specifications and performance requirements
   - Integration needs and compliance requirements

2. **Azure Opportunity Identification**: Identify specific Azure services that match the requirements:
   - Azure App Service for web applications
   - Azure SQL Database/Cosmos DB for data storage
   - Azure AI services for document processing/ML needs
   - Azure DevOps for CI/CD and project management
   - Azure Security Center for compliance and security
   - Azure Monitor for observability
   - Consider cost optimization opportunities

3. **Business Case Development**: 
   - Calculate potential cost savings vs current state
   - ROI projections with realistic timelines
   - Competitive advantages of Azure ecosystem
   - Risk mitigation through Azure's enterprise features

4. **Executive Proposal**: Generate a comprehensive proposal with:

   📋 **EXECUTIVE SUMMARY**
   - 2-3 key business impacts and financial benefits
   - Top 3 Azure service recommendations
   - Overall ROI and cost savings projection

   🎯 **AZURE SERVICE RECOMMENDATIONS**
   - Specific Azure services with business justification
   - Technical implementation approach
   - Cost analysis (monthly/annual estimates)
   - Implementation timeline for each service

   📊 **FINANCIAL ANALYSIS**
   - Current state costs vs Azure costs
   - Monthly and annual savings projections
   - ROI calculation over 12-24 months
   - TCO comparison

   🚀 **IMPLEMENTATION ROADMAP**
   - Phase 1: Quick wins (0-3 months)
   - Phase 2: Core migration (3-6 months)
   - Phase 3: Advanced features (6-12 months)
   - Resource requirements and timeline

   📈 **BUSINESS BENEFITS**
   - Operational efficiency improvements
   - Scalability and performance gains
   - Security and compliance advantages
   - Innovation enablement opportunities

   ✅ **NEXT STEPS**
   - Immediate action items
   - Decision timeline
   - Required stakeholder engagement
   - Technical proof of concept recommendations

**IMPORTANT**: Use the o3-deep-research capabilities to provide thorough analysis with specific, quantified recommendations. Include realistic cost estimates, implementation timelines, and measurable business benefits.

Generate a complete executive-ready proposal that demonstrates clear value proposition for Azure adoption.
            """

            print(
                "💬 Sending analysis request to orchestrator with o3-deep-research..."
            )
            message = self.project_client.agents.messages.create(
                thread_id=thread.id, role="user", content=analysis_message
            )

            # Create run with the agent's configured model (GPT-4o)
            print("🤖 Starting agent processing with GPT-4o...")
            run = self.project_client.agents.runs.create(
                thread_id=thread.id,
                agent_id=self.orchestrator_agent_id,
                # Remove model override to use the agent's configured model
                additional_instructions="Use your orchestration capabilities to coordinate with specialized agents and provide comprehensive Azure service recommendations with specific cost estimates and implementation details.",
            )

            # Standard timeout for GPT-4o processing
            max_wait_time = 300  # 5 minutes for GPT-4o analysis
            wait_time = 0

            print("⏳ Processing SOW document with GPT-4o orchestrator...")
            while (
                run.status in ["queued", "in_progress", "requires_action"]
                and wait_time < max_wait_time
            ):
                await asyncio.sleep(10)  # Check every 10 seconds
                wait_time += 10
                run = self.project_client.agents.runs.get(
                    thread_id=thread.id, run_id=run.id
                )

                # Progress updates
                if wait_time % 30 == 0:  # Every 30 seconds
                    print(
                        f"🔄 GPT-4o orchestration in progress... {wait_time} seconds elapsed, status: {run.status}"
                    )

            print(f"🏁 GPT-4o processing completed with status: {run.status}")

            if run.status == "completed":
                # Get the comprehensive proposal
                print("📥 Retrieving generated proposal...")
                messages = self.project_client.agents.messages.list(thread_id=thread.id)

                # Find the assistant's response (latest message)
                proposal_message = None
                for msg in reversed(
                    list(messages)
                ):  # Get most recent assistant message
                    if msg.role == "assistant":
                        proposal_message = msg
                        break

                if not proposal_message:
                    return {
                        "status": "error",
                        "error": "No assistant response found in thread",
                        "debug_messages": [
                            f"{msg.role}: {msg.content[0].text.value[:100]}..."
                            for msg in messages
                        ],
                    }

                proposal_text = proposal_message.content[0].text.value

                print("✅ GPT-4o proposal generated successfully!")
                print(f"📊 Proposal length: {len(proposal_text)} characters")

                return {
                    "status": "success",
                    "proposal": proposal_text,
                    "thread_id": thread.id,
                    "processing_time": wait_time,
                    "timestamp": datetime.now().isoformat(),
                    "agent_used": "orchestrator_gpt4o",
                    "model_used": "gpt-4o",
                    "filename": filename,
                    "document_length": len(document_text),
                }
            else:
                # Handle timeout or failure
                error_msg = f"GPT-4o processing failed with status: {run.status}"
                if hasattr(run, "last_error") and run.last_error:
                    error_msg += f" - {run.last_error}"
                elif wait_time >= max_wait_time:
                    error_msg += " - Processing timeout (5 minutes exceeded)"

                print(f"❌ Processing failed: {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg,
                    "processing_time": wait_time,
                    "run_status": run.status,
                    "model_used": "gpt-4o",
                }

        except Exception as e:
            print(f"❌ Error in orchestrator processing: {str(e)}")
            import traceback

            traceback.print_exc()
            return {
                "status": "error",
                "error": f"Orchestrator processing failed: {str(e)}",
            }


# Enhanced Mock service for testing o3 capabilities
class MockSOWService:
    async def process_sow_document(
        self, file_content: bytes, filename: str
    ) -> Dict[str, Any]:
        """Enhanced mock service that simulates o3-deep-research output"""

        # Simulate longer processing time for o3
        await asyncio.sleep(8)

        return {
            "status": "success",
            "proposal": f"""📋 COMPREHENSIVE AZURE UPSELLING PROPOSAL - o3 DEEP RESEARCH ANALYSIS

Document Analyzed: {filename}
Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Model: o3-deep-research
Analysis Depth: Comprehensive Enterprise Assessment

📋 EXECUTIVE SUMMARY

Based on comprehensive analysis using o3-deep-research capabilities, we've identified transformational Azure opportunities with projected annual savings of $420,000 (38% cost reduction) and operational efficiency improvements of 65%.

Strategic Recommendations:
• Complete infrastructure modernization to Azure - $25K/month savings
• AI-powered document processing pipeline - 85% automation increase  
• Enterprise-grade security and compliance - Risk mitigation worth $2M annually
• DevOps transformation - 10x faster delivery cycles

Total Investment: $180,000 | 24-Month ROI: 340% | Payback Period: 8 months

🎯 TOP AZURE SERVICE RECOMMENDATIONS

1. **AZURE APP SERVICE + CONTAINER APPS**
   Business Impact: $300K annual infrastructure savings, 99.99% SLA
   Technical Benefits: Auto-scaling, zero-downtime deployments, integrated CI/CD
   Monthly Cost: $4,200 (vs current $12,500)
   Implementation: 8 weeks
   Risk Level: Low

2. **AZURE COGNITIVE SERVICES + DOCUMENT INTELLIGENCE**
   Business Impact: Process 2,000 documents/day vs current 100/day capacity
   ROI: $180K annually from labor cost savings
   Technical Benefits: 95% accuracy, multi-format support, custom models
   Monthly Cost: $1,800
   Implementation: 6 weeks
   Risk Level: Low

3. **AZURE SYNAPSE ANALYTICS + POWER BI**
   Business Impact: Real-time insights, 75% faster reporting
   ROI: $120K annually from improved decision making
   Technical Benefits: Unified analytics, AI integration, enterprise scale
   Monthly Cost: $3,500
   Implementation: 12 weeks
   Risk Level: Medium

4. **AZURE SECURITY CENTER + SENTINEL**
   Business Impact: Enterprise security posture, compliance automation
   Risk Mitigation: Potential breach cost avoidance ($2M average)
   Technical Benefits: AI-powered threat detection, automated response
   Monthly Cost: $2,200
   Implementation: 6 weeks
   Risk Level: Low

5. **AZURE DEVOPS + GITHUB ENTERPRISE**
   Business Impact: 10x faster deployment cycles (2 weeks → 2 hours)
   Productivity Gain: 40% developer efficiency improvement
   Technical Benefits: End-to-end automation, integrated security scanning
   Monthly Cost: $1,200
   Implementation: 4 weeks
   Risk Level: Low

📊 COMPREHENSIVE FINANCIAL ANALYSIS

Current State Costs (Annual):
- Infrastructure & Hosting: $150,000
- Manual Processing Labor: $240,000  
- Security & Compliance: $80,000
- Development & Operations: $180,000
- TOTAL: $650,000

Proposed Azure Solution (Annual):
- Azure Services: $156,000
- Implementation & Training: $60,000 (one-time)
- Ongoing Support: $14,000
- TOTAL: $230,000 (Year 1: $290,000)

Financial Benefits:
- Year 1 Net Savings: $360,000
- Year 2+ Annual Savings: $420,000
- 24-Month ROI: 340%
- Break-even Point: 8 months

🚀 PHASED IMPLEMENTATION ROADMAP

**PHASE 1: FOUNDATION (Months 1-3)**
- Azure App Service migration
- Basic security implementation
- Cost Optimization: $8K/month immediate savings
- Resources: 2 cloud architects, 3 developers

**PHASE 2: INTELLIGENCE (Months 4-6)**  
- Document Intelligence deployment
- Power BI analytics implementation
- Productivity Gains: 40% process automation
- Resources: 1 AI specialist, 2 analysts

**PHASE 3: OPTIMIZATION (Months 7-12)**
- Advanced security features
- DevOps transformation
- Performance Gains: 65% overall efficiency improvement
- Resources: 1 DevOps engineer, ongoing support

📈 QUANTIFIED BUSINESS BENEFITS

Operational Efficiency:
- Document processing: 85% reduction in manual effort
- Deployment cycles: 95% time reduction
- System uptime: 99.99% SLA vs current 98%
- Security incidents: 90% reduction through AI monitoring

Strategic Advantages:
- Scalability: Handle 500% growth without infrastructure investment
- Innovation: AI/ML capabilities enable new product features
- Compliance: Automated compliance reporting saves 200 hours/month
- Talent: Access to Azure's extensive developer ecosystem

Competitive Position:
- Market responsiveness: 10x faster feature delivery
- Data insights: Real-time analytics vs quarterly reports
- Cost structure: 38% lower operational costs than competitors
- Risk profile: Enterprise-grade security and disaster recovery

✅ IMMEDIATE NEXT STEPS

1. **Executive Decision (Week 1)**
   - Present proposal to C-suite
   - Secure $290K Year 1 budget approval
   - Designate internal Azure champion

2. **Technical Validation (Weeks 2-4)**
   - Azure architecture review workshop
   - Proof-of-concept deployment
   - Performance benchmarking

3. **Implementation Planning (Weeks 5-8)**
   - Detailed migration planning
   - Team training program
   - Vendor partnerships and support agreements

4. **Phase 1 Kickoff (Month 2)**
   - Project team assignment
   - Azure environment provisioning
   - Migration execution begins

🎯 DECISION FRAMEWORK

This proposal provides a comprehensive pathway to Azure transformation with quantified benefits and realistic implementation timelines. The combination of immediate cost savings, operational improvements, and strategic capabilities positions your organization for sustained competitive advantage.

**Recommendation**: Proceed with Executive Decision phase immediately to capitalize on identified opportunities and begin realizing benefits within 60 days.

*This analysis leverages o3-deep-research capabilities for comprehensive assessment of technical and business factors.*
            """,
            "thread_id": "mock-o3-123",
            "processing_time": 8,
            "timestamp": datetime.now().isoformat(),
            "agent_used": "mock_o3",
            "model_used": "o3-deep-research",
            "filename": filename,
            "document_length": len(file_content),
        }
