async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = "Permintaan gagal. Silakan coba lagi.";
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Tetap gunakan pesan umum jika respons bukan JSON.
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export const api = {
  kursi: () => request("/api/kursi"),
  statistik: () => request("/api/statistik"),
  health: () => request("/api/health"),
  pesan: (kursi_id, pemesan) =>
    request("/api/pesan", {
      method: "POST",
      body: JSON.stringify({ kursi_id, pemesan }),
    }),
  batal: (kursi_id, pemesan) =>
    request("/api/batal", {
      method: "POST",
      body: JSON.stringify({ kursi_id, pemesan }),
    }),

    simulasiRace: (jumlah_client, kursi_id) =>
    request("/api/simulasi/race", {
    method: "POST",
    body: JSON.stringify({ jumlah_client, kursi_id }),
    }),
  
  bersihkanSimulasi: () =>
    request("/api/simulasi/bersihkan", {
      method: "POST",
      body: JSON.stringify({}),
    }),
};

