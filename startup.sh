#!/bin/bash
# Startup script for NSP Agent on Azure Web App

echo "🚀 Starting NSP Agent (Next Step Proposals)..."

# Create necessary directories
mkdir -p logs uploads templates static

# Set permissions
chmod 755 logs uploads

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "📦 Installing Python dependencies..."
    pip install -r requirements.txt
elif [ -f "requirements-minimal.txt" ]; then
    echo "📦 Installing minimal dependencies..."
    pip install -r requirements-minimal.txt
fi

# Set Python path
export PYTHONPATH="/home/site/wwwroot:$PYTHONPATH"

# Set Flask environment
export FLASK_APP=app.py
export FLASK_ENV=production

echo "🌐 Starting Flask application..."

# Start the application with gunicorn
exec gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 300 --access-logfile '-' --error-logfile '-' app:app



# Set environment variables for deployment
export PROJECT_ENDPOINT="https://nsp-foundry.services.ai.azure.com/api/projects/NSP-AGENT-FOUNDRY"
export ORCHESTRATOR_AGENT_ID="asst_ODMsCCq1orV9gotFLQA08pS0"
export FLASK_SECRET_KEY="75435c7867f9421f365ee22b05d59271e71f637cbb4f4a564aa4b69f8b3b92b9"
export AZURE_CLIENT_ID="ef924b30-1d21-4608-8f38-a6de95e26d60"
export AZURE_CLIENT_SECRET="your-azure-client-secret"
export AZURE_TENANT_ID="your-azure-tenant-id"