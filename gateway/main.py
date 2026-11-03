import json
import os
import queue
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Iterator

import grpc
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import cinema_pb2 as pb
import cinema_pb2_grpc as pb_grpc
from client import batal, dengan_retry, lihat_kursi, statistik, validasi_input

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
GRPC_HOST = os.getenv("GRPC_HOST", "localhost")
GRPC_PORT = os.getenv("GRPC_PORT", "50051")
GRPC_TARGET = f"{GRPC_HOST}:{GRPC_PORT}"
RPC_TIMEOUT = 2.0
HEARTBEAT_SECONDS = 15


class ReservasiRequest(BaseModel):
    kursi_id: str
    pemesan: str

class SimulasiRequest(BaseModel):
    jumlah_client: int = 20
    kursi_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    channel = grpc.insecure_channel(GRPC_TARGET)
    app.state.grpc_channel = channel
    app.state.grpc_stub = pb_grpc.BioskopStub(channel)
    try:
        yield
    finally:
        channel.close()


app = FastAPI(title="Gateway Reservasi Bioskop", lifespan=lifespan)
SIMULATION_LOCK = threading.Lock()
app.state.last_simulation_bookings = []


def _stub():
    return app.state.grpc_stub


def _status_code(error: grpc.RpcError) -> grpc.StatusCode:
    return error.code()


def _http_error(error: grpc.RpcError) -> HTTPException:
    code = _status_code(error)
    mapped = {
        grpc.StatusCode.UNAVAILABLE: (503, "Server tidak dapat dihubungi"),
        grpc.StatusCode.DEADLINE_EXCEEDED: (
            504,
            "Permintaan melewati batas waktu. Silakan coba lagi.",
        ),
        grpc.StatusCode.INVALID_ARGUMENT: (400, "Data yang dikirim tidak valid"),
        grpc.StatusCode.NOT_FOUND: (404, "Kursi tidak ditemukan"),
    }
    status, message = mapped.get(
        code,
        (502, "Terjadi kesalahan saat berkomunikasi dengan server bioskop"),
    )
    return HTTPException(status_code=status, detail=message)


def _validate(kursi_id: str, pemesan: str) -> tuple[str, str]:
    try:
        return validasi_input(kursi_id, pemesan)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _seat_status(status: int) -> str:
    return "TERPESAN" if status == pb.TERPESAN else "TERSEDIA"


def _seat_data(seat: Any) -> dict[str, str]:
    return {
        "kursi_id": seat.kursi_id,
        "status": _seat_status(seat.status),
        "pemesan": seat.pemesan,
    }


@app.get("/api/kursi")
async def get_kursi():
    try:
        denah = await run_in_threadpool(lihat_kursi, _stub())
        return [_seat_data(seat) for seat in denah.kursi]
    except grpc.RpcError as error:
        raise _http_error(error) from error


@app.post("/api/pesan")
async def pesan_kursi(request: ReservasiRequest):
    kursi_id, pemesan = _validate(request.kursi_id, request.pemesan)
    request_id = str(uuid.uuid4())

    def panggil_rpc():
        return dengan_retry(
            lambda _attempt: _stub().PesanKursi(
                pb.PesanKursiRequest(
                    request_id=request_id,
                    kursi_id=kursi_id,
                    pemesan=pemesan,
                ),
                timeout=RPC_TIMEOUT,
            ),
            log=False,
        )

    try:
        response = await run_in_threadpool(panggil_rpc)
        return {"sukses": response.sukses, "pesan": response.pesan}
    except grpc.RpcError as error:
        raise _http_error(error) from error


@app.post("/api/batal")
async def batalkan_pesanan(request: ReservasiRequest):
    kursi_id, pemesan = _validate(request.kursi_id, request.pemesan)
    try:
        response = await run_in_threadpool(batal, _stub(), kursi_id, pemesan)
        return {"sukses": response.sukses, "pesan": response.pesan}
    except grpc.RpcError as error:
        raise _http_error(error) from error


@app.get("/api/statistik")
async def get_statistik():
    try:
        result = await run_in_threadpool(statistik, _stub())
        return {
            "total": result.total,
            "terpesan": result.terpesan,
            "tersedia": result.tersedia,
        }
    except grpc.RpcError as error:
        raise _http_error(error) from error


