#!/bin/bash
set -e

echo "Starting application..."

# Find actual app and virtual environment directories
if [ -f "/home/site/wwwroot/manage.py" ]; then
    APP_DIR="/home/site/wwwroot"
    # Check for antenv in multiple locations
    if [ -d "$APP_DIR/antenv" ]; then
        VENV_DIR="$APP_DIR/antenv"
    elif [ -d "/tmp/8de"*"/antenv" ]; then
        VENV_DIR=$(find /tmp -maxdepth 2 -type d -name "antenv" 2>/dev/null | head -1)
    fi
else
    # App extracted to /tmp by Oryx
    APP_DIR=$(find /tmp -maxdepth 1 -type d -name "8de*" 2>/dev/null | head -1)
    if [ -n "$APP_DIR" ] && [ -f "$APP_DIR/manage.py" ]; then
        VENV_DIR="$APP_DIR/antenv"
    else
        echo "ERROR: Cannot find app directory with manage.py"
        exit 1
    fi
fi

echo "App directory: $APP_DIR"
echo "Virtual env: $VENV_DIR"

cd "$APP_DIR"

# Activate virtual environment
if [ -n "$VENV_DIR" ] && [ -d "$VENV_DIR" ]; then
    echo "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
else
    echo "WARNING: Virtual environment not found!"
fi

# Show Python info
echo "Python: $(which python)"
echo "Python version: $(python --version)"

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput || echo "Migration failed"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || echo "Collectstatic failed"

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --timeout 600 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
