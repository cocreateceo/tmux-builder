# Documentation

This folder contains all project documentation for tmux-builder.

## Core Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](QUICKSTART.md) | Quick setup and usage guide |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture overview |
| [SMARTBUILD_ARCHITECTURE_ANALYSIS.md](SMARTBUILD_ARCHITECTURE_ANALYSIS.md) | Detailed SmartBuild pattern analysis |
| [PROJECT_GUIDELINES.md](PROJECT_GUIDELINES.md) | Development best practices and lessons learned |

## Design & Implementation Plans

Located in `plans/`:

| Document | Description |
|----------|-------------|
| [functional-gaps-design.md](plans/2026-01-24-functional-gaps-design.md) | Design for multi-user cloud deployment |
| [functional-gaps-implementation-plan.md](plans/2026-01-24-functional-gaps-implementation-plan.md) | 14-task implementation plan |

## Key Features

### Multi-User Cloud Deployment

tmux-builder supports multi-user deployments with:

- **User Isolation**: GUID-based user folders with individual sessions
- **Cloud Providers**: AWS (S3, CloudFront, EC2) and Azure (Blob, CDN, VMs)
- **Deployment Types**: Static sites and dynamic applications (Node.js, Python)

### 9-Step Pipeline

1. Create user (GUID folder & registry)
2. Create session (folder structure)
3. Gather requirements (parse POST body)
4. Create plan (Claude planning)
5. Generate code (Claude coding)
6. Deploy (AWS/Azure)
7. Health check (verify 200 OK)
8. Screenshot (Playwright capture)
9. E2E tests (generate & run)

### SmartBuild Pattern

File-based I/O for LLM-friendly operations:

- **Input**: JSON files in `sessions/active/<name>/prompts/`
- **Output**: Text files in `sessions/active/<name>/output/`
- **Signals**: Completion markers like `PHASE_COMPLETE: planning`

## API Reference

See main [README.md](../README.md#api-endpoints) for full API documentation.

## Agents & Skills

### Agents (`.claude/agents/`)

- **Deployers**: aws-s3-static, aws-elastic-beanstalk, azure-blob-static, azure-app-service
- **Testers**: health-check, screenshot
- **Utilities**: cache-invalidator, log-analyzer

### Skills (`.claude/skills/`)

- **AWS**: s3-upload, cloudfront-create, cloudfront-invalidate, eb-deploy, ec2-launch, rds-configure, elasticache-setup
- **Azure**: blob-upload, cdn-create, cdn-purge, app-service-deploy, sql-configure, redis-setup
- **Core**: project-inception, plan-validation, integration-verification
- **Testing**: health-check, screenshot-capture, e2e-generate, e2e-run
