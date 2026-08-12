import { useEffect, useRef, useState } from "react";
import "./App.css";

function App() {
  const [screen, setScreen] = useState("welcome");
  const [mode, setMode] = useState("write");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [showChat, setShowChat] = useState(true);
  const [voiceStatus, setVoiceStatus] = useState("EN ESPERA");
  const [clock, setClock] = useState(new Date());
  const [language, setLanguage] = useState("es-ES");
  const [memoryItems, setMemoryItems] = useState([]);
  const [personalityMode, setPersonalityMode] = useState("normal");
  const [conversationMemory, setConversationMemory] = useState([]);
  const [semanticContext, setSemanticContext] = useState(null);

  const recognitionRef = useRef(null);
  const restartTimerRef = useRef(null);
  const loadingRef = useRef(false);
  const speakingRef = useRef(false);
  const listeningRef = useRef(false);
  const modeRef = useRef(mode);

  const [writeChat, setWriteChat] = useState([
    { role: "jarvis", text: "Sistema listo, Gabo." },
  ]);

  const [voiceChat, setVoiceChat] = useState([
    { role: "jarvis", text: "Modo voz listo." },
  ]);

  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [wakeEnabled, setWakeEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
const cameraLoopRef = useRef(null);
  const cameraStreamRef = useRef(null);

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000);
    cargarMemoria();
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  useEffect(() => {
    speakingRef.current = speaking;
  }, [speaking]);

  useEffect(() => {
    listeningRef.current = listening;
  }, [listening]);

  useEffect(() => {
    modeRef.current = mode;

    if (mode === "voice" && wakeEnabled) {
      iniciarWakeWord();
    } else {
      detenerReconocimiento();
    }
  }, [mode, wakeEnabled]);

  const horaActual = clock.toLocaleTimeString("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const fechaActual = clock.toLocaleDateString("es-ES", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  function currentChatSetter() {
    return mode === "voice" ? setVoiceChat : setWriteChat;
  }

  function normalizar(texto) {
    return texto.toLowerCase().replace(/[^\wáéíóúñ ]/g, " ").trim();
  }

  function evaluarMensaje(texto) {
    const t = normalizar(texto);

    const preguntasSignificado = [
      "que significa",
      "qué significa",
      "significado de",
      "que quiere decir",
      "qué quiere decir",
      "explica",
    ];

    const peligroReal = [
      "quiero matar",
      "voy a matar",
      "como matar",
      "cómo matar",
      "hacer una bomba",
      "fabricar una bomba",
      "hackear banco",
    ];

    for (const patron of preguntasSignificado) {
      if (t.includes(patron)) return { permitido: true };
    }

    for (const patron of peligroReal) {
      if (t.includes(patron)) {
        return {
          permitido: false,
          respuesta: "No puedo ayudar con eso.",
        };
      }
    }

    return { permitido: true };
  }

  async function hablar(texto) {
    if (!texto || !texto.trim()) return;

    try {
      setSpeaking(true);
      setVoiceStatus("RESPONDIENDO");
      window.__jarvis_hablando = true;

      await fetch("http://127.0.0.1:5090/speak", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: texto,
        }),
      });
    } catch (error) {
      console.error("Error hablando:", error);
    } finally {
      window.__jarvis_hablando = false;
      setSpeaking(false);
      setVoiceStatus("EN ESPERA");

      if (modeRef.current === "voice" && wakeEnabled) {
        setTimeout(() => {
          iniciarWakeWord();
        }, 1400);
      }
    }
  }

  function detenerReconocimiento() {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.stop();
      } catch {}
    }

    recognitionRef.current = null;
    setListening(false);
  }

  function detenerVoz() {
    detenerReconocimiento();
    setWakeEnabled(false);
    setSpeaking(false);
    setListening(false);
    setLoading(false);
    setVoiceStatus("EN ESPERA");
  }

  function activarVoz() {
    setWakeEnabled(true);
    setVoiceStatus("EN ESPERA");
    setTimeout(() => iniciarWakeWord(), 500);
  }

async function activarCamara() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false,
    });

    if (videoRef.current) {
      videoRef.current.srcObject = stream;

      await new Promise((resolve) => {
        videoRef.current.onloadedmetadata = resolve;
      });

      await videoRef.current.play();
    }

    const dibujar = () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;

      if (video && canvas) {
        const ctx = canvas.getContext("2d");
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      }

      cameraLoopRef.current = requestAnimationFrame(dibujar);
    };

    dibujar();

    setCameraEnabled(true);
  } catch (error) {
    console.error("Error cámara:", error);
    alert("No pude activar la cámara.");
  }
}

