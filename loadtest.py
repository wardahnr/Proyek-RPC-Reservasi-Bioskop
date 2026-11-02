"""Pengujian beban untuk sistem reservasi bioskop berbasis gRPC.

Mode:
  race    : beberapa client berebut satu kursi yang sama.
  kinerja : mengukur siklus pesan-lihat-batal untuk 1, 5, dan 20 client.
  semua   : menjalankan kedua pengujian.

Throughput dihitung dari jumlah RPC yang menerima respons dibagi waktu uji.
RPC yang gagal karena error komunikasi dicatat terpisah.
"""
import argparse
import csv
import math
import statistics
import sys
import threading
import time
import uuid

import grpc

import cinema_pb2 as pb
import cinema_pb2_grpc as pb_grpc

BARIS = "ABCDE"
KOLOM = 10
SEMUA_KURSI = [f"{b}{k}" for b in BARIS for k in range(1, KOLOM + 1)]


def buat_stub(alamat):
    """Membuat channel dan stub gRPC untuk satu client pengujian."""
    channel = grpc.insecure_channel(alamat)
    return channel, pb_grpc.BioskopStub(channel)


def kursi_tersedia(stub, jumlah=1, timeout=5):
    """Mengambil sejumlah ID kursi yang saat ini masih tersedia."""
    denah = stub.LihatKursi(pb.Kosong(), timeout=timeout)
    tersedia = [k.kursi_id for k in denah.kursi if k.status == pb.TERSEDIA]
    if len(tersedia) < jumlah:
        raise RuntimeError(
            f"Kursi tersedia hanya {len(tersedia)}, sedangkan pengujian membutuhkan {jumlah}. "
            "Batalkan beberapa pesanan atau kurangi jumlah client."
        )
    return tersedia[:jumlah]


def bersihkan_kursi(alamat, kursi_id, pemilik_yang_diharapkan=None):
    """Membatalkan kursi uji hanya jika pemiliknya cocok dengan penguji."""
    channel = None
    try:
        channel, stub = buat_stub(alamat)
        denah = stub.LihatKursi(pb.Kosong(), timeout=5)
        detail = next((k for k in denah.kursi if k.kursi_id == kursi_id), None)
        if detail is None or detail.status != pb.TERPESAN or not detail.pemesan:
            return True
        if pemilik_yang_diharapkan is not None and detail.pemesan not in pemilik_yang_diharapkan:
            print(
                f"  Peringatan: {kursi_id} dimiliki {detail.pemesan}; "
                "tidak dibatalkan karena bukan pemilik pengujian."
            )
            return False
        hasil = stub.BatalkanPesanan(
            pb.BatalRequest(kursi_id=kursi_id, pemesan=detail.pemesan),
            timeout=5,
        )
        return hasil.sukses
    except grpc.RpcError as exc:
        print(f"  Peringatan: gagal membersihkan {kursi_id}: {exc.code().name} - {exc.details()}")
        return False
    finally:
        if channel is not None:
            channel.close()


