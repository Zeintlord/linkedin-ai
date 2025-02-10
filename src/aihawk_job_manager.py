from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger
import time

class AIHawkJobManager:
    def __init__(self, driver):
        self.driver = driver

    def start_search(self, job_title, location):
        """
        Realiza la búsqueda de empleos en LinkedIn.
        """
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title}&location={location}&f_WT=2"
        logger.info(f"Navegando a la URL de búsqueda: {search_url}")
        self.driver.get(search_url)

        try:
            # Esperamos hasta que la lista de empleos aparezca
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "scaffold-layout__list-container"))
            )
            time.sleep(3)  # Breve espera adicional para evitar problemas de carga
            logger.info("Lista de trabajos cargada correctamente.")
        except Exception as e:
            logger.error(f"No se pudo cargar la lista de trabajos: {e}")

    def apply_to_jobs(self):
        """
        Aplica a los empleos encontrados en la búsqueda.
        """
        try:
            job_listings = self.driver.find_elements(By.CLASS_NAME, "job-card-container")
            if not job_listings:
                logger.warning("No se encontraron trabajos en la búsqueda.")
                return

            for job in job_listings:
                try:
                    job.click()
                    time.sleep(3)

                    # Intentamos encontrar el botón "Easy Apply"
                    easy_apply_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, '//button[contains(@class, "jobs-apply-button") and contains(., "Easy Apply")]')
                        )
                    )
                    easy_apply_button.click()
                    logger.info("Botón 'Easy Apply' clickeado exitosamente.")

                    # Aquí podemos agregar la lógica para completar formularios si es necesario

                except Exception as e:
                    logger.warning(f"No se pudo aplicar al trabajo: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error al procesar la lista de trabajos: {e}")
