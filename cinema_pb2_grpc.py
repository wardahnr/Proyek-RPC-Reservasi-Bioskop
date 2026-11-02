"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings

import cinema_pb2 as cinema__pb2

GRPC_GENERATED_VERSION = '1.85.1'
GRPC_VERSION = grpc.__version__
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    raise RuntimeError(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + ' but the generated code in cinema_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
    )


class BioskopStub:
    """Layanan reservasi kursi bioskop (1 studio, 50 kursi: A1..E10)
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.LihatKursi = channel.unary_unary(
                '/cinema.Bioskop/LihatKursi',
                request_serializer=cinema__pb2.Kosong.SerializeToString,
                response_deserializer=cinema__pb2.DenahKursi.FromString,
                _registered_method=True)
        self.PesanKursi = channel.unary_unary(
                '/cinema.Bioskop/PesanKursi',
                request_serializer=cinema__pb2.PesanKursiRequest.SerializeToString,
                response_deserializer=cinema__pb2.StatusResponse.FromString,
                _registered_method=True)
        self.BatalkanPesanan = channel.unary_unary(
                '/cinema.Bioskop/BatalkanPesanan',
                request_serializer=cinema__pb2.BatalRequest.SerializeToString,
                response_deserializer=cinema__pb2.StatusResponse.FromString,
                _registered_method=True)
        self.StreamStatusKursi = channel.unary_stream(
                '/cinema.Bioskop/StreamStatusKursi',
                request_serializer=cinema__pb2.Kosong.SerializeToString,
                response_deserializer=cinema__pb2.PerubahanKursi.FromString,
                _registered_method=True)
        self.GetStatistik = channel.unary_unary(
                '/cinema.Bioskop/GetStatistik',
                request_serializer=cinema__pb2.Kosong.SerializeToString,
                response_deserializer=cinema__pb2.Statistik.FromString,
                _registered_method=True)


class BioskopServicer:
    """Layanan reservasi kursi bioskop (1 studio, 50 kursi: A1..E10)
    """

    def LihatKursi(self, request, context):
        """unary
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def PesanKursi(self, request, context):
        """unary, TIDAK idempoten -> request_id
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def BatalkanPesanan(self, request, context):
        """unary
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def StreamStatusKursi(self, request, context):
        """server streaming
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetStatistik(self, request, context):
        """unary, idempoten
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_BioskopServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'LihatKursi': grpc.unary_unary_rpc_method_handler(
                    servicer.LihatKursi,
                    request_deserializer=cinema__pb2.Kosong.FromString,
                    response_serializer=cinema__pb2.DenahKursi.SerializeToString,
            ),
            'PesanKursi': grpc.unary_unary_rpc_method_handler(
                    servicer.PesanKursi,
                    request_deserializer=cinema__pb2.PesanKursiRequest.FromString,
                    response_serializer=cinema__pb2.StatusResponse.SerializeToString,
            ),
            'BatalkanPesanan': grpc.unary_unary_rpc_method_handler(
                    servicer.BatalkanPesanan,
                    request_deserializer=cinema__pb2.BatalRequest.FromString,
                    response_serializer=cinema__pb2.StatusResponse.SerializeToString,
            ),
            'StreamStatusKursi': grpc.unary_stream_rpc_method_handler(
                    servicer.StreamStatusKursi,
                    request_deserializer=cinema__pb2.Kosong.FromString,
                    response_serializer=cinema__pb2.PerubahanKursi.SerializeToString,
            ),
            'GetStatistik': grpc.unary_unary_rpc_method_handler(
                    servicer.GetStatistik,
                    request_deserializer=cinema__pb2.Kosong.FromString,
                    response_serializer=cinema__pb2.Statistik.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'cinema.Bioskop', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('cinema.Bioskop', rpc_method_handlers)


class Bioskop:
    """Layanan reservasi kursi bioskop (1 studio, 50 kursi: A1..E10)
    """

    @staticmethod
    def LihatKursi(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/cinema.Bioskop/LihatKursi',
            cinema__pb2.Kosong.SerializeToString,
            cinema__pb2.DenahKursi.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def PesanKursi(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/cinema.Bioskop/PesanKursi',
            cinema__pb2.PesanKursiRequest.SerializeToString,
            cinema__pb2.StatusResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def BatalkanPesanan(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/cinema.Bioskop/BatalkanPesanan',
            cinema__pb2.BatalRequest.SerializeToString,
            cinema__pb2.StatusResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def StreamStatusKursi(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_stream(
            request,
            target,
            '/cinema.Bioskop/StreamStatusKursi',
            cinema__pb2.Kosong.SerializeToString,
            cinema__pb2.PerubahanKursi.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def GetStatistik(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/cinema.Bioskop/GetStatistik',
            cinema__pb2.Kosong.SerializeToString,
            cinema__pb2.Statistik.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
