#!/bin/bash
# Quick test runner

cd "/Users/amoghreddy/Desktop/Prediction Markets"

echo "🧪 Running Unit Tests..."
echo ""

"/Users/amoghreddy/Desktop/Prediction Markets/venv/bin/python" -m unittest discover -s tests -p 'test_*.py' -v

echo ""
echo "=" * 70
echo "✅ Test run complete!"
echo ""
echo "To run specific tests:"
echo "  python -m unittest tests.test_bayesian -v"
echo "  python -m unittest tests.test_matcher -v"
echo "  python -m unittest tests.test_config -v"
echo "  python -m unittest tests.test_api_clients -v"
