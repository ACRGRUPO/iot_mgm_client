import os
import json
import subprocess
import requests
import logging
from typing import Dict

default_logger = logging.getLogger(__name__)

class MetadataCollector:
    @staticmethod
    def collect(logger: logging.Logger = default_logger) -> Dict:
        """Collect additional device metadata"""
        metadata = {"kernel": "Unknown", "os": "Unknown", "ip_addresses": {}, "public_ip": "Unknown"}
        
        try:
            # Get kernel version
            kernel = subprocess.check_output(["/usr/bin/uname", "-r"], text=True).strip()
            metadata["kernel"] = kernel
            
            # Get distribution info if available
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            os_name = line.split("=")[1].strip().strip('"')
                            metadata["os"] = os_name
                            break
            
            # Get IP addresses
            ip_info = []
            interfaces = subprocess.check_output(["ip", "-j", "addr"], text=True)
            interfaces_data = json.loads(interfaces)
            
            for interface in interfaces_data:
                if interface["ifname"] != "lo":  # Skip loopback
                    for addr_info in interface.get("addr_info", []):
                        if addr_info.get("family") == "inet":  # IPv4
                            ip_info.append({
                                "name": interface["ifname"],
                                "ip": addr_info["local"],
                                "mac": interface["address"]
                            })
            metadata["ip_addresses"] = ip_info

            try:
                # Get Public IP address
                public_ip = requests.get("https://ipaddress.ai/ip").text
                metadata["public_ip"] = public_ip.splitlines()[0]  # first line
            except Exception as e:
                metadata["public_ip"] = "Unknown"
                logger.warning(f"Error getting public IP address: {str(e)}")
            
            logger.info(f"Collected metadata: {metadata}")
        except Exception as e:
            logger.warning(f"Error collecting metadata: {str(e)}")
        
        return metadata