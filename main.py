import os
import re
import sys
from pathlib import Path
import yaml
import click
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from src.utils import chrome_browser_options
from src.aihawk_authenticator import AIHawkAuthenticator
from src.aihawk_job_manager import AIHawkJobManager
from loguru import logger

class ConfigError(Exception):
    pass

class ConfigValidator:
    @staticmethod
    def validate_yaml_file(yaml_path: Path) -> dict:
        try:
            with open(yaml_path, 'r') as stream:
                return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Error reading file {yaml_path}: {exc}")
        except FileNotFoundError:
            raise ConfigError(f"File not found: {yaml_path}")

    @staticmethod
    def validate_config(config_yaml_path: Path) -> dict:
        parameters = ConfigValidator.validate_yaml_file(config_yaml_path)
        if not isinstance(parameters, dict):
            raise ConfigError(f"Config file {config_yaml_path} is not a valid dictionary.")
        return parameters

    @staticmethod
    def validate_secrets(secrets_yaml_path: Path) -> dict:
        secrets = ConfigValidator.validate_yaml_file(secrets_yaml_path)
        return secrets

def init_browser() -> webdriver.Chrome:
    try:
        options = chrome_browser_options()
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize browser: {str(e)}")

def create_and_run_bot(parameters, secrets):
    try:
        browser = init_browser()

        # Autenticación en LinkedIn
        login_component = AIHawkAuthenticator(browser)
        login_component.start_login()

        # Búsqueda y aplicación a trabajos
        job_manager = AIHawkJobManager(browser)
        job_title = parameters.get("job_title", "Head of Sales")
        location = parameters.get("location", "United States")

        job_manager.start_search(job_title, location)  # Hace la búsqueda
        job_manager.apply_to_jobs()  # Aplica a los trabajos encontrados

        logger.info("Proceso de aplicación completado.")

    except WebDriverException as e:
        logger.error(f"WebDriver error occurred: {e}")
    except Exception as e:
        raise RuntimeError(f"Error running the bot: {str(e)}")

@click.command()
@click.option('--resume', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path), help="Path to the resume PDF file")
def main(resume: Path = None):
    try:
        data_folder = Path("data_folder")
        secrets_file = data_folder / "secrets.yaml"
        config_file = data_folder / "config.yaml"

        parameters = ConfigValidator.validate_config(config_file)
        secrets = ConfigValidator.validate_secrets(secrets_file)

        create_and_run_bot(parameters, secrets)

    except ConfigError as ce:
        logger.error(f"Configuration error: {str(ce)}")
    except FileNotFoundError as fnf:
        logger.error(f"File not found error: {str(fnf)}")
    except RuntimeError as re:
        logger.error(f"Runtime error: {str(re)}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()
