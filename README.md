# Bot de musica para Discord

Bot de musica para Discord basado en `discord.py` y `Lavalink`. Reproduce audio desde YouTube, usa comandos slash y separa el backend de voz en un servicio dedicado.

## Arranque recomendado

La forma recomendada de instalar y ejecutar el proyecto es con Docker Compose.

```bash
cp .env.docker.example .env
docker compose up --build
```

Para detenerlo:

```bash
docker compose down
```

Para ver logs:

```bash
docker compose logs -f
```

## Que incluye Docker

- `bot`: ejecuta `main.py` con Python y las dependencias fijadas.
- `lavalink`: ejecuta Lavalink en su propio contenedor.
- Ambos servicios se comunican por red interna usando `LAVALINK_HOST=lavalink`.

Con Docker no necesitas instalar Python, Java ni crear un `venv` en el host.

Docker es el flujo por defecto; el modo local queda como alternativa para desarrollo o casos especiales.

## Requisitos

Si usas Docker:

- Docker
- Docker Compose
- Una aplicacion de Discord con bot creado

Si usas instalacion local:

- Python 3.14 o compatible con `requirements.txt`
- Un JDK compatible con Lavalink 4.2.2

## Configurar Discord

1. Ve al [Discord Developer Portal](https://discord.com/developers/applications).
2. Crea una nueva aplicacion.
3. En la seccion Bot, crea el bot y copia su token.
4. En Privileged Gateway Intents, no necesitas activar Message Content Intent.
5. El bot usa `guilds` y `voice_states`.
6. Invita el bot con los scopes `bot` y `applications.commands`.
7. Dale permisos de voz como minimo:
   - View Channel
   - Connect
   - Speak

## Variables de entorno

El proyecto lee la configuracion desde `.env`.

Variables usadas:

- `BOT_TOKEN`: token del bot de Discord.
- `LAVALINK_HOST`: host de Lavalink. En Docker lo usa el servicio `bot`, en local suele ser `localhost`.
- `LAVALINK_PORT`: puerto de Lavalink. Por defecto `2333`.
- `LAVALINK_HOST_PORT`: puerto del host para publicar Lavalink. Por defecto `2333`.
- `LAVALINK_PASSWORD`: clave compartida entre el bot y Lavalink.

Ejemplo local:

```env
BOT_TOKEN=tu_token_de_discord
LAVALINK_HOST=localhost
LAVALINK_PORT=2333
LAVALINK_PASSWORD=tu_password_compartida
```

Ejemplo para Docker:

```env
BOT_TOKEN=tu_token_de_discord
LAVALINK_PASSWORD=tu_password_compartida
LAVALINK_HOST_PORT=2333
```

## Estructura

- `main.py` arranca el bot y conecta a Lavalink.
- `config.py` lee variables de entorno.
- `cogs/music.py` contiene los comandos de musica.
- `utils/lavalink_voice.py` implementa el puente de voz.
- `utils/search.py` resuelve busquedas con yt-dlp.
- `lavalink/application.yml` configura Lavalink.
- `docker-compose.yml` define el stack Docker.

## Uso con Docker

### Primer arranque

```bash
cp .env.docker.example .env
docker compose up --build
```

### Parar el stack

```bash
docker compose down
```

### Ver logs

```bash
docker compose logs -f
```

### Notas

- Lavalink expone el puerto `2333`.
- Si `2333` ya esta ocupado en el host, cambia `LAVALINK_HOST_PORT` en `.env`.
- El bot usa `lavalink` como host interno.
- Si cambias `LAVALINK_PASSWORD`, reinicia ambos contenedores.

## Uso local

Si prefieres ejecutar sin Docker, puedes usar el flujo tradicional.

### Instalar dependencias

```bash
./venv/bin/python bootstrap.py
```

### Ejecutar Lavalink

```bash
set -a
source .env
set +a
java -jar lavalink/Lavalink.jar --spring.config.additional-location=file:./lavalink/
```

### Ejecutar el bot

```bash
set -a
source .env
set +a
./venv/bin/python main.py
```

### Arranque automatizado local

```bash
./venv/bin/python run.py
```

`run.py` prepara Lavalink, espera a que responda y luego inicia el bot.

## Comandos disponibles

- `/play query:` reproduce una cancion o busqueda.
- `/add query:` añade una cancion a la cola.
- `/playlist query:` reproduce una playlist publica de YouTube.
- `/queue` muestra la cola actual.
- `/skip` salta la pista actual.
- `/pause` pausa la reproduccion.
- `/resume` reanuda la reproduccion.
- `/stop` detiene todo y desconecta el bot.
- `/nowplaying` muestra la pista actual y su progreso.
- `/autoplay` activa o desactiva la continuacion automatica de musica. Cuando esta activo, al vaciarse la cola el bot busca y añade canciones relacionadas con la ultima pista reproducida.

## Problemas comunes

### `BOT_TOKEN must be set in the environment`

Falta `BOT_TOKEN` en `.env` o en el entorno.

### `LAVALINK_PASSWORD must be set in the environment`

Falta la clave compartida entre el bot y Lavalink.

### `Cannot connect to host localhost:2333`

Lavalink no esta corriendo, esta en otro host o el puerto no coincide.

### `address already in use`

El puerto `2333` ya esta ocupado por otro proceso.

## Seguridad

- No subas `.env` al repositorio.
- Rota el token del bot si alguna vez estuvo expuesto.
- Mantén sincronizado `LAVALINK_PASSWORD` entre el bot y Lavalink.

## Termux

Si quieres ejecutarlo en Android con Termux, revisa `install_termux.sh`.
