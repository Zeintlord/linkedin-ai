import time
import random
from selenium.webdriver.chrome.options import Options

def scroll_slow(driver, element, step=300, reverse=False):
    """
    Scrollea el elemento de forma gradual para no parecer un bot.
    Utiliza un 'step' configurable y la dirección (normal o reverse).
    """
    scroll_height = driver.execute_script("return arguments[0].scrollHeight", element)
    if reverse:
        scroll_range = range(scroll_height, 0, -step)
    else:
        scroll_range = range(0, scroll_height, step)

    for value in scroll_range:
        driver.execute_script("arguments[0].scrollTop = %s;", element, value)
        time.sleep(random.uniform(0.2, 0.4))  # Pausa breve por cada salto

def chrome_browser_options():
    """
    Genera un objeto de configuraciones para Chrome (Selenium).
    Desactiva notificaciones, extensiones, etc. 
    """
    chrome_options = Options()
    # Iniciar con la ventana maximizada
    chrome_options.add_argument("--start-maximized")
    # Desactivar algunas notificaciones, barras e infobars.
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-extensions")
    # Puedes agregar más opciones si deseas (headless, user-agent personalizado, etc.)
    return chrome_options
