# Judge spot-check v1 (30 random judgments, models hidden)

For each row, say whether you agree with the judge's verdict. Disagreements measure judge error.

## 1. en-04 (answerable, en)

**Question:** My frontend on localhost 3000 keeps getting blocked when it calls my API. What's going on, and how do I fix it?

**Reference answer:** That is CORS: the browser blocks calls to a different origin unless the backend allows it. Add CORSMiddleware to your app with the list of origins you want to allow.

**Spoken answer:** Let me check the docs. Your frontend at localhost on port 3000 and your API are on different origins, because the port counts as part of the origin. That's CORS, and the browser blocks the calls unless your API says it allows that origin.

To fix it, add FastAPI's CORSMiddleware to your app and put "http://localhost:3000" in the list of allowed origins. The defaults are restrictive, so you may also need to allow methods and headers, since only GET is allowed by default.

If you use cookies or authorization headers, enable allow credentials. In that case you can't use the wildcard, so you have to list origins, methods, and headers explicitly. The CORS page in the tutorial has the details.

**Judge:** PASS. The answer correctly identifies CORS and tells the user to add CORSMiddleware with http://localhost:3000 as an allowed origin, and every detail it adds is supported by the retrieved CORS sections (port being part of the origin, restrictive defaults, GET-only default methods, no wildcards with credentials).

**Agree?** yes / no: 

## 2. en-05 (answerable, en)

**Question:** What do I do to send back a 404 when the item isn't there?

**Reference answer:** Raise an HTTPException with a status code of 404 and a detail message. You raise it instead of returning it, so the rest of the function does not run.

**Spoken answer:** Let me check the docs. To send a 404, you raise an HTTPException with status code 404 and a detail message when the item isn't found. FastAPI then returns that error to the client as a normal response. The main error handling page in the docs, called Handling Errors, shows this pattern.

**Judge:** FAIL. The answer matches the reference, but the retrieved sections never show raising HTTPException with status_code 404 and a detail message, and the retrieved Handling Errors excerpt doesn't demonstrate that pattern, so these specifics are unsupported.

**Agree?** yes / no: 

## 3. en-07 (answerable, en)

**Question:** How do I make sure my database session gets closed after every request?

**Reference answer:** Use a dependency with yield: the code before the yield creates the session and the code after it runs once the response is done, so you can close the session there. A try/finally makes sure the cleanup always runs.

**Spoken answer:** Let me check the docs. The way to do this in FastAPI is to write a dependency function that creates the session, uses yield to hand it to your path operations, and closes it in the code after the yield. FastAPI runs that cleanup after the response is sent, by default. If you want it to close earlier, right after your path operation function returns, you can pass scope="function" to Depends(). The docs for this are in the "Dependencies with yield" tutorial page, under "A database dependency with yield" and "Early exit and scope".

**Judge:** PASS. The answer correctly describes using a yield dependency that creates the session and closes it after the yield, running after the response by default, with scope="function" for earlier closing, all supported by the retrieved sections; omitting the try/finally detail is minor.

**Agree?** yes / no: 

## 4. en-09 (answerable, en)

**Question:** How would I serve my images and CSS files from the app itself?

**Reference answer:** Mount a StaticFiles instance at a path, pointing it at the directory that holds your files.

**Spoken answer:** Let me check the docs. You can use FastAPI's StaticFiles class. Import it, then mount an instance at a path like "/static", pointing at the folder that holds your images and CSS. Anything requested under that path gets served from that folder. The details are on the Static Files page of the tutorial.

**Judge:** PASS. The answer correctly says to import StaticFiles and mount it at a path such as "/static" pointing at the folder of files, and every claim is supported by the retrieved Static Files sections.

**Agree?** yes / no: 

## 5. en-12 (answerable, en)

**Question:** How do I update only the fields the client actually sent, instead of overwriting the whole item?

**Reference answer:** Use PATCH for partial updates, and call the Pydantic model's model_dump with exclude_unset so you only get the fields the client really sent.

**Spoken answer:** Let me check the docs. To update only what the client sent, use a Pydantic model and call its model dump method with exclude unset set to True. That gives you a dictionary with just the fields the request included, leaving out defaults. Then make a copy of the stored model with model copy, passing that dictionary as the update parameter, and save the result. The Body Updates page in the tutorial walks through this, and it works with PATCH, though it can also be used with PUT.

**Judge:** PASS. The answer correctly describes using model_dump with exclude_unset, then model_copy with update, and mentions PATCH (or PUT), all supported by the retrieved Body - Updates sections.

