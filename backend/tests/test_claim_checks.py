"""Regression for a valid money-bearing quote with a different structured field."""
import copy
import pytest
from investigator import validate_sources
from structured import source_value_check,compare

QUOTE='Within 14 days of the date of this order, I order Air Canada to pay Mr. Moffatt a total of $812.02'


@pytest.mark.parametrize('field,value,expected',[
    ('refund_status','ordered_to_pay','value_not_found_in_quote'),
    ('amount','812.02','value_in_quote'),
    ('amount','$812.02','value_in_quote'),
    ('amount','CAD 812.02','value_not_found_in_quote'),
])
def test_literal_value_check_uses_the_selected_field_value_not_other_numbers(field,value,expected):
    assert source_value_check({'field':field,'value':value,'quote':QUOTE})==expected


def test_status_label_mismatch_does_not_discard_an_exact_quote_or_hypothesis_link():
    claim={'id':'C-003','source_id':'E-test','quote':QUOTE,'text':'The tribunal ordered a payment.',
        'subject':'airline','field':'refund_status','value':'ordered_to_pay','epistemic_status':'document_order'}
    data={'claims':[copy.deepcopy(claim)],'hypotheses':[{'id':'H1','supports':['C-003'],'challenges':[]}],'requests':[]}
    result=validate_sources(data,[{'id':'E-test','text':QUOTE}])
    assert result['rejected_claims']==[] and len(result['claims'])==1
    actual=result['claims'][0]
    assert actual['source_check']=='exact_quote_found'
    assert actual['structured_check']=='value_not_found_in_quote'
    assert result['hypotheses'][0]['supports']==['C-003']
    # Literal mismatch must not fabricate a deterministic status comparison.
    actual['semantic_support']='entailed'
    other={'id':'C-004','source_id':'E-other','subject':'airline','field':'refund_status',
        'value':'pending','quote':'Refund pending','semantic_support':'entailed'}
    assert compare([actual,other])==[]