def uji_race(alamat, n_client=20, ronde=5, timeout_rpc=10):
    """Menguji apakah tepat satu dari beberapa client berhasil memesan kursi yang sama."""
    print(
        f"\n=== UJI RACE CONDITION: {n_client} client berebut 1 kursi, {ronde} ronde ===",
        flush=True,
    )
    if n_client < 2:
        print("Pengujian race membutuhkan minimal 2 client.")
        return False

    semua_ok = True

    for nomor_ronde in range(ronde):
        channel_awal = None
        try:
            channel_awal, stub_awal = buat_stub(alamat)
            kursi = kursi_tersedia(stub_awal, jumlah=1)[0]
        except (grpc.RpcError, RuntimeError) as exc:
            print(f"Ronde {nomor_ronde + 1}: tidak dapat menyiapkan pengujian: {exc}")
            semua_ok = False
            break
        finally:
            if channel_awal is not None:
                channel_awal.close()

        hasil = []
        error = []
        lock_hasil = threading.Lock()
        
        barrier = threading.Barrier(n_client + 1, timeout=15)

        def kerja(indeks):
            channel = None
            nama = f"race_{nomor_ronde + 1}_user{indeks}"
            try:
                channel, stub = buat_stub(alamat)
                
                stub.GetStatistik(pb.Kosong(), timeout=timeout_rpc)
                barrier.wait()

                response = stub.PesanKursi(
                    pb.PesanKursiRequest(
                        request_id=str(uuid.uuid4()),
                        kursi_id=kursi,
                        pemesan=nama,
                    ),
                    timeout=timeout_rpc,
                )
                with lock_hasil:
                    hasil.append((nama, response.sukses, response.pesan))
            except threading.BrokenBarrierError:
                with lock_hasil:
                    error.append(f"{nama}: tidak berhasil mencapai titik mulai bersama (barrier timeout)")
            except grpc.RpcError as exc:
                with lock_hasil:
                    error.append(f"{nama}: {exc.code().name} - {exc.details()}")
                try:
                    barrier.abort()
                except Exception:
                    pass
            except Exception as exc:
                with lock_hasil:
                    error.append(f"{nama}: {type(exc).__name__}: {exc}")
                try:
                    barrier.abort()
                except Exception:
                    pass
            finally:
                if channel is not None:
                    channel.close()

        threads = [
            threading.Thread(target=kerja, args=(i,), name=f"race-client-{i + 1}")
            for i in range(n_client)
        ]
        for thread in threads:
            thread.start()

        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            with lock_hasil:
                error.append("Thread utama: barrier gagal; tidak semua client siap.")

        for thread in threads:
            thread.join(timeout=timeout_rpc + 5)

        masih_aktif = [thread.name for thread in threads if thread.is_alive()]
        if masih_aktif:
            error.append("Thread belum selesai: " + ", ".join(masih_aktif))

        pemenang = [nama for nama, sukses, _ in hasil if sukses]
        ditolak = sum(1 for _, sukses, _ in hasil if not sukses)
        ok = len(hasil) == n_client and len(pemenang) == 1 and not error
        semua_ok = semua_ok and ok

        print(
            f"  ronde {nomor_ronde + 1}: kursi {kursi} -> "
            f"respons={len(hasil)}/{n_client}, berhasil={len(pemenang)}, "
            f"ditolak={ditolak}, error_rpc/thread={len(error)} "
            f"{'OK' if ok else '<-- PERIKSA HASIL'}",
            flush=True,
        )
        for pesan_error in error[:5]:
            print(f"    Error: {pesan_error}")

        if pemenang:
            bersih = bersihkan_kursi(alamat, kursi, set(pemenang))
            if not bersih:
                print(f"  Peringatan: kursi {kursi} belum dapat dipastikan bersih.")

    print(
        "HASIL:",
        "LULUS (tepat satu pemenang pada setiap ronde)" if semua_ok else "GAGAL (periksa rincian di atas)",
        flush=True,
    )
    return semua_ok


def _persentil95(nilai):
    """Menghitung persentil ke-95 dengan nearest-rank."""
    if not nilai:
        return 0.0
    urut = sorted(nilai)
    indeks = max(0, math.ceil(0.95 * len(urut)) - 1)
    return urut[indeks]


