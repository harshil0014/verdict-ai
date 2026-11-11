export function CaseNavigation({tab,evidenceCount,witnessCount,onSelect}: {
  tab:string;evidenceCount:number;witnessCount:number;onSelect:(tab:string)=>void;
}) {
  return <>{[['investigation','Investigation'],['evidence',`Evidence · ${evidenceCount}`],
    ['requests',`Witnesses · ${witnessCount}`],['timeline','Timeline'],['review','Findings']].map(([key,label])=>
    <button key={key} className={tab===key?'selected':''} aria-current={tab===key?'page':undefined} onClick={()=>onSelect(key)}>{label}</button>)}</>;
}
