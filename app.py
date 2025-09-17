# app.py
from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import os
import asyncio
import io
import mimetypes
from datetime import datetime
from simple_sow_service import SOWProposalService, MockSOWService

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-secret-key-change-in-production"
)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max file size

# Initialize service - use real Azure AI Foundry service
try:
    if os.environ.get("PROJECT_ENDPOINT") and os.environ.get("ORCHESTRATOR_AGENT_ID"):
        sow_service = SOWProposalService()
        print("✅ Azure AI Foundry service initialized successfully")
        print(f"🎯 Using orchestrator agent: {os.environ.get('ORCHESTRATOR_AGENT_ID')}")
    else:
        sow_service = MockSOWService()
        print(
            "⚠️  Using mock service - missing PROJECT_ENDPOINT or ORCHESTRATOR_AGENT_ID"
        )
        print("📝 Please check your .env file")
except Exception as e:
    print(f"⚠️  Azure service failed to initialize: {e}")
    print("🔄 Falling back to mock service")
    sow_service = MockSOWService()

# Store processed proposals for download
proposals_storage = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NSP Agent Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .card-hover:hover { transform: translateY(-2px); transition: all 0.3s ease; }
        .pulse-blue { animation: pulse-blue 2s infinite; }
        @keyframes pulse-blue {
            0%, 100% { background-color: rgb(59, 130, 246); }
            50% { background-color: rgb(37, 99, 235); }
        }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Header -->
    <header class="gradient-bg text-white shadow-lg">
        <div class="max-w-6xl mx-auto px-6 py-8">
            <div class="text-center">
                <h1 class="text-4xl font-bold mb-2">🎯 NSP Agent Portal</h1>
                <p class="text-xl opacity-90">Transform Scope of Work documents into Azure upselling opportunities</p>
                <div class="mt-4 flex justify-center space-x-6 text-sm">
                    <div class="flex items-center">
                        <span class="w-2 h-2 bg-green-400 rounded-full mr-2"></span>
                        AI-Powered Analysis
                    </div>
                    <div class="flex items-center">
                        <span class="w-2 h-2 bg-green-400 rounded-full mr-2"></span>
                        Azure Integration
                    </div>
                    <div class="flex items-center">
                        <span class="w-2 h-2 bg-green-400 rounded-full mr-2"></span>
                        ROI Calculator
                    </div>
                </div>
            </div>
        </div>
    </header>

    <div class="max-w-6xl mx-auto px-6 py-8 space-y-8">
        
        <!-- Upload Section -->
        <div class="bg-white rounded-xl shadow-lg p-8 card-hover">
            <div class="text-center mb-6">
                <h2 class="text-2xl font-bold text-gray-800 mb-2">📄 Upload SOW Document</h2>
                <p class="text-gray-600">Upload your Scope of Work document to identify Azure opportunities</p>
            </div>
            
            <form id="uploadForm" class="space-y-6">
                <div class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 transition-colors">
                    <div class="mb-4">
                        <svg class="mx-auto h-16 w-16 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                        </svg>
                    </div>
                    <input type="file" id="fileInput" accept=".pdf,.docx,.doc,.txt" 
                           class="mb-4 text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" required>
                    <p class="text-sm text-gray-500 mt-2">
                        <strong>Supported formats:</strong> PDF, Word (.docx, .doc), Text files
                    </p>
                    <p class="text-xs text-gray-400 mt-1">Maximum file size: 50MB</p>
                </div>
                
                <div class="flex justify-center">
                    <button type="submit" id="analyzeBtn" 
                            class="bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 font-medium transition-colors flex items-center space-x-2">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                        </svg>
                        <span>🔍 Analyze SOW Document</span>
                    </button>
                </div>
            </form>
        </div>

        <!-- Processing Section -->
        <div id="processingSection" class="bg-white rounded-xl shadow-lg p-8 hidden">
            <div class="text-center mb-6">
                <h3 class="text-xl font-semibold text-gray-800 mb-2">⚡ Processing Your SOW Document</h3>
                <p class="text-gray-600">This may take 3-5 minutes depending on document complexity</p>
            </div>
            
            <!-- Progress Bar -->
            <div class="mb-6">
                <div class="flex justify-between text-sm text-gray-600 mb-2">
                    <span>Progress</span>
                    <span id="progressText">0%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-3">
                    <div id="progressBar" class="pulse-blue h-3 rounded-full transition-all duration-500" style="width: 0%"></div>
                </div>
            </div>
            
            <!-- Processing Steps -->
            <div class="grid md:grid-cols-2 gap-4">
                <div id="step1" class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                    <div class="w-6 h-6 rounded-full border-2 border-gray-300 flex items-center justify-center">
                        <div class="w-3 h-3 rounded-full bg-gray-300"></div>
                    </div>
                    <span class="text-gray-600">Parsing document structure...</span>
                </div>
                <div id="step2" class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                    <div class="w-6 h-6 rounded-full border-2 border-gray-300 flex items-center justify-center">
                        <div class="w-3 h-3 rounded-full bg-gray-300"></div>
                    </div>
                    <span class="text-gray-600">Analyzing Azure opportunities...</span>
                </div>
                <div id="step3" class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                    <div class="w-6 h-6 rounded-full border-2 border-gray-300 flex items-center justify-center">
                        <div class="w-3 h-3 rounded-full bg-gray-300"></div>
                    </div>
                    <span class="text-gray-600">Researching services and pricing...</span>
                </div>
                <div id="step4" class="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                    <div class="w-6 h-6 rounded-full border-2 border-gray-300 flex items-center justify-center">
                        <div class="w-3 h-3 rounded-full bg-gray-300"></div>
                    </div>
                    <span class="text-gray-600">Generating proposal...</span>
                </div>
            </div>
            
            <!-- Cancel Button -->
            <div class="text-center mt-6">
                <button onclick="cancelProcessing()" class="text-gray-500 hover:text-gray-700 text-sm">
                    Cancel Processing
                </button>
            </div>
        </div>

        <!-- Results Section -->
        <div id="resultsSection" class="bg-white rounded-xl shadow-lg p-8 hidden">
            <div class="text-center mb-6">
                <h3 class="text-2xl font-bold text-green-600 mb-2">✅ Next Step Proposal Generated</h3>
                <p class="text-gray-600">Your Next Step opportunities analysis is complete</p>
                <div id="processingStats" class="mt-2 text-sm text-gray-500"></div>
            </div>
            
            <div class="bg-gray-50 rounded-lg p-6 mb-6">
                <div class="max-h-96 overflow-y-auto">
                    <pre id="proposalText" class="whitespace-pre-wrap text-sm text-gray-800 font-mono"></pre>
                </div>
            </div>
            
            <!-- Action Buttons -->
            <div class="flex flex-wrap gap-4 justify-center">
                <button onclick="downloadProposal()" 
                        class="flex items-center space-x-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    <span>📥 Download Proposal</span>
                </button>
                
                <button onclick="copyToClipboard()" 
                        class="flex items-center space-x-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                    </svg>
                    <span>📋 Copy to Clipboard</span>
                </button>
                
                <button onclick="emailProposal()" 
                        class="flex items-center space-x-2 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                    </svg>
                    <span>📧 Share via Email</span>
                </button>
                
                <button onclick="resetForm()" 
                        class="flex items-center space-x-2 px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                    </svg>
                    <span>🔄 Analyze Another SOW</span>
                </button>
            </div>
        </div>

        <!-- Error Section -->
        <div id="errorSection" class="bg-red-50 border border-red-200 rounded-xl p-8 hidden">
            <div class="text-center">
                <div class="text-red-500 mb-4">
                    <svg class="mx-auto h-16 w-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"/>
                    </svg>
                </div>
                <h3 class="text-lg font-semibold text-red-800 mb-2">❌ Processing Error</h3>
                <p id="errorText" class="text-red-600 mb-4"></p>
                <button onclick="resetForm()" 
                        class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors">
                    Try Again
                </button>
            </div>
        </div>

        <!-- Feature Overview -->
        <div class="bg-white rounded-xl shadow-lg p-8">
            <h3 class="text-xl font-bold text-center text-gray-800 mb-6">🚀 How It Works</h3>
            <div class="grid md:grid-cols-4 gap-6">
                <div class="text-center">
                    <div class="bg-blue-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-3">
                        <span class="text-2xl">📄</span>
                    </div>
                    <h4 class="font-semibold mb-2">Upload SOW</h4>
                    <p class="text-sm text-gray-600">Upload your Scope of Work document in PDF or Word format</p>
                </div>
                <div class="text-center">
                    <div class="bg-green-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-3">
                        <span class="text-2xl">🤖</span>
                    </div>
                    <h4 class="font-semibold mb-2">AI Analysis</h4>
                    <p class="text-sm text-gray-600">Advanced AI analyzes requirements and identifies opportunities</p>
                </div>
                <div class="text-center">
                    <div class="bg-purple-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-3">
                        <span class="text-2xl">🔍</span>
                    </div>
                    <h4 class="font-semibold mb-2">Research</h4>
                    <p class="text-sm text-gray-600">Deep research on Azure services, pricing, and competitive positioning</p>
                </div>
                <div class="text-center">
                    <div class="bg-orange-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-3">
                        <span class="text-2xl">📊</span>
                    </div>
                    <h4 class="font-semibold mb-2">Proposal</h4>
                    <p class="text-sm text-gray-600">Generate comprehensive proposal with ROI analysis</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Toast Notification -->
    <div id="toast" class="fixed top-4 right-4 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg hidden">
        <span id="toastMessage"></span>
    </div>

    <script>
        let currentProposal = '';
        let currentFileName = '';
        let processingAborted = false;

        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];
            
            if (!file) {
                showToast('Please select a file', 'error');
                return;
            }

            // Validate file size
            if (file.size > 50 * 1024 * 1024) {
                showToast('File size exceeds 50MB limit', 'error');
                return;
            }

            currentFileName = file.name;
            processingAborted = false;
            
            // Show processing section
            document.getElementById('processingSection').classList.remove('hidden');
            document.getElementById('resultsSection').classList.add('hidden');
            document.getElementById('errorSection').classList.add('hidden');
            
            // Start progress simulation
            simulateProgress();

            // Upload file
            const formData = new FormData();
            formData.append('file', file);

            try {
                const response = await fetch('/api/sow/process', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (processingAborted) {
                    return; // User cancelled
                }

                if (result.status === 'success') {
                    currentProposal = result.proposal;
                    document.getElementById('proposalText').textContent = result.proposal;
                    
                    // Show processing stats
                    const stats = `Processing time: ${result.processing_time || 'N/A'}s | Timestamp: ${new Date(result.timestamp).toLocaleString()}`;
                    document.getElementById('processingStats').textContent = stats;
                    
                    document.getElementById('processingSection').classList.add('hidden');
                    document.getElementById('resultsSection').classList.remove('hidden');
                    
                    showToast('Proposal generated successfully!', 'success');
                } else {
                    showError(result.error || 'Processing failed');
                }
            } catch (error) {
                if (!processingAborted) {
                    showError('Network error: ' + error.message);
                }
            }
        });

        function simulateProgress() {
            let progress = 0;
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            
            const progressInterval = setInterval(() => {
                if (processingAborted) {
                    clearInterval(progressInterval);
                    return;
                }
                
                progress += Math.random() * 15 + 5; // Variable progress speed
                progress = Math.min(progress, 95); // Don't reach 100% until done
                
                progressBar.style.width = progress + '%';
                progressText.textContent = Math.round(progress) + '%';
                
                // Update step indicators
                if (progress >= 25) updateStep('step1', '✅ Document structure parsed');
                if (progress >= 50) updateStep('step2', '✅ Azure opportunities identified');  
                if (progress >= 75) updateStep('step3', '✅ Service research completed');
                if (progress >= 90) updateStep('step4', '✅ Proposal being finalized...');
                
            }, 800);
        }

        function updateStep(stepId, text) {
            const step = document.getElementById(stepId);
            const circle = step.querySelector('.w-6.h-6 div');
            const textSpan = step.querySelector('span');
            
            if (text.startsWith('✅')) {
                circle.classList.remove('bg-gray-300');
                circle.classList.add('bg-green-500');
                step.classList.remove('bg-gray-50');
                step.classList.add('bg-green-50');
            }
            
            textSpan.textContent = text;
        }

        function showError(message) {
            document.getElementById('processingSection').classList.add('hidden');
            document.getElementById('errorSection').classList.remove('hidden');
            document.getElementById('errorText').textContent = message;
            showToast('Processing failed', 'error');
        }

        function showToast(message, type = 'success') {
            const toast = document.getElementById('toast');
            const toastMessage = document.getElementById('toastMessage');
            
            toastMessage.textContent = message;
            toast.className = `fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg ${type === 'error' ? 'bg-red-500' : 'bg-green-500'} text-white`;
            toast.classList.remove('hidden');
            
            setTimeout(() => {
                toast.classList.add('hidden');
            }, 3000);
        }

        function downloadProposal() {
            const blob = new Blob([currentProposal], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Azure-NSP-Proposal-${currentFileName.replace(/\.[^/.]+$/, "")}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('Proposal downloaded successfully!');
        }

        function copyToClipboard() {
            navigator.clipboard.writeText(currentProposal).then(() => {
                showToast('Proposal copied to clipboard!');
            }).catch(() => {
                showToast('Failed to copy to clipboard', 'error');
            });
        }

        function emailProposal() {
            const subject = encodeURIComponent(`Azure Next Step Proposal - ${currentFileName}`);
            const body = encodeURIComponent(currentProposal);
            const mailtoLink = `mailto:?subject=${subject}&body=${body}`;
            window.location.href = mailtoLink;
        }

        function resetForm() {
            processingAborted = true;
            document.getElementById('uploadForm').reset();
            document.getElementById('processingSection').classList.add('hidden');
            document.getElementById('resultsSection').classList.add('hidden');
            document.getElementById('errorSection').classList.add('hidden');
            
            // Reset progress
            document.getElementById('progressBar').style.width = '0%';
            document.getElementById('progressText').textContent = '0%';
            
            // Reset steps
            ['step1', 'step2', 'step3', 'step4'].forEach(stepId => {
                const step = document.getElementById(stepId);
                const circle = step.querySelector('.w-6.h-6 div');
                const textSpan = step.querySelector('span');
                
                circle.classList.remove('bg-green-500');
                circle.classList.add('bg-gray-300');
                step.classList.remove('bg-green-50');
                step.classList.add('bg-gray-50');
                
                const defaultTexts = {
                    'step1': 'Parsing document structure...',
                    'step2': 'Analyzing Azure opportunities...',
                    'step3': 'Researching services and pricing...',
                    'step4': 'Generating proposal...'
                };
                textSpan.textContent = defaultTexts[stepId];
            });
            
            currentProposal = '';
            currentFileName = '';
        }

        function cancelProcessing() {
            processingAborted = true;
            resetForm();
            showToast('Processing cancelled');
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    """Main page with upload interface"""
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/sow/process", methods=["POST"])
def process_sow():
    """Process SOW document and return proposal"""
    try:
        # Validate request
        if "file" not in request.files:
            return jsonify({"status": "error", "error": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "" or not file.filename:
            return jsonify({"status": "error", "error": "No file selected"}), 400

        # Validate file type
        allowed_extensions = {".pdf", ".docx", ".doc", ".txt"}
        file_extension = os.path.splitext(file.filename.lower())[1]
        if file_extension not in allowed_extensions:
            return (
                jsonify(
                    {
                        "status": "error",
                        "error": f"Unsupported file type: {file_extension}. Supported: {', '.join(allowed_extensions)}",
                    }
                ),
                400,
            )

        # Read file content
        file.seek(0)  # Reset file pointer
        file_content = file.read()
        filename = file.filename

        # Validate file size
        if len(file_content) == 0:
            return jsonify({"status": "error", "error": "File is empty"}), 400

        # Process with service
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                sow_service.process_sow_document(file_content, filename)
            )
        finally:
            loop.close()

        # Store proposal for potential download
        if result.get("status") == "success" and "thread_id" in result:
            proposals_storage[result["thread_id"]] = {
                "proposal": result["proposal"],
                "filename": filename,
                "timestamp": result.get("timestamp", datetime.now().isoformat()),
            }

        return jsonify(result)

    except Exception as e:
        return jsonify({"status": "error", "error": f"Server error: {str(e)}"}), 500


@app.route("/api/proposal/<thread_id>/download")
def download_proposal(thread_id):
    """Download proposal as text file"""
    try:
        if thread_id not in proposals_storage:
            return jsonify({"error": "Proposal not found"}), 404

        proposal_data = proposals_storage[thread_id]

        # Create text file
        output = io.StringIO()
        output.write(proposal_data["proposal"])
        output.seek(0)

        # Generate filename
        safe_filename = "".join(
            c for c in proposal_data["filename"] if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        download_filename = f"Azure-Proposal-{safe_filename}.txt"

        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            as_attachment=True,
            download_name=download_filename,
            mimetype="text/plain",
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "service": "NSP Agent Portal",
            "timestamp": datetime.now().isoformat(),
            "azure_integration": (
                "mock" if isinstance(sow_service, MockSOWService) else "live"
            ),
        }
    )


@app.route("/api/stats")
def get_stats():
    """Get basic usage statistics"""
    return jsonify(
        {
            "proposals_generated": len(proposals_storage),
            "service_type": (
                "mock" if isinstance(sow_service, MockSOWService) else "azure"
            ),
            "uptime": "running",
        }
    )


if __name__ == "__main__":
    print("🚀 Starting NSP Agent Portal...")
    print(
        f"📊 Service type: {'Mock' if isinstance(sow_service, MockSOWService) else 'Azure AI Foundry'}"
    )
    print("🌐 Open your browser to: http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