function detenerCamara() {
  if (cameraStreamRef.current) {
    cameraStreamRef.current.getTracks().forEach((track) => track.stop());
    cameraStreamRef.current = null;
  }

  if (videoRef.current) {
    videoRef.current.srcObject = null;
  }

  setCameraEnabled(false);
}

  function necesitaInternet(texto) {
    const t = texto.toLowerCase();

    return (
      t.includes("busca en internet") ||
      t.includes("busca en google") ||
      t.includes("investiga") ||
      t.includes("noticias") ||
      t.includes("actual") ||
      t.includes("precio") ||
      t.includes("presidente") ||
      t.includes("quién es") ||
      t.includes("quien es") ||
      t.includes("qué significa") ||
      t.includes("que significa") ||
      t.includes("significado de") ||
      t.includes("qué quiere decir") ||
      t.includes("que quiere decir") ||
      t.includes("modismo") ||
      t.includes("slang") ||
      t.includes("jerga") ||
      t.includes("caracteristicas") ||
      t.includes("características") ||
      t.includes("sobre") ||
      t.includes("creador de contenido") ||
      t.includes("streamer") ||
      t.includes("tiktok") ||
      t.includes("facebook") ||
      t.includes("instagram")
    );
  }

  function detectarMemoria(texto) {
    const t = texto.toLowerCase();

    return (
      t.startsWith("recuerda") ||
      t.startsWith("jarvis recuerda") ||
      t.includes("guarda esto") ||
      t.includes("recuerda que")
    );
  }

  function detectarPreguntaMemoria(texto) {
    const t = texto.toLowerCase();

    return (
      t.includes("qué recuerdas") ||
      t.includes("que recuerdas") ||
      t.includes("mi color favorito") ||
      t.includes("qué sabes de mí") ||
      t.includes("que sabes de mi")
    );
  }

  function detectarModoPersonalidad(texto) {
    const t = texto.toLowerCase();

    if (t.includes("modo serio") || t.includes("jarvis modo serio")) {
      setPersonalityMode("serio");
      return "Modo serio activado.";
    }

    if (t.includes("modo bro") || t.includes("jarvis modo bro")) {
      setPersonalityMode("bro");
      return "Modo bro activado.";
    }

    if (t.includes("modo normal") || t.includes("jarvis modo normal")) {
      setPersonalityMode("normal");
      return "Modo normal activado.";
    }

    return null;
  }

  async function cargarMemoria() {
    try {
      const response = await fetch("http://127.0.0.1:5070/memory");
      const data = await response.json();
      setMemoryItems(data.memoria || []);
    } catch {}
  }

  async function guardarMemoria(texto) {
    try {
      const response = await fetch("http://127.0.0.1:5070/remember", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
      });

      const data = await response.json();
      cargarMemoria();

      return data.respuesta || "Memoria guardada.";
    } catch {
      return "No pude guardar la memoria.";
    }
  }

  async function buscarMemoria(pregunta) {
    try {
      const response = await fetch("http://127.0.0.1:5070/search_memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pregunta }),
      });

      const data = await response.json();
      const resultados = data.resultados || [];

      if (resultados.length === 0) {
        return "No recuerdo nada relacionado con eso.";
      }

      return resultados.map((r) => r.texto).join(". ");
    } catch {
      return "No pude acceder a la memoria.";
    }
  }


  async function resolverContexto(textoOriginal) {
    try {
      const response = await fetch("http://127.0.0.1:5070/resolve_context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pregunta: textoOriginal,
          historial: conversationMemory.slice(-8),
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || "No pude resolver el contexto.");
      }

      setSemanticContext(data);
      return data;
    } catch (error) {
      console.error("Context resolver:", error);

      const limpio = textoOriginal
        .replace(/^\s*(oye\s+|hey\s+)?jarvis\b[\s,;:.-]*/i, "")
        .trim();

      return {
        ok: false,
        pregunta_original: textoOriginal,
        pregunta_limpia: limpio,
        pregunta_resuelta: limpio,
        vocativo: "",
        tono: "neutral",
        intencion: "",
        relacion: "",
        entidad_principal: "",
        tipo_entidad: "",
        entidades: [],
        usa_contexto: false,
      };
    }
  }

  async function comprometerTurnoContexto(usuario, jarvis, resolved) {
    try {
      await fetch("http://127.0.0.1:5070/commit_turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          usuario,
          jarvis,
          resolved: resolved || {},
        }),
      });
    } catch (error) {
      console.error("Commit contexto:", error);
    }
  }

  function respuestaLocal(text) {
    const t = text.toLowerCase();

    if (t.includes("qué día es hoy") || t.includes("que dia es hoy")) {
      const fecha = new Date().toLocaleDateString("es-ES", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      });

      return `Hoy es ${fecha}.`;
    }

    if (t.includes("qué hora es") || t.includes("que hora es")) {
      const hora = new Date().toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      });

      return `Son las ${hora}.`;
    }

    return null;
  }


  function pareceAccionDeterminista(texto) {
    const t = (texto || "").trim().toLowerCase();

    return /^(abre|abrir|abreme|ábreme|abri|abrí|inicia|iniciar|ejecuta|ejecutar|lanza|lanzar|cierra|cerrar|reproduce|pon|ponme|busca|buscar|buscame|búscame)\b/i.test(t);
  }

  async function ejecutarAccionApp(text) {
    try {
      const response = await fetch("http://127.0.0.1:5050/accion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: text }),
      });

      return await response.json();
    } catch {
      return { handled: false };
    }
  }

  function agregarMensajeVacio(setCurrentChat, text) {
    setCurrentChat((prev) => [
      ...prev,
      { role: "user", text },
      { role: "jarvis", text: "" },
    ]);
  }

  function actualizarUltimoMensaje(setCurrentChat, piece) {
    setCurrentChat((prev) => {
      const copy = [...prev];

      copy[copy.length - 1] = {
        ...copy[copy.length - 1],
        text: copy[copy.length - 1].text + piece,
      };

      return copy;
    });
  }

 function actualizarMemoriaConversacion(userText, jarvisText = "") {
  setConversationMemory((prev) => {
    const nueva = [
      ...prev,
      {
        user: userText,
        jarvis: jarvisText,
        timestamp: Date.now(),
      },
    ];

    window.__jarvis_last_context =
      nueva[nueva.length - 1];

    return nueva.slice(-8);
  });
}

  async function streamInternet(text, setCurrentChat, semantic = null) {
    const response = await fetch("http://127.0.0.1:5000/internet_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pregunta: text,
        semantic: semantic || {},
      }),
    });

    if (!response.body) {
      throw new Error("No hay stream disponible.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let respuestaCompleta = "";
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) continue;

        const data = JSON.parse(line);
        const piece = data.piece || "";

        if (!piece) continue;

        if (
          piece.includes("Investigando en internet") ||
          piece.includes("Analizando fuentes")
        ) {
          setVoiceStatus("PENSANDO");
          continue;
        }

        respuestaCompleta += piece;
        actualizarUltimoMensaje(setCurrentChat, piece);
      }
    }

    return respuestaCompleta;
  }

  async function streamOllamaLocal(text, setCurrentChat, semantic = null) {
    const contextoReciente = conversationMemory
      .map(
        (c) => `
Usuario: ${c.user}
Jarvis: ${c.jarvis}
`
      )
      .join("\n");

    const estilo =
      personalityMode === "serio"
        ? `
- Hablas extremadamente elegante y profesional.
- Respuestas precisas y directas.
- Casi nunca haces bromas.
`
        : personalityMode === "bro"
        ? `
- Hablas relajado y cercano.
- Puedes bromear más seguido.
- Puedes usar expresiones coloquiales suaves.
`
        : `
- Hablas elegante, natural y equilibrado.
- Humor inteligente ocasional.
`;

    const prompt = `
Eres JARVIS, el asistente personal de Gabo.

Personalidad:
${estilo}

- Eres elegante, leal, inteligente y directo.
- Tienes humor fino, rápido y ocasional, sin pasarte.
- Hablas como asistente personal avanzado, no como chatbot genérico.
- Puedes decir “señor” de vez en cuando, pero no en cada frase.
- Si Gabo dice algo gracioso o informal, puedes seguirle el tono.
- Si algo falla, lo dices claro, sin dramatizar.
- Si una respuesta puede ser corta, sé corto.
- Si Gabo pide algo largo, cumple sin resumir de más.
- Tienes estilo tecnológico, calmado y seguro.
- No uses emojis dentro de Jarvis salvo que Gabo los pida.

Reglas:
- Responde en español.
- Sé útil, natural y concreto.
- Puedes explicar modismos, insultos coloquiales, jerga y frases populares.
- No bloquees palabras solo por ser groseras.
- Solo rechaza daño real o peligro real.
- Si Gabo pide una acción, responde como si fueras su sistema.
- Nunca digas que eres un chatbot.
- Tu nombre es Jarvis.

Contexto reciente:
${contextoReciente}

Contexto semántico resuelto:
- Pregunta original: ${semantic?.pregunta_original || text}
- Pregunta resuelta: ${semantic?.pregunta_resuelta || text}
- Vocativo/apodo dirigido a Jarvis: ${semantic?.vocativo || "(ninguno)"}
- Tono detectado: ${semantic?.tono || "neutral"}
- Intención: ${semantic?.intencion || ""}
- Relación solicitada: ${semantic?.relacion || ""}
- Entidad principal: ${semantic?.entidad_principal || ""}

Reglas de identidad y comprensión:
- Si el usuario usa un vocativo/apodo contigo, es una forma de dirigirse a Jarvis, no parte del tema.
- Puedes reaccionar brevemente al apodo con sarcasmo fino o humor seco si encaja.
- El sarcasmo es ocasional y nunca debe reducir la claridad.
- Si el usuario está frustrado, evita bromear.
- Responde exactamente a la relación solicitada.
- Si pregunta por director, no respondas protagonista.
- Si pregunta por autor, no resumas la obra.
- Si el mensaje depende del turno anterior, usa la pregunta resuelta y no pidas aclaración innecesaria.

Ejemplos de tono:
- “Hecho.”
- “Listo, señor.”
- “Eso fue más fácil que convencer a Windows de actualizarse sin molestar.”
- “Entendido. Me encargo.”
- “No encontré eso, pero no voy a culpar al universo todavía.”

Última instrucción del usuario:
${text}

IMPORTANTE:
Si el usuario usa frases como:
- explícalo mejor
- más corto
- repítelo
- más serio
- con humor

NO preguntes qué significan.
Asume que hacen referencia al último tema de la conversación y responde directamente.
`;

    const response = await fetch("http://localhost:11434/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "jarvis2",
        prompt,
        stream: true,
      }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let respuestaCompleta = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split("\n").filter(Boolean);

      for (const line of lines) {
        const data = JSON.parse(line);
        const piece = data.response || "";

        if (piece) {
          respuestaCompleta += piece;
          actualizarUltimoMensaje(setCurrentChat, piece);
        }
      }
    }

    return respuestaCompleta;
  }

  function esInterrupcion(texto) {
  const t = texto.toLowerCase().trim();

  const interrupcionesExactas = [
    "para",
    "jarvis para",
    "detente",
    "jarvis detente",
    "cancela",
    "jarvis cancela",
    "stop",
    "jarvis stop",
    "espera",
    "jarvis espera",
  ];

  return interrupcionesExactas.includes(t);
}