**Agree?** yes / no: 

## 6. en-13 (answerable, en)

**Question:** Can FastAPI do real time two-way stuff, like a chat?

**Reference answer:** Yes, with WebSockets. You create a websocket in your app, then in the route you await incoming messages and send messages back.

**Spoken answer:** Let me check the docs. Yes, FastAPI supports WebSockets, which give you a two-way connection where the client and server can keep sending messages back and forth over the same connection, perfect for something like a chat. You install the websockets library, then define a WebSocket endpoint. In those endpoints you can also use things like Depends, Query, Header, and Cookie, just like in regular endpoints. The WebSockets page in the advanced section has a working example with a simple chat-style page you can try.

**Judge:** PASS. The assistant correctly says FastAPI supports two-way real-time communication via WebSockets over a single connection, and every specific claim (installing websockets, defining an endpoint, using Depends/Query/Header/Cookie, the advanced-section chat example) is supported by the retrieved sections.

**Agree?** yes / no: 

## 7. en-15 (answerable, en)

**Question:** Can an endpoint give back an HTML page instead of JSON?

**Reference answer:** Yes. Set response_class to HTMLResponse in the path operation decorator, or return an HTMLResponse directly.

**Spoken answer:** Let me check the docs. Yes, it can. You can return an HTMLResponse object from your endpoint, and FastAPI will send your HTML with the text/html type instead of JSON. You can also set response class to HTMLResponse so the docs describe it as HTML. The details are on the Custom Response page, under the HTMLResponse and "Return a Response" sections.

**Judge:** PASS. The answer correctly says to return an HTMLResponse or set response_class to HTMLResponse, and each claim, including that response_class documents the response as text/html, is supported by the retrieved Custom Response sections.

**Agree?** yes / no: 

## 8. en-16 (answerable, en)

**Question:** My app runs behind a proxy that strips a path prefix, so the docs page breaks. How do I tell FastAPI about the prefix?

**Reference answer:** Give FastAPI the prefix as the root path, for example with the --root-path command line option (like --root-path /api/v1), so the docs and OpenAPI use the right URLs.

**Spoken answer:** Let me check the docs. You tell FastAPI about the stripped prefix with the root path setting. You can start the server with the root path option, for example fastapi run with --root-path set to your prefix, or pass it when creating the app. That makes the docs UI request the OpenAPI schema under the prefix, so the page works. The "Behind a Proxy" page in the advanced docs walks through this with a Traefik example.

**Judge:** FAIL. The core answer (use fastapi run --root-path with the prefix so the docs UI fetches the OpenAPI schema under it) matches the reference, but the claim that you can instead pass the root path when creating the app is not supported by any retrieved section.

**Agree?** yes / no: 

## 9. en-18 (answerable, en)

**Question:** Is there a way to hide the /docs page once I deploy to production?

**Reference answer:** Yes. Take openapi_url from a setting or environment variable and set it to an empty string in production, which disables OpenAPI and the docs UIs. The docs also warn that hiding them is not real security.

**Spoken answer:** Let me check the docs. Yes, you can hide it. Set the docs URL parameter to None when you create your FastAPI app to turn off Swagger UI at slash docs, and do the same with the redoc URL parameter for ReDoc. For production, the Conditional OpenAPI page shows how to read the OpenAPI URL from settings. If you set that environment variable to an empty string, the docs and the OpenAPI schema all return a 404. Hiding the docs isn't real security, because your endpoints are still reachable, so you should still protect them with proper permissions and authentication.

**Judge:** PASS. The answer covers docs_url=None, the conditional openapi_url env var set to empty (which returns 404s) and the security-through-obscurity warning, all supported by the retrieved sections.

**Agree?** yes / no: 

## 10. en-20 (answerable, en)

**Question:** Does FastAPI work with GraphQL, and which library should I pick?

**Reference answer:** Yes, with any GraphQL library that supports ASGI. Strawberry is the recommended one because its design is closest to FastAPI's.

**Spoken answer:** Let me check the docs. Yes, FastAPI works with GraphQL, since it follows the ASGI standard and GraphQL libraries with ASGI support can plug in. The docs recommend Strawberry, because its design is closest to FastAPI's and it's built on type annotations. Other options listed are Ariadne, Tartiflette, and Graphene through starlette-graphene3. You can read this on the GraphQL page of the how-to guides.

