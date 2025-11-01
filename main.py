# main.py
import os
import time
import re
import unicodedata
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError

# --- ELIMINADO: 'import threading' ya no es necesario ---

import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, time as dt_time, timezone


def normalize_text(text):
    """Normaliza el texto: tildes, minúsculas, sin espacios/puntuación."""
    try:
        nfkd_form = unicodedata.normalize("NFD", text)
        only_ascii = nfkd_form.encode("ascii", "ignore").decode("utf-8")
        lower_text = only_ascii.lower()
        compact_text = re.sub(r"[^a-z0-9]", "", lower_text)
        return compact_text
    except Exception:
        return text.lower()


# --- Configuración ---
load_dotenv()

# Configuración de Nitter
NITTER_URL = os.getenv("NITTER_INSTANCE_URL", "https://nitter.net")
ACCOUNTS_TO_MONITOR = os.getenv("X_ACCOUNTS", "").split(",")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", 300))
SHOW_BROWSER = os.getenv("SHOW_BROWSER", "False").lower() == "true"

# Configuración de Keywords
KEYWORDS_RAW = [k for k in os.getenv("KEYWORDS", "").split(",") if k]
KEYWORDS_TO_SEARCH = [normalize_text(k) for k in KEYWORDS_RAW]

# Configuración de Email
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_RECIPIENTS = [
    email.strip()
    for email in os.getenv("EMAIL_RECIPIENTS", "").split(",")
    if email.strip()
]

# Configuración de Horario
START_TIME_STR = os.getenv("START_TIME_UTC")
END_TIME_STR = os.getenv("END_TIME_UTC")


def parse_utc_time(time_str):
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        print(
            f"ERROR: El formato de hora '{time_str}' es incorrecto. Debe ser HH:MM. Ignorando..."
        )
        return None


START_TIME_UTC = parse_utc_time(START_TIME_STR)
END_TIME_UTC = parse_utc_time(END_TIME_STR)

# --- Selectores de Nitter ---
POST_CONTAINER_SELECTOR = "div.timeline-item"
POST_TEXT_SELECTOR = "div.tweet-content"
POST_LINK_SELECTOR = "a.tweet-link"

# --- MODIFICADO: Ya no necesitamos un candado 'lock' ---
last_seen_post_id = {}


def is_within_time_window():
    """Comprueba si la hora actual UTC está dentro de la franja definida."""
    if not START_TIME_UTC or not END_TIME_UTC:
        return True
    current_utc_time = datetime.now(timezone.utc).time()
    start = START_TIME_UTC
    end = END_TIME_UTC
    if start <= end:
        return start <= current_utc_time <= end
    else:
        return current_utc_time >= start or current_utc_time <= end


