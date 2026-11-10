import copy
import pytest
from investigator import validate_sources
from assessment_quality import deduplicate,finalize
from evidence_acquisition import prepare_requests,prior_request,reconcile_requests

def claim(id='C1',source='E1',text='The buyer reports non-receipt.',quote='I did not receive it.',**kw):
    return dict(id=id,source_id=source,text=text,quote=quote,subject='parcel',field='receipt_status',value='',stance='buyer',epistemic_status='party_report',semantic_support='entailed',**kw)

def test_repeated_paragraph_and_addresses_disguised_as_money_fail_before_semantic_review():
    text='I did not receive the parcel. '+('This repeats an entire statement rather than one fact. '*7)
    source={'id':'E1','text':text+' Address: Flat 4, Example House'}
    bad=claim(text=text,quote='I did not receive the parcel.')
    wrong=claim(id='C2',text='The record names Example House.',quote='Flat 4, Example House');wrong.update(field='amount',value='Flat 4, Example House')
    result=validate_sources({'claims':[bad,wrong],'hypotheses':[{'id':'H1','supports':['C1','C2'],'challenges':[]}],'requests':[]},[source])
    assert result['claims']==[] and len(result['rejected_claims'])==2 and result['hypotheses'][0]['supports']==[]

def test_duplicate_fact_keeps_independent_citations_and_remaps_every_graph_reference():
    a=claim();b=claim('C2','E2');c=claim('C3',text='The buyer reports another destination.',quote='My destination is Example House.')
    result={'claims':[a,b,c],'hypotheses':[{'supports':['C1','C2','C3'],'challenges':['C2']}],'duplicate_claims':[]}
    deduplicate(result)
    assert len(result['claims'])==2 and result['claims'][0]['additional_citations'][0]['source_id']=='E2'
    assert result['hypotheses'][0]=={'supports':['C1','C3'],'challenges':['C1']}
    assert len(result['duplicate_claims'])==1

def test_distinct_facts_in_the_same_quoted_paragraph_are_not_deduplicated():
    quote='I did not receive it. My address is Example House.'
    a=claim(quote=quote);b=claim('C2',quote=quote,text='The buyer names Example House.');b.update(field='destination_address',value='Example House')
    result={'claims':[a,b],'hypotheses':[]};deduplicate(result)
    assert len(result['claims'])==2

def test_freeform_narrative_never_promotes_uploaded_delivery_confirmation_to_carrier_proof():
    c=claim(text='The document lists delivery to Example House.');c.update(stance='seller',field='destination_address')
    result={'claims':[c],'summary':'Tracking proves successful delivery. The buyer must accept delivery.','recommendation':'Accept delivery.','finding':'supports_seller'}
    finalize(result,{'reason':'ITEM_NOT_RECEIVED','evidence':[{'id':'E1','party':'seller','origin':'portal_upload','origin_verified':False}]})
    assert result['finding']=='insufficient' and result['summary'].startswith('Seller’s submitted record:')
    assert 'Tracking proves' not in result['summary'] and 'Accept delivery' not in result['recommendation']
    assert result['proposed_narrative']['recommendation']=='Accept delivery.'

def request(question='Please provide the original order shipping address.',**kw):
    return dict(id='W1',title='Original checkout address',question=question,recipient='payment_provider',rationale='Identify the original destination.',priority='first',**kw)

@pytest.mark.parametrize('status,state',[('received','response_received'),('unavailable','reported_unavailable'),('open','link_ready'),('withdrawn','withdrawn')])
def test_rewording_a_request_does_not_erase_its_existing_outcome(status,state):
    old={**request(),'id':'R1','status':status};case={'requests':[old]};before=copy.deepcopy(case)
    suggestion=request('Please supply the raw unedited address from the original checkout session.')
    result={'requests':[suggestion]};plan=prepare_requests(result,case)
    assert plan[0]['state']==state and plan[0]['request_id']=='R1' and case==before
    assert 'Please supply' not in result['recommendation']

def test_received_reply_reporting_unavailability_is_not_requested_again():
    prior={**request(),'id':'R1','status':'received','evidence_id':'E1'}
    case={'requests':[prior],'evidence':[{'id':'E1','text':'I do not have access to the original checkout address.','title':'Original record unavailable'}]}
    result={'requests':[request('Supply the original shipping address captured at purchase.')]}
    assert prepare_requests(result,case)[0]['state']=='reported_unavailable'

def test_specific_carrier_followup_is_distinct_from_repeating_seller_confirmation():
    old={'id':'R1','title':'Proof of delivery','question':'Provide proof of delivery.','recipient':'seller','status':'received'}
    case={'requests':[old]}
    carrier=request('Please supply the carrier’s own delivery scan.');carrier.update(title='Carrier verification',recipient='carrier')
    assert prior_request(carrier,case) is None
    follow={**old,'id':'W2','question':'Supply the carrier-issued signed original.','follow_up_to':'R1','unresolved_defect':'The submitted seller confirmation contains no carrier-issued scan.'}
    assert prior_request(follow,case) is None
    old['status']='unavailable'
    follow['title']='Proof of delivery'
    assert prior_request(follow,case)['id']=='R1'

def test_different_explicit_orders_do_not_share_completion():
    case={'requests':[{**request('Original shipping address for order ORDER123.'),'id':'R1','status':'received'}]}
    assert prior_request(request('Original shipping address for order ORDER456.'),case) is None

def test_upload_without_a_request_is_recognized_as_already_supplied():
    suggestion={'id':'W1','title':'Proof of delivery','question':'Provide proof of delivery.','recipient':'seller','rationale':'Review the recorded destination.','priority':'first'}
    result={'requests':[suggestion]}
    plan=prepare_requests(result,{'requests':[],'evidence':[{'id':'E1','title':'Delivery Confirmation.png','party':'seller'}]})
    assert plan[0]['state']=='evidence_received' and plan[0]['source_id']=='E1'

def test_addressed_suggestions_stay_in_diagnostics_not_as_new_requests():
    suggestion=request();result={'requests':[suggestion]}
    reconcile_requests(result,{'requests':[{**suggestion,'id':'R1','status':'received'}]})
    assert result['requests']==[] and result['proposed_requests']==[suggestion]
    assert result['acquisition_plan'][0]['state']=='response_received'
