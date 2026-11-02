import grpc
import cinema_pb2 as pb
import cinema_pb2_grpc as pb_grpc

with grpc.insecure_channel("localhost:50051") as channel:
    stub = pb_grpc.BioskopStub(channel)

    request_id = "uji-request-001"

    # Percobaan 1: permintaan pertama
    req1 = pb.PesanKursiRequest(
        request_id=request_id,
        kursi_id="E10",
        pemesan="Wardah"
    )

    r1 = stub.PesanKursi(req1, timeout=5)
    print("Percobaan 1:", r1.sukses, "-", r1.pesan)

    # Percobaan 2: ID dan isi permintaan sama
    r2 = stub.PesanKursi(req1, timeout=5)
    print("Percobaan 2:", r2.sukses, "-", r2.pesan)

    # Percobaan 3: ID sama, tetapi isi berbeda
    req3 = pb.PesanKursiRequest(
        request_id=request_id,
        kursi_id="B1",
        pemesan="Budi"
    )

    try:
        r3 = stub.PesanKursi(req3, timeout=5)
        print("Percobaan 3:", r3.sukses, "-", r3.pesan)
    except grpc.RpcError as e:
        print(
            "Percobaan 3 ditolak:",
            e.code().name,
            "-",
            e.details()
        )

    # Kembalikan kursi E10 menjadi tersedia
    batal = stub.BatalkanPesanan(
        pb.BatalRequest(kursi_id="E10", pemesan="Wardah"),
        timeout=5
    )
    print("Pembatalan E10:", batal.pesan)

