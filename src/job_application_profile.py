import yaml
from loguru import logger
from pathlib import Path

class JobApplicationProfile:
    """
    Clase que gestiona la información del currículum/usuario
    para su uso en el proceso de postulación.
    """
    def __init__(self, plain_text_resume: str):
        """
        plain_text_resume: cadena con el contenido YAML de 'plain_text_resume.yaml'
        """
        self.raw_text = plain_text_resume
        self.data = {}
        self._parse_resume()

    def _parse_resume(self):
        """
        Parsea el contenido YAML y lo guarda en self.data (dict).
        """
        try:
            self.data = yaml.safe_load(self.raw_text)
            logger.debug("Parsed plain_text_resume into dictionary.")
        except Exception as e:
            logger.error(f"Failed to parse plain_text_resume: {e}")
            self.data = {}

    def get_personal_info(self):
        """
        Retorna la sección 'personal_information' del YAML, si existe.
        """
        return self.data.get("personal_information", {})

    def get_education_details(self):
        """
        Retorna la lista de 'education_details'.
        """
        return self.data.get("education_details", [])

    def get_experience_details(self):
        """
        Retorna la lista de 'experience_details'.
        """
        return self.data.get("experience_details", [])

    def get_legal_authorization(self):
        """
        Retorna 'legal_authorization' si existe.
        """
        return self.data.get("legal_authorization", {})

    # Puedes añadir más getters según tus secciones (certifications, achievements, etc.)

    def __repr__(self):
        """
        Representación simple de la clase para debug.
        """
        name = self.data.get('personal_information', {}).get('name', 'Unknown')
        surname = self.data.get('personal_information', {}).get('surname', 'User')
        return f"<JobApplicationProfile for {name} {surname}>"
