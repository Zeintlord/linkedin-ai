import requests
import random
import datetime
from loguru import logger

class GPTAnswerer:
    """
    Clase que interactúa con un LLM (por ejemplo, Gemini) para responder 
    preguntas abiertas o de selección múltiple en LinkedIn.
    """
    def __init__(self, parameters: dict, llm_api_key: str):
        self.parameters = parameters
        self.llm_api_key = llm_api_key
        self.current_job = None

        # Extraemos datos de la configuración
        self.llm_model = parameters.get('llm_model', 'gemini-pro')
        self.llm_model_type = parameters.get('llm_model_type', 'gemini')
        # URL del endpoint de Gemini, si la config lo define (puedes ajustarlo a tu API real).
        self.llm_api_url = parameters.get('llm_api_url', '')

    def set_job(self, job):
        """
        El EasyApplier llama a este método antes de rellenar el formulario,
        para que la lógica LLM sepa de qué trabajo se trata (si lo necesita).
        """
        self.current_job = job

    def answer_question_from_options(self, question_text: str, options: list[str]) -> str:
        """
        Recibe una pregunta de selección múltiple con un set de opciones
        y decide la mejor respuesta usando el LLM (si es gemini) 
        o una lógica fallback en otros casos.
        """
        logger.debug(f"[LLM] Answering question '{question_text}' from options: {options}")

        # Si detectamos 'gemini' en la config, llamamos a la API
        if self.llm_model_type.lower() == 'gemini':
            if not self.llm_api_url:
                logger.warning("No llm_api_url provided for Gemini. Using random choice fallback.")
                return random.choice(options)

            try:
                payload = {
                    "prompt": question_text,
                    "options": options,
                    "model": self.llm_model
                }
                headers = {
                    "Authorization": f"Bearer {self.llm_api_key}",
                    "Content-Type": "application/json"
                }

                logger.debug(f"Sending request to Gemini LLM at {self.llm_api_url}")
                response = requests.post(self.llm_api_url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()

                data = response.json()
                # Supongamos que la respuesta viene en un campo "answer"
                gemini_answer = data.get("answer", "")

                if gemini_answer in options:
                    logger.debug(f"Gemini LLM provided valid answer: {gemini_answer}")
                    return gemini_answer
                else:
                    # Si la respuesta no está en las opciones, elegimos random
                    logger.warning(f"Gemini's answer '{gemini_answer}' not in {options}. Using random fallback.")
                    return random.choice(options)

            except Exception as e:
                logger.warning(f"Gemini request failed: {e}. Using random fallback.")
                return random.choice(options)

        # Si no es gemini, la lógica "fallback" se limita a elegir una opción aleatoria
        logger.debug("Using fallback method (random choice).")
        return random.choice(options)

    def answer_question_textual_wide_range(self, question_text: str) -> str:
        """
        Responde preguntas abiertas. Si es gemini, llamamos a la API 
        para obtener una respuesta. Caso contrario, fallback genérico.
        """
        logger.debug(f"[LLM] Answering open question: '{question_text}'")

        if self.llm_model_type.lower() == 'gemini':
            if not self.llm_api_url:
                logger.warning("No llm_api_url provided for Gemini. Using fallback response.")
                return self._fallback_text()

            try:
                payload = {
                    "prompt": question_text,
                    "model": self.llm_model
                }
                headers = {
                    "Authorization": f"Bearer {self.llm_api_key}",
                    "Content-Type": "application/json"
                }
                logger.debug(f"Sending open question to Gemini LLM at {self.llm_api_url}")
                response = requests.post(self.llm_api_url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()

                data = response.json()
                gemini_answer = data.get("answer", "")
                if gemini_answer:
                    logger.debug(f"Gemini LLM answered: {gemini_answer[:100]} ...")
                    return gemini_answer
                else:
                    logger.warning("Gemini LLM gave empty answer. Using fallback text.")
                    return self._fallback_text()
            except Exception as e:
                logger.warning(f"Gemini request failed for open question: {e}")
                return self._fallback_text()
        else:
            logger.debug("Using fallback open text method.")
            return self._fallback_text()

    def answer_question_numeric(self, question_text: str) -> str:
        """
        Retorna un número en formato string. 
        Llamada a Gemini si se desea, o fallback si no aplica.
        """
        logger.debug(f"[LLM] Answering numeric question: '{question_text}'")

        if self.llm_model_type.lower() == 'gemini' and self.llm_api_url:
            try:
                payload = {
                    "prompt": f"Return a numeric answer for: {question_text}",
                    "model": self.llm_model
                }
                headers = {
                    "Authorization": f"Bearer {self.llm_api_key}",
                    "Content-Type": "application/json"
                }
                response = requests.post(self.llm_api_url, json=payload, headers=headers, timeout=15)
                response.raise_for_status()
                data = response.json()
                numeric_answer = data.get("answer", "42")
                # Podrías validar si numeric_answer realmente es un número:
                return numeric_answer
            except Exception as e:
                logger.warning(f"Gemini request for numeric question failed: {e}")
                return "42"
        else:
            # Fallback: "42"
            return "42"

    def answer_question_date(self) -> datetime.date:
        """
        Retorna una fecha (por ejemplo, la actual). 
        Si quisieras usar Gemini, podrías análogamente hacerlo con un prompt distinto.
        """
        logger.debug("[LLM] Answering date question.")
        return datetime.date.today()

    def resume_or_cover(self, parent_text: str) -> str:
        """
        Determina si el campo de upload es para 'resume' o 'cover letter',
        en función de un string heurístico. 
        """
        parent_text = parent_text.lower()
        if 'cover' in parent_text:
            return 'cover'
        return 'resume'

    def _fallback_text(self) -> str:
        """
        Devuelve una respuesta genérica como fallback cuando no se puede 
        contactar a Gemini o no hay config LLM.
        """
        return (
            "I'm excited about the opportunity to contribute "
            "to this role with my experience and enthusiasm. "
            "Looking forward to discussing further details!"
        )
