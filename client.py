"""Client reservasi bioskop: library (timeout + retry + request_id) dan CLI."""
import argparse
import time
import uuid

import grpc

import cinema_pb2 as pb
import cinema_pb2_grpc as pb_grpc

DAPAT_DIULANG = (grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.UNAVAILABLE)

BARIS = "ABCDE"
KOLOM = 10

KURSI_VALID = {
    f"{b}{k}"
    for b in BARIS
    for k in range(1, KOLOM + 1)
}


def validasi_input(kursi_id, pemesan):
    """Membersihkan dan memvalidasi input pemesanan."""

    kursi_id = kursi_id.strip().upper()
    pemesan = pemesan.strip()

    if not kursi_id:
        raise ValueError("Nomor kursi wajib diisi")

    if kursi_id not in KURSI_VALID:
        raise ValueError(
            f"Kursi {kursi_id} tidak valid. "
            "Gunakan A1 sampai E10."
        )

    if not pemesan:
        raise ValueError("Nama pemesan wajib diisi")

    return kursi_id, pemesan



def dengan_retry(panggil, maks=4, dasar=0.5, log=True):
    """Jalankan panggil(nomor_percobaan) dengan exponential backoff."""
    for p in range(1, maks + 1):
        try:
            return panggil(p)
        except grpc.RpcError as e:
            if e.code() not in DAPAT_DIULANG or p == maks:
                raise
            jeda = dasar * 2 ** (p - 1)
            if log:
                print(f"  percobaan {p} gagal ({e.code().name}), ulang dalam {jeda}s", flush=True)
            time.sleep(jeda)


def pesan_kursi(stub, kursi_id, pemesan, timeout=2.0, maks=4, id_tetap=True, log=True):
    kursi_id, pemesan = validasi_input(kursi_id, pemesan)

    rid = str(uuid.uuid4())

    def panggil(p):
        r = rid if id_tetap else str(uuid.uuid4())  # id_tetap=False hanya untuk demo kesalahan
        req = pb.PesanKursiRequest(request_id=r, kursi_id=kursi_id, pemesan=pemesan)
        return stub.PesanKursi(req, timeout=timeout)

    return dengan_retry(panggil, maks=maks, log=log)


def lihat_kursi(stub, timeout=2.0):  # idempoten -> aman di-retry
    return dengan_retry(lambda p: stub.LihatKursi(pb.Kosong(), timeout=timeout))



def batal(stub, kursi_id, pemesan, timeout=2.0):
    kursi_id, pemesan = validasi_input(kursi_id, pemesan)

    return stub.BatalkanPesanan(
        pb.BatalRequest(
            kursi_id=kursi_id,
            pemesan=pemesan
        ),
        timeout=timeout
    )


def statistik(stub, timeout=2.0):
    return dengan_retry(lambda p: stub.GetStatistik(pb.Kosong(), timeout=timeout))


def cetak_denah(denah):
    peta = {k.kursi_id: k.status for k in denah.kursi}
    print("      " + " ".join(f"{k:>2}" for k in range(1, 11)))
    for b in "ABCDE":
        baris = " ".join(" X" if peta[f"{b}{k}"] == pb.TERPESAN else " ." for k in range(1, 11))
        print(f"  {b}   {baris}")
    print("  (. = tersedia, X = terpesan)")


def main():
    ap = argparse.ArgumentParser(description="Client bioskop gRPC")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=50051)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lihat")
    sub.add_parser("statistik")
    sub.add_parser("pantau")
    p = sub.add_parser("pesan"); p.add_argument("kursi"); p.add_argument("pemesan")
    p = sub.add_parser("batal"); p.add_argument("kursi"); p.add_argument("pemesan")
    p = sub.add_parser("demo-retry", help="demo timeout+retry; jalankan server dengan --lambat 1.0")
    p.add_argument("kursi"); p.add_argument("pemesan")
    p.add_argument("--id-baru", action="store_true", help="BUAT request_id baru tiap retry (salah!)")
    a = ap.parse_args()

    with grpc.insecure_channel(f"{a.host}:{a.port}") as ch:
        stub = pb_grpc.BioskopStub(ch)
        try:
            if a.cmd == "lihat":
                cetak_denah(lihat_kursi(stub))
            elif a.cmd == "statistik":
                s = statistik(stub); print(f"Total={s.total} Terpesan={s.terpesan} Tersedia={s.tersedia}")
            elif a.cmd == "pesan":
                print(pesan_kursi(stub, a.kursi, a.pemesan).pesan)
            elif a.cmd == "batal":
                print(batal(stub, a.kursi, a.pemesan).pesan)
            elif a.cmd == "demo-retry":
                r = pesan_kursi(stub, a.kursi, a.pemesan, timeout=1.0, id_tetap=not a.id_baru)
                print("Hasil akhir:", r.sukses, "-", r.pesan)
            elif a.cmd == "pantau":
                print("Memantau perubahan kursi (Ctrl+C untuk berhenti)...")
                for ev in stub.StreamStatusKursi(pb.Kosong()):
                    print(f"  {ev.kursi_id}: {pb.StatusKursi.Name(ev.status)} {ev.pemesan}")
   
        except ValueError as e:
            print("Input tidak valid:", e)

        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNAVAILABLE:
                print(
                    "Server tidak dapat dihubungi. "
                    "Pastikan server sedang berjalan."
                )

            elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                print(
                    "Permintaan melewati batas waktu. "
                    "Silakan periksa koneksi dan status server."
                )

            else:
                print(
                    "Terjadi kesalahan:",
                    e.code().name,
                    "-",
                    e.details()
                )

        except KeyboardInterrupt:
            print("\nProgram dihentikan.")



if __name__ == "__main__":
    main()
