DB_PATH = "pro_portfoy.db"

TEFAS_URL = "https://www.tefas.gov.tr/api/FonGetir/GetirFonBilgileri"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx",
}

YF_ALIASES = {
    "USD": "TRY=X",
    "EUR": "EURTRY=X",
    "GBP": "GBPTRY=X",
    "ONS": "GC=F",
    "XAUUSD": "GC=F",
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "BIST100": "XU100.IS",
}

GRAM_ALTIN_ALIASES = {"GRAM", "GRAM ALTIN", "ALTIN", "XAU", "GAU"}
