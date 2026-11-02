"""Server reservasi bioskop (gRPC).

Opsi simulasi (untuk demo & pembuktian di laporan):
  --tanpa-lock        matikan lock -> race condition bisa dibuktikan
  --jeda-kritis MS    jeda di dalam bagian kritis (memperbesar peluang race)
  --lambat P          peluang (0-1) balasan PesanKursi terlambat 3 detik
                      SETELAH pemesanan terjadi (simulasi balasan hilang)
"""
import argparse
import contextlib
import queue
import random
import threading
import time
from concurrent import futures

import grpc

import cinema_pb2 as pb
import cinema_pb2_grpc as pb_grpc

BARIS = "ABCDE"
KOLOM = 10


class Studio:
    """Data bersama. Semua akses ke kursi/proses dilindungi satu lock."""

    def __init__(self, pakai_lock=True, jeda_kritis_ms=0):
        self.kursi = {f"{b}{k}": "" for b in BARIS for k in range(1, KOLOM + 1)}  # id -> pemesan ("" = kosong)
        self.proses = {}   # request_id -> (kursi_id, pemesan, StatusResponse)
        self.lock = threading.Lock() if pakai_lock else contextlib.nullcontext()
        self.jeda_kritis = jeda_kritis_ms / 1000.0
        self.subs = set()  # antrean milik tiap client streaming
        self.subs_lock = threading.Lock()

    def publikasi(self, kursi_id, status, pemesan):
        ev = pb.PerubahanKursi(kursi_id=kursi_id, status=status, pemesan=pemesan,
                               waktu_ms=int(time.time() * 1000))
        with self.subs_lock:
            for q in list(self.subs):
                q.put(ev)


class Bioskop(pb_grpc.BioskopServicer):
    def __init__(self, studio, peluang_lambat=0.0):
        self.s = studio
        self.peluang_lambat = peluang_lambat

    def LihatKursi(self, request, context):
        with self.s.lock:
            daftar = [pb.Kursi(kursi_id=k, status=pb.TERPESAN if p else pb.TERSEDIA, pemesan=p)
                      for k, p in self.s.kursi.items()]
        return pb.DenahKursi(kursi=daftar)

    
    def PesanKursi(self, request, context):
        # 1. Normalisasi input
        request_id = request.request_id.strip()
        kursi_id = request.kursi_id.strip().upper()
        pemesan = request.pemesan.strip()

        # 2. Validasi input
        if not request_id:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "request_id wajib diisi"
            )

        if not pemesan:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "Nama pemesan wajib diisi"
            )

        if kursi_id not in self.s.kursi:
            context.abort(
                grpc.StatusCode.NOT_FOUND,
                f"Kursi {kursi_id} tidak ditemukan"
            )

        # 3. Periksa request_id dan proses pemesanan
        with self.s.lock:

            sebelumnya = self.s.proses.get(request_id)

            # Kalau request_id pernah digunakan
            if sebelumnya is not None:
                kursi_lama, pemesan_lama, hasil_lama = sebelumnya

                # ID sama tetapi isi permintaan berbeda
                if kursi_lama != kursi_id or pemesan_lama != pemesan:
                    context.abort(
                        grpc.StatusCode.INVALID_ARGUMENT,
                        "request_id sudah digunakan untuk permintaan berbeda"
                    )

                # Permintaan sama: kembalikan hasil sebelumnya
                return hasil_lama

            # 4. Periksa ketersediaan kursi
            if self.s.kursi[kursi_id]:
                hasil = pb.StatusResponse(
                    sukses=False,
                    pesan=f"Kursi {kursi_id} sudah dipesan"
                )

            else:
                if self.s.jeda_kritis:
                    time.sleep(self.s.jeda_kritis)

                # 5. Simpan pemesanan
                self.s.kursi[kursi_id] = pemesan

                hasil = pb.StatusResponse(
                    sukses=True,
                    pesan=f"Kursi {kursi_id} berhasil dipesan"
                )

                # 6. Beritahu client yang sedang memantau kursi
                self.s.publikasi(
                    kursi_id,
                    pb.TERPESAN,
                    pemesan
                )

            # 7. Simpan ID, isi permintaan, dan hasilnya
            self.s.proses[request_id] = (
                kursi_id,
                pemesan,
                hasil
            )

        return hasil


    def BatalkanPesanan(self, request, context):
        if request.kursi_id not in self.s.kursi:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Kursi {request.kursi_id} tidak ada")
        with self.s.lock:
            pemilik = self.s.kursi[request.kursi_id]
            if not pemilik:
                return pb.StatusResponse(sukses=False, pesan="Kursi belum dipesan")
            if pemilik != request.pemesan:
                return pb.StatusResponse(sukses=False, pesan="Bukan pemesan kursi ini")
            self.s.kursi[request.kursi_id] = ""
            self.s.publikasi(request.kursi_id, pb.TERSEDIA, "")
        return pb.StatusResponse(sukses=True, pesan=f"Pesanan kursi {request.kursi_id} dibatalkan")

    def StreamStatusKursi(self, request, context):
        q = queue.Queue()
        with self.s.subs_lock:
            self.s.subs.add(q)          # daftar dulu agar tidak ada perubahan yang terlewat
        try:
            with self.s.lock:
                snapshot = list(self.s.kursi.items())
            now = int(time.time() * 1000)
            for k, p in snapshot:       # kirim kondisi awal
                yield pb.PerubahanKursi(kursi_id=k, status=pb.TERPESAN if p else pb.TERSEDIA,
                                        pemesan=p, waktu_ms=now)
            while context.is_active():  # lalu kirim setiap perubahan
                try:
                    yield q.get(timeout=1.0)
                except queue.Empty:
                    continue
        finally:
            with self.s.subs_lock:
                self.s.subs.discard(q)

    def GetStatistik(self, request, context):
        with self.s.lock:
            terpesan = sum(1 for p in self.s.kursi.values() if p)
        total = len(self.s.kursi)
        return pb.Statistik(total=total, terpesan=terpesan, tersedia=total - terpesan)


def serve():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=50051)
    ap.add_argument("--workers", type=int, default=64,
                    help="max_workers; tiap stream aktif memakai 1 thread")
    ap.add_argument("--tanpa-lock", action="store_true")
    ap.add_argument("--jeda-kritis", type=float, default=0, help="ms")
    ap.add_argument("--lambat", type=float, default=0.0)
    a = ap.parse_args()

    studio = Studio(pakai_lock=not a.tanpa_lock, jeda_kritis_ms=a.jeda_kritis)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=a.workers))
    pb_grpc.add_BioskopServicer_to_server(Bioskop(studio, a.lambat), server)
    server.add_insecure_port(f"[::]:{a.port}")
    server.start()
    print(f"Server bioskop berjalan di port {a.port} "
          f"(lock={'OFF' if a.tanpa_lock else 'ON'}, workers={a.workers}, lambat={a.lambat})", flush=True)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
