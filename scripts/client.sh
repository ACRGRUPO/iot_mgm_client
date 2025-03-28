#!/bin/bash
set -e

SERVICE_USER="acr_iot"
SERVICE_GROUP="acr_iot"
PROGRAM_NAME="iot_mgm_client"
LOG_DIR="/var/log/$PROGRAM_NAME"
INSTALL_DIR="/opt/$PROGRAM_NAME"
SERVICE_FILE="/etc/systemd/system/$PROGRAM_NAME.service"

# check params "configure, install, uninstall, configure_Service"
if [ "$1" != "configure" ] && [ "$1" != "install" ] && [ "$1" != "uninstall" ] && [ "$1" != "configure_service" ] && [ "$1" != "update" ]; then
    echo "Usage: $0 [configure|install|uninstall|configure_service|update]"
    exit 1
fi

if [ "$1" == "install" ]; then
    # Create group if it doesn't exist
    if ! getent group "$SERVICE_GROUP" > /dev/null; then
        echo "Creating group $SERVICE_GROUP..."
        sudo groupadd --system "$SERVICE_GROUP"
    fi

    # Create user if it doesn't exist
    if ! id -u "$SERVICE_USER" > /dev/null 2>&1; then
        echo "Creating user $SERVICE_USER with home directory..."
        sudo adduser --gecos "" --ingroup "$SERVICE_GROUP" "$SERVICE_USER"
    fi

    # Create log directory if it doesn't exist and set proper ownership/permissions
    if [ ! -d "$LOG_DIR" ]; then
        echo "Creating log directory $LOG_DIR..."
        sudo mkdir -p "$LOG_DIR"
    fi

    echo "Setting ownership and permissions for $LOG_DIR..."
    sudo chown "$SERVICE_USER":"$SERVICE_GROUP" "$LOG_DIR"
    sudo chmod 750 "$LOG_DIR"

    echo "User, group, and log directory setup complete."

    echo "Setting up the installation directory..."
    # deploy to /opt/iot_mgm_client
    sudo cp -r ../iot_mgm_client $INSTALL_DIR
    sudo chown -R $SERVICE_USER:$SERVICE_GROUP $INSTALL_DIR
    sudo chmod -R 755 $INSTALL_DIR
    echo "Installation directory setup complete."

    # copy the service file
    echo "Copying the service file..."
    sudo cp ./scripts/iot_mgm_client.service $SERVICE_FILE
fi

if [ "$1" == "configure" ]; then
    echo "Configuring the service..."
    # create the log file
    sudo touch $LOG_DIR/iot_mgm_client.log
    sudo chown $SERVICE_USER:$SERVICE_GROUP $LOG_DIR/iot_mgm_client.log
    sudo chmod 640 $LOG_DIR/iot_mgm_client.log

    # reload the systemd manager configuration
    echo "Reloading the systemd manager configuration..."
    sudo systemctl daemon-reload

    # enable the service
    echo "Enabling the service..."
    sudo systemctl enable iot_mgm_client.service
    sudo systemctl status iot_mgm_client.service
fi

if [ "$1" == "uninstall" ]; then
    echo "You are about to uninstall the service. This will stop the service, remove the installation directory"
    echo "You must do it locally on the device."
    read -p "Do you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    echo "Uninstalling the service..."
    # stop the service
    sudo systemctl stop iot_mgm_client.service
    # disable the service
    sudo systemctl disable iot_mgm_client.service
    # remove the service file
    sudo rm /etc/systemd/system/iot_mgm_client.service
    # remove the installation directory
    sudo rm -rf $INSTALL_DIR
    # remove the log directory
    sudo rm -rf $LOG_DIR
    # remove the user
    sudo userdel $SERVICE_USER
    # remove the group
    sudo groupdel $SERVICE_GROUP
fi

if [ "$1" == "configure_service" ]; then
    # copy the service file
    echo "Copying the service file..."
    sudo cp ./scripts/iot_mgm_client.service $SERVICE_FILE
    echo "Updating the service file..."
    # update the service file
    sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|" "$SERVICE_FILE"
    sudo sed -i "s#Environment=PATH=.*:\(\$PATH\)\$#Environment=PATH=${INSTALL_DIR}:\1#g" "$SERVICE_FILE"
    sudo sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 ./src/client.py|" "$SERVICE_FILE"
    sudo sed -i "s|User=.*|User=$SERVICE_USER|" "$SERVICE_FILE"
    sudo sed -i "s|Group=.*|Group=$SERVICE_GROUP|" "$SERVICE_FILE"
    # show the service file
    sudo cat $SERVICE_FILE
fi

if [ "$1" == "update" ]; then
    echo "You are about to update the service. This will stop the service, remove the installation directory, and deploy the new version."
    read -p "Do you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    # check if we are inside the git repository
    if [ ! -d ".git" ]; then
        echo "This script must be run from the git repository."
        exit 1
    fi
    echo "Updating the service..."
    git reset --hard
    git fetch
    git pull
    chmod +x ./scripts/client.sh
    chmod +x ./scripts/restart_service.sh
    
    # save .env file to /tmp
    echo "Saving the .env file..."
    sudo cp $INSTALL_DIR/.env /tmp/iot_mgm_client.env
    # remove the installation directory
    echo "Cleaning up the installation directory..."
    sudo rm -rf $INSTALL_DIR
    echo "Deploying the new version..."
    # deploy to /opt/iot_mgm_client
    sudo cp -r ../iot_mgm_client $INSTALL_DIR
    sudo chown -R $SERVICE_USER:$SERVICE_GROUP $INSTALL_DIR
    sudo chmod -R 755 $INSTALL_DIR
    echo "Restoring the .env file..."
    # copy .env file back
    sudo cp /tmp/iot_mgm_client.env $INSTALL_DIR/.env
    
    # restart the service
    echo "Restarting the service..."
    sudo nohup ./scripts/restart_service.sh > update.log 2>&1 &
    backgroup_pid=$!
    sleep 5
    if ps -p $backgroup_pid > /dev/null
    then        
        sudo systemctl status iot_mgm_client.service
    else
        echo "Service failed to restart. Check the logs in /var/log/iot_mgm_client/iot_mgm_client.log and update.log."

fi