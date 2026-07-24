(() => {
  "use strict";

  const FILE_INFO = Object.freeze({
    name: "meeting-recording.mp4",
    duration: "00:02:14",
    size: "28.6 MB",
    format: "MP4",
  });

  const PROCESSING_PERCENTAGE = 62;

  function createInitialState() {
    return {
      view: "ready",
      language: "Auto detect",
      speakers: 2,
      processing: null,
      isPlaying: false,
    };
  }

  function createProcessingSession() {
    return {
      stage: "transcribing",
      percentage: PROCESSING_PERCENTAGE,
      elapsed: "01:42",
      estimatedTotal: "03:10",
    };
  }

  function transition(state, event = {}) {
    switch (event.type) {
      case "set-language":
        if (state.view !== "ready") return state;
        return { ...state, language: String(event.language || "Auto detect") };

      case "set-speakers": {
        if (state.view !== "ready") return state;
        const speakers = Math.max(1, Math.min(8, Math.round(Number(event.speakers) || 1)));
        return { ...state, speakers };
      }

      case "start-transcription":
        if (state.view !== "ready") return state;
        return { ...state, view: "processing", processing: createProcessingSession(), isPlaying: false };

      case "complete-transcription":
        if (state.view !== "processing") return state;
        return { ...state, view: "complete", processing: null, isPlaying: false };

      case "cancel-transcription":
        if (state.view === "ready") return state;
        return { ...state, view: "ready", processing: null, isPlaying: false };

      case "toggle-playback":
        if (state.view !== "complete") return state;
        return { ...state, isPlaying: !state.isPlaying };

      default:
        return state;
    }
  }

  function formatProgress(session) {
    return {
      percentage: `${session.percentage}%`,
      elapsed: `Elapsed ${session.elapsed}`,
      estimatedTotal: `Estimated total ${session.estimatedTotal}`,
    };
  }

  function mountTranscriberMain(root = document.querySelector('[data-app="transcriber-main"]')) {
    if (!root) return () => {};

    let state = createInitialState();
    let completionTimer = null;
    const views = [...root.querySelectorAll("[data-view]")];
    const queryState = new URLSearchParams(globalThis.location?.search || "").get("state");
    const freezeReferenceState = queryState === "processing";

    if (queryState === "processing") {
      state = transition(state, { type: "start-transcription" });
    } else if (queryState === "complete") {
      state = transition(transition(state, { type: "start-transcription" }), { type: "complete-transcription" });
    }

    const stopCompletion = () => {
      if (completionTimer !== null) {
        globalThis.clearTimeout(completionTimer);
        completionTimer = null;
      }
    };

    const render = () => {
      root.dataset.currentView = state.view;
      for (const view of views) view.hidden = view.dataset.view !== state.view;
      for (const output of root.querySelectorAll("[data-speaker-count]")) output.textContent = String(state.speakers);
      for (const select of root.querySelectorAll('[data-field="language"]')) select.value = state.language;

      const playButton = root.querySelector('[data-action="toggle-play"]');
      if (playButton) {
        playButton.setAttribute("aria-label", state.isPlaying ? "Pause transcript recording" : "Play transcript recording");
        playButton.classList.toggle("is-playing", state.isPlaying);
      }
    };

    const scheduleCompletion = () => {
      stopCompletion();
      if (freezeReferenceState) return;
      const reducedMotion = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
      completionTimer = globalThis.setTimeout(() => {
        state = transition(state, { type: "complete-transcription" });
        render();
      }, reducedMotion ? 900 : 4800);
    };

    root.addEventListener("click", (event) => {
      const control = event.target.closest("[data-action]");
      if (!control || !root.contains(control)) return;

      switch (control.dataset.action) {
        case "transcribe":
          state = transition(state, { type: "start-transcription" });
          render();
          scheduleCompletion();
          return;
        case "cancel":
          stopCompletion();
          state = transition(state, { type: "cancel-transcription" });
          break;
        case "increase-speakers":
          state = transition(state, { type: "set-speakers", speakers: state.speakers + 1 });
          break;
        case "decrease-speakers":
          state = transition(state, { type: "set-speakers", speakers: state.speakers - 1 });
          break;
        case "toggle-play":
          state = transition(state, { type: "toggle-playback" });
          break;
        case "open-file":
          state = { ...createInitialState(), language: state.language, speakers: state.speakers };
          break;
        default:
          return;
      }

      render();
    });

    root.addEventListener("change", (event) => {
      if (!event.target.matches('[data-field="language"]')) return;
      state = transition(state, { type: "set-language", language: event.target.value });
      render();
    });

    render();
    return stopCompletion;
  }

  globalThis.TranscriberMainClassic = Object.freeze({
    FILE_INFO,
    createInitialState,
    transition,
    formatProgress,
  });

  if (typeof document !== "undefined") mountTranscriberMain();
})();
