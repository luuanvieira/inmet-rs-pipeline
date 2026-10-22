import functools
import http.server
import threading
import zipfile
from pathlib import Path

from inmet_pipeline.download import baixar_ano, zip_valido


class _Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _servidor(pasta: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(_Silencioso, directory=str(pasta))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_baixa_e_nao_baixa_de_novo(tmp_path):
    origem, destino = tmp_path / "origem", tmp_path / "destino"
    origem.mkdir()
    with zipfile.ZipFile(origem / "2024.zip", "w") as zf:
        zf.writestr("INMET_S_RS_A801_TESTE.CSV", "REGIAO:;S\n")

    srv, url = _servidor(origem)
    try:
        caminho = baixar_ano(2024, url, destino)
        assert zip_valido(caminho)
        modificado_em = caminho.stat().st_mtime_ns

        (origem / "2024.zip").unlink()  # se tentasse baixar de novo, daria 404
        assert baixar_ano(2024, url, destino).stat().st_mtime_ns == modificado_em
    finally:
        srv.shutdown()


def test_arquivo_corrompido_nao_fica_no_destino(tmp_path):
    origem, destino = tmp_path / "origem", tmp_path / "destino"
    origem.mkdir()
    (origem / "2023.zip").write_text("pagina de erro, nao e zip")

    srv, url = _servidor(origem)
    try:
        try:
            baixar_ano(2023, url, destino)
        except RuntimeError:
            pass
        else:
            raise AssertionError("deveria ter falhado")
        assert list(destino.iterdir()) == []  # nem o .zip nem o .part
    finally:
        srv.shutdown()
