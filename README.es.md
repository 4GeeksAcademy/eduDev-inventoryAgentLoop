# API de inventario y agente CLI

[English](README.md) · [Enunciado original](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-basic-inventory-agent-loop/README.md)

Aplicación educativa mínima: un único inventario compartido, API FastAPI con CSV
y un bucle manual de herramientas con Groq. `main.py` y `server.py` son ejemplos
del starter conservados, pero no se utilizan.

## Inicio rápido: dos terminales

Instala [uv](https://docs.astral.sh/uv/) y Python 3.11 o superior. Desde la raíz:

```bash
uv sync
# Crear solo si no existe; nunca sobrescribir el .env real:
if [ ! -e .env ]; then cp -n .env.example .env; fi
# Terminal 1: primero la API
uv run uvicorn api.app:app --reload
```

Edita el `.env` local para configurar tu propio `GROQ_API_KEY`; no lo publiques.
En la terminal 2, también desde la raíz:

```bash
uv run python agent.py
```

Opcionalmente ejecuta `source .venv/bin/activate` en cada terminal para usar los
comandos del enunciado: `uvicorn api.app:app --reload` y `python agent.py`.
Con `uv run` no necesitas un comando `python` global. Documentación interactiva:
http://127.0.0.1:8000/docs. Usa un solo proceso/worker de API por archivo.

Las cuatro dependencias directas son `fastapi`, `uvicorn`, `openai` y
`python-dotenv`. El SDK OpenAI usa el endpoint compatible de Groq
`https://api.groq.com/openai/v1`, sin frameworks de agentes. `GROQ_MODEL` permite
cambiar el modelo (predeterminado `llama-3.3-70b-versatile`); `API_BASE_URL` vale
`http://127.0.0.1:8000` por defecto. Las variables del entorno tienen prioridad
sobre `.env`; solo la entrada CLI carga ese archivo, no la API ni los tests.

Detén primero el agente con `exit`, `quit`, Ctrl+C o EOF; después, la API con
Ctrl+C. Reinicia primero la API y después el agente: no se reinician ni el stock
ni el registro. Una respuesta final termina el turno, no la sesión.

## Ejemplo y límites

1. «Añade Arroz con 8 kg».
2. Inmediatamente: «Muestra alertas por debajo de 10».
3. «Llegó una entrega de 5 kg de Arroz».
4. «Vende 4 kg de Arroz».

El stock esperado es 8 → 13 → 9 kg. Las alertas usan comparación estricta
`< 10`: exactamente 10 no genera alerta. Hay un único inventario, sin sucursales
ni previsión semanal de demanda. Cada producto tiene una unidad fija; el agente
no convierte unidades y debe preguntar si faltan unidades o hay nombres ambiguos.

Las herramientas son `get_inventory`, `add_product`, `change_stock` y
`get_alerts`; el agente accede al inventario por HTTP, nunca directamente al CSV.
El historial de sesión vive en memoria y desaparece al salir. El registro de
auditoría `conversation_log.csv` persiste y añade eventos sin reemplazarlos, con
campos exactos `actor,message,tool_call,timestamp`. Incluye mensajes públicos y
solicitudes/resultados de herramientas, no razonamiento privado. Una nueva sesión
no carga el registro como historial. Es texto plano: puede contener datos privados
o secretos escritos en el chat. No introduzcas credenciales ni compartas el log.

No hay reintentos automáticos de API ni proveedor. Una escritura puede haberse
aplicado aunque expire la solicitud: consulta el inventario antes de repetirla.
Un fallo del proveedor permite continuar o salir sin repetir herramientas ya
completadas. Es un ejercicio de un usuario, no infraestructura de producción.

## API y almacenamiento

| Solicitud | Entrada | Resultado |
| --- | --- | --- |
| `GET /inventory` | Ninguna | Lista, inicialmente vacía |
| `POST /inventory` | `name`, `quantity`, `unit` | Producto creado, HTTP 201 |
| `PATCH /inventory/{product_id}` | `delta` con signo | Producto actualizado |
| `GET /inventory/alerts?threshold=10` | Umbral opcional, por defecto 10 | Productos estrictamente por debajo |

Los productos tienen `id` entero estable, `name` y `unit` sin espacios exteriores,
y `quantity` decimal. Se aceptan números JSON o cadenas decimales; las respuestas
usan cadenas para preservar precisión. Los IDs nuevos aumentan desde el mayor
existente; los nombres pueden repetirse. Campos vacíos, valores no finitos,
stock negativo o cambios bajo cero devuelven HTTP 422; un ID desconocido, 404.
El umbral debe ser finito y no negativo.

La primera escritura correcta crea `products.csv`, con cabecera
`id,name,quantity,unit`. `INVENTORY_CSV_PATH` permite otro archivo antes de iniciar
la API. Las rutas relativas se resuelven desde la raíz del proyecto; se admiten
rutas absolutas y el directorio padre debe existir. Un CSV malformado devuelve
HTTP 500 sin sobrescribirlo; repáralo manualmente. El bloqueo solo protege dentro
del proceso: no hay transacciones resistentes a fallos ni bloqueo multiproceso.
Conserva copias de seguridad de datos valiosos.

## Comprobaciones locales

```bash
# Checks acotados:
uv run python -m unittest discover -s tests -p 'test_api.py' -v
uv run python -m unittest discover -s tests -p 'test_agent.py' -v
uv run python -m unittest discover -s tests -p 'test_integration.py' -v
# Suite final:
uv run python -m unittest discover -s tests -v
```

Los tests usan archivos temporales, sin credenciales, lecturas de `.env` ni llamadas
a proveedores. API e integración usan servidores HTTP locales desechables;
la integración simula solo las respuestas del SDK y verifica historial,
persistencia tras reinicio y registro acumulado entre sesiones. No se ha verificado
una llamada real a Groq; esa comprobación con credenciales sigue pendiente.

Git ignora `.env`, `.venv`, bytecode, `products.csv` y `conversation_log.csv`.
Nunca publiques secretos. Antes de entregar, revisa los requisitos de repositorio,
enlace y demostración del enunciado y excluye CSV privados y credenciales.
Publicar es un paso manual separado.

### Contribuidores

Esta plantilla fue creada como parte de los [Recursos de Python de 4Geeks](https://4geeks.com/es/technology/python) para el aprendizaje en [4Geeks.com](https://4geeks.com) por [Alejandro Sanchez](https://twitter.com/alesanchezr) y [muchos otros contribuyentes](https://github.com/4GeeksAcademy/python-hello/graphs/contributors).