**Judge:** PASS. The answer correctly says FastAPI works with any ASGI-compatible GraphQL library and recommends Strawberry for its FastAPI-like, type-annotation-based design, and every claim, including the alternative libraries, is supported by the retrieved sections.

**Agree?** yes / no: 

## 11. en-21 (answerable, en)

**Question:** Can you walk me through writing a Dockerfile for my FastAPI app?

**Reference answer:** Start from the official Python image, set a working directory, copy and install requirements.txt first, copy your app code, and end with a CMD in exec form that runs fastapi run on port 80.

**Spoken answer:** Let me check the docs. The docs suggest a short Dockerfile. You start from the official Python image, set the working directory to a folder called code, and copy in your requirements file first. Then you install the requirements, copy your app folder, and set the start command to run the app with fastapi run on port 80. Copying the requirements before your code lets Docker cache the install step, so rebuilds are faster. The full example is on the FastAPI in Containers page, under the Docker section.

**Judge:** PASS. The answer matches the reference steps: official Python image, WORKDIR /code, requirements copied and installed first, then app code, then a fastapi run command on port 80, and the caching explanation is supported by the retrieved Dockerfile section.

**Agree?** yes / no: 

## 12. es-02 (answerable, es)

**Question:** Tengo una tarea pesada y quiero responderle primero al usuario y que se termine después. ¿Cómo lo hago?

**Reference answer:** Declara un parámetro de tipo BackgroundTasks en la función de tu ruta y llama a add_task con tu función y sus argumentos. FastAPI la ejecuta después de enviar la respuesta.

**Spoken answer:** Déjame revisar la documentación. En FastAPI puedes hacer esto con BackgroundTasks. Declaras un parámetro de tipo BackgroundTasks en tu función de ruta, y dentro llamas al método add task con tu función pesada. FastAPI devuelve la respuesta al usuario y luego ejecuta esa tarea. Está explicado en la página de Tareas en Segundo Plano del tutorial.

**Judge:** PASS. The answer matches the reference: declare a BackgroundTasks parameter, call add_task, and the task runs after the response is sent, all of which the retrieved background-tasks sections support.

**Agree?** yes / no: 

## 13. es-03 (answerable, es)

**Question:** Mi frontend en localhost 3000 no puede llamar a mi API porque el navegador lo bloquea. ¿Qué hago?

**Reference answer:** Es un tema de CORS: el navegador bloquea las llamadas a otro origen si el backend no lo permite. Agrega CORSMiddleware a tu app con la lista de orígenes permitidos.

**Spoken answer:** Déjame revisar la documentación. Lo que pasa es que tu API tiene que permitir explícitamente el origen de tu frontend, que es http://localhost:3000. En FastAPI se hace con el CORSMiddleware: lo importas, pones http://localhost:3000 en la lista de orígenes permitidos y lo agregas a tu aplicación. Revisa la página de tutorial de CORS en la documentación para ver el ejemplo completo.

**Judge:** PASS. The assistant correctly says the fix is to add CORSMiddleware with http://localhost:3000 in the allowed origins, and every claim is supported by the retrieved CORS sections.

**Agree?** yes / no: 

## 14. es-03 (answerable, es)

**Question:** Mi frontend en localhost 3000 no puede llamar a mi API porque el navegador lo bloquea. ¿Qué hago?

**Reference answer:** Es un tema de CORS: el navegador bloquea las llamadas a otro origen si el backend no lo permite. Agrega CORSMiddleware a tu app con la lista de orígenes permitidos.

**Spoken answer:** Déjame revisar la documentación. Necesitas habilitar CORS en tu API con el CORSMiddleware de FastAPI. Lo importas, creas una lista de orígenes permitidos que incluya http://localhost:3000, y lo agregas como middleware a tu aplicación.

Por defecto es muy restrictivo, así que también tienes que habilitar los métodos y headers que uses, con allow methods y allow headers. Si usas cookies o tokens de autorización, activa allow credentials, pero entonces no puedes usar el comodín "" y debes listar todo explícitamente. Lo encuentras en la página de CORS del tutorial.

**Judge:** PASS. The answer correctly identifies CORS and says to add CORSMiddleware with http://localhost:3000 as an allowed origin, and its points on restrictive defaults, allow_methods/allow_headers and no wildcards with credentials are all supported by the retrieved CORS sections.

**Agree?** yes / no: 

## 15. es-04 (answerable, es)

**Question:** Mi main.py ya quedó enorme. ¿Cómo divido mis rutas en varios archivos?

