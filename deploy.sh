#!/bin/bash

echo "🚀 Face Access Control System - Deployment Script"
echo "=================================================="

# Check if .env exists
if [ ! -f "backend/.env" ]; then
    echo "⚠️  Creating .env file from example..."
    cp backend/.env.example backend/.env
    echo "✅ Please edit backend/.env with your configuration"
    echo "   Especially update SECRET_KEY and POSTGRES_PASSWORD"
    read -p "Press enter to continue after editing .env file..."
fi

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker compose down

# Build and start services
echo "🏗️  Building and starting services..."
docker compose up -d --build

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 10

# Check health
echo "🏥 Checking service health..."
curl -f http://localhost/health || echo "❌ Backend not responding"

# Show status
echo ""
echo "📊 Service Status:"
docker compose ps

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Access the system at:"
echo "  🏠 Home: http://localhost"
echo "  📋 Organizer: http://localhost/organizer"
echo "  ✨ Register: http://localhost/register"
echo "  🚪 Access Check: http://localhost/access"
echo ""
echo "📝 View logs with: docker compose logs -f"
echo "🔄 Restart with: docker compose restart"
echo "🛑 Stop with: docker compose down"
echo ""
