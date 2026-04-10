# Bot de musica para Discord

Bot de musica para Discord basado en `discord.py` y `Lavalink`. El proyecto usa comandos slash, reproduce audio desde YouTube y separa la logica de voz en un puente dedicado para Lavalink.

## Flujo general

1. Creas la aplicacion del bot en el portal de Discord.
2. Ejecutas el bootstrap y pegas el `BOT_TOKEN` cuando te lo pida.
3. El bootstrap crea el `venv`, instala dependencias y valida que tengas Java.
4. El arranque prepara Lavalink.jar automaticamente si falta y luego lo levanta con el mismo secreto que usa el bot.
5. Usas los comandos slash dentro de tu servidor.

## Requisitos

- Python 3.14 o compatible con las dependencias fijadas en `requirements.txt`.
- Un JDK moderno compatible con Lavalink 4.2.2. En este entorno se uso Java 25.
- Una aplicacion de Discord con bot creado.
- Acceso al servidor de Discord donde vas a probar la musica.

## Estructura del proyecto

- [main.py](main.py) arranca el bot, carga los cogs y conecta a Lavalink.
- [config.py](config.py) lee la configuracion desde variables de entorno.
- [cogs/music.py](cogs/music.py) contiene los comandos de musica.
- [utils/lavalink_voice.py](utils/lavalink_voice.py) implementa el puente de voz.
- [utils/search.py](utils/search.py) resuelve busquedas y metadata con yt-dlp.
- [lavalink/application.yml](lavalink/application.yml) configura el backend Lavalink.
- [requirements.txt](requirements.txt) fija las dependencias de Python.

## Configurar Discord