**Reference answer:** Pon las rutas relacionadas en sus propios módulos usando APIRouter y luego agrega cada router a la app principal con app.include_router().

**Spoken answer:** Déjame revisar la documentación. Puedes mover tus rutas a archivos separados usando APIRouter, que funciona como una especie de "mini FastAPI". En cada archivo, por ejemplo uno de usuarios y otro de items, creas un router y declaras ahí tus rutas igual que en la app principal. Después, en tu main.py, incluyes cada router con include router, y puedes agregarle un prefijo, tags o dependencias sin tocar el archivo original. La guía está en la página "Aplicaciones más grandes - Múltiples archivos".

**Judge:** PASS. The answer covers the reference's key point (create an APIRouter in each module, then add each one with app.include_router), and every claim, including the prefix/tags/dependencies option and the page name, is supported by the retrieved sections.

**Agree?** yes / no: 

## 16. es-07 (answerable, es)

**Question:** Quiero conectar mi API a una base de datos SQL, empezando con SQLite. ¿Cómo lo armo?

**Reference answer:** Con SQLModel creas un engine, que guarda las conexiones a la base de datos, y creas las tablas con SQLModel.metadata.create_all. Para SQLite usas check_same_thread=False y una sesión por petición con una dependencia con yield.

**Spoken answer:** Déjame revisar la documentación. Para empezar, instala SQLModel con uv add sqlmodel. Después, en el tutorial de Bases de Datos SQL, verás cómo crear un engine, que es el objeto que mantiene las conexiones a tu archivo de SQLite. Luego defines tus modelos de tabla con SQLModel y usas una sesión por request para leer y escribir datos. Lo revisas en la página de Bases de Datos SQL (Relacionales) de la documentación.

**Judge:** PASS. The answer correctly covers installing SQLModel, creating an engine that holds the SQLite connections, defining table models, and using one session per request, all supported by the retrieved sections; omitting check_same_thread=False and create_all is a minor gap.

**Agree?** yes / no: 

## 17. es-10 (answerable, es)

**Question:** ¿Puedo ejecutar código en todas las peticiones, por ejemplo para medir cuánto tarda cada una?

**Reference answer:** Sí, con un middleware: decoras una función con @app.middleware("http"), recibe la request y call_next, y puedes medir el tiempo y agregar una cabecera como X-Process-Time a la respuesta.

**Spoken answer:** Déjame revisar la documentación. Sí, puedes hacerlo con un middleware. Es una función que recibe cada petición antes de que llegue a tu ruta y cada respuesta antes de enviarla, así que puedes anotar la hora de inicio, dejar que la petición siga, y restar al final para calcular cuánto tardó. La documentación muestra este caso exacto: añadir un encabezado personalizado llamado X-Process-Time con los segundos de procesamiento, usando time.perf counter para medir. Lo encontrarás en la página de Middleware del tutorial.

**Judge:** PASS. The answer correctly identifies middleware as the solution and describes the X-Process-Time header timed with time.perf_counter, all of which the retrieved middleware sections support; omitting the @app.middleware("http") decorator and call_next is only a minor gap.

**Agree?** yes / no: 

## 18. es-13 (answerable, es)

**Question:** ¿Cómo cambio el código de estado HTTP que devuelve una ruta, por ejemplo para responder 201 al crear algo?

**Reference answer:** Pasa el parámetro status_code en el decorador de la ruta. El código se devuelve en la respuesta y también se documenta en OpenAPI.

**Spoken answer:** Déjame revisar la documentación. Para responder 201 al crear algo, pasas status code en el decorador de la ruta, por ejemplo @app.post(...), y le pones el número 201. Si no quieres memorizar números, puedes usar status.HTTP 201 CREATED importando status desde fastapi. También existe un caso más avanzado, donde cambias el código dentro de la función con un parámetro Response; lo encuentras en la página de cambio de código de estado de respuesta de la documentación avanzada.

**Judge:** PASS. The answer correctly says to pass status_code=201 in the route decorator, matching the reference, and each claim is supported by the retrieved sections: the fastapi.status convenience variables and the advanced Response parameter for changing the code at runtime.

**Agree?** yes / no: 

## 19. es-16 (answerable, es)

**Question:** ¿Se pueden devolver páginas HTML armadas con plantillas Jinja?

**Reference answer:** Sí, con Jinja2Templates: creas un objeto templates, recibes la Request en la ruta y devuelves un TemplateResponse con el nombre de la plantilla, la request y un diccionario de contexto.

