import os
import sys
import logging
import socket

def load_env_file(filepath=".env") -> dict:
    env_vars = {}
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                env_vars[key] = value
                os.environ[key] = value
        return env_vars
    except FileNotFoundError:
        logging.error(f"Environment file not found: {filepath}")
        sys.exit(1)

def validate_config(config: dict) -> None:
    required_fields = {
        "SERVER_URL": "SERVER_URL is required",
        "DEVICE_ID": "DEVICE_ID is required"
    }
    for key, msg in required_fields.items():
        if not config.get(key):
            logging.error(msg)
            sys.exit(1)
    if not config.get("API_SECRET_TOKEN") or not config.get("KEY_FILE"):
        logging.error("API_SECRET_TOKEN and KEY_FILE are required")
        sys.exit(1)

def load_config() -> dict:
    env_vars = load_env_file()
    config = {}
    config["SERVER_URL"] = env_vars.get("SERVER_URL", "")
    config["API_SECRET_TOKEN"] = env_vars.get("API_SECRET_TOKEN", "")
    config["DEVICE_ID"] = env_vars.get("DEVICE_ID") or socket.gethostname()
    ssh_local_port = env_vars.get("SSH_LOCAL_PORT", "22")
    config["SSH_LOCAL_PORT"] = int(ssh_local_port) if ssh_local_port.isdigit() else ""
    config["HEARTBEAT_INTERVAL"] = int(env_vars.get("HEARTBEAT_INTERVAL", "60"))
    config["TUNNEL_INTERVAL"] = int(env_vars.get("TUNNEL_INTERVAL", "120"))
    config["MAX_RECONNECT_DELAY"] = int(env_vars.get("MAX_RECONNECT_DELAY", "300"))
    config["LOG_FILE"] = env_vars.get("LOG_FILE", "/var/log/acr_iot_client.log")
    config["KEY_FILE"] = env_vars.get("KEY_FILE", "")
    config["LOG_LEVEL"] = env_vars.get("LOG_LEVEL", "INFO")

    validate_config(config)
              
    config["KEY_FILE"] = os.path.expanduser(os.path.join("~/.ssh", config["KEY_FILE"]))
              
    return config