def _stream_events(stub) -> Iterator[str]:
    events: queue.Queue[tuple[str, Any]] = queue.Queue()
    stopped = threading.Event()
    stream = stub.StreamStatusKursi(pb.Kosong())

    def read_stream():
        try:
            for index, change in enumerate(stream):
                if stopped.is_set():
                    break
                events.put(
                    (
                        "change",
                        {
                            "kursi_id": change.kursi_id,
                            "status": _seat_status(change.status),
                            "pemesan": change.pemesan,
                            "waktu_ms": change.waktu_ms,
                            "snapshot": index < 50,
                        },
                    )
                )
        except grpc.RpcError as error:
            events.put(("stream_error", _http_error(error).detail))
        finally:
            events.put(("finished", None))

    worker = threading.Thread(target=read_stream, daemon=True)
    worker.start()
    try:
        while True:
            try:
                event_type, payload = events.get(timeout=HEARTBEAT_SECONDS)
            except queue.Empty:
                yield ": heartbeat\n\n"
                continue
            if event_type == "change":
                data = json.dumps(payload, ensure_ascii=False)
                yield f"data: {data}\n\n"
            elif event_type == "stream_error":
                data = json.dumps({"pesan": payload}, ensure_ascii=False)
                yield f"event: stream_error\ndata: {data}\n\n"
            elif event_type == "finished":
                return
    finally:
        stopped.set()
        stream.cancel()


