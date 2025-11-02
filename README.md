# 🤖 Monitor de Keywords para X (vía Nitter)

Un bot simple que vigila perfiles de X (a través de una instancia de Nitter) en busca de palabras clave específicas. Cuando encuentra una coincidencia en un post nuevo, envía una alerta instantánea por correo electrónico.

## ✨ Características Principales

  * **Monitorización Múltiple:** Vigila varias cuentas de X al mismo tiempo.
  * **Detección de Keywords:** Busca en los posts una lista personalizable de palabras clave.
  * **Detección Inteligente:** Ignora tildes, mayúsculas y minúsculas. (`"Urgente"` y `"urgénte"` coincidirán con `"urgente"`).
  * **Alertas por Email:** Envía notificaciones inmediatas usando SMTP (probado con Gmail).
  * **Horario Programable:** Puedes definir una franja horaria en UTC (ej. de `09:00` a `17:00`) para que el bot solo esté activo en ese periodo.
  * **Eficiente:** Distribuye las comprobaciones de forma equitativa para no sobrecargar el servidor.

## 🚀 Instalación y Puesta en Marcha (con `uv`)

Sigue estos pasos para ejecutar el monitor en tu máquina local usando `uv`.

### 1\. Prerrequisitos

Asegúrate de tener **Python 3.10+** y `uv` instalados. Si no tienes `uv`, puedes instalarlo rápidamente:

```bash
# En macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# En Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

### 2\. Clonar el Repositorio

```bash
git clone https://github.com/marcoslafoz/x-keyword-monitor.git
cd x-keyword-monitor
```

### 3\. Configurar el Entorno

Copia el archivo de ejemplo `.env.example` y renómbralo a `.env`.

```bash
cp .env.example .env
```

Ahora, **edita el archivo `.env`** y rellena todas las variables:

  * `NITTER_INSTANCE_URL`: La URL de la instancia de Nitter que quieres usar (ej. `https://nitter.net`).
  * `X_ACCOUNTS`: Las cuentas de X a vigilar, separadas por comas (ej. `perfil1,perfil2`).
  * `KEYWORDS`: Las palabras clave a buscar, separadas por comas (ej. `alerta,urgente,importante`).
  * `EMAIL_RECIPIENTS`: Los correos que recibirán las alertas (separados por comas).
  * `SMTP_SERVER`: Tu servidor de correo (ej. `smtp.gmail.com`).
  * `SMTP_PORT`: El puerto (ej. `587`).
  * `SMTP_USER`: Tu email de envío.
  * `SMTP_PASSWORD`: Tu contraseña de aplicación (si usas Gmail/Google).
  * `START_TIME_UTC` (Opcional): Hora de inicio en formato `HH:MM`.
  * `END_TIME_UTC` (Opcional): Hora de fin en formato `HH:MM`.

### 4\. Instalar y Ejecutar

`uv` puede crear el entorno, instalar las dependencias y ejecutar el script. No necesitas activar el entorno manualmente.

```bash
# 1. Crea el entorno virtual (creará una carpeta .venv)
uv venv

# 2. Instala las dependencias de Python en el .venv
uv pip install -r requirements.txt

# 3. Instala el navegador (ejecutando el comando *dentro* del .venv)
uv run playwright install chromium

# 4. Ejecuta el bot
uv run main.py
```

El bot comenzará a funcionar y verás los logs directamente en tu terminal.

## 🛠️ Stack Tecnológico

  * **🐍 Python 3.11+**
  * **🤖 Playwright:** Para controlar el navegador *headless* y leer Nitter.
  * **💠 Nitter:** Se usa como *frontend* alternativo a X para evitar bloqueos.
  * **⚡ uv:** El gestor de paquetes y entorno virtual de alta velocidad.
