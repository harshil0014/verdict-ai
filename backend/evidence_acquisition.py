"""Prepare useful evidence requests with the analysis, without contacting anyone."""
from store import digest,now


def prepare_requests(result,case):
    plan=[]
    for suggestion in result.get('requests',[]):
        existing=next((r for r in reversed(case.get('requests',[]))
            if r.get('recipient')==suggestion['recipient'] and r.get('question','').strip()==suggestion['question'].strip()),None)
        state={'open':'link_ready','received':'response_received','unavailable':'reported_unavailable','withdrawn':'withdrawn'}.get((existing or {}).get('status'),'prepared')
        plan.append({'id':'A-'+digest({'question':suggestion['question'],'recipient':suggestion['recipient']})[:16],
            'suggestion_id':suggestion['id'],'state':state,'prepared_at':now(),
            'title':suggestion['title'],'question':suggestion['question'],'recipient':suggestion['recipient'],
            'rationale':suggestion['rationale'],'priority':suggestion['priority'],
            'request_id':existing['id'] if existing else None,
            'contact_authorization':'A private response link can be created by the authorized owner. No external contact or disclosure is performed by preparation.',
            'message_sent_by_verdict':False,'input_digest':result.get('input_digest')})
    return plan
