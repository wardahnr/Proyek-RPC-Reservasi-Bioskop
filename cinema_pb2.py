"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    7,
    35,
    1,
    '',
    'cinema.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0c\x63inema.proto\x12\x06\x63inema\"\x08\n\x06Kosong\"O\n\x05Kursi\x12\x10\n\x08kursi_id\x18\x01 \x01(\t\x12#\n\x06status\x18\x02 \x01(\x0e\x32\x13.cinema.StatusKursi\x12\x0f\n\x07pemesan\x18\x03 \x01(\t\"*\n\nDenahKursi\x12\x1c\n\x05kursi\x18\x01 \x03(\x0b\x32\r.cinema.Kursi\"J\n\x11PesanKursiRequest\x12\x12\n\nrequest_id\x18\x01 \x01(\t\x12\x10\n\x08kursi_id\x18\x02 \x01(\t\x12\x0f\n\x07pemesan\x18\x03 \x01(\t\"1\n\x0c\x42\x61talRequest\x12\x10\n\x08kursi_id\x18\x01 \x01(\t\x12\x0f\n\x07pemesan\x18\x02 \x01(\t\"/\n\x0eStatusResponse\x12\x0e\n\x06sukses\x18\x01 \x01(\x08\x12\r\n\x05pesan\x18\x02 \x01(\t\"j\n\x0ePerubahanKursi\x12\x10\n\x08kursi_id\x18\x01 \x01(\t\x12#\n\x06status\x18\x02 \x01(\x0e\x32\x13.cinema.StatusKursi\x12\x0f\n\x07pemesan\x18\x03 \x01(\t\x12\x10\n\x08waktu_ms\x18\x04 \x01(\x03\">\n\tStatistik\x12\r\n\x05total\x18\x01 \x01(\x05\x12\x10\n\x08terpesan\x18\x02 \x01(\x05\x12\x10\n\x08tersedia\x18\x03 \x01(\x05*)\n\x0bStatusKursi\x12\x0c\n\x08TERSEDIA\x10\x00\x12\x0c\n\x08TERPESAN\x10\x01\x32\xaf\x02\n\x07\x42ioskop\x12\x30\n\nLihatKursi\x12\x0e.cinema.Kosong\x1a\x12.cinema.DenahKursi\x12?\n\nPesanKursi\x12\x19.cinema.PesanKursiRequest\x1a\x16.cinema.StatusResponse\x12?\n\x0f\x42\x61talkanPesanan\x12\x14.cinema.BatalRequest\x1a\x16.cinema.StatusResponse\x12=\n\x11StreamStatusKursi\x12\x0e.cinema.Kosong\x1a\x16.cinema.PerubahanKursi0\x01\x12\x31\n\x0cGetStatistik\x12\x0e.cinema.Kosong\x1a\x11.cinema.Statistikb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'cinema_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_STATUSKURSI']._serialized_start=507
  _globals['_STATUSKURSI']._serialized_end=548
  _globals['_KOSONG']._serialized_start=24
  _globals['_KOSONG']._serialized_end=32
  _globals['_KURSI']._serialized_start=34
  _globals['_KURSI']._serialized_end=113
  _globals['_DENAHKURSI']._serialized_start=115
  _globals['_DENAHKURSI']._serialized_end=157
  _globals['_PESANKURSIREQUEST']._serialized_start=159
  _globals['_PESANKURSIREQUEST']._serialized_end=233
  _globals['_BATALREQUEST']._serialized_start=235
  _globals['_BATALREQUEST']._serialized_end=284
  _globals['_STATUSRESPONSE']._serialized_start=286
  _globals['_STATUSRESPONSE']._serialized_end=333
  _globals['_PERUBAHANKURSI']._serialized_start=335
  _globals['_PERUBAHANKURSI']._serialized_end=441
  _globals['_STATISTIK']._serialized_start=443
  _globals['_STATISTIK']._serialized_end=505
  _globals['_BIOSKOP']._serialized_start=551
  _globals['_BIOSKOP']._serialized_end=854
# @@protoc_insertion_point(module_scope)
