# main.py
import os
import time
import re
import unicodedata
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError

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


# --- Configuración y Carga de Variables ---
load_dotenv()

# Nitter
NITTER_URL = os.getenv("NITTER_INSTANCE_URL", "https://nitter.net")
ACCOUNTS_TO_MONITOR = os.getenv("X_ACCOUNTS", "").split(",")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", 300))
SHOW_BROWSER = os.getenv("SHOW_BROWSER", "False").lower() == "true"

# Keywords
KEYWORDS_RAW = [k for k in os.getenv("KEYWORDS", "").split(",") if k]
KEYWORDS_TO_SEARCH = [normalize_text(k) for k in KEYWORDS_RAW]

# Email
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_RECIPIENTS = [
    email.strip()
    for email in os.getenv("EMAIL_RECIPIENTS", "").split(",")
    if email.strip()
]

# Horario (UTC)
START_TIME_STR = os.getenv("START_TIME_UTC")
END_TIME_STR = os.getenv("END_TIME_UTC")


def parse_utc_time(time_str):
    """Convierte un string 'HH:MM' a un objeto time."""
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
POST_TEXT_SELECTOR = "div.tweet-content"
POST_LINK_SELECTOR = "a.tweet-link"

# --- Estado Global ---
last_seen_post_id = {}


def is_within_time_window():
    """Comprueba si la hora actual UTC está dentro de la franja definida."""
    if not START_TIME_UTC or not END_TIME_UTC:
        return True  # Si no hay horario, se ejecuta 24/7

    current_utc_time = datetime.now(timezone.utc).time()
    start = START_TIME_UTC
    end = END_TIME_UTC

    if start <= end:
        # Horario normal (p.ej. 09:00 a 17:00)
        return start <= current_utc_time <= end
    else:
        # Horario que cruza la medianoche (p.ej. 22:00 a 04:00)
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
    """Obtiene el post más reciente (no fijado) de una cuenta de Nitter."""
    print(f"Buscando posts en perfil: {account}")
    try:
        url = f"{NITTER_URL}/{account}"
        page.goto(url, wait_until="networkidle", timeout=15000)

        page.wait_for_selector("div.timeline-item", timeout=10000)
        all_post_elements = page.query_selector_all("div.timeline > div.timeline-item")

        latest_post_element = None

        for element in all_post_elements:
            is_pinned = element.query_selector("div.pinned")
            if not is_pinned:
                latest_post_element = element
                break

        if not latest_post_element:
            print(f"No se encontró ningún post 'real' (no fijado) para {account}.")
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
        print(
            f"Timeout esperando la página de {account}. ¿Instancia de Nitter caída o bloqueando por bot?"
        )
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


def check_single_account(page, account):
    """Comprueba una sola cuenta y toma medidas si hay un post nuevo."""
    if not account:
        return

    print(f"\n--- Comprobando {account} ---")
    post_id, post_text = get_latest_post_data(page, account)

    if not post_id:
        # El error ya se imprimió en get_latest_post_data
        return

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
            # MODIFICACIÓN MEJORADA: Comprobar si el post tiene texto
            if post_text and post_text.strip():
                first_line = post_text.split("\n")[0]
                print(
                    f"INFO: Nuevo post de @{account} (sin keywords): {first_line[:100]}..."
                )
            else:
                # Si post_text está vacío o solo tiene espacios
                print(
                    f"INFO: Nuevo post de @{account} (sin keywords): [Post sin texto (solo multimedia o enlace)]"
                )

        last_seen_post_id[account] = post_id
    else:
        print(f"Sin posts nuevos para {account}.")


def main_loop():
    """Bucle principal del monitor."""
    print("Iniciando monitor SECUENCIAL DISTRIBUIDO (Playwright + Nitter)...")

    accounts_list = [acc.strip() for acc in ACCOUNTS_TO_MONITOR if acc.strip()]
    num_accounts = len(accounts_list)

    if num_accounts == 0:
        print("ERROR: No hay cuentas para monitorizar (X_ACCOUNTS). Saliendo.")
        return

    try:
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

    if START_TIME_UTC and END_TIME_UTC:
        print(f"Horario de monitorización (UTC): {START_TIME_UTC} a {END_TIME_UTC}")
    else:
        print("Horario de monitorización: 24/7")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not SHOW_BROWSER)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        try:
            account_index = 0
            while True:
                if is_within_time_window():
                    account_to_check = accounts_list[account_index]
                    print("\n--- Horario activo. ---")
                    check_single_account(page, account_to_check)
                else:
                    print(
                        f"\n--- Fuera del horario de monitorización (UTC {START_TIME_UTC} - {END_TIME_UTC}). Durmiendo... ---"
                    )
                    print(
                        f"(La próxima cuenta a comprobar será: {accounts_list[account_index]})"
                    )

                account_index = (account_index + 1) % num_accounts

                print(
                    f"--- Ciclo parcial completado. Esperando {delay_between_checks:.2f} segundos... ---"
                )
                time.sleep(delay_between_checks)

        except KeyboardInterrupt:
            print("\n\n--- Programa parado por el usuario (Ctrl+C). ---")

        finally:
            print("--- Cerrando el navegador... ---")
            page.close()
            context.close()
            browser.close()
            print("--- ¡Adiós! ---")


if __name__ == "__main__":
    main_loop()