def uji_kinerja(
    alamat,
    jumlah_client=(1, 5, 20),
    total_siklus=200,
    keluaran="hasil_kinerja.csv",
    timeout_rpc=10,
):
    """Satu siklus berisi PesanKursi + LihatKursi + BatalkanPesanan.

    Throughput = RPC yang menerima respons / waktu pengujian.
    Latensi dihitung dari RPC yang menerima respons. Error komunikasi dicatat terpisah.
    """
    print(
        f"\n=== UJI KINERJA: target {total_siklus} siklus per skenario (maks. 3 RPC/siklus) ===",
        flush=True,
    )
    hasil_skenario = []

    for n_client in jumlah_client:
        if n_client < 1:
            print(f"Lewati skenario {n_client} client: jumlah harus minimal 1.")
            continue

        channel_awal = None
        try:
            channel_awal, stub_awal = buat_stub(alamat)
            daftar_kursi = kursi_tersedia(stub_awal, jumlah=n_client)
        except (grpc.RpcError, RuntimeError) as exc:
            print(f"Tidak dapat memulai skenario {n_client} client: {exc}")
            hasil_skenario.append({"client": n_client, "gagal_setup": str(exc)})
            continue
        finally:
            if channel_awal is not None:
                channel_awal.close()

        barrier = threading.Barrier(n_client + 1, timeout=30)
        lock_aggregate = threading.Lock()
        aggregate = {
            "latensi_ms": [],
            "rpc_selesai": 0,
            "rpc_error": 0,
            "siklus_berhasil": 0,
            "siklus_gagal": 0,
            "error": [],
        }

        def kerja(indeks):
            channel = None
            nama = f"load_{n_client}_{indeks}"
            kursi = daftar_kursi[indeks]
            lokal = {
                "latensi_ms": [],
                "rpc_selesai": 0,
                "rpc_error": 0,
                "siklus_berhasil": 0,
                "siklus_gagal": 0,
                "error": [],
            }
            sedang_dipesan = False

            def catat_panggilan(fungsi):
                mulai_rpc = time.perf_counter()
                try:
                    response = fungsi()
                    lokal["latensi_ms"].append((time.perf_counter() - mulai_rpc) * 1000)
                    lokal["rpc_selesai"] += 1
                    return response
                except grpc.RpcError as exc:
                    lokal["rpc_error"] += 1
                    lokal["error"].append(f"{nama}: {exc.code().name} - {exc.details()}")
                    raise

            try:
                channel, stub = buat_stub(alamat)
                stub.GetStatistik(pb.Kosong(), timeout=timeout_rpc)
                barrier.wait()

                jumlah_lokal = total_siklus // n_client
                if indeks < total_siklus % n_client:
                    jumlah_lokal += 1

                for _ in range(jumlah_lokal):
                    sedang_dipesan = False
                    request_id = str(uuid.uuid4())

                    try:
                        pesan = catat_panggilan(
                            lambda: stub.PesanKursi(
                                pb.PesanKursiRequest(
                                    request_id=request_id,
                                    kursi_id=kursi,
                                    pemesan=nama,
                                ),
                                timeout=timeout_rpc,
                            )
                        )
                        if not pesan.sukses:
                            lokal["siklus_gagal"] += 1
                            lokal["error"].append(f"{nama}: pemesanan ditolak: {pesan.pesan}")
                            continue

                        sedang_dipesan = True

                        denah = catat_panggilan(
                            lambda: stub.LihatKursi(pb.Kosong(), timeout=timeout_rpc)
                        )
                        detail = next(
                            (item for item in denah.kursi if item.kursi_id == kursi),
                            None,
                        )
                        if detail is None or detail.status != pb.TERPESAN or detail.pemesan != nama:
                            lokal["siklus_gagal"] += 1
                            lokal["error"].append(
                                f"{nama}: hasil LihatKursi tidak menunjukkan {kursi} milik {nama}"
                            )
                            continue

                        batal = catat_panggilan(
                            lambda: stub.BatalkanPesanan(
                                pb.BatalRequest(kursi_id=kursi, pemesan=nama),
                                timeout=timeout_rpc,
                            )
                        )
                        if not batal.sukses:
                            lokal["siklus_gagal"] += 1
                            lokal["error"].append(f"{nama}: pembatalan ditolak: {batal.pesan}")
                            continue

                        sedang_dipesan = False
                        lokal["siklus_berhasil"] += 1

                    except grpc.RpcError:
                        lokal["siklus_gagal"] += 1
                        break

            except threading.BrokenBarrierError:
                lokal["error"].append(f"{nama}: barrier gagal; worker tidak siap.")
            except grpc.RpcError as exc:
                lokal["rpc_error"] += 1
                lokal["error"].append(f"{nama}: persiapan koneksi gagal: {exc.code().name} - {exc.details()}")
                try:
                    barrier.abort()
                except Exception:
                    pass
            except Exception as exc:
                lokal["error"].append(f"{nama}: {type(exc).__name__}: {exc}")
                try:
                    barrier.abort()
                except Exception:
                    pass
            finally:
                if sedang_dipesan and channel is not None:
                    try:
                        denah_akhir = stub.LihatKursi(pb.Kosong(), timeout=5)
                        detail_akhir = next(
                            (item for item in denah_akhir.kursi if item.kursi_id == kursi),
                            None,
                        )
                        if detail_akhir and detail_akhir.pemesan == nama:
                            stub.BatalkanPesanan(
                                pb.BatalRequest(kursi_id=kursi, pemesan=nama),
                                timeout=5,
                            )
                    except grpc.RpcError as exc:
                        lokal["error"].append(
                            f"{nama}: pembersihan kursi gagal: {exc.code().name}"
                        )
                if channel is not None:
                    channel.close()
                with lock_aggregate:
                    aggregate["latensi_ms"].extend(lokal["latensi_ms"])
                    for key in ("rpc_selesai", "rpc_error", "siklus_berhasil", "siklus_gagal"):
                        aggregate[key] += lokal[key]
                    aggregate["error"].extend(lokal["error"])

        threads = [
            threading.Thread(target=kerja, args=(i,), name=f"load-client-{i + 1}")
            for i in range(n_client)
        ]
        for thread in threads:
            thread.start()

        mulai = time.perf_counter()
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            print(f"Peringatan: barrier skenario {n_client} client gagal.")

        for thread in threads:
            thread.join(timeout=max(30, timeout_rpc * 3 + 5))

        masih_aktif = [thread.name for thread in threads if thread.is_alive()]
        total_waktu = max(time.perf_counter() - mulai, 1e-9)
        latensi = aggregate["latensi_ms"]
        rata = statistics.mean(latensi) if latensi else 0.0
        p95 = _persentil95(latensi)
        throughput = aggregate["rpc_selesai"] / total_waktu
        total_rpc = aggregate["rpc_selesai"] + aggregate["rpc_error"]

        baris = {
            "client": n_client,
            "total_rpc": total_rpc,
            "rpc_selesai": aggregate["rpc_selesai"],
            "rpc_error": aggregate["rpc_error"],
            "siklus_berhasil": aggregate["siklus_berhasil"],
            "siklus_gagal": aggregate["siklus_gagal"],
            "waktu_s": round(total_waktu, 3),
            "throughput_rps": round(throughput, 2),
            "latensi_rata2_ms": round(rata, 2),
            "latensi_p95_ms": round(p95, 2),
        }
        hasil_skenario.append(baris)

        print(
            f"\nSkenario {n_client} client: "
            f"siklus berhasil={baris['siklus_berhasil']}, "
            f"siklus gagal={baris['siklus_gagal']}, "
            f"RPC selesai={baris['rpc_selesai']}, RPC error={baris['rpc_error']}"
        )
        if masih_aktif:
            print("  Peringatan thread belum selesai:", ", ".join(masih_aktif))
        for pesan_error in aggregate["error"][:5]:
            print("  Error:", pesan_error)

    if not hasil_skenario:
        print("Tidak ada skenario kinerja yang berhasil disiapkan.")
        return False

    print(
        f"\n{'client':>6} {'total RPC':>10} {'RPC selesai':>12} {'RPC error':>10} "
        f"{'siklus OK':>10} {'waktu(s)':>9} {'throughput':>12} {'rata2(ms)':>10} {'P95(ms)':>9}"
    )
    for baris in hasil_skenario:
        if "gagal_setup" in baris:
            continue
        print(
            f"{baris['client']:>6} {baris['total_rpc']:>10} "
            f"{baris['rpc_selesai']:>12} {baris['rpc_error']:>10} "
            f"{baris['siklus_berhasil']:>10} {baris['waktu_s']:>9.3f} "
            f"{baris['throughput_rps']:>12.2f} {baris['latensi_rata2_ms']:>10.2f} "
            f"{baris['latensi_p95_ms']:>9.2f}"
        )

    kolom = [
        "client", "total_rpc", "rpc_selesai", "rpc_error",
        "siklus_berhasil", "siklus_gagal", "waktu_s", "throughput_rps",
        "latensi_rata2_ms", "latensi_p95_ms",
    ]
    with open(keluaran, "w", newline="", encoding="utf-8") as file_csv:
        penulis = csv.DictWriter(file_csv, fieldnames=kolom)
        penulis.writeheader()
        for baris in hasil_skenario:
            if "gagal_setup" not in baris:
                penulis.writerow(baris)
    print(f"Tersimpan: {keluaran}")

    baris_valid = [b for b in hasil_skenario if "gagal_setup" not in b]
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        xs = [b["client"] for b in baris_valid]
        fig, ax = plt.subplots(1, 2, figsize=(10, 4))
        ax[0].plot(xs, [b["throughput_rps"] for b in baris_valid], marker="o")
        ax[0].set_title("Throughput")
        ax[0].set_xlabel("Jumlah client")
        ax[0].set_ylabel("RPC selesai / detik")
        ax[0].set_xticks(xs)

        ax[1].plot(xs, [b["latensi_rata2_ms"] for b in baris_valid], marker="o", label="Rata-rata")
        ax[1].plot(xs, [b["latensi_p95_ms"] for b in baris_valid], marker="s", label="P95")
        ax[1].set_title("Latensi")
        ax[1].set_xlabel("Jumlah client")
        ax[1].set_ylabel("Milidetik")
        ax[1].set_xticks(xs)
        ax[1].legend()
        fig.tight_layout()
        fig.savefig("grafik_kinerja.png", dpi=150)
        plt.close(fig)
        print("Tersimpan: grafik_kinerja.png")
    except ImportError:
        print("Matplotlib tidak terpasang; grafik dilewati. Jalankan: pip install matplotlib")

    return all(b.get("siklus_gagal", 0) == 0 for b in baris_valid)


def main():
    parser = argparse.ArgumentParser(description="Pengujian beban sistem reservasi bioskop gRPC")
    parser.add_argument("mode", choices=["race", "kinerja", "semua"])
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--client", type=int, default=20, help="jumlah client untuk mode race")
    parser.add_argument("--ronde", type=int, default=5, help="jumlah ronde untuk mode race")
    parser.add_argument("--siklus", type=int, default=200, help="total siklus per skenario kinerja")
    args = parser.parse_args()

    alamat = f"{args.host}:{args.port}"
    berhasil = True

    if args.mode in ("race", "semua"):
        berhasil = uji_race(alamat, n_client=args.client, ronde=args.ronde) and berhasil

    if args.mode in ("kinerja", "semua"):
        berhasil = uji_kinerja(alamat, total_siklus=args.siklus) and berhasil

    return 0 if berhasil else 1


if __name__ == "__main__":
    sys.exit(main())