def send_email_alert(account, keyword, post_text, post_id):
    """Envía una notificación por email vía SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD or not EMAIL_RECIPIENTS:
        print("INFO: Variables de SMTP no configuradas. Saltando envío de email.")
        return
    print(f"Enviando alerta por email a: {', '.join(EMAIL_RECIPIENTS)}")
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Alerta de Keyword: @{account} mencionó '{keyword}'"
    message["From"] = SMTP_USER
    message["To"] = ", ".join(EMAIL_RECIPIENTS)
    post_url = f"{NITTER_URL}/{account}/status/{post_id}"
    text = f"""
    ¡Alerta!
    La cuenta @{account} ha publicado un nuevo post que contiene la palabra clave: '{keyword}'.
    
    Texto del post:
    "{post_text}"
    
    Enlace al post: {post_url}
    """
    message.attach(MIMEText(text, "plain"))
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, EMAIL_RECIPIENTS, message.as_string())
        print(f"¡Email de alerta enviado con éxito para @{account}!")
    except Exception as e:
        print(f"ERROR: No se pudo enviar el email para @{account}: {e}")


def get_latest_post_data(page, account):
    """Obtiene el post más reciente usando Playwright en Nitter."""
    print(f"Buscando posts en perfil: {account}")
    try:
        url = f"{NITTER_URL}/{account}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)

        page.wait_for_selector(POST_CONTAINER_SELECTOR, timeout=10000)
        latest_post_element = page.query_selector(POST_CONTAINER_SELECTOR)

        if not latest_post_element:
            return None, None

        text_element = latest_post_element.query_selector(POST_TEXT_SELECTOR)
        post_text = text_element.inner_text() if text_element else ""

        link_element = latest_post_element.query_selector(POST_LINK_SELECTOR)
        post_id = None
        if link_element:
            href = link_element.get_attribute("href")
            if href:
                post_id = href.split("/")[-1].split("#")[0]

        if not post_id:
            post_id = post_text[:50]

        return post_id, post_text
    except TimeoutError:
        print(f"Timeout esperando la página de {account}. ¿Instancia de Nitter caída?")
        return None, None
    except Exception as e:
        print(f"Error inesperado al procesar {account}: {e}")
        return None, None


def check_for_keywords(post_text):
    """Comprueba keywords normalizadas contra el texto del post normalizado."""
    if not post_text:
        return None
    normalized_post_text = normalize_text(post_text)
    for i, normalized_keyword in enumerate(KEYWORDS_TO_SEARCH):
        if normalized_keyword in normalized_post_text:
            return KEYWORDS_RAW[i]
    return None


# --- NUEVA FUNCIÓN: Lógica de comprobación de una sola cuenta ---
# (Esto es lo que antes hacía la función del hilo 'check_account_thread')
def check_single_account(page, account):
    """Comprueba una sola cuenta y toma medidas si hay un post nuevo."""
    if not account:
        return

    print(f"\n--- Comprobando {account} ---")
    post_id, post_text = get_latest_post_data(page, account)

    if not post_id:
        print(f"No se pudo obtener post para {account}.")
        return

    # No se necesita candado 'lock', es secuencial
    last_id = last_seen_post_id.get(account)

    if post_id != last_id:
        print(f"¡NUEVO POST DETECTADO para {account}!")

        found_keyword = check_for_keywords(post_text)

        if found_keyword:
            print("*" * 40)
            print(
                f"¡¡ALERTA!! El post de @{account} CONTIENE la palabra: '{found_keyword}'"
            )
            print(f"Texto: {post_text[:150]}...")
            print("*" * 40)
            send_email_alert(account, found_keyword, post_text, post_id)
        else:
            print(
                f"INFO: Nuevo post de @{account} (sin keywords): {post_text[:100]}..."
            )

        # Actualización secuencial segura
        last_seen_post_id[account] = post_id
    else:
        print(f"Sin posts nuevos para {account}.")


# --- ELIMINADA: La función 'check_account_thread' se ha borrado ---


# --- MODIFICADO: 'main_loop' ahora es secuencial con retraso dinámico ---
def main_loop():
    print("Iniciando monitor SECUENCIAL DISTRIBUIDO (Playwright + Nitter)...")
    print(f"Instancia: {NITTER_URL}")
    print(f"Keywords (originales): {KEYWORDS_RAW}")
    if START_TIME_UTC and END_TIME_UTC:
        print(f"Horario de monitorización (UTC): {START_TIME_UTC} a {END_TIME_UTC}")
    else:
        print("Horario de monitorización: 24/7")

    # --- NUEVA LÓGICA DE TIEMPO ---
    accounts_list = [acc for acc in ACCOUNTS_TO_MONITOR if acc.strip()]
    num_accounts = len(accounts_list)

    if num_accounts == 0:
        print("ERROR: No hay cuentas para monitorizar. Saliendo.")
        return

    # Calcular el retraso dinámico
    try:
        # El tiempo de espera es el intervalo TOTAL dividido por el número de cuentas
        delay_between_checks = CHECK_INTERVAL / num_accounts
    except ZeroDivisionError:
        print(
            f"ERROR: CHECK_INTERVAL es cero ({CHECK_INTERVAL}). Usando 60s por defecto."
        )
        delay_between_checks = 60

    print(
        f"Total de {num_accounts} cuentas. Intervalo total del ciclo: {CHECK_INTERVAL}s."
    )
    print(f"Se comprobará una cuenta cada {delay_between_checks:.2f} segundos.")
    # --- FIN DE LÓGICA DE TIEMPO ---

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not SHOW_BROWSER)
        # Creamos UN contexto y UNA página que se reutilizarán en serie
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            java_script_enabled=False,
        )
        page = context.new_page()

        try:
            account_index = 0  # Usamos un índice para saber qué cuenta toca
            while True:
                # Comprobar si estamos en la franja horaria
                if is_within_time_window():

                    # Obtener la cuenta que toca comprobar en este ciclo
                    account_to_check = accounts_list[account_index]

                    print("\n--- Horario activo. ---")
                    # Llamar a la función de comprobación para esa única cuenta
                    check_single_account(page, account_to_check)

                else:
                    # Estamos fuera de horario, saltamos la comprobación
                    print(
                        f"\n--- Fuera del horario de monitorización (UTC {START_TIME_UTC} - {END_TIME_UTC}). Durmiendo... ---"
                    )
                    print(
                        f"(La próxima cuenta a comprobar será: {accounts_list[account_index]})"
                    )

                # Mover el índice a la siguiente cuenta para el próximo ciclo
                account_index = (account_index + 1) % num_accounts

                # Esperar el tiempo dinámico calculado ANTES de comprobar la siguiente cuenta
                print(
                    f"--- Ciclo parcial completado. Esperando {delay_between_checks:.2f} segundos... ---"
                )
                time.sleep(delay_between_checks)

        except KeyboardInterrupt:
            print("\nDeteniendo el monitor.")
        finally:
            page.close()
            context.close()
            browser.close()


if __name__ == "__main__":
    main_loop()
