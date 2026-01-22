#!/bin/bash
FLYCTL="/home/itzzonk/.fly/bin/flyctl"

echo "Step 1: Authenticating..."
$FLYCTL auth login

echo "Step 2: Launching app configuration..."
# This generates fly.toml if not exists
if [ ! -f "fly.toml" ]; then
    $FLYCTL launch --no-deploy
else
    echo "fly.toml already exists, skipping launch configuration."
fi

echo "Step 3: Deploying..."
$FLYCTL deploy

echo "Done! Your app should be live."
