export const LANGUAGES = Object.freeze([
  Object.freeze({ id: "en", label: "English", flag: "flag-en.png", prototypeEnabled: true }),
  Object.freeze({ id: "es", label: "Spanish", flag: "flag-es.png", prototypeEnabled: false }),
  Object.freeze({ id: "de", label: "German", flag: "flag-de.png", prototypeEnabled: false }),
  Object.freeze({ id: "fr", label: "French", flag: "flag-fr.png", searchTerms: "France", prototypeEnabled: false }),
  Object.freeze({ id: "ja", label: "Japanese", flag: "flag-ja.png", prototypeEnabled: false }),
  Object.freeze({ id: "uk", label: "Ukrainian", flag: "flag-uk.png", prototypeEnabled: false }),
]);

export const MODEL_INFO = Object.freeze({
  name: "Whisper Large v3 Turbo",
  size: "1.6 GB",
  languagesSupported: "99 languages",
  ramVram: "6 GB / 4 GB",
  license: "MIT",
});

const DOWNLOAD_LIMIT = 68;
const DOWNLOAD_TOTAL_GB = 1.6;
const DOWNLOAD_ETA = "About 2 min remaining";

export function createInitialState() {
  return {
    view: "select",
    selectedLanguage: null,
    download: null,
  };
}

function createDownload(percentage = 0) {
  const clampedPercentage = Math.max(0, Math.min(DOWNLOAD_LIMIT, Number(percentage) || 0));
  const downloadedGb = Number(((clampedPercentage / 100) * DOWNLOAD_TOTAL_GB).toFixed(1));

  return {
    status: "downloading",
    percentage: clampedPercentage,
    downloadedGb,
    totalGb: DOWNLOAD_TOTAL_GB,
    eta: DOWNLOAD_ETA,
  };
}

export function transition(state, event = {}) {
  switch (event.type) {
    case "select-language":
      if (event.language !== "en" || state.view === "downloading") return state;
      return {
        view: "ready",
        selectedLanguage: "en",
        download: null,
      };

    case "start-download":
      if (state.view !== "ready" || state.selectedLanguage !== "en") return state;
      return {
        ...state,
        view: "downloading",
        download: createDownload(),
      };

    case "progress":
      if (state.view !== "downloading" || !state.download) return state;
      return {
        ...state,
        download: createDownload(event.percentage),
      };

    case "cancel-download":
      if (state.view !== "downloading") return state;
      return {
        view: "ready",
        selectedLanguage: state.selectedLanguage,
        download: null,
      };

    default:
      return state;
  }
}

export function filterLanguages(languages, query) {
  const normalizedQuery = String(query ?? "").trim().toLocaleLowerCase();
  if (!normalizedQuery) return [...languages];

  return languages.filter(({ label, searchTerms = "" }) =>
    `${label} ${searchTerms}`.toLocaleLowerCase().includes(normalizedQuery),
  );
}

function formatGigabytes(value) {
  return `${Number(value).toFixed(1)} GB`;
}

export function formatProgress(session) {
  return {
    percentage: `${session.percentage}%`,
    transferred: `${formatGigabytes(session.downloadedGb)} of ${formatGigabytes(session.totalGb)}`,
    eta: session.eta,
  };
}

export function mountModelDownload(
  root = typeof document === "undefined"
    ? null
    : document.querySelector('[data-app="model-download"]'),
) {
  if (!root) return () => {};

  let state = createInitialState();
  let progressTimer = null;

  const views = [...root.querySelectorAll("[data-view]")];
  const languageRows = [...root.querySelectorAll(".language-row[data-language]")];
  const progressbar = root.querySelector('[role="progressbar"]');

  const stopProgress = () => {
    if (progressTimer !== null) {
      window.clearInterval(progressTimer);
      progressTimer = null;
    }
  };

  const renderProgress = () => {
    if (!state.download || !progressbar) return;

    const formatted = formatProgress(state.download);
    root.querySelector("[data-progress-percentage]").textContent = formatted.percentage;
    root.querySelector("[data-progress-transferred]").textContent = formatted.transferred;
    root.querySelector("[data-progress-eta]").textContent = formatted.eta;
    root.querySelector("[data-progress-fill]").style.width = `${state.download.percentage}%`;
    progressbar.setAttribute("aria-valuenow", String(state.download.percentage));
    progressbar.setAttribute("aria-valuetext", `${formatted.percentage}, ${formatted.transferred}`);
  };

  const render = () => {
    root.dataset.currentView = state.view;
    for (const view of views) view.hidden = view.dataset.view !== state.view;
    for (const row of languageRows) {
      const isSelected = row.dataset.language === state.selectedLanguage;
      row.classList.toggle("is-selected", isSelected);
      row.setAttribute("aria-pressed", String(isSelected));

      const checkmark = row.querySelector(".language-row__check");
      if (checkmark) checkmark.hidden = !isSelected;
    }
    renderProgress();
  };

  const advanceProgress = () => {
    if (!state.download || state.download.percentage >= DOWNLOAD_LIMIT) {
      stopProgress();
      return;
    }

    state = transition(state, {
      type: "progress",
      percentage: Math.min(state.download.percentage + 4, DOWNLOAD_LIMIT),
    });
    render();
  };

  const beginProgress = () => {
    stopProgress();

    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      state = transition(state, { type: "progress", percentage: DOWNLOAD_LIMIT });
      render();
      return;
    }

    progressTimer = window.setInterval(advanceProgress, 80);
  };

  root.addEventListener("click", (event) => {
    const control = event.target.closest("[data-action]");
    if (!control || !root.contains(control)) return;

    const action = control.dataset.action;
    if (action === "select-language") {
      state = transition(state, {
        type: "select-language",
        language: control.dataset.language,
      });
    } else if (action === "download") {
      state = transition(state, { type: "start-download" });
      if (state.view === "downloading") beginProgress();
    } else if (action === "cancel") {
      stopProgress();
      state = transition(state, { type: "cancel-download" });
    }

    render();
  });

  render();

  return () => {
    stopProgress();
  };
}

if (typeof document !== "undefined") {
  mountModelDownload();
}
