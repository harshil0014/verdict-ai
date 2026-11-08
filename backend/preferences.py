"""Account-level explicit map sharing; existing per-case choices remain overrides."""
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field
from domain import StrictModel
import saas_auth as auth
from saas_store import repo

class MapPreference(StrictModel):
    mode:str=Field(pattern='^(off|area_only|address)$')
    acknowledged:bool=False

router=APIRouter()
@router.get('/api/preferences')
async def preferences(user=Depends(auth.current_session)):
    return await repo.rpc('experience:preferences')

@router.post('/api/preferences/maps')
async def save_maps(data:MapPreference,user=Depends(auth.current_session)):
    if data.mode!='off' and not data.acknowledged:raise HTTPException(422,'Please confirm you are authorized to share these addresses with the map service.')
    result=await repo.rpc('experience:set_maps',{'mode':data.mode})
    from automatic_investigation import WAKE
    WAKE.set()
    return result