function expandirOrdenSeguimiento(texto) {
  const t = texto.toLowerCase().trim();

  const ultimo =
    window.__jarvis_last_context ||
    conversationMemory[conversationMemory.length - 1];

  const tema =
    window.__jarvis_last_topic ||
    ultimo?.user ||
    ultimo?.jarvis ||
    "";

  if (!tema) return texto;

  if (
    t.includes("explícalo mejor") ||
    t.includes("explicalo mejor") ||
    t.includes("explícame mejor") ||
    t.includes("explicame mejor") ||
    t.includes("explica lo mejor")
  ) {
    return `
Responde directamente.

Da una explicación mucho más detallada.
Usa ejemplos simples.
No hagas preguntas.
No pidas aclaraciones.
No digas "listo para explicarlo"; explica de una vez.

Tema:
${tema}
`;
  }

  if (
    t.includes("más corto") ||
    t.includes("mas corto")
  ) {
    return `
Responde directamente.

Haz una versión corta y resumida.

Tema:
${tema}
`;
  }

  if (
    t.includes("repítelo") ||
    t.includes("repitelo") ||
    t.includes("otra vez")
  ) {
    return `
Responde nuevamente este tema.

Tema:
${tema}
`;
  }

  if (
    t.includes("compárala") ||
    t.includes("comparala") ||
    t.includes("compáralo") ||
    t.includes("comparalo")
  ) {
    return `
Compara usando el tema anterior como referencia.

Tema anterior:
${tema}

Nueva petición:
${texto}
`;
  }

  if (
    t.includes("y para") ||
    t.includes("para videojuegos") ||
    t.includes("en videojuegos") ||
    t.includes("para ia") ||
    t.includes("para inteligencia artificial")
  ) {
    return `
Responde directamente usando el tema anterior como contexto.

Tema anterior:
${tema}

Nueva pregunta:
${texto}
`;
  }

  return texto;
}


  function limpiarAnclaJarvis(texto) {
    return (texto || "")
      .replace(/^\s*(oye\s+|hey\s+)?jarvis\b[\s,;:.-]*/i, "")
      .trim();
  }


