import json
import logging
import os
import random
import signal
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from typing import Dict, Optional
import requests

from metadata import MetadataCollector
from env_config import load_config

# my_application.py
import logging.config
from log_config import client_log_config
import keys

# Configure logging using the imported log_config
logging.config.dictConfig(client_log_config)

# Get the logger
logger = logging.getLogger("iot_mgm_client")

# Load configuration
config = load_config()
SERVER_URL = config["SERVER_URL"]
API_SECRET_TOKEN = config["API_SECRET_TOKEN"]
DEVICE_ID = config["DEVICE_ID"]
SSH_LOCAL_PORT = config["SSH_LOCAL_PORT"]
HEARTBEAT_INTERVAL = config["HEARTBEAT_INTERVAL"]
TUNNEL_INTERVAL = config["TUNNEL_INTERVAL"]
MAX_RECONNECT_DELAY = config["MAX_RECONNECT_DELAY"]
LOG_FILE = config["LOG_FILE"]
LOG_LEVEL = config["LOG_LEVEL"].upper()

logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logger.info(f"===== Starting Remote Client Agent for device {DEVICE_ID}")
logger.info(f"Server URL: {SERVER_URL}")
logger.info(f"Log Level.: {LOG_LEVEL}")

class RemoteClientAgent:
    def __init__(self):
        self.device_id = DEVICE_ID
        self.hostname = socket.gethostname()
        self.ssh_process = None
        self.tunnel_config = None
        self.running = True
        self.reconnect_delay = 1
        self.private_key_file = None
        self.last_heartbeat_time = 0
        self.last_tunnel_time = 0
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)
        
        try:
            # Get additional metadata
            # REMOVE self.metadata = self.collect_device_metadata()
            self.metadata = MetadataCollector.collect(logger = logger)
        except Exception as e:
            logger.error(f"Error initializing agent obtaining metadata: {str(e)}")
            sys.exit(1)

        try:
            # Obtain hostname
            self.device_id = str(socket.gethostname())
            # Device ID is a combination device + mac
            self.device_id = f"{self.device_id}-{self.metadata['ip_addresses'][0]['mac']}"
        except Exception as e:
            logger.error(f"Error initializing agent obtaining device ID: {str(e)}")
            sys.exit(1)
    
    def ensure_key_pair_exists(self):
        """Ensure that the SSH key pair exists, create it if it doesn't"""
        key_path = os.path.expanduser("~/.ssh/acr_iot")
        
        keys.generate_key_pair(key_path, logger)
        keys.remove_public_key_from_authorized_keys(key_path, logger=logger)
        keys.add_public_key_to_authorized_keys(key_path, logger=logger)

    def terminate_ssh_process(self):
        """Terminate the SSH tunnel if it is running."""
        if self.ssh_process:
            logger.info("Terminating SSH process")
            self.ssh_process.terminate()
            try:
                self.ssh_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ssh_process.kill()
            self.ssh_process = None

    def register_with_server(self) -> bool:
        # Ensure no SSH process is running before registration
        if self.ssh_process:
            logger.info("Terminating existing SSH process before registration")
            self.terminate_ssh_process()
            
        try:
            # Ensure the key pair exists
            self.ensure_key_pair_exists()

            # Read client private key from ~/.ssh/acr_iot
            key_path = os.path.expanduser("~/.ssh/acr_iot")            
            private_key = keys.read_key(key_path, logger)
            key_path = os.path.expanduser("~/.ssh/acr_iot.pub")            
            public_key = keys.read_key(key_path, logger)
            
            response = requests.post(
                f"{SERVER_URL}/register",
                headers={"X-API-Key": API_SECRET_TOKEN},
                json={
                    "device_id": self.device_id,
                    "hostname": self.hostname,
                    "metadata": self.metadata,
                    "private_key": private_key,
                    "public_key": public_key
                },
                timeout=30
            )
            
            if response.status_code == 200:
                self.tunnel_config = response.json()
                logger.debug("Registration response: %s", self.tunnel_config)  # new detailed logging
            
                # Validate that the tunnel configuration includes the access key, port, and server_ip
                if not all(key in self.tunnel_config for key in ("port", "server_ip")):
                    logger.error("Invalid tunnel configuration received from server")
                    return False
                logger.info(f"Successfully registered with server. Port: {self.tunnel_config['port']}")
                return True
            else:
                logger.error(f"Failed to register with server: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error registering with server: {str(e)}")
            return False
    
    def setup_ssh_tunnel(self) -> bool:
        """Set up SSH reverse tunnel based on server configuration"""
        if not self.tunnel_config:
            logger.error("No tunnel configuration available")
            return False
        
        try:
                        
            # New tunnel cleanup
            keys.empty_know_hosts(logger)

            # Build SSH command for reverse tunnel
            ssh_cmd = [
                "/usr/bin/ssh",
                "-vvv" if LOG_LEVEL == "DEBUG" else "-q",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-i", os.path.expanduser('~/.ssh/acr_iot'),
                "-R", f"{self.tunnel_config['port']}:localhost:{SSH_LOCAL_PORT}",
                "-N",  # Don't execute a remote command
                f"acr_iot@{self.tunnel_config['server_ip']}"
            ]
            
            # Start SSH process
            logger.info(f"Starting SSH tunnel: {' '.join(ssh_cmd)}")
            self.ssh_process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Reset reconnect delay on successful connection
            self.reconnect_delay = 1
            logger.info("SSH tunnel established successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up SSH tunnel: {str(e)}")
            return False
    

    def is_heartbeat_due(self) -> bool:
        """Return True if enough time has elapsed since the last heartbeat."""
        current_time = time.time()
        return (current_time - self.last_heartbeat_time) >= HEARTBEAT_INTERVAL

    def is_tunnel_due(self) -> bool:
        """Return True if enough time has elapsed since the last tunnel check."""
        current_time = time.time()
        return (current_time - self.last_tunnel_time) >= TUNNEL_INTERVAL

    def active_tunnel_test(self) -> bool:
        """Actively test if the SSH tunnel is forwarding connections."""
        if not self.tunnel_config or not self.ssh_process:
            return False        
        
        # Only perform the test if the heartbeat interval has elapsed
        if not self.is_tunnel_due():
            return True
        
        # temprary disable tunnel test
        return True

        server_ip = self.tunnel_config.get("server_ip")
        port = self.tunnel_config.get("port")        
        logger.debug(f"Testing tunnel to {server_ip}:{port}")        
        try:
            with socket.create_connection((server_ip, port), timeout=5):
                logger.debug("Active tunnel test succeeded")
                self.last_tunnel_time = time.time()
                return True
        except Exception as e:
            logger.warning(f"Active tunnel test failed: {str(e)}")            
            return False

    def send_heartbeat(self) -> bool:
        """Send heartbeat message to server"""
        current_time = time.time()
        
        # Only perform the test if the heartbeat interval has elapsed
        if not self.is_heartbeat_due():
            return True
        
        try:
            response = requests.post(
                f"{SERVER_URL}/heartbeat",
                headers={"X-API-Key": API_SECRET_TOKEN},
                json={"device_id": self.device_id},
                timeout=10
            )
            
            if response.status_code == 200:
                self.last_heartbeat_time = current_time
                logger.debug("Heartbeat sent successfully")
                return True
            elif response.status_code == 404:
                logger.info("Heartbeat received 404: device not registered, attempting to register.")
                if self.register_with_server():
                    # Retry heartbeat after successful registration
                    return self.send_heartbeat()
                else:
                    logger.warning("Re-registration failed after 404 heartbeat.")
                    return False
            else:
                logger.warning(f"Failed to send heartbeat: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.warning(f"Error sending heartbeat: {str(e)}")
            return False
    
    def monitor_ssh_process(self) -> bool:
        """Check SSH process status and restart if needed"""
        if not self.ssh_process:
            return False
        
        # Check if process is still running
        if self.ssh_process.poll() is not None:
            exit_code = self.ssh_process.returncode
            stdout, stderr = self.ssh_process.communicate()
            
            logger.warning(f"SSH process terminated with exit code {exit_code}")
            if stdout:
                logger.debug(f"SSH stdout: {stdout}")
            if stderr:
                logger.warning(f"SSH stderr: {stderr}")
            
            self.ssh_process = None
            return False
        
        return True
    
    def handle_exit(self, signum, frame):
        """Handle process termination signals"""
        logger.info(f"Received signal {signum}, shutting down")
        self.running = False
        
        # Clean up resources
        if self.ssh_process:
            logger.info("Terminating SSH process")
            self.terminate_ssh_process()
        
        if self.private_key_file:
            try:
                os.unlink(self.private_key_file.name)
            except Exception as e:
                logger.warning(f"Error removing private key file: {str(e)}")
        
        sys.exit(0)
    
    def _increase_reconnect_delay(self):
        """ Increase the reconnect delay exponentially, up to a maximum value """
        self.reconnect_delay = min(self.reconnect_delay * 2, MAX_RECONNECT_DELAY)

    def _retry(self, action: str):
        """ Log a retry message and sleep for the reconnect delay """
        logger.error(f"{action} failed, retrying in {self.reconnect_delay} seconds")
        time.sleep(self.reconnect_delay)
        self._increase_reconnect_delay()
    
    def run(self):
        """Main loop"""
        logger.info(f"Starting Remote Client Agent for device {self.device_id}")
        
        while self.running:
            # Check SSH process status
            if not self.monitor_ssh_process():
                logger.info("SSH tunnel not active, initiating connection")
                
                # Register with server if needed
                if not self.tunnel_config and not self.register_with_server():
                    self._retry("Server registration")
                    continue
                
                # Setup SSH tunnel
                if not self.setup_ssh_tunnel():
                    self._retry("SSH tunnel setup")
                    continue
            
            if not self.send_heartbeat() and self.ssh_process:
                logger.info("Heartbeat failed: terminating SSH tunnel to force reconnection")
                self.terminate_ssh_process()
            
            # Perform active tunnel test
            if self.tunnel_config and self.ssh_process:
                if not self.active_tunnel_test():
                   logger.warning("Active tunnel test failed: terminating SSH tunnel to force reconnection")
                   self.terminate_ssh_process()
            
            # Small sleep to avoid CPU spinning
            time.sleep(5)

if __name__ == "__main__":
    agent = RemoteClientAgent()
    agent.run()