@app.get("/api/stream")
async def stream_status_kursi():
    return StreamingResponse(
        _stream_events(_stub()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health():
    try:
        await run_in_threadpool(
            _stub().GetStatistik,
            pb.Kosong(),
            timeout=1.5,
        )
        return {"status": "ok", "pesan": "Terhubung ke server bioskop"}
    except grpc.RpcError as error:
        raise _http_error(error) from error

def _run_race_simulation(
    jumlah_client: int,
    kursi_pilihan: str,
) -> dict[str, Any]:
    
    # Gunakan kursi yang dipilih pengguna.
    denah = _stub().LihatKursi(pb.Kosong(), timeout=5)

    kursi = next(
        (
            seat for seat in denah.kursi
            if seat.kursi_id == kursi_pilihan
        ),
        None,
    )

    if kursi is None:
        raise HTTPException(
            status_code=404,
            detail="Kursi yang dipilih tidak ditemukan.",
        )

    if kursi.status != pb.TERSEDIA:
        raise HTTPException(
            status_code=409,
            detail="Kursi yang dipilih sudah dipesan. Pilih kursi lain.",
        )

    kursi_id = kursi.kursi_id

    # Semua client menunggu di barrier sebelum mengirim RPC.
    barrier = threading.Barrier(jumlah_client + 1, timeout=15)
    hasil = []
    hasil_lock = threading.Lock()

    def worker(index: int):
        channel = None
        nama = f"Simulasi-{uuid.uuid4().hex[:8]}-{index + 1}"

        item = {
            "nomor": index + 1,
            "client": f"Client {index + 1}",
            "pemesan": nama,
            "status": "ERROR",
            "pesan": "Client belum menyelesaikan permintaan.",
        }

        try:
            channel = grpc.insecure_channel(GRPC_TARGET)
            stub = pb_grpc.BioskopStub(channel)

            # Pastikan koneksi setiap client siap.
            stub.GetStatistik(pb.Kosong(), timeout=5)

            # Semua client mulai mengirim permintaan setelah siap.
            barrier.wait(timeout=15)

            response = stub.PesanKursi(
                pb.PesanKursiRequest(
                    request_id=str(uuid.uuid4()),
                    kursi_id=kursi_id,
                    pemesan=nama,
                ),
                timeout=10,
            )

            item["status"] = (
                "BERHASIL" if response.sukses else "DITOLAK"
            )
            item["pesan"] = response.pesan

        except threading.BrokenBarrierError:
            item["status"] = "ERROR"
            item["pesan"] = "Client gagal mencapai waktu mulai bersama."

        except grpc.RpcError as error:
            item["status"] = "ERROR"
            item["pesan"] = (
                f"{error.code().name}: {error.details()}"
            )

        except Exception as error:
            item["status"] = "ERROR"
            item["pesan"] = str(error)

        finally:
            if channel is not None:
                channel.close()

            with hasil_lock:
                hasil.append(item)

    # Membuat client sebanyak jumlah yang dipilih.
    threads = [
        threading.Thread(target=worker, args=(i,))
        for i in range(jumlah_client)
    ]

    for thread in threads:
        thread.start()

    # Thread utama ikut menunggu agar seluruh client mulai bersama.
    try:
        barrier.wait(timeout=15)
    except threading.BrokenBarrierError:
        pass

    batas_waktu = time.monotonic() + 12

    for thread in threads:
        sisa_waktu = max(0, batas_waktu - time.monotonic())
        thread.join(timeout=sisa_waktu)

    masih_aktif = [
        thread.name for thread in threads if thread.is_alive()
    ]

    hasil.sort(key=lambda item: item["nomor"])

    pemenang = [
        item for item in hasil
        if item["status"] == "BERHASIL"
    ]

    ditolak = sum(
        1 for item in hasil
        if item["status"] == "DITOLAK"
    )

    jumlah_error = sum(
        1 for item in hasil
        if item["status"] == "ERROR"
    ) + len(masih_aktif)

    lulus = (
        len(hasil) == jumlah_client
        and len(pemenang) == 1
        and jumlah_error == 0
    )

    # Simpan pemilik kursi hasil simulasi untuk proses pembersihan.
    app.state.last_simulation_bookings = [
        {
            "kursi_id": kursi_id,
            "pemesan": item["pemesan"],
        }
        for item in pemenang
    ]

    if lulus:
        pesan = "LULUS: tepat satu client berhasil memesan kursi."
    else:
        pesan = (
            "SIMULASI PERLU DIPERIKSA: hasil tidak memenuhi "
            "kriteria tepat satu pemenang tanpa error."
        )

    return {
        "sukses": lulus,
        "kursi_id": kursi_id,
        "jumlah_client": jumlah_client,
        "berhasil": len(pemenang),
        "ditolak": ditolak,
        "error": jumlah_error,
        "pemenang": pemenang[0]["client"] if pemenang else None,
        "dapat_dibersihkan": bool(pemenang),
        "pesan": pesan,
        "detail": [
            {
                "client": item["client"],
                "status": item["status"],
                "pesan": item["pesan"],
            }
            for item in hasil
        ],
    }


def _clear_simulation_booking():
    bookings = app.state.last_simulation_bookings

    if not bookings:
        raise HTTPException(
            status_code=400,
            detail="Tidak ada kursi hasil simulasi yang perlu dibersihkan.",
        )

    denah = _stub().LihatKursi(pb.Kosong(), timeout=5)

    # Cari hanya kursi yang masih dimiliki client simulasi.
    for booking in bookings:
        seat = next(
            (
                item for item in denah.kursi
                if item.kursi_id == booking["kursi_id"]
            ),
            None,
        )

        if (
            seat is not None
            and seat.status == pb.TERPESAN
            and seat.pemesan == booking["pemesan"]
        ):
            response = batal(
                _stub(),
                booking["kursi_id"],
                booking["pemesan"],
            )

            if response.sukses:
                app.state.last_simulation_bookings = [
                    item for item in bookings
                    if item != booking
                ]

            return {
                "sukses": response.sukses,
                "pesan": response.pesan,
            }

    app.state.last_simulation_bookings = []

    raise HTTPException(
        status_code=409,
        detail=(
            "Kursi simulasi sudah berubah atau tidak lagi dimiliki "
            "oleh client simulasi. Tidak ada pesanan lain yang dibatalkan."
        ),
    )


@app.post("/api/simulasi/race")
async def simulasi_race(request: SimulasiRequest):
    if request.jumlah_client not in (5, 10, 20):
        raise HTTPException(
            status_code=400,
            detail="Jumlah client yang tersedia hanya 5, 10, atau 20.",
        )

    if not SIMULATION_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Simulasi lain sedang berjalan. Silakan tunggu.",
        )

    try:
        return await run_in_threadpool(
            _run_race_simulation,
            request.jumlah_client,
            request.kursi_id,
        )
    finally:
        SIMULATION_LOCK.release()


@app.post("/api/simulasi/bersihkan")
async def bersihkan_simulasi():
    if not SIMULATION_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="Simulasi lain sedang berjalan. Silakan tunggu.",
        )

    try:
        return await run_in_threadpool(_clear_simulation_booking)
    finally:
        SIMULATION_LOCK.release()

app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="frontend",
)
