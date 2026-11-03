import { api } from "./api.js";
import { flashSeat, renderSeatmap } from "./seatmap.js";

const state = {
  seats: new Map(),
  selectedSeat: null,
  activeCancelSeat: null,
  eventCount: 0,
  busy: false,
};

const elements = {
  seatmap: document.querySelector("#seatmap"),
  selectedSeat: document.querySelector("#selected-seat"),
  summarySeat: document.querySelector("#summary-seat"),
  summaryName: document.querySelector("#summary-name"),
  bookingName: document.querySelector("#booking-name"),
  bookingForm: document.querySelector("#booking-form"),
  bookingError: document.querySelector("#booking-error"),
  bookButton: document.querySelector("#book-button"),
  cancelDialog: document.querySelector("#cancel-dialog"),
  cancelSeat: document.querySelector("#cancel-seat"),
  cancelName: document.querySelector("#cancel-name"),
  cancelError: document.querySelector("#cancel-error"),
  cancelForm: document.querySelector("#cancel-form"),
  cancelButton: document.querySelector("#cancel-button"),
  connectionStatus: document.querySelector("#connection-status"),
  connectionLabel: document.querySelector("#connection-label"),
  serverBanner: document.querySelector("#server-banner"),
  serverBannerMessage: document.querySelector("#server-banner-message"),
  activityList: document.querySelector("#activity-list"),
  activityEmpty: document.querySelector("#activity-empty"),
  raceForm: document.querySelector("#race-form"),
  raceClientCount: document.querySelector("#race-client-count"),
  raceResult: document.querySelector("#race-result"),
  raceRunButton: document.querySelector("#race-run-button"),
  raceSuccess: document.querySelector("#race-success"),
  raceRejected: document.querySelector("#race-rejected"),
  raceErrors: document.querySelector("#race-errors"),
  raceMessage: document.querySelector("#race-message"),
  raceDetails: document.querySelector("#race-details"),
  raceCleanButton: document.querySelector("#race-clean-button"),
};

function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  const icon = document.createElement("span");
  icon.className = "toast-icon";
  icon.textContent = type === "success" ? "✓" : "!";
  const text = document.createElement("span");
  text.textContent = message;
  toast.append(icon, text);
  document.querySelector("#toast-region").append(toast);
  window.setTimeout(() => toast.remove(), 4500);
}

function setServerState(connected, message = "") {
  elements.serverBanner.hidden = connected;
  if (!connected) elements.serverBannerMessage.textContent = message;
}

function setConnectionStatus(status) {
  elements.connectionStatus.classList.remove("live", "disconnected", "reconnecting");
  elements.connectionStatus.classList.add(status);
  elements.connectionLabel.textContent = {
    live: "Live",
    disconnected: "Terputus",
    reconnecting: "Menyambung ulang",
  }[status];
}

function renderSeats() {
  renderSeatmap(elements.seatmap, state.seats, state.selectedSeat, selectSeat);
  elements.selectedSeat.textContent = state.selectedSeat || "Belum dipilih";
  elements.summarySeat.textContent = state.selectedSeat || "—";
  elements.bookButton.disabled = !state.selectedSeat || state.busy;
}

function renderStatistics(stats) {
  document.querySelector("#stat-total").textContent = stats.total;
  document.querySelector("#stat-booked").textContent = stats.terpesan;
  document.querySelector("#stat-available").textContent = stats.tersedia;
  const occupancy = stats.total ? Math.round((stats.terpesan / stats.total) * 100) : 0;
  document.querySelector("#occupancy-value").textContent = `${occupancy}%`;
  document.querySelector("#occupancy-bar").style.width = `${occupancy}%`;
  document.querySelector(".progress-track").setAttribute("aria-valuenow", String(occupancy));
}

function selectSeat(seat) {
  if (state.busy) return;
  if (seat.status === "TERSEDIA") {
    state.selectedSeat = state.selectedSeat === seat.kursi_id ? null : seat.kursi_id;
    elements.bookingError.textContent = "";
    renderSeats();
    if (state.selectedSeat) elements.bookingName.focus();
    return;
  }
  state.activeCancelSeat = seat.kursi_id;
  elements.cancelSeat.textContent = seat.kursi_id;
  elements.cancelName.value = "";
  elements.cancelError.textContent = "";
  elements.cancelDialog.showModal();
  elements.cancelName.focus();
}

function setButtonLoading(button, loading) {
  button.classList.toggle("is-loading", loading);
  button.disabled = loading;
}

