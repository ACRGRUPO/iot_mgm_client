# IOT Management Client

## Overview

`client.sh` is a client script that manages interactions with the IoT management system. It supports operations such as installing, configuring, and uninstalling the service, as well as updating the service configuration. The script handles user and group creation, deployment of the installation directory, and systemd service management.

## Usage

1. Ensure `client.sh` is executable:
   ```
   chmod +x client.sh
   ```

2. Run the script with one of these options:
   - `install`: Sets up the system by creating necessary user and group, deploying the application, and copying the service file.
   - `configure`: Configures the service by creating log files, reloading systemd, and enabling the service.
   - `uninstall`: Removes the service, its files, and associated user/group.
   - `configure_Service`: Copies and updates the service file settings.
   
   Example:
   ```
   ./client.sh install
   ```