**Spoken answer:** Déjame revisar la documentación. Sí, se puede. Instala jinja2, crea un objeto Jinja2Templates y, en tu path operation, declara un parámetro Request y devuelve un TemplateResponse con el nombre de la plantilla, el request y un diccionario de contexto con los valores que quieres mostrar en el HTML.

Si pones response class=HTMLResponse en el decorador, la documentación interactiva sabrá que la respuesta es HTML. También puedes usar url for() dentro de la plantilla para enlazar archivos estáticos, como un CSS. Todo está en la página de Plantillas, en la sección avanzada.

**Judge:** PASS. The answer matches the reference (Jinja2Templates, a Request parameter, and a TemplateResponse with the template name, request and context), and its extra details on installing jinja2, response_class=HTMLResponse and url_for with static files are all supported by the retrieved template sections.

**Agree?** yes / no: 

## 20. es-17 (answerable, es)

**Question:** ¿Cómo le pongo una cookie a la respuesta?

**Reference answer:** Declara un parámetro de tipo Response en la función de la ruta y define la cookie en ese objeto temporal. FastAPI la toma y la incluye en la respuesta final. También puedes devolver un Response directamente.

**Spoken answer:** Déjame revisar la documentación. Para poner una cookie en la respuesta, declaras en tu función un parámetro de tipo Response, y luego estableces la cookie en ese objeto. FastAPI toma esa cookie y la agrega a la respuesta final, aunque devuelvas un diccionario u otro dato. También puedes crear tu propia Response, ponerle la cookie y devolverla directamente. Lo encuentras en la página de Cookies de Response de la documentación avanzada.

**Judge:** PASS. The answer covers both ways of setting a cookie, declaring a Response parameter and returning a Response directly, and every claim is supported by the retrieved Cookies de Response sections.

**Agree?** yes / no: 

## 21. es-25 (answerable, es)

**Question:** ¿Qué son las variables de entorno y para qué las usa FastAPI?

**Reference answer:** Son valores que viven fuera de tu código, en el sistema operativo, y que tu aplicación puede leer. Se usan para configuración como URLs de bases de datos, credenciales de correo y claves secretas.

**Spoken answer:** Déjame revisar la documentación. Una variable de entorno, o env var, es un valor que vive fuera de tu código de Python, en el sistema operativo, y que tu aplicación y otros programas pueden leer. FastAPI las usa comúnmente para configuraciones como la URL de la base de datos, credenciales de correo y claves secretas, que suelen cambiar o ser sensibles. Siempre llegan como texto, así que cualquier conversión o validación se hace en código, y para eso puedes usar Pydantic Settings. Lo encuentras en las páginas de Variables de Entorno y de Configuraciones y Variables de Entorno.

**Judge:** PASS. The answer correctly defines environment variables and their configuration uses, and its extra details (values arrive as strings, validation is done in code, Pydantic Settings, they change or are sensitive) are all supported by the retrieved sections.

**Agree?** yes / no: 

## 22. st-en-02 (smalltalk, en)

**Question:** Thanks, that was really helpful.

**Reference answer:** (none)

**Spoken answer:** You're welcome! If you have more questions about FastAPI, just ask.

**Judge:** PASS. The reply is a short, friendly acknowledgment of thanks that makes no factual claims.

**Agree?** yes / no: 

## 23. st-es-02 (smalltalk, es)

**Question:** Muchas gracias, eso era todo.

**Reference answer:** (none)

**Spoken answer:** ¡De nada! Que tengas un excelente día.

**Judge:** PASS. The reply is a short, friendly Spanish farewell that fits the user's thanks and makes no claims about FastAPI.

**Agree?** yes / no: 

## 24. st-es-02 (smalltalk, es)

**Question:** Muchas gracias, eso era todo.

**Reference answer:** (none)

**Spoken answer:** ¡De nada! Que tengas un excelente día.

**Judge:** PASS. The reply is a short, friendly Spanish farewell that fits the user's thanks and makes no claims.

**Agree?** yes / no: 

## 25. st-es-03 (smalltalk, es)

**Question:** ¿Me escuchas bien?

**Reference answer:** (none)

**Spoken answer:** Sí, te escucho perfectamente. ¿Qué te gustaría saber sobre FastAPI?

**Judge:** PASS. The reply is a short, friendly confirmation in Spanish that offers help with FastAPI and makes no made-up claims.

**Agree?** yes / no: 

