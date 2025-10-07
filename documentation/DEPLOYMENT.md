# Deployment Guide

## Prerequisites

### For GitHub Actions CI/CD
1. GitHub repository with Actions enabled
2. Access to target Ubuntu server (SSH)
3. Docker and Docker Compose installed on server

### GitHub Secrets Configuration

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

| Secret Name | Description | Example |
|------------|-------------|---------|
| `SSH_HOST` | Server IP or hostname | `203.0.113.10` |
| `SSH_USER` | SSH username | `ubuntu` |
| `SSH_KEY` | Private SSH key | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `SSH_PORT` | SSH port (optional) | `22` |
| `DEPLOY_PATH` | Deployment directory | `~/speech-to-text-service` |

**Note**: The `GITHUB_TOKEN` is automatically provided by GitHub Actions.

## Server Setup

### 1. Initial Server Configuration

SSH into your Ubuntu server:

```bash
ssh ubuntu@YOUR_SERVER_IP
```

### 2. Install Docker

```bash
# Update package index
sudo apt-get update

# Install dependencies
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up stable repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in for group changes to take effect
```

### 3. Prepare Deployment Directory

```bash
# Create deployment directory
mkdir -p ~/speech-to-text-service
cd ~/speech-to-text-service

# Clone repository (optional - if you want to use git pull in deploy script)
git clone https://github.com/YOUR_USERNAME/speech-to-text-service.git .

# Or just create necessary files
mkdir -p models
```

### 4. Create Environment File

```bash
# Copy example and edit
cp .env.example .env
nano .env
```

Edit `.env` with your configuration:
```bash
MODEL_SIZE=small
COMPUTE_TYPE=int8
MAX_FILE_MB=30
MAX_DURATION_SEC=600
```

### 5. Update docker-compose.yml

Edit `docker-compose.yml` and replace `your-org` with your GitHub username:

```yaml
services:
  stt:
    image: ghcr.io/YOUR_USERNAME/speech-to-text-service:latest
    # ... rest of config
```

## Deployment Methods

### Method 1: Automatic (via GitHub Actions) - Recommended

1. **Push to main branch**:
   ```bash
   git add .
   git commit -m "Deploy changes"
   git push origin main
   ```

2. **Monitor deployment**:
   - Go to GitHub repository → Actions tab
   - Watch CI workflow complete
   - Watch Deploy workflow run automatically

3. **Verify deployment**:
   ```bash
   curl http://YOUR_SERVER_IP:8000/health
   ```

### Method 2: Manual Deployment

On your server:

```bash
cd ~/speech-to-text-service

# Login to GitHub Container Registry
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Pull latest image
docker compose pull

# Start services
docker compose up -d

# Check status
docker compose ps
docker compose logs -f
```

## Verification

### 1. Health Check

```bash
curl http://YOUR_SERVER_IP:8000/health
```

Expected response:
```json
{"status":"ok"}
```

### 2. Transcribe Test

```bash
curl -X POST http://YOUR_SERVER_IP:8000/transcribe \
  -F "file=@samples/hello.m4a"
```

### 3. Web Client

Open in browser:
```
http://YOUR_SERVER_IP:8000/web
```

## Troubleshooting

### Check Logs

```bash
# All logs
docker compose logs

# Follow logs
docker compose logs -f

# Specific service
docker compose logs stt
```

### Restart Service

```bash
docker compose restart
```

### Rebuild and Restart

```bash
docker compose down
docker compose up -d --build
```

### Check Container Status

```bash
docker compose ps
docker ps -a
```

### Check Disk Space

```bash
df -h
docker system df
```

### Clean Up Old Images

```bash
docker image prune -a
docker system prune -a
```

## Firewall Configuration

If using UFW (Ubuntu Firewall):

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP
sudo ufw allow 8000/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

## SSL/TLS Setup (Optional)

For production, use a reverse proxy with SSL:

### Using Nginx + Let's Encrypt

```bash
# Install Nginx
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Configure Nginx
sudo nano /etc/nginx/sites-available/stt-service

# Add configuration:
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/stt-service /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

## Monitoring

### Check Resource Usage

```bash
# CPU and Memory
docker stats

# Disk usage
docker system df
du -sh models/
```

### Set Up Log Rotation

Create `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Restart Docker:
```bash
sudo systemctl restart docker
```

## Rollback

If deployment fails:

```bash
# Use previous image tag
docker compose pull ghcr.io/YOUR_USERNAME/speech-to-text-service:PREVIOUS_SHA

# Or rebuild from specific commit
git checkout PREVIOUS_COMMIT
docker compose up -d --build
```

## Support

For issues:
1. Check logs: `docker compose logs -f`
2. Verify environment variables: `docker compose config`
3. Check GitHub Actions logs
4. Review CHECKLIST.md for missing items
