client_log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] - %(levelname)s - %(funcName)s - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "stream": "ext://sys.stderr",
        },
        "file": {  
            "class": "logging.FileHandler",
            "formatter": "default",
            "filename": "/var/log/iot_mgm_client/iot_mgm_client.log",  
            "mode": "a", 
        },
    },
    "loggers": {
        "iot_mgm_client": {
            "handlers": ["console", "file"], 
            "level": "INFO",
            "propagate": False,
        },
    },
    "root":{
        "level":"WARNING",
        "handlers":["console","file"] 
    }
}

