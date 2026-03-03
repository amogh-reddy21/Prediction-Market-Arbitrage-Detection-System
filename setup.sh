#!/bin/bash

# Prediction Market Arbitrage System Setup Script

set -e

echo "🚀 Setting up Prediction Market Arbitrage System..."

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

echo "✓ Python 3 found"

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed."
    exit 1
fi

echo "✓ Node.js found"

# Check for MySQL
if ! command -v mysql &> /dev/null; then
    echo "❌ MySQL is required but not installed."
    echo "Install with: brew install mysql"
    exit 1
fi

echo "✓ MySQL found"

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from example..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys and MySQL credentials"
else
    echo "✓ .env file already exists"
fi

# Create Python virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✓ Python dependencies installed"

# Setup database
echo "🗄️  Setting up MySQL database..."
echo "Please enter your MySQL root password when prompted:"

mysql -u root -p << EOF
SOURCE schema.sql;
EOF

echo "✓ Database initialized"

# Setup frontend
echo "⚛️  Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo "✓ Frontend dependencies installed"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API credentials"
echo "2. Start the data collector: source venv/bin/activate && python src/scheduler.py"
echo "3. Start the API server (new terminal): source venv/bin/activate && python src/app.py"
echo "4. Start the frontend (new terminal): cd frontend && npm start"
echo ""
echo "Dashboard will be available at: http://localhost:3000"
echo "API will be available at: http://localhost:5000"
