#!/bin/bash
# Script to generate htpasswd file for nginx basic authentication
# This provides an optional security layer for the dashboard

echo "====================================="
echo "DMARC Dashboard Basic Auth Setup"
echo "====================================="
echo ""
echo "This will create a password-protected login for your dashboard."
echo ""

# Check if htpasswd is installed
if ! command -v htpasswd &> /dev/null; then
    echo "Error: htpasswd command not found"
    echo ""
    echo "Install apache2-utils:"
    echo "  Ubuntu/Debian: sudo apt-get install apache2-utils"
    echo "  CentOS/RHEL: sudo yum install httpd-tools"
    echo "  macOS: brew install httpd"
    exit 1
fi

# Get username
read -p "Enter username for dashboard access: " username

if [ -z "$username" ]; then
    echo "Error: Username cannot be empty"
    exit 1
fi

# Create htpasswd file
htpasswd_file="nginx/.htpasswd"

# Create directory if it doesn't exist
mkdir -p nginx

# Generate password
echo ""
echo "Creating password for user: $username"
htpasswd -c "$htpasswd_file" "$username"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Password file created successfully: $htpasswd_file"
    echo ""
    echo "Next steps:"
    echo "1. Copy nginx/nginx-auth.conf.example to nginx/nginx.conf"
    echo "2. Uncomment the auth_basic lines in nginx.conf"
    echo "3. Restart nginx: docker-compose restart nginx"
    echo ""
    echo "To add more users:"
    echo "  htpasswd $htpasswd_file <username>"
else
    echo ""
    echo "✗ Failed to create password file"
    exit 1
fi
