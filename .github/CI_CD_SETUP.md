# CI/CD Pipeline Setup Guide

## Overview

DisruptIQ uses GitHub Actions for automated CI/CD with three main workflows:

1. **Continuous Integration (ci.yml)** - Automated testing, linting, security scanning
2. **Continuous Deployment (cd.yml)** - Automated deployment to staging/production
3. **Docker Publishing (docker-publish.yml)** - Multi-architecture Docker image builds

## Prerequisites

### 1. GitHub Repository Settings

#### Required Secrets

Navigate to **Settings → Secrets and variables → Actions** and add the following secrets:

##### OpenAI Integration
- `OPENAI_API_KEY` - OpenAI API key for LLM features

##### Code Quality & Coverage
- `CODECOV_TOKEN` - Token from codecov.io for coverage reports
- `SONAR_TOKEN` - SonarCloud token for code quality analysis

##### Deployment - Staging
- `STAGING_HOST` - Staging server IP/hostname
- `STAGING_USERNAME` - SSH username for staging
- `STAGING_SSH_KEY` - Private SSH key for staging server

##### Deployment - Production
- `PROD_HOST` - Production server IP/hostname
- `PROD_USERNAME` - SSH username for production
- `PROD_SSH_KEY` - Private SSH key for production server

##### Notifications
- `SLACK_WEBHOOK` - Slack webhook URL for deployment notifications

##### GitHub Packages
- `GITHUB_TOKEN` - Automatically provided by GitHub Actions (no setup needed)

### 2. External Service Setup

