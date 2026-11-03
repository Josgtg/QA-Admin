# QA-Admin

Aplicación web para que un encargado de calidad (QA) administre varios proyectos,
aplique modelos de calidad, seleccione técnicas de QA y registre evidencias para
medir la salud de cada proyecto.

El proyecto se construye por releases a partir de las historias de usuario
definidas en [`historias_de_usuario.md`](historias_de_usuario.md).

## Tecnologías

| Componente | Versión / herramienta |
| --- | --- |
| Lenguaje | Python 3.12 |
| Framework | Django 6.1.2 |
| Base de datos | SQLite (`db.sqlite3`) |
| Frontend | HTML, CSS y JavaScript sin framework |
| Diagramas | PlantUML (`diagrams/*.puml`) |

## Estructura del proyecto

```
QA-Admin/
├── apps/
│   ├── modelos/          # Modelos de calidad y métricas (en construcción)
│   ├── tecnicas/         # Técnicas QA, pasos, seguimiento y evidencias
│   └── reportes/         # Reportes y exportación (en construcción)
├── diagrams/             # Diagramas PlantUML (clases y secuencia)
├── qa_admin/             # Configuración, URLs y vistas del proyecto Django
├── static/css/app.css    # Estilos de la interfaz
├── templates/            # Plantillas HTML (base, demo, técnicas)
├── historias_de_usuario.md
├── manage.py
└── requirements.txt
```

## Puesta en marcha

### 1. Requisitos

- Python 3.12 o superior
- Git

### 2. Clonar e instalar

```bash
git clone <url-del-repositorio>
cd QA-Admin

python3 -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Base de datos y usuario administrador

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Ejecutar el servidor

```bash
python manage.py runserver
```

Rutas disponibles:

| Ruta | Descripción |
| --- | --- |
| `/admin/` | Administración de Django |
| `/demo/` | Demo de la interfaz visual |
| `/tecnicas/seguimiento/` | Selección de técnicas QA por proyecto (HU-05) |
<<<<<<< Updated upstream
| `/modelos/proyecto/` | Modelo de calidad del proyecto activo: abre el ítem «Modelos de Calidad» del menú lateral (HU-02) |
| `/modelos/` | Catálogo de modelos de calidad predefinidos (HU-03), desde el botón «Ver catálogo de modelos» |
| `/` | Proyectos agrupados y filtrados por periodo (HU-07) |
| `/crear/` | Registro de un nuevo proyecto (HU-07) |
=======
| `/modelos/` | Catálogo de modelos de calidad predefinidos (HU-03) |
| `/proyectos/<id>/metricas/` | Estado de las métricas del proyecto (HU-08) |
| `/proyectos/<id>/metricas/<metrica_id>/` | Historial de mediciones de una métrica (HU-08) |
| `/proyectos/` | Proyectos agrupados y filtrados por periodo (HU-07) |
| `/proyectos/crear/` | Registro de un nuevo proyecto (HU-07) |
| `/proyectos/<id>/` | Tablero del proyecto (HU-07) |
| `/` | Inicio: redirige al último proyecto abierto o a la lista |
>>>>>>> Stashed changes

La migración `tecnicas.0004_tecnicas_ejemplo` carga un catálogo base con dos
técnicas de ejemplo: Revisión de código y Revisión de requisitos.

## Flujo de trabajo con Git

- `main`: versión estable.
- Ramas por historia de usuario, por ejemplo `hu5` para la HU-05.
- Antes de empezar una HU, actualiza `main` y crea tu rama:

```bash
git checkout main
git pull
git checkout -b huXX
```

- Los mensajes de commit se escriben en español y describen el cambio:

```bash
git add .
git commit -m "Añadida lógica huXX"
```

## Diagramas

Los diagramas de clases y de secuencia están en `diagrams/` en formato PlantUML.
Se pueden visualizar con la extensión de PlantUML de VS Code / IntelliJ o con el
CLI de PlantUML:

```bash
plantuml diagrams/*.puml
```
