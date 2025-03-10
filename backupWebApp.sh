#!/bin/bash

# Get the current date and time in the format DD-MM-YYYY_HH-MM
TIMESTAMP=$(date +"%d-%m-%Y_%H-%M")

# Get the current directory name
CURRENT_DIR=$(basename "$PWD")

# Define the backup filename
BACKUP_NAME="web_app_${TIMESTAMP}.tar.gz"

# Define the backup directory (one level up)
BACKUP_DIR="../backup"

# Create the backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create a tar.gz archive of the current directory and place it in the backup folder
tar -czf "$BACKUP_DIR/$BACKUP_NAME" . 

# Print success message
echo "Backup created: $BACKUP_DIR/$BACKUP_NAME"