function necesitaResolverSemantico(textoOriginal, textoLimpio) {
  const t = (textoLimpio || "").trim().toLowerCase();

  if (!t) return false;

  // Explicit pronoun/reference follow-ups.
  if (
    /^(y|pero|entonces|además|ademas)\b/i.test(t) ||
    /\b(quién|quien)\s+(lo|la|los|las)\b/i.test(t) ||
    /\b(el libro|la película|la pelicula|la serie|el juego|esa empresa|esa persona)\b/i.test(t) ||
    /^(cuándo|cuando|dónde|donde|cuánto|cuanto)\s+(sale|salió|salio|está|esta|cuesta|vale)\??$/i.test(t) ||
    /^(quién|quien)\s+es\s+(el|la)\s+(autor|autora|director|directora)\??$/i.test(t)
  ) {
    return true;
  }

  const seguimiento = [
    "explícalo mejor",
    "explicalo mejor",
    "explícame mejor",
    "explicame mejor",
    "más corto",
    "mas corto",
    "repítelo",
    "repitelo",
    "otra vez",
    "compáralo",
    "comparalo",
    "compárala",
    "comparala",
  ];

  if (seguimiento.some((frase) => t.includes(frase))) {
    return true;
  }

  // Standalone factual/action/news questions should bypass the context LLM.
  const autosuficiente =
    /^(qu[eé]|qui[eé]n|de qui[eé]n|cu[aá]ndo|d[oó]nde|cu[aá]nto|cu[aá]l|c[oó]mo|por qu[eé]|dime|di |explica|expl[ií]came|busca|investiga|abre|abrir|inicia|ejecuta|lanza|pon|reproduce|compara|haz|dame|mu[eé]strame|recuerda|guarda|quiero|necesito|puedes|podr[ií]as|h[aá]blame|hablame)\b/i;

  if (autosuficiente.test(t)) {
    return false;
  }

  // Possible arbitrary vocative after "Jarvis": use resolver only when the
  // remaining sentence does not look like a normal request.
  const teniaAnclaJarvis =
    /^\s*(oye\s+|hey\s+)?jarvis\b/i.test(textoOriginal || "");

  if (teniaAnclaJarvis && t.split(/\s+/).length >= 3) {
    return true;
  }

  return false;
}

function contextoSemanticoDirecto(textoOriginal, textoLimpio) {
  return {
    ok: true,
    pregunta_original: textoOriginal,
    pregunta_limpia: textoLimpio,
    pregunta_resuelta: textoLimpio,
    vocativo: "",
    tono: "neutral",
    intencion: "",
    relacion: "",
    entidad_principal: "",
    tipo_entidad: "",
    entidades: [],
    usa_contexto: false,
    confianza: 1,
    modo: "directo",
  };
}

