import { KokoroTTS } from "https://cdn.jsdelivr.net/npm/kokoro-js@1.2.1/+esm";

const MODEL_ID = "onnx-community/Kokoro-82M-v1.0-ONNX";
const VOICE = "af_heart";
let modelPromise = null;
let currentAudio = null;
let currentUrl = null;

function announce(status, detail = "") {
  window.dispatchEvent(new CustomEvent("studyquest:kokoro-status", { detail: { status, detail } }));
}

async function loadModel() {
  if (!modelPromise) {
    announce("loading", "Downloading the free voice for its first use…");
    let timeoutId;
    const loading = KokoroTTS.from_pretrained(MODEL_ID, {
      dtype: "q4",
      device: "wasm",
      progress_callback: progress => {
        if (progress.status === "progress" && Number.isFinite(progress.progress)) {
          announce("loading", `Downloading voice: ${Math.round(progress.progress)}%`);
        }
      }
    });
    const timeout = new Promise((_, reject) => {
      timeoutId = window.setTimeout(() => reject(new Error("Voice download timed out after 45 seconds.")), 45000);
    });
    modelPromise = Promise.race([loading, timeout]).then(model => {
      window.clearTimeout(timeoutId);
      announce("ready", "Kokoro voice ready");
      return model;
    }).catch(error => {
      window.clearTimeout(timeoutId);
      modelPromise = null;
      announce("error", error.message);
      throw error;
    });
  }
  return modelPromise;
}

async function speak(text) {
  const model = await loadModel();
  announce("generating", "Creating Buddy celebration…");
  const generated = await model.generate(String(text), { voice: VOICE, speed: 1.05 });
  const blob = generated.toBlob();
  if (currentAudio) currentAudio.pause();
  if (currentUrl) URL.revokeObjectURL(currentUrl);
  currentUrl = URL.createObjectURL(blob);
  currentAudio = new Audio(currentUrl);
  await currentAudio.play();
  announce("speaking", "Buddy is speaking");
  currentAudio.addEventListener("ended", () => announce("ready", "Kokoro voice ready"), { once: true });
  return true;
}

window.StudyQuestKokoroVoice = { speak, preload: loadModel, voice: VOICE };
