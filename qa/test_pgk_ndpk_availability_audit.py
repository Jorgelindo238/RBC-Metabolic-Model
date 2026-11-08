from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_pgk_ndpk_availability import rate_explanation
from reaction_positivity import limit_signed_fluxes


def test_availability_explains_atp_production_as_well_as_consumption():
    names=["ATP","ADP","B13PG","PEP","GDP","GTP"]
    reactions=["VPGK","VPK","VNDPK"]
    matrix=np.array([[1,1,-1],[-1,-1,1],[-1,0,0],[0,-1,0],[0,0,-1],[0,0,1.]])
    x=np.array([.0001,.000002,1.,1.,1.,1.])
    raw=np.array([1.,1.,1.])
    executed,_=limit_signed_fluxes(x,raw,matrix,threshold=.001)
    result=rate_explanation(x,raw,executed,matrix,names,reactions,.001)
    assert [r["availability_factor"] for r in result]==pytest.approx([.002,.002,.1])
    assert [r["limiting_pools"] for r in result]==[["ADP"],["ADP"],["ATP"]]
    with pytest.raises(ValueError,match="not explained"):
        rate_explanation(x,raw,raw,matrix,names,reactions,.001)


def test_reverse_ndpk_is_limited_by_adp_not_atp():
    names=["ATP","ADP","B13PG","PEP","GDP","GTP"]
    reactions=["VPGK","VPK","VNDPK"]
    matrix=np.array([[1,1,-1],[-1,-1,1],[-1,0,0],[0,-1,0],[0,0,-1],[0,0,1.]])
    x=np.array([1.,.000002,1.,1.,1.,1.])
    raw=np.array([0.,0.,-1.])
    executed,_=limit_signed_fluxes(x,raw,matrix,threshold=.001)
    r=rate_explanation(x,raw,executed,matrix,names,reactions,.001)[2]
    assert r["availability_factor"]==pytest.approx(.002) and r["limiting_pools"]==["ADP"]
