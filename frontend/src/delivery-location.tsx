import React from 'react';
import type {Map as LeafletMapType} from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './delivery-location.css';

type API=(path:string,method?:string,body?:any)=>Promise<any>;
const labels:any={off:'Local comparison only',area_only:'PIN-code area lookup',address:'Address lookup (unit details omitted)'};

export function DeliveryMap({mentions}:{mentions:any[]}){
 const ref=React.useRef<HTMLDivElement>(null),[failed,setFailed]=React.useState(false);
 React.useEffect(()=>{let disposed=false,map:LeafletMapType|undefined;
  (async()=>{try{const L=await import('leaflet');if(disposed||!ref.current)return;
   const points=mentions.filter(m=>m.geocode?.status==='resolved'&&Number.isFinite(m.geocode.lat)&&Number.isFinite(m.geocode.lon));
   if(!points.length)return;map=L.map(ref.current,{scrollWheelZoom:false});
   L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,referrerPolicy:'origin',attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).on('tileerror',()=>setFailed(true)).addTo(map);
   const coords:[number,number][]=[];
   points.forEach(m=>{const g=m.geocode;coords.push([g.lat,g.lon]);const content=document.createElement('div');
    // Provider/source text never enters an HTML-string popup.
    content.textContent=(m.role==='intended'?'Intended destination: ':'Reported delivery: ')+m.address+' · '+g.precision.replaceAll('_',' ')+' · '+m.source_id;
    L.circleMarker([g.lat,g.lon],{radius:m.role==='intended'?11:6,color:m.role==='intended'?'#214f40':'#be6c37',weight:3,fillOpacity:.55}).bindPopup(content).addTo(map!);
   });
   map.fitBounds(L.latLngBounds(coords).pad(.3),{maxZoom:points.some(m=>m.geocode.precision!=='building'&&m.geocode.precision!=='source_reported_gps')?12:16});
   map.invalidateSize();
  }catch{setFailed(true)}})();return()=>{disposed=true;map?.remove()};
 },[mentions]);
 return <><div ref={ref} className="delivery-map" aria-label="Interactive source-linked delivery location map"/>{failed&&<p role="status">Map tiles are unavailable. Preserved coordinates, source passages and comparisons remain below.</p>}<p className="fine">Green: intended destination. Orange: reported delivery. Overlapping markers do not establish the same building or actual receipt. Map data © OpenStreetMap contributors; geocoding by Photon.</p></>;
}

