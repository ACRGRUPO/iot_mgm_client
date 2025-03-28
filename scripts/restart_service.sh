#!/bin/bash

# stop the service
echo "Stopping the service..."
sudo systemctl stop iot_mgm_client.service

# start the service
echo "Starting the service..."
sudo systemctl start iot_mgm_client.service
sudo systemctl status iot_mgm_client.service

