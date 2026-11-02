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


app.mount(
    "/",
    StaticFiles(directory=str(FRONTEND_DIR), html=True),
    name="frontend",
)
