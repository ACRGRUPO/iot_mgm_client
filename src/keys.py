import os
import subprocess
import logging

def generate_key_pair(key_path: str, logger: logging.Logger = None) -> None:
    """Generate an SSH key pair if it does not exist."""
    logger = logger or logging.getLogger(__name__)
    if not os.path.exists(key_path):
        logger.info(f"Key pair not found at {key_path}, generating new key pair")
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        result = subprocess.run(
            ["/usr/bin/ssh-keygen", "-t", "rsa", "-b", "2048", "-f", key_path, "-N", ""],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"New key pair generated at {key_path}")
        else:
            logger.error(f"Error generating key pair: {result.stderr}")
            raise Exception("Key generation failed")
    else:
        logger.info(f"Key pair already exists at {key_path}")

def add_public_key_to_authorized_keys(key_path: str, authorized_keys_path: str = "~/.ssh/authorized_keys", logger: logging.Logger = None) -> None:
    """Add the public key to authorized_keys if not already present."""
    logger = logger or logging.getLogger(__name__)
    auth_keys = os.path.expanduser(authorized_keys_path)
    pub_key_file = key_path + ".pub"
    if not os.path.exists(pub_key_file):
        logger.error(f"Public key file not found at {pub_key_file}")
        raise Exception("Public key file missing")
    with open(pub_key_file, "r") as f:
        pub_key = f.read().strip()
    
    # Ensure authorized_keys exists
    if not os.path.exists(auth_keys):
        os.makedirs(os.path.dirname(auth_keys), exist_ok=True)
        open(auth_keys, "w").close()

    with open(auth_keys, "r") as f:
        keys = f.read()
    if pub_key in keys:
        logger.info("Public key already exists in authorized_keys")
    else:
        with open(auth_keys, "a") as f:
            f.write(pub_key + "\n")
        logger.info("Public key added to authorized_keys")

def remove_public_key_from_authorized_keys(key_path: str, authorized_keys_path: str = "~/.ssh/authorized_keys", logger: logging.Logger = None) -> None:
    """Remove the public key from authorized_keys if present."""
    logger = logger or logging.getLogger(__name__)
    auth_keys = os.path.expanduser(authorized_keys_path)
    pub_key_file = key_path + ".pub"
    if not os.path.exists(pub_key_file):
        logger.error(f"Public key file not found at {pub_key_file}")
        return
    with open(pub_key_file, "r") as f:
        pub_key = f.read().strip()
    
    if not os.path.exists(auth_keys):
        logger.info("authorized_keys file does not exist")
        return

    with open(auth_keys, "r") as f:
        lines = f.readlines()
    
    with open(auth_keys, "w") as f:
        for line in lines:
            if pub_key not in line:
                f.write(line)
    logger.info("Public key removed from authorized_keys if it existed")

def empty_know_hosts(logger: logging.Logger = None) -> None:
    """Empty the known_hosts file."""
    logger = logger or logging.getLogger(__name__)
    known_hosts_path = os.path.expanduser("~/.ssh/known_hosts")
    if not os.path.exists(known_hosts_path):
        logger.info("known_hosts file does not exist")
        return
    open(known_hosts_path, "w").close()
    logger.info("known_hosts file emptied")

def read_key(key_path: str, logger: logging.Logger = None) -> str:
    """Get a key from the key file."""
    logger = logger or logging.getLogger(__name__)
    if not os.path.exists(key_path):
        logger.error(f"Key file not found at {key_path}")
        raise Exception("Key file missing")
    with open(key_path, "r") as f:
        key = f.read()
    return key