## 26. st-es-04 (smalltalk, es)

**Question:** ¿Qué puedes hacer? ¿En qué me puedes ayudar?

**Reference answer:** (none)

**Spoken answer:** Puedo ayudarte con dudas sobre FastAPI, el framework de Python para crear APIs. Busco en la documentación oficial, en inglés y en español, y te explico lo que encuentro: cómo definir rutas, validar datos, manejar errores, usar dependencias o desplegar la aplicación. Si la documentación no cubre tu pregunta, te lo diré claramente sin inventar respuestas. ¿Qué quieres saber?

**Judge:** PASS. The reply is a brief, friendly description of the assistant's FastAPI help scope that invites a question and makes no fabricated claims about FastAPI.

**Agree?** yes / no: 

## 27. un-en-05 (unanswerable, en)

**Question:** How do I hook up Sentry so I get alerts when my API throws errors?

**Reference answer:** (none)

**Spoken answer:** Let me check the docs. The FastAPI docs don't cover Sentry setup specifically. What they do cover is OpenTelemetry: FastAPI records unhandled exceptions as OpenTelemetry logs, linked to the request's trace, so you can forward those to your monitoring provider. You can find that in the OpenTelemetry page of the advanced guide. For Sentry's own setup steps, check Sentry's documentation.

**Judge:** PASS. The assistant clearly said the docs don't cover Sentry setup, and its only specifics (OpenTelemetry logging of unhandled exceptions linked to traces) are supported by the retrieved section, with no invented Sentry details.

**Agree?** yes / no: 

## 28. un-es-01 (unanswerable, es)

**Question:** ¿Cómo despliego mi API en Azure App Service desde el portal?

**Reference answer:** (none)

**Spoken answer:** Déjame revisar la documentación. Para resumir: la documentación de FastAPI no cubre el despliegue en Azure App Service desde el portal. Sí dice que puedes desplegar tu app en cualquier proveedor de nube siguiendo la guía de ese proveedor. Si quieres una opción dentro de la documentación, la página de FastAPI Cloud explica cómo desplegar con un solo comando, fastapi deploy.

**Judge:** PASS. The assistant clearly says the docs don't cover deploying to Azure App Service from the portal, and its extra remarks (deploy on any provider by following that provider's guides, FastAPI Cloud via fastapi deploy) are supported by the retrieved sections.

**Agree?** yes / no: 

## 29. un-es-04 (unanswerable, es)

**Question:** Quiero ver las métricas de mi API en Grafana con Prometheus, ¿cómo lo configuro?

**Reference answer:** (none)

**Spoken answer:** Déjame revisar la documentación. Las docs de FastAPI no hablan de Prometheus ni de Grafana, pero sí explican cómo sacar métricas con OpenTelemetry, que ya viene integrado.

FastAPI registra por defecto métricas de las requests HTTP, como el número de requests, la duración de las responses y las requests activas. Para exportarlas, instala fastapi[standard] y define tres variables de entorno: FASTAPI OTEL AUTO CONFIGURE en true, OTEL SERVICE NAME con el nombre de tu servicio y OTEL EXPORTER OTLP ENDPOINT con la URL de un servicio que acepte OTLP. Si ese servicio requiere autenticación, usas OTEL EXPORTER OTLP HEADERS.

Cómo conectar eso con Prometheus y Grafana en concreto no está en la documentación. Puedes revisar la página de OpenTelemetry en la sección de temas avanzados.

**Judge:** PASS. The assistant clearly says the docs don't cover Prometheus or Grafana, and the OpenTelemetry details it offers instead (default metrics, fastapi[standard], the three env vars, the OTLP headers) are all supported by the retrieved sections.

**Agree?** yes / no: 

## 30. un-es-05 (unanswerable, es)

**Question:** ¿Cómo hago una prueba de carga con Locust para saber cuántas peticiones aguanta mi API?

**Reference answer:** (none)

**Spoken answer:** Déjame revisar la documentación. Ya te lo dije, pero te lo repito: la documentación de FastAPI no cubre las pruebas de carga con Locust, así que no puedo decirte cómo hacerlas sin inventar. Si te sirve, puedo buscar información sobre las pruebas normales con TestClient o sobre cómo desplegar con varios workers.

**Judge:** PASS. The assistant clearly states that the FastAPI docs don't cover load testing with Locust and gives no unsupported specifics, only offering to look up related topics; the slightly curt 'ya te lo dije' doesn't affect correctness.

**Agree?** yes / no: 
