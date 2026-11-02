# Reservasi Tiket Bioskop dengan gRPC (Studi Kasus 1)

Layanan reservasi kursi (1 studio, 50 kursi A1–E10) berbasis gRPC.
Fitur: pemesanan aman dari race condition (lock), deduplikasi `request_id`
(at-most-once), timeout + retry (exponential backoff), dan server streaming status kursi.

## 1. Instalasi
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Generate stub dari `cinema.proto`
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. cinema.proto
```
Menghasilkan `cinema_pb2.py` dan `cinema_pb2_grpc.py`.

## 3. Menjalankan
Terminal 1 (server):
```bash
python server.py
```
Terminal 2 (client CLI; di mesin lain ganti `localhost` dengan IP server via `--host`):
```bash
python client.py lihat
python client.py pesan A1 andi
python client.py pesan A1 budi        # gagal: sudah dipesan
python client.py batal A1 andi
python client.py statistik
python client.py pantau               # server streaming; buka di terminal ke-3 lalu pesan kursi
```

## 4. Daftar RPC
| RPC | Tipe | Keterangan |
|---|---|---|
| LihatKursi | Unary | Denah + status semua kursi |
| PesanKursi | Unary | Dilindungi lock + `request_id` |
| BatalkanPesanan | Unary | Hanya pemesan asli |
| StreamStatusKursi | Server streaming | Snapshot awal lalu setiap perubahan |
| GetStatistik | Unary | Total / terpesan / tersedia |

## 5. Pengujian (untuk laporan)
**a. Race condition (dengan lock)**
```bash
python server.py
python loadtest.py race          # 20 client rebutan 1 kursi, 5 ronde -> harus tepat 1 sukses
```
**b. Pembuktian race condition (tanpa lock) sebagai pembanding**
```bash
python server.py --tanpa-lock --jeda-kritis 20
python loadtest.py race          # kursi terjual ke banyak client -> GAGAL
```
**c. Kinerja 1 / 5 / 20 client** (menghasilkan `hasil_kinerja.csv` dan `grafik_kinerja.png`)
```bash
python server.py
python loadtest.py kinerja
```
**d. Timeout + retry + deduplikasi**
```bash
python server.py --lambat 1.0                      # balasan selalu terlambat 3 s setelah kursi terpesan
python client.py demo-retry C1 andi                # request_id tetap -> berhasil (dedup)
python client.py demo-retry C2 andi --id-baru      # request_id baru tiap retry -> salah: "sudah dipesan"
python client.py statistik
```
**e. Failure UNAVAILABLE**: matikan server saat client berjalan; client akan retry lalu error.

## 6. Demo di 2 mesin / 2 container
**Docker Compose** (server dan client = dua container):
```bash
docker compose up --build
```
**Dua laptop**: jalankan `python server.py` di laptop A, lalu di laptop B
`python loadtest.py semua --host <IP_LAPTOP_A>` (izinkan port 50051 di firewall).

## 7. Strategi
- **Concurrency**: satu `threading.Lock` melindungi seluruh bagian cek-lalu-set (check-then-act)
  agar atomik. Lock tunggal dipilih karena kritis-section sangat singkat dan datanya kecil.
- **Idempotensi**: `PesanKursi` tidak idempoten, maka dilindungi `request_id` (UUID dibuat
  sekali per niat pemesanan, dipakai ulang di semua retry). Server menyimpan hasil di `proses`.
- **Retry**: hanya untuk `DEADLINE_EXCEEDED` dan `UNAVAILABLE`, exponential backoff 0.5/1/2 s.
- **Keterbatasan**: `proses` ada di memori, sehingga hilang jika server restart
  (perbaikan: simpan ke SQLite/Redis, atau beri TTL).
