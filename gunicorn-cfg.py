# -*- encoding: utf-8 -*-
"""
Gunicorn configuration for Azure App Service deployment
"""

# Azure App Service expects port 8000
bind = '0.0.0.0:8000'

# Number of worker processes (recommended: 2-4 for Free tier)
workers = 1

# Timeout for requests (10 minutes for long-running algorithm tasks)
timeout = 600

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
capture_output = True
enable_stdio_inheritance = True
