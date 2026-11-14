from purrint import Family, all_models, get_model, identify, normalize_name


def test_catalog_size_and_families():
    models = all_models()
    assert len(models) == 107
    assert len(all_models(Family.V5G)) == 50
    assert len(all_models(Family.V5X)) == 57
    assert len({m.name for m in models}) == 107


def test_every_vendor_model_maps_to_a_family():
    for m in all_models():
        assert m.vendor_model in ("V5G", "V5X", "V5X_S")
        assert (m.family is Family.V5G) == (m.vendor_model == "V5G")


def test_identify_variants():
    assert identify("MX10").family is Family.V5G
    assert identify("mx10").name == "MX10"
    assert identify("CYLO BT PRINTER").name == "CYLOBTPRINTER"
    assert identify("XO POPPY").display_name == "XO POPPY"
    assert identify("MX10-8A3F").name == "MX10"
    assert identify("MXW01").family is Family.V5X
    assert identify("Instant Print Plus").vendor_model == "V5X_S"
    assert identify("Q15A").name == "Q15A"
    assert identify("BQ95B").name == "BQ95B"
    assert identify("Totally Unknown") is None
    assert identify("") is None


def test_manufacturer_data_switches_to_v5x():
    model = identify("MX10", {0x1234: bytes(7) + b"\x59"})
    assert model.family is Family.V5X and model.vendor_model == "V5X_S"
    assert identify("MX10", {0x1234: b"\x01\x02"}).family is Family.V5G


def test_density_profiles():
    mx06 = get_model("MX06")
    assert mx06.density.image.at(1) == 150 and mx06.density.image.at(7) == 200
    assert mx06.density.image.at(4) == 180
    assert get_model("PD01").density is get_model("MX11").density
    assert get_model("MX10").density is None


def test_normalize():
    assert normalize_name(" Mini  Printer ") == "MINIPRINTER"
