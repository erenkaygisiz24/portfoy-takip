from providers import classify_asset_type, yf_symbol


def test_asset_type():
    assert classify_asset_type("Fon") == "Fon"
    assert classify_asset_type("Hisse Senedi") == "Hisse Senedi"
    assert classify_asset_type("Döviz") == "Döviz"


def test_yf_symbol():
    assert yf_symbol("THYAO", "Hisse Senedi") == "THYAO.IS"
    assert yf_symbol("USD", "Döviz") == "TRY=X"