async function sendMessage(textFromVoice = null, speakResponse = false) {
    let text = (textFromVoice || message).trim();

    if (!text) return;

    const textoOriginal = text;

    // Vaciar el input inmediatamente al enviar. Antes quedaba visible mientras
    // el resolver semántico / Ollama / Internet trabajaban, dando la impresión
    // de que el mensaje se había quedado colgado.
    if (!textFromVoice) {
      setMessage("");
    }

    // =====================================================
    // FAST PATH DE ACCIONES
    // =====================================================
    // Abrir/cerrar/iniciar/reproducir/buscar no necesita esperar a Ollama
    // ni al Semantic Context Resolver. Si el servidor 5050 la maneja,
    // terminamos aquí. Esto elimina varios segundos de latencia.
    const textoRapido = limpiarAnclaJarvis(textoOriginal);

    if (pareceAccionDeterminista(textoRapido)) {
      if (loadingRef.current) return;

      const setCurrentChat = currentChatSetter();

      try {
        const accionRapida = await ejecutarAccionApp(textoRapido);

        if (accionRapida?.handled) {
          const respuestaRapida =
            accionRapida.respuesta || "Hecho.";

          setCurrentChat((prev) => [
            ...prev,
            { role: "user", text: textoOriginal },
            { role: "jarvis", text: respuestaRapida },
          ]);

          actualizarMemoriaConversacion(
            textoOriginal,
            respuestaRapida
          );

          // Guardamos el turno sin bloquear la acción.
          comprometerTurnoContexto(
            textoOriginal,
            respuestaRapida,
            {
              pregunta_original: textoOriginal,
              pregunta_limpia: textoRapido,
              pregunta_resuelta: textoRapido,
              vocativo: "",
              tono: "neutral",
              intencion: "accion",
              relacion: "accion_sistema",
              entidad_principal: "",
              entidades: [],
              usa_contexto: false,
            }
          );

          setMessage("");
          setLoading(false);
          setVoiceStatus("EN ESPERA");

          if (speakResponse) {
            await hablar(respuestaRapida);
          }

          return;
        }
      } catch (error) {
        console.error("Fast path acción:", error);
        // Si el 5050 falla o no maneja la orden, seguimos con el flujo normal.
      }
    }

    const esSeguimiento =
      text.toLowerCase().includes("y para") ||
      text.toLowerCase().includes("para videojuegos") ||
      text.toLowerCase().includes("en videojuegos") ||
      text.toLowerCase().includes("para ia") ||
      text.toLowerCase().includes("para inteligencia artificial") ||
      text.toLowerCase().includes("compárala") ||
      text.toLowerCase().includes("comparala") ||
      text.toLowerCase().includes("compáralo") ||
      text.toLowerCase().includes("comparalo") ||
      text.toLowerCase().includes("más corto") ||
      text.toLowerCase().includes("mas corto") ||
      text.toLowerCase().includes("explícalo mejor") ||
      text.toLowerCase().includes("explicalo mejor") ||
      text.toLowerCase().includes("explícame mejor") ||
      text.toLowerCase().includes("explicame mejor") ||
      text.toLowerCase().includes("explica lo mejor") ||
      text.toLowerCase().includes("repítelo") ||
      text.toLowerCase().includes("repitelo") ||
      text.toLowerCase().includes("otra vez");

    if (!esSeguimiento && text) {
      window.__jarvis_last_topic = text;
    }

    if (esInterrupcion(textoOriginal)) {
      try {
        await fetch("http://127.0.0.1:5090/stop", {
          method: "POST",
        });
      } catch {}

      setLoading(false);
      setSpeaking(false);
      setListening(false);
      setVoiceStatus("EN ESPERA");

      if (speakResponse) {
        await hablar("Está bien, señor.");
      }

      return;
    }


if (loadingRef.current) return;

const setCurrentChat = currentChatSetter();

// Mostrar el turno INMEDIATAMENTE en el chat antes de esperar al resolver
// semántico, Internet u Ollama. Así aparecen "Tú:" y "Jarvis:" al instante.
agregarMensajeVacio(setCurrentChat, textoOriginal);

// El resolver semántico ya NO bloquea todas las preguntas.
// Solo se usa cuando hay referencias, seguimiento o un posible vocativo.
// Las preguntas autosuficientes pasan directamente al motor correspondiente.
const textoBaseSemantico =
  textoOriginal
    .replace(/^\s*(oye\s+|hey\s+)?jarvis\b[\s,;:.-]*/i, "")
    .trim();

const requiereResolver =
  necesitaResolverSemantico(textoOriginal, textoBaseSemantico);

setLoading(true);
setVoiceStatus("PENSANDO");

const semantic = requiereResolver
  ? await resolverContexto(textoOriginal)
  : contextoSemanticoDirecto(textoOriginal, textoBaseSemantico);

const textoLimpioSemantico =
  semantic?.pregunta_limpia ||
  textoBaseSemantico;

const textoResueltoSemantico =
  semantic?.pregunta_resuelta ||
  textoLimpioSemantico ||
  expandirOrdenSeguimiento(text);

// Las acciones ejecutables NO deben convertirse en frases informativas.
// "abre OBS" debe seguir siendo "abre OBS", aunque el resolver produzca
// "OBS Studio se está abriendo".
text = pareceAccionDeterminista(textoLimpioSemantico)
  ? textoLimpioSemantico
  : textoResueltoSemantico;

console.log("TEXTO ORIGINAL:", textoOriginal);
console.log("CONTEXTO SEMÁNTICO:", semantic);
console.log("TEXTO LIMPIO:", textoLimpioSemantico);
console.log("TEXTO FINAL:", text);

const textoLower = text.toLowerCase();


// ========================================
// VISIÓN JARVIS
// ========================================

if (
  textoLower.includes("qué ves") ||
  textoLower.includes("que ves") ||
  textoLower.includes("qué estás viendo") ||
  textoLower.includes("que estas viendo") ||
  textoLower.includes("analiza lo que ves") ||
  textoLower.includes("mira esto")
) {
  try {
    setMessage("");
    setLoading(true);
    setVoiceStatus("ANALIZANDO");

    const mensajeAnalisis = "Analizando lo que veo.";

    setCurrentChat((prev) => {
      const copy = [...prev];
      copy[copy.length - 1] = {
        role: "jarvis",
        text: mensajeAnalisis,
      };
      return copy;
    });

    if (speakResponse) {
      await hablar(mensajeAnalisis);
    }

    const response = await fetch(
      "http://127.0.0.1:5080/analyze"
    );

    const data = await response.json();

    if (data.ok && data.respuesta) {
      const respuestaVision = data.respuesta.trim();

      setCurrentChat((prev) => {
        const copy = [...prev];

        copy[copy.length - 1] = {
          role: "jarvis",
          text: respuestaVision,
        };

        return copy;
      });

      actualizarMemoriaConversacion(
        textoOriginal,
        respuestaVision
      );

      setLoading(false);

      if (speakResponse) {
        await hablar(respuestaVision);
      }

      setVoiceStatus("EN ESPERA");

      if (modeRef.current === "voice" && wakeEnabled) {
        setTimeout(() => iniciarWakeWord(), 800);
      }

      return;
    }

    const errorVision =
      "No pude analizar lo que estoy viendo.";

    setCurrentChat((prev) => {
      const copy = [...prev];

      copy[copy.length - 1] = {
        role: "jarvis",
        text: errorVision,
      };

      return copy;
    });

    setLoading(false);

    if (speakResponse) {
      await hablar(errorVision);
    }

    setVoiceStatus("EN ESPERA");
    return;

  } catch (error) {
    console.error("ERROR VISION:", error);

    const errorConexion =
      "No pude conectarme con el sistema de visión.";

    setCurrentChat((prev) => {
      const copy = [...prev];
      copy[copy.length - 1] = {
        role: "jarvis",
        text: errorConexion,
      };
      return copy;
    });

    setMessage("");
    setLoading(false);

    if (speakResponse) {
      await hablar(errorConexion);
    }

    setVoiceStatus("EN ESPERA");
    return;
  }
}


// ========================================
// SEGURIDAD / JARVIS NORMAL
// ========================================

const seguridad = evaluarMensaje(text);

if (!seguridad.permitido) {
  setCurrentChat((prev) => {
    const copy = [...prev];
    copy[copy.length - 1] = {
      role: "jarvis",
      text: seguridad.respuesta,
    };
    return copy;
  });

  actualizarMemoriaConversacion(
    text,
    seguridad.respuesta
  );

  if (speakResponse) {
    await hablar(seguridad.respuesta);
  }

  setMessage("");
  return;
}


    if (detectarMemoria(text)) {
      const respuesta = await guardarMemoria(text);

      setCurrentChat((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "jarvis",
          text: respuesta,
        };
        return copy;
      });

      actualizarMemoriaConversacion(text, respuesta);

      if (speakResponse) await hablar(respuesta);

      setMessage("");
      return;
    }

    if (detectarPreguntaMemoria(text)) {
      const respuesta = await buscarMemoria(text);

      setCurrentChat((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "jarvis",
          text: respuesta,
        };
        return copy;
      });

      actualizarMemoriaConversacion(text, respuesta);

      if (speakResponse) await hablar(respuesta);

      setMessage("");
      return;
    }

    const modoRespuesta = detectarModoPersonalidad(text);

    if (modoRespuesta) {
      setCurrentChat((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "jarvis",
          text: modoRespuesta,
        };
        return copy;
      });

      actualizarMemoriaConversacion(text, modoRespuesta);

      if (speakResponse) {
        await hablar(modoRespuesta);
      }

      setMessage("");
      return;
    }

    // ========================================