1. Ve al [Discord Developer Portal](https://discord.com/developers/applications).
2. Crea una nueva aplicacion.
3. En la seccion Bot, crea el bot y copia su token.
4. En Privileged Gateway Intents, no necesitas activar Message Content Intent para este proyecto.
5. El bot usa `guilds` y `voice_states`, asi que asegúrate de que esos intents esten permitidos por el codigo.
6. Invita el bot al servidor con los scopes `bot` y `applications.commands`.
7. Dale permisos de voz como minimo:
   - View Channel
   - Connect
   - Speak

Si quieres probar diagnosticos de permisos, conviene dejar tambien `Move Members` solo para casos de administracion, aunque no es necesario para reproducir musica.

## Variables de entorno

El bot y Lavalink leen el secreto desde el entorno. `config.py` falla al iniciar si faltan los valores obligatorios.
Si arrancas con [bootstrap.py](bootstrap.py), el script crea `.env` desde [.env.example](.env.example) si hace falta y te pide `BOT_TOKEN` en la primera ejecucion.

Variables usadas:

- `BOT_TOKEN`: token del bot de Discord.
- `LAVALINK_HOST`: host de Lavalink. Por defecto `localhost`.
- `LAVALINK_PORT`: puerto de Lavalink. Por defecto `2333`.
- `LAVALINK_PASSWORD`: clave compartida entre el bot y Lavalink.

Archivo de ejemplo: [.env.example](.env.example)

Ejemplo de `.env`:

```env
BOT_TOKEN=tu_token_de_discord
LAVALINK_HOST=localhost
LAVALINK_PORT=2333
LAVALINK_PASSWORD=tu_password_compartida
```

## Instalacion inicial

```bash
./venv/bin/python bootstrap.py
```

Este comando crea el entorno virtual local si falta, instala las dependencias fijadas, pide `BOT_TOKEN` si no esta guardado, prepara Lavalink.jar si no existe y luego arranca Lavalink y el bot.

Si prefieres hacerlo por partes, puedes crear el entorno manualmente e instalar con `pip`, pero el bootstrap ya cubre todo el flujo habitual.

## Configurar Lavalink

El backend vive en [lavalink/application.yml](lavalink/application.yml). El archivo ya esta preparado para leer la clave desde `LAVALINK_PASSWORD`.
El jar principal de Lavalink se descarga automaticamente en el primer arranque si no existe. Los plugins siguen viviendo como artefactos locales dentro de [lavalink/plugins/](lavalink/plugins/); no es necesario versionarlos en el repositorio.

Puntos importantes:

- El puerto por defecto es `2333`.
- El password de Lavalink debe coincidir con `LAVALINK_PASSWORD`.
- YouTube esta habilitado a traves del plugin.
- La fuente nativa de YouTube de Lavalink esta desactivada porque el plugin es la ruta esperada.

Arranque recomendado desde la carpeta `lavalink`:

```bash
set -a
source ../.env
set +a
java -jar Lavalink.jar --spring.config.additional-location=file:./
```

Si prefieres lanzarlo desde la raiz del proyecto, apunta al jar y a la carpeta de configuracion:

```bash
set -a
source .env
set +a
java -jar lavalink/Lavalink.jar --spring.config.additional-location=file:/home/james/bot-discord/lavalink/
```

## Ejecutar el bot

Abre otra terminal, carga el mismo entorno y arranca Python:

```bash
set -a
source .env
set +a
./venv/bin/python main.py
```

Cuando el bot arranca, sincroniza los comandos slash automaticamente desde [main.py](main.py).

## Arranque automatizado

Si ya tienes el entorno preparado y solo quieres levantar Lavalink y el bot, usa el lanzador incluido:

```bash
./venv/bin/python run.py
```

Ese script hace esto:

1. Lee `.env`.
2. Si `LAVALINK_PASSWORD` esta vacio, genera uno nuevo automaticamente.
3. Guarda ese valor en `.env`.
4. Prepara o descarga `Lavalink.jar` si falta e inicia Lavalink.
5. Espera a que responda `/version`.
6. Inicia el bot con el mismo entorno.

Con esto el usuario solo necesita poner `BOT_TOKEN` una vez.

## Comandos disponibles

### Musica

- `/play query:` reproduce una cancion o una busqueda de YouTube y la pone en cola.
- `/add query:` añade una cancion a la cola sin interrumpir la reproduccion actual.
- `/playlist query:` reproduce una playlist publica de YouTube por URL o por busqueda con titulo + autor.
- `/queue` muestra la cola actual.
- `/skip` salta la pista actual.
- `/pause` pausa la reproduccion.
- `/resume` reanuda la reproduccion.
- `/stop` detiene todo y desconecta el bot.
- `/nowplaying` muestra la pista actual y su progreso.

## Problemas comunes

### `BOT_TOKEN must be set in the environment`

No cargaste las variables de entorno antes de iniciar el bot. Ejecuta `source .env` o exporta los valores en tu shell.

### `LAVALINK_PASSWORD must be set in the environment`

La clave no esta disponible para el proceso de Python o para Lavalink. Asegurate de exportarla antes de arrancar ambos.

### `Cannot connect to host localhost:2333`

Lavalink no esta corriendo, esta en otro host o el puerto no coincide.

### `La dirección ya se está usando`

El puerto `2333` ya esta ocupado por otro proceso de Lavalink o por una instancia anterior que no cerraste.

### El bot entra al canal pero no suena nada

- Revisa que el bot tenga permisos `Connect` y `Speak`.
- Confirma que Lavalink y el bot comparten el mismo `LAVALINK_PASSWORD`.

## Seguridad

- No subas tu `.env` al repositorio.
- Rota el token del bot si alguna vez estuvo escrito en claro.
- Mantén sincronizado el password de Lavalink entre el bot y `application.yml`.

## Notas de implementacion

- `yt-dlp` se ejecuta fuera del event loop para evitar bloqueos.
- El puente de voz usa `utils/lavalink_voice.py` en lugar de Mafic.
- La busqueda prueba variantes con `audio`, prioriza la version original cuando la consulta incluye pistas del artista y penaliza resultados tipo cover/letra/lyrics/en vivo.
- Para playlists publicas, el bot puede resolver URLs publicas de YouTube directamente, o buscar la playlist por nombre + autor con el comando `/playlist`.
- Si quieres la lista exacta, la forma mas precisa sigue siendo pegar la URL publica de la playlist de YouTube; si no la tienes, usa el titulo de la playlist junto con el autor.
- Las dependencias estan fijadas para reproducibilidad.
