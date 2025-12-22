# Quick Start Guide - Get Running in 10 Minutes

## Step 1: Prepare Server (2 minutes)

```bash
# SSH into your Contabo server
ssh root@89.117.49.7

# Install Docker if not present
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
apt-get install docker-compose-plugin -y
```

## Step 2: Deploy Application (3 minutes)

```bash
# Clone the repository
cd /opt
git clone https://github.com/abdulahshahid/face-access-prototype-.git face-access
cd face-access

# Configure environment
cp backend/.env.example backend/.env

# Generate secret key and edit .env
echo "SECRET_KEY=$(openssl rand -hex 32)" >> backend/.env
nano backend/.env  # Update POSTGRES_PASSWORD

# Deploy!
chmod +x deploy.sh
./deploy.sh
```

## Step 3: Verify It Works (2 minutes)

```bash
# Check services
docker compose ps

# Test health endpoint
curl http://localhost/health

# Should return: {"status":"healthy","database":"connected","service":"face-access-control"}
```

## Step 4: Test the Flow (3 minutes)

### Upload Attendees
1. Open browser: `http://YOUR_SERVER_IP/organizer`
2. Upload the sample CSV: `sample_attendees.csv`
3. Copy an invite link

### Register a User
1. Open the invite link (or go to `/register`)
2. Enter the invite code
3. Allow camera access
4. Take a selfie
5. Complete registration

### Test Access Control
1. Go to `http://YOUR_SERVER_IP/access`
2. Start camera
3. Click "Check Access"
4. Should show "OK ✅" if you just registered

## Done! 🎉

Your system is now running at:
- Home: http://YOUR_SERVER_IP/
- Organizer: http://YOUR_SERVER_IP/organizer
- Register: http://YOUR_SERVER_IP/register  
- Access: http://YOUR_SERVER_IP/access

## Common Issues & Fixes

### "Cannot connect to Docker daemon"
```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### "Port already in use"
```bash
# Check what's using port 80
sudo lsof -i :80
# Stop it or change nginx port in docker-compose.yml
```

### "Camera not working"
- Use HTTPS (camera requires secure context)
- Check browser permissions
- Try Chrome/Firefox

### "Face not detected"
- Ensure good lighting
- Face camera directly
- Remove glasses/mask

## Next Steps

1. **Add SSL**: Follow DEPLOYMENT_GUIDE.md SSL section
2. **Configure domain**: Point your domain to server IP
3. **Set up backups**: Run the backup script daily
4. **Monitor logs**: `docker compose logs -f`

## Useful Commands

```bash
# View logs
docker compose logs -f

# Restart services
docker compose restart

# Stop everything
docker compose down

# Update and restart
git pull && docker compose up -d --build

# Access database
docker compose exec postgres psql -U faceaccess -d faceaccess
```

## Test Data

Use `sample_attendees.csv` for testing:
- 10 sample attendees
- Valid name and email format
- Ready to upload

## Production Checklist Before Going Live

- [ ] Changed SECRET_KEY in .env
- [ ] Changed POSTGRES_PASSWORD in .env  
- [ ] Enabled firewall (ports 22, 80, 443 only)
- [ ] Set up SSL certificate
- [ ] Tested registration flow
- [ ] Tested access check
- [ ] Set up backups
- [ ] Tested backup restore

## Support

- Documentation: README.md
- Detailed deployment: DEPLOYMENT_GUIDE.md
- Issues: Check `docker compose logs -f`

**Good luck with your demo tomorrow! 🚀**