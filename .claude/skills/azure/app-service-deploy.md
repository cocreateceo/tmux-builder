# Azure App Service Deploy Skill

## Purpose

Deploy web applications to Azure App Service for managed hosting with automatic scaling, built-in CI/CD, and support for multiple runtimes (Node.js, Python, .NET, Java, PHP).

## Prerequisites

- Azure CLI installed and configured (`az login`)
- `sunwaretech` Azure profile/subscription configured
- Application source code ready for deployment
- App Service Plan created or ability to create one

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `app_name` | Web app name (globally unique) | Yes | `myapp-webapp` |
| `resource_group` | Azure resource group | Yes | `my-resource-group` |
| `plan_name` | App Service Plan name | Yes | `myapp-plan` |
| `runtime` | Runtime stack | Yes | `NODE:18-lts`, `PYTHON:3.11` |
| `source_dir` | Application source directory | Yes | `./source/` |
| `location` | Azure region | No | `eastus` |
| `sku` | App Service Plan tier | No | `F1`, `B1`, `S1` |

## Usage Examples

### Set Azure Subscription

Always set the subscription before running commands:

```bash
az account set --subscription "sunwaretech"
```

### Create App Service Plan

```bash
az appservice plan create \
  --name {plan_name} \
  --resource-group {resource_group} \
  --location {location} \
  --sku {sku} \
  --is-linux \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create Web App (Node.js)

```bash
az webapp create \
  --name {app_name} \
  --resource-group {resource_group} \
  --plan {plan_name} \
  --runtime "NODE:18-lts" \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create Web App (Python)

```bash
az webapp create \
  --name {app_name} \
  --resource-group {resource_group} \
  --plan {plan_name} \
  --runtime "PYTHON:3.11" \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Deploy from Local Directory (Zip Deploy)

```bash
# Create deployment package
cd {source_dir}
zip -r ../deploy.zip . -x "*.git*" -x "node_modules/*" -x "__pycache__/*" -x "*.pyc"

# Deploy the package
az webapp deploy \
  --name {app_name} \
  --resource-group {resource_group} \
  --src-path ../deploy.zip \
  --type zip
```

### Deploy Using Git (Local Git)

```bash
# Configure local git deployment
az webapp deployment source config-local-git \
  --name {app_name} \
  --resource-group {resource_group}

# Get deployment credentials
az webapp deployment list-publishing-credentials \
  --name {app_name} \
  --resource-group {resource_group} \
  --query "{username: publishingUserName, password: publishingPassword}" \
  --output json

# Add remote and push
cd {source_dir}
git remote add azure https://{app_name}.scm.azurewebsites.net/{app_name}.git
git push azure main
```

### Deploy from GitHub

```bash
az webapp deployment source config \
  --name {app_name} \
  --resource-group {resource_group} \
  --repo-url https://github.com/{owner}/{repo} \
  --branch main \
  --git-token {github_token}
```

### Deploy Using Kudu API

```bash
# Get publish profile credentials
CREDS=$(az webapp deployment list-publishing-credentials \
  --name {app_name} \
  --resource-group {resource_group} \
  --query "{user: publishingUserName, pass: publishingPassword}" \
  --output json)

USER=$(echo $CREDS | jq -r '.user')
PASS=$(echo $CREDS | jq -r '.pass')

# Deploy zip via Kudu
curl -X POST \
  -u "$USER:$PASS" \
  --data-binary @deploy.zip \
  "https://{app_name}.scm.azurewebsites.net/api/zipdeploy"
```

## Configure Application Settings

### Set Environment Variables

```bash
az webapp config appsettings set \
  --name {app_name} \
  --resource-group {resource_group} \
  --settings KEY1=value1 KEY2=value2 NODE_ENV=production
```

### Set Connection Strings

```bash
az webapp config connection-string set \
  --name {app_name} \
  --resource-group {resource_group} \
  --connection-string-type SQLAzure \
  --settings DATABASE="Server=tcp:myserver.database.windows.net;Database=mydb;..."
```

### Configure Startup Command

```bash
# Node.js
az webapp config set \
  --name {app_name} \
  --resource-group {resource_group} \
  --startup-file "npm start"

# Python
az webapp config set \
  --name {app_name} \
  --resource-group {resource_group} \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 app:app"
```

## Scaling Configuration

### Scale Up (Change Plan Tier)

```bash
az appservice plan update \
  --name {plan_name} \
  --resource-group {resource_group} \
  --sku S1
```

### Scale Out (Add Instances)

```bash
az webapp scale \
  --name {app_name} \
  --resource-group {resource_group} \
  --instance-count 3
```

### Enable Auto-scaling

```bash
az monitor autoscale create \
  --resource-group {resource_group} \
  --resource {plan_name} \
  --resource-type Microsoft.Web/serverfarms \
  --name autoscale-rule \
  --min-count 1 \
  --max-count 10 \
  --count 1
```

## Verification

Check deployment status and get app URL:

```bash
# Get web app state
az webapp show \
  --name {app_name} \
  --resource-group {resource_group} \
  --query "state" \
  --output tsv

# Get default hostname
az webapp show \
  --name {app_name} \
  --resource-group {resource_group} \
  --query "defaultHostName" \
  --output tsv

# Check deployment status
az webapp deployment list-publishing-profiles \
  --name {app_name} \
  --resource-group {resource_group}

# View deployment logs
az webapp log deployment show \
  --name {app_name} \
  --resource-group {resource_group}

# Stream application logs
az webapp log tail \
  --name {app_name} \
  --resource-group {resource_group}
```

The app URL will be: `https://{app_name}.azurewebsites.net`

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `WebsiteWithNameAlreadyExists` | App name taken globally | Choose unique app name |
| `NumberOfWorkersExceeded` | Plan limit reached | Upgrade plan or reduce workers |
| `DeploymentFailed` | Build/deploy error | Check deployment logs |
| `ApplicationError` | Runtime crash | Check application logs |
| `ServiceUnavailable` | App not responding | Verify startup command and health |

## Notes

- App names must be globally unique across all Azure customers
- Free tier (F1) has limitations: 60 CPU minutes/day, no custom domains
- Always include `requirements.txt` (Python) or `package.json` (Node.js)
- Use deployment slots for zero-downtime deployments
- Enable Application Insights for monitoring and diagnostics
- Configure HTTPS-only for production applications
- Consider using managed identity for secure access to other Azure services
- Use `.deployment` file to customize build process
