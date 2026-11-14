from PIL import Image

from purrint.cli import main


def test_models_command(capsys):
    assert main(["models"]) == 0
    out = capsys.readouterr().out
    assert "MX10" in out and "MXW01" in out and "107 models" in out


def test_text_simulated(tmp_path):
    out = tmp_path / "page.png"
    assert main(["text", "Hola\\nmundo", "--simulate", str(out), "--align", "center"]) == 0
    img = Image.open(out)
    assert img.width > 384


def test_image_simulated(tmp_path):
    src = tmp_path / "in.png"
    Image.linear_gradient("L").resize((640, 360)).save(src)
    out = tmp_path / "page.png"
    assert main(["image", str(src), "--simulate", str(out), "--dither", "atkinson", "--cooldown", "0"]) == 0
    assert Image.open(out).height > 600  # landscape was rotated to use paper length


def test_info_simulated(capsys):
    assert main(["info", "--simulate", "x.png", "--model", "MXW01"]) == 0
    out = capsys.readouterr().out
    assert "V5X" in out and "high_voltage" in out
