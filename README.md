# 🤖 X/Nitter Keyword Monitor

Un bot de monitorización que comprueba cuentas de X (a través de Nitter) en busca de nuevos posts que contengan palabras clave específicas. Cuando encuentra una coincidencia, envía una alerta por correo electrónico.

El script está diseñado para ser robusto, eficiente y fácil de configurar, todo ello dentro de un contenedor Docker.

## ✨ Características

* **Monitorización de Múltiples Cuentas:** Vigila varias cuentas de X simultáneamente.
* **Búsqueda de Múltiples Keywords:** Detecta una lista personalizable de palabras clave.
* **Detección Inteligente:** Ignora mayúsculas, minúsculas, tildes y espacios en las palabras clave (p.ej., "Urgente", "urgénte", "u r g e n t e" coincidirán con "urgente").
* **Alertas por Email:** Envía notificaciones instantáneas a través de SMTP (probado con Gmail).
* **Horario Programable:** Define una franja horaria en UTC (inicio y fin) para que el monitor solo se ejecute cuando tú quieras.
* **Comprobaciones Distribuidas:** Distribuye de forma inteligente el tiempo de comprobación. Si tienes 10 cuentas y un intervalo de 60 minutos, comprobará una cuenta cada 6 minutos, evitando sobrecargar el servidor.
* **Totalmente Contenerizado:** Todo el proyecto se ejecuta en un contenedor Docker con Docker Compose para una configuración y despliegue sencillos.

## 🛠️ Stack Tecnológico

* **🐍 Python 3.11+**
* **🤖 Playwright:** Para controlar un navegador *headless* y navegar por Nitter.
* **💠 Nitter:** Se usa como *frontend* alternativo a X.com para evitar bloqueos de inicio de sesión y diseños complejos.
* **⚡ uv:** El gestor de paquetes y entorno virtual de alta velocidad.
* **🐳 Docker & Docker Compose:** Para crear una imagen y ejecutar la aplicación de forma aislada y reproducible.