export function DeliveryLocation({current,api,changed,onSource}:{current:any;api:API;changed:()=>Promise<void>;onSource:(id:string)=>void}){
 const record=current.delivery_location,authorization=current.location_authorization?.mode||'off';
 const [mode,setMode]=React.useState(authorization),[ack,setAck]=React.useState(false),[busy,setBusy]=React.useState(false),[error,setError]=React.useState('');
 React.useEffect(()=>{setMode(authorization);setAck(false);setError('')},[current.id,authorization]);
 async function save(){setBusy(true);setError('');try{await api(`/cases/${current.id}/location-authorization`,'POST',{mode,acknowledged:ack});await changed()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 const plotted=(record?.mentions||[]).filter((m:any)=>m.role!=='other'&&m.geocode?.status==='resolved');
 return <section className="delivery-location" aria-label="Smart Delivery Location Verification"><div className="delivery-heading"><div><span className="eyebrow">SOURCE-BACKED DESTINATION CHECK</span><h3>Smart Delivery Location Verification</h3></div><span className={'delivery-state '+(record?.status==='LOCATION MISMATCH'?'conflict':'')}>{record?.status||'UNVERIFIED'}</span></div>
 <p>Addresses are compared automatically when evidence arrives. A delivery scan and delivery to the intended destination are different claims.</p>
 <details className="delivery-privacy"><summary>Location privacy · {labels[authorization]}</summary><p>Local comparison sends no address to a mapping provider. Optional Photon/OpenStreetMap lookups disclose only the extracted query: PIN code in area mode, or address with unit/floor details omitted in address mode. Documents and names are not intentionally sent; review your evidence for personal information inside an address. Map tiles disclose your IP and visible geographic area to OpenStreetMap. Public services are best effort. This authorization applies to future evidence in this case until disabled.</p>
 <label>Lookup preference<select value={mode} onChange={e=>setMode(e.target.value)}>{Object.entries(labels).map(([key,label])=><option value={key} key={key}>{String(label)}</option>)}</select></label>
 {mode!=='off'&&<label className="delivery-consent"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>I am authorized to share this location information with Photon/OpenStreetMap and load map tiles.</label>}
 <button className="secondary small" disabled={busy||(mode!=='off'&&!ack)} onClick={save}>{busy?'Saving…':'Save privacy preference'}</button>{error&&<p role="alert">{error}</p>}
 </details>
 {!record&&<p className="fine">Waiting for source-backed intended and reported delivery locations. Missing information will remain unverified.</p>}
 {record&&<><p className="fine">Checked {new Date(record.checked_at).toLocaleString()} · {record.extraction}. {record.extraction_error}</p>
 {record.comparisons.map((pair:any,i:number)=><div className="delivery-comparison" key={i}><strong>{pair.status}</strong>{pair.distance_m!==null&&<p>Approximate separation: {pair.distance_m>=1000?(pair.distance_m/1000).toFixed(1)+' km':pair.distance_m+' m'}. {pair.distance_label}</p>}<ul>{[...pair.supporting_facts,...pair.conflicting_facts,...pair.limitations].map((fact:string,j:number)=><li key={j}>{fact}</li>)}</ul></div>)}
 {plotted.length>0&&authorization!=='off'&&<DeliveryMap mentions={plotted}/>}
 {record.mentions.map((m:any)=><article className="delivery-source" key={m.id}><header><strong>{m.role==='intended'?'Intended destination':m.role==='reported_delivery'?'Reported delivery destination':'Other location · not compared'}</strong><button className="text-btn" onClick={()=>onSource(m.source_id)}>Inspect source {m.source_id}</button></header><p>{m.address}</p><blockquote>{m.quote}</blockquote><p>Source-supplied PIN: <strong>{m.explicit_postcode||'Not supplied'}</strong> · {m.source_authenticity}</p>
 {m.geocode?.status==='resolved'?<><p>{m.geocode.provider} · {m.geocode.precision.replaceAll('_',' ')}{m.geocode.precision==='postcode_area'?' · Approximate area location':''}</p><p className="fine">{m.geocode.lat.toFixed(6)}, {m.geocode.lon.toFixed(6)}. Decimal places do not establish accuracy. {m.geocode.uncertainty_basis}</p>{m.geocode.inferred_postcode&&<p>Map-provider PIN (inferred): {m.geocode.inferred_postcode}. This is not a PIN supplied by the carrier.</p>}{m.geocode.retrieved_at&&<p className="fine">Retrieved {new Date(m.geocode.retrieved_at).toLocaleString()}{m.geocode.cached?' · Preserved cached response':''}</p>}{m.geocode.response_sha256&&<details><summary>Integrity and provenance</summary><code>{m.geocode.response_sha256}</code><p>SHA-256 of preserved provider response. Source SHA-256: {m.source_sha256}</p><code>{m.quote_sha256}</code><p>SHA-256 of the original quoted passage.</p></details>}</>:<p className="fine">{m.geocode?.detail||'Not mapped; no precise location has been invented.'}</p>}</article>)}
 {record.limitations.map((text:string,i:number)=><p className="fine" key={i}>{text}</p>)}<details><summary>Verification record integrity</summary><code>{record.record_sha256}</code><p className="fine">Derived comparison record; source wording and reported authenticity remain unchanged.</p></details>
 </>}
 </section>;
}
