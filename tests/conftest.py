import time
import pytest
from spots import Spot

# Minimal cty.dat content covering W (NA), G (EU), JA (AS), VK (OC), PY (SA), ZS (AF)
MINIMAL_CTY = """\
United States:            05:  08:  NA:   43.00:    87.90:    -5.0:  K:
    K,W,AA,AB,AC,AD,AE,AF,AG,AI,AJ,AK,AL,AM,AN,WA,WB,WC,WD,WE,WF,WG,WH,WI,WJ,WK,WL,WM,WN,WO,WP,WQ,WR,WS,WT,WU,WV,WW,WX,WY,WZ,KA,KB,KC,KD,KE,KF,KG,KH,KI,KJ,KK,KL,KM,KN,KO,KP,KQ,KR,KS,KT,KU,KV,KW,KX,KY,KZ,NA,NB,NC,ND,NE,NF,NG,NH,NI,NJ,NK,NL,NM,NN,NO,NP,NQ,NR,NS,NT,NU,NV,NW,NX,NY,NZ;
England:                  14:  27:  EU:   52.77:     1.47:     0.0:  G:
    G,GD,GI,GJ,GM,GU,GW,2E,2I,2J,2M,2U,2W,M;
Japan:                    25:  45:  AS:   35.68:  -139.77:    -9.0:  JA:
    JA,JD,JE,JF,JG,JH,JI,JJ,JK,JL,JM,JN,JO,JP,JQ,JR,JS,7J,7K,7L,7M,7N,8J,8K,8L,8M,8N;
Australia:                29:  55:  OC:  -25.73:  -134.50:   -10.0:  VK:
    AX,VH,VI,VJ,VK,VL,VM,VN,VZ;
Brazil:                   11:  15:  SA:  -10.00:    53.00:    -3.0:  PY:
    PP,PQ,PR,PS,PT,PU,PV,PW,PX,PY,ZV,ZW,ZX,ZY,ZZ;
South Africa:             38:  57:  AF:  -29.10:   -26.00:    -2.0:  ZS:
    S8,ZR,ZS,ZT,ZU;
"""


@pytest.fixture
def minimal_cty(tmp_path):
    p = tmp_path / "cty.dat"
    p.write_text(MINIMAL_CTY, encoding="utf-8")
    return str(p)


def make_spot(**kwargs) -> Spot:
    defaults = dict(
        spotter="W1AW",
        dx="K1ABC",
        freq_khz=14025.0,
        mode="CW",
        snr_db=10,
        wpm=25,
        spot_type="CQ",
        time_utc="1234Z",
        timestamp=time.time(),
        band_m=20,
        spotter_continent="NA",
        dx_continent="NA",
        dx_entity="United States",
    )
    defaults.update(kwargs)
    return Spot(**defaults)
