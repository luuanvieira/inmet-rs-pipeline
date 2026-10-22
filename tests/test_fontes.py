import zipfile
from pathlib import Path

from inmet_pipeline.fontes import csvs_da_pasta, csvs_do_zip

FIXTURES = Path(__file__).parent / "fixtures"


def test_pasta_filtra_pela_uf():
    nomes = [nome for nome, _ in csvs_da_pasta(FIXTURES, "RS")]
    assert len(nomes) == 2
    assert all("_RS_" in n for n in nomes)


def test_zip_filtra_pela_uf_e_ignora_subpastas(tmp_path):
    caminho = tmp_path / "2024.zip"
    with zipfile.ZipFile(caminho, "w") as zf:
        for csv in FIXTURES.glob("*.CSV"):
            zf.write(csv, arcname=f"2024/{csv.name}")
        zf.writestr("2024/LEIAME.txt", "nao e csv")

    encontrados = dict(csvs_do_zip(caminho, "RS"))
    assert len(encontrados) == 2
    assert all(nome.startswith("2024.zip/INMET_S_RS_") for nome in encontrados)
    assert all(conteudo.startswith(b"REGIAO") for conteudo in encontrados.values())
