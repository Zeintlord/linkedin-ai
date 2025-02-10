import base64
import json
import os
import random
import re
import time
import traceback
from typing import List, Optional, Any, Tuple

from httpx import HTTPStatusError
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from reportlab.pdfbase.pdfmetrics import stringWidth
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

import src.utils as utils
from loguru import logger


class AIHawkEasyApplier:
    """
    Clase encargada de manejar el formulario de postulación "Easy Apply" 
    en LinkedIn. Incluye la lógica de:
    - Localizar el botón "Easy Apply".
    - Hacer clic en él.
    - Llenar campos de texto, dropdown, radio, etc.
    - Subir CV o cover letter.
    - Enviar la postulación.
    """

    def __init__(
        self,
        driver: Any,
        resume_dir: Optional[str],
        set_old_answers: List[Tuple[str, str, str]],
        gpt_answerer: Any,
        resume_generator_manager: Any
    ):
        logger.debug("Initializing AIHawkEasyApplier")
        # Verificar si la ruta al resume es válida
        if resume_dir is None or (hasattr(resume_dir, "resolve") and not resume_dir.resolve().is_file()):
            resume_dir = None

        self.driver = driver
        self.resume_path = resume_dir
        self.set_old_answers = set_old_answers  # Respuestas preexistentes
        self.gpt_answerer = gpt_answerer
        self.resume_generator_manager = resume_generator_manager
        self.all_data = self._load_questions_from_json()
        self.current_job = None

        logger.debug("AIHawkEasyApplier initialized successfully")

    def _load_questions_from_json(self) -> List[dict]:
        """
        Carga de un archivo JSON local las preguntas y respuestas ya respondidas,
        para no tener que preguntarle al LLM repetidamente.
        """
        output_file = 'answers.json'
        logger.debug(f"Loading questions from JSON file: {output_file}")
        try:
            with open(output_file, 'r') as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                        raise ValueError("JSON file format is incorrect. Expected a list of questions.")
                except json.JSONDecodeError:
                    logger.error("JSON decoding failed")
                    data = []
            logger.debug("Questions loaded successfully from JSON")
            return data
        except FileNotFoundError:
            logger.warning(f"JSON file not found: {output_file}, returning empty list")
            return []
        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Error loading questions data from JSON file: {tb_str}")
            raise Exception(f"Error loading questions data from JSON file: \nTraceback:\n{tb_str}")

    def check_for_premium_redirect(self, job: Any, max_attempts=3):
        """
        En caso de que LinkedIn redirija a alguna página de Premium, 
        hace reintentos para volver al link original de la oferta.
        """
        current_url = self.driver.current_url
        attempts = 0

        while "linkedin.com/premium" in current_url and attempts < max_attempts:
            logger.warning("Redirected to Premium page. Attempting to return to job page.")
            attempts += 1
            self.driver.get(job.link)
            time.sleep(2)
            current_url = self.driver.current_url

        if "linkedin.com/premium" in current_url:
            logger.error(f"Failed to return to job page after {max_attempts} attempts.")
            raise Exception("Redirected to Premium page and failed to return to job page.")

    def apply_to_job(self, job: Any) -> None:
        """
        Punto de entrada para postularse a un 'job' específico.
        """
        logger.debug(f"Applying to job: {job}")
        try:
            self.job_apply(job)
            logger.info(f"Successfully applied to job: {job.title}")
        except Exception as e:
            logger.error(f"Failed to apply to job: {job.title}, error: {str(e)}")
            raise e

    def job_apply(self, job: Any):
        """
        Navega a la página del empleo, localiza 'Easy Apply', 
        y rellena el formulario.
        """
        logger.debug(f"Starting job application for job: {job}")

        try:
            self.driver.get(job.link)
            logger.debug(f"Navigated to job link: {job.link}")
        except WebDriverException as e:
            logger.error(f"Failed to navigate to job link: {job.link}, error: {str(e)}")
            raise

        time.sleep(random.uniform(3, 5))
        self.check_for_premium_redirect(job)

        try:
            # Asegurarse de que no haya un elemento activo que obstruya
            self.driver.execute_script("document.activeElement.blur();")

            self.check_for_premium_redirect(job)

            # 1. Localizar el botón 'Easy Apply'
            easy_apply_button = self._find_easy_apply_button(job)

            self.check_for_premium_redirect(job)

            # 2. Obtener descripción y posible recruiter link
            job_description = self._get_job_description()
            job.set_job_description(job_description)
            recruiter_link = self._get_job_recruiter()
            job.set_recruiter_link(recruiter_link)

            self.current_job = job

            # 3. Clic en 'Easy Apply'
            actions = ActionChains(self.driver)
            actions.move_to_element(easy_apply_button).click().perform()
            logger.debug("'Easy Apply' button clicked successfully")

            # 4. Pasamos job info al LLM
            self.gpt_answerer.set_job(job)

            # 5. Llenar formulario con `_fill_application_form`
            logger.debug("Filling out application form")
            self._fill_application_form(job)
            logger.debug(f"Job application process completed successfully for job: {job}")

        except Exception as e:
            tb_str = traceback.format_exc()
            logger.error(f"Failed to apply to job: {job}, error: {tb_str}")

            # Si hubo un error, descartamos la aplicación
            self._discard_application()
            raise Exception(f"Failed to apply to job! Original exception:\nTraceback:\n{tb_str}")

    def _find_easy_apply_button(self, job: Any) -> Any:
        """
        Intenta localizar el botón 'Easy Apply' mediante diferentes XPaths.
        """
        logger.debug("Searching for 'Easy Apply' button")
        attempt = 0

        search_methods = [
            {
                'description': "XPath con jobs-apply-button y texto 'Easy Apply'",
                'find_elements': True,
                'xpath': '//button[contains(@class, "jobs-apply-button") and .//span[contains(@class, "artdeco-button__text") and normalize-space(text()) = "Easy Apply"]]'
            },
            {
                'description': "aria-label containing 'Easy Apply to'",
                'find_elements': False,
                'xpath': '//button[contains(@aria-label, "Easy Apply to")]'
            },
            {
                'description': "button text fallback",
                'find_elements': False,
                'xpath': '//button[contains(text(), "Easy Apply") or contains(text(), "Apply now") or contains(text(), "Solicitud sencilla")]'
            }
        ]

        while attempt < 2:
            self.check_for_premium_redirect(job)
            self._scroll_page()

            for method in search_methods:
                try:
                    logger.debug(f"Trying {method['description']}")
                    if method.get('find_elements'):
                        # localiza multiple elements
                        buttons = self.driver.find_elements(By.XPATH, method['xpath'])
                        if buttons:
                            for index, button in enumerate(buttons):
                                try:
                                    WebDriverWait(self.driver, 10).until(EC.visibility_of(button))
                                    WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(button))
                                    logger.debug(f"Found 'Easy Apply' button (attempt {index+1}), returning it.")
                                    return button
                                except Exception as e:
                                    logger.warning(f"Button found but not clickable: {e}")
                        else:
                            logger.warning(f"No elements found with {method['description']}")
                    else:
                        button = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, method['xpath']))
                        )
                        WebDriverWait(self.driver, 10).until(EC.visibility_of(button))
                        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(button))
                        logger.debug("Found 'Easy Apply' button, returning it.")
                        return button

                except TimeoutException:
                    logger.warning(f"Timeout searching for Easy Apply with {method['description']}")
                except Exception as e:
                    logger.warning(f"Error with {method['description']}: {e}")

            self.check_for_premium_redirect(job)

            if attempt == 0:
                logger.debug("Refreshing page to retry finding 'Easy Apply' button")
                self.driver.refresh()
                time.sleep(random.randint(3, 5))
            attempt += 1

        page_source = self.driver.page_source
        logger.error("No clickable 'Easy Apply' button found after 2 attempts.")
        raise Exception("No clickable 'Easy Apply' button found")

    def _scroll_page(self) -> None:
        """
        Realiza un scroll en la página para asegurarse de que
        elementos que están fuera de la vista puedan cargarse.
        """
        logger.debug("Scrolling the page")
        scrollable_element = self.driver.find_element(By.TAG_NAME, 'html')
        utils.scroll_slow(self.driver, scrollable_element, step=300, reverse=False)
        utils.scroll_slow(self.driver, scrollable_element, step=300, reverse=True)

    def _get_job_description(self) -> str:
        """
        Intentar obtener la descripción de la oferta desde la página.
        """
        logger.debug("Getting job description")
        try:
            # A veces hay un botón "See more" para expandir la descripción
            try:
                see_more_button = self.driver.find_element(By.XPATH, '//button[@aria-label="Click to see more description"]')
                ActionChains(self.driver).move_to_element(see_more_button).click().perform()
                time.sleep(2)
            except NoSuchElementException:
                logger.debug("'See more' button not found. Skipping...")

            # Intentar buscar la descripción en distintos class names
            try:
                description = self.driver.find_element(By.CLASS_NAME, 'jobs-description-content__text').text
            except NoSuchElementException:
                logger.debug("Trying alternative class for job description (premium layout).")
                description = self.driver.find_element(By.CLASS_NAME, 'job-details-about-the-job-module__description').text

            logger.debug("Job description retrieved successfully")
            return description
        except NoSuchElementException:
            tb_str = traceback.format_exc()
            logger.error(f"Job description not found: {tb_str}")
            raise Exception("Job description not found.")
        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Error getting Job description: {tb_str}")
            raise Exception(f"Error getting Job description:\n{tb_str}")

    def _get_job_recruiter(self):
        """
        Algunas veces LinkedIn muestra 'Meet the hiring team'.
        Intentar extraer el link de la persona que recluta si está disponible.
        """
        logger.debug("Getting job recruiter information")
        try:
            hiring_team_section = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//h2[text()="Meet the hiring team"]'))
            )
            recruiter_elements = hiring_team_section.find_elements(
                By.XPATH, './/following::a[contains(@href, "linkedin.com/in/")]'
            )
            if recruiter_elements:
                recruiter_link = recruiter_elements[0].get_attribute('href')
                logger.debug(f"Recruiter link: {recruiter_link}")
                return recruiter_link
            else:
                return ""
        except Exception as e:
            logger.warning(f"Failed to retrieve recruiter info: {e}")
            return ""

    def _fill_application_form(self, job):
        """
        Aquí se itera en cada paso del formulario de Easy Apply.
        """
        while True:
            self.fill_up(job)
            # Ver si hay que darle a 'Next' o ya 'Submit'
            if self._next_or_submit():
                logger.debug("Application form fully submitted.")
                break

    def fill_up(self, job) -> None:
        """
        Rellena los campos del formulario que aparezcan en la vista actual.
        """
        logger.debug(f"Filling up form sections for job: {job}")
        try:
            # Contenedor principal
            easy_apply_content = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'jobs-easy-apply-content'))
            )
            pb4_elements = easy_apply_content.find_elements(By.CLASS_NAME, 'pb4')
            for element in pb4_elements:
                self._process_form_element(element, job)
        except Exception as e:
            logger.error(f"Failed to find form elements: {e}")

    def _process_form_element(self, element, job) -> None:
        logger.debug("Processing form element")
        # Chequear si hay campo de upload
        if self._is_upload_field(element):
            self._handle_upload_fields(element, job)
        else:
            # Llenar las preguntas extras
            self._fill_additional_questions()

    def _is_upload_field(self, element) -> bool:
        is_upload = bool(element.find_elements(By.XPATH, ".//input[@type='file']"))
        logger.debug(f"Element is upload field: {is_upload}")
        return is_upload

    def _handle_upload_fields(self, element, job) -> None:
        """
        Maneja la subida de CV, cover letter, etc.
        """
        logger.debug("Handling upload fields")
        # A veces hay un botón 'Show more resumes'
        try:
            show_more_button = self.driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Show more resumes')]")
            show_more_button.click()
            logger.debug("Clicked 'Show more resumes' button")
        except NoSuchElementException:
            logger.debug("'Show more resumes' button not found, continuing...")

        file_upload_elements = self.driver.find_elements(By.XPATH, "//input[@type='file']")
        for input_file in file_upload_elements:
            parent = input_file.find_element(By.XPATH, "..")
            self.driver.execute_script("arguments[0].classList.remove('hidden')", input_file)
            # Decidimos si es 'resume' o 'cover' en base a la etiqueta
            output = self.gpt_answerer.resume_or_cover(parent.text.lower())
            if 'resume' in output:
                logger.debug("Uploading resume")
                if self.resume_path:
                    # Tenemos un path a un PDF
                    input_file.send_keys(str(self.resume_path))
                    logger.debug(f"Resume uploaded from path: {self.resume_path}")
                else:
                    # Generar uno en tiempo real
                    logger.debug("Resume path not set, generating new resume PDF")
                    self._create_and_upload_resume(input_file, job)
            elif 'cover' in output:
                logger.debug("Uploading cover letter")
                self._create_and_upload_cover_letter(input_file, job)
        logger.debug("Finished handling upload fields")

    def _create_and_upload_resume(self, element, job):
        """
        Generar un PDF de CV en tiempo real con 'resume_generator_manager'
        y subirlo.
        """
        logger.debug("Starting the process of creating and uploading resume.")
        folder_path = 'generated_cv'
        os.makedirs(folder_path, exist_ok=True)

        while True:
            try:
                timestamp = int(time.time())
                file_path_pdf = os.path.join(folder_path, f"CV_{timestamp}.pdf")
                logger.debug(f"Generated file path for resume: {file_path_pdf}")

                # Pedimos al resume_generator_manager un PDF base64
                resume_pdf_base64 = self.resume_generator_manager.pdf_base64(job_description_text=job.description)

                with open(file_path_pdf, "xb") as f:
                    f.write(base64.b64decode(resume_pdf_base64))
                logger.debug(f"Resume generated and saved to: {file_path_pdf}")
                break

            except HTTPStatusError as e:
                # Manejo de Rate Limit
                if e.response.status_code == 429:
                    retry_after = e.response.headers.get('retry-after') or "20"
                    wait_time = int(retry_after)
                    logger.warning(f"Rate limit exceeded, waiting {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTTP error generating resume: {e}")
                    raise
            except Exception as e:
                logger.error(f"Failed to generate resume: {e}")
                if "RateLimitError" in str(e):
                    logger.warning("Rate limit error encountered, retrying...")
                    time.sleep(20)
                else:
                    raise

        # Verificar tamaño < 2 MB (LinkedIn a veces limita)
        file_size = os.path.getsize(file_path_pdf)
        max_file_size = 2 * 1024 * 1024  # 2 MB
        if file_size > max_file_size:
            logger.error(f"Resume file size exceeds 2 MB: {file_size} bytes")
            raise ValueError("Resume file size exceeds the maximum limit of 2 MB.")

        # Verificar formato aceptado
        allowed_extensions = {'.pdf', '.doc', '.docx'}
        _, file_extension = os.path.splitext(file_path_pdf)
        if file_extension.lower() not in allowed_extensions:
            logger.error(f"Invalid resume file format: {file_extension}")
            raise ValueError("Resume file format is not allowed. Only PDF, DOC, DOCX supported.")

        # Subir
        element.send_keys(os.path.abspath(file_path_pdf))
        job.pdf_path = os.path.abspath(file_path_pdf)
        time.sleep(2)
        logger.debug("Resume created and uploaded successfully")

    def _create_and_upload_cover_letter(self, element, job) -> None:
        """
        Generar un PDF de cover letter con reportlab y subirlo.
        """
        logger.debug("Starting the process of creating and uploading cover letter.")
        cover_letter_text = self.gpt_answerer.answer_question_textual_wide_range("Write a cover letter")
        folder_path = 'generated_cv'
        os.makedirs(folder_path, exist_ok=True)

        timestamp = int(time.time())
        file_path_pdf = os.path.join(folder_path, f"Cover_Letter_{timestamp}.pdf")
        logger.debug(f"Generated file path for cover letter: {file_path_pdf}")

        # Generar PDF con reportlab
        from reportlab.pdfbase.pdfmetrics import stringWidth
        c = canvas.Canvas(file_path_pdf, pagesize=A4)
        page_width, page_height = A4
        text_object = c.beginText(50, page_height - 50)
        text_object.setFont("Helvetica", 12)

        max_width = page_width - 100
        bottom_margin = 50

        def split_text_by_width(text, font_name, font_size, max_line_width):
            """
            Función auxiliar para dividir texto en líneas 
            si excede el ancho de la hoja.
            """
            lines = []
            for line in text.split('\n'):
                if stringWidth(line, font_name, font_size) <= max_line_width:
                    lines.append(line)
                else:
                    words = line.split()
                    new_line = ""
                    for word in words:
                        if stringWidth(new_line + word + " ", font_name, font_size) <= max_line_width:
                            new_line += word + " "
                        else:
                            lines.append(new_line.strip())
                            new_line = word + " "
                    lines.append(new_line.strip())
            return lines

        wrapped_lines = split_text_by_width(cover_letter_text, "Helvetica", 12, max_width)
        for line in wrapped_lines:
            if text_object.getY() <= bottom_margin:
                c.drawText(text_object)
                c.showPage()
                text_object = c.beginText(50, page_height - 50)
                text_object.setFont("Helvetica", 12)
            text_object.textLine(line)

        c.drawText(text_object)
        c.save()
        logger.debug(f"Cover letter generated and saved to: {file_path_pdf}")

        # Verificar tamaño y formato
        file_size = os.path.getsize(file_path_pdf)
        max_file_size = 2 * 1024 * 1024
        if file_size > max_file_size:
            logger.error(f"Cover letter file size exceeds 2 MB: {file_size}")
            raise ValueError("Cover letter file size exceeds the maximum limit of 2 MB.")

        _, file_extension = os.path.splitext(file_path_pdf)
        if file_extension.lower() not in {'.pdf', '.doc', '.docx'}:
            logger.error(f"Invalid cover letter file format: {file_extension}")
            raise ValueError("Cover letter file format is not allowed (PDF, DOC, DOCX).")

        element.send_keys(os.path.abspath(file_path_pdf))
        job.cover_letter_path = os.path.abspath(file_path_pdf)
        time.sleep(2)
        logger.debug("Cover letter created and uploaded successfully")

    def _fill_additional_questions(self) -> None:
        """
        Lógica para rellenar preguntas adicionales (ej. 'Cover letter text', 
        'Are you authorized to work in X', etc.).
        """
        logger.debug("Filling additional questions")
        form_sections = self.driver.find_elements(By.CLASS_NAME, 'jobs-easy-apply-form-section__grouping')
        for section in form_sections:
            self._process_form_section(section)

    def _process_form_section(self, section):
        """
        Detectar tipo de pregunta (radio, textbox, dropdown, etc.) 
        y delegar a métodos específicos.
        """
        # Aquí podrías implementar tu lógica para 
        # `_find_and_handle_radio_question`, `_find_and_handle_textbox_question`, etc.
        # Simplificado: no implementado en detalle en este snippet.
        pass

    def _next_or_submit(self):
        """
        Localiza el botón 'Next' o 'Submit application'. 
        Si es 'Submit', lo clica y retorna True indicando que ya finalizó.
        Si es 'Next', clica y retorna False indicando que hay más pasos.
        """
        logger.debug("Clicking 'Next' or 'Submit' button")
        next_button = self.driver.find_element(By.CLASS_NAME, "artdeco-button--primary")
        button_text = next_button.text.lower()
        if 'submit application' in button_text or 'enviar solicitud' in button_text:
            logger.debug("Submit button found, submitting application.")
            self._unfollow_company()
            time.sleep(random.uniform(1.5, 2.5))
            next_button.click()
            time.sleep(random.uniform(1.5, 2.5))
            return True
        time.sleep(random.uniform(1.5, 2.5))
        next_button.click()
        time.sleep(random.uniform(3.0, 5.0))
        self._check_for_errors()
        return False

    def _unfollow_company(self) -> None:
        """
        A veces LinkedIn agrega una checkbox de "Follow company".
        Aquí intentamos desmarcarla si existe.
        """
        try:
            logger.debug("Attempting to unfollow company checkbox")
            follow_checkbox = self.driver.find_element(
                By.XPATH, "//label[contains(.,'to stay up to date with their page.')]"
            )
            follow_checkbox.click()
        except Exception as e:
            logger.debug(f"Failed to unfollow company: {e}")

    def _check_for_errors(self) -> None:
        """
        Tras hacer clic en Next, chequear si hay errores de validación
        en el formulario.
        """
        logger.debug("Checking for form errors")
        error_elements = self.driver.find_elements(By.CLASS_NAME, 'artdeco-inline-feedback--error')
        if error_elements:
            logger.error(f"Form submission failed with errors: {error_elements}")
            texts = [e.text for e in error_elements]
            raise Exception(f"Failed answering or file upload: {texts}")

    def _discard_application(self) -> None:
        """
        Si algo sale mal, descartamos la aplicación para no dejarla en un estado intermedio.
        """
        logger.debug("Discarding application due to error")
        try:
            # Clic en la X del modal
            self.driver.find_element(By.CLASS_NAME, 'artdeco-modal__dismiss').click()
            time.sleep(random.uniform(3, 5))
            # Confirmar
            discard_buttons = self.driver.find_elements(By.CLASS_NAME, 'artdeco-modal__confirm-dialog-btn')
            if discard_buttons:
                discard_buttons[0].click()
            time.sleep(random.uniform(3, 5))
        except Exception as e:
            logger.warning(f"Failed to discard application: {e}")

    def _save_questions_to_json(self, question_data: dict) -> None:
        """
        Guarda en 'answers.json' la respuesta a una pregunta
        para reusar en el futuro.
        """
        output_file = 'answers.json'
        question_data['question'] = self._sanitize_text(question_data['question'])
        logger.debug(f"Saving question data to JSON: {question_data}")

        try:
            try:
                with open(output_file, 'r') as f:
                    try:
                        data = json.load(f)
                        if not isinstance(data, list):
                            raise ValueError("JSON file format is incorrect. Expected a list of questions.")
                    except json.JSONDecodeError:
                        logger.error("JSON decoding failed")
                        data = []
            except FileNotFoundError:
                logger.warning("answers.json not found, creating new file")
                data = []

            data.append(question_data)
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=4)
            logger.debug("Question data saved successfully to JSON")

        except Exception:
            tb_str = traceback.format_exc()
            logger.error(f"Error saving questions data to JSON file: {tb_str}")
            raise Exception(f"Error saving questions data to JSON file: \nTraceback:\n{tb_str}")

    def _sanitize_text(self, text: str) -> str:
        """
        Limpia texto (baja a minúsculas, elimina caracter extraños) para comparaciones.
        """
        sanitized_text = text.lower().strip().replace('"', '').replace('\\', '')
        sanitized_text = re.sub(r'[\x00-\x1F\x7F]', '', sanitized_text).replace('\n', ' ').replace('\r', '').rstrip(',')
        return sanitized_text
