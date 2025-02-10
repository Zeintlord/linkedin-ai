import os
import yaml
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger

class AIHawkAuthenticator:
    """
    Esta clase se encarga de autenticar en LinkedIn usando Selenium.
    Puede leer las credenciales desde variables de entorno o desde
    un secrets.yaml, si así lo defines.
    """
    def __init__(self, driver):
        self.driver = driver
        with open("data_folder/secrets.yaml", "r") as f:
            secrets = yaml.safe_load(f)
        self.linkedin_email = secrets["linkedin_email"]
        self.linkedin_password = secrets["linkedin_password"]

    def set_credentials(self, email, password):
        """
        Permite setear las credenciales en caso de querer hacerlo manualmente
        en lugar de variables de entorno.
        """
        self.linkedin_email = email
        self.linkedin_password = password

    def start_login(self):
        """
        Abre la página de login de LinkedIn y realiza la autenticación.
        Asume que self.linkedin_email y self.linkedin_password están configurados.
        """
        logger.info("Starting LinkedIn login...")

        # 1. Navegamos a la página de login
        self.driver.get("https://www.linkedin.com/login")

        # 2. Esperamos que aparezca el campo de usuario
        email_input = WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        password_input = self.driver.find_element(By.ID, "password")

        # 3. Ingresamos credenciales
        email_input.clear()
        email_input.send_keys(self.linkedin_email)
        password_input.clear()
        password_input.send_keys(self.linkedin_password)

        # 4. Enviamos el formulario
        password_input.submit()
        logger.debug("Submitted login form.")

        # 5. Esperar a que aparezca algo de la Home (barra de búsqueda, etc.)
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.ID, "global-nav-search"))
        )
        logger.info("LinkedIn login successful.")
