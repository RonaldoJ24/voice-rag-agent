# Gold set review sample v1 (20 of 68 rows, seed 20261020)

For each row, check three things and mark it OK or write the fix:
1. The question sounds like something a real person would ask (spoken rows are casual on purpose).
2. The gold sections really answer it (open the links).
3. The reference answer is correct and complete for those sections.

Unanswerable rows should NOT be answerable from the FastAPI docs. Small-talk rows should need no search.

## en-02 (answerable, en, spoken)

**Question:** How do I make a route need a login?

**Gold sections:** [tutorial/security/first-steps.md#fastapis-oauth2passwordbearer](https://fastapi.tiangolo.com/tutorial/security/first-steps/#fastapis-oauth2passwordbearer), [tutorial/security/first-steps.md#use-it](https://fastapi.tiangolo.com/tutorial/security/first-steps/#use-it), [tutorial/security/first-steps.md#what-it-does](https://fastapi.tiangolo.com/tutorial/security/first-steps/#what-it-does), [advanced/security/http-basic-auth.md#simple-http-basic-auth](https://fastapi.tiangolo.com/advanced/security/http-basic-auth/#simple-http-basic-auth)

**Reference answer:** Create an OAuth2PasswordBearer scheme and use it as a dependency with Depends. If the request has no Authorization header with a Bearer token, FastAPI answers with a 401 before your function runs.

**Verdict:** OK / fix: 

## en-07 (answerable, en, spoken)

**Question:** How do I make sure my database session gets closed after every request?

**Gold sections:** [tutorial/dependencies/dependencies-with-yield.md#a-database-dependency-with-yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#a-database-dependency-with-yield), [tutorial/dependencies/dependencies-with-yield.md#dependencies-with-yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield), [tutorial/dependencies/dependencies-with-yield.md#a-dependency-with-yield-and-try](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#a-dependency-with-yield-and-try)

**Reference answer:** Use a dependency with yield: the code before the yield creates the session and the code after it runs once the response is done, so you can close the session there. A try/finally makes sure the cleanup always runs.

**Verdict:** OK / fix: 

## en-11 (answerable, en, written)

**Question:** Why does my fixed route /users/me get swallowed by /users/{user_id}?

**Gold sections:** [tutorial/path-params.md#order-matters](https://fastapi.tiangolo.com/tutorial/path-params/#order-matters)

**Reference answer:** Path operations are evaluated in order, so the fixed path /users/me has to be declared before /users/{user_id}.

**Verdict:** OK / fix: 

## en-15 (answerable, en, spoken)

**Question:** Can an endpoint give back an HTML page instead of JSON?

**Gold sections:** [advanced/custom-response.md#return-a-response](https://fastapi.tiangolo.com/advanced/custom-response/#return-a-response), [advanced/custom-response.md#htmlresponse](https://fastapi.tiangolo.com/advanced/custom-response/#htmlresponse), [advanced/custom-response.md#custom-response-html-stream-file-others](https://fastapi.tiangolo.com/advanced/custom-response/#custom-response-html-stream-file-others)

**Reference answer:** Yes. Set response_class to HTMLResponse in the path operation decorator, or return an HTMLResponse directly.

**Verdict:** OK / fix: 

## en-16 (answerable, en, written)

**Question:** My app runs behind a proxy that strips a path prefix, so the docs page breaks. How do I tell FastAPI about the prefix?

**Gold sections:** [advanced/behind-a-proxy.md#providing-the-root-path](https://fastapi.tiangolo.com/advanced/behind-a-proxy/#providing-the-root-path), [advanced/behind-a-proxy.md#proxy-with-a-stripped-path-prefix](https://fastapi.tiangolo.com/advanced/behind-a-proxy/#proxy-with-a-stripped-path-prefix)

**Reference answer:** Give FastAPI the prefix as the root path, for example with the --root-path command line option (like --root-path /api/v1), so the docs and OpenAPI use the right URLs.

**Verdict:** OK / fix: 

## en-21 (answerable, en, spoken)

**Question:** Can you walk me through writing a Dockerfile for my FastAPI app?

**Gold sections:** [deployment/docker.md#dockerfile](https://fastapi.tiangolo.com/deployment/docker/#dockerfile), [deployment/docker.md#build-a-docker-image-for-fastapi](https://fastapi.tiangolo.com/deployment/docker/#build-a-docker-image-for-fastapi), [deployment/docker.md#build-the-docker-image](https://fastapi.tiangolo.com/deployment/docker/#build-the-docker-image)

**Reference answer:** Start from the official Python image, set a working directory, copy and install requirements.txt first, copy your app code, and end with a CMD in exec form that runs fastapi run on port 80.

**Verdict:** OK / fix: 

## en-25 (answerable, en, written)

**Question:** What's the difference between fastapi dev and fastapi run?

**Gold sections:** [fastapi-cli.md#fastapi-dev](https://fastapi.tiangolo.com/fastapi-cli/#fastapi-dev), [fastapi-cli.md#fastapi-run](https://fastapi.tiangolo.com/fastapi-cli/#fastapi-run), [fastapi-cli.md#fastapi-cli](https://fastapi.tiangolo.com/fastapi-cli/#fastapi-cli)

**Reference answer:** fastapi dev starts development mode with auto-reload on and listens only on 127.0.0.1. fastapi run is production mode, with auto-reload off, listening on 0.0.0.0.

**Verdict:** OK / fix: 

## es-02 (answerable, es, spoken)

**Question:** Tengo una tarea pesada y quiero responderle primero al usuario y que se termine después. ¿Cómo lo hago?

**Gold sections:** [tutorial/background-tasks.md#using-backgroundtasks](https://fastapi.tiangolo.com/es/tutorial/background-tasks/#using-backgroundtasks), [tutorial/background-tasks.md#add-the-background-task](https://fastapi.tiangolo.com/es/tutorial/background-tasks/#add-the-background-task), [tutorial/background-tasks.md#background-tasks](https://fastapi.tiangolo.com/es/tutorial/background-tasks/#background-tasks)

**Reference answer:** Declara un parámetro de tipo BackgroundTasks en la función de tu ruta y llama a add_task con tu función y sus argumentos. FastAPI la ejecuta después de enviar la respuesta.

**Verdict:** OK / fix: 

## es-03 (answerable, es, spoken)

**Question:** Mi frontend en localhost 3000 no puede llamar a mi API porque el navegador lo bloquea. ¿Qué hago?

**Gold sections:** [tutorial/cors.md#cors-cross-origin-resource-sharing](https://fastapi.tiangolo.com/es/tutorial/cors/#cors-cross-origin-resource-sharing), [tutorial/cors.md#use-corsmiddleware](https://fastapi.tiangolo.com/es/tutorial/cors/#use-corsmiddleware), [tutorial/cors.md#steps](https://fastapi.tiangolo.com/es/tutorial/cors/#steps)

**Reference answer:** Es un tema de CORS: el navegador bloquea las llamadas a otro origen si el backend no lo permite. Agrega CORSMiddleware a tu app con la lista de orígenes permitidos.

**Verdict:** OK / fix: 

## es-05 (answerable, es, spoken)

**Question:** ¿Cómo evito que la contraseña salga en la respuesta cuando regreso un usuario?

**Gold sections:** [tutorial/response-model.md#add-an-output-model](https://fastapi.tiangolo.com/es/tutorial/response-model/#add-an-output-model), [tutorial/response-model.md#return-type-and-data-filtering](https://fastapi.tiangolo.com/es/tutorial/response-model/#return-type-and-data-filtering), [tutorial/response-model.md#response-model-return-type](https://fastapi.tiangolo.com/es/tutorial/response-model/#response-model-return-type)

**Reference answer:** Crea un modelo de salida sin el campo de la contraseña y úsalo como response model o tipo de retorno. FastAPI filtra los datos y solo envía los campos de ese modelo.

**Verdict:** OK / fix: 

## es-11 (answerable, es, written)

**Question:** ¿Cómo aplico una misma dependencia a todas las rutas de mi aplicación?

**Gold sections:** [tutorial/dependencies/global-dependencies.md#global-dependencies](https://fastapi.tiangolo.com/es/tutorial/dependencies/global-dependencies/#global-dependencies)

**Reference answer:** Agrega las dependencias a la aplicación FastAPI misma, y se aplicarán a todas las rutas de la app.

**Verdict:** OK / fix: 

## es-16 (answerable, es, written)

**Question:** ¿Se pueden devolver páginas HTML armadas con plantillas Jinja?

**Gold sections:** [advanced/templates.md#using-jinja2templates](https://fastapi.tiangolo.com/es/advanced/templates/#using-jinja2templates), [advanced/templates.md#templates](https://fastapi.tiangolo.com/es/advanced/templates/#templates)

**Reference answer:** Sí, con Jinja2Templates: creas un objeto templates, recibes la Request en la ruta y devuelves un TemplateResponse con el nombre de la plantilla, la request y un diccionario de contexto.

**Verdict:** OK / fix: 

## es-17 (answerable, es, spoken)

**Question:** ¿Cómo le pongo una cookie a la respuesta?

**Gold sections:** [advanced/response-cookies.md#response-cookies](https://fastapi.tiangolo.com/es/advanced/response-cookies/#response-cookies)

**Reference answer:** Declara un parámetro de tipo Response en la función de la ruta y define la cookie en ese objeto temporal. FastAPI la toma y la incluye en la respuesta final. También puedes devolver un Response directamente.

**Verdict:** OK / fix: 

## es-21 (answerable, es, spoken)

**Question:** Tengo código con Pydantic v1, ¿hay alguna herramienta para pasarlo a v2 sin hacerlo todo a mano?

**Gold sections:** [how-to/migrate-from-pydantic-v1-to-pydantic-v2.md#bump-pydantic](https://fastapi.tiangolo.com/es/how-to/migrate-from-pydantic-v1-to-pydantic-v2/#bump-pydantic)

**Reference answer:** Sí, bump-pydantic, del mismo equipo de Pydantic, que cambia automáticamente la mayor parte del código. Después corres tus pruebas para confirmar que todo funciona.

**Verdict:** OK / fix: 

## un-en-01 (unanswerable, en, spoken)

**Question:** How do I deploy my FastAPI app to AWS Lambda with Mangum?

**Verdict:** OK / fix: 

## un-en-02 (unanswerable, en, spoken)

**Question:** How do I take payments with Stripe in my FastAPI backend?

**Verdict:** OK / fix: 

## un-es-02 (unanswerable, es, spoken)

**Question:** ¿Cómo le hago para subir mi proyecto a Heroku?

**Verdict:** OK / fix: 

## un-es-04 (unanswerable, es, spoken)

**Question:** Quiero ver las métricas de mi API en Grafana con Prometheus, ¿cómo lo configuro?

**Verdict:** OK / fix: 

## st-en-01 (smalltalk, en, spoken)

**Question:** Hi there!

**Verdict:** OK / fix: 

## st-es-02 (smalltalk, es, spoken)

**Question:** Muchas gracias, eso era todo.

**Verdict:** OK / fix: 