function addActivity(change) {
  const item = document.createElement("li");
  const booked = change.status === "TERPESAN";
  item.className = `activity-item${booked ? " booked" : ""}`;

  const main = document.createElement("div");
  main.className = "activity-main";
  const seat = document.createElement("span");
  seat.className = "activity-seat";
  seat.textContent = change.kursi_id;
  const description = document.createElement("div");
  description.className = "activity-text";
  const title = document.createElement("strong");
  title.textContent = booked ? "Kursi dipesan" : "Pemesanan dibatalkan";
  const details = document.createElement("span");
  details.textContent = change.pemesan ? `oleh ${change.pemesan}` : "Kursi tersedia";
  description.append(title, details);
  main.append(seat, description);
  const timestamp = document.createElement("time");
  const date = new Date(Number(change.waktu_ms));
  timestamp.className = "activity-time";
  timestamp.dateTime = date.toISOString();
  timestamp.textContent = date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  item.append(main, timestamp);
  elements.activityList.prepend(item);
  while (elements.activityList.children.length > 30) elements.activityList.lastElementChild.remove();
  state.eventCount += 1;
  document.querySelector("#activity-count").textContent = String(state.eventCount);
  elements.activityEmpty.hidden = true;
}

async function refreshStatistics() {
  const stats = await api.statistik();
  renderStatistics(stats);
}

async function refreshSeats() {
  const seats = await api.kursi();
  state.seats = new Map(seats.map((seat) => [seat.kursi_id, seat]));
  if (state.selectedSeat && state.seats.get(state.selectedSeat)?.status === "TERPESAN") {
    state.selectedSeat = null;
  }
  renderSeats();
  await refreshStatistics();
}

function applyStreamChange(change) {
  const previous = state.seats.get(change.kursi_id);
  const isSnapshot = change.snapshot === true;
  state.seats.set(change.kursi_id, {
    kursi_id: change.kursi_id,
    status: change.status,
    pemesan: change.pemesan,
  });
  if (state.selectedSeat === change.kursi_id && change.status === "TERPESAN") {
    state.selectedSeat = null;
    showToast(`Kursi ${change.kursi_id} baru saja dipesan orang lain. Silakan pilih kursi lain.`, "error");
  }
  renderSeats();
  if (!isSnapshot) flashSeat(elements.seatmap, change.kursi_id);
  if (!isSnapshot && (previous?.status !== change.status || previous?.pemesan !== change.pemesan)) {
    addActivity(change);
    refreshStatistics().catch(handleError);
  }
  setServerState(true);
}

function startStream() {
  const source = new EventSource("/api/stream");
  source.onopen = () => {
    setConnectionStatus("live");
    setServerState(true);
  };
  source.onmessage = (event) => {
    try {
      applyStreamChange(JSON.parse(event.data));
    } catch {
      showToast("Pembaruan kursi tidak dapat dibaca.", "error");
    }
  };
  source.addEventListener("stream_error", (event) => {
    let message = "Koneksi ke server bioskop terputus.";
    try {
      message = JSON.parse(event.data).pesan || message;
    } catch {
      // Gunakan pesan umum untuk data SSE yang tidak valid.
    }
    setConnectionStatus("reconnecting");
    setServerState(false, message);
    source.close();
    window.setTimeout(startStream, 1800);
  });
  source.onerror = () => {
    setConnectionStatus("reconnecting");
    api.health().then(() => setServerState(true)).catch(() => {
      setConnectionStatus("disconnected");
      setServerState(false, "Kami akan mencoba menyambungkan kembali secara otomatis.");
    });
  };
}

function handleError(error) {
  if (error.status === 503 || error.status === 504) {
    setServerState(false, error.message);
    setConnectionStatus("disconnected");
  }
  showToast(error.message || "Terjadi kesalahan. Silakan coba lagi.", "error");
}

function renderRaceResult(result) {
  elements.raceResult.hidden = false;

  elements.raceSuccess.textContent = result.berhasil;
  elements.raceRejected.textContent = result.ditolak;
  elements.raceErrors.textContent = result.error;

  elements.raceMessage.textContent = result.pesan || "Simulasi selesai.";

if (result.pemenang) {
  elements.raceMessage.textContent += ` Pemenang: ${result.pemenang}.`;
}

  elements.raceDetails.replaceChildren();

  (result.detail || []).forEach((item) => {
    const row = document.createElement("div");
    row.className = "race-detail-item";

    row.textContent = [
      item.client || item.nama || "Client",
      item.status || "",
      item.pesan || "",
    ].filter(Boolean).join(" — ");

    elements.raceDetails.append(row);
  });

  elements.raceCleanButton.hidden = !result.dapat_dibersihkan;
}

// Menjalankan simulasi race condition
elements.raceForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const jumlahClient = Number(elements.raceClientCount.value);

  elements.raceResult.hidden = true;
  elements.raceRunButton.disabled = true;
  elements.raceRunButton.textContent = "Simulasi sedang berjalan...";

  try {
    const result = await api.simulasiRace(jumlahClient);
    renderRaceResult(result);
    showToast(result.pesan || "Simulasi race condition selesai.");
    await refreshSeats();
  } catch (error) {
    handleError(error);
  } finally {
    elements.raceRunButton.disabled = false;
    elements.raceRunButton.textContent = "Jalankan Simulasi →";
  }
});

