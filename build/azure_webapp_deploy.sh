#!/bin/bash
# Azure Web App Deployment Script for NSP Agent

# Configuration
RESOURCE_GROUP="nsp-agent-rg"
LOCATION="eastus"
APP_SERVICE_PLAN="nsp-agent-plan"
WEB_APP_NAME="nsp-agent-$(date +%s)"  # Unique name
PYTHON_VERSION="3.11"

echo "🚀 Starting NSP Agent (Next Step Proposals) deployment to Azure Web App..."

# Function to check if command succeeded
check_command() {
    if [ $? -eq 0 ]; then
        echo "✅ $1 successful"
    else
        echo "❌ $1 failed"
        exit 1
    fi
}

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI is not installed. Please install it first."
    exit 1
fi

# Login to Azure (if not already logged in)
echo "🔐 Checking Azure login status..."
az account show > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Please login to Azure:"
    az login
fi

echo "📋 Current Azure subscription:"
az account show --query "name" -o tsv

# Create resource group
echo "📂 Creating resource group: $RESOURCE_GROUP..."
az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION
check_command "Resource group creation"

# Create App Service Plan (Linux, Python support)
echo "⚙️ Creating App Service Plan..."
az appservice plan create \
    --name $APP_SERVICE_PLAN \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku B1 \
    --is-linux
check_command "App Service Plan creation"

# Create Web App
echo "🌐 Creating Web App: $WEB_APP_NAME..."
az webapp create \
    --resource-group $RESOURCE_GROUP \
    --plan $APP_SERVICE_PLAN \
    --name $WEB_APP_NAME \
    --runtime "PYTHON|$PYTHON_VERSION" \
    --startup-file "startup.sh"
check_command "Web App creation"

# Configure app settings (environment variables)
echo "⚙️ Configuring application settings..."
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $WEB_APP_NAME \
    --settings \
        SCM_DO_BUILD_DURING_DEPLOYMENT=true \
        WEBSITE_RUN_FROM_PACKAGE=1 \
        PROJECT_ENDPOINT="$PROJECT_ENDPOINT" \
        ORCHESTRATOR_AGENT_ID="$ORCHESTRATOR_AGENT_ID" \
        FLASK_SECRET_KEY="$FLASK_SECRET_KEY" \
        AZURE_CLIENT_ID="$AZURE_CLIENT_ID" \
        AZURE_CLIENT_SECRET="$AZURE_CLIENT_SECRET" \
        AZURE_TENANT_ID="$AZURE_TENANT_ID" \
        PYTHONPATH="/home/site/wwwroot"
check_command "App settings configuration"

# Enable logging
echo "📝 Enabling application logging..."
az webapp log config \
    --resource-group $RESOURCE_GROUP \
    --name $WEB_APP_NAME \
    --application-logging filesystem \
    --level information
check_command "Logging configuration"

# Create deployment package
echo "📦 Creating deployment package..."
zip -r nsp-agent-deploy.zip . \
    -x "*.git*" "*.vscode*" "__pycache__*" "*.pyc" "venv/*" "logs/*" "uploads/*" \
    "azure_deployment_script.sh" "docker-compose.yml" "Dockerfile" "*.md"
check_command "Deployment package creation"

# Deploy the application
echo "🚀 Deploying NSP Agent to Web App..."
az webapp deployment source config-zip \
    --resource-group $RESOURCE_GROUP \
    --name $WEB_APP_NAME \
    --src nsp-agent-deploy.zip
check_command "Application deployment"

# Get the app URL
APP_URL=$(az webapp show \
    --name $WEB_APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --query "defaultHostName" \
    --output tsv)

# Wait a moment for deployment to complete
echo "⏳ Waiting for deployment to complete..."
sleep 30

# Test the health endpoint
echo "🔍 Testing application health..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$APP_URL/api/health" || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ Health check passed!"
else
    echo "⚠️ Health check returned status: $HTTP_STATUS"
    echo "📋 Check logs with: az webapp log tail --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP"
fi

# Clean up deployment package
rm -f nsp-agent-deploy.zip

echo ""
echo "🎉 NSP Agent deployment completed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Resource Group: $RESOURCE_GROUP"
echo "🌐 App Name: $WEB_APP_NAME"
echo "🔗 App URL: https://$APP_URL"
echo "📊 Health Check: https://$APP_URL/api/health"
echo "🎯 NSP Agent: https://$APP_URL"
echo ""
echo "🔧 Management Commands:"
echo "   View logs: az webapp log tail --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP"
echo "   Restart app: az webapp restart --name $WEB_APP_NAME --resource-group $RESOURCE_GROUP"
echo "   Delete app: az group delete --name $RESOURCE_GROUP"
echo ""
echo "📝 To update NSP Agent:"
echo "   1. Make your changes"
echo "   2. Run: zip -r update.zip . -x '*.git*' '__pycache__*'"
echo "   3. Deploy: az webapp deployment source config-zip --resource-group $RESOURCE_GROUP --name $WEB_APP_NAME --src update.zip"
echo ""
echo "🚀 NSP Agent is now live and ready for Next Step Proposals!"