#### Codecov Setup
1. Go to [codecov.io](https://codecov.io)
2. Sign in with GitHub
3. Add your repository
4. Copy the upload token
5. Add as `CODECOV_TOKEN` secret in GitHub

#### SonarCloud Setup
1. Go to [sonarcloud.io](https://sonarcloud.io)
2. Sign in with GitHub
3. Create new organization or use existing
4. Import repository
5. Copy the token
6. Add as `SONAR_TOKEN` secret in GitHub
7. Update `sonar-project.properties` with your organization key

#### Slack Notifications Setup
1. Create Slack webhook:
   - Go to Slack workspace
   - Apps → Incoming Webhooks
   - Add to workspace
   - Copy webhook URL
2. Add as `SLACK_WEBHOOK` secret in GitHub

### 3. Server Setup (Staging & Production)

#### Server Requirements
- Ubuntu 20.04+ or Debian 11+
- Docker & Docker Compose installed
- SSH access configured
- Minimum 2GB RAM, 20GB disk

#### SSH Key Setup
```bash
# On your local machine
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/disruptiq_deploy

# Copy public key to servers
ssh-copy-id -i ~/.ssh/disruptiq_deploy.pub user@staging-server
ssh-copy-id -i ~/.ssh/disruptiq_deploy.pub user@prod-server

# Add private key to GitHub secrets
cat ~/.ssh/disruptiq_deploy
# Copy output to STAGING_SSH_KEY and PROD_SSH_KEY secrets
```

#### Server Directory Structure
```bash
# Create deployment directory on servers
ssh user@server
sudo mkdir -p /opt/disruptiq
sudo chown $USER:$USER /opt/disruptiq
cd /opt/disruptiq

# Clone repository or upload docker-compose files
git clone https://github.com/your-org/DisruptIQ_CC.git .

# Create .env file
cp .env.example .env
nano .env  # Configure production values

# Create backup directory
mkdir -p backups
```

#### Firewall Configuration
```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Workflows Explanation

### CI Workflow (ci.yml)

**Triggers:** Push to main/develop, Pull Requests

**Jobs:**
1. **backend-tests** - Python testing, linting, coverage
   - Black formatting check
   - isort import sorting
   - Flake8 linting
   - MyPy type checking
   - Pytest with >85% coverage requirement

2. **frontend-tests** - JavaScript/TypeScript testing
   - ESLint
   - Jest tests
   - Build verification

3. **docker-build** - Docker image build test
   - Multi-stage build validation
   - Cache optimization

4. **security-scan** - Security vulnerability scanning
   - Trivy filesystem scan
   - Python dependency check with Safety
   - SARIF upload to GitHub Security

5. **code-quality** - SonarCloud analysis
   - Code smells detection
   - Security hotspots
   - Technical debt calculation

6. **integration-tests** - Full stack testing
   - Docker Compose deployment
   - API endpoint testing
   - Health checks

### CD Workflow (cd.yml)

**Triggers:**
- Push to main branch
- Version tags (v*.*.*)
- Manual workflow dispatch

**Jobs:**
1. **build-and-push** - Build and publish Docker images
   - GitHub Container Registry
   - Multi-platform support (amd64, arm64)
   - Automated tagging (latest, semver, sha)

2. **deploy-staging** - Deploy to staging (develop branch only)
   - SSH deployment
   - Rolling update
   - Health check verification
   - Slack notification

3. **deploy-production** - Deploy to production (tags only)
   - Database backup creation
   - Rolling update with zero downtime
   - Database migrations
   - Smoke tests
   - Automatic rollback on failure
   - GitHub release creation
   - Slack notification

4. **migration-check** - Database migration validation
   - Test migrations up/down
   - Ensure reversibility

### Docker Publish Workflow (docker-publish.yml)

**Triggers:**
- Weekly schedule (Sundays at 2 AM)
- Push to main/develop
- Version tags
- Pull requests

**Features:**
- Multi-architecture builds (amd64, arm64)
- QEMU emulation for cross-platform
- Advanced caching with GitHub Actions cache
- Vulnerability scanning with Trivy
- Automated tagging strategy

## Branch Strategy

### main
- Production-ready code
- Protected branch
- Requires PR approval
- Deploys to production on tag push

### develop
- Development integration branch
- Deploys to staging on push
- CI runs on all pushes

### feature/*
- Feature branches
- CI runs on PR to develop/main
- No deployment

## Deployment Process

### Staging Deployment
```bash
git checkout develop
git pull origin develop
git push origin develop
# GitHub Actions automatically deploys to staging
```

### Production Deployment
```bash
# Create and push version tag
git checkout main
git pull origin main
git tag -a v1.2.3 -m "Release version 1.2.3"
git push origin v1.2.3
# GitHub Actions automatically deploys to production
```

### Manual Deployment Trigger
1. Go to Actions tab in GitHub
2. Select "Continuous Deployment" workflow
3. Click "Run workflow"
4. Select branch
5. Click "Run workflow"

## Monitoring Deployments

### GitHub Actions Dashboard
- **Actions** tab shows all workflow runs
- Click on workflow run for detailed logs
- View each job's output

### Slack Notifications
- Automatic notifications on deployment success/failure
- Includes deployment status and version

### Health Checks
After deployment, verify:
```bash
# Staging
curl https://staging.disruptiq.com/health
curl https://staging.disruptiq.com/health/detailed

# Production
curl https://disruptiq.com/health
curl https://disruptiq.com/health/detailed
```

## Rollback Procedure

### Automatic Rollback
- Production deployment automatically rolls back on failure
- Restores from latest backup

### Manual Rollback
```bash
# SSH to production server
ssh user@prod-server
cd /opt/disruptiq

# Find latest backup
ls -lt backups/

# Restore database
docker-compose exec -T postgres psql -U $POSTGRES_USER -d disruptiq < backup_YYYYMMDD_HHMMSS.sql

# Restore volumes
BACKUP_FILE="backups/postgres_backup_YYYYMMDD_HHMMSS.tar.gz"
docker run --rm -v disruptiq_postgres_data:/data -v $(pwd)/backups:/backup alpine sh -c "cd /data && tar xzf /backup/$(basename $BACKUP_FILE)"

# Restart services
docker-compose restart
```

## Troubleshooting

### CI Failures

#### Test Failures
```bash
# Run tests locally
cd backend
pytest tests/ -v --cov=app

# Check specific test
pytest tests/test_specific.py -v -s
```

#### Linting Failures
```bash
# Fix formatting
black app/ tests/
isort app/ tests/

# Check linting
flake8 app/
```

#### Coverage Below 85%
```bash
# Generate coverage report
pytest --cov=app --cov-report=html
# Open htmlcov/index.html to see uncovered lines
```

### Deployment Failures

#### SSH Connection Issues
- Verify SSH key is correct in GitHub secrets
- Check server firewall allows SSH from GitHub IPs
- Test SSH manually: `ssh -i key user@server`

#### Docker Issues
```bash
# On server
docker-compose ps  # Check service status
docker-compose logs backend  # View logs
docker system df  # Check disk space
```

#### Database Migration Issues
```bash
# On server
docker-compose exec backend alembic current  # Check current version
docker-compose exec backend alembic history  # View migration history
docker-compose exec backend alembic upgrade head  # Manual upgrade
```

## Security Best Practices

1. **Secrets Management**
   - Never commit secrets to repository
   - Rotate secrets regularly (every 90 days)
   - Use separate secrets for staging/production

2. **SSH Keys**
   - Use dedicated deploy keys
   - Restrict key permissions on server
   - Monitor SSH access logs

3. **Docker Images**
   - Scan images for vulnerabilities
   - Use specific version tags, not `latest` in production
   - Regularly update base images

4. **Database Backups**
   - Automated backups before each deployment
   - Test restore procedures regularly
   - Store backups offsite

## Performance Optimization

### GitHub Actions Caching
- Docker layer caching enabled
- pip/npm dependency caching
- Reduces build time by ~60%

### Parallel Jobs
- Tests run in parallel when possible
- Frontend/backend tests independent

### Resource Limits
- Jobs timeout after 60 minutes
- Can be adjusted in workflow files

## Cost Optimization

### GitHub Actions Minutes
- Free tier: 2,000 minutes/month for private repos
- Monitor usage in Settings → Billing

### Reduce CI Runtime
```yaml
# Skip CI for documentation changes
on:
  push:
    paths-ignore:
      - '**.md'
      - 'docs/**'
```

## Support & Maintenance

### Regular Maintenance Tasks
- [ ] Weekly: Review failed workflows
- [ ] Monthly: Update dependencies
- [ ] Quarterly: Rotate secrets
- [ ] Quarterly: Review and optimize workflows

### Getting Help
- GitHub Actions documentation: https://docs.github.com/actions
- DisruptIQ issues: Create GitHub issue with `ci/cd` label