// Membersihkan hasil simulasi
elements.raceCleanButton.addEventListener("click", async () => {
  elements.raceCleanButton.disabled = true;

  try {
    const result = await api.bersihkanSimulasi();

    elements.raceResult.hidden = true;

    showToast(result.pesan || "Hasil simulasi berhasil dibersihkan.");
    await refreshSeats();
  } catch (error) {
    handleError(error);
  } finally {
    elements.raceCleanButton.disabled = false;
  }
});

function switchTab(activity) {
  document.querySelector("#seatmap-view").hidden = activity;
  document.querySelector("#activity-view").hidden = !activity;
  document.querySelector("#tab-seatmap").classList.toggle("active", !activity);
  document.querySelector("#tab-activity").classList.toggle("active", activity);
  document.querySelector("#tab-seatmap").setAttribute("aria-selected", String(!activity));
  document.querySelector("#tab-activity").setAttribute("aria-selected", String(activity));
}

elements.bookingName.addEventListener("input", () => {
  elements.summaryName.textContent = elements.bookingName.value.trim() || "—";
  elements.bookingError.textContent = "";
});

elements.bookingForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const pemesan = elements.bookingName.value.trim();
  if (!state.selectedSeat) {
    elements.bookingError.textContent = "Pilih kursi yang tersedia terlebih dahulu.";
    return;
  }
  if (!pemesan) {
    elements.bookingError.textContent = "Nama pemesan wajib diisi.";
    elements.bookingName.focus();
    return;
  }

  state.busy = true;
  renderSeats();
  setButtonLoading(elements.bookButton, true);
  elements.bookingError.textContent = "";
  try {
    const result = await api.pesan(state.selectedSeat, pemesan);
    if (result.sukses) {
      showToast(result.pesan || `Kursi ${state.selectedSeat} berhasil dipesan.`);
      state.selectedSeat = null;
      elements.bookingName.value = "";
      elements.summaryName.textContent = "—";
    } else {
      showToast(result.pesan || "Kursi tidak dapat dipesan.", "error");
    }
    await refreshSeats();
  } catch (error) {
    handleError(error);
    if (error.status === 503 || error.status === 504) {
      await refreshSeats().catch(() => {});
    } else {
      await refreshSeats().catch(handleError);
    }
  } finally {
    state.busy = false;
    setButtonLoading(elements.bookButton, false);
    renderSeats();
  }
});

elements.cancelForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const pemesan = elements.cancelName.value.trim();
  if (!pemesan) {
    elements.cancelError.textContent = "Nama pemesan wajib diisi.";
    elements.cancelName.focus();
    return;
  }
  state.busy = true;
  setButtonLoading(elements.cancelButton, true);
  elements.cancelError.textContent = "";
  try {
    const result = await api.batal(state.activeCancelSeat, pemesan);
    if (result.sukses) {
      showToast(result.pesan || `Pesanan kursi ${state.activeCancelSeat} berhasil dibatalkan.`);
      elements.cancelDialog.close();
    } else {
      elements.cancelError.textContent = result.pesan || "Nama pemesan tidak sesuai.";
      showToast(result.pesan || "Pembatalan ditolak. Pastikan nama pemesan asli.", "error");
    }
    await refreshSeats();
  } catch (error) {
    handleError(error);
  } finally {
    state.busy = false;
    setButtonLoading(elements.cancelButton, false);
    renderSeats();
  }
});

document.querySelector("#close-dialog").addEventListener("click", () => elements.cancelDialog.close());
document.querySelector("#keep-seat").addEventListener("click", () => elements.cancelDialog.close());
document.querySelector("#tab-seatmap").addEventListener("click", () => switchTab(false));
document.querySelector("#tab-activity").addEventListener("click", () => switchTab(true));
document.querySelector("#theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("ruang-layar-theme", next);
});

const savedTheme = localStorage.getItem("ruang-layar-theme");
if (savedTheme === "light" || savedTheme === "dark") {
  document.documentElement.dataset.theme = savedTheme;
}

renderSeats();
refreshSeats()
  .then(() => setServerState(true))
  .catch((error) => {
    setServerState(false, error.message);
    setConnectionStatus("disconnected");
  });
startStream();
window.setInterval(() => {
  api.health().then(() => setServerState(true)).catch(() => {
    setServerState(false, "Kami akan mencoba menyambungkan kembali secara otomatis.");
    setConnectionStatus("disconnected");
  });
}, 10000);