// ACCIONES DE WINDOWS
// No ejecutar si es una consulta de internet
// ========================================

let accion = {
  handled: false
};

const textoAccion =
  pareceAccionDeterminista(textoLimpioSemantico)
    ? textoLimpioSemantico
    : text;

// Las acciones deterministas se prueban SIEMPRE primero.
// Solo si el servidor 5050 dice handled:false seguimos con Internet/Ollama.
if (pareceAccionDeterminista(textoAccion) || !necesitaInternet(text)) {
  accion = await ejecutarAccionApp(textoAccion);
}

if (accion.handled) {
  setCurrentChat((prev) => {
    const copy = [...prev];
    copy[copy.length - 1] = {
      role: "jarvis",
      text: accion.respuesta,
    };
    return copy;
  });

  actualizarMemoriaConversacion(
    text,
    accion.respuesta
  );

  if (speakResponse) {
    await hablar(accion.respuesta);
  }

  setMessage("");
  setLoading(false);
  setVoiceStatus("EN ESPERA");
  return;
}

    const local = respuestaLocal(text);

    if (local) {
      setCurrentChat((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "jarvis",
          text: local,
        };
        return copy;
      });

      actualizarMemoriaConversacion(text, local);

      if (speakResponse) await hablar(local);

      setMessage("");
      setLoading(false);
      setVoiceStatus("EN ESPERA");
      return;
    }

    setMessage("");

    let respuestaCompleta = "";

    try {
      if (necesitaInternet(text)) {
        respuestaCompleta = await streamInternet(text, setCurrentChat, semantic);
      } else {
        respuestaCompleta = await streamOllamaLocal(text, setCurrentChat, semantic);
      }

      setLoading(false);

      actualizarMemoriaConversacion(textoOriginal, respuestaCompleta);
      comprometerTurnoContexto(
        textoOriginal,
        respuestaCompleta,
        semantic
      );

      if (speakResponse && respuestaCompleta.trim()) {
        await hablar(respuestaCompleta);
      }
    } catch {
      respuestaCompleta = "No pude conectar con el sistema.";

      setCurrentChat((prev) => {
        const copy = [...prev];

        copy[copy.length - 1] = {
          role: "jarvis",
          text: respuestaCompleta,
        };

        return copy;
      });

      setLoading(false);

      actualizarMemoriaConversacion(textoOriginal, respuestaCompleta);
      comprometerTurnoContexto(
        textoOriginal,
        respuestaCompleta,
        semantic
      );

      if (speakResponse) await hablar(respuestaCompleta);
    }

    // Safety latch: no completed turn may leave Jarvis permanently busy.
    setLoading(false);
    loadingRef.current = false;
    setVoiceStatus("EN ESPERA");

    if (modeRef.current === "voice" && wakeEnabled) {
      setTimeout(() => iniciarWakeWord(), 800);
    }
  }

  function limpiarOrdenVoz(texto) {
    let orden = texto.trim();

    orden = orden.replace(/^jarvis\s*/i, "");
    orden = orden.replace(/^oye\s+/i, "");
    orden = orden.replace(/^hey\s+/i, "");
    orden = orden.replace(/^por favor\s+/i, "");

    return orden.trim();
  }

  function contieneWakeWord(texto) {
    const t = normalizar(texto);

    return (
      t.includes("jarvis") ||
      t.includes("yarvis") ||
      t.includes("jervis") ||
      t.includes("charvis")
    );
  }

  function extraerOrdenDesdeWakeWord(texto) {
    const partes = texto.split(/jarvis|yarvis|jervis|charvis/i);

    if (partes.length > 1) {
      return partes.slice(1).join(" ").trim();
    }

    return limpiarOrdenVoz(texto);
  }

  function textoPareceRuido(texto) {
    const t = normalizar(texto);

    if (!t) return true;
    if (t.length < 4) return true;

    const ruidos = [
      "eh",
      "ah",
      "mmm",
      "um",
      "uh",
      "hmm",
      "ruido",
      "silencio",
      "gracias",
      "ok",
      "okay",
      "bueno",
    ];

    if (ruidos.includes(t)) return true;

    const palabras = t.split(" ").filter(Boolean);

    if (palabras.length === 1 && t !== "jarvis") {
      return true;
    }

    return false;
  }

  async function prepararMicrofono() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: false,
          channelCount: 1,
        },
      });

      stream.getTracks().forEach((track) => track.stop());

      return true;
    } catch {
      return false;
    }
  }

  async function iniciarWakeWord() {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Tu navegador no soporta reconocimiento de voz.");
      return;
    }

    if (modeRef.current !== "voice") return;
    if (!wakeEnabled) return;
    if (loadingRef.current || listeningRef.current) return;

    await prepararMicrofono();

    detenerReconocimiento();

    const recognition = new SpeechRecognition();

    recognitionRef.current = recognition;

    recognition.lang = language;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    let enviado = false;

    setListening(true);
    setVoiceStatus("EN ESPERA");

    try {
      recognition.start();
    } catch {
      setListening(false);
      return;
    }

    recognition.onresult = async (event) => {
      const resultado = event.results[0][0];
      const textoDetectado = resultado.transcript.trim();
      if (
        window.__jarvis_hablando &&
        esInterrupcion(textoDetectado)
      ) {
        try {
          await fetch("http://127.0.0.1:5090/stop", {
            method: "POST",
          });
        } catch {}

        setSpeaking(false);
        setVoiceStatus("EN ESPERA");
        recognition.stop();

        await hablar("Está bien, señor.");

        return;
      }
      const confianza = resultado.confidence || 0;

      setVoiceStatus("ANALIZANDO");

      if (confianza > 0 && confianza < 0.55) {
        recognition.stop();
        return;
      }

      await new Promise((resolve) => setTimeout(resolve, 1600));

      if (textoPareceRuido(textoDetectado)) {
        setVoiceStatus("EN ESPERA");
        recognition.stop();
        return;
      }

      if (!contieneWakeWord(textoDetectado)) {
        setVoiceStatus("EN ESPERA");
        recognition.stop();
        return;
      }

      const orden = extraerOrdenDesdeWakeWord(textoDetectado);
      const textoLimpio = orden.trim().toLowerCase();

      if (textoLimpio === "" || textoLimpio === "jarvis") {
  recognition.stop();
  setListening(false);
  setVoiceStatus("EN ESPERA");

  setTimeout(() => {
    iniciarWakeWord();
  }, 700);

  return;
}

      enviado = true;

      // Cortar el micrófono antes de ejecutar la orden evita que Jarvis
      // se escuche a sí mismo cuando empiece a hablar.
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;

      try {
        recognition.stop();
      } catch {}

      recognitionRef.current = null;
      setListening(false);
      setVoiceStatus("PENSANDO");

      await sendMessage(orden, true);
    };

    recognition.onerror = () => {
      setListening(false);
      setVoiceStatus("EN ESPERA");
    };

    recognition.onend = () => {
      setListening(false);

      if (
        modeRef.current === "voice" &&
        wakeEnabled &&
        !enviado &&
        !loadingRef.current
      ) {
        restartTimerRef.current = setTimeout(() => {
          iniciarWakeWord();
        }, 700);
      }
    };
  }

  function entrarSistema() {
    setScreen("main");

    setTimeout(() => {
      hablar("Bienvenido señor, sistema iniciado.");
    }, 700);
  }

  if (screen === "welcome") {
    return (
      <div className="welcome-screen">
        <div className="welcome-glow one" />
        <div className="welcome-glow two" />

        <div className="welcome-card">
          <div className="welcome-mini-orb">
            <div />
          </div>

          <h1>
            J.A.R.V.I.S <span>2.0</span>
          </h1>

          <p>Bienvenido, Gabo</p>

          <button onClick={entrarSistema}>INICIAR SISTEMA</button>
        </div>
      </div>
    );
  }

  return (
    <div className="jarvis-shell">
      <aside
        className={`sidebar ${sidebarOpen ? "expanded" : ""}`}
        onMouseEnter={() => setSidebarOpen(true)}
        onMouseLeave={() => setSidebarOpen(false)}
      >
        <div className="avatar-ring">
          <div className="avatar-core">J</div>
        </div>

        <nav>
          <button
            className={mode === "home" ? "nav-active" : ""}
            onClick={() => setMode("home")}
          >
            <span className="nav-icon">⌂</span>
            <span>Inicio</span>
          </button>

          <button
            className={mode === "voice" ? "nav-active" : ""}
            onClick={() => setMode("voice")}
          >
            <span className="nav-icon">≋</span>
            <span>Voz</span>
          </button>

          <button
            className={mode === "write" ? "nav-active" : ""}
            onClick={() => setMode("write")}
          >
            <span className="nav-icon">✎</span>
            <span>Escribir</span>
          </button>

          <button
            className={mode === "memory" ? "nav-active" : ""}
            onClick={() => setMode("memory")}
          >
            <span className="nav-icon">◇</span>
            <span>Memoria</span>
          </button>

          <button
            className={mode === "settings" ? "nav-active" : ""}
            onClick={() => setMode("settings")}
          >
            <span className="nav-icon">⚙</span>
            <span>Ajustes</span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="connection-card">
            <span className="dot" />
            <span className="connection-text">Conectado</span>
          </div>

          <div className="sidebar-clock">{horaActual}</div>
          <div className="sidebar-date">{fechaActual}</div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <h1>
            J.A.R.V.I.S <span>2.0</span>
          </h1>
        </header>

        <section className="core-stage">
          <div className="grid-bg" />

          {mode !== "home" && (
            <div
              className={`orb-rings ${
                loading || listening || speaking ? "active-orb" : ""
              }`}
            >
              <div className="ring r1" />
              <div className="ring r2" />
              <div className="ring r3" />

              <div className="network-orb">
                <div className="core-light" />
              </div>
            </div>
          )}

          {mode === "write" && showChat && (
            <div className="chat-feed">
              {writeChat.map((item, index) => (
                <div key={index} className={`chat-msg ${item.role}`}>
                  <strong>{item.role === "user" ? "Tú" : "Jarvis"}:</strong>{" "}
                  {item.text}
                </div>
              ))}
            </div>
          )}

          {mode === "voice" && (
            <div className="voice-panel">
              <h2>{voiceStatus}</h2>

              <div className="voice-buttons">
                <button onClick={activarVoz}>ACTIVAR</button>
                <button onClick={detenerVoz}>DETENER</button>
              </div>

              <p style={{ marginTop: "14px", opacity: 0.75 }}>
                Modo manos libres: di “Jarvis” y luego tu orden.
              </p>

              <p style={{ marginTop: "8px", opacity: 0.55 }}>
                Ejemplo: “Jarvis pon Back in Black”.
              </p>
            </div>
          )}

          {mode === "memory" && (
            <div className="voice-placeholder">
              <h2>Memoria</h2>
              <p>Recuerdos guardados:</p>

              <div
                style={{
                  maxHeight: "260px",
                  overflowY: "auto",
                  marginTop: "20px",
                }}
              >
                {memoryItems.map((item, index) => (
                  <div key={index} style={{ marginBottom: "12px" }}>
                    • {item.texto}
                  </div>
                ))}
              </div>
            </div>
          )}

          {mode === "home" && (
  <div
    className="voice-panel"
    style={{
      width: "100%",
      height: "100%",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      textAlign: "center",
      position: "relative",
      zIndex: 20,
      boxSizing: "border-box",
      padding: "20px",
    }}
  >
    <h2 style={{ marginBottom: "18px" }}>
      Visión Jarvis
    </h2>

    <div
      style={{
        width: "min(640px, 90vw)",
        aspectRatio: "4 / 3",
        overflow: "hidden",
        borderRadius: "16px",
        border: "2px solid cyan",
        backgroundColor: "black",
        boxShadow: "0 0 25px rgba(0, 255, 255, 0.35)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        margin: "0 auto",
      }}
    >
      <img
        src="http://127.0.0.1:5080/video"
        alt="Cámara de Jarvis"
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          display: "block",
          margin: 0,
          padding: 0,
        }}
      />
    </div>

    <p
      style={{
        marginTop: "12px",
        marginBottom: 0,
        opacity: 0.75,
      }}
    >
      Cámara conectada
    </p>
  </div>
)}

          {mode === "settings" && (
            <div className="settings-panel">
              <h2>Ajustes</h2>

              <div className="setting-row">
                <label>Idioma de reconocimiento</label>

                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  <option value="es-MX">Español Latino</option>
                  <option value="es-ES">Español España</option>
                  <option value="en-US">Inglés</option>
                </select>
              </div>
            </div>
          )}
        </section>

        {mode === "write" && (
          <section className="bottom-console">
            <input
              className="jarvis-input"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") sendMessage();
              }}
              placeholder="Escribe a Jarvis..."
            />

            <div className="console-actions">
              <button onClick={() => sendMessage()}>➤</button>
            </div>
          </section>
        )}

        {mode === "voice" && (
          <section className="bottom-console voice-console">
            <div className="voice-status">Modo voz activo · {voiceStatus}</